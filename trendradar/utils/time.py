# coding=utf-8
"""
Time Utility Module - Unified time processing functions
"""

from datetime import datetime
from typing import Optional

import pytz

# Default timezone
DEFAULT_TIMEZONE = "Asia/Shanghai"


def get_configured_time(timezone: str = DEFAULT_TIMEZONE) -> datetime:
    """
    Get current time for the configured timezone

    Args:
        timezone: Timezone name, e.g., 'Asia/Shanghai', 'America/New_York'

    Returns:
        Current time with timezone information
    """
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        print(f"[Warning] Unknown timezone '{timezone}', using default {DEFAULT_TIMEZONE}")
        tz = pytz.timezone(DEFAULT_TIMEZONE)
    return datetime.now(tz)


def format_date_folder(
    date: Optional[str] = None, timezone: str = DEFAULT_TIMEZONE
) -> str:
    """
    Format date folder name (ISO format: YYYY-MM-DD)

    Args:
        date: Specific date string, uses current date if None
        timezone: Timezone name

    Returns:
        Formatted date string, e.g., '2025-12-09'
    """
    if date:
        return date
    return get_configured_time(timezone).strftime("%Y-%m-%d")


def format_time_filename(timezone: str = DEFAULT_TIMEZONE) -> str:
    """
    Format time filename (格式: HH-MM, used for filenames)

    Windows systems do not support colon in filenames, so hyphen is used

    Args:
        timezone: Timezone name

    Returns:
        Formatted time string, e.g., '15-30'
    """
    return get_configured_time(timezone).strftime("%H-%M")


def get_current_time_display(timezone: str = DEFAULT_TIMEZONE) -> str:
    """
    Get current time display (Format: HH:MM, used for display)

    Args:
        timezone: Timezone name

    Returns:
        Formatted time string, e.g., '15:30'
    """
    return get_configured_time(timezone).strftime("%H:%M")


def convert_time_for_display(time_str: str) -> str:
    """
    Convert HH-MM format to HH:MM format for display

    Args:
        time_str: Input time string, e.g., '15-30'

    Returns:
        Converted time string, e.g., '15:30'
    """
    if time_str and "-" in time_str and len(time_str) == 5:
        return time_str.replace("-", ":")
    return time_str
