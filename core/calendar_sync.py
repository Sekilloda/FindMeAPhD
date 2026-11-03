import os
import re
import json
import sqlite3
import warnings
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List
from dateutil import parser
from dotenv import load_dotenv

# Suppress harmless Python 3.9 EOL / LibreSSL urllib3 warnings from Google libraries
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*")

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "db", "system.db")
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", os.path.join(PROJECT_ROOT, "token.json"))
GMAIL_CREDS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", os.path.join(PROJECT_ROOT, "credentials.json"))
DEFAULT_CALENDAR_NAME = os.getenv("GOOGLE_CALENDAR_NAME", "🎓 Hypatia PhD Deadlines")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar"
]


class CalendarSync:
    """
    Manages synchronization of high-scoring PhD application deadlines to Google Calendar.
    Provides a dynamic, always-accurate point of reference so upcoming deadlines
    are clearly visible on macOS, iOS/Android, and Google Calendar web.
    """

    @staticmethod
    def parse_deadline(deadline_str: Optional[str]) -> Optional[date]:
        """
        Parses variable portal deadline formats into a Python date object.
        Supports ISO (YYYY-MM-DD), natural text ('Monday, September 28, 2026'),
        dot notation ('03.Nov.2026'), and European formats.
        Returns None for missing or 'unspecified' deadlines.
        """
        if not deadline_str:
            return None
        clean = str(deadline_str).strip()
        if not clean or "unspecified" in clean.lower():
            return None
        try:
            if re.match(r"^\d{4}-\d{2}-\d{2}$", clean):
                return parser.isoparse(clean).date()
            return parser.parse(clean, fuzzy=True, dayfirst=True).date()
        except Exception:
            return None

    @staticmethod
    def get_calendar_service():
        """
        Returns an authenticated Google Calendar API client (v3) using token.json.
        Returns None if token is missing, expired, or lacks calendar permissions.
        """
        if not os.path.exists(GMAIL_TOKEN_PATH):
            return None

        try:
            with open(GMAIL_TOKEN_PATH, "r", encoding="utf-8") as f:
                token_data = json.load(f)
                granted_scopes = set(token_data.get("scopes", []))
                if not any("calendar" in s for s in granted_scopes):
                    return None

            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, scopes=SCOPES)

            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(GMAIL_TOKEN_PATH, "w", encoding="utf-8") as token_file:
                        token_file.write(creds.to_json())
                    os.chmod(GMAIL_TOKEN_PATH, 0o600)
                except Exception as refresh_err:
                    print(f"[CalendarSync] Failed to refresh OAuth token: {refresh_err}")
                    return None

            if creds and creds.valid:
                # Verify that token actually contains calendar permissions
                token_scopes = set(creds.scopes or [])
                has_cal_scope = any("calendar" in s for s in token_scopes)
                if not has_cal_scope:
                    return None
                return build("calendar", "v3", credentials=creds)
            return None
        except Exception as e:
            # Handles insufficient scopes or malformed tokens gracefully
            err_str = str(e)
            if "insufficient" in err_str.lower() or "scope" in err_str.lower():
                print("[CalendarSync] Google Calendar scope not yet granted in token.json.")
                print("               Run: ./venv/bin/python scripts/setup_google.py --oauth")
            else:
                print(f"[CalendarSync] Initialization error: {e}")
            return None

    @staticmethod
    def get_or_create_calendar(service, calendar_name: str = DEFAULT_CALENDAR_NAME) -> str:
        """
        Locates or creates a dedicated secondary calendar in Google Calendar
        so PhD deadlines can be easily toggled on/off, colored, or shared.
        Falls back to 'primary' if creation fails or if GOOGLE_CALENDAR_ID is set.
        """
        explicit_cal_id = os.getenv("GOOGLE_CALENDAR_ID")
        if explicit_cal_id:
            return explicit_cal_id

        try:
            # Check existing calendars in user's account
            cal_list = service.calendarList().list().execute()
            items = cal_list.get("items", [])
            for item in items:
                summary = item.get("summary", "").strip()
                if summary == calendar_name or summary == "Hypatia PhD Deadlines":
                    return item["id"]

            # If not found, create dedicated secondary calendar
            print(f"[CalendarSync] Creating dedicated Google Calendar: '{calendar_name}'...")
            new_calendar = {
                "summary": calendar_name,
                "description": "Application deadlines for high-fit Theoretical Physics PhD positions discovered by Hypatia.",
                "timeZone": os.getenv("TIMEZONE", "Europe/Stockholm")
            }
            created = service.calendars().insert(body=new_calendar).execute()
            cal_id = created.get("id")
            print(f"[CalendarSync] Successfully created calendar: {calendar_name} (ID: {cal_id})")
            return cal_id
        except Exception as e:
            print(f"[CalendarSync] Could not create dedicated calendar ({e}). Falling back to 'primary'.")
            return "primary"

    @staticmethod
    def build_event_body(
        offering: Dict[str, Any],
        evaluation: Optional[Dict[str, Any]] = None,
        guide_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Constructs a rich Google Calendar all-day event body with comprehensive
        match information, direct links, and multi-stage reminders.
        """
        deadline_str = offering.get("deadline")
        deadline_date = CalendarSync.parse_deadline(deadline_str)
        if not deadline_date:
            return None

        # Google Calendar all-day events require exclusive end date (next day)
        start_date = deadline_date.isoformat()
        end_date = (deadline_date + timedelta(days=1)).isoformat()

        title = offering.get("title", "PhD Opportunity")
        institution = offering.get("institution", "University")
        location = offering.get("location", "")
        offering_id = offering.get("id") or "untracked"

        score = 0.0
        score_academic = 0.0
        score_geography = 0.0
        score_financial = 0.0
        eval_summary = ""

        if evaluation:
            score = evaluation.get("total_score", 0.0)
            score_academic = evaluation.get("score_academic", 0.0)
            score_geography = evaluation.get("score_geography", 0.0)
            score_financial = evaluation.get("score_financial", 0.0)
            eval_summary = evaluation.get("evaluation_summary", "")
        elif offering.get("total_score"):
            score = float(offering.get("total_score") or 0.0)
            score_academic = float(offering.get("score_academic") or 0.0)
            score_geography = float(offering.get("score_geography") or 0.0)
            score_financial = float(offering.get("score_financial") or 0.0)
            eval_summary = offering.get("evaluation_reasoning", "")

        summary = f"🚨 [Deadline] 🎓 [{score:.1f}/10] {title} - {institution}"
        event_location = f"{institution}, {location}".strip(", ")

        # Read quick guide pointers if available
        guide_section = ""
        if guide_path and os.path.exists(guide_path):
            try:
                with open(guide_path, "r", encoding="utf-8") as f:
                    guide_lines = f.readlines()
                    guide_section = "\n\nAPPLICATION GUIDANCE POINTERS:\n" + "".join(guide_lines[:25])
            except Exception:
                pass

        primary_url = offering.get("url", "")
        inspire_url = offering.get("inspire_url", "")
        url_text = f"Primary Vacancy Link: {primary_url}"
        if inspire_url and inspire_url != primary_url:
            url_text += f"\nInspireHEP Record: {inspire_url}"

        description = f"""🎓 HYPATIA PHD OPPORTUNITY - APPLICATION DEADLINE
============================================================
Position: {title}
Institution: {institution}
Location: {location}
Application Deadline: {deadline_date.isoformat()}

MATCH EVALUATION BREAKDOWN:
- Total Weighted Score: {score:.1f} / 10.0
- Academic Fit (QCD / Quantum Computing): {score_academic:.1f} / 10.0
- Geography (Scandinavia & EU Priority) : {score_geography:.1f} / 10.0
- Financials (> €2,000/mo Floor)        : {score_financial:.1f} / 10.0

LINKS & DETAILS:
{url_text}

EVALUATOR REASONING:
{eval_summary}
{guide_section}
============================================================
Discovered and monitored autonomously by Hypatia."""

        return {
            "summary": summary,
            "location": event_location,
            "description": description,
            "start": {
                "date": start_date
            },
            "end": {
                "date": end_date
            },
            # Color 11 is 'Flamingo' (bold red/coral) in Google Calendar
            "colorId": "11",
            "transparency": "transparent", # Doesn't block schedule availability
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 20160}, # 14 days before
                    {"method": "popup", "minutes": 10080}, # 7 days before
                    {"method": "popup", "minutes": 4320},  # 3 days before
                    {"method": "popup", "minutes": 1440},  # 1 day before
                    {"method": "popup", "minutes": 540}    # 9:00 AM on deadline day
                ]
            },
            "extendedProperties": {
                "private": {
                    "hypatia_offering_id": str(offering_id),
                    "hypatia_score": f"{score:.1f}"
                }
            }
        }

    @staticmethod
    def sync_offering(
        offering: Dict[str, Any],
        evaluation: Optional[Dict[str, Any]] = None,
        guide_path: Optional[str] = None,
        service=None,
        calendar_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Syncs a single PhD offering's deadline to Google Calendar.
        If the event already exists, it is updated. Otherwise, a new event is created.
        Updates offerings table with calendar_event_id.
        """
        deadline = offering.get("deadline")
        parsed_date = CalendarSync.parse_deadline(deadline)
        if not parsed_date:
            return None

        event_body = CalendarSync.build_event_body(offering, evaluation, guide_path)
        if not event_body:
            return None

        svc = service or CalendarSync.get_calendar_service()
        if not svc:
            return None

        cal_id = calendar_id or CalendarSync.get_or_create_calendar(svc)
        existing_event_id = offering.get("calendar_event_id")
        offering_id = offering.get("id")

        try:
            # 1. Update existing event if event ID is known
            if existing_event_id:
                try:
                    updated = svc.events().update(
                        calendarId=cal_id,
                        eventId=existing_event_id,
                        body=event_body
                    ).execute()
                    print(f"[CalendarSync] Updated event on Google Calendar: {parsed_date} - {offering.get('title')[:35]}...")
                    return updated.get("id")
                except Exception as update_err:
                    if "404" not in str(update_err):
                        print(f"[CalendarSync] Event update failed ({update_err}), trying insertion...")

            # 2. Prevent duplicates by checking extendedProperties
            if offering_id:
                try:
                    prop_search = svc.events().list(
                        calendarId=cal_id,
                        privateExtendedProperty=f"hypatia_offering_id={offering_id}"
                    ).execute()
                    found_items = prop_search.get("items", [])
                    if found_items:
                        match_id = found_items[0]["id"]
                        updated = svc.events().update(
                            calendarId=cal_id,
                            eventId=match_id,
                            body=event_body
                        ).execute()
                        CalendarSync._record_calendar_id(offering_id, match_id)
                        print(f"[CalendarSync] Updated existing matched event: {parsed_date} (ID: {match_id})")
                        return match_id
                except Exception:
                    pass

            # 3. Insert new event
            created = svc.events().insert(calendarId=cal_id, body=event_body).execute()
            created_id = created.get("id")
            print(f"[✓] Created Google Calendar event: {parsed_date} - {offering.get('title')[:35]}... (ID: {created_id})")

            if offering_id:
                CalendarSync._record_calendar_id(offering_id, created_id)

            return created_id

        except Exception as e:
            err_msg = str(e)
            if "insufficientPermissions" in err_msg or "scope" in err_msg.lower():
                print("[CalendarSync] Insufficient OAuth permissions for Calendar.")
                print("               Please run: ./venv/bin/python scripts/setup_google.py --oauth")
            else:
                print(f"[CalendarSync] Failed to sync event to Google Calendar: {e}")
            return None

    @staticmethod
    def _record_calendar_id(offering_id: int, calendar_event_id: str):
        """Updates offerings table with the assigned Google Calendar event ID."""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "UPDATE offerings SET calendar_event_id = ?, calendar_synced_at = ? WHERE id = ?",
                (calendar_event_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), offering_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[CalendarSync] Could not update database with calendar_event_id: {e}")

    @staticmethod
    def sync_all_high_scoring(threshold: float = 7.5) -> Dict[str, int]:
        """
        Retroactively synchronizes all high-scoring positions in the database
        that have valid deadline dates to Google Calendar.
        """
        svc = CalendarSync.get_calendar_service()
        if not svc:
            print("[CalendarSync] Google Calendar service not ready. Cannot sync.")
            return {"synced": 0, "skipped": 0, "failed": 0}

        cal_id = CalendarSync.get_or_create_calendar(svc)

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("""
            SELECT id, url, title, institution, location, deadline, total_score,
                   score_academic, score_geography, score_financial,
                   evaluation_reasoning, guide_path, calendar_event_id
            FROM offerings
            WHERE total_score >= ?
            ORDER BY total_score DESC
        """, (threshold,))

        rows = [dict(r) for r in c.fetchall()]
        conn.close()

        stats = {"total_high_scoring": len(rows), "synced": 0, "skipped_no_deadline": 0, "failed": 0}

        print(f"\n=======================================================")
        print(f"  Hypatia Google Calendar Sync (Threshold: ≥{threshold}/10)")
        print(f"  Target Calendar: {cal_id}")
        print(f"  Eligible Postings Found: {len(rows)}")
        print(f"=======================================================\n")

        for off in rows:
            parsed = CalendarSync.parse_deadline(off.get("deadline"))
            if not parsed:
                print(f"[-] Skipping #{off['id']}: {off['title'][:35]}... (Deadline: Unspecified)")
                stats["skipped_no_deadline"] += 1
                continue

            event_id = CalendarSync.sync_offering(
                offering=off,
                guide_path=off.get("guide_path"),
                service=svc,
                calendar_id=cal_id
            )
            if event_id:
                stats["synced"] += 1
            else:
                stats["failed"] += 1

        print("\n=======================================================")
        print(f"  Calendar Sync Complete:")
        print(f"  - Successfully Synced : {stats['synced']}")
        print(f"  - Skipped (No Date)   : {stats['skipped_no_deadline']}")
        print(f"  - Failed              : {stats['failed']}")
        print("=======================================================\n")
        return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hypatia Google Calendar Sync")
    parser.add_argument("--sync", action="store_true", help="Sync all high-scoring positions in DB to Google Calendar")
    parser.add_argument("--threshold", type=float, default=7.5, help="Score threshold for syncing (default: 7.5)")
    parser.add_argument("--status", action="store_true", help="Check Google Calendar connection status")
    args = parser.parse_args()

    if args.status:
        svc = CalendarSync.get_calendar_service()
        if svc:
            cal_id = CalendarSync.get_or_create_calendar(svc)
            print(f"[✓] Google Calendar is AUTHENTICATED and ACTIVE. Active Calendar: {cal_id}")
        else:
            print("[!] Google Calendar service is NOT ready or lacks OAuth calendar scope.")
            print("    Run: ./venv/bin/python scripts/setup_google.py --oauth")
    elif args.sync:
        CalendarSync.sync_all_high_scoring(threshold=args.threshold)
    else:
        parser.print_help()
