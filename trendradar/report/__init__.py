# coding=utf-8
"""
Report Generation Module

Provides report generation and formatting functionality, including:
- HTML report generation
- Title formatting utilities

Module Structure:
- helpers: Report helper functions (cleaning, escaping, formatting)
- formatter: Platform title formatting
- html: HTML report rendering
- generator: Report generator
"""

from trendradar.report.helpers import (
    clean_title,
    html_escape,
    format_rank_display,
)
from trendradar.report.formatter import format_title_for_platform
from trendradar.report.html import render_html_content
from trendradar.report.generator import (
    prepare_report_data,
    generate_html_report,
)

__all__ = [
    # Helper functions
    "clean_title",
    "html_escape",
    "format_rank_display",
    # Formatter functions
    "format_title_for_platform",
    # HTML Rendering
    "render_html_content",
    # Report Generator
    "prepare_report_data",
    "generate_html_report",
]
