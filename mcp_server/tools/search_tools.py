"""
Intelligent News Retrieval Tools

Provides advanced search functions like fuzzy search, link query, and historical related news retrieval.
"""

import re
from collections import Counter
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from ..services.data_service import DataService
from ..utils.validators import validate_keyword, validate_limit
from ..utils.errors import MCPError, InvalidParameterError, DataNotFoundError


class SearchTools:
    """Intelligent News Retrieval Tools Class"""

    def __init__(self, project_root: str = None):
        """
        Initialize intelligent retrieval tools

        Args:
            project_root: Project root directory
        """
        self.data_service = DataService(project_root)
        self.stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'else', 'when',
            'at', 'from', 'by', 'for', 'with', 'about', 'against', 'between',
            'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'to', 'of', 'in', 'on', 'is', 'are', 'was', 'were', 'be', 'been'
        }

    def search_news_unified(
        self,
        query: str,
        search_mode: str = "keyword",
        date_range: Optional[Dict[str, str]] = None,
        platforms: Optional[List[str]] = None,
        limit: int = 50,
        sort_by: str = "relevance",
        threshold: float = 0.6,
        include_url: bool = False
    ) -> Dict:
        """
        Unified News Search Tool

        Args:
            query: Query content (required)
            search_mode: Search mode:
                - "keyword": Exact keyword match (default)
                - "fuzzy": Fuzzy content matching
                - "entity": Entity name search
            date_range: Date range, format: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            platforms: List of platform filters
            limit: Return count limit, default 50
            sort_by: Sorting method: "relevance", "weight", "date"
            threshold: Similarity threshold (fuzzy mode only)
            include_url: Whether to include URL links, default False

        Returns:
            Search results dictionary
        """
        try:
            # Parameter validation
            query = validate_keyword(query)

            if search_mode not in ["keyword", "fuzzy", "entity"]:
                raise InvalidParameterError(
                    f"Invalid search mode: {search_mode}",
                    suggestion="Supported modes: keyword, fuzzy, entity"
                )

            if sort_by not in ["relevance", "weight", "date"]:
                raise InvalidParameterError(
                    f"Invalid sort method: {sort_by}",
                    suggestion="Supported sorting: relevance, weight, date"
                )

            limit = validate_limit(limit, default=50)
            threshold = max(0.0, min(1.0, threshold))

            # Handle date range
            if date_range:
                from ..utils.validators import validate_date_range
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                # If no date specified, use latest available data date
                earliest, latest = self.data_service.get_available_date_range()

                if latest is None:
                    # No data available
                    return {
                        "success": False,
                        "error": {
                            "code": "NO_DATA_AVAILABLE",
                            "message": "No news data available in output directory",
                            "suggestion": "Please ensure crawler has been run"
                        }
                    }

                # Use latest available date
                start_date = end_date = latest

            # Collect all matching news
            all_matches = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    all_titles, id_to_name, timestamps = self.data_service.parser.read_all_titles_for_date(
                        date=current_date,
                        platform_ids=platforms
                    )

                    # Execute different search logic based on mode
                    if search_mode == "keyword":
                        matches = self._search_by_keyword_mode(
                            query, all_titles, id_to_name, current_date, include_url
                        )
                    elif search_mode == "fuzzy":
                        matches = self._search_by_fuzzy_mode(
                            query, all_titles, id_to_name, current_date, threshold, include_url
                        )
                    else:  # entity
                        matches = self._search_by_entity_mode(
                            query, all_titles, id_to_name, current_date, include_url
                        )

                    all_matches.extend(matches)

                except DataNotFoundError:
                    # No data for this date, continue to next
                    pass

                current_date += timedelta(days=1)

            if not all_matches:
                # Get available range for hint
                earliest, latest = self.data_service.get_available_date_range()

                # Determine time range description
                if start_date.date() == datetime.now().date() and start_date == end_date:
                    time_desc = "today"
                elif start_date == end_date:
                    time_desc = start_date.strftime("%Y-%m-%d")
                else:
                    time_desc = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

                # Build error message
                if earliest and latest:
                    available_desc = f"{earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}"
                    message = f"No matching news found (Query: {time_desc}, Available: {available_desc})"
                else:
                    message = f"No matching news found ({time_desc})"

                result = {
                    "success": True,
                    "results": [],
                    "total": 0,
                    "query": query,
                    "search_mode": search_mode,
                    "time_range": time_desc,
                    "message": message
                }
                return result

            # Sorting logic
            if sort_by == "relevance":
                all_matches.sort(key=lambda x: x.get("similarity_score", 1.0), reverse=True)
            elif sort_by == "weight":
                from .analytics import calculate_news_weight
                all_matches.sort(key=lambda x: calculate_news_weight(x), reverse=True)
            elif sort_by == "date":
                all_matches.sort(key=lambda x: x.get("date", ""), reverse=True)

            # Limit results
            results = all_matches[:limit]

            # Build time range description
            if start_date.date() == datetime.now().date() and start_date == end_date:
                time_range_desc = "today"
            elif start_date == end_date:
                time_range_desc = start_date.strftime("%Y-%m-%d")
            else:
                time_range_desc = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

            result = {
                "success": True,
                "summary": {
                    "total_found": len(all_matches),
                    "returned_count": len(results),
                    "requested_limit": limit,
                    "search_mode": search_mode,
                    "query": query,
                    "platforms": platforms or "all",
                    "time_range": time_range_desc,
                    "sort_by": sort_by
                },
                "results": results
            }

            if search_mode == "fuzzy":
                result["summary"]["threshold"] = threshold
                if len(all_matches) < limit:
                    result["note"] = f"In fuzzy mode with threshold {threshold}, only {len(all_matches)} results were found"

            return result

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

    def _search_by_keyword_mode(
        self,
        query: str,
        all_titles: Dict,
        id_to_name: Dict,
        current_date: datetime,
        include_url: bool
    ) -> List[Dict]:
        """
        Keyword search mode (exact match)

        Args:
            query: Search keyword
            all_titles: All titles dictionary
            id_to_name: Platform ID to name mapping
            current_date: Current date

        Returns:
            Matched news list
        """
        matches = []
        query_lower = query.lower()

        for platform_id, titles in all_titles.items():
            platform_name = id_to_name.get(platform_id, platform_id)

            for title, info in titles.items():
                if query_lower in title.lower():
                    news_item = {
                        "title": title,
                        "platform": platform_id,
                        "platform_name": platform_name,
                        "date": current_date.strftime("%Y-%m-%d"),
                        "similarity_score": 1.0,
                        "ranks": info.get("ranks", []),
                        "count": len(info.get("ranks", [])),
                        "rank": info["ranks"][0] if info["ranks"] else 999
                    }

                    if include_url:
                        news_item["url"] = info.get("url", "")
                        news_item["mobileUrl"] = info.get("mobileUrl", "")

                    matches.append(news_item)

        return matches

    def _search_by_fuzzy_mode(
        self,
        query: str,
        all_titles: Dict,
        id_to_name: Dict,
        current_date: datetime,
        threshold: float,
        include_url: bool
    ) -> List[Dict]:
        """
        Fuzzy search mode (using similarity algorithm)

        Args:
            query: Search content
            all_titles: All titles dictionary
            id_to_name: Platform ID to name mapping
            current_date: Current date
            threshold: Similarity threshold

        Returns:
            Matched news list
        """
        matches = []

        for platform_id, titles in all_titles.items():
            platform_name = id_to_name.get(platform_id, platform_id)

            for title, info in titles.items():
                is_match, similarity = self._fuzzy_match(query, title, threshold)

                if is_match:
                    news_item = {
                        "title": title,
                        "platform": platform_id,
                        "platform_name": platform_name,
                        "date": current_date.strftime("%Y-%m-%d"),
                        "similarity_score": round(similarity, 4),
                        "ranks": info.get("ranks", []),
                        "count": len(info.get("ranks", [])),
                        "rank": info["ranks"][0] if info["ranks"] else 999
                    }

                    if include_url:
                        news_item["url"] = info.get("url", "")
                        news_item["mobileUrl"] = info.get("mobileUrl", "")

                    matches.append(news_item)

        return matches

    def _search_by_entity_mode(
        self,
        query: str,
        all_titles: Dict,
        id_to_name: Dict,
        current_date: datetime,
        include_url: bool
    ) -> List[Dict]:
        """
        Entity search mode (auto sorted by weight)

        Args:
            query: Entity name
            all_titles: All titles dictionary
            id_to_name: Platform ID to name mapping
            current_date: Current date

        Returns:
            Matched news list
        """
        matches = []

        for platform_id, titles in all_titles.items():
            platform_name = id_to_name.get(platform_id, platform_id)

            for title, info in titles.items():
                if query in title:
                    news_item = {
                        "title": title,
                        "platform": platform_id,
                        "platform_name": platform_name,
                        "date": current_date.strftime("%Y-%m-%d"),
                        "similarity_score": 1.0,
                        "ranks": info.get("ranks", []),
                        "count": len(info.get("ranks", [])),
                        "rank": info["ranks"][0] if info["ranks"] else 999
                    }

                    if include_url:
                        news_item["url"] = info.get("url", "")
                        news_item["mobileUrl"] = info.get("mobileUrl", "")

                    matches.append(news_item)

        return matches

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _fuzzy_match(self, query: str, text: str, threshold: float = 0.3) -> Tuple[bool, float]:
        """
        Fuzzy matching function

        Args:
            query: Query text
            text: Text to match against
            threshold: Match threshold

        Returns:
            (is_match, similarity_score)
        """
        if query.lower() in text.lower():
            return True, 1.0

        similarity = self._calculate_similarity(query, text)
        if similarity >= threshold:
            return True, similarity

        query_words = set(self._extract_keywords(query))
        text_words = set(self._extract_keywords(text))

        if not query_words or not text_words:
            return False, 0.0

        common_words = query_words & text_words
        keyword_overlap = len(common_words) / len(query_words)

        if keyword_overlap >= 0.5:  # 50% keyword overlap
            return True, keyword_overlap

        return False, similarity

    def _extract_keywords(self, text: str, min_length: int = 2) -> List[str]:
        """
        Extract keywords from text

        Args:
            text: Input text
            min_length: Minimum word length

        Returns:
            List of keywords
        """
        text = re.sub(r'http[s]?://\S+', '', text)
        text = re.sub(r'\[.*?\]', '', text)

        words = re.findall(r'[\w]+', text)

        keywords = [
            word for word in words
            if word and len(word) >= min_length and word not in self.stopwords
        ]

        return keywords

    def _calculate_keyword_overlap(self, keywords1: List[str], keywords2: List[str]) -> float:
        """
        Calculate overlap between two keyword lists

        Args:
            keywords1: First keyword list
            keywords2: Second keyword list

        Returns:
            Overlap score (0-1)
        """
        if not keywords1 or not keywords2:
            return 0.0

        set1 = set(keywords1)
        set2 = set(keywords2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def search_related_news_history(
        self,
        reference_text: str,
        time_preset: str = "yesterday",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        threshold: float = 0.4,
        limit: int = 50,
        include_url: bool = False
    ) -> Dict:
        """
        Search historical news related to a reference text

        Args:
            reference_text: Reference news title or content
            time_preset: Time range preset: "yesterday", "last_week", "last_month", "custom"
            start_date: Custom start date (if time_preset="custom")
            end_date: Custom end date (if time_preset="custom")
            threshold: Similarity threshold (0-1), default 0.4
            limit: Return count limit, default 50
            include_url: Whether to include URL links, default False

        Returns:
            Search results dictionary
        """
        try:
            # Parameter validation
            reference_text = validate_keyword(reference_text)
            threshold = max(0.0, min(1.0, threshold))
            limit = validate_limit(limit, default=50)

            # Determine query date range
            today = datetime.now()

            if time_preset == "yesterday":
                search_start = today - timedelta(days=1)
                search_end = today - timedelta(days=1)
            elif time_preset == "last_week":
                search_start = today - timedelta(days=7)
                search_end = today - timedelta(days=1)
            elif time_preset == "last_month":
                search_start = today - timedelta(days=30)
                search_end = today - timedelta(days=1)
            elif time_preset == "custom":
                if not start_date or not end_date:
                    raise InvalidParameterError(
                        "Custom time range requires both start_date and end_date",
                        suggestion="Please provide start_date and end_date parameters"
                    )
                search_start = start_date
                search_end = end_date
            else:
                raise InvalidParameterError(
                    f"Unsupported time range preset: {time_preset}",
                    suggestion="Please use 'yesterday', 'last_week', 'last_month' or 'custom'"
                )

            # Extract keywords from reference text
            reference_keywords = self._extract_keywords(reference_text)

            if not reference_keywords:
                raise InvalidParameterError(
                    "Could not extract keywords from reference text",
                    suggestion="Please provide more descriptive text"
                )

            # Collect all related news
            all_related_news = []
            current_date = search_start

            while current_date <= search_end:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(current_date)

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        for title, info in titles.items():
                            title_similarity = self._calculate_similarity(reference_text, title)
                            title_keywords = self._extract_keywords(title)
                            keyword_overlap = self._calculate_keyword_overlap(
                                reference_keywords,
                                title_keywords
                            )

                            # Combined score (70% keyword overlap + 30% text similarity)
                            combined_score = keyword_overlap * 0.7 + title_similarity * 0.3

                            if combined_score >= threshold:
                                news_item = {
                                    "title": title,
                                    "platform": platform_id,
                                    "platform_name": platform_name,
                                    "date": current_date.strftime("%Y-%m-%d"),
                                    "similarity_score": round(combined_score, 4),
                                    "keyword_overlap": round(keyword_overlap, 4),
                                    "text_similarity": round(title_similarity, 4),
                                    "common_keywords": list(set(reference_keywords) & set(title_keywords)),
                                    "rank": info["ranks"][0] if info["ranks"] else 0
                                }

                                if include_url:
                                    news_item["url"] = info.get("url", "")
                                    news_item["mobileUrl"] = info.get("mobileUrl", "")

                                all_related_news.append(news_item)

                except DataNotFoundError:
                    pass
                except Exception as e:
                    print(f"Warning: Error processing date {current_date.strftime('%Y-%m-%d')}: {e}")

                current_date += timedelta(days=1)

            if not all_related_news:
                return {
                    "success": True,
                    "results": [],
                    "total": 0,
                    "query": reference_text,
                    "time_preset": time_preset,
                    "date_range": {
                        "start": search_start.strftime("%Y-%m-%d"),
                        "end": search_end.strftime("%Y-%m-%d")
                    },
                    "message": "No related news found"
                }

            # Sort by similarity
            all_related_news.sort(key=lambda x: x["similarity_score"], reverse=True)
            results = all_related_news[:limit]

            # Statistics
            platform_distribution = Counter([news["platform"] for news in all_related_news])
            date_distribution = Counter([news["date"] for news in all_related_news])

            result = {
                "success": True,
                "summary": {
                    "total_found": len(all_related_news),
                    "returned_count": len(results),
                    "requested_limit": limit,
                    "threshold": threshold,
                    "reference_text": reference_text,
                    "reference_keywords": reference_keywords,
                    "time_preset": time_preset,
                    "date_range": {
                        "start": search_start.strftime("%Y-%m-%d"),
                        "end": search_end.strftime("%Y-%m-%d")
                    }
                },
                "results": results,
                "statistics": {
                    "platform_distribution": dict(platform_distribution),
                    "date_distribution": dict(date_distribution),
                    "avg_similarity": round(
                        sum([news["similarity_score"] for news in all_related_news]) / len(all_related_news),
                        4
                    ) if all_related_news else 0.0
                }
            }

            if len(all_related_news) < limit:
                result["note"] = f"With threshold {threshold}, only {len(all_related_news)} related news items were found"

            return result

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
