#!/usr/bin/env python3
"""
Send Notifications - Read from database and send notifications without crawling

This script reads the latest data from the database and sends notifications
(hourly or daily summaries) based on the current time.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict

# Add project root to path
sys.path.append(os.getcwd())

from trendradar.core import load_config
from trendradar.context import AppContext
from trendradar.core.summary import SummaryGenerator
from trendradar.storage import get_storage_manager

# Configure logging to stderr so stdout is clean for JSON
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

def send_notifications() -> Dict:
    """
    Read latest data from database and send notifications.
    Returns a dict with execution results.
    """
    try:
        # 1. Initialize Context
        config = load_config()
        ctx = AppContext(config)

        crawl_date = ctx.format_date()
        crawl_time = ctx.format_time()

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
            force_new=False
        )

        # Check if there's data to work with
        existing_data = storage_manager.get_today_all_data(crawl_date)
        if not existing_data:
            logger.warning("No data found in database for today")
            return {
                "status": "no_data",
                "message": "No news data found in database for today"
            }

        # 2. Generate Summary (Hourly or Daily)
        summary_gen = SummaryGenerator(storage_manager)
        current_hour = int(crawl_time.split('-')[0])

        if current_hour >= 23:  # End of day (11 PM or later)
            logger.info("Generating daily summary (end of day)...")
            summary = summary_gen.generate_daily_summary(crawl_date)
            report_type = "Daily Summary"
        else:
            logger.info("Generating hourly summary...")
            summary = summary_gen.generate_hourly_summary(crawl_date, crawl_time)
            report_type = "Hourly Summary"

        if not summary:
            logger.warning("No summary could be generated")
            return {
                "status": "no_summary",
                "message": "Could not generate summary from existing data"
            }

        # Save summary to database
        storage_manager.save_hourly_summary(summary, crawl_date)
        logger.info(f"Summary generated: {len(summary.get('highlights', []))} highlights.")

        # Format notification text based on type
        if current_hour >= 23:
            notification_text = summary_gen.format_daily_notification(summary)
        else:
            notification_text = summary_gen.format_notification(summary)

        try:
            print("\n" + notification_text + "\n")
        except UnicodeEncodeError:
            # Fallback for terminals that don't support emojis/special chars
            print("\n" + notification_text.encode('ascii', 'ignore').decode('ascii') + "\n")

        # Send notification
        if config.get("ENABLE_NOTIFICATION", True):
            logger.info(f"Sending {report_type} notification...")
            dispatcher = ctx.create_notification_dispatcher()
            dispatcher.dispatch_all(
                report_data={"full_text": notification_text},
                report_type=report_type,
                mode="current"
            )
            logger.info("Notification dispatch process completed.")
        else:
            logger.info("Notifications disabled in config")

        return {
            "status": "success",
            "report_type": report_type,
            "highlights_count": len(summary.get('highlights', [])),
            "timestamp": crawl_time,
            "date": crawl_date
        }

    except Exception as e:
        logger.error(f"Error sending notifications: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

def main():
    """Main entry point"""
    result = send_notifications()
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()