# coding=utf-8
"""
Storage Module - Supports Multiple Storage Backends

Supported storage backends:
- local: Local SQLite + TXT/HTML files
- remote: Remote Cloud Storage (S3 compatible protocol: R2/OSS/COS/S3 etc.)
- auto: Automatically selected based on environment (remote for GitHub Actions, local otherwise)
"""

from trendradar.storage.base import (
    StorageBackend,
    NewsItem,
    NewsData,
    convert_crawl_results_to_news_data,
    convert_news_data_to_results,
)
from trendradar.storage.local import LocalStorageBackend
from trendradar.storage.manager import StorageManager, get_storage_manager

# Remote backend optional import (requires boto3)
try:
    from trendradar.storage.remote import RemoteStorageBackend
    HAS_REMOTE = True
except ImportError:
    RemoteStorageBackend = None
    HAS_REMOTE = False

__all__ = [
    # Base Classes
    "StorageBackend",
    "NewsItem",
    "NewsData",
    # Conversion Functions
    "convert_crawl_results_to_news_data",
    "convert_news_data_to_results",
    # Backend Implementations
    "LocalStorageBackend",
    "RemoteStorageBackend",
    "HAS_REMOTE",
    # Managers
    "StorageManager",
    "get_storage_manager",
]
