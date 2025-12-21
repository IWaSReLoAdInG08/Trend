import sqlite3
import json
from pathlib import Path

db_path = Path("output/2025-12-21/news.db")
if not db_path.exists():
    print("DB not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Categorized News (Top 5) ---")
cursor.execute("SELECT title, categories FROM news_items WHERE categories != '[]' LIMIT 5")
for row in cursor.fetchall():
    print(f"Title: {row[0]}")
    print(f"Cats: {row[1]}")
    print("-" * 20)

print("\n--- Latest Hourly Summary ---")
cursor.execute("SELECT time_window, highlights, top_categories FROM hourly_summaries ORDER BY created_at DESC LIMIT 1")
row = cursor.fetchone()
if row:
    print(f"Window: {row[0]}")
    print(f"Highlights: {row[1]}")
    print(f"Top Cats: {row[2]}")
else:
    print("No summary found")

conn.close()
