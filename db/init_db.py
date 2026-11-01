import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "system.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Offerings Table with UNIQUE(url) for deduplication
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS offerings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL UNIQUE,
        source TEXT,
        title TEXT NOT NULL,
        institution TEXT,
        location TEXT,
        country TEXT,
        region TEXT,
        offering_type TEXT DEFAULT 'phd',
        description TEXT,
        deadline TEXT,
        arxiv_categories TEXT,
        compensation_raw TEXT,
        duration_weeks INTEGER,
        topics_mentioned TEXT,
        score_geography REAL,
        score_academic REAL,
        score_financial REAL,
        total_score REAL,
        evaluation_reasoning TEXT,
        status TEXT DEFAULT 'new',
        guide_path TEXT,
        secondary_urls TEXT,
        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notified_at TIMESTAMP
    )
    """)

    # Ensure secondary_urls column exists for existing databases
    try:
        cursor.execute("ALTER TABLE offerings ADD COLUMN secondary_urls TEXT")
    except Exception:
        pass

    # Sites Table (for any supplemental URL targets)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_url TEXT NOT NULL UNIQUE,
        scraping_method TEXT,
        target_type TEXT DEFAULT 'phd',
        last_checked TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized with deduplication constraints at {DB_PATH}")

if __name__ == "__main__":
    init_db()
