
import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from trendradar.core import load_config
from trendradar.context import AppContext
from trendradar.storage import get_storage_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_report(target_date: str = None, output_path: str = None):
    """
    Generate HTML report from stored data for a specific date.
    
    Args:
        target_date: Date string YYYY-MM-DD. Defaults to today.
        output_path: Optional custom output directory.
    """
    try:
        # 1. Initialize
        config = load_config()
        if output_path:
            config["OUTPUT_DIR"] = output_path
            
        ctx = AppContext(config)
        
        # 2. Determine Date
        if not target_date:
            target_date = ctx.format_date()
        
        logger.info(f"Generating report for date: {target_date}")
        
        # 3. Read Data from Storage
        # IMPORTANT: Pass None as platform_ids to fetch ALL data regardless of config
        # This handles the RSS-only case where platform_ids might be empty in config
        all_results, id_to_name, title_info = ctx.read_today_titles(
            None, quiet=False
        )
        
        # Note: read_today_titles usually defaults to "today". 
        # We need to ensure we can query a specific date if it's not today.
        # But for now, let's assume the user wants the "daily summary" which is typically "today" unless we modify StorageManager.
        # However, StorageManager.get_today_all_data accepts a 'date' param!
        # The current ctx.read_today_titles doesn't seem to expose the date param.
        # Let's bypass ctx.read_today_titles and go to storage directly for flexibility.
        
        storage_config = config.get("STORAGE", {})
        local_config = storage_config.get("LOCAL", {})
        
        storage_manager = get_storage_manager(
            backend_type=storage_config.get("BACKEND", "auto"),
            data_dir=local_config.get("DATA_DIR", "output"),
            timezone=config.get("TIMEZONE", "Asia/Kolkata"),
            force_new=True
        )
        
        # Fetch specific date data directly
        news_data = storage_manager.get_today_all_data(date=target_date)
        
        if not news_data or not news_data.items:
            logger.warning(f"No data found for date {target_date}")
            return
            
        # Reconstruct result structure expected by analysis pipeline
        all_results = {}
        final_id_to_name = news_data.id_to_name
        title_info = {}
        
        for source_id, news_list in news_data.items.items():
            all_results[source_id] = {}
            title_info[source_id] = {}
            
            for item in news_list:
                all_results[source_id][item.title] = {
                    "ranks": getattr(item, 'ranks', [item.rank]),
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or ""
                }
                title_info[source_id][item.title] = {
                    "first_time": getattr(item, 'first_time', item.crawl_time),
                    "last_time": getattr(item, 'last_time', item.crawl_time),
                    "count": getattr(item, 'count', 1),
                    "ranks": getattr(item, 'ranks', [item.rank]),
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or ""
                }
        
        total_items = sum(len(titles) for titles in all_results.values())
        logger.info(f"Loaded {total_items} items from database.")
        
        # 4. Perform Analysis
        word_groups, filter_words, global_filters = ctx.load_frequency_words()
        
        stats, total = ctx.count_frequency(
            all_results,
            word_groups,
            filter_words,
            final_id_to_name,
            title_info,
            new_titles=None,
            mode="daily",
            global_filters=global_filters
        )
        
        # 5. Generate HTML
        html_file = ctx.generate_html(
            stats,
            total, # total_titles
            failed_ids=[],
            new_titles=None,
            id_to_name=final_id_to_name,
            mode="daily",
            is_daily_summary=True # Forces typical daily report format
        )
        
        if html_file:
            # If output path is custom, we might want to copy/move it, 
            # but ctx.generate_html puts it in standardized dated folders.
            logger.info(f"Report generated successfully: {html_file}")
            
            # Also ensure index.html in root is updated to this latest report
            root_index = Path("index.html")
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
            with open(root_index, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Updated root index.html")
            
        else:
            logger.error("Failed to generate HTML file.")

    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TrendRadar Report Generator')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, help='Output directory')
    
    args = parser.parse_args()
    
    generate_report(args.date, args.output)
