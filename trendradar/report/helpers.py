# coding=utf-8
"""
Report Helpers Module

Provides common helper functions related to report generation
"""

import re
from typing import List


def clean_title(title: str) -> str:
    """Clean special characters in title

    Cleaning rules:
    - Replace newlines (\n, \r) with spaces
    - Merge multiple continuous whitespace characters into a single space
    - Remove leading and trailing whitespace

    Args:
        title: Original title string

    Returns:
        Cleaned title string
    """
    if not isinstance(title, str):
        title = str(title)
    cleaned_title = title.replace("\n", " ").replace("\r", " ")
    cleaned_title = re.sub(r"\s+", " ", cleaned_title)
    cleaned_title = cleaned_title.strip()
    return cleaned_title


def html_escape(text: str) -> str:
    """HTML special character escaping

    Escaping rules (in order):
    - & → &amp;
    - < → &lt;
    - > → &gt;
    - " → &quot;
    - ' → &#x27;

    Args:
        text: Original text

    Returns:
        Escaped text
    """
    if not isinstance(text, str):
        text = str(text)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def format_rank_display(ranks: List[int], rank_threshold: int, format_type: str) -> str:
    """Format rank display

    Generates corresponding rank string based on different platform types.
    Highlights when the minimum rank is less than or equal to the threshold.

    Args:
        ranks: List of ranks (may contain duplicates)
        rank_threshold: Highlight threshold, ranks less than or equal to this value will be highlighted
        format_type: Platform type, supports:
            - "html": HTML format
            - "feishu": Feishu/Lark format
            - "dingtalk": DingTalk format
            - "wework": WeChat Work format
            - "telegram": Telegram format
            - "slack": Slack format
            - Others: Default markdown format

    Returns:
        Formatted rank string, e.g., "[1]" or "[1 - 5]"
        Returns empty string if rank list is empty
    """
    if not ranks:
        return ""

    unique_ranks = sorted(set(ranks))
    min_rank = unique_ranks[0]
    max_rank = unique_ranks[-1]

    # Select highlight format based on platform type
    if format_type == "html":
        highlight_start = "<font color='red'><strong>"
        highlight_end = "</strong></font>"
    elif format_type == "feishu":
        highlight_start = "<font color='red'>**"
        highlight_end = "**</font>"
    elif format_type == "dingtalk":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "wework":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "telegram":
        highlight_start = "<b>"
        highlight_end = "</b>"
    elif format_type == "slack":
        highlight_start = "*"
        highlight_end = "*"
    else:
        # Default markdown format
        highlight_start = "**"
        highlight_end = "**"

    # Generate rank display
    if min_rank <= rank_threshold:
        if min_rank == max_rank:
            return f"{highlight_start}[{min_rank}]{highlight_end}"
        else:
            return f"{highlight_start}[{min_rank} - {max_rank}]{highlight_end}"
    else:
        if min_rank == max_rank:
            return f"[{min_rank}]"
        else:
            return f"[{min_rank} - {max_rank}]"
