
import os
import sys
import json
import logging
import argparse
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

def fetch_data(send_notifications: bool = True) -> Dict:
    """
    Fetch news data from configured sources (RSS) and save to DB.
    Returns a dict with execution results.
    """
    try:
        # 1. Initialize Context
        config = load_config()
        ctx = AppContext(config)
        
        crawl_date = ctx.format_date()
        
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
            force_new=False  # Don't force new, allow caching
        )
        
        # Check if data was fetched recently (within 1 hour) by checking crawl times
        crawl_times = storage_manager.get_crawl_times(crawl_date)
        if crawl_times:
            latest_crawl = crawl_times[-1]  # Most recent crawl time
            current_time = ctx.format_time()
            
            try:
                # Parse times like "14-30" (HH-MM)
                latest_hour, latest_minute = map(int, latest_crawl.split('-'))
                current_hour, current_minute = map(int, current_time.split('-'))
                
                time_diff = (current_hour - latest_hour) * 60 + (current_minute - latest_minute)
                
                if time_diff < 60:  # Less than 1 hour ago
                    logger.info(f"Data already fetched recently at {latest_crawl}, skipping fetch")
                    return {
                        "status": "skipped",
                        "message": f"Data already up to date (last crawl: {latest_crawl})",
                        "last_crawl": latest_crawl
                    }
            except Exception as e:
                logger.warning(f"Time parsing failed: {e}, continuing with fetch")
        
        logger.info("No recent crawl found or time check failed, proceeding with RSS feed fetching...")
        
        # Only proceed with fetching if we don't have recent data
        logger.info("Proceeding with RSS feed fetching...")
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
                
                # 5. Generate Summary (Hourly or Daily)
                current_hour = int(crawl_time.split('-')[0])
                if current_hour >= 23:  # End of day (11 PM or later)
                    logger.info("Generating daily summary (end of day)...")
                    summary = summary_gen.generate_daily_summary(crawl_date)
                    report_type = "Daily Summary"
                else:
                    logger.info("Generating hourly summary...")
                    summary = summary_gen.generate_hourly_summary(crawl_date, crawl_time)
                    report_type = "Hourly Summary"
                
                if summary:
                    # Save summary (both hourly and daily use the same table)
                    storage_manager.save_hourly_summary(summary, crawl_date)
                    logger.info(f"Summary generated: {len(summary.get('highlights', []))} highlights.")
                    
                    # Format notification text based on type
                    if current_hour >= 23:
                        notification_text = summary_gen.format_daily_notification(summary)
                        report_type = "Daily Summary"
                    else:
                        notification_text = summary_gen.format_notification(summary)
                        report_type = "Hourly Summary"
                    
                    try:
                        print("\n" + notification_text + "\n")
                    except UnicodeEncodeError:
                        # Fallback for terminals that don't support emojis/special chars
                        print("\n" + notification_text.encode('ascii', 'ignore').decode('ascii') + "\n")
                    
                    # Send notification (only if requested)
                    if send_notifications and config.get("ENABLE_NOTIFICATION", True):
                        logger.info(f"Sending {report_type} notification...")
                        dispatcher = ctx.create_notification_dispatcher()
                        dispatcher.dispatch_all(
                            report_data={"full_text": notification_text},
                            report_type=report_type,
                            mode="current"
                        )
                        logger.info("Notification dispatch process completed.")
                    elif not send_notifications:
                        logger.info("Skipping notifications (fetch-only mode)")
                    else:
                        logger.info("Notifications disabled in config")
            
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

def main():
    """Main entry point with command line argument parsing"""
    parser = argparse.ArgumentParser(description='Fetch news data and optionally send notifications')
    parser.add_argument('--no-notify', action='store_true',
                       help='Skip sending notifications (fetch-only mode)')
    parser.add_argument('--notify-only', action='store_true',
                       help='Only send notifications from existing data (no fetching)')

    args = parser.parse_args()

    if args.notify_only:
        # Import and run the notification script
        from send_notifications import send_notifications
        result = send_notifications()
    else:
        # Normal fetch mode (with optional notification skipping)
        send_notifications_flag = not args.no_notify
        result = fetch_data(send_notifications=send_notifications_flag)

    # Print JSON result to stdout for parsing by external tools/caller
    # Use ensure_ascii=True to avoid UnicodeEncodeError in Windows terminals
    try:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    except Exception:
        print(json.dumps({"status": "error", "message": "Failed to print results due to encoding error"}))

if __name__ == "__main__":
    main()
