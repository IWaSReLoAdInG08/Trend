# coding=utf-8
"""
Core Module - Configuration Management and Core Utilities
"""

from trendradar.core.config import (
    parse_multi_account_config,
    validate_paired_configs,
    limit_accounts,
    get_account_at_index,
)
from trendradar.core.loader import load_config
from trendradar.core.frequency import load_frequency_words, matches_word_groups
from trendradar.core.data import (
    save_titles_to_file,
    read_all_today_titles_from_storage,
    read_all_today_titles,
    detect_latest_new_titles_from_storage,
    detect_latest_new_titles,
    is_first_crawl_today,
)
from trendradar.core.analyzer import (
    calculate_news_weight,
    format_time_display,
    count_word_frequency,
    group_by_categories,
)

__all__ = [
    "parse_multi_account_config",
    "validate_paired_configs",
    "limit_accounts",
    "get_account_at_index",
    "load_config",
    "load_frequency_words",
    "matches_word_groups",
    # Data Processing
    "save_titles_to_file",
    "read_all_today_titles_from_storage",
    "read_all_today_titles",
    "detect_latest_new_titles_from_storage",
    "detect_latest_new_titles",
    "is_first_crawl_today",
    # Statistics Analysis
    "calculate_news_weight",
    "format_time_display",
    "count_word_frequency",
    "group_by_categories",
]
