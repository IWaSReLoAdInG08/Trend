# coding=utf-8
"""
Local Storage Backend - SQLite + TXT/HTML

Uses SQLite as primary storage, supports optional TXT snapshots and HTML reports
"""

import sqlite3
import shutil
import pytz
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from trendradar.storage.base import StorageBackend, NewsItem, NewsData
from trendradar.utils.time import (
    get_configured_time,
    format_date_folder,
    format_time_filename,
)
from trendradar.utils.url import normalize_url


class LocalStorageBackend(StorageBackend):
    """
    Local Storage Backend

    Uses SQLite database to store news data, supporting:
    - SQLite database files organized by date
    - Optional TXT snapshots (for debugging)
    - HTML report generation
    """

    def __init__(
        self,
        data_dir: str = "output",
        enable_txt: bool = True,
        enable_html: bool = True,
        timezone: str = "Asia/Shanghai",
    ):
        """
        Initialize Local Storage Backend

        Args:
            data_dir: Data directory path
            enable_txt: Whether to enable TXT snapshot
            enable_html: Whether to enable HTML report
            timezone: Timezone config (default Asia/Shanghai)
        """
        self.data_dir = Path(data_dir)
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.timezone = timezone
        self._db_connections: Dict[str, sqlite3.Connection] = {}

    @property
    def backend_name(self) -> str:
        return "local"

    @property
    def supports_txt(self) -> bool:
        return self.enable_txt

    def _get_configured_time(self) -> datetime:
        """Get current time in configured timezone"""
        return get_configured_time(self.timezone)

    def _format_date_folder(self, date: Optional[str] = None) -> str:
        """Format date folder name (ISO format: YYYY-MM-DD)"""
        return format_date_folder(date, self.timezone)

    def _format_time_filename(self) -> str:
        """Format time filename (Format: HH-MM)"""
        return format_time_filename(self.timezone)

    def _get_db_path(self, date: Optional[str] = None) -> Path:
        """Get SQLite database path"""
        date_folder = self._format_date_folder(date)
        db_dir = self.data_dir / date_folder
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "news.db"

    def _get_connection(self, date: Optional[str] = None) -> sqlite3.Connection:
        """Get database connection (cached)"""
        db_path = str(self._get_db_path(date))

        if db_path not in self._db_connections:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            self._init_tables(conn)
            self._db_connections[db_path] = conn

        return self._db_connections[db_path]

    def _get_schema_path(self) -> Path:
        """Get schema.sql file path"""
        return Path(__file__).parent / "schema.sql"

    def _init_tables(self, conn: sqlite3.Connection) -> None:
        """Initialize database table structure from schema.sql"""
        schema_path = self._get_schema_path()
        
        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            conn.executescript(schema_sql)
        else:
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        conn.commit()

    def save_news_data(self, data: NewsData) -> bool:
        """
        Save news data to SQLite (using URL as unique identifier, supports title update detection)

        Args:
            data: News data

        Returns:
            Whether save was successful
        """
        try:
            conn = self._get_connection(data.date)
            cursor = conn.cursor()

            # Get current time in configured timezone
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            # First sync platform info to platforms table
            for source_id, source_name in data.id_to_name.items():
                cursor.execute("""
                    INSERT INTO platforms (id, name, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        updated_at = excluded.updated_at
                """, (source_id, source_name, now_str))

            # Statistics counters
            new_count = 0
            updated_count = 0
            title_changed_count = 0
            success_sources = []

            for source_id, news_list in data.items.items():
                success_sources.append(source_id)

                for item in news_list:
                    try:
                        # Normalize URL (remove dynamic params like band_rank in Weibo)
                        normalized_url = normalize_url(item.url, source_id) if item.url else ""

                        # Check if already exists (by normalized URL + platform_id)
                        if normalized_url:
                            cursor.execute("""
                                SELECT id, title FROM news_items
                                WHERE url = ? AND platform_id = ?
                            """, (normalized_url, source_id))
                            existing = cursor.fetchone()

                            if existing:
                                # Exists, update record
                                existing_id, existing_title = existing

                                # Check if title changed
                                if existing_title != item.title:
                                    # Record title change
                                    cursor.execute("""
                                        INSERT INTO title_changes
                                        (news_item_id, old_title, new_title, changed_at)
                                        VALUES (?, ?, ?, ?)
                                    """, (existing_id, existing_title, item.title, now_str))
                                    title_changed_count += 1

                                # Record rank history
                                cursor.execute("""
                                    INSERT INTO rank_history
                                    (news_item_id, rank, crawl_time, created_at)
                                    VALUES (?, ?, ?, ?)
                                """, (existing_id, item.rank, data.crawl_time, now_str))

                                # Update existing record
                                cursor.execute("""
                                    UPDATE news_items SET
                                        title = ?,
                                        rank = ?,
                                        mobile_url = ?,
                                        last_crawl_time = ?,
                                        crawl_count = crawl_count + 1,
                                        updated_at = ?
                                    WHERE id = ?
                                """, (item.title, item.rank, item.mobile_url,
                                      data.crawl_time, now_str, existing_id))
                                updated_count += 1
                            else:
                                # Does not exist, insert new record (store normalized URL)
                                cursor.execute("""
                                    INSERT INTO news_items
                                    (title, platform_id, rank, url, mobile_url,
                                     first_crawl_time, last_crawl_time, crawl_count,
                                     created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                                """, (item.title, source_id, item.rank, normalized_url,
                                      item.mobile_url, data.crawl_time, data.crawl_time,
                                      now_str, now_str))
                                new_id = cursor.lastrowid
                                # Record initial rank
                                cursor.execute("""
                                    INSERT INTO rank_history
                                    (news_item_id, rank, crawl_time, created_at)
                                    VALUES (?, ?, ?, ?)
                                """, (new_id, item.rank, data.crawl_time, now_str))
                                new_count += 1
                        else:
                            # URL is empty, insert directly (no deduplication)
                            cursor.execute("""
                                INSERT INTO news_items
                                (title, platform_id, rank, url, mobile_url,
                                 first_crawl_time, last_crawl_time, crawl_count,
                                 created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                            """, (item.title, source_id, item.rank, "",
                                  item.mobile_url, data.crawl_time, data.crawl_time,
                                  now_str, now_str))
                            new_id = cursor.lastrowid
                            # Record initial rank
                            cursor.execute("""
                                INSERT INTO rank_history
                                (news_item_id, rank, crawl_time, created_at)
                                VALUES (?, ?, ?, ?)
                            """, (new_id, item.rank, data.crawl_time, now_str))
                            new_count += 1

                    except sqlite3.Error as e:
                        print(f"Failed to save news item [{item.title[:30]}...]: {e}")

            total_items = new_count + updated_count

            # Record crawl info
            cursor.execute("""
                INSERT OR REPLACE INTO crawl_records
                (crawl_time, total_items, created_at)
                VALUES (?, ?, ?)
            """, (data.crawl_time, total_items, now_str))

            # Get ID of just inserted crawl_record
            cursor.execute("""
                SELECT id FROM crawl_records WHERE crawl_time = ?
            """, (data.crawl_time,))
            record_row = cursor.fetchone()
            if record_row:
                crawl_record_id = record_row[0]

                # Record successful sources
                for source_id in success_sources:
                    cursor.execute("""
                        INSERT OR REPLACE INTO crawl_source_status
                        (crawl_record_id, platform_id, status)
                        VALUES (?, ?, 'success')
                    """, (crawl_record_id, source_id))

                # Record failed sources
                for failed_id in data.failed_ids:
                    # Ensure failed platform is also in platforms table
                    cursor.execute("""
                        INSERT OR IGNORE INTO platforms (id, name, updated_at)
                        VALUES (?, ?, ?)
                    """, (failed_id, failed_id, now_str))

                    cursor.execute("""
                        INSERT OR REPLACE INTO crawl_source_status
                        (crawl_record_id, platform_id, status)
                        VALUES (?, ?, 'failed')
                    """, (crawl_record_id, failed_id))

            conn.commit()

            # Output detailed storage statistics log
            log_parts = [f"[Local Storage] Completed: New {new_count}"]
            if updated_count > 0:
                log_parts.append(f"Updated {updated_count}")
            if title_changed_count > 0:
                log_parts.append(f"Title Changed {title_changed_count}")
            print(", ".join(log_parts))

            return True

        except Exception as e:
            print(f"[Local Storage] Save failed: {e}")
            return False

    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """
        Get all news data for a specific date (merged)

        Args:
            date: Date string, defaults to today

        Returns:
            Merged news data
        """
        try:
            db_path = self._get_db_path(date)
            if not db_path.exists():
                return None

            conn = self._get_connection(date)
            cursor = conn.cursor()

            # Get all news data (including id for querying rank history)
            cursor.execute("""
                SELECT n.id, n.title, n.platform_id, p.name as platform_name,
                       n.rank, n.url, n.mobile_url,
                       n.first_crawl_time, n.last_crawl_time, n.crawl_count
                FROM news_items n
                LEFT JOIN platforms p ON n.platform_id = p.id
                ORDER BY n.platform_id, n.last_crawl_time
            """)

            rows = cursor.fetchall()
            if not rows:
                return None

            # Collect all news_item_ids
            news_ids = [row[0] for row in rows]

            # Batch query rank history
            rank_history_map: Dict[int, List[int]] = {}
            if news_ids:
                placeholders = ",".join("?" * len(news_ids))
                cursor.execute(f"""
                    SELECT news_item_id, rank FROM rank_history
                    WHERE news_item_id IN ({placeholders})
                    ORDER BY news_item_id, crawl_time
                """, news_ids)
                for rh_row in cursor.fetchall():
                    news_id, rank = rh_row[0], rh_row[1]
                    if news_id not in rank_history_map:
                        rank_history_map[news_id] = []
                    if rank not in rank_history_map[news_id]:
                        rank_history_map[news_id].append(rank)

            # Group by platform_id
            items: Dict[str, List[NewsItem]] = {}
            id_to_name: Dict[str, str] = {}
            crawl_date = self._format_date_folder(date)

            for row in rows:
                news_id = row[0]
                platform_id = row[2]
                title = row[1]
                platform_name = row[3] or platform_id

                id_to_name[platform_id] = platform_name

                if platform_id not in items:
                    items[platform_id] = []

                # Get rank history, use current rank if not found
                ranks = rank_history_map.get(news_id, [row[4]])

                items[platform_id].append(NewsItem(
                    title=title,
                    source_id=platform_id,
                    source_name=platform_name,
                    rank=row[4],
                    url=row[5] or "",
                    mobile_url=row[6] or "",
                    crawl_time=row[8],  # last_crawl_time
                    ranks=ranks,
                    first_time=row[7],  # first_crawl_time
                    last_time=row[8],   # last_crawl_time
                    count=row[9],       # crawl_count
                ))

            final_items = items

            # Get failed sources
            cursor.execute("""
                SELECT DISTINCT css.platform_id
                FROM crawl_source_status css
                JOIN crawl_records cr ON css.crawl_record_id = cr.id
                WHERE css.status = 'failed'
            """)
            failed_ids = [row[0] for row in cursor.fetchall()]

            # Get latest crawl time
            cursor.execute("""
                SELECT crawl_time FROM crawl_records
                ORDER BY crawl_time DESC
                LIMIT 1
            """)

            time_row = cursor.fetchone()
            crawl_time = time_row[0] if time_row else self._format_time_filename()

            return NewsData(
                date=crawl_date,
                crawl_time=crawl_time,
                items=final_items,
                id_to_name=id_to_name,
                failed_ids=failed_ids,
            )

        except Exception as e:
            print(f"[Local Storage] Failed to read data: {e}")
            return None

    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """
        Get data from the latest crawl

        Args:
            date: Date string, defaults to today

        Returns:
            Latest crawl news data
        """
        try:
            db_path = self._get_db_path(date)
            if not db_path.exists():
                return None

            conn = self._get_connection(date)
            cursor = conn.cursor()

            # Get latest crawl time
            cursor.execute("""
                SELECT crawl_time FROM crawl_records
                ORDER BY crawl_time DESC
                LIMIT 1
            """)

            time_row = cursor.fetchone()
            if not time_row:
                return None

            latest_time = time_row[0]

            # Get news data for that time (including id for querying rank history)
            cursor.execute("""
                SELECT n.id, n.title, n.platform_id, p.name as platform_name,
                       n.rank, n.url, n.mobile_url,
                       n.first_crawl_time, n.last_crawl_time, n.crawl_count
                FROM news_items n
                LEFT JOIN platforms p ON n.platform_id = p.id
                WHERE n.last_crawl_time = ?
            """, (latest_time,))

            rows = cursor.fetchall()
            if not rows:
                return None

            # Collect all news_item_ids
            news_ids = [row[0] for row in rows]

            # Batch query rank history
            rank_history_map: Dict[int, List[int]] = {}
            if news_ids:
                placeholders = ",".join("?" * len(news_ids))
                cursor.execute(f"""
                    SELECT news_item_id, rank FROM rank_history
                    WHERE news_item_id IN ({placeholders})
                    ORDER BY news_item_id, crawl_time
                """, news_ids)
                for rh_row in cursor.fetchall():
                    news_id, rank = rh_row[0], rh_row[1]
                    if news_id not in rank_history_map:
                        rank_history_map[news_id] = []
                    if rank not in rank_history_map[news_id]:
                        rank_history_map[news_id].append(rank)

            items: Dict[str, List[NewsItem]] = {}
            id_to_name: Dict[str, str] = {}
            crawl_date = self._format_date_folder(date)

            for row in rows:
                news_id = row[0]
                platform_id = row[2]
                platform_name = row[3] or platform_id
                id_to_name[platform_id] = platform_name

                if platform_id not in items:
                    items[platform_id] = []

                # Get rank history, use current rank if not found
                ranks = rank_history_map.get(news_id, [row[4]])

                items[platform_id].append(NewsItem(
                    title=row[1],
                    source_id=platform_id,
                    source_name=platform_name,
                    rank=row[4],
                    url=row[5] or "",
                    mobile_url=row[6] or "",
                    crawl_time=row[8],  # last_crawl_time
                    ranks=ranks,
                    first_time=row[7],  # first_crawl_time
                    last_time=row[8],   # last_crawl_time
                    count=row[9],       # crawl_count
                ))

            # Get failed sources (for the latest crawl)
            cursor.execute("""
                SELECT css.platform_id
                FROM crawl_source_status css
                JOIN crawl_records cr ON css.crawl_record_id = cr.id
                WHERE cr.crawl_time = ? AND css.status = 'failed'
            """, (latest_time,))

            failed_ids = [row[0] for row in cursor.fetchall()]

            return NewsData(
                date=crawl_date,
                crawl_time=latest_time,
                items=items,
                id_to_name=id_to_name,
                failed_ids=failed_ids,
            )

        except Exception as e:
            print(f"[Local Storage] Failed to get latest data: {e}")
            return None

    def detect_new_titles(self, current_data: NewsData) -> Dict[str, Dict]:
        """
        Detect new titles

        Compares current crawl data with historical data to find new titles.
        Key logic: Only titles that have never appeared in historical batches count as new.

        Args:
            current_data: Currently crawled data

        Returns:
            New title data {source_id: {title: NewsItem}}
        """
        try:
            # Get historical data
            historical_data = self.get_today_all_data(current_data.date)

            if not historical_data:
                # No historical data, all are new
                new_titles = {}
                for source_id, news_list in current_data.items.items():
                    new_titles[source_id] = {item.title: item for item in news_list}
                return new_titles

            # Get current batch time
            current_time = current_data.crawl_time

            # Collect historical titles (first_time < current_time)
            # This handles cases where same title has multiple records due to URL changes
            historical_titles: Dict[str, set] = {}
            for source_id, news_list in historical_data.items.items():
                historical_titles[source_id] = set()
                for item in news_list:
                    first_time = getattr(item, 'first_time', item.crawl_time)
                    if first_time < current_time:
                        historical_titles[source_id].add(item.title)

            # Check if there is historical data
            has_historical_data = any(len(titles) > 0 for titles in historical_titles.values())
            if not has_historical_data:
                # First crawl, no "new" concept
                return {}

            # Detect new
            new_titles = {}
            for source_id, news_list in current_data.items.items():
                hist_set = historical_titles.get(source_id, set())
                for item in news_list:
                    if item.title not in hist_set:
                        if source_id not in new_titles:
                            new_titles[source_id] = {}
                        new_titles[source_id][item.title] = item

            return new_titles

        except Exception as e:
            print(f"[Local Storage] Failed to detect new titles: {e}")
            return {}

    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """
        Save TXT snapshot

        Args:
            data: News data

        Returns:
            Saved file path
        """
        if not self.enable_txt:
            return None

        try:
            date_folder = self._format_date_folder(data.date)
            txt_dir = self.data_dir / date_folder / "txt"
            txt_dir.mkdir(parents=True, exist_ok=True)

            file_path = txt_dir / f"{data.crawl_time}.txt"

            with open(file_path, "w", encoding="utf-8") as f:
                for source_id, news_list in data.items.items():
                    source_name = data.id_to_name.get(source_id, source_id)

                    # Write source title
                    if source_name and source_name != source_id:
                        f.write(f"{source_id} | {source_name}\n")
                    else:
                        f.write(f"{source_id}\n")

                    # Sort by rank
                    sorted_news = sorted(news_list, key=lambda x: x.rank)

                    for item in sorted_news:
                        line = f"{item.rank}. {item.title}"
                        if item.url:
                            line += f" [URL:{item.url}]"
                        if item.mobile_url:
                            line += f" [MOBILE:{item.mobile_url}]"
                        f.write(line + "\n")

                    f.write("\n")

                # Write failed sources
                if data.failed_ids:
                    f.write("==== Failed IDs ====\n")
                    for failed_id in data.failed_ids:
                        f.write(f"{failed_id}\n")

            print(f"[Local Storage] TXT snapshot saved: {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[Local Storage] Failed to save TXT snapshot: {e}")
            return None

    def save_html_report(self, html_content: str, filename: str, is_summary: bool = False) -> Optional[str]:
        """
        Save HTML report

        Args:
            html_content: HTML content
            filename: File name
            is_summary: Whether it is a summary report

        Returns:
            Saved file path
        """
        if not self.enable_html:
            return None

        try:
            date_folder = self._format_date_folder()
            html_dir = self.data_dir / date_folder / "html"
            html_dir.mkdir(parents=True, exist_ok=True)

            file_path = html_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"[Local Storage] HTML report saved: {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[Local Storage] Failed to save HTML report: {e}")
            return None

    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """
        Check if it's the first crawl of the day

        Args:
            date: Date string, defaults to today

        Returns:
            Whether it is the first crawl
        """
        try:
            db_path = self._get_db_path(date)
            if not db_path.exists():
                return True

            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) as count FROM crawl_records
            """)

            row = cursor.fetchone()
            count = row[0] if row else 0

            # If only one or no record, consider it as the first crawl
            return count <= 1

        except Exception as e:
            print(f"[Local Storage] Failed to check usage: {e}")
            return True

    def get_crawl_times(self, date: Optional[str] = None) -> List[str]:
        """
        Get list of all crawl times for a specific date

        Args:
            date: Date string, defaults to today

        Returns:
            List of crawl times (sorted by time)
        """
        try:
            db_path = self._get_db_path(date)
            if not db_path.exists():
                return []

            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT crawl_time FROM crawl_records
                ORDER BY crawl_time
            """)

            rows = cursor.fetchall()
            return [row[0] for row in rows]

        except Exception as e:
            print(f"[Local Storage] Failed to get crawl times: {e}")
            return []

    def cleanup(self) -> None:
        """Clean up resources (close database connection)"""
        for db_path, conn in self._db_connections.items():
            try:
                conn.close()
                print(f"[Local Storage] Closed database connection: {db_path}")
            except Exception as e:
                print(f"[Local Storage] Failed to close connection {db_path}: {e}")

        self._db_connections.clear()

    def cleanup_old_data(self, retention_days: int) -> int:
        """
        Clean up old data

        Args:
            retention_days: Retention days (0 means no cleanup)

        Returns:
            Number of deleted date directories
        """
        if retention_days <= 0:
            return 0

        deleted_count = 0
        cutoff_date = self._get_configured_time() - timedelta(days=retention_days)

        try:
            if not self.data_dir.exists():
                return 0

            for date_folder in self.data_dir.iterdir():
                if not date_folder.is_dir() or date_folder.name.startswith('.'):
                    continue

                # Parse date folder name (supports two formats)
                folder_date = None
                try:
                    # ISO format: YYYY-MM-DD
                    date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_folder.name)
                    if date_match:
                        folder_date = datetime(
                            int(date_match.group(1)),
                            int(date_match.group(2)),
                            int(date_match.group(3)),
                            tzinfo=pytz.timezone("Asia/Shanghai")
                        )
                    else:
                        # Old Chinese format: YYYY年MM月DD日
                        date_match = re.match(r'(\d{4})年(\d{2})月(\d{2})日', date_folder.name)
                        if date_match:
                            folder_date = datetime(
                                int(date_match.group(1)),
                                int(date_match.group(2)),
                                int(date_match.group(3)),
                                tzinfo=pytz.timezone("Asia/Shanghai")
                            )
                except Exception:
                    continue

                if folder_date and folder_date < cutoff_date:
                    # Close database connection for that date first
                    db_path = str(self._get_db_path(date_folder.name))
                    if db_path in self._db_connections:
                        try:
                            self._db_connections[db_path].close()
                            del self._db_connections[db_path]
                        except Exception:
                            pass

                    # Delete entire date directory
                    try:
                        shutil.rmtree(date_folder)
                        deleted_count += 1
                        print(f"[Local Storage] Cleaned up old data: {date_folder.name}")
                    except Exception as e:
                        print(f"[Local Storage] Failed to delete directory {date_folder.name}: {e}")

            if deleted_count > 0:
                print(f"[Local Storage] Total cleaned {deleted_count} old date directories")

            return deleted_count

        except Exception as e:
            print(f"[Local Storage] Failed to clean up: {e}")
            return deleted_count

    def has_pushed_today(self, date: Optional[str] = None) -> bool:
        """
        Check if pushed today

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Whether pushed
        """
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            target_date = self._format_date_folder(date)

            cursor.execute("""
                SELECT pushed FROM push_records WHERE date = ?
            """, (target_date,))

            row = cursor.fetchone()
            if row:
                return bool(row[0])
            return False

        except Exception as e:
            print(f"[Local Storage] Failed to check push record: {e}")
            return False

    def record_push(self, report_type: str, date: Optional[str] = None) -> bool:
        """
        Record push

        Args:
            report_type: Report type
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Whether recording was successful
        """
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            target_date = self._format_date_folder(date)
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO push_records (date, pushed, push_time, report_type, created_at)
                VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    pushed = 1,
                    push_time = excluded.push_time,
                    report_type = excluded.report_type
            """, (target_date, now_str, report_type, now_str))

            conn.commit()

            print(f"[Local Storage] Push recorded: {report_type} at {now_str}")
            return True

        except Exception as e:
            print(f"[Local Storage] Failed to record push: {e}")
            return False

    def __del__(self):
        """Destructor, ensures connection closure"""
        self.cleanup()
