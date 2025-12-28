import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from trendradar.storage.base import NewsData, NewsItem

class SummaryGenerator:
    """
    Generates concise summaries and highlights from NewsData.
    """
    
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        
    def generate_hourly_summary(self, date: str, current_time: str) -> Dict[str, Any]:
        """
        Generate high-level summary for the last hour.
        
        Args:
            date: Current date
            current_time: Current crawl time
            
        Returns:
            Dict containing highlights, top categories, and metadata.
        """
        # 1. Get all data for today to find recent items
        data = self.storage_manager.get_today_all_data(date)
        if not data:
            return {}
            
        # 2. Filter items from the last hour (roughly)
        # Assuming current_time is HH:MM
        try:
            now_dt = datetime.strptime(current_time, "%H-%M")
            hour_ago_dt = now_dt - timedelta(hours=1)
            hour_ago_str = hour_ago_dt.strftime("%H-%M")
        except:
            hour_ago_str = "00-00" # Fallback
            
        recent_items: List[NewsItem] = []
        category_counts: Dict[str, int] = {}
        
        for source_id, items in data.items.items():
            for item in items:
                # Basic check: item.last_time is the crawl time
                if item.last_time >= hour_ago_str:
                    recent_items.append(item)
                    for cat in item.categories:
                        category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # 3. Sort by rank and filter unique titles (rudimentary deduplication)
        recent_items.sort(key=lambda x: x.rank)
        
        final_highlights = []
        seen_titles = set()
        for item in recent_items:
            # Simple title cleaning for comparison
            short_title = item.title[:30].lower()
            if short_title not in seen_titles:
                final_highlights.append(item.title)
                seen_titles.add(short_title)
            if len(final_highlights) >= 5: # Top 5 highlights
                break
                
        # 4. Get top 3 categories
        sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        top_cats = [c[0] for c in sorted_cats[:3]]
        
        return {
            "time_window": f"{hour_ago_str} to {current_time}",
            "date": date,
            "highlights": final_highlights,
            "top_categories": top_cats,
            "item_count": len(recent_items)
        }

    def format_notification(self, summary: Dict[str, Any]) -> str:
        """Format summary into a user-friendly notification message."""
        if not summary:
            return "No news updates found for the last hour."
            
        msg = f"🔔 **Hourly News Update ({summary['time_window']})**\n"
        for h in summary['highlights']:
            msg += f"• {h}\n"
        
        if summary['top_categories']:
            msg += f"\n🔍 Trending: {', '.join(summary['top_categories'])}"
            
        return msg

    def generate_daily_summary(self, date: str) -> Dict[str, Any]:
        """
        Generate high-level summary for the entire day.
        
        Args:
            date: Current date
            
        Returns:
            Dict containing highlights, top categories, and metadata.
        """
        # 1. Get all data for today
        data = self.storage_manager.get_today_all_data(date)
        if not data:
            return {}
            
        # 2. Collect all items from the day
        all_items: List[NewsItem] = []
        category_counts: Dict[str, int] = {}
        
        for source_id, items in data.items.items():
            for item in items:
                all_items.append(item)
                for cat in item.categories:
                    category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # 3. Sort by rank and filter unique titles
        all_items.sort(key=lambda x: x.rank)
        
        final_highlights = []
        seen_titles = set()
        for item in all_items:
            # Simple title cleaning for comparison
            short_title = item.title[:30].lower()
            if short_title not in seen_titles:
                final_highlights.append(item.title)
                seen_titles.add(short_title)
            if len(final_highlights) >= 10:  # Top 10 highlights for daily
                break
                
        # 4. Get top 5 categories
        sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        top_cats = [c[0] for c in sorted_cats[:5]]
        
        return {
            "time_window": "10 to 23",  # Assuming business hours 10 AM to 11 PM
            "date": date,
            "highlights": final_highlights,
            "top_categories": top_cats,
            "item_count": len(all_items)
        }

    def format_daily_notification(self, summary: Dict[str, Any]) -> str:
        """Format daily summary into a user-friendly notification message."""
        if not summary:
            return "No news updates found for today."
            
        msg = f"🌅 **Daily News Summary ({summary['time_window']})**\n"
        msg += f"📊 Total articles: {summary['item_count']}\n\n"
        msg += "🔥 Top Stories:\n"
        for i, h in enumerate(summary['highlights'][:5], 1):  # Show top 5
            msg += f"{i}. {h}\n"
        
        if summary['top_categories']:
            msg += f"\n🔍 Trending Topics: {', '.join(summary['top_categories'][:3])}"
            
        return msg
