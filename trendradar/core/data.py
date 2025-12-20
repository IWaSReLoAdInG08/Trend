# coding=utf-8
"""
Data Processing Module

Provides data reading, saving, and detection functions:
- save_titles_to_file: Save titles to TXT file
- read_all_today_titles: Read all titles for today from storage backend
- detect_latest_new_titles: Detect new titles in the latest batch
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable


def save_titles_to_file(
    results: Dict,
    id_to_name: Dict,
    failed_ids: List,
    output_path: str,
    clean_title_func: Callable[[str], str],
) -> str:
    """
    Save titles to TXT file

    Args:
        results: Crawl results {source_id: {title: title_data}}
        id_to_name: ID to name mapping
        failed_ids: List of failed IDs
        output_path: Output file path
        clean_title_func: Title cleaning function

    Returns:
        str: Saved file path
    """
    # Ensure directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for id_value, title_data in results.items():
            # id | name or id
            name = id_to_name.get(id_value)
            if name and name != id_value:
                f.write(f"{id_value} | {name}\n")
            else:
                f.write(f"{id_value}\n")

            # Sort titles by rank
            sorted_titles = []
            for title, info in title_data.items():
                cleaned_title = clean_title_func(title)
                if isinstance(info, dict):
                    ranks = info.get("ranks", [])
                    url = info.get("url", "")
                    mobile_url = info.get("mobileUrl", "")
                else:
                    ranks = info if isinstance(info, list) else []
                    url = ""
                    mobile_url = ""

                rank = ranks[0] if ranks else 1
                sorted_titles.append((rank, cleaned_title, url, mobile_url))

            sorted_titles.sort(key=lambda x: x[0])

            for rank, cleaned_title, url, mobile_url in sorted_titles:
                line = f"{rank}. {cleaned_title}"

                if url:
                    line += f" [URL:{url}]"
                if mobile_url:
                    line += f" [MOBILE:{mobile_url}]"
                f.write(line + "\n")

            f.write("\n")

        if failed_ids:
            f.write("==== Failed IDs ====\n")
            for id_value in failed_ids:
                f.write(f"{id_value}\n")

    return output_path


def read_all_today_titles_from_storage(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
) -> Tuple[Dict, Dict, Dict]:
    """
    Read all titles for today from storage backend (SQLite data)

    Args:
        storage_manager: Storage manager instance
        current_platform_ids: Current monitored platform IDs (for filtering)

    Returns:
        Tuple[Dict, Dict, Dict]: (all_results, id_to_name, title_info)
    """
    try:
        news_data = storage_manager.get_today_all_data()

        if not news_data or not news_data.items:
            return {}, {}, {}

        all_results = {}
        final_id_to_name = {}
        title_info = {}

        for source_id, news_list in news_data.items.items():
            # Filter by platform
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue

            # Get source name
            source_name = news_data.id_to_name.get(source_id, source_id)
            final_id_to_name[source_id] = source_name

            if source_id not in all_results:
                all_results[source_id] = {}
                title_info[source_id] = {}

            for item in news_list:
                title = item.title
                ranks = getattr(item, 'ranks', [item.rank])
                first_time = getattr(item, 'first_time', item.crawl_time)
                last_time = getattr(item, 'last_time', item.crawl_time)
                count = getattr(item, 'count', 1)

                all_results[source_id][title] = {
                    "ranks": ranks,
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or "",
                }

                title_info[source_id][title] = {
                    "first_time": first_time,
                    "last_time": last_time,
                    "count": count,
                    "ranks": ranks,
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or "",
                }

        return all_results, final_id_to_name, title_info

    except Exception as e:
        print(f"[Storage] Failed to read data from storage backend: {e}")
        return {}, {}, {}


def read_all_today_titles(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
    quiet: bool = False,
) -> Tuple[Dict, Dict, Dict]:
    """
    Read all titles for today (from storage backend)

    Args:
        storage_manager: Storage manager instance
        current_platform_ids: Current monitored platform IDs (for filtering)
        quiet: Whether to be quiet (no logging)

    Returns:
        Tuple[Dict, Dict, Dict]: (all_results, id_to_name, title_info)
    """
    all_results, final_id_to_name, title_info = read_all_today_titles_from_storage(
        storage_manager, current_platform_ids
    )

    if not quiet:
        if all_results:
            total_count = sum(len(titles) for titles in all_results.values())
            print(f"[Storage] Read {total_count} titles from storage backend")
        else:
            print("[Storage] No data for today")

    return all_results, final_id_to_name, title_info


def detect_latest_new_titles_from_storage(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
) -> Dict:
    """
    Detect new titles from the latest batch in storage backend

    Args:
        storage_manager: Storage manager instance
        current_platform_ids: Current monitored platform IDs (for filtering)

    Returns:
        Dict: New titles {source_id: {title: title_data}}
    """
    try:
        # Get latest crawl data
        latest_data = storage_manager.get_latest_crawl_data()
        if not latest_data or not latest_data.items:
            return {}

        # Get all historical data
        all_data = storage_manager.get_today_all_data()
        if not all_data or not all_data.items:
            # No historical data (first crawl), no "new" titles
            return {}

        # Get latest batch time
        latest_time = latest_data.crawl_time

        # Step 1: Collect latest batch titles (last_crawl_time = latest_time)
        latest_titles = {}
        for source_id, news_list in latest_data.items.items():
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue
            latest_titles[source_id] = {}
            for item in news_list:
                latest_titles[source_id][item.title] = {
                    "ranks": [item.rank],
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or "",
                }

        # Step 2: Collect historical titles
        # Key logic: A title is historical if its first_crawl_time < latest_time
        # Even if multiple records exist (different URLs), if any record is historical, the title is historical
        historical_titles = {}
        for source_id, news_list in all_data.items.items():
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue

            historical_titles[source_id] = set()
            for item in news_list:
                first_time = getattr(item, 'first_time', item.crawl_time)
                # If record's first appearance is earlier than latest batch, it's historical
                if first_time < latest_time:
                    historical_titles[source_id].add(item.title)

        # Check if first crawl of the day (no historical titles)
        # If all platform historical sets are empty, implies only one batch exists
        has_historical_data = any(len(titles) > 0 for titles in historical_titles.values())
        if not has_historical_data:
            return {}

        # Step 3: Identify new titles = Latest batch titles - Historical titles
        new_titles = {}
        for source_id, source_latest_titles in latest_titles.items():
            historical_set = historical_titles.get(source_id, set())
            source_new_titles = {}

            for title, title_data in source_latest_titles.items():
                if title not in historical_set:
                    source_new_titles[title] = title_data

            if source_new_titles:
                new_titles[source_id] = source_new_titles

        return new_titles

    except Exception as e:
        print(f"[Storage] Failed to detect new titles from storage backend: {e}")
        return {}


def detect_latest_new_titles(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
    quiet: bool = False,
) -> Dict:
    """
    Detect new titles in the latest batch for today (from storage backend)

    Args:
        storage_manager: Storage manager instance
        current_platform_ids: Current monitored platform IDs (for filtering)
        quiet: Whether to be quiet (no logging)

    Returns:
        Dict: New titles {source_id: {title: title_data}}
    """
    new_titles = detect_latest_new_titles_from_storage(storage_manager, current_platform_ids)
    if new_titles and not quiet:
        total_new = sum(len(titles) for titles in new_titles.values())
        print(f"[Storage] Detected {total_new} new titles from storage backend")
    return new_titles


def is_first_crawl_today(output_dir: str, date_folder: str) -> bool:
    """
    Check if it is the first crawl of the day

    Args:
        output_dir: Output directory
        date_folder: Date folder name

    Returns:
        bool: True if it is the first crawl of the day
    """
    txt_dir = Path(output_dir) / date_folder / "txt"

    if not txt_dir.exists():
        return True

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    return len(files) <= 1
