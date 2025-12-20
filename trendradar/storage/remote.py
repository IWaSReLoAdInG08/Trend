# coding=utf-8
"""
Remote Storage Backend (S3 Compatible Protocol)

Supports Cloudflare R2, Aliyun OSS, Tencent Cloud COS, AWS S3, MinIO, etc.
Uses S3 compatible API (boto3) to access object storage.
Data flow: Download today's SQLite -> Merge new data -> Upload back to remote
"""

import pytz
import re
import shutil
import sys
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None
    BotoConfig = None
    ClientError = Exception

from trendradar.storage.base import StorageBackend, NewsItem, NewsData
from trendradar.utils.time import (
    get_configured_time,
    format_date_folder,
    format_time_filename,
)
from trendradar.utils.url import normalize_url


class RemoteStorageBackend(StorageBackend):
    """
    Remote Storage Backend (S3 Compatible Protocol)

    Features:
    - Uses S3 compatible API to access remote storage
    - Supports Cloudflare R2, Aliyun OSS, Tencent Cloud COS, AWS S3, MinIO, etc.
    - Downloads SQLite to a temporary directory for operations
    - Supports data merging and uploading
    - Supports pulling historical data from remote to local
    - Automatically cleans up temporary files after execution
    """

    def __init__(
        self,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str,
        region: str = "",
        enable_txt: bool = False,  # Remote mode defaults to not generating TXT
        enable_html: bool = True,
        temp_dir: Optional[str] = None,
        timezone: str = "Asia/Shanghai",
    ):
        """
        Initialize Remote Storage Backend

        Args:
            bucket_name: Bucket name
            access_key_id: Access key ID
            secret_access_key: Secret access key
            endpoint_url: Service endpoint URL
            region: Region (optional, required by some providers)
            enable_txt: Whether to enable TXT snapshot (default off)
            enable_html: Whether to enable HTML report
            temp_dir: Temporary directory path (default uses system temp dir)
            timezone: Timezone config (default Asia/Shanghai)
        """
        if not HAS_BOTO3:
            raise ImportError("Remote storage backend requires boto3: pip install boto3")

        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region = region
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.timezone = timezone

        # Create temp directory
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="trendradar_"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Initialize S3 client
        # Use virtual-hosted style addressing (mainstream)
        # Select signature version based on provider:
        # - Tencent Cloud COS uses SigV2 to avoid chunked encoding issues
        # - Other providers (AWS S3, Cloudflare R2, Aliyun OSS, MinIO, etc.) default to SigV4
        is_tencent_cos = "myqcloud.com" in endpoint_url.lower()
        signature_version = 's3' if is_tencent_cos else 's3v4'

        s3_config = BotoConfig(
            s3={"addressing_style": "virtual"},
            signature_version=signature_version,
        )

        client_kwargs = {
            "endpoint_url": endpoint_url,
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "config": s3_config,
        }
        if region:
            client_kwargs["region_name"] = region

        self.s3_client = boto3.client("s3", **client_kwargs)

        # Track downloaded files (for cleanup)
        self._downloaded_files: List[Path] = []
        self._db_connections: Dict[str, sqlite3.Connection] = {}

        print(f"[Remote Storage] Initialized, Bucket: {bucket_name}, Signature Version: {signature_version}")

    @property
    def backend_name(self) -> str:
        return "remote"

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

    def _get_remote_db_key(self, date: Optional[str] = None) -> str:
        """Get object key for SQLite file in remote storage"""
        date_folder = self._format_date_folder(date)
        return f"news/{date_folder}.db"

    def _get_local_db_path(self, date: Optional[str] = None) -> Path:
        """Get local temporary SQLite file path"""
        date_folder = self._format_date_folder(date)
        return self.temp_dir / date_folder / "news.db"

    def _check_object_exists(self, r2_key: str) -> bool:
        """
        Check if object exists in remote storage

        Args:
            r2_key: Remote object key

        Returns:
            Whether exists
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=r2_key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            # S3 compatible storage may return 404, NoSuchKey, or other variants
            if error_code in ("404", "NoSuchKey", "Not Found"):
                return False
            # Other errors (like permission issues) are also treated as non-existent, but print warning
            print(f"[Remote Storage] Failed to check object existence ({r2_key}): {e}")
            return False
        except Exception as e:
            print(f"[Remote Storage] Exception checking object existence ({r2_key}): {e}")
            return False

    def _download_sqlite(self, date: Optional[str] = None) -> Optional[Path]:
        """
        Download today's SQLite file from remote storage to local temp directory

        Uses get_object + iter_chunks instead of download_file,
        to correctly handle chunked transfer encoding for Tencent Cloud COS.

        Args:
            date: Date string

        Returns:
            Local file path, or None if not exists
        """
        r2_key = self._get_remote_db_key(date)
        local_path = self._get_local_db_path(date)

        # Ensure directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists first
        if not self._check_object_exists(r2_key):
            print(f"[Remote Storage] File does not exist, creating new database: {r2_key}")
            return None

        try:
            # Use get_object + iter_chunks instead of download_file
            # iter_chunks automatically handles chunked transfer encoding
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=r2_key)
            with open(local_path, 'wb') as f:
                for chunk in response['Body'].iter_chunks(chunk_size=1024*1024):
                    f.write(chunk)
            self._downloaded_files.append(local_path)
            print(f"[Remote Storage] Downloaded: {r2_key} -> {local_path}")
            return local_path
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            # S3 compatible storage may return different error codes
            if error_code in ("404", "NoSuchKey", "Not Found"):
                print(f"[Remote Storage] File does not exist, creating new database: {r2_key}")
                return None
            else:
                print(f"[Remote Storage] Download failed (Error Code: {error_code}): {e}")
                raise
        except Exception as e:
            print(f"[Remote Storage] Download exception: {e}")
            raise

    def _upload_sqlite(self, date: Optional[str] = None) -> bool:
        """
        Upload local SQLite file to remote storage

        Args:
            date: Date string

        Returns:
            Whether upload was successful
        """
        local_path = self._get_local_db_path(date)
        r2_key = self._get_remote_db_key(date)

        if not local_path.exists():
            print(f"[Remote Storage] Local file does not exist, cannot upload: {local_path}")
            return False

        try:
            # Get local file size
            local_size = local_path.stat().st_size
            print(f"[Remote Storage] Preparing to upload: {local_path} ({local_size} bytes) -> {r2_key}")

            # Read file content as bytes then upload
            # Avoid requests library using chunked transfer encoding when passing file object
            # Tencent Cloud COS and other S3 compatible services may not handle chunked encoding correctly
            with open(local_path, 'rb') as f:
                file_content = f.read()

            # Use put_object and explicitly set ContentLength to ensure chunked encoding is not used
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=r2_key,
                Body=file_content,
                ContentLength=local_size,
                ContentType='application/x-sqlite3',
            )
            print(f"[Remote Storage] Uploaded: {local_path} -> {r2_key}")

            # Verify upload success
            if self._check_object_exists(r2_key):
                print(f"[Remote Storage] Upload verification successful: {r2_key}")
                return True
            else:
                print(f"[Remote Storage] Upload verification failed: File not found in remote storage")
                return False

        except Exception as e:
            print(f"[Remote Storage] Upload failed: {e}")
            return False

    def _get_connection(self, date: Optional[str] = None) -> sqlite3.Connection:
        """Get database connection"""
        local_path = self._get_local_db_path(date)
        db_path = str(local_path)

        if db_path not in self._db_connections:
            # Ensure directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # If not exists locally, try downloading from remote storage
            if not local_path.exists():
                self._download_sqlite(date)

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
        Save news data to remote storage (using URL as unique identifier, supports title update detection)

        Flow: Download existing DB -> Insert/Update data -> Upload back to remote storage

        Args:
            data: News data

        Returns:
            Whether save was successful
        """
        try:
            conn = self._get_connection(data.date)
            cursor = conn.cursor()

            # Query existing record count
            cursor.execute("SELECT COUNT(*) as count FROM news_items")
            row = cursor.fetchone()
            existing_count = row[0] if row else 0
            if existing_count > 0:
                print(f"[Remote Storage] Found {existing_count} existing records, merging new data")

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
                        print(f"[Remote Storage] Failed to save news item [{item.title[:30]}...]: {e}")

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

            # Query total records after merge
            cursor.execute("SELECT COUNT(*) as count FROM news_items")
            row = cursor.fetchone()
            final_count = row[0] if row else 0

            # Output detailed storage statistics log
            log_parts = [f"[Remote Storage] Completed: New {new_count}"]
            if updated_count > 0:
                log_parts.append(f"Updated {updated_count}")
            if title_changed_count > 0:
                log_parts.append(f"Title Changed {title_changed_count}")
            log_parts.append(f"(Total after deduplication: {final_count})")
            print(", ".join(log_parts))

            # Upload to remote storage
            if self._upload_sqlite(data.date):
                print(f"[Remote Storage] Data synced to remote storage")
                return True
            else:
                print(f"[Remote Storage] Failed to upload to remote storage")
                return False

        except Exception as e:
            print(f"[Remote Storage] Save failed: {e}")
            return False

    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Get all news data for a specific date (merged)"""
        try:
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
            print(f"[Remote Storage] Failed to read data: {e}")
            return None

    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Get data from the latest crawl"""
        try:
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

            # Get news data for that time, JOIN to get platform name
            cursor.execute("""
                SELECT n.title, n.platform_id, p.name as platform_name,
                       n.rank, n.url, n.mobile_url,
                       n.first_crawl_time, n.last_crawl_time, n.crawl_count
                FROM news_items n
                LEFT JOIN platforms p ON n.platform_id = p.id
                WHERE n.last_crawl_time = ?
            """, (latest_time,))

            rows = cursor.fetchall()
            if not rows:
                return None

            items: Dict[str, List[NewsItem]] = {}
            id_to_name: Dict[str, str] = {}
            crawl_date = self._format_date_folder(date)

            for row in rows:
                platform_id = row[1]
                platform_name = row[2] or platform_id
                id_to_name[platform_id] = platform_name

                if platform_id not in items:
                    items[platform_id] = []

                items[platform_id].append(NewsItem(
                    title=row[0],
                    source_id=platform_id,
                    source_name=platform_name,
                    rank=row[3],
                    url=row[4] or "",
                    mobile_url=row[5] or "",
                    crawl_time=row[7],  # last_crawl_time
                    ranks=[row[3]],
                    first_time=row[6],  # first_crawl_time
                    last_time=row[7],   # last_crawl_time
                    count=row[8],       # crawl_count
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
            print(f"[Remote Storage] Failed to get latest data: {e}")
            return None

    def detect_new_titles(self, current_data: NewsData) -> Dict[str, Dict]:
        """
        Detect new titles

        Compares current crawl data with historical data to find new titles.
        Key logic: Only titles that have never appeared in historical batches count as new.
        """
        try:
            historical_data = self.get_today_all_data(current_data.date)

            if not historical_data:
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
            print(f"[Remote Storage] Failed to detect new titles: {e}")
            return {}

    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """Save TXT snapshot (remote mode defaults to unsupported)"""
        if not self.enable_txt:
            return None

        # If enabled, save to local temp directory
        try:
            date_folder = self._format_date_folder(data.date)
            txt_dir = self.temp_dir / date_folder / "txt"
            txt_dir.mkdir(parents=True, exist_ok=True)

            file_path = txt_dir / f"{data.crawl_time}.txt"

            with open(file_path, "w", encoding="utf-8") as f:
                for source_id, news_list in data.items.items():
                    source_name = data.id_to_name.get(source_id, source_id)

                    if source_name and source_name != source_id:
                        f.write(f"{source_id} | {source_name}\n")
                    else:
                        f.write(f"{source_id}\n")

                    sorted_news = sorted(news_list, key=lambda x: x.rank)

                    for item in sorted_news:
                        line = f"{item.rank}. {item.title}"
                        if item.url:
                            line += f" [URL:{item.url}]"
                        if item.mobile_url:
                            line += f" [MOBILE:{item.mobile_url}]"
                        f.write(line + "\n")

                    f.write("\n")

                if data.failed_ids:
                    f.write("==== Failed IDs ====\n")
                    for failed_id in data.failed_ids:
                        f.write(f"{failed_id}\n")

            print(f"[Remote Storage] TXT snapshot saved: {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[Remote Storage] Failed to save TXT snapshot: {e}")
            return None

    def save_html_report(self, html_content: str, filename: str, is_summary: bool = False) -> Optional[str]:
        """Save HTML report to temporary directory"""
        if not self.enable_html:
            return None

        try:
            date_folder = self._format_date_folder()
            html_dir = self.temp_dir / date_folder / "html"
            html_dir.mkdir(parents=True, exist_ok=True)

            file_path = html_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"[Remote Storage] HTML report saved: {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[Remote Storage] Failed to save HTML report: {e}")
            return None

    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """Check if it's the first crawl of the day"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) as count FROM crawl_records
            """)

            row = cursor.fetchone()
            count = row[0] if row else 0

            return count <= 1

        except Exception as e:
            print(f"[Remote Storage] Failed to check usage: {e}")
            return True

    def cleanup(self) -> None:
        """Clean up resources (close database connection and delete temporary files)"""
        # Check if Python is shutting down
        if sys.meta_path is None:
            return

        # Close database connection
        db_connections = getattr(self, "_db_connections", {})
        for db_path, conn in list(db_connections.items()):
            try:
                conn.close()
                print(f"[Remote Storage] Closed database connection: {db_path}")
            except Exception as e:
                print(f"[Remote Storage] Failed to close connection {db_path}: {e}")

        if db_connections:
            db_connections.clear()

        # Delete temporary directory
        temp_dir = getattr(self, "temp_dir", None)
        if temp_dir:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    print(f"[Remote Storage] Temporary directory cleaned: {temp_dir}")
            except Exception as e:
                # Ignore error when Python keeps shutting down
                if sys.meta_path is not None:
                    print(f"[Remote Storage] Failed to clean temporary directory: {e}")

        downloaded_files = getattr(self, "_downloaded_files", None)
        if downloaded_files:
            downloaded_files.clear()

    def cleanup_old_data(self, retention_days: int) -> int:
        """
        Clean up old data in remote storage

        Args:
            retention_days: Retention days (0 means no cleanup)

        Returns:
            Number of deleted database files
        """
        if retention_days <= 0:
            return 0

        deleted_count = 0
        cutoff_date = self._get_configured_time() - timedelta(days=retention_days)

        try:
            # List all objects under the news/ prefix in remote storage
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix="news/")

            # Collect objects to delete
            objects_to_delete = []
            deleted_dates = set()

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']

                    # Parse date (format: news/YYYY-MM-DD.db or news/YYYY年MM月DD日.db)
                    folder_date = None
                    try:
                        # ISO format: news/YYYY-MM-DD.db
                        date_match = re.match(r'news/(\d{4})-(\d{2})-(\d{2})\.db$', key)
                        if date_match:
                            folder_date = datetime(
                                int(date_match.group(1)),
                                int(date_match.group(2)),
                                int(date_match.group(3)),
                                tzinfo=pytz.timezone("Asia/Shanghai")
                            )
                            date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                        else:
                            # Old Chinese format: news/YYYY年MM月DD日.db
                            date_match = re.match(r'news/(\d{4})年(\d{2})月(\d{2})日\.db$', key)
                            if date_match:
                                folder_date = datetime(
                                    int(date_match.group(1)),
                                    int(date_match.group(2)),
                                    int(date_match.group(3)),
                                    tzinfo=pytz.timezone("Asia/Shanghai")
                                )
                                date_str = f"{date_match.group(1)}年{date_match.group(2)}月{date_match.group(3)}日"
                    except Exception:
                        continue

                    if folder_date and folder_date < cutoff_date:
                        objects_to_delete.append({'Key': key})
                        deleted_dates.add(date_str)

            # Batch delete objects (maximum 1000 at a time)
            if objects_to_delete:
                batch_size = 1000
                for i in range(0, len(objects_to_delete), batch_size):
                    batch = objects_to_delete[i:i + batch_size]
                    try:
                        self.s3_client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': batch}
                        )
                        print(f"[Remote Storage] Deleted {len(batch)} objects")
                    except Exception as e:
                        print(f"[Remote Storage] Batch delete failed: {e}")

                deleted_count = len(deleted_dates)
                for date_str in sorted(deleted_dates):
                    print(f"[Remote Storage] Cleaned up old data: news/{date_str}.db")

                print(f"[Remote Storage] Total cleaned {deleted_count} old date database files")

            return deleted_count

        except Exception as e:
            print(f"[Remote Storage] Failed to clean up: {e}")
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
            print(f"[Remote Storage] Failed to check push record: {e}")
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

            print(f"[Remote Storage] Push recorded: {report_type} at {now_str}")

            # Upload to remote storage to ensure persistence
            if self._upload_sqlite(date):
                print(f"[Remote Storage] Push record synced to remote storage")
                return True
            else:
                print(f"[Remote Storage] Failed to sync push record to remote storage")
                return False

        except Exception as e:
            print(f"[Remote Storage] Failed to record push: {e}")
            return False

    def __del__(self):
        """Destructor"""
        # Check if Python is shutting down
        if sys.meta_path is None:
            return
        try:
            self.cleanup()
        except Exception:
            # Ignore errors during Python shutdown
            pass

    def pull_recent_days(self, days: int, local_data_dir: str = "output") -> int:
        """
        Pull recent N days' data from remote to local

        Args:
            days: Number of days to pull
            local_data_dir: Local data directory

        Returns:
            Number of successfully pulled database files
        """
        if days <= 0:
            return 0

        local_dir = Path(local_data_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        pulled_count = 0
        now = self._get_configured_time()

        print(f"[Remote Storage] Starting to pull last {days} days of data...")

        for i in range(days):
            date = now - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            # Local target path
            local_date_dir = local_dir / date_str
            local_db_path = local_date_dir / "news.db"

            # Skip if already exists locally
            if local_db_path.exists():
                print(f"[Remote Storage] Skipped (Exists locally): {date_str}")
                continue

            # Remote object key
            remote_key = f"news/{date_str}.db"

            # Check if exists in remote
            if not self._check_object_exists(remote_key):
                print(f"[Remote Storage] Skipped (Remote does not exist): {date_str}")
                continue

            # Download (use get_object + iter_chunks to handle chunked encoding)
            try:
                local_date_dir.mkdir(parents=True, exist_ok=True)
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=remote_key)
                with open(local_db_path, 'wb') as f:
                    for chunk in response['Body'].iter_chunks(chunk_size=1024*1024):
                        f.write(chunk)
                print(f"[Remote Storage] Pulled: {remote_key} -> {local_db_path}")
                pulled_count += 1
            except Exception as e:
                print(f"[Remote Storage] Pull failed ({date_str}): {e}")

        print(f"[Remote Storage] Pull completed, downloaded {pulled_count} database files")
        return pulled_count

    def list_remote_dates(self) -> List[str]:
        """
        List all available dates in remote storage

        Returns:
            List of date strings (YYYY-MM-DD format)
        """
        dates = []

        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix="news/")

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']
                    # Parse date
                    date_match = re.match(r'news/(\d{4}-\d{2}-\d{2})\.db$', key)
                    if date_match:
                        dates.append(date_match.group(1))

            return sorted(dates, reverse=True)

        except Exception as e:
            print(f"[Remote Storage] Failed to list remote dates: {e}")
            return []
