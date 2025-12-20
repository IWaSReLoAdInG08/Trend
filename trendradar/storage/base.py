# coding=utf-8
"""
Storage Backend Abstract Base Class and Data Models

Defines a unified storage interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class NewsItem:
    """News Item Data Model"""

    title: str                          # News title
    source_id: str                      # Source platform ID (e.g., toutiao, baidu)
    source_name: str = ""               # Source platform name (used at runtime, not stored in DB)
    rank: int = 0                       # Rank
    url: str = ""                       # Link URL
    mobile_url: str = ""                # Mobile URL
    crawl_time: str = ""                # Crawl time (HH:MM format)

    # Statistics (for analysis)
    ranks: List[int] = field(default_factory=list)  # Historical rank list
    first_time: str = ""                # First appearance time
    last_time: str = ""                 # Last appearance time
    count: int = 1                      # Occurrence count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "rank": self.rank,
            "url": self.url,
            "mobile_url": self.mobile_url,
            "crawl_time": self.crawl_time,
            "ranks": self.ranks,
            "first_time": self.first_time,
            "last_time": self.last_time,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NewsItem":
        """Create from dictionary"""
        return cls(
            title=data.get("title", ""),
            source_id=data.get("source_id", ""),
            source_name=data.get("source_name", ""),
            rank=data.get("rank", 0),
            url=data.get("url", ""),
            mobile_url=data.get("mobile_url", ""),
            crawl_time=data.get("crawl_time", ""),
            ranks=data.get("ranks", []),
            first_time=data.get("first_time", ""),
            last_time=data.get("last_time", ""),
            count=data.get("count", 1),
        )


@dataclass
class NewsData:
    """
    News Data Collection

    Structure:
    - date: Date (YYYY-MM-DD)
    - crawl_time: Crawl time (HH:MM)
    - items: News items grouped by source ID
    - id_to_name: Source ID to name mapping
    - failed_ids: List of failed source IDs
    """

    date: str                                   # Date
    crawl_time: str                             # Crawl time
    items: Dict[str, List[NewsItem]]            # News grouped by source
    id_to_name: Dict[str, str] = field(default_factory=dict)   # ID to name mapping
    failed_ids: List[str] = field(default_factory=list)        # Failed IDs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        items_dict = {}
        for source_id, news_list in self.items.items():
            items_dict[source_id] = [item.to_dict() for item in news_list]

        return {
            "date": self.date,
            "crawl_time": self.crawl_time,
            "items": items_dict,
            "id_to_name": self.id_to_name,
            "failed_ids": self.failed_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NewsData":
        """Create from dictionary"""
        items = {}
        items_data = data.get("items", {})
        for source_id, news_list in items_data.items():
            items[source_id] = [NewsItem.from_dict(item) for item in news_list]

        return cls(
            date=data.get("date", ""),
            crawl_time=data.get("crawl_time", ""),
            items=items,
            id_to_name=data.get("id_to_name", {}),
            failed_ids=data.get("failed_ids", []),
        )

    def get_total_count(self) -> int:
        """Get total news count"""
        return sum(len(news_list) for news_list in self.items.values())

    def merge_with(self, other: "NewsData") -> "NewsData":
        """
        Merge another NewsData into current data

        Merge rules:
        - Merge rank history for news with same source_id + title
        - Update last_time and count
        - Keep the earlier first_time
        """
        merged_items = {}

        # Copy current data
        for source_id, news_list in self.items.items():
            merged_items[source_id] = {item.title: item for item in news_list}

        # Merge other data
        for source_id, news_list in other.items.items():
            if source_id not in merged_items:
                merged_items[source_id] = {}

            for item in news_list:
                if item.title in merged_items[source_id]:
                    # Merge existing news
                    existing = merged_items[source_id][item.title]

                    # Merge ranks
                    existing_ranks = set(existing.ranks) if existing.ranks else set()
                    new_ranks = set(item.ranks) if item.ranks else set()
                    merged_ranks = sorted(existing_ranks | new_ranks)
                    existing.ranks = merged_ranks

                    # Update times
                    if item.first_time and (not existing.first_time or item.first_time < existing.first_time):
                        existing.first_time = item.first_time
                    if item.last_time and (not existing.last_time or item.last_time > existing.last_time):
                        existing.last_time = item.last_time

                    # Update count
                    existing.count += 1

                    # Keep URL (if not present)
                    if not existing.url and item.url:
                        existing.url = item.url
                    if not existing.mobile_url and item.mobile_url:
                        existing.mobile_url = item.mobile_url
                else:
                    # Add new news
                    merged_items[source_id][item.title] = item

        # Convert back to list format
        final_items = {}
        for source_id, items_dict in merged_items.items():
            final_items[source_id] = list(items_dict.values())

        # Merge id_to_name
        merged_id_to_name = {**self.id_to_name, **other.id_to_name}

        # Merge failed_ids (deduplicate)
        merged_failed_ids = list(set(self.failed_ids + other.failed_ids))

        return NewsData(
            date=self.date or other.date,
            crawl_time=other.crawl_time,  # Use newer crawl time
            items=final_items,
            id_to_name=merged_id_to_name,
            failed_ids=merged_failed_ids,
        )


class StorageBackend(ABC):
    """
    Storage Backend Abstract Base Class

    All storage backends must implement these methods to support:
    - Save news data
    - Read all data for today
    - Detect new news
    - Generate report files (TXT/HTML)
    """

    @abstractmethod
    def save_news_data(self, data: NewsData) -> bool:
        """
        Save news data

        Args:
            data: News data

        Returns:
            Whether save was successful
        """
        pass

    @abstractmethod
    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """
        Get all news data for a specific date

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Merged news data, or None if no data
        """
        pass

    @abstractmethod
    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """
        Get data from the latest crawl

        Args:
            date: Date string, defaults to today

        Returns:
            Latest crawl news data
        """
        pass

    @abstractmethod
    def detect_new_titles(self, current_data: NewsData) -> Dict[str, Dict]:
        """
        Detect new titles

        Args:
            current_data: Currently crawled data

        Returns:
            New title data, format: {source_id: {title: title_data}}
        """
        pass

    @abstractmethod
    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """
        Save TXT snapshot (optional feature, available in local environment)

        Args:
            data: News data

        Returns:
            Saved file path, or None if not supported
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """
        Check if it is the first crawl of the day

        Args:
            date: Date string, defaults to today

        Returns:
            Whether it is the first crawl
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """
        Clean up resources (e.g., temporary files, database connections)
        """
        pass

    @abstractmethod
    def cleanup_old_data(self, retention_days: int) -> int:
        """
        Clean up old data

        Args:
            retention_days: Retention days (0 means no cleanup)

        Returns:
            Number of deleted date directories
        """
        pass

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """
        Storage backend name
        """
        pass

    @property
    @abstractmethod
    def supports_txt(self) -> bool:
        """
        Whether TXT snapshot generation is supported
        """
        pass

    # === Push Record Related Methods ===

    @abstractmethod
    def has_pushed_today(self, date: Optional[str] = None) -> bool:
        """
        Check if pushed today

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Whether pushed
        """
        pass

    @abstractmethod
    def record_push(self, report_type: str, date: Optional[str] = None) -> bool:
        """
        Record push

        Args:
            report_type: Report type
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Whether recording was successful
        """
        pass


def convert_crawl_results_to_news_data(
    results: Dict[str, Dict],
    id_to_name: Dict[str, str],
    failed_ids: List[str],
    crawl_time: str,
    crawl_date: str,
) -> NewsData:
    """
    Convert crawl results to NewsData format

    Args:
        results: Crawl results {source_id: {title: {ranks: [], url: "", mobileUrl: ""}}}
        id_to_name: Source ID to name mapping
        failed_ids: Failed source IDs
        crawl_time: Crawl time (HH:MM)
        crawl_date: Crawl date (YYYY-MM-DD)

    Returns:
        NewsData object
    """
    items = {}

    for source_id, titles_data in results.items():
        source_name = id_to_name.get(source_id, source_id)
        news_list = []

        for title, data in titles_data.items():
            if isinstance(data, dict):
                ranks = data.get("ranks", [])
                url = data.get("url", "")
                mobile_url = data.get("mobileUrl", "")
            else:
                # Compatible with old format
                ranks = data if isinstance(data, list) else []
                url = ""
                mobile_url = ""

            rank = ranks[0] if ranks else 99

            news_item = NewsItem(
                title=title,
                source_id=source_id,
                source_name=source_name,
                rank=rank,
                url=url,
                mobile_url=mobile_url,
                crawl_time=crawl_time,
                ranks=ranks,
                first_time=crawl_time,
                last_time=crawl_time,
                count=1,
            )
            news_list.append(news_item)

        items[source_id] = news_list

    return NewsData(
        date=crawl_date,
        crawl_time=crawl_time,
        items=items,
        id_to_name=id_to_name,
        failed_ids=failed_ids,
    )


def convert_news_data_to_results(data: NewsData) -> tuple:
    """
    Convert NewsData back to original results format (for compatibility with existing code)

    Args:
        data: NewsData object

    Returns:
        (results, id_to_name, title_info) tuple
    """
    results = {}
    title_info = {}

    for source_id, news_list in data.items.items():
        results[source_id] = {}
        title_info[source_id] = {}

        for item in news_list:
            results[source_id][item.title] = {
                "ranks": item.ranks,
                "url": item.url,
                "mobileUrl": item.mobile_url,
            }

            title_info[source_id][item.title] = {
                "first_time": item.first_time,
                "last_time": item.last_time,
                "count": item.count,
                "ranks": item.ranks,
                "url": item.url,
                "mobileUrl": item.mobile_url,
            }

    return results, data.id_to_name, title_info
