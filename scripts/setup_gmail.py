#!/usr/bin/env python3
"""
Gmail Setup & Verification Tool for Hypatia PhD Monitor.

Supports two headless authentication methods:
  Method 1: Official Gmail REST API (OAuth 2.0 - token.json)
  Method 2: Gmail App Password (SMTP over TLS - zero-GCP-console alternative)

Usage:
  python scripts/setup_gmail.py --status
  python scripts/setup_gmail.py --oauth
  python scripts/setup_gmail.py --app-password "xxxx xxxx xxxx xxxx"
  python scripts/setup_gmail.py --test
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
from core.calendar_sync import CalendarSync, SCOPES


def check_status():
    print("\n=======================================================")
    print("  Hypatia - Gmail Configuration Status")
    print("=======================================================")
    print(f"  Sender Account   : {DEFAULT_SENDER}")
    print(f"  Alert Recipient  : {DEFAULT_RECIPIENT}")
    print(f"  Credentials File : {GMAIL_CREDS_PATH} ({'FOUND' if os.path.exists(GMAIL_CREDS_PATH) else 'MISSING'})")
    print(f"  OAuth Token File : {GMAIL_TOKEN_PATH} ({'FOUND' if os.path.exists(GMAIL_TOKEN_PATH) else 'MISSING'})")

    # Check OAuth validity
    api_ready = False
    if os.path.exists(GMAIL_TOKEN_PATH):
        service = Mailer._get_gmail_service()
        if service:
            print("  [✓] Gmail REST API (OAuth 2.0) is AUTHENTICATED and READY.")
            api_ready = True
        else:
            print("  [!] OAuth token exists but is invalid or expired. Run: python scripts/setup_gmail.py --oauth")
    else:
        print("  [-] Gmail REST API not authenticated yet.")

    # Check App Password
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
    app_pw = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_APP_PASS")
    smtp_ready = False
    if app_pw:
        clean_pw = app_pw.replace(" ", "")
        masked = clean_pw[:3] + "*" * (len(clean_pw) - 6) + clean_pw[-3:]
        print(f"  [✓] Gmail App Password is CONFIGURED ({masked}).")
        smtp_ready = True
    else:
        print("  [-] Gmail App Password not configured in .env.")

    print("\n  Summary:")
    if api_ready:
        print("  -> Active Transport: Gmail REST API (Headless HTTPS)")
    elif smtp_ready:
        print("  -> Active Transport: Gmail SMTP with App Password (Headless TLS)")
    else:
        print("  -> No Gmail transport active yet. Outbox queue will cache alerts until configured.")
        print("\n  To configure:")
        print("    1. For Gmail API: Place credentials.json in project root and run:")
        print("         python scripts/setup_gmail.py --oauth")
        print("    2. For App Password: Create at https://myaccount.google.com/apppasswords and run:")
        print("         python scripts/setup_gmail.py --app-password <16_character_code>")
    print("=======================================================\n")
    return api_ready or smtp_ready


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


def setup_oauth():
    print("\n[*] Starting Gmail OAuth 2.0 Setup...")
    creds_file = _find_credentials_file()
    if not creds_file or not os.path.exists(creds_file):
        print(f"\n[!] Error: No client secrets JSON found at '{GMAIL_CREDS_PATH}' or matching 'client_secret*.json'!")
        print("    Please follow these steps in Google Cloud Console:")
        print("    1. Go to https://console.cloud.google.com/apis/credentials")
        print("    2. Create an OAuth 2.0 Client ID (Application type: Desktop App).")
        print("    3. Enable 'Gmail API' under Enabled APIs & Services.")
        print("    4. Download the JSON credentials file and place it in the project directory:")
        print(f"       {GMAIL_CREDS_PATH}")
        print("    5. Re-run: python scripts/setup_gmail.py --oauth\n")
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
        print("[*] Opening local browser to authenticate with Google...")
        creds = flow.run_local_server(port=0)

        with open(GMAIL_TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
        os.chmod(GMAIL_TOKEN_PATH, 0o600)

        print(f"[✓] Authentication successful! Saved OAuth credentials to {os.path.basename(GMAIL_TOKEN_PATH)}")
        print("    Permissions set to 600 (owner only). File is ignored by git.")
        print("    Hypatia can now dispatch email alerts headlessly even when your Mac is locked.\n")
        return True
    except Exception as e:
        print(f"[!] OAuth setup failed: {e}")
        return False


def set_app_password(password: str):
    clean = password.replace(" ", "").strip()
    if len(clean) != 16:
        print(f"[!] Warning: Google App Passwords are usually 16 characters (got {len(clean)}).")

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

    print(f"[✓] Successfully saved GMAIL_APP_PASSWORD in {env_path}")
    print("    Hypatia can now dispatch email alerts headlessly via Gmail SMTP.\n")
    return True


def send_test_email(recipient: str = DEFAULT_RECIPIENT):
    print(f"\n[*] Sending test PhD alert to {recipient}...")
    sample_offering = {
        "id": 999,
        "source": "inspirehep",
        "title": "PhD Position in Exclusive π0 Muoproduction at COMPASS (CERN)",
        "institution": "Czech Technical University in Prague",
        "location": "Prague, Czechia",
        "regions": ["Europe"],
        "deadline": "2026-12-15",
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
        "evaluation_summary": "Test dispatch confirming headless delivery without AppleScript/Mail.app."
    }
    sample_guide = "## Verification Test\nThis test message confirms that Hypatia can dispatch alerts headlessly."

    temp_guide = os.path.join(PROJECT_ROOT, "scratch", "test_guide.md")
    os.makedirs(os.path.dirname(temp_guide), exist_ok=True)
    with open(temp_guide, "w", encoding="utf-8") as f:
        f.write(sample_guide)

    success = Mailer.send_phd_alert(sample_offering, sample_eval, guide_path=temp_guide, recipient=recipient)
    if success:
        print(f"[✓] Test email successfully delivered to {recipient}!")
    else:
        print(f"[!] Email could not be sent directly. It was queued to the outbox.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configure Gmail for Hypatia PhD Monitor")
    parser.add_argument("--status", action="store_true", help="Check current Gmail configuration status")
    parser.add_argument("--oauth", action="store_true", help="Run interactive OAuth 2.0 authorization (browser)")
    parser.add_argument("--app-password", type=str, help="Configure a 16-character Google App Password in .env")
    parser.add_argument("--test", action="store_true", help="Send a test alert to verify dispatch")
    parser.add_argument("--to", default=DEFAULT_RECIPIENT, help="Recipient address for test email")
    args = parser.parse_args()

    if args.oauth:
        setup_oauth()
    elif args.app_password:
        set_app_password(args.app_password)
    elif args.test:
        send_test_email(args.to)
    else:
        check_status()
