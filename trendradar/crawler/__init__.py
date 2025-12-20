# coding=utf-8
"""
Crawler Module

Provides data fetching functionality, supporting NewsNow API and RSS feeds
"""

from trendradar.crawler.fetcher import DataFetcher
from trendradar.crawler.rss_fetcher import RSSFetcher

__all__ = ["DataFetcher", "RSSFetcher"]
