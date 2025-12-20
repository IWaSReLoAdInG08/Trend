
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.append(os.getcwd())

from trendradar.core import load_config
from trendradar.context import AppContext
from trendradar.crawler import RSSFetcher
from trendradar.storage import convert_crawl_results_to_news_data, get_storage_manager

# Configure logging to stderr so stdout is clean for JSON
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

def fetch_data() -> Dict:
    """
    Fetch news data from configured sources (RSS) and save to DB.
    Returns a dict with execution results.
    """
    try:
        # 1. Initialize Context
        config = load_config()
        ctx = AppContext(config)
        
        # Access nested storage config
        storage_config = config.get("STORAGE", {})
        local_config = storage_config.get("LOCAL", {})
        formats_config = storage_config.get("FORMATS", {})
        
        storage_manager = get_storage_manager(
            backend_type=storage_config.get("BACKEND", "auto"),
            data_dir=local_config.get("DATA_DIR", "output"),
            enable_txt=formats_config.get("TXT", True),
            enable_html=formats_config.get("HTML", True),
            timezone=config.get("TIMEZONE", "Asia/Kolkata"),
            force_new=True
        )
        
        # Configure Proxy if enabled
        crawler_config = config.get("CRAWLER", {}) # Note: loader.py merges crawler config into top level but let's check defaults
        # Actually loader.py updates config directly. Let's look at how loader.py structures it.
        # It updates config with _load_crawler_config.
        
        use_proxy = config.get("USE_PROXY", False)
        proxy_url = config.get("DEFAULT_PROXY", "") if use_proxy else None
        
        rss_fetcher = RSSFetcher(proxy_url=proxy_url)
        
        logger.info(f"Timezone: {ctx.timezone}")
        
        # 2. Fetch from RSS Feeds
        results = {}
        id_to_name = {}
        failed_ids = []
        
        rss_feeds = config.get("RSS_FEEDS", [])
        if rss_feeds:
            logger.info(f"Fetching {len(rss_feeds)} RSS feeds...")
            feeds_list = [
                (feed["rss_url"], feed["id"], feed["name"])
                for feed in rss_feeds
            ]
            rss_results, rss_id_to_name, rss_failed = rss_fetcher.crawl_rss_feeds(feeds_list)
            
            results.update(rss_results)
            id_to_name.update(rss_id_to_name)
            failed_ids.extend(rss_failed)
        else:
            logger.warning("No RSS feeds configured.")
            
        total_items = sum(len(items) for items in results.values())
        logger.info(f"Fetched {total_items} items from {len(results)} sources.")
        
        # 3. Save to Database
        if results:
            crawl_time = ctx.format_time()
            crawl_date = ctx.format_date()
            news_data = convert_crawl_results_to_news_data(
                results, id_to_name, failed_ids, crawl_time, crawl_date
            )
            
            saved = storage_manager.save_news_data(news_data)
            if saved:
                logger.info("Data saved to database.")
            
            # Optional: Save TXT snapshot for debug/backup
            txt_file = storage_manager.save_txt_snapshot(news_data)
            
            return {
                "status": "success",
                "fetched_count": total_items,
                "sources_count": len(results),
                "failed_sources": failed_ids,
                "timestamp": crawl_time,
                "date": crawl_date,
                "txt_snapshot": txt_file
            }
        else:
            return {
                "status": "warning",
                "message": "No data fetched",
                "fetched_count": 0
            }
            
    except Exception as e:
        logger.error(f"Error fetching news: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    result = fetch_data()
    # Print JSON result to stdout for parsing by external tools/caller
    print(json.dumps(result, indent=2))
