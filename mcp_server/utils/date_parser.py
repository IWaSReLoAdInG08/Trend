"""
Date Parsing Tool

Supports parsing multiple natural language date formats, including relative and absolute dates.
English-only implementation to ensure ASCII safety.
"""

import re
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional

from .errors import InvalidParameterError


class DateParser:
    """Date Parser Class"""

    # English date mapping
    EN_DATE_MAPPING = {
        "today": 0,
        "yesterday": 1,
    }

    # Date range expressions (for resolve_date_range_expression)
    RANGE_EXPRESSIONS = {
        "today": "today",
        "yesterday": "yesterday",
        "this week": "this_week",
        "current week": "this_week",
        "last week": "last_week",
        "this month": "this_month",
        "current month": "this_month",
        "last month": "last_month",
        "last 3 days": "last_3_days",
        "past 3 days": "last_3_days",
        "last 7 days": "last_7_days",
        "past 7 days": "last_7_days",
        "past week": "last_7_days",
        "last 14 days": "last_14_days",
        "past 14 days": "last_14_days",
        "last 30 days": "last_30_days",
        "past 30 days": "last_30_days",
        "past month": "last_30_days",
    }

    # Weekday mapping
    WEEKDAY_EN = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }

    @staticmethod
    def parse_date_query(date_query: str) -> datetime:
        """
        Parse date query string

        Supported formats:
        - Relative date: today, yesterday, N days ago
        - Week: last monday, this friday
        - Absolute: 2025-10-10, 2025/11/11
        """
        if not date_query or not isinstance(date_query, str):
            raise InvalidParameterError(
                "Date query string cannot be empty",
                suggestion="Please provide a valid date query, e.g., today, yesterday, 2025-10-10"
            )

        date_query = date_query.strip().lower()

        # 1. English relative date mapping
        if date_query in DateParser.EN_DATE_MAPPING:
            days_ago = DateParser.EN_DATE_MAPPING[date_query]
            return datetime.now() - timedelta(days=days_ago)

        # 2. Match "N days ago"
        en_days_ago_match = re.match(r'(\d+)\s*days?\s+ago', date_query)
        if en_days_ago_match:
            days = int(en_days_ago_match.group(1))
            if days > 365:
                raise InvalidParameterError(
                    f"Days too large: {days} days",
                    suggestion="Please use a relative date less than 365 days or use an absolute date"
                )
            return datetime.now() - timedelta(days=days)

        # 3. Match weekday (English): last monday, this friday
        en_weekday_match = re.match(r'(last|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', date_query)
        if en_weekday_match:
            week_type = en_weekday_match.group(1)
            weekday_str = en_weekday_match.group(2)
            target_weekday = DateParser.WEEKDAY_EN[weekday_str]
            return DateParser._get_date_by_weekday(target_weekday, week_type == "last")

        # 4. Match absolute date: YYYY-MM-DD
        iso_date_match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_query)
        if iso_date_match:
            try:
                return datetime(int(iso_date_match.group(1)), int(iso_date_match.group(2)), int(iso_date_match.group(3)))
            except ValueError as e:
                raise InvalidParameterError(f"Invalid date: {date_query}", suggestion=str(e))

        # 5. Match slash format: YYYY/MM/DD or MM/DD
        slash_date_match = re.match(r'(?:(\d{4})/)?(\d{1,2})/(\d{1,2})', date_query)
        if slash_date_match:
            year_str = slash_date_match.group(1)
            month = int(slash_date_match.group(2))
            day = int(slash_date_match.group(3))
            year = int(year_str) if year_str else datetime.now().year
            if not year_str and month > datetime.now().month:
                year -= 1
            try:
                return datetime(year, month, day)
            except ValueError as e:
                raise InvalidParameterError(f"Invalid date: {date_query}", suggestion=str(e))

        # If no format matches
        raise InvalidParameterError(
            f"Unrecognized date format: {date_query}",
            suggestion="Supported formats: today, yesterday, N days ago, last monday, this friday, YYYY-MM-DD"
        )

    @staticmethod
    def _get_date_by_weekday(target_weekday: int, is_last_week: bool) -> datetime:
        """Get date by weekday"""
        today = datetime.now()
        current_weekday = today.weekday()
        if is_last_week:
            diff = current_weekday + 7 - target_weekday
        else:
            diff = current_weekday - target_weekday
        return today - timedelta(days=diff)

    @staticmethod
    def format_date_folder(date: datetime) -> str:
        """Format date to folder name YYYY-MM-DD"""
        return date.strftime("%Y-%m-%d")

    @staticmethod
    def validate_date_not_future(date: datetime) -> None:
        """Validate date is not in the future"""
        if date.date() > datetime.now().date():
            raise InvalidParameterError(f"Date cannot be in the future: {date.strftime('%Y-%m-%d')}")

    @staticmethod
    def validate_date_not_too_old(date: datetime, max_days: int = 365) -> None:
        """Validate date is not too old"""
        days_ago = (datetime.now().date() - date.date()).days
        if days_ago > max_days:
            raise InvalidParameterError(f"Date is too old (max {max_days} days): {date.strftime('%Y-%m-%d')}")

    @staticmethod
    def resolve_date_range_expression(expression: str) -> Dict:
        """Resolve natural language date expressions to standard date ranges"""
        if not expression or not isinstance(expression, str):
            raise InvalidParameterError("Date expression cannot be empty")

        expression_lower = expression.strip().lower()
        today = datetime.now()

        # 1. Try predefined expressions
        normalized = DateParser.RANGE_EXPRESSIONS.get(expression_lower)

        # 2. Try dynamic pattern
        if not normalized:
            en_match = re.match(r'(?:last|past)\s+(\d+)\s+days?', expression_lower)
            if en_match:
                days = int(en_match.group(1))
                normalized = f"last_{days}_days"

        if not normalized:
            raise InvalidParameterError(
                f"Unrecognized date expression: {expression}",
                suggestion="Supported: today, yesterday, this week, last week, this month, last month, last N days"
            )

        start_date, end_date, description = DateParser._calculate_date_range(normalized, today)

        return {
            "success": True,
            "expression": expression,
            "normalized": normalized,
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "current_date": today.strftime("%Y-%m-%d"),
            "description": description
        }

    @staticmethod
    def _calculate_date_range(normalized: str, today: datetime) -> Tuple[datetime, datetime, str]:
        """Calculate date range"""
        if normalized == "today":
            return today, today, "today"
        if normalized == "yesterday":
            yest = today - timedelta(days=1)
            return yest, yest, "yesterday"
        if normalized == "this_week":
            start = today - timedelta(days=today.weekday())
            end = today
            return start, end, f"this week ({start.strftime('%m-%d')} to {end.strftime('%m-%d')})"
        if normalized == "last_week":
            this_mon = today - timedelta(days=today.weekday())
            start = this_mon - timedelta(days=7)
            end = start + timedelta(days=6)
            return start, end, f"last week ({start.strftime('%m-%d')} to {end.strftime('%m-%d')})"
        if normalized == "this_month":
            start = today.replace(day=1)
            return start, today, f"this month ({start.strftime('%m-%d')} to {today.strftime('%m-%d')})"
        if normalized == "last_month":
            first_this = today.replace(day=1)
            end = first_this - timedelta(days=1)
            start = end.replace(day=1)
            return start, end, f"last month ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})"

        match = re.match(r'last_(\d+)_days', normalized)
        if match:
            days = int(match.group(1))
            start = today - timedelta(days=days - 1)
            return start, today, f"last {days} days ({start.strftime('%m-%d')} to {today.strftime('%m-%d')})"

        return today, today, "today (default)"

    @staticmethod
    def get_supported_expressions() -> Dict[str, list]:
        """Get supported expressions"""
        return {
            "Day": ["today", "yesterday"],
            "Week": ["this week", "last week"],
            "Month": ["this month", "last month"],
            "Last N days": ["last 7 days", "last 30 days"]
        }
