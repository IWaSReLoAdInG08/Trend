# coding=utf-8
"""
App Context Module

Provides the AppContext class, encapsulating all configuration dependencies,
eliminating global state and wrapper functions.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from trendradar.utils.time import (
    get_configured_time,
    format_date_folder,
    format_time_filename,
    get_current_time_display,
    convert_time_for_display,
)
from trendradar.core import (
    load_frequency_words,
    matches_word_groups,
    save_titles_to_file,
    read_all_today_titles,
    detect_latest_new_titles,
    is_first_crawl_today,
    count_word_frequency,
    group_by_categories,
)
from trendradar.report import (
    clean_title,
    prepare_report_data,
    generate_html_report,
    render_html_content,
)
from trendradar.notification import (
    render_feishu_content,
    render_dingtalk_content,
    split_content_into_batches,
    NotificationDispatcher,
    PushRecordManager,
)
from trendradar.storage import get_storage_manager


class AppContext:
    """
    App Context Class

    Encapsulates all configuration dependencies, providing a unified interface.
    Eliminates dependency on global CONFIG, improving testability.

    Usage Example:
        config = load_config()
        ctx = AppContext(config)

        # Time operations
        now = ctx.get_time()
        date_folder = ctx.format_date()

        # Storage operations
        storage = ctx.get_storage_manager()

        # Report generation
        html = ctx.generate_html_report(stats, total_titles, ...)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize App Context

        Args:
            config: Complete configuration dictionary
        """
        self.config = config
        self._storage_manager = None

    # === Config Access ===

    @property
    def timezone(self) -> str:
        """Get configured timezone"""
        return self.config.get("TIMEZONE", "Asia/Shanghai")

    @property
    def rank_threshold(self) -> int:
        """Get rank threshold"""
        return self.config.get("RANK_THRESHOLD", 50)

    @property
    def weight_config(self) -> Dict:
        """Get weight configuration"""
        return self.config.get("WEIGHT_CONFIG", {})

    @property
    def platforms(self) -> List[Dict]:
        """Get platform configuration list"""
        return self.config.get("PLATFORMS", [])

    @property
    def platform_ids(self) -> List[str]:
        """Get platform ID list"""
        return [p["id"] for p in self.platforms]

    # === Time Operations ===

    def get_time(self) -> datetime:
        """Get current time in configured timezone"""
        return get_configured_time(self.timezone)

    def format_date(self) -> str:
        """Format date folder (YYYY-MM-DD)"""
        return format_date_folder(timezone=self.timezone)

    def format_time(self) -> str:
        """Format time filename (HH-MM)"""
        return format_time_filename(self.timezone)

    def get_time_display(self) -> str:
        """Get time display (HH:MM)"""
        return get_current_time_display(self.timezone)

    @staticmethod
    def convert_time_display(time_str: str) -> str:
        """Convert HH-MM to HH:MM"""
        return convert_time_for_display(time_str)

    # === Storage Operations ===

    def get_storage_manager(self):
        """Get storage manager (lazy initialization, singleton)"""
        if self._storage_manager is None:
            storage_config = self.config.get("STORAGE", {})
            remote_config = storage_config.get("REMOTE", {})
            local_config = storage_config.get("LOCAL", {})
            pull_config = storage_config.get("PULL", {})

            self._storage_manager = get_storage_manager(
                backend_type=storage_config.get("BACKEND", "auto"),
                data_dir=local_config.get("DATA_DIR", "output"),
                enable_txt=storage_config.get("FORMATS", {}).get("TXT", True),
                enable_html=storage_config.get("FORMATS", {}).get("HTML", True),
                remote_config={
                    "bucket_name": remote_config.get("BUCKET_NAME", ""),
                    "access_key_id": remote_config.get("ACCESS_KEY_ID", ""),
                    "secret_access_key": remote_config.get("SECRET_ACCESS_KEY", ""),
                    "endpoint_url": remote_config.get("ENDPOINT_URL", ""),
                    "region": remote_config.get("REGION", ""),
                },
                local_retention_days=local_config.get("RETENTION_DAYS", 0),
                remote_retention_days=remote_config.get("RETENTION_DAYS", 0),
                pull_enabled=pull_config.get("ENABLED", False),
                pull_days=pull_config.get("DAYS", 7),
                timezone=self.timezone,
            )
        return self._storage_manager

    def get_output_path(self, subfolder: str, filename: str) -> str:
        """Get output path"""
        output_dir = Path("output") / self.format_date() / subfolder
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir / filename)

    # === Data Processing ===

    def save_titles(self, results: Dict, id_to_name: Dict, failed_ids: List) -> str:
        """Save titles to file"""
        output_path = self.get_output_path("txt", f"{self.format_time()}.txt")
        return save_titles_to_file(results, id_to_name, failed_ids, output_path, clean_title)

    def read_today_titles(
        self, platform_ids: Optional[List[str]] = None, quiet: bool = False
    ) -> Tuple[Dict, Dict, Dict]:
        """Read all titles for today"""
        return read_all_today_titles(self.get_storage_manager(), platform_ids, quiet=quiet)

    def detect_new_titles(
        self, platform_ids: Optional[List[str]] = None, quiet: bool = False
    ) -> Dict:
        """Detect new titles in the latest batch"""
        return detect_latest_new_titles(self.get_storage_manager(), platform_ids, quiet=quiet)

    def is_first_crawl(self) -> bool:
        """Check if it's the first crawl of the day"""
        return self.get_storage_manager().is_first_crawl_today()

    # === Frequency Word Processing ===

    def load_frequency_words(
        self, frequency_file: Optional[str] = None
    ) -> Tuple[List[Dict], List[str], List[str]]:
        """Load frequency word configuration"""
        return load_frequency_words(frequency_file)

    def matches_word_groups(
        self,
        title: str,
        word_groups: List[Dict],
        filter_words: List[str],
        global_filters: Optional[List[str]] = None,
    ) -> bool:
        """Check if title matches word group rules"""
        return matches_word_groups(title, word_groups, filter_words, global_filters)

    # === Statistics Analysis ===

    def count_frequency(
        self,
        results: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        title_info: Optional[Dict] = None,
        new_titles: Optional[Dict] = None,
        mode: str = "daily",
        global_filters: Optional[List[str]] = None,
        quiet: bool = False,
    ) -> Tuple[List[Dict], int]:
        """Count word frequency"""
        return count_word_frequency(
            results=results,
            word_groups=word_groups,
            filter_words=filter_words,
            id_to_name=id_to_name,
            title_info=title_info,
            rank_threshold=self.rank_threshold,
            new_titles=new_titles,
            mode=mode,
            global_filters=global_filters,
            weight_config=self.weight_config,
            max_news_per_keyword=self.config.get("MAX_NEWS_PER_KEYWORD", 0),
            sort_by_position_first=self.config.get("SORT_BY_POSITION_FIRST", False),
            is_first_crawl_func=self.is_first_crawl,
            convert_time_func=self.convert_time_display,
            quiet=quiet,
        )

    def group_by_categories(self, news_data: Any) -> List[Dict]:
        """Group news items by their categories for reporting"""
        return group_by_categories(
            news_data=news_data,
            weight_config=self.weight_config,
            rank_threshold=self.rank_threshold,
            convert_time_func=self.convert_time_display,
        )

    # === Report Generation ===

    def prepare_report(
        self,
        stats: List[Dict],
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        mode: str = "daily",
    ) -> Dict:
        """Prepare report data"""
        return prepare_report_data(
            stats=stats,
            failed_ids=failed_ids,
            new_titles=new_titles,
            id_to_name=id_to_name,
            mode=mode,
            rank_threshold=self.rank_threshold,
            matches_word_groups_func=self.matches_word_groups,
            load_frequency_words_func=self.load_frequency_words,
        )

    def generate_html(
        self,
        stats: List[Dict],
        total_titles: int,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        mode: str = "daily",
        is_daily_summary: bool = False,
        update_info: Optional[Dict] = None,
    ) -> str:
        """Generate HTML report"""
        return generate_html_report(
            stats=stats,
            total_titles=total_titles,
            failed_ids=failed_ids,
            new_titles=new_titles,
            id_to_name=id_to_name,
            mode=mode,
            is_daily_summary=is_daily_summary,
            update_info=update_info,
            rank_threshold=self.rank_threshold,
            output_dir="output",
            date_folder=self.format_date(),
            time_filename=self.format_time(),
            render_html_func=lambda *args, **kwargs: self.render_html(*args, **kwargs),
            matches_word_groups_func=self.matches_word_groups,
            load_frequency_words_func=self.load_frequency_words,
            enable_index_copy=True,
        )

    def render_html(
        self,
        report_data: Dict,
        total_titles: int,
        is_daily_summary: bool = False,
        mode: str = "daily",
        update_info: Optional[Dict] = None,
    ) -> str:
        """Render HTML content"""
        return render_html_content(
            report_data=report_data,
            total_titles=total_titles,
            is_daily_summary=is_daily_summary,
            mode=mode,
            update_info=update_info,
            reverse_content_order=self.config.get("REVERSE_CONTENT_ORDER", False),
            get_time_func=self.get_time,
        )

    # === Notification Rendering ===

    def render_feishu(
        self,
        report_data: Dict,
        update_info: Optional[Dict] = None,
        mode: str = "daily",
    ) -> str:
        """Render Feishu content"""
        return render_feishu_content(
            report_data=report_data,
            update_info=update_info,
            mode=mode,
            separator=self.config.get("FEISHU_MESSAGE_SEPARATOR", "---"),
            reverse_content_order=self.config.get("REVERSE_CONTENT_ORDER", False),
            get_time_func=self.get_time,
        )

    def render_dingtalk(
        self,
        report_data: Dict,
        update_info: Optional[Dict] = None,
        mode: str = "daily",
    ) -> str:
        """Render DingTalk content"""
        return render_dingtalk_content(
            report_data=report_data,
            update_info=update_info,
            mode=mode,
            reverse_content_order=self.config.get("REVERSE_CONTENT_ORDER", False),
            get_time_func=self.get_time,
        )

    def split_content(
        self,
        report_data: Dict,
        format_type: str,
        update_info: Optional[Dict] = None,
        max_bytes: Optional[int] = None,
        mode: str = "daily",
    ) -> List[str]:
        """Split message content into batches"""
        return split_content_into_batches(
            report_data=report_data,
            format_type=format_type,
            update_info=update_info,
            max_bytes=max_bytes,
            mode=mode,
            batch_sizes={
                "dingtalk": self.config.get("DINGTALK_BATCH_SIZE", 20000),
                "feishu": self.config.get("FEISHU_BATCH_SIZE", 29000),
                "default": self.config.get("MESSAGE_BATCH_SIZE", 4000),
            },
            feishu_separator=self.config.get("FEISHU_MESSAGE_SEPARATOR", "---"),
            reverse_content_order=self.config.get("REVERSE_CONTENT_ORDER", False),
            get_time_func=self.get_time,
        )

    # === Send Notifications ===

    def create_notification_dispatcher(self) -> NotificationDispatcher:
        """Create notification dispatcher"""
        return NotificationDispatcher(
            config=self.config,
            get_time_func=self.get_time,
            split_content_func=self.split_content,
        )

    def create_push_manager(self) -> PushRecordManager:
        """Create push record manager"""
        return PushRecordManager(
            storage_backend=self.get_storage_manager(),
            get_time_func=self.get_time,
        )

    # === Resource Cleanup ===

    def cleanup(self):
        """Clean up resources"""
        if self._storage_manager:
            self._storage_manager.cleanup_old_data()
            self._storage_manager.cleanup()
            self._storage_manager = None
