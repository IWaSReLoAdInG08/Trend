"""
Data Query Tools

Implements P0 core data query tools in English.
"""

from typing import Dict, List, Optional

from ..services.data_service import DataService
from ..utils.validators import (
    validate_platforms,
    validate_limit,
    validate_keyword,
    validate_date_range,
    validate_top_n,
    validate_mode,
    validate_date_query
)
from ..utils.errors import MCPError


class DataQueryTools:
    """Data Query Tools Class"""

    def __init__(self, project_root: str = None):
        """
        Initialize data query tools

        Args:
            project_root: Project root directory
        """
        self.data_service = DataService(project_root)

    def get_latest_news(
        self,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_url: bool = False
    ) -> Dict:
        """
        Get the latest batch of crawled news data

        Args:
            platforms: List of platform IDs
            limit: Return count limit, default 50
            include_url: Whether to include URL links, default False

        Returns:
            News list dictionary
        """
        try:
            # Type validation
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)

            # Fetch data
            news_list = self.data_service.get_latest_news(
                platforms=platforms,
                limit=limit,
                include_url=include_url
            )

            return {
                "news": news_list,
                "total": len(news_list),
                "platforms": platforms,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def search_news_by_keyword(
        self,
        keyword: str,
        date_range: Optional[Dict] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Search historical news by keyword

        Args:
            keyword: Search keyword (required)
            date_range: Date range, format: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            platforms: List of platform filters
            limit: Return count limit (optional)

        Returns:
            Search results dictionary
        """
        try:
            # Parameter validation
            keyword = validate_keyword(keyword)
            date_range_tuple = validate_date_range(date_range)
            platforms = validate_platforms(platforms)

            if limit is not None:
                limit = validate_limit(limit, default=100)

            # Search data
            search_result = self.data_service.search_news_by_keyword(
                keyword=keyword,
                date_range=date_range_tuple,
                platforms=platforms,
                limit=limit
            )

            return {
                **search_result,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def get_trending_topics(
        self,
        top_n: Optional[int] = None,
        mode: Optional[str] = None
    ) -> Dict:
        """
        Get frequency statistics of news for personal followed words

        Note: This tool counts the frequency of words in config/frequency_words.txt,
        not automatically extracted topics.

        Args:
            top_n: Return top N followed words, default 10
            mode: Mode - daily, current, incremental

        Returns:
            Topic frequency statistics dictionary
        """
        try:
            # Param validation
            top_n = validate_top_n(top_n, default=10)
            valid_modes = ["daily", "current", "incremental"]
            mode = validate_mode(mode, valid_modes, default="current")

            # Get trending topics
            trending_result = self.data_service.get_trending_topics(
                top_n=top_n,
                mode=mode
            )

            return {
                **trending_result,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def get_news_by_date(
        self,
        date_query: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_url: bool = False
    ) -> Dict:
        """
        Query news by date, supports natural language

        Args:
            date_query: Date query string (optional, default "today")
            platforms: List of platform IDs
            limit: Return count limit, default 50
            include_url: Whether to include URL links, default False

        Returns:
            News list dictionary
        """
        try:
            # Param validation - default today
            if date_query is None:
                date_query = "today"
            target_date = validate_date_query(date_query)
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)

            # Fetch data
            news_list = self.data_service.get_news_by_date(
                target_date=target_date,
                platforms=platforms,
                limit=limit,
                include_url=include_url
            )

            return {
                "news": news_list,
                "total": len(news_list),
                "date": target_date.strftime("%Y-%m-%d"),
                "date_query": date_query,
                "platforms": platforms,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }
