# coding=utf-8
"""
Report Generation Module

Provides report data preparation and HTML generation functions:
- prepare_report_data: Prepare report data
- generate_html_report: Generate HTML report
"""

from pathlib import Path
from typing import Dict, List, Optional, Callable


def prepare_report_data(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
    rank_threshold: int = 3,
    matches_word_groups_func: Optional[Callable] = None,
    load_frequency_words_func: Optional[Callable] = None,
) -> Dict:
    """
    Prepare report data

    Args:
        stats: List of statistical results
        failed_ids: List of failed IDs
        new_titles: New titles
        id_to_name: ID to name mapping
        mode: Report mode (daily/incremental/current)
        rank_threshold: Rank threshold
        matches_word_groups_func: Word group matching function
        load_frequency_words_func: Load frequency words function

    Returns:
        Dict: Prepared report data
    """
    processed_new_titles = []

    # Hide new news section in incremental mode
    hide_new_section = mode == "incremental"

    # Only process new news section if not in hidden mode
    if not hide_new_section:
        filtered_new_titles = {}
        if new_titles and id_to_name:
            # If a matching function is provided, filter using it
            if matches_word_groups_func and load_frequency_words_func:
                word_groups, filter_words, global_filters = load_frequency_words_func()
                for source_id, titles_data in new_titles.items():
                    filtered_titles = {}
                    for title, title_data in titles_data.items():
                        if matches_word_groups_func(title, word_groups, filter_words, global_filters):
                            filtered_titles[title] = title_data
                    if filtered_titles:
                        filtered_new_titles[source_id] = filtered_titles
            else:
                # Use all if no matching function
                filtered_new_titles = new_titles

            # Print filtered new hot topics count (consistent with push display)
            original_new_count = sum(len(titles) for titles in new_titles.values()) if new_titles else 0
            filtered_new_count = sum(len(titles) for titles in filtered_new_titles.values()) if filtered_new_titles else 0
            if original_new_count > 0:
                print(f"After frequency word filtering: {filtered_new_count} new hot topic matches (original {original_new_count})")

        if filtered_new_titles and id_to_name:
            for source_id, titles_data in filtered_new_titles.items():
                source_name = id_to_name.get(source_id, source_id)
                source_titles = []

                for title, title_data in titles_data.items():
                    url = title_data.get("url", "")
                    mobile_url = title_data.get("mobileUrl", "")
                    ranks = title_data.get("ranks", [])

                    processed_title = {
                        "title": title,
                        "source_name": source_name,
                        "time_display": "",
                        "count": 1,
                        "ranks": ranks,
                        "rank_threshold": rank_threshold,
                        "url": url,
                        "mobile_url": mobile_url,
                        "is_new": True,
                    }
                    source_titles.append(processed_title)

                if source_titles:
                    processed_new_titles.append(
                        {
                            "source_id": source_id,
                            "source_name": source_name,
                            "titles": source_titles,
                        }
                    )

    processed_stats = []
    for stat in stats:
        if stat["count"] <= 0:
            continue

        processed_titles = []
        for title_data in stat["titles"]:
            processed_title = {
                "title": title_data["title"],
                "source_name": title_data["source_name"],
                "time_display": title_data["time_display"],
                "count": title_data["count"],
                "ranks": title_data["ranks"],
                "rank_threshold": title_data["rank_threshold"],
                "url": title_data.get("url", ""),
                "mobile_url": title_data.get("mobileUrl", ""),
                "is_new": title_data.get("is_new", False),
            }
            processed_titles.append(processed_title)

        processed_stats.append(
            {
                "word": stat["word"],
                "count": stat["count"],
                "percentage": stat.get("percentage", 0),
                "titles": processed_titles,
            }
        )

    return {
        "stats": processed_stats,
        "new_titles": processed_new_titles,
        "failed_ids": failed_ids or [],
        "total_new_count": sum(
            len(source["titles"]) for source in processed_new_titles
        ),
    }


def generate_html_report(
    stats: List[Dict],
    total_titles: int,
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
    is_daily_summary: bool = False,
    update_info: Optional[Dict] = None,
    rank_threshold: int = 3,
    output_dir: str = "output",
    date_folder: str = "",
    time_filename: str = "",
    render_html_func: Optional[Callable] = None,
    matches_word_groups_func: Optional[Callable] = None,
    load_frequency_words_func: Optional[Callable] = None,
    enable_index_copy: bool = True,
) -> str:
    """
    Generate HTML Report

    Args:
        stats: List of statistical results
        total_titles: Total number of titles
        failed_ids: List of failed IDs
        new_titles: New titles
        id_to_name: ID to name mapping
        mode: Report mode (daily/incremental/current)
        is_daily_summary: Whether it is a daily summary
        update_info: Update information
        rank_threshold: Rank threshold
        output_dir: Output directory
        date_folder: Date folder name
        time_filename: Time filename
        render_html_func: HTML rendering function
        matches_word_groups_func: Word group matching function
        load_frequency_words_func: Load frequency words function
        enable_index_copy: Whether to copy to index.html

    Returns:
        str: Generated HTML file path
    """
    if is_daily_summary:
        if mode == "current":
            filename = "current_summary.html"
        elif mode == "incremental":
            filename = "daily_incremental.html"
        else:
            filename = "daily_summary.html"
    else:
        filename = f"{time_filename}.html"

    # Build output path
    output_path = Path(output_dir) / date_folder / "html"
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = str(output_path / filename)

    # Prepare report data
    report_data = prepare_report_data(
        stats,
        failed_ids,
        new_titles,
        id_to_name,
        mode,
        rank_threshold,
        matches_word_groups_func,
        load_frequency_words_func,
    )

    # Render HTML content
    if render_html_func:
        html_content = render_html_func(
            report_data, total_titles, is_daily_summary, mode, update_info
        )
    else:
        # Default simple HTML
        html_content = f"<html><body><h1>Report</h1><pre>{report_data}</pre></body></html>"

    # Write to file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # If it is a daily summary and index copy is enabled
    if is_daily_summary and enable_index_copy:
        # Generate to root directory (for GitHub Pages access)
        root_index_path = Path("index.html")
        with open(root_index_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Also generate to output directory (for Docker Volume mount access)
        output_index_path = Path(output_dir) / "index.html"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        with open(output_index_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    return file_path
