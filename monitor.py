#!/usr/bin/env python3
import os
import sys
import sqlite3
import json
import signal
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.init_db import init_db
from core.llm_router import LLMRouter
from core.fetchers import (
    InspireHEPFetcher, QuantikiFetcher, CERNFetcher,
    DESYFetcher, ScandinavianVarbiFetcher, AcademicPositionsFetcher
)
from core.deduplicator import DuplicateDetector
from core.evaluator import OfferingEvaluator
from core.dossier import DossierGenerator
from core.notifier import Notifier
from core.mailer import Mailer

# Graceful signal handler to unload local models if stopped by launchd or user
def _handle_exit(signum, frame):
    print(f"\n[!] Signal {signum} received. Cleaning up and unloading models...")
    LLMRouter.unload_models()
    sys.exit(0)

signal.signal(signal.SIGTERM, _handle_exit)
signal.signal(signal.SIGINT, _handle_exit)

import argparse
DB_PATH = os.path.join(os.path.dirname(__file__), 'db', 'system.db')
REF_DOC_PATH = os.path.join(os.path.dirname(__file__), 'db', 'reference_document.json')
DEFAULT_HIGH_SCORE_THRESHOLD = 7.5

def check_environment():
    if not os.path.exists(REF_DOC_PATH):
        print(f"[!] Error: Reference profile not found at {REF_DOC_PATH}")
        sys.exit(1)
        
    local_up = LLMRouter.ensure_local_running()
    has_cloud_keys = any(os.getenv(k) for k in ["GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"])
    
    if local_up:
        print("[✓] Local llama-server is ACTIVE on http://127.0.0.1:8080. Using local models.")
    elif has_cloud_keys:
        print("[i] Local llama-server not detected, but cloud API keys found. Using cloud cascade.")
    else:
        print("[!] Warning: Local llama-server is NOT running on http://127.0.0.1:8080 and no cloud API keys were found in .env.")
        print("    To run locally, execute in a terminal:")
        print("      ~/Models/start-llama-router.sh")
        print("    Or set GROQ_API_KEY / GEMINI_API_KEY in .env.")
        sys.exit(1)

