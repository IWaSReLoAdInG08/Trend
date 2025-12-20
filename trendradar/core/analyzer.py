# coding=utf-8
"""
Analysis Module

Provides news statistics and analysis functions:
- calculate_news_weight: Calculate news weight
- format_time_display: Format time display
- count_word_frequency: Count word frequency
"""

from typing import Dict, List, Tuple, Optional, Callable

from trendradar.core.frequency import matches_word_groups


def calculate_news_weight(
    title_data: Dict,
    rank_threshold: int,
    weight_config: Dict,
) -> float:
    """
    Calculate news weight for sorting

    Args:
        title_data: Title data containing ranks and count
        rank_threshold: Rank threshold
        weight_config: Weight configuration {RANK_WEIGHT, FREQUENCY_WEIGHT, HOTNESS_WEIGHT}

    Returns:
        float: Calculated weight value
    """
    ranks = title_data.get("ranks", [])
    if not ranks:
        return 0.0

    count = title_data.get("count", len(ranks))

    # Rank Weight: Σ(11 - min(rank, 10)) / count
    rank_scores = []
    for rank in ranks:
        score = 11 - min(rank, 10)
        rank_scores.append(score)

    rank_weight = sum(rank_scores) / len(ranks) if ranks else 0

    # Frequency Weight: min(count, 10) * 10
    frequency_weight = min(count, 10) * 10

    # Hotness Bonus: high rank count / total count * 100
    high_rank_count = sum(1 for rank in ranks if rank <= rank_threshold)
    hotness_ratio = high_rank_count / len(ranks) if ranks else 0
    hotness_weight = hotness_ratio * 100

    total_weight = (
        rank_weight * weight_config["RANK_WEIGHT"]
        + frequency_weight * weight_config["FREQUENCY_WEIGHT"]
        + hotness_weight * weight_config["HOTNESS_WEIGHT"]
    )

    return total_weight


def format_time_display(
    first_time: str,
    last_time: str,
    convert_time_func: Callable[[str], str],
) -> str:
    """
    Format time display (convert HH-MM to HH:MM)

    Args:
        first_time: First appearance time
        last_time: Last appearance time
        convert_time_func: Time conversion function

    Returns:
        str: Formatted time display string
    """
    if not first_time:
        return ""
    # Convert to display format
    first_display = convert_time_func(first_time)
    last_display = convert_time_func(last_time)
    if first_display == last_display or not last_display:
        return first_display
    else:
        return f"[{first_display} ~ {last_display}]"


