"""
Data Access Service

Provides a unified data query interface, encapsulating data access logic in English.
"""

import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .cache_service import get_cache
from .parser_service import ParserService
from ..utils.errors import DataNotFoundError


class DataService:
    """Data Access Service Class"""

    def __init__(self, project_root: str = None):
        """
        Initialize data service

        Args:
            project_root: Project root directory
        """
        self.parser = ParserService(project_root)
        self.cache = get_cache()

    def get_latest_news(
        self,
        platforms: Optional[List[str]] = None,
        limit: int = 50,
        include_url: bool = False
    ) -> List[Dict]:
        """
        Get the latest batch of crawled news data

        Args:
            platforms: List of platform IDs
            limit: Return count limit
            include_url: Whether to include URL links

        Returns:
            News list
        """
        # Try cache
        cache_key = f"latest_news:{','.join(platforms or [])}:{limit}:{include_url}"
        cached = self.cache.get(cache_key, ttl=900)
        if cached:
            return cached

        # Read today's data
        all_titles, id_to_name, timestamps = self.parser.read_all_titles_for_date(
            date=None,
            platform_ids=platforms
        )

        # Get latest fetch time
        if timestamps:
            latest_timestamp = max(timestamps.values())
            fetch_time = datetime.fromtimestamp(latest_timestamp)
        else:
            fetch_time = datetime.now()

        # Convert to news list
        news_list = []
        for platform_id, titles in all_titles.items():
            platform_name = id_to_name.get(platform_id, platform_id)

            for title, info in titles.items():
                rank = info["ranks"][0] if info["ranks"] else 0

                news_item = {
                    "title": title,
                    "platform": platform_id,
                    "platform_name": platform_name,
                    "rank": rank,
                    "timestamp": fetch_time.strftime("%Y-%m-%d %H:%M:%S")
                }

                if include_url:
                    news_item["url"] = info.get("url", "")
                    news_item["mobileUrl"] = info.get("mobileUrl", "")

                news_list.append(news_item)

        # Sort by rank
        news_list.sort(key=lambda x: x["rank"])
        result = news_list[:limit]

        # Cache result
        self.cache.set(cache_key, result)

        return result

    def get_news_by_date(
        self,
        target_date: datetime,
        platforms: Optional[List[str]] = None,
        limit: int = 50,
        include_url: bool = False
    ) -> List[Dict]:
        """
        Get news by specific date
        """
        date_str = target_date.strftime("%Y-%m-%d")
        cache_key = f"news_by_date:{date_str}:{','.join(platforms or [])}:{limit}:{include_url}"
        cached = self.cache.get(cache_key, ttl=1800)
        if cached:
            return cached

        # Read data for specified date
        all_titles, id_to_name, _ = self.parser.read_all_titles_for_date(
            date=target_date,
            platform_ids=platforms
        )

        news_list = []
        for platform_id, titles in all_titles.items():
            platform_name = id_to_name.get(platform_id, platform_id)

            for title, info in titles.items():
                avg_rank = sum(info["ranks"]) / len(info["ranks"]) if info["ranks"] else 0

                news_item = {
                    "title": title,
                    "platform": platform_id,
                    "platform_name": platform_name,
                    "rank": info["ranks"][0] if info["ranks"] else 0,
                    "avg_rank": round(avg_rank, 2),
                    "count": len(info["ranks"]),
                    "date": date_str
                }

                if include_url:
                    news_item["url"] = info.get("url", "")
                    news_item["mobileUrl"] = info.get("mobileUrl", "")

                news_list.append(news_item)

        news_list.sort(key=lambda x: x["rank"])
        result = news_list[:limit]
        self.cache.set(cache_key, result)

        return result

    def search_news_by_keyword(
        self,
        keyword: str,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Search news by keyword across historical data
        """
        if date_range:
            start_date, end_date = date_range
        else:
            start_date = end_date = datetime.now()

        results = []
        platform_distribution = Counter()

        current_date = start_date
        while current_date <= end_date:
            try:
                all_titles, id_to_name, _ = self.parser.read_all_titles_for_date(
                    date=current_date,
                    platform_ids=platforms
                )

                for platform_id, titles in all_titles.items():
                    platform_name = id_to_name.get(platform_id, platform_id)

                    for title, info in titles.items():
                        if keyword.lower() in title.lower():
                            avg_rank = sum(info["ranks"]) / len(info["ranks"]) if info["ranks"] else 0

                            results.append({
                                "title": title,
                                "platform": platform_id,
                                "platform_name": platform_name,
                                "ranks": info["ranks"],
                                "count": len(info["ranks"]),
                                "avg_rank": round(avg_rank, 2),
                                "url": info.get("url", ""),
                                "mobileUrl": info.get("mobileUrl", ""),
                                "date": current_date.strftime("%Y-%m-%d")
                            })
                            platform_distribution[platform_id] += 1
            except DataNotFoundError:
                pass

            current_date += timedelta(days=1)

        if not results:
            raise DataNotFoundError(
                f"No news found containing keyword '{keyword}'",
                suggestion="Try different keywords or expand the date range."
            )

        total_ranks = []
        for item in results:
            total_ranks.extend(item["ranks"])

        avg_rank = sum(total_ranks) / len(total_ranks) if total_ranks else 0
        total_found = len(results)
        if limit is not None and limit > 0:
            results = results[:limit]

        return {
            "results": results,
            "total": len(results),
            "total_found": total_found,
            "statistics": {
                "platform_distribution": dict(platform_distribution),
                "avg_rank": round(avg_rank, 2),
                "keyword": keyword
            }
        }

    def get_trending_topics(
        self,
        top_n: int = 10,
        mode: str = "current"
    ) -> Dict:
        """
        Get frequency statistics for watched keywords
        """
        cache_key = f"trending_topics:{top_n}:{mode}"
        cached = self.cache.get(cache_key, ttl=1800)
        if cached:
            return cached

        all_titles, id_to_name, timestamps = self.parser.read_all_titles_for_date()

        if not all_titles:
            raise DataNotFoundError(
                "No news data found for today",
                suggestion="Ensure the crawler has been run successfully."
            )

        word_groups = self.parser.parse_frequency_words()
        titles_to_process = all_titles # Simplified for current/daily distinction in this version

        word_frequency = Counter()
        keyword_to_news = {}

        for platform_id, titles in titles_to_process.items():
            for title in titles.keys():
                for group in word_groups:
                    all_words = group.get("required", []) + group.get("normal", [])
                    for word in all_words:
                        if word and word in title:
                            word_frequency[word] += 1
                            if word not in keyword_to_news:
                                keyword_to_news[word] = []
                            keyword_to_news[word].append(title)

        top_keywords = word_frequency.most_common(top_n)
        topics = []
        for keyword, frequency in top_keywords:
            matched_news = keyword_to_news.get(keyword, [])
            topics.append({
                "keyword": keyword,
                "frequency": frequency,
                "matched_news": len(set(matched_news)),
                "trend": "stable",
                "weight_score": 0.0
            })

        result = {
            "topics": topics,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "total_keywords": len(word_frequency),
            "description": self._get_mode_description(mode)
        }

        self.cache.set(cache_key, result)
        return result

    def _get_mode_description(self, mode: str) -> str:
        """Get mode description"""
        descriptions = {
            "daily": "Daily cumulative statistics",
            "current": "Latest batch statistics"
        }
        return descriptions.get(mode, "Unknown mode")

    def get_current_config(self, section: str = "all") -> Dict:
        """Get current system configuration"""
        cache_key = f"config:{section}"
        cached = self.cache.get(cache_key, ttl=3600)
        if cached:
            return cached

        config_data = self.parser.parse_yaml_config()
        word_groups = self.parser.parse_frequency_words()

        result = {}
        if section in ("all", "crawler"):
            result["crawler"] = {
                "enable_crawler": config_data.get("crawler", {}).get("enable_crawler", True),
                "use_proxy": config_data.get("crawler", {}).get("use_proxy", False),
                "request_interval": config_data.get("crawler", {}).get("request_interval", 1),
                "platforms": [p["id"] for p in config_data.get("platforms", [])]
            }

        if section in ("all", "push"):
            push_config = {
                "enable_notification": config_data.get("notification", {}).get("enable_notification", True),
                "enabled_channels": [],
                "message_batch_size": config_data.get("notification", {}).get("message_batch_size", 20)
            }
            webhooks = config_data.get("notification", {}).get("webhooks", {})
            for channel in ["feishu", "dingtalk", "wework"]:
                if webhooks.get(f"{channel}_url"):
                    push_config["enabled_channels"].append(channel)
            result["push"] = push_config

        if section in ("all", "keywords"):
            result["keywords"] = {
                "word_groups": word_groups,
                "total_groups": len(word_groups)
            }

        if section in ("all", "weights"):
            result["weights"] = {
                "rank_weight": config_data.get("weight", {}).get("rank_weight", 0.6),
                "frequency_weight": config_data.get("weight", {}).get("frequency_weight", 0.3),
                "hotness_weight": config_data.get("weight", {}).get("hotness_weight", 0.1)
            }

        final_result = result if section == "all" else result.get(section, {})
        self.cache.set(cache_key, final_result)
        return final_result

    def get_available_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Scan output directory for available date range"""
        output_dir = self.parser.project_root / "output"
        if not output_dir.exists():
            return (None, None)

        available_dates = []
        for date_folder in output_dir.iterdir():
            if date_folder.is_dir() and not date_folder.name.startswith('.'):
                folder_date = self._parse_date_folder_name(date_folder.name)
                if folder_date:
                    available_dates.append(folder_date)

        if not available_dates:
            return (None, None)
        return (min(available_dates), max(available_dates))

    def _parse_date_folder_name(self, folder_name: str) -> Optional[datetime]:
        """Parse date folder name Supporting Chinese and ISO formats"""
        # ISO format: YYYY-MM-DD
        iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', folder_name)
        if iso_match:
            try:
                return datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            except ValueError:
                pass

        # Support both ISO and legacy Chinese date formats (using unicode escapes for ASCII safety)
        chinese_match = re.match(r'(\d{4})\u5e74(\d{2})\u6708(\d{2})\u65e5', folder_name)
        if chinese_match:
            try:
                return datetime(int(chinese_match.group(1)), int(chinese_match.group(2)), int(chinese_match.group(3)))
            except ValueError:
                pass

        return None

    def get_system_status(self) -> Dict:
        """Get system operational status"""
        output_dir = self.parser.project_root / "output"
        total_storage = 0
        oldest_record = None
        latest_record = None

        if output_dir.exists():
            for date_folder in output_dir.iterdir():
                if date_folder.is_dir() and not date_folder.name.startswith('.'):
                    folder_date = self._parse_date_folder_name(date_folder.name)
                    if folder_date:
                        if oldest_record is None or folder_date < oldest_record:
                            oldest_record = folder_date
                        if latest_record is None or folder_date > latest_record:
                            latest_record = folder_date
                    for item in date_folder.rglob("*"):
                        if item.is_file():
                            total_storage += item.stat().st_size

        return {
            "system": {
                "project_root": str(self.parser.project_root)
            },
            "data": {
                "total_storage": f"{total_storage / 1024 / 1024:.2f} MB",
                "oldest_record": oldest_record.strftime("%Y-%m-%d") if oldest_record else None,
                "latest_record": latest_record.strftime("%Y-%m-%d") if latest_record else None,
            },
            "cache": self.cache.get_stats(),
            "health": "healthy"
        }