def run_monitor(limit: int = 50, high_score_threshold: float = DEFAULT_HIGH_SCORE_THRESHOLD, unload_after: bool = True):
    print(f"\n=======================================================")
    print(f"  Hypatia - Autonomous PhD Opportunity Monitor")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Score Alert Threshold: {high_score_threshold}/10.0")
    print(f"  Memory Auto-Unload: {'Enabled' if unload_after else 'Disabled'}")
    print(f"=======================================================")
    
    check_environment()
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check and flush any pending alerts from previous runs
        outbox_start = Mailer.flush_outbox()
        if outbox_start.get("sent", 0) > 0:
            print(f"[✓] Successfully flushed {outbox_start['sent']} pending alert(s) from outbox.")

        # Load tracked records for cross-source deduplication and comparison
        cursor.execute("SELECT id, url, title, institution, deadline, secondary_urls FROM offerings")
        existing_records = [dict(row) for row in cursor.fetchall()]
        existing_urls = {row["url"] for row in existing_records}
        deduplicator = DuplicateDetector(existing_records)
        
        # 1. Fetch live listings from InspireHEP
        print(f"\n[*] Fetching active listings from InspireHEP (limit: {limit})...")
        inspire_fetcher = InspireHEPFetcher()
        inspire_offerings = inspire_fetcher.fetch_open_phds(limit=limit)

        # 2. Fetch live listings from Quantiki
        print(f"[*] Fetching active listings from Quantiki (limit: {min(limit, 25)})...")
        quantiki_fetcher = QuantikiFetcher()
        quantiki_offerings = quantiki_fetcher.fetch_open_phds(limit=min(limit, 25), existing_urls=existing_urls)
        
        # 3. Fetch live listings from CERN
        print(f"[*] Fetching active listings from CERN...")
        cern_fetcher = CERNFetcher()
        cern_offerings = cern_fetcher.fetch_open_phds(limit=15, existing_urls=existing_urls)

        # 4. Fetch live listings from DESY
        print(f"[*] Fetching active listings from DESY...")
        desy_fetcher = DESYFetcher()
        desy_offerings = desy_fetcher.fetch_open_phds(limit=15, existing_urls=existing_urls)

        # 5. Fetch live listings from Scandinavian Universities (Varbi: Lund, Stockholm, Uppsala, KTH)
        print(f"[*] Fetching active listings from Scandinavian Universities (Lund, Stockholm, Uppsala, KTH)...")
        varbi_fetcher = ScandinavianVarbiFetcher()
        varbi_offerings = varbi_fetcher.fetch_open_phds(limit_per_uni=5, existing_urls=existing_urls)

        # 6. Check AcademicPositions
        academic_pos_fetcher = AcademicPositionsFetcher()
        academic_pos_fetcher.fetch_open_phds(existing_urls=existing_urls)

        live_offerings = (
            inspire_offerings +
            quantiki_offerings +
            cern_offerings +
            desy_offerings +
            varbi_offerings
        )
        print(f"\n[*] Total active listings retrieved across all feeds: {len(live_offerings)} ({len(existing_urls)} already tracked in DB).")
        
        new_offerings = [off for off in live_offerings if off["url"] not in existing_urls and off.get("inspire_url") not in existing_urls]
        print(f"[+] Found {len(new_offerings)} potential new listings to inspect.")
        
        if not new_offerings:
            print("\n[✓] Everything is up to date. No new positions to evaluate.")
            outbox_stats = Mailer.get_outbox_stats()
            signal_data = {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "inspected": 0,
                "evaluated": 0,
                "high_matches": 0,
                "outbox_pending": outbox_stats["pending"],
                "outbox_sent_total": outbox_stats["sent"]
            }
            print(f"\nHYPATIA_SIGNAL:{json.dumps(signal_data)}")
            return

        evaluator = OfferingEvaluator()
        dossier_gen = DossierGenerator()
        high_matches = []
        evaluated_count = 0
        
        # 3. Evaluate each new candidate after cross-source deduplication check
        for idx, off in enumerate(new_offerings, 1):
            # Check intelligent cross-source deduplication
            is_dup, match, reason = deduplicator.find_duplicate(off)
            if is_dup:
                matched_id = match.get("id")
                print(f"\n[{idx}/{len(new_offerings)}] [Deduplicator] Cross-portal duplicate detected for: {off['title']} ({off['source']})")
                print(f"    -> Merged with existing #{matched_id}: {reason}")
                
                # Merge secondary URL into existing record
                existing_sec = match.get("secondary_urls") or ""
                sec_list = json.loads(existing_sec) if existing_sec.startswith("[") else ([existing_sec] if existing_sec else [])
                if off["url"] not in sec_list and off["url"] != match.get("url"):
                    sec_list.append(off["url"])
                    cursor.execute("UPDATE offerings SET secondary_urls = ? WHERE id = ?", (json.dumps(sec_list), matched_id))
                    conn.commit()
                    match["secondary_urls"] = json.dumps(sec_list)
                continue

            evaluated_count += 1
            print(f"\n[{idx}/{len(new_offerings)}] Evaluating: {off['title']} ({off['institution']}) [{off['source']}]")
            
            evaluation = evaluator.evaluate(off)
            total_score = evaluation.get("total_score", 0.0)
            status = "evaluated"
            guide_path = None
            
            print(f"    Scores -> Academic: {evaluation.get('score_academic', 0):.1f} | Geography: {evaluation.get('score_geography', 0):.1f} | Financial: {evaluation.get('score_financial', 0):.1f} ==> Total: {total_score:.1f}/10")
            
            # 4. Insert into DB to get assigned offering ID
            cursor.execute(
                """INSERT INTO offerings (
                    url, source, title, institution, location, country, region,
                    offering_type, description, deadline, arxiv_categories,
                    topics_mentioned, score_geography, score_academic, score_financial,
                    total_score, evaluation_reasoning, status, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    off["url"],
                    off["source"],
                    off["title"],
                    off["institution"],
                    off["location"],
                    off.get("country", ""),
                    ", ".join(off.get("regions", [])),
                    off["offering_type"],
                    off["description"],
                    off["deadline"],
                    json.dumps(off.get("arxiv_categories", [])),
                    json.dumps(evaluation.get("topics_mentioned", [])),
                    evaluation.get("score_geography"),
                    evaluation.get("score_academic"),
                    evaluation.get("score_financial"),
                    total_score,
                    evaluation.get("evaluation_summary"),
                    status,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            offering_id = cursor.lastrowid
            conn.commit()
            off["id"] = offering_id

            # Add to deduplicator index for subsequent candidates in this run
            deduplicator.existing_offerings.append(off)
            deduplicator._index_records()
            
            # 5. Handle high scoring positions (Dossier + Notification/Email)
            if total_score >= high_score_threshold and not evaluation.get("disqualified", False):
                print(f"    ⭐ HIGH FIT MATCH! Generating application dossier and notifying...")
                status = "high_score"
                guide_path = dossier_gen.generate_dossier(off, evaluation)
                
                cursor.execute(
                    "UPDATE offerings SET status = ?, guide_path = ?, notified_at = ? WHERE id = ?",
                    (status, guide_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), offering_id)
                )
                conn.commit()
                
                Notifier.notify_high_score(off, evaluation, guide_path)
                high_matches.append((off, evaluation, guide_path))

        # Flush any remaining queued alerts
        Mailer.flush_outbox()
        outbox_stats = Mailer.get_outbox_stats()

        print("\n=======================================================")
        print(f"  Summary of Run:")
        print(f"  - Inspected Listings: {len(new_offerings)}")
        print(f"  - Newly Evaluated   : {evaluated_count}")
        print(f"  - High Matches (≥{high_score_threshold}) : {len(high_matches)}")
        print(f"  - Outbox Status     : {outbox_stats['pending']} pending, {outbox_stats['sent']} total sent")
        if high_matches:
            print("  - Alerts emailed or queued in outbox / recorded in phd_alerts.md.")
        print("=======================================================\n")

        signal_data = {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "inspected": len(new_offerings),
            "evaluated": evaluated_count,
            "high_matches": len(high_matches),
            "outbox_pending": outbox_stats["pending"],
            "outbox_sent_total": outbox_stats["sent"]
        }
        print(f"HYPATIA_SIGNAL:{json.dumps(signal_data)}")
    finally:
        conn.close()
        if unload_after:
            LLMRouter.unload_models()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hypatia PhD Monitor")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of listings to fetch from feeds")
    parser.add_argument("--threshold", type=float, default=DEFAULT_HIGH_SCORE_THRESHOLD, help="Score threshold (0-10)")
    parser.add_argument("--keep-loaded", action="store_true", help="Keep model loaded in RAM after run instead of releasing memory")
    args = parser.parse_args()
    run_monitor(limit=args.limit, high_score_threshold=args.threshold, unload_after=not args.keep_loaded)
