# coding=utf-8
"""
Storage Manager - Unified Management of Storage Backends

Automatically selects the appropriate storage backend based on environment and configuration
"""

import os
from typing import Optional, List, Dict

from trendradar.storage.base import StorageBackend, NewsData


# Storage Manager Singleton
_storage_manager: Optional["StorageManager"] = None


class StorageManager:
    """
    Storage Manager

    Features:
    - Auto-detect running environment (GitHub Actions / Docker / Local)
    - Select storage backend based on config (local / remote / auto)
    - Provide unified storage interface
    - Support pulling data from remote to local
    """

    def __init__(
        self,
        backend_type: str = "auto",
        data_dir: str = "output",
        enable_txt: bool = True,
        enable_html: bool = True,
        remote_config: Optional[dict] = None,
        local_retention_days: int = 0,
        remote_retention_days: int = 0,
        pull_enabled: bool = False,
        pull_days: int = 0,
        timezone: str = "Asia/Shanghai",
    ):
        """
        Initialize Storage Manager

        Args:
            backend_type: Storage backend type (local / remote / auto)
            data_dir: Local data directory
            enable_txt: Whether to enable TXT snapshot
            enable_html: Whether to enable HTML report
            remote_config: Remote storage config (endpoint_url, bucket_name, access_key_id etc.)
            local_retention_days: Local data retention days (0 = unlimited)
            remote_retention_days: Remote data retention days (0 = unlimited)
            pull_enabled: Whether to enable auto pull on startup
            pull_days: Pull last N days of data
            timezone: Timezone config (default Asia/Shanghai)
        """
        self.backend_type = backend_type
        self.data_dir = data_dir
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.remote_config = remote_config or {}
        self.local_retention_days = local_retention_days
        self.remote_retention_days = remote_retention_days
        self.pull_enabled = pull_enabled
        self.pull_days = pull_days
        self.timezone = timezone

        self._backend: Optional[StorageBackend] = None
        self._remote_backend: Optional[StorageBackend] = None

    @staticmethod
    def is_github_actions() -> bool:
        """Check if running in GitHub Actions environment"""
        return os.environ.get("GITHUB_ACTIONS") == "true"

    @staticmethod
    def is_docker() -> bool:
        """Check if running in Docker container"""
        # Method 1: Check /.dockerenv file
        if os.path.exists("/.dockerenv"):
            return True

        # Method 2: Check cgroup (Linux)
        try:
            with open("/proc/1/cgroup", "r") as f:
                return "docker" in f.read()
        except (FileNotFoundError, PermissionError):
            pass

        # Method 3: Check environment variable
        return os.environ.get("DOCKER_CONTAINER") == "true"

    def _resolve_backend_type(self) -> str:
        """Resolve actual backend type to use"""
        if self.backend_type == "auto":
            if self.is_github_actions():
                # GitHub Actions environment, check if remote storage is configured
                if self._has_remote_config():
                    return "remote"
                else:
                    print("[StorageManager] GitHub Actions environment but remote storage not configured, using local storage")
                    return "local"
            else:
                return "local"
        return self.backend_type

    def _has_remote_config(self) -> bool:
        """Check if there is valid remote storage configuration"""
        # Check config or environment variables
        bucket_name = self.remote_config.get("bucket_name") or os.environ.get("S3_BUCKET_NAME")
        access_key = self.remote_config.get("access_key_id") or os.environ.get("S3_ACCESS_KEY_ID")
        secret_key = self.remote_config.get("secret_access_key") or os.environ.get("S3_SECRET_ACCESS_KEY")
        endpoint = self.remote_config.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL")

        # Debug logs
        has_config = bool(bucket_name and access_key and secret_key and endpoint)
        if not has_config:
            print(f"[StorageManager] Remote storage config check failed:")
            print(f"  - bucket_name: {'Configured' if bucket_name else 'Not configured'}")
            print(f"  - access_key_id: {'Configured' if access_key else 'Not configured'}")
            print(f"  - secret_access_key: {'Configured' if secret_key else 'Not configured'}")
            print(f"  - endpoint_url: {'Configured' if endpoint else 'Not configured'}")

        return has_config

    def _create_remote_backend(self) -> Optional[StorageBackend]:
        """Create remote storage backend"""
        try:
            from trendradar.storage.remote import RemoteStorageBackend

            return RemoteStorageBackend(
                bucket_name=self.remote_config.get("bucket_name") or os.environ.get("S3_BUCKET_NAME", ""),
                access_key_id=self.remote_config.get("access_key_id") or os.environ.get("S3_ACCESS_KEY_ID", ""),
                secret_access_key=self.remote_config.get("secret_access_key") or os.environ.get("S3_SECRET_ACCESS_KEY", ""),
                endpoint_url=self.remote_config.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL", ""),
                region=self.remote_config.get("region") or os.environ.get("S3_REGION", ""),
                enable_txt=self.enable_txt,
                enable_html=self.enable_html,
                timezone=self.timezone,
            )
        except ImportError as e:
            print(f"[StorageManager] Failed to import remote backend: {e}")
            print("[StorageManager] Please ensure boto3 is installed: pip install boto3")
            return None
        except Exception as e:
            print(f"[StorageManager] Failed to initialize remote backend: {e}")
            return None

    def get_backend(self) -> StorageBackend:
        """Get storage backend instance"""
        if self._backend is None:
            resolved_type = self._resolve_backend_type()

            if resolved_type == "remote":
                self._backend = self._create_remote_backend()
                if self._backend:
                    print(f"[StorageManager] Using REMOTE storage backend")
                else:
                    print("[StorageManager] Fallback to LOCAL storage")
                    resolved_type = "local"

            if resolved_type == "local" or self._backend is None:
                from trendradar.storage.local import LocalStorageBackend

                self._backend = LocalStorageBackend(
                    data_dir=self.data_dir,
                    enable_txt=self.enable_txt,
                    enable_html=self.enable_html,
                    timezone=self.timezone,
                )
                print(f"[StorageManager] Using LOCAL storage backend (Data Dir: {self.data_dir})")

        return self._backend

    def pull_from_remote(self) -> int:
        """
        Pull data from remote to local

        Returns:
            Number of successfully pulled files
        """
        if not self.pull_enabled or self.pull_days <= 0:
            return 0

        if not self._has_remote_config():
            print("[StorageManager] Remote storage not configured, cannot pull")
            return 0

        # Create remote backend (if not exists)
        if self._remote_backend is None:
            self._remote_backend = self._create_remote_backend()

        if self._remote_backend is None:
            print("[StorageManager] Failed to create remote backend, pull failed")
            return 0

        # Call pull method
        return self._remote_backend.pull_recent_days(self.pull_days, self.data_dir)

    def save_news_data(self, data: NewsData) -> bool:
        """Save news data"""
        return self.get_backend().save_news_data(data)

    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Get all data for today"""
        return self.get_backend().get_today_all_data(date)

    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Get latest crawl data"""
        return self.get_backend().get_latest_crawl_data(date)

    def detect_new_titles(self, current_data: NewsData) -> dict:
        """Detect new titles"""
        return self.get_backend().detect_new_titles(current_data)

    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """Save TXT snapshot"""
        return self.get_backend().save_txt_snapshot(data)

    def save_html_report(self, html_content: str, filename: str, is_summary: bool = False) -> Optional[str]:
        """Save HTML report"""
        return self.get_backend().save_html_report(html_content, filename, is_summary)

    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """Check if it's the first crawl of the day"""
        return self.get_backend().is_first_crawl_today(date)

    def cleanup(self) -> None:
        """Clean up resources"""
        if self._backend:
            self._backend.cleanup()
        if self._remote_backend:
            self._remote_backend.cleanup()

    def cleanup_old_data(self) -> int:
        """
        Clean up old data

        Returns:
            Number of deleted date directories
        """
        total_deleted = 0

        # Clean local data
        if self.local_retention_days > 0:
            total_deleted += self.get_backend().cleanup_old_data(self.local_retention_days)

        # Clean remote data (if configured)
        if self.remote_retention_days > 0 and self._has_remote_config():
            if self._remote_backend is None:
                self._remote_backend = self._create_remote_backend()
            if self._remote_backend:
                total_deleted += self._remote_backend.cleanup_old_data(self.remote_retention_days)

        return total_deleted

    @property
    def backend_name(self) -> str:
        """Get current backend name"""
        return self.get_backend().backend_name

    @property
    def supports_txt(self) -> bool:
        """Whether TXT snapshot is supported"""
        return self.get_backend().supports_txt

    # === Push Record Related Methods ===

    def has_pushed_today(self, date: Optional[str] = None) -> bool:
        """
        Check if pushed today

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Whether pushed
        """
        return self.get_backend().has_pushed_today(date)

    def record_push(self, report_type: str, date: Optional[str] = None) -> bool:
        """
        Record push

        Args:
            report_type: Report type
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Whether recording was successful
        """
        return self.get_backend().record_push(report_type, date)

    # === Opinion & Sentiment Related Methods ===

    def save_opinions(self, opinions: List[dict], date: Optional[str] = None) -> List[int]:
        """Save public opinions/reactions"""
        return self.get_backend().save_opinions(opinions, date)

    def link_opinion_to_news(self, news_item_id: int, opinion_id: int, match_type: str = 'keyword', match_score: float = 1.0, date: Optional[str] = None) -> bool:
        """Link an opinion to a news item"""
        return self.get_backend().link_opinion_to_news(news_item_id, opinion_id, match_type, match_score, date)

    def save_sentiment_summary(self, summary_data: dict, date: Optional[str] = None) -> bool:
        """Save a sentiment summary for a news item"""
        return self.get_backend().save_sentiment_summary(summary_data, date)

    def save_hourly_summary(self, summary_data: dict, date: Optional[str] = None) -> bool:
        """Save an hourly summary"""
        return self.get_backend().save_hourly_summary(summary_data, date)

    def get_latest_summary(self, date: Optional[str] = None) -> Optional[Dict]:
        """Get the latest hourly summary"""
        return self.get_backend().get_latest_summary(date)

    def get_news_with_opinions(self, news_item_id: int, date: Optional[str] = None) -> dict:
        """Get a specific news item with its linked opinions and sentiment summary"""
        return self.get_backend().get_news_with_opinions(news_item_id, date)


