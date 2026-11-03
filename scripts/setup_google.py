#!/usr/bin/env python3
"""
Google Workspace Setup & Verification Tool (Gmail + Google Calendar)
for Hypatia PhD Monitor.

Supports:
  - Official Gmail REST API (OAuth 2.0 - token.json)
  - Google Calendar API (v3) - Automatic deadline event synchronization
  - Gmail App Password (SMTP over TLS - alternative)

Usage:
  python scripts/setup_google.py --status
  python scripts/setup_google.py --oauth
  python scripts/setup_google.py --sync-calendar
  python scripts/setup_google.py --test
"""

import os
import sys
import argparse
import warnings
from typing import Optional
from dotenv import load_dotenv

# Suppress harmless Python 3.9 EOL / LibreSSL urllib3 warnings from Google libraries
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*")

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from core.mailer import Mailer, DEFAULT_SENDER, DEFAULT_RECIPIENT, GMAIL_TOKEN_PATH, GMAIL_CREDS_PATH
from core.calendar_sync import CalendarSync, SCOPES, DEFAULT_CALENDAR_NAME


def _find_credentials_file() -> Optional[str]:
    """Finds credentials.json or any client_secret_*.json in project root."""
    if os.path.exists(GMAIL_CREDS_PATH):
        return GMAIL_CREDS_PATH
    import glob
    matches = glob.glob(os.path.join(PROJECT_ROOT, "client_secret*.json")) + glob.glob(os.path.join(PROJECT_ROOT, "*credentials*.json"))
    matches = [m for m in matches if not m.endswith("token.json")]
    if matches:
        return matches[0]
    return None


def check_status():
    print("\n=======================================================")
    print("  Hypatia - Google Workspace Configuration Status")
    print("=======================================================")
    print(f"  Google Account   : {DEFAULT_SENDER}")
    print(f"  Alert Recipient  : {DEFAULT_RECIPIENT}")
    print(f"  Credentials File : {GMAIL_CREDS_PATH} ({'FOUND' if os.path.exists(GMAIL_CREDS_PATH) else 'MISSING'})")
    print(f"  OAuth Token File : {GMAIL_TOKEN_PATH} ({'FOUND' if os.path.exists(GMAIL_TOKEN_PATH) else 'MISSING'})")

    # 1. Check Gmail API Status
    gmail_ready = False
    if os.path.exists(GMAIL_TOKEN_PATH):
        service = Mailer._get_gmail_service()
        if service:
            print("  [✓] Gmail REST API (OAuth 2.0) : AUTHENTICATED and READY.")
            gmail_ready = True
        else:
            print("  [!] Gmail REST API             : OAuth token invalid or lacks permission.")
    else:
        print("  [-] Gmail REST API             : Not authenticated yet.")

    # Check App Password fallback
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
    app_pw = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_APP_PASS")
    if app_pw:
        clean_pw = app_pw.replace(" ", "")
        masked = clean_pw[:3] + "*" * (len(clean_pw) - 6) + clean_pw[-3:]
        print(f"  [✓] Gmail App Password (SMTP)  : CONFIGURED ({masked}).")

    # 2. Check Google Calendar API Status
    cal_ready = False
    if os.path.exists(GMAIL_TOKEN_PATH):
        cal_service = CalendarSync.get_calendar_service()
        if cal_service:
            cal_id = CalendarSync.get_or_create_calendar(cal_service)
            print(f"  [✓] Google Calendar API (v3)   : AUTHENTICATED and ACTIVE.")
            print(f"      -> Target Calendar         : {cal_id}")
            cal_ready = True
        else:
            print("  [!] Google Calendar API (v3)   : Missing 'calendar.events' scope.")
            print("      Run: python scripts/setup_google.py --oauth to grant Calendar access.")
    else:
        print("  [-] Google Calendar API (v3)   : Not authenticated yet.")

    print("\n  Summary:")
    if gmail_ready and cal_ready:
        print("  -> Full Integration Active: Headless Gmail Alerts + Dynamic Google Calendar Deadlines.")
    elif gmail_ready:
        print("  -> Gmail is active, but Google Calendar needs re-authorization.")
        print("     Run: python scripts/setup_google.py --oauth")
    else:
        print("  -> Run 'python scripts/setup_google.py --oauth' to authenticate both Gmail and Calendar.")
    print("=======================================================\n")
    return gmail_ready and cal_ready


