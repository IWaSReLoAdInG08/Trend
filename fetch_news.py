
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
from trendradar.crawler import RSSFetcher, OpinionFetcher
from trendradar.core.categorizer import NewsCategorizer
from trendradar.core.summary import SummaryGenerator
from trendradar.storage import convert_crawl_results_to_news_data, get_storage_manager

# Configure logging to stderr so stdout is clean for JSON
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Set default email configuration
os.environ["EMAIL_PASSWORD"] = "ismgbdbkxquzhfix"
os.environ["EMAIL_FROM"] = "vermashivanshu83@gmail.com"
os.environ["EMAIL_TO"] = "vermashivanshu83@gmail.com"
os.environ["EMAIL_SMTP_SERVER"] = "smtp.gmail.com"
os.environ["EMAIL_SMTP_PORT"] = "465"

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
        categorizer = NewsCategorizer()
        summary_gen = SummaryGenerator(storage_manager)
        
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
            
            # Categorize each item
            for source_id, items in news_data.items.items():
                for item in items:
                    item.categories = categorizer.categorize(item.title)
            
            saved = storage_manager.save_news_data(news_data)
            if saved:
                logger.info("Data saved to database.")
                
                # 4. Fetch Public Reactions (Opinions)
                # Only for the top 10 news items to avoid rate limits
                opinion_fetcher = OpinionFetcher(proxy_url=proxy_url)
                
                # Get the newly saved data with IDs
                all_today_data = storage_manager.get_today_all_data(crawl_date)
                if all_today_data:
                    # Collect a few top trending items across platforms
                    top_items = []
                    for source_id, items in all_today_data.items.items():
                        top_items.extend(items[:2]) # Top 2 from each source
                    
                    # Limit to total 10 searches to be safe
                    for item in top_items[:10]:
                        # Use title as search query
                        # Extracting news_item_id - we need to query it from DB since items in all_today_data might not have ID
                        # but wait, get_today_all_data does include ID in our revised local.py
                        
                        # Find the DB ID for this item (title + platform)
                        # Actually, better to just modify get_today_all_data to return IDs if it doesn't.
                        # (I checked: it does return ID in the row mapping)
                        
                        news_item_id = getattr(item, 'id', None)
                        if not news_item_id:
                            continue
                            
                        logger.info(f"Fetching opinions for: {item.title[:50]}...")
                        reddit_opinions = opinion_fetcher.fetch_reddit_opinions(item.title, limit=5)
                        
                        if reddit_opinions:
                            # Analyze sentiment for each
                            for op in reddit_opinions:
                                sentiment = opinion_fetcher.analyze_sentiment(op['text'])
                                op.update(sentiment)
                                
                            # Save and link
                            op_ids = storage_manager.save_opinions(reddit_opinions, crawl_date)
                            for op_id in op_ids:
                                storage_manager.link_opinion_to_news(news_item_id, op_id, match_type='title_search', date=crawl_date)
                            
                            # Aggregate sentiment for summary
                            avg_score = sum(o['score'] for o in reddit_opinions) / len(reddit_opinions)
                            overall = "positive" if avg_score > 0.1 else "negative" if avg_score < -0.1 else "neutral"
                            
                            storage_manager.save_sentiment_summary({
                                "news_item_id": news_item_id,
                                "topic": item.title[:100],
                                "overall_sentiment": overall,
                                "average_score": avg_score,
                                "opinion_count": len(reddit_opinions),
                                "summary_text": f"Found {len(reddit_opinions)} reactions on Reddit. Average sentiment: {overall}."
                            }, crawl_date)
                
                # 5. Generate Hourly Summary
                logger.info("Generating hourly summary...")
                summary = summary_gen.generate_hourly_summary(crawl_date, crawl_time)
                if summary:
                    storage_manager.save_hourly_summary(summary, crawl_date)
                    logger.info(f"Summary generated: {len(summary.get('highlights', []))} highlights.")
                    
                    # Format notification text
                    notification_text = summary_gen.format_notification(summary)
                    try:
                        print("\n" + notification_text + "\n")
                    except UnicodeEncodeError:
                        # Fallback for terminals that don't support emojis/special chars
                        print("\n" + notification_text.encode('ascii', 'ignore').decode('ascii') + "\n")
                    
                    # Send Telegram notification if enabled
                    if config.get("ENABLE_NOTIFICATION", True):
                        logger.info("Sending Telegram notification...")
                        dispatcher = ctx.create_notification_dispatcher()
                        dispatcher.dispatch_all(
                            report_data={"full_text": notification_text},
                            report_type="Hourly Summary",
                            mode="current"
                        )
                        logger.info("Notification dispatch process completed.")
            
            # Optional: Save TXT snapshot for debug/backup
            txt_file = storage_manager.save_txt_snapshot(news_data)
            
            # 6. Prepare Results
            final_results = {
                "status": "success",
                "fetched_count": total_items,
                "sources_count": len(results),
                "failed_sources": failed_ids,
                "timestamp": crawl_time,
                "date": crawl_date,
                "txt_snapshot": txt_file
            }
            return final_results
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
    # Use ensure_ascii=True to avoid UnicodeEncodeError in Windows terminals
    try:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    except Exception:
        print(json.dumps({"status": "error", "message": "Failed to print results due to encoding error"}))
