import os
import subprocess
from datetime import datetime
from typing import Dict, Any
from core.mailer import Mailer
from core.calendar_sync import CalendarSync

ALERTS_MD_PATH = os.path.join(os.path.dirname(__file__), '..', 'phd_alerts.md')

class Notifier:
    """
    Handles notifications for high-scoring PhD vacancies:
    - Primary: Rich email alerts with full match details and application pointers.
    - Calendar: Populates Google Calendar with deadline events (dynamic point of reference).
    - Digest: Updates phd_alerts.md digest.
    - Secondary: Optional desktop banners.
    """
    
    @staticmethod
    def notify_high_score(offering: Dict[str, Any], evaluation: Dict[str, Any], guide_path: str = None):
        title = offering.get('title', 'PhD Opportunity')
        institution = offering.get('institution', 'University')
        total_score = evaluation.get('total_score', 0.0)
        
        # 1. Primary Action: Send email with vacancy details and application pointers
        print(f"[Notifier] Dispatching email alert for: {title} ({institution})...")
        Mailer.send_phd_alert(offering, evaluation, guide_path)
        
        # 2. Dynamic Point of Reference: Sync to Google Calendar
        try:
            cal_id = CalendarSync.sync_offering(offering, evaluation, guide_path)
            if cal_id:
                offering["calendar_event_id"] = cal_id
        except Exception as cal_err:
            print(f"[Notifier] Google Calendar sync skipped: {cal_err}")
        
        # 3. Append to phd_alerts.md
        Notifier._append_to_alerts_md(offering, evaluation, guide_path)
        
        # 4. Optional desktop notification (default: False, enabled if DESKTOP_NOTIFICATIONS=true)
        if os.getenv("DESKTOP_NOTIFICATIONS", "false").lower() in ("true", "1", "yes"):
            Notifier._send_macos_notification(
                title="🎓 High-Fit PhD Match Found!",
                subtitle=f"Score: {total_score:.1f}/10 - {institution}",
                message=f"{title}"
            )
        
    @staticmethod
    def _send_macos_notification(title: str, subtitle: str, message: str):
        safe_title = title.replace('"', '\\"')
        safe_subtitle = subtitle.replace('"', '\\"')
        safe_msg = message.replace('"', '\\"').replace('\n', ' ')[:120]
        
        script = f'display notification "{safe_msg}" with title "{safe_title}" subtitle "{safe_subtitle}" sound name "Glass"'
        try:
            subprocess.run(["osascript", "-e", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Notifier] Could not send macOS notification: {e}")

    @staticmethod
    def _append_to_alerts_md(offering: Dict[str, Any], evaluation: Dict[str, Any], guide_path: str = None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        days_left = Mailer.get_days_until_deadline(offering.get('deadline'))
        is_urgent = days_left is not None and 0 <= days_left <= 14
        urgent_badge = f" 🚨 **[URGENT: {days_left} DAYS LEFT]**" if is_urgent else ""
        
        guide_rel_link = ""
        if guide_path:
            rel = os.path.relpath(guide_path, os.path.dirname(ALERTS_MD_PATH))
            guide_dir = os.path.dirname(rel)
            guide_rel_link = f"[📖 Application & Cover Letter Guide]({rel}) | [📄 Vacancy Details]({guide_dir}/description.md)"
            
        entry = f"""
### [{evaluation.get('total_score', 0):.1f}/10] {offering.get('title')}{urgent_badge}
- **Institution**: {offering.get('institution')} ({offering.get('location')})
- **Application Deadline**: **{offering.get('deadline')}**{urgent_badge}
- **Discovered**: {timestamp}
- **Direct Link**: [{offering.get('url')}]({offering.get('url')})
- **InspireHEP Link**: [{offering.get('inspire_url', offering.get('url'))}]({offering.get('inspire_url', offering.get('url'))})
- **Score Breakdown**: Academic: {evaluation.get('score_academic', 0):.1f} | Geography: {evaluation.get('score_geography', 0):.1f} | Financial: {evaluation.get('score_financial', 0):.1f}
- **Summary**: {evaluation.get('evaluation_summary')}
- **Dossier**: {guide_rel_link}

---
"""
        if not os.path.exists(ALERTS_MD_PATH):
            header = f"# 🎓 Theoretical Physics PhD Alerts & Top Matches\n\n*Updated automatically by Hypatia Monitor. Postings with a match score $\\ge$ 7.5/10 are stored below.*\n\n---\n"
            with open(ALERTS_MD_PATH, 'w', encoding='utf-8') as f:
                f.write(header + entry)
        else:
            with open(ALERTS_MD_PATH, 'a', encoding='utf-8') as f:
                f.write(entry)
                
        print(f"[Notifier] Appended top match to {ALERTS_MD_PATH}")