def setup_oauth():
    print("\n[*] Starting Google Workspace OAuth 2.0 Authorization...")
    creds_file = _find_credentials_file()
    if not creds_file or not os.path.exists(creds_file):
        print(f"\n[!] Error: No client secrets JSON found at '{GMAIL_CREDS_PATH}' or matching 'client_secret*.json'!")
        print("    Please follow these steps in Google Cloud Console:")
        print("    1. Go to https://console.cloud.google.com/apis/credentials")
        print("    2. Create an OAuth 2.0 Client ID (Application type: Desktop App).")
        print("    3. Enable both 'Gmail API' and 'Google Calendar API' under Enabled APIs.")
        print("    4. Download the JSON credentials file and place it in the project directory:")
        print(f"       {GMAIL_CREDS_PATH}")
        print("    5. Re-run: python scripts/setup_google.py --oauth\n")
        return False

    # Secure credentials file permissions
    try:
        os.chmod(creds_file, 0o600)
    except Exception:
        pass

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
        print(f"[*] Loaded credentials from: {os.path.basename(creds_file)}")
        print(f"[*] Requesting scopes: Gmail Send + Google Calendar Events")
        print("[*] Opening local browser to authenticate with Google...")
        creds = flow.run_local_server(port=0)

        with open(GMAIL_TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
        os.chmod(GMAIL_TOKEN_PATH, 0o600)

        print(f"[✓] Authentication successful! Saved updated token to {os.path.basename(GMAIL_TOKEN_PATH)}")
        print("    Permissions set to 600 (owner only). File is ignored by git.")
        print("    Hypatia can now dispatch emails and populate Google Calendar deadlines automatically.\n")
        return True
    except Exception as e:
        print(f"[!] OAuth setup failed: {e}")
        return False


def set_app_password(password: str):
    clean = password.replace(" ", "").strip()
    env_path = os.path.join(PROJECT_ROOT, ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GMAIL_APP_PASSWORD=") or line.startswith("GMAIL_APP_PASS="):
                    lines.append(f"GMAIL_APP_PASSWORD={clean}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"GMAIL_APP_PASSWORD={clean}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"[✓] Successfully saved GMAIL_APP_PASSWORD in {env_path}\n")
    return True


def run_test(recipient: str = DEFAULT_RECIPIENT):
    print("\n=======================================================")
    print("  Running Hypatia Google Integration Verification Test")
    print("=======================================================\n")

    sample_offering = {
        "id": 9999,
        "source": "inspirehep",
        "title": "PhD Position in Theoretical Quantum Physics & QCD Witness Circuits",
        "institution": "Stockholm University",
        "location": "Stockholm, Sweden",
        "regions": ["Scandinavia", "Europe"],
        "deadline": "2026-12-15",
        "url": "https://example.com/phd-test",
        "inspire_url": "https://inspirehep.net/jobs/9999999"
    }
    sample_eval = {
        "total_score": 9.3,
        "score_academic": 9.5,
        "score_geography": 10.0,
        "score_financial": 8.5,
        "compensation_detected": "Swedish Doctoral Salary Scale (~33,000 SEK/mo)",
        "topics_mentioned": ["Quantum witness circuits", "QCD hadronization", "Lund string model"],
        "evaluation_summary": "Top-tier match testing end-to-end email alert dispatch and calendar deadline synchronization."
    }

    # 1. Test Email Dispatch
    print(f"[*] 1/2: Testing Email Dispatch to {recipient}...")
    email_success = Mailer.send_phd_alert(sample_offering, sample_eval, recipient=recipient)
    if email_success:
        print(f"[✓] Email alert successfully dispatched via Gmail API to {recipient}!")
    else:
        print(f"[!] Email could not be sent directly (queued to outbox).")

    # 2. Test Google Calendar Sync
    print("\n[*] 2/2: Testing Google Calendar Event Creation...")
    cal_id = CalendarSync.sync_offering(sample_offering, sample_eval)
    if cal_id:
        print(f"[✓] Google Calendar event successfully created for deadline 2026-12-15 (Event ID: {cal_id})!")
    else:
        print("[!] Google Calendar event creation skipped or failed (check permissions).")

    print("\n=======================================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configure Google Services (Gmail + Calendar) for Hypatia")
    parser.add_argument("--status", action="store_true", help="Check current Gmail and Google Calendar status")
    parser.add_argument("--oauth", action="store_true", help="Run interactive OAuth authorization (Gmail + Calendar)")
    parser.add_argument("--sync-calendar", action="store_true", help="Retroactively sync all high-scoring positions in DB to Google Calendar")
    parser.add_argument("--app-password", type=str, help="Configure a 16-character Google App Password in .env")
    parser.add_argument("--test", action="store_true", help="Send test email alert and create test calendar event")
    parser.add_argument("--to", default=DEFAULT_RECIPIENT, help="Recipient address for test email")
    args = parser.parse_args()

    if args.oauth:
        setup_oauth()
    elif args.sync_calendar:
        CalendarSync.sync_all_high_scoring()
    elif args.app_password:
        set_app_password(args.app_password)
    elif args.test:
        run_test(args.to)
    else:
        check_status()
