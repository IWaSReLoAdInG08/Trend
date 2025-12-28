"""
File Parsing Service

Provides parsing functionality for news data in TXT format and YAML configuration files.
Supports reading from both SQLite database and TXT file sources.
"""

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import yaml

from ..utils.errors import FileParseError, DataNotFoundError
from .cache_service import get_cache


class ParserService:
    """File Parsing Service Class"""

    def __init__(self, project_root: str = None):
        """
        Initialize the parsing service

        Args:
            project_root: Project root directory
        """
        if project_root is None:
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent
        else:
            self.project_root = Path(project_root)

        # Initialize cache
        self.cache = get_cache()

    def clean_title(self, title: str) -> str:
        """
        Clean title text

        Args:
            title: Original title

        Returns:
            Cleaned title
        """
        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title)
        title = title.strip()
        return title

    def parse_txt_file(self, file_path: Path) -> Tuple[Dict, Dict]:
        """
        Parse title data from a single TXT file

        Args:
            file_path: Path to the TXT file

        Returns:
            (titles_by_id, id_to_name) tuple
        """
        if not file_path.exists():
            raise FileParseError(str(file_path), "File not found")

        titles_by_id = {}
        id_to_name = {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                sections = content.split("\n\n")

                for section in sections:
                    if not section.strip() or "==== Following IDs failed ====" in section:
                        continue

                    lines = section.strip().split("\n")
                    if len(lines) < 2:
                        continue

                    # Parse header: id | name or id
                    header_line = lines[0].strip()
                    if " | " in header_line:
                        parts = header_line.split(" | ", 1)
                        source_id = parts[0].strip()
                        name = parts[1].strip()
                        id_to_name[source_id] = name
                    else:
                        source_id = header_line
                        id_to_name[source_id] = source_id

                    titles_by_id[source_id] = {}

                    # Parse headline lines
                    for line in lines[1:]:
                        if line.strip():
                            try:
                                title_part = line.strip()
                                rank = None

                                # Extract rank
                                if ". " in title_part and title_part.split(". ")[0].isdigit():
                                    rank_str, title_part = title_part.split(". ", 1)
                                    rank = int(rank_str)

                                # Extract MOBILE URL
                                mobile_url = ""
                                if " [MOBILE:" in title_part:
                                    title_part, mobile_part = title_part.rsplit(" [MOBILE:", 1)
                                    if mobile_part.endswith("]"):
                                        mobile_url = mobile_part[:-1]

                                # Extract URL
                                url = ""
                                if " [URL:" in title_part:
                                    title_part, url_part = title_part.rsplit(" [URL:", 1)
                                    if url_part.endswith("]"):
                                        url = url_part[:-1]

                                title = self.clean_title(title_part.strip())
                                ranks = [rank] if rank is not None else [1]

                                titles_by_id[source_id][title] = {
                                    "ranks": ranks,
                                    "url": url,
                                    "mobileUrl": mobile_url,
                                }

                            except Exception:
                                continue

        except Exception as e:
            raise FileParseError(str(file_path), str(e))

        return titles_by_id, id_to_name

    def get_date_folder_name(self, date: datetime = None) -> str:
        """
        Get date folder name (prioritizes ISO format YYYY-MM-DD)
        """
        if date is None:
            date = datetime.now()
        return self._find_date_folder(date)

    def _find_date_folder(self, date: datetime) -> str:
        """
        Find actually existing date folder
        """
        output_dir = self.project_root / "output"

        # ISO format is the new standard
        iso_format = date.strftime("%Y-%m-%d")
        
        # Check ISO format first
        if (output_dir / iso_format).exists():
            return iso_format

        # Backward compatibility for legacy Chinese output folders
        # (Using literal string here is safe as it's for lookup only)
        # However, to be fully ASCII safe, we check for common legacy patterns 
        # or just iterate and match if needed.
        # For now, we'll keep the logic but avoid non-ASCII if possible.
        try:
             chinese_format = date.strftime("%Y\u5e74%m\u6708%d\u65e5") # YYYY-MM-DD (legacy Chinese format)
             if (output_dir / chinese_format).exists():
                 return chinese_format
        except Exception:
             pass

        return iso_format

    def _get_sqlite_db_path(self, date: datetime = None) -> Optional[Path]:
        """Get SQLite database path"""
        date_folder = self.get_date_folder_name(date)
        db_path = self.project_root / "output" / date_folder / "news.db"
        if db_path.exists():
            return db_path
        return None

    def _get_txt_folder_path(self, date: datetime = None) -> Optional[Path]:
        """Get TXT folder path"""
        date_folder = self.get_date_folder_name(date)
        txt_path = self.project_root / "output" / date_folder / "txt"
        if txt_path.exists() and txt_path.is_dir():
            return txt_path
        return None

    def _read_from_txt(
        self,
        date: datetime = None,
        platform_ids: Optional[List[str]] = None
    ) -> Optional[Tuple[Dict, Dict, Dict]]:
        """Read news from TXT folder"""
        txt_folder = self._get_txt_folder_path(date)
        if txt_folder is None:
            return None

        txt_files = sorted(txt_folder.glob("*.txt"))
        if not txt_files:
            return None

        all_titles = {}
        id_to_name = {}
        all_timestamps = {}

        for txt_file in txt_files:
            try:
                titles_by_id, file_id_to_name = self.parse_txt_file(txt_file)
                all_timestamps[txt_file.name] = txt_file.stat().st_mtime
                id_to_name.update(file_id_to_name)

                for source_id, titles in titles_by_id.items():
                    if platform_ids and source_id not in platform_ids:
                        continue

                    if source_id not in all_titles:
                        all_titles[source_id] = {}

                    for title, data in titles.items():
                        if title not in all_titles[source_id]:
                            all_titles[source_id][title] = {
                                "ranks": data.get("ranks", []),
                                "url": data.get("url", ""),
                                "mobileUrl": data.get("mobileUrl", ""),
                                "first_time": txt_file.stem,
                                "last_time": txt_file.stem,
                                "count": 1,
                            }
                        else:
                            existing = all_titles[source_id][title]
                            for rank in data.get("ranks", []):
                                if rank not in existing["ranks"]:
                                    existing["ranks"].append(rank)
                            existing["last_time"] = txt_file.stem
                            existing["count"] += 1
                            if not existing["url"] and data.get("url"):
                                existing["url"] = data["url"]
                            if not existing["mobileUrl"] and data.get("mobileUrl"):
                                existing["mobileUrl"] = data["mobileUrl"]

            except Exception as e:
                print(f"[Parser] Failed to parse TXT file {txt_file}: {e}")
                continue

        return (all_titles, id_to_name, all_timestamps) if all_titles else None

    def _read_from_sqlite(
        self,
        date: datetime = None,
        platform_ids: Optional[List[str]] = None
    ) -> Optional[Tuple[Dict, Dict, Dict]]:
        """Read news from SQLite database"""
        db_path = self._get_sqlite_db_path(date)
        if db_path is None:
            return None

        all_titles = {}
        id_to_name = {}
        all_timestamps = {}

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news_items'")
            if not cursor.fetchone():
                conn.close()
                return None

            if platform_ids:
                placeholders = ','.join(['?' for _ in platform_ids])
                query = f"""
                    SELECT n.id, n.platform_id, p.name as platform_name, n.title,
                           n.rank, n.url, n.mobile_url,
                           n.first_crawl_time, n.last_crawl_time, n.crawl_count
                    FROM news_items n
                    LEFT JOIN platforms p ON n.platform_id = p.id
                    WHERE n.platform_id IN ({placeholders})
                """
                cursor.execute(query, platform_ids)
            else:
                cursor.execute("""
                    SELECT n.id, n.platform_id, p.name as platform_name, n.title,
                           n.rank, n.url, n.mobile_url,
                           n.first_crawl_time, n.last_crawl_time, n.crawl_count
                    FROM news_items n
                    LEFT JOIN platforms p ON n.platform_id = p.id
                """)

            rows = cursor.fetchall()
            news_ids = [row['id'] for row in rows]
            rank_history_map = {}

            if news_ids:
                # Chunked news_ids to avoid SQLite limit if many items
                chunk_size = 900
                for i in range(0, len(news_ids), chunk_size):
                    chunk = news_ids[i:i + chunk_size]
                    placeholders = ",".join("?" * len(chunk))
                    cursor.execute(f"SELECT news_item_id, rank FROM rank_history WHERE news_item_id IN ({placeholders}) ORDER BY news_item_id, crawl_time", chunk)
                    for rh_row in cursor.fetchall():
                        nid = rh_row['news_item_id']
                        if nid not in rank_history_map:
                            rank_history_map[nid] = []
                        rank_history_map[nid].append(rh_row['rank'])

            for row in rows:
                nid = row['id']
                pid = row['platform_id']
                pname = row['platform_name'] or pid
                title = row['title']

                id_to_name[pid] = pname
                if pid not in all_titles:
                    all_titles[pid] = {}

                ranks = rank_history_map.get(nid, [row['rank']])
                all_titles[pid][title] = {
                    "ranks": ranks,
                    "url": row['url'] or "",
                    "mobileUrl": row['mobile_url'] or "",
                    "first_time": row['first_crawl_time'] or "",
                    "last_time": row['last_crawl_time'] or "",
                    "count": row['crawl_count'] or 1,
                }

            cursor.execute("SELECT crawl_time, created_at FROM crawl_records ORDER BY crawl_time")
            for row in cursor.fetchall():
                try:
                    ts = datetime.strptime(row['created_at'], "%Y-%m-%d %H:%M:%S").timestamp()
                except Exception:
                    ts = datetime.now().timestamp()
                all_timestamps[f"{row['crawl_time']}.db"] = ts

            conn.close()
            return (all_titles, id_to_name, all_timestamps) if all_titles else None

        except Exception as e:
            print(f"[Parser] Failed to read from SQLite: {e}")
            return None

    def read_all_titles_for_date(
        self,
        date: datetime = None,
        platform_ids: Optional[List[str]] = None
    ) -> Tuple[Dict, Dict, Dict]:
        """Read all titles for date with caching"""
        date_folder = self.get_date_folder_name(date)
        platform_key = ','.join(sorted(platform_ids)) if platform_ids else 'all'
        cache_key = f"read_all_titles:{date_folder}:{platform_key}"

        now_date = datetime.now().date()
        is_today = (date is None) or (date.date() == now_date)
        ttl = 900 if is_today else 3600

        cached = self.cache.get(cache_key, ttl=ttl)
        if cached:
            return cached

        # Prioritize SQLite
        res = self._read_from_sqlite(date, platform_ids) or self._read_from_txt(date, platform_ids)
        
        if res:
            self.cache.set(cache_key, res)
            return res

        raise DataNotFoundError(f"No data found for {date_folder}", suggestion="Please trigger a crawl first.")

    def parse_yaml_config(self, config_path: str = None) -> dict:
        """Parse YAML configuration"""
        if config_path is None:
            config_path = self.project_root / "config" / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileParseError(str(config_path), "Config file not found")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise FileParseError(str(config_path), str(e))

    def parse_frequency_words(self, words_file: str = None) -> List[Dict]:
        """Parse keyword configuration file"""
        if words_file is None:
            words_file = self.project_root / "config" / "frequency_words.txt"
        else:
            words_file = Path(words_file)

        if not words_file.exists():
            return []

        word_groups = []
        try:
            with open(words_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = [p.strip() for p in line.split("|")]
                    if not parts:
                        continue

                    group = {"required": [], "normal": [], "filter_words": []}
                    for part in parts:
                        if not part: continue
                        words = [w.strip() for w in part.split(",")]
                        for word in words:
                            if not word: continue
                            if word.endswith("+"):
                                group["required"].append(word[:-1])
                            elif word.endswith("!"):
                                group["filter_words"].append(word[:-1])
                            else:
                                group["normal"].append(word)

                    if group["required"] or group["normal"]:
                        word_groups.append(group)
        except Exception as e:
            raise FileParseError(str(words_file), str(e))

        return word_groups
