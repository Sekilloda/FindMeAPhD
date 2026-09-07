import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "system.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Sites Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_url TEXT NOT NULL,
        scraping_method TEXT NOT NULL,
        target_type TEXT NOT NULL
    )
    """)

    # Offerings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS offerings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        institution TEXT NOT NULL,
        location TEXT NOT NULL,
        offering_type TEXT NOT NULL,
        url TEXT NOT NULL,
        description TEXT NOT NULL,
        duration_weeks INTEGER,
        compensation_raw TEXT,
        topics_mentioned TEXT, -- JSON list
        score_geography REAL,
        score_academic REAL,
        score_financial REAL,
        total_score REAL
    )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()
