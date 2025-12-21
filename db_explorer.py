import sqlite3
import os
from pathlib import Path

def explore_db(date_folder=None):
    if not date_folder:
        from datetime import datetime
        date_folder = datetime.now().strftime("%Y-%m-%d")
    
    db_path = Path(f"output/{date_folder}/news.db")
    if not db_path.exists():
        print(f"No database found for date: {date_folder}")
        for p in Path("output").rglob("news.db"):
            print(f"Found alternative: {p}")
            db_path = p
            break
        else: return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    def print_table(name, query):
        print(f"\n--- {name} ---")
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            if not rows: print("Empty")
            for row in rows: print(dict(row))
        except Exception as e:
            print(f"Error reading {name}: {e}")

    print_table("NEWS ITEMS", "SELECT id, title, platform_id, rank FROM news_items LIMIT 5")
    print_table("OPINIONS", "SELECT * FROM opinions LIMIT 5")
    print_table("NEWS_OPINIONS_LINK", "SELECT * FROM news_opinions_link LIMIT 5")
    print_table("SENTIMENT_SUMMARIES", "SELECT * FROM sentiment_summaries LIMIT 5")

    conn.close()

if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else None
    explore_db(date)