def count_word_frequency(
    results: Dict,
    word_groups: List[Dict],
    filter_words: List[str],
    id_to_name: Dict,
    title_info: Optional[Dict] = None,
    rank_threshold: int = 3,
    new_titles: Optional[Dict] = None,
    mode: str = "daily",
    global_filters: Optional[List[str]] = None,
    weight_config: Optional[Dict] = None,
    max_news_per_keyword: int = 0,
    sort_by_position_first: bool = False,
    is_first_crawl_func: Optional[Callable[[], bool]] = None,
    convert_time_func: Optional[Callable[[str], str]] = None,
    quiet: bool = False,
) -> Tuple[List[Dict], int]:
    """
    Count word frequency, supporting required words, frequency words, filter words, global filters, and marking new titles

    Args:
        results: Crawl results {source_id: {title: title_data}}
        word_groups: Word group configuration list
        filter_words: Filter words list
        id_to_name: Mapping from ID to name
        title_info: Title statistics info (optional)
        rank_threshold: Rank threshold
        new_titles: New titles (optional)
        mode: Report mode (daily/incremental/current)
        global_filters: Global filter words (optional)
        weight_config: Weight configuration
        max_news_per_keyword: Max news per keyword
        sort_by_position_first: Whether to prioritize sorting by config position
        is_first_crawl_func: Function to check if it's the first crawl of the day
        convert_time_func: Time conversion function
        quiet: Whether to be quiet (no logging)

    Returns:
        Tuple[List[Dict], int]: (Stats results list, Total title count)
    """
    # Default weight config
    if weight_config is None:
        weight_config = {
            "RANK_WEIGHT": 0.4,
            "FREQUENCY_WEIGHT": 0.3,
            "HOTNESS_WEIGHT": 0.3,
        }

    # Default time conversion function
    if convert_time_func is None:
        convert_time_func = lambda x: x

    # Default first crawl check function
    if is_first_crawl_func is None:
        is_first_crawl_func = lambda: True

    # If no word groups configured, create a virtual group for all news
    if not word_groups:
        print("Empty frequency words config, showing all news")
        word_groups = [{"required": [], "normal": [], "group_key": "All News"}]
        filter_words = []  # Clear filter words, show all news

    is_first_today = is_first_crawl_func()

    # Determine data source and new title marking logic
    if mode == "incremental":
        if is_first_today:
            # Incremental mode + First crawl of the day: process all news, mark all as new
            results_to_process = results
            all_news_are_new = True
        else:
            # Incremental mode + Not first crawl: process only new news
            results_to_process = new_titles if new_titles else {}
            all_news_are_new = True
    elif mode == "current":
        # Current mode: process only current time batch news, but stats come from full history
        if title_info:
            latest_time = None
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time

            # Process only news where last_time equals latest_time
            if latest_time:
                results_to_process = {}
                for source_id, source_titles in results.items():
                    if source_id in title_info:
                        filtered_titles = {}
                        for title, title_data in source_titles.items():
                            if title in title_info[source_id]:
                                info = title_info[source_id][title]
                                if info.get("last_time") == latest_time:
                                    filtered_titles[title] = title_data
                        if filtered_titles:
                            results_to_process[source_id] = filtered_titles

                print(
                    f"Current List Mode: Latest time {latest_time}, filtered {sum(len(titles) for titles in results_to_process.values())} current news items"
                )
            else:
                results_to_process = results
        else:
            results_to_process = results
        all_news_are_new = False
    else:
        # Daily summary mode: process all news
        results_to_process = results
        all_news_are_new = False
        total_input_news = sum(len(titles) for titles in results.values())
        filter_status = (
            "Show All"
            if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News"
            else "Frequency Word Filtering"
        )
        print(f"Daily Summary Mode: Processing {total_input_news} news items, Mode: {filter_status}")

    word_stats = {}
    total_titles = 0
    processed_titles = {}
    matched_new_count = 0

    if title_info is None:
        title_info = {}
    if new_titles is None:
        new_titles = {}

    for group in word_groups:
        group_key = group["group_key"]
        word_stats[group_key] = {"count": 0, "titles": {}}

    for source_id, titles_data in results_to_process.items():
        total_titles += len(titles_data)

        if source_id not in processed_titles:
            processed_titles[source_id] = {}

        for title, title_data in titles_data.items():
            if title in processed_titles.get(source_id, {}):
                continue

            # Use unified matching logic
            matches_frequency_words = matches_word_groups(
                title, word_groups, filter_words, global_filters
            )

            if not matches_frequency_words:
                continue

            # If incremental mode or first time in current mode, count matched new news
            if (mode == "incremental" and all_news_are_new) or (
                mode == "current" and is_first_today
            ):
                matched_new_count += 1

            source_ranks = title_data.get("ranks", [])
            source_url = title_data.get("url", "")
            source_mobile_url = title_data.get("mobileUrl", "")

            # Find matching word group (defensive conversion to ensure type safety)
            title_lower = str(title).lower() if not isinstance(title, str) else title.lower()
            for group in word_groups:
                required_words = group["required"]
                normal_words = group["normal"]

                # If "All News" mode, all titles match the first (and only) group
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News":
                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []
                else:
                    # Original matching logic
                    if required_words:
                        all_required_present = all(
                            req_word.lower() in title_lower
                            for req_word in required_words
                        )
                        if not all_required_present:
                            continue

                    if normal_words:
                        any_normal_present = any(
                            normal_word.lower() in title_lower
                            for normal_word in normal_words
                        )
                        if not any_normal_present:
                            continue

                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []

                first_time = ""
                last_time = ""
                count_info = 1
                ranks = source_ranks if source_ranks else []
                url = source_url
                mobile_url = source_mobile_url

                # For current mode, get full data from historical stats
                if (
                    mode == "current"
                    and title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                elif (
                    title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)

                if not ranks:
                    ranks = [99]

                time_display = format_time_display(first_time, last_time, convert_time_func)

                source_name = id_to_name.get(source_id, source_id)

                # Check if new
                is_new = False
                if all_news_are_new:
                    # In incremental mode, all processed news are new, or all news are new on first run of the day
                    is_new = True
                elif new_titles and source_id in new_titles:
                    # Check if in new titles list
                    new_titles_for_source = new_titles[source_id]
                    is_new = title in new_titles_for_source

                word_stats[group_key]["titles"][source_id].append(
                    {
                        "title": title,
                        "source_name": source_name,
                        "first_time": first_time,
                        "last_time": last_time,
                        "time_display": time_display,
                        "count": count_info,
                        "ranks": ranks,
                        "rank_threshold": rank_threshold,
                        "url": url,
                        "mobileUrl": mobile_url,
                        "is_new": is_new,
                    }
                )

                if source_id not in processed_titles:
                    processed_titles[source_id] = {}
                processed_titles[source_id][title] = True

                break

    # Final summary log
    if mode == "incremental":
        if is_first_today:
            total_input_news = sum(len(titles) for titles in results.values())
            filter_status = (
                "Show All"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News"
                else "Frequency Matches"
            )
            print(
                f"Incremental Mode: First crawl of the day, {matched_new_count} matched {filter_status} out of {total_input_news} news"
            )
        else:
            if new_titles:
                total_new_count = sum(len(titles) for titles in new_titles.values())
                filter_status = (
                    "Show All"
                    if len(word_groups) == 1
                    and word_groups[0]["group_key"] == "All News"
                    else "Matched Frequency Words"
                )
                print(
                    f"Incremental Mode: {matched_new_count} matched {filter_status} out of {total_new_count} newly added news"
                )
                if matched_new_count == 0 and len(word_groups) > 1:
                    print("Incremental Mode: No new news matched frequency words, skipping notification")
            else:
                print("Incremental Mode: No new news detected")
    elif mode == "current":
        total_input_news = sum(len(titles) for titles in results_to_process.values())
        if is_first_today:
            filter_status = (
                "Show All"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News"
                else "Frequency Matches"
            )
            print(
                f"Current List Mode: First crawl of the day, {matched_new_count} matched {filter_status} out of {total_input_news} current news"
            )
        else:
            matched_count = sum(stat["count"] for stat in word_stats.values())
            filter_status = (
                "Show All"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News"
                else "Frequency Matches"
            )
            print(
                f"Current List Mode: {matched_count} matched {filter_status} out of {total_input_news} current news"
            )

    stats = []
    # Create map for group_key to position and max_count
    group_key_to_position = {
        group["group_key"]: idx for idx, group in enumerate(word_groups)
    }
    group_key_to_max_count = {
        group["group_key"]: group.get("max_count", 0) for group in word_groups
    }

    for group_key, data in word_stats.items():
        all_titles = []
        for source_id, title_list in data["titles"].items():
            all_titles.extend(title_list)

        # Sort by weight
        sorted_titles = sorted(
            all_titles,
            key=lambda x: (
                -calculate_news_weight(x, rank_threshold, weight_config),
                min(x["ranks"]) if x["ranks"] else 999,
                -x["count"],
            ),
        )

        # Apply max display count limit (Priority: Individual Config > Global Config)
        group_max_count = group_key_to_max_count.get(group_key, 0)
        if group_max_count == 0:
            # Use global config
            group_max_count = max_news_per_keyword

        if group_max_count > 0:
            sorted_titles = sorted_titles[:group_max_count]

        stats.append(
            {
                "word": group_key,
                "count": data["count"],
                "position": group_key_to_position.get(group_key, 999),
                "titles": sorted_titles,
                "percentage": (
                    round(data["count"] / total_titles * 100, 2)
                    if total_titles > 0
                    else 0
                ),
            }
        )

    # Sort priority based on config
    if sort_by_position_first:
        # First by config position, then by hotness count
        stats.sort(key=lambda x: (x["position"], -x["count"]))
    else:
        # First by hotness count, then by config position (original logic)
        stats.sort(key=lambda x: (-x["count"], x["position"]))

    # Print filtered matched news count
    matched_news_count = sum(len(stat["titles"]) for stat in stats if stat["count"] > 0)
    if not quiet and mode == "daily":
        print(f"Daily Summary Mode: Processing {total_titles} news items, Mode: Frequency Word Filtering")
        print(f"After Frequency Filtering: {matched_news_count} news matched")

    return stats, total_titles