def get_storage_manager(
    backend_type: str = "auto",
    data_dir: str = "output",
    enable_txt: bool = True,
    enable_html: bool = True,
    remote_config: Optional[dict] = None,
    local_retention_days: int = 0,
    remote_retention_days: int = 0,
    pull_enabled: bool = False,
    pull_days: int = 0,
    timezone: str = "Asia/Shanghai",
    force_new: bool = False,
) -> StorageManager:
    """
    Get Storage Manager Singleton

    Args:
        backend_type: Storage backend type
        data_dir: Local data directory
        enable_txt: Whether to enable TXT snapshot
        enable_html: Whether to enable HTML report
        remote_config: Remote storage config
        local_retention_days: Local data retention days (0 = unlimited)
        remote_retention_days: Remote data retention days (0 = unlimited)
        pull_enabled: Whether to enable auto pull on startup
        pull_days: Pull last N days of data
        timezone: Timezone config (default Asia/Shanghai)
        force_new: Whether to force create new instance

    Returns:
        StorageManager instance
    """
    global _storage_manager

    if _storage_manager is None or force_new:
        _storage_manager = StorageManager(
            backend_type=backend_type,
            data_dir=data_dir,
            enable_txt=enable_txt,
            enable_html=enable_html,
            remote_config=remote_config,
            local_retention_days=local_retention_days,
            remote_retention_days=remote_retention_days,
            pull_enabled=pull_enabled,
            pull_days=pull_days,
            timezone=timezone,
        )

    return _storage_manager
