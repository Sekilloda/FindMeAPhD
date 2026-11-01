#!/usr/bin/env python3
"""
Test Suite: Real-World Cross-Source Deduplication & Comparison
Tests DuplicateDetector against actual database records from InspireHEP,
Quantiki, DESY, CERN, and Scandinavian University portals.
"""

import os
import sys
import sqlite3
import json

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.deduplicator import DuplicateDetector

def run_tests():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "system.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Load the base offerings snapshot (IDs 1-64) against which these candidates are tested
    c.execute("SELECT id, url, title, institution, deadline, secondary_urls FROM offerings WHERE id <= 64")
    existing_records = [dict(r) for r in c.fetchall()]
    conn.close()

    print(f"======================================================================")
    print(f"  REAL-WORLD DEDUPLICATOR TEST SUITE")
    print(f"  Loaded {len(existing_records)} existing real offerings from database")
    print(f"======================================================================\n")

    detector = DuplicateDetector(existing_records)

    tests = [
        # --- TEST CATEGORY A: Real Cross-Feed Duplicates (Different URLs, Same Real Job) ---
        {
            "name": "DESY ATLAS Group (InspireHEP vs Direct DESY Portal)",
            "candidate": {
                "source": "desy",
                "url": "https://v22.desy.de/e67416/records322068/index_eng.html",
                "title": "PhD Student for the ATLAS Group",
                "institution": "DESY",
                "deadline": "Unspecified"
            },
            "expected_duplicate": True,
            "expected_id": 30,
            "category": "Cross-Source Duplicate"
        },
        {
            "name": "DESY SRF Cavity (InspireHEP vs Direct DESY Portal)",
            "candidate": {
                "source": "desy",
                "url": "https://v22.desy.de/e67416/records313903/index_eng.html",
                "title": "PhD position in SRF cavity control for gravitational wave searches",
                "institution": "DESY",
                "deadline": "2027-10-20"
            },
            "expected_duplicate": True,
            "expected_id": 12,
            "category": "Cross-Source Duplicate"
        },
        {
            "name": "Stockholm Rydberg Ions (Quantiki Title Variant vs Varbi Format)",
            "candidate": {
                "source": "scandinavian_varbi",
                "url": "https://su.varbi.com/en/what:job/jobID:965538/",
                "title": "PhD student in 2D quantum simulations with trapped Rydberg ions",
                "institution": "Stockholms universitet",
                "deadline": "2026-09-28"
            },
            "expected_duplicate": True,
            "expected_id": 64,
            "category": "Title Variant / Synonym Duplicate"
        },
        {
            "name": "Zagreb QCD Hadron Structure (InspireHEP vs Euraxess External Apply Link)",
            "candidate": {
                "source": "euraxess",
                "url": "https://euraxess.ec.europa.eu/jobs/475934",
                "title": "Doctoral Student, Contest Point No. 10 - QCD Phenomenology and Hadron Structure",
                "institution": "Rudjer Boskovic Institute, Zagreb",
                "deadline": "2026-11-27"
            },
            "expected_duplicate": True,
            "expected_id": 4,
            "category": "Title Variant Duplicate"
        },
        {
            "name": "CERN Event Reconstruction (Generic Portal Posting vs SmartRecruiters Format)",
            "candidate": {
                "source": "hep_portal",
                "url": "https://physics-jobs.eu/cern-reconstruction-2026",
                "title": "Event Reconstruction Physicist at CERN (Future Circular Collider)",
                "institution": "CERN",
                "deadline": "2026-11-13"
            },
            "expected_duplicate": False, # Currently not in DB, should be recognized as brand new!
            "expected_id": None,
            "category": "New Unique Posting"
        },

        # --- TEST CATEGORY B: Real Negative Controls (Distinct Postings that Must NOT Duplicate) ---
        {
            "name": "Uppsala Quantum Verification (Real Varbi Job) vs Existing Quantiki Postings",
            "candidate": {
                "source": "scandinavian_varbi",
                "url": "https://uu.varbi.com/en/what:job/jobID:961891/",
                "title": "PhD student focusing on Scalable Quantum Program Verification",
                "institution": "Uppsala University",
                "deadline": "15.Nov.2026"
            },
            "expected_duplicate": False,
            "expected_id": None,
            "category": "Distinct Position (Negative Control)"
        },
        {
            "name": "Stockholm Anharmonic Quantum Sensing (Real Varbi Job) vs Existing Postings",
            "candidate": {
                "source": "scandinavian_varbi",
                "url": "https://su.varbi.com/en/what:job/jobID:973731/",
                "title": "PhD Student in Theoretical Physics: Quantum Sensing with Anharmonic Systems",
                "institution": "Stockholm University",
                "deadline": "03.Nov.2026"
            },
            "expected_duplicate": False,
            "expected_id": None,
            "category": "Distinct Position (Negative Control)"
        },
        {
            "name": "Lund Applied Nuclear Physics (Real Varbi Job) vs Existing Postings",
            "candidate": {
                "source": "scandinavian_varbi",
                "url": "https://lu.varbi.com/en/what:job/jobID:972103/",
                "title": "Doctoral student in applied nuclear physics",
                "institution": "Lund University",
                "deadline": "20.Nov.2026"
            },
            "expected_duplicate": False,
            "expected_id": None,
            "category": "Distinct Position (Negative Control)"
        },
        {
            "name": "Uppsala Nuclear Fission (Real Varbi Job) vs Lund Applied Nuclear",
            "candidate": {
                "source": "scandinavian_varbi",
                "url": "https://uu.varbi.com/en/what:job/jobID:981431/",
                "title": "PhD student in experimental nuclear physics with a focus on nuclear fission and gamma-ray emission",
                "institution": "Uppsala University",
                "deadline": "27.Nov.2026"
            },
            "expected_duplicate": False,
            "expected_id": None,
            "category": "Distinct Position (Negative Control)"
        }
    ]

    passed = 0
    failed = 0

    for idx, test in enumerate(tests, 1):
        name = test["name"]
        cand = test["candidate"]
        exp_dup = test["expected_duplicate"]
        exp_id = test["expected_id"]
        cat = test["category"]

        is_dup, match, reason = detector.find_duplicate(cand)
        matched_id = match.get("id") if match else None

        # Verify test condition
        success = (is_dup == exp_dup)
        if exp_id is not None:
            success = success and (matched_id == exp_id)

        status_tag = "✅ PASS" if success else "❌ FAIL"
        if success:
            passed += 1
        else:
            failed += 1

        print(f"Test #{idx} [{cat}]")
        print(f"  Name     : {name}")
        print(f"  Candidate: '{cand['title']}' ({cand['institution']})")
        print(f"  Result   : Duplicate={is_dup} (Expected={exp_dup}) | Matched ID: {matched_id} (Expected={exp_id})")
        print(f"  Reason   : {reason}")
        print(f"  Status   : {status_tag}\n")

    print(f"======================================================================")
    print(f"  TEST SUMMARY: {passed} Passed, {failed} Failed (Total: {len(tests)})")
    print(f"======================================================================")

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
