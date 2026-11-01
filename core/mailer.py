import os
import re
import json
import glob
import shutil
import base64
import smtplib
import subprocess
import warnings
from datetime import date, datetime
from dateutil import parser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Suppress harmless Python 3.9 EOL / LibreSSL urllib3 warnings from Google libraries
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*")

load_dotenv()

DEFAULT_SENDER = os.getenv("GMAIL_SENDER", "daniel.programa.cometa@gmail.com")
DEFAULT_RECIPIENT = os.getenv("NOTIFICATION_EMAIL", "danielgarciavillacanas@protonmail.com")

OUTBOX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outbox")
SENT_DIR = os.path.join(OUTBOX_DIR, "sent")
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "token.json"))
GMAIL_CREDS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credentials.json"))

# Ensure outbox directories exist
os.makedirs(OUTBOX_DIR, exist_ok=True)
os.makedirs(SENT_DIR, exist_ok=True)


class Mailer:
    """
    Dispatches rich email alerts for high-scoring PhD vacancies containing
    full match details, evaluation scores, and complete application/cover letter guidance.
    
    Supported dispatch backends:
      1. Gmail API (OAuth 2.0 REST API - Headless, works when screen is locked/sleeping)
      2. Gmail SMTP (via App Password - Headless, zero-GCP-console alternative)
      3. Custom SMTP (Generic host/port/user/pass)
      4. macOS Apple Mail via AppleScript (fallback only if explicitly enabled)
    
    Persistent Outbox Queue:
      - If dispatch fails (offline, rate limited, credentials pending), alerts are queued to outbox/*.json.
      - Automatically flushes queued emails once credentials or network become available.
    """

    @staticmethod
    def get_days_until_deadline(deadline_str: Optional[str]) -> Optional[int]:
        """Calculates days remaining until the deadline."""
        if not deadline_str or "unspecified" in str(deadline_str).lower():
            return None
        deadline_str = str(deadline_str).strip()
        try:
            if re.match(r"^\d{4}-\d{2}-\d{2}$", deadline_str):
                target_date = parser.isoparse(deadline_str).date()
            else:
                target_date = parser.parse(deadline_str, fuzzy=True, dayfirst=True).date()
            return (target_date - date.today()).days
        except Exception:
            return None

    @staticmethod
    def get_outbox_stats() -> Dict[str, int]:
        """Returns counts of pending and sent alerts in outbox."""
        pending_files = [f for f in glob.glob(os.path.join(OUTBOX_DIR, "*.json")) if not f.endswith(".gitkeep")]
        sent_files = [f for f in glob.glob(os.path.join(SENT_DIR, "*.json")) if not f.endswith(".gitkeep")]
        return {"pending": len(pending_files), "sent": len(sent_files)}

    @staticmethod
    def queue_alert(
        offering: Dict[str, Any],
        evaluation: Dict[str, Any],
        guide_text: str,
        subject: str,
        plain_body: str,
        html_body: str,
        recipient: str = DEFAULT_RECIPIENT
    ) -> str:
        """
        Saves an alert payload into the persistent outbox queue.
        Returns the path to the queued JSON file.
        """
        offering_id = offering.get("id") or "untracked"
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r"[^\w\-]", "_", offering.get("title", "phd")[:30]).strip("_")
        filename = f"{timestamp_str}_{offering_id}_{safe_title}.json"
        queue_path = os.path.join(OUTBOX_DIR, filename)

        payload = {
            "id": filename[:-5],
            "created_at": datetime.now().isoformat(),
            "offering_id": offering_id,
            "title": offering.get("title"),
            "institution": offering.get("institution"),
            "deadline": offering.get("deadline"),
            "recipient": recipient,
            "subject": subject,
            "plain_body": plain_body,
            "html_body": html_body,
            "attempts": 0,
            "status": "pending",
            "last_error": None,
            "offering": offering,
            "evaluation": evaluation
        }

        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"[Outbox] Alert queued to outbox: {filename}")
        return queue_path

    @staticmethod
    def _archive_sent_alert(alert_id: str, payload: Dict[str, Any]):
        """Archives a successfully sent alert in outbox/sent/."""
        sent_path = os.path.join(SENT_DIR, f"{alert_id}.json")
        payload["status"] = "sent"
        payload["sent_at"] = datetime.now().isoformat()
        with open(sent_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _get_gmail_service():
        """
        Builds and returns an authenticated Google API client for Gmail
        using OAuth 2.0 (token.json).
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = None
            if os.path.exists(GMAIL_TOKEN_PATH):
                creds = Credentials.from_authorized_user_file(
                    GMAIL_TOKEN_PATH,
                    scopes=["https://www.googleapis.com/auth/gmail.send"]
                )

            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(GMAIL_TOKEN_PATH, "w", encoding="utf-8") as token_file:
                        token_file.write(creds.to_json())
                    os.chmod(GMAIL_TOKEN_PATH, 0o600)
                    print("[Mailer] Refreshed Gmail API OAuth token.")
                except Exception as refresh_err:
                    print(f"[Mailer] Failed to refresh Gmail OAuth token: {refresh_err}")
                    creds = None

            if creds and creds.valid:
                return build("gmail", "v1", credentials=creds)
            return None
        except Exception as e:
            print(f"[Mailer] Error initializing Gmail API: {e}")
            return None

    @staticmethod
    def _send_gmail_api(recipient: str, subject: str, plain_text: str, html_text: str, sender: str = DEFAULT_SENDER) -> bool:
        """Dispatches an email alert via the official Gmail REST API."""
        try:
            service = Mailer._get_gmail_service()
            if not service:
                return False

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient

            msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_text, "html", "utf-8"))

            raw_bytes = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
            body = {"raw": raw_bytes}

            service.users().messages().send(userId="me", body=body).execute()
            print(f"[✓] Email alert successfully sent via Gmail API to {recipient}!")
            return True
        except Exception as e:
            print(f"[Mailer] Gmail API dispatch failed: {e}")
            return False

    @staticmethod
    def _send_gmail_smtp(recipient: str, subject: str, plain_text: str, html_text: str, sender: str, app_password: str) -> bool:
        """Dispatches an email via Gmail SMTP using a 16-character App Password."""
        clean_pass = app_password.replace(" ", "")
        return Mailer._send_smtp(
            recipient=recipient,
            subject=subject,
            plain_text=plain_text,
            html_text=html_text,
            host="smtp.gmail.com",
            port=587,
            user=sender,
            password=clean_pass
        )

    @staticmethod
    def _send_smtp(recipient: str, subject: str, plain_text: str, html_text: str, host: str, port: int, user: str, password: str) -> bool:
        """Dispatches an email alert via generic SMTP with STARTTLS."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = user
            msg["To"] = recipient

            msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_text, "html", "utf-8"))

            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(user, [recipient], msg.as_string())

            print(f"[✓] Email alert successfully sent via SMTP ({host}) to {recipient}!")
            return True
        except Exception as e:
            print(f"[Mailer] SMTP send failed ({host}): {e}")
            return False

    @staticmethod
    def _send_apple_mail(recipient: str, subject: str, content: str) -> bool:
        """Dispatches via Apple Mail via AppleScript (fallback only)."""
        safe_subject = subject.replace('\\', '\\\\').replace('"', '\\"')
        safe_content = content.replace('\\', '\\\\').replace('"', '\\"')

        script = f'''
        tell application "Mail"
            set newMessage to make new outgoing message with properties {{subject:"{safe_subject}", content:"{safe_content}", visible:false}}
            tell newMessage
                make new to recipient at end of to recipients with properties {{address:"{recipient}"}}
                send
            end tell
        end tell
        '''
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                print(f"[✓] Email alert successfully dispatched via Apple Mail to {recipient}!")
                return True
            else:
                print(f"[Mailer] Apple Mail dispatch error: {res.stderr.strip()}")
                return False
        except Exception as e:
            print(f"[Mailer] Apple Mail execution error: {e}")
            return False

    @staticmethod
    def _dispatch_raw(recipient: str, subject: str, plain_body: str, html_body: str) -> bool:
        """
        Attempts direct delivery through the available backends in order of preference:
          1. Gmail REST API (OAuth 2.0 / token.json)
          2. Gmail SMTP (App Password via GMAIL_APP_PASSWORD)
          3. Custom SMTP (SMTP_HOST, SMTP_USER, SMTP_PASS)
          4. macOS Apple Mail (only if USE_APPLE_MAIL=true)
        """
        # 1. Check Gmail REST API
        if os.path.exists(GMAIL_TOKEN_PATH):
            if Mailer._send_gmail_api(recipient, subject, plain_body, html_body, sender=DEFAULT_SENDER):
                return True

        # 2. Check Gmail SMTP (App Password)
        gmail_app_pw = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_APP_PASS")
        if gmail_app_pw:
            if Mailer._send_gmail_smtp(recipient, subject, plain_body, html_body, sender=DEFAULT_SENDER, app_password=gmail_app_pw):
                return True

        # 3. Check Custom SMTP
        smtp_host = os.getenv("SMTP_HOST")
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        if smtp_host and smtp_user and smtp_pass:
            if Mailer._send_smtp(recipient, subject, plain_body, html_body, smtp_host, smtp_port, smtp_user, smtp_pass):
                return True

        # 4. Fallback: Apple Mail (disabled by default for headless stability)
        use_apple_mail = os.getenv("USE_APPLE_MAIL", "false").lower() in ("true", "1", "yes")
        if use_apple_mail:
            print(f"[Mailer] Attempting fallback dispatch via Apple Mail...")
            if Mailer._send_apple_mail(recipient, subject, plain_body):
                return True

        return False

    @staticmethod
    def send_phd_alert(
        offering: Dict[str, Any],
        evaluation: Dict[str, Any],
        guide_path: Optional[str] = None,
        recipient: str = DEFAULT_RECIPIENT,
        queue_on_failure: bool = True
    ) -> bool:
        """
        Main entry point to dispatch a PhD vacancy alert.
        If email cannot be sent immediately, it is automatically saved to the persistent outbox queue.
        """
        title = offering.get('title', 'PhD Opportunity')
        institution = offering.get('institution', 'University')
        total_score = evaluation.get('total_score', 0.0)

        days_left = Mailer.get_days_until_deadline(offering.get('deadline'))
        is_urgent = days_left is not None and 0 <= days_left <= 14

        urgent_tag = f"🚨 [URGENT - {days_left}d Left] " if is_urgent else ""
        subject = f"{urgent_tag}🎓 [{total_score:.1f}/10 Match] {title} - {institution}"

        guide_text = ""
        if guide_path and os.path.exists(guide_path):
            with open(guide_path, 'r', encoding='utf-8') as f:
                guide_text = f.read()

        plain_body = Mailer._build_plain_text(offering, evaluation, guide_text, is_urgent, days_left)
        html_body = Mailer._build_html(offering, evaluation, guide_text, is_urgent, days_left)

        # Attempt immediate dispatch
        sent = Mailer._dispatch_raw(recipient, subject, plain_body, html_body)

        offering_id = offering.get("id") or "untracked"
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r"[^\w\-]", "_", offering.get("title", "phd")[:30]).strip("_")
        alert_id = f"{timestamp_str}_{offering_id}_{safe_title}"

        alert_payload = {
            "id": alert_id,
            "created_at": datetime.now().isoformat(),
            "offering_id": offering_id,
            "title": title,
            "institution": institution,
            "deadline": offering.get("deadline"),
            "recipient": recipient,
            "subject": subject,
            "plain_body": plain_body,
            "html_body": html_body,
            "attempts": 1 if sent else 0,
            "status": "sent" if sent else "pending",
            "last_error": None if sent else "Immediate dispatch failed or credentials not configured",
            "offering": offering,
            "evaluation": evaluation
        }

        if sent:
            Mailer._archive_sent_alert(alert_id, alert_payload)
            return True

        if queue_on_failure:
            queue_file = os.path.join(OUTBOX_DIR, f"{alert_id}.json")
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump(alert_payload, f, indent=2, ensure_ascii=False)
            print(f"[Outbox] Alert safely stored in outbox queue: {queue_file}")
            print("         Will be automatically dispatched on next run or via 'python core/mailer.py --flush'.")
            return False

        return False

    @staticmethod
    def flush_outbox(recipient_override: Optional[str] = None) -> Dict[str, int]:
        """
        Iterates through all pending JSON alerts in the outbox directory and
        attempts to dispatch them via active email channels.
        Successfully sent alerts are moved to outbox/sent/.
        """
        pending_files = sorted(glob.glob(os.path.join(OUTBOX_DIR, "*.json")))
        pending_files = [f for f in pending_files if not f.endswith(".gitkeep")]

        stats = {
            "pending_found": len(pending_files),
            "sent": 0,
            "failed": 0,
            "remaining": len(pending_files)
        }

        if not pending_files:
            return stats

        print(f"[Outbox] Found {len(pending_files)} pending alert(s) in outbox. Attempting dispatch...")

        for queue_file in pending_files:
            try:
                with open(queue_file, "r", encoding="utf-8") as f:
                    alert_data = json.load(f)
            except Exception as read_err:
                print(f"[Outbox] Corrupt queue file {queue_file}: {read_err}")
                stats["failed"] += 1
                continue

            target_recipient = recipient_override or alert_data.get("recipient", DEFAULT_RECIPIENT)
            subject = alert_data.get("subject", "Hypatia PhD Alert")
            plain_body = alert_data.get("plain_body", "")
            html_body = alert_data.get("html_body", "")

            sent = Mailer._dispatch_raw(target_recipient, subject, plain_body, html_body)

            if sent:
                stats["sent"] += 1
                stats["remaining"] -= 1
                alert_data["status"] = "sent"
                alert_data["sent_at"] = datetime.now().isoformat()
                alert_data["attempts"] = alert_data.get("attempts", 0) + 1
                
                # Move to sent archive
                sent_path = os.path.join(SENT_DIR, os.path.basename(queue_file))
                with open(sent_path, "w", encoding="utf-8") as sf:
                    json.dump(alert_data, sf, indent=2, ensure_ascii=False)
                try:
                    os.remove(queue_file)
                except OSError:
                    pass
                print(f"[Outbox] Successfully flushed & archived: {os.path.basename(queue_file)}")
            else:
                stats["failed"] += 1
                alert_data["attempts"] = alert_data.get("attempts", 0) + 1
                alert_data["last_attempt"] = datetime.now().isoformat()
                alert_data["last_error"] = "Dispatch failed or email backend unavailable"
                with open(queue_file, "w", encoding="utf-8") as qf:
                    json.dump(alert_data, qf, indent=2, ensure_ascii=False)
                print(f"[Outbox] Failed to flush: {os.path.basename(queue_file)} (Attempts: {alert_data['attempts']})")

        return stats

    @staticmethod
    def _build_plain_text(offering: Dict[str, Any], evaluation: Dict[str, Any], guide_text: str, is_urgent: bool = False, days_left: Optional[int] = None) -> str:
        urgent_banner = ""
        if is_urgent:
            urgent_banner = f"""
**********************************************************************
  🚨 URGENT: ONLY {days_left} DAYS LEFT UNTIL APPLICATION DEADLINE!
  Deadline Date: {offering.get('deadline')}
**********************************************************************
"""
        source = offering.get("source", "portal")
        primary_url = offering.get("url", "")
        inspire_url = offering.get("inspire_url", "")
        external_url = offering.get("external_url", "")

        url_lines = []
        if source == "inspirehep":
            if inspire_url:
                url_lines.append(f"INSPIREHEP RECORD: {inspire_url}")
            if primary_url and primary_url != inspire_url:
                url_lines.append(f"DIRECT DEPARTMENT LINK: {primary_url}")
        elif source == "quantiki":
            url_lines.append(f"QUANTIKI LISTING: {primary_url}")
            if external_url and external_url != primary_url:
                url_lines.append(f"EMPLOYER WEB PAGE: {external_url}")
        else:
            url_lines.append(f"VACANCY URL: {primary_url}")

        url_block = "\n".join(url_lines)

        return f"""======================================================================
  HYPATIA PHD MONITOR - HIGH FIT POSITION ALERT
======================================================================
{urgent_banner}
POSITION: {offering.get('title')}
INSTITUTION: {offering.get('institution')}
LOCATION: {offering.get('location')} ({', '.join(offering.get('regions', []))})
APPLICATION DEADLINE: {offering.get('deadline')} {'(URGENT: ' + str(days_left) + ' days remaining)' if is_urgent else ''}

{url_block}

----------------------------------------------------------------------
MATCH EVALUATION:
----------------------------------------------------------------------
Total Score: {evaluation.get('total_score', 0):.1f} / 10.0
- Academic Fit: {evaluation.get('score_academic', 0):.1f} / 10.0
- Geography:    {evaluation.get('score_geography', 0):.1f} / 10.0
- Financials:   {evaluation.get('score_financial', 0):.1f} / 10.0

Topics: {', '.join(evaluation.get('topics_mentioned', []))}
Compensation: {evaluation.get('compensation_detected') or 'Standard institutional contract'}

EVALUATOR REASONING:
{evaluation.get('evaluation_summary')}

----------------------------------------------------------------------
APPLICATION DOSSIER & POINTERS:
----------------------------------------------------------------------
{guide_text}

======================================================================
Generated by Hypatia Autonomous PhD Opportunity Monitor
"""

    @staticmethod
    def _build_html(offering: Dict[str, Any], evaluation: Dict[str, Any], guide_text: str, is_urgent: bool = False, days_left: Optional[int] = None) -> str:
        html_guide = guide_text.replace("\n", "<br/>")

        urgent_html = ""
        if is_urgent:
            urgent_html = f"""
            <div style="background: #fef2f2; border: 2px solid #ef4444; border-radius: 8px; padding: 16px; margin-bottom: 24px; color: #991b1b;">
              <strong style="font-size: 16px;">🚨 URGENT DEADLINE NOTICE:</strong>
              <div style="margin-top: 4px; font-size: 14px;">
                Only <strong>{days_left} days remaining</strong> to submit your application for this position (Deadline: <strong>{offering.get('deadline')}</strong>). Immediate preparation recommended.
              </div>
            </div>
            """

        urgent_badge = f'<span class="badge" style="background: #ef4444; color: #ffffff; margin-left: 8px;">🚨 URGENT ({days_left}d Left)</span>' if is_urgent else ""

        source = offering.get("source", "portal")
        primary_url = offering.get("url", "#")
        inspire_url = offering.get("inspire_url", "")
        external_url = offering.get("external_url", "")

        buttons_html = []
        if source == "inspirehep":
            if inspire_url:
                buttons_html.append(f'<a class="button" href="{inspire_url}">View on InspireHEP &rarr;</a>')
            if primary_url and primary_url != inspire_url:
                buttons_html.append(f'<a class="button" style="background: #047857; margin-left: 8px;" href="{primary_url}">Direct Department Application &rarr;</a>')
        elif source == "quantiki":
            buttons_html.append(f'<a class="button" href="{primary_url}">View on Quantiki &rarr;</a>')
            if external_url and external_url != primary_url:
                buttons_html.append(f'<a class="button" style="background: #047857; margin-left: 8px;" href="{external_url}">Employer Webpage &rarr;</a>')
        else:
            buttons_html.append(f'<a class="button" href="{primary_url}">View Official Vacancy &rarr;</a>')

        action_buttons = "\n".join(buttons_html)

        return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1f2937; margin: 0; padding: 20px; }}
    .container {{ max-width: 720px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }}
    .header {{ background: #1e3a8a; color: #ffffff; padding: 24px; }}
    .header h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
    .badge {{ display: inline-block; background: #fbbf24; color: #1e3a8a; font-weight: bold; padding: 4px 10px; border-radius: 9999px; font-size: 14px; }}
    .content {{ padding: 24px; }}
    .score-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    .score-table th, .score-table td {{ border: 1px solid #e5e7eb; padding: 10px; text-align: left; }}
    .score-table th {{ background: #f3f4f6; }}
    .button {{ display: inline-block; background: #2563eb; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; margin-top: 10px; }}
    .section-title {{ font-size: 18px; font-weight: 700; color: #1e3a8a; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; margin-top: 24px; }}
    .guide-box {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 18px; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge">{evaluation.get('total_score', 0):.1f} / 10 Match Score</span>
      {urgent_badge}
      <h1 style="margin-top: 10px;">{offering.get('title')}</h1>
      <p style="margin: 0; opacity: 0.9;">{offering.get('institution')} &bull; Deadline: <strong>{offering.get('deadline')}</strong></p>
    </div>
    
    <div class="content">
      {urgent_html}
      
      <p><strong>Location:</strong> {offering.get('location')} ({', '.join(offering.get('regions', []))})</p>
      <p><strong>Compensation:</strong> {evaluation.get('compensation_detected') or 'Standard institutional funding'}</p>
      
      <div style="margin-top: 12px; margin-bottom: 20px;">
        {action_buttons}
      </div>
      
      <div class="section-title">Evaluation Breakdown</div>
      <table class="score-table">
        <tr><th>Metric</th><th>Score</th></tr>
        <tr><td>Academic Fit (QCD / Quantum Computing)</td><td><strong>{evaluation.get('score_academic', 0):.1f} / 10.0</strong></td></tr>
        <tr><td>Geography (Scandinavia & EU Priority)</td><td><strong>{evaluation.get('score_geography', 0):.1f} / 10.0</strong></td></tr>
        <tr><td>Financials (&gt; €2,000 / month floor)</td><td><strong>{evaluation.get('score_financial', 0):.1f} / 10.0</strong></td></tr>
        <tr style="background: #eff6ff;"><td><strong>Total Weighted Score</strong></td><td><strong style="color: #1e3a8a;">{evaluation.get('total_score', 0):.1f} / 10.0</strong></td></tr>
      </table>
      
      <p><strong>Evaluator Rationale:</strong><br/>{evaluation.get('evaluation_summary')}</p>
      
      <div class="section-title">Application Dossier & Guidance</div>
      <div class="guide-box">
        {html_guide}
      </div>
    </div>
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hypatia Mailer & Outbox Queue")
    parser.add_argument("--to", default=DEFAULT_RECIPIENT, help="Recipient email address")
    parser.add_argument("--test", action="store_true", help="Send a test email alert")
    parser.add_argument("--flush", action="store_true", help="Flush all pending emails in outbox")
    parser.add_argument("--status", action="store_true", help="Check outbox queue status")
    parser.add_argument("--urgent", action="store_true", help="Simulate urgent deadline (< 14 days)")
    args = parser.parse_args()

    stats = Mailer.get_outbox_stats()
    print(f"[Outbox Status] Pending: {stats['pending']} | Sent Archived: {stats['sent']}")

    if args.flush:
        print(f"Flushing outbox to {args.to}...")
        result = Mailer.flush_outbox(recipient_override=args.to)
        print(f"Flush Result: {result}")

    elif args.test:
        deadline_test = "2026-11-08" if args.urgent else "2026-12-15"
        sample_offering = {
            "id": 999,
            "source": "inspirehep",
            "title": "PhD Position in Exclusive π0 Muoproduction at COMPASS (CERN)",
            "institution": "Czech Technical University in Prague",
            "location": "Prague, Czechia",
            "regions": ["Europe"],
            "deadline": deadline_test,
            "url": "https://fjfi.cvut.cz/sites/default/files/documents/2026-10/PhD_Meson_COMPASSen_1.pdf",
            "inspire_url": "https://inspirehep.net/jobs/3220801"
        }
        sample_eval = {
            "total_score": 8.5,
            "score_academic": 8.0,
            "score_geography": 9.0,
            "score_financial": 8.5,
            "compensation_detected": "Standard European Research Fellowship (> €2,200/mo)",
            "topics_mentioned": ["Hadron physics", "QCD phenomenology", "GPD models", "CERN"],
            "evaluation_summary": "Strong synergy with non-perturbative hadron physics and QCD phenomenology."
        }
        print(f"Sending test alert to {args.to}...")
        Mailer.send_phd_alert(sample_offering, sample_eval, recipient=args.to)
