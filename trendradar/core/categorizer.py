import json
import re
from typing import List, Dict
from trendradar.core.categories import CATEGORIES

class NewsCategorizer:
    """
    Categorizes news articles based on keywords in title and summary.
    """
    
    def __init__(self):
        self.category_map = CATEGORIES
        
    def categorize(self, title: str, summary: str = "") -> List[str]:
        """
        Categorize an article based on title and summary content.
        
        Args:
            title: Article title
            summary: Article summary or snippet
            
        Returns:
            List of matching category names
        }
        """
        text = f"{title} {summary}".lower()
        matched_categories = []
        
        for category, config in self.category_map.items():
            keywords = config.get("keywords", [])
            for keyword in keywords:
                # Use word boundary search for more accuracy
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                if re.search(pattern, text):
                    matched_categories.append(category)
                    break # Found a match for this category, move to next
                    
        return matched_categories

    def categorize_to_json(self, title: str, summary: str = "") -> str:
        """Helper to return categories as a JSON string for DB storage."""
        return json.dumps(self.categorize(title, summary))
