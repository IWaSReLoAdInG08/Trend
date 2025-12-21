# coding=utf-8
import requests
import time
import logging
from typing import List, Dict, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

class OpinionFetcher:
    """Fetcher for public opinions from platforms like Reddit."""
    
    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def fetch_reddit_opinions(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Fetch opinions from Reddit based on a search query.
        Uses Reddit's .json search endpoint.
        """
        if not query:
            return []
            
        encoded_query = quote(query)
        # Search across all subreddits, sort by relevance
        url = f"https://www.reddit.com/search.json?q={encoded_query}&limit={limit}&sort=relevance"
        
        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}
            
        try:
            logger.info(f"Searching Reddit for: {query}")
            response = requests.get(url, headers=self.headers, proxies=proxies, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            results = []
            children = data.get('data', {}).get('children', [])
            for post in children:
                post_data = post.get('data', {})
                text = post_data.get('title', '')
                if post_data.get('selftext'):
                    text += "\n" + post_data.get('selftext')
                
                results.append({
                    "text": text,
                    "source": "reddit",
                    "author": post_data.get('author'),
                    "upvotes": post_data.get('ups', 0),
                    "original_url": f"https://www.reddit.com{post_data.get('permalink', '')}",
                    "pub_time": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(post_data.get('created_utc', 0)))
                })
            
            logger.info(f"Found {len(results)} Reddit opinions for '{query}'")
            return results
        except Exception as e:
            logger.error(f"Failed to fetch Reddit opinions for '{query}': {e}")
            return []

    def analyze_sentiment(self, text: str) -> Dict:
        """
        Simple rule-based sentiment analysis.
        """
        positive_words = ['good', 'great', 'excellent', 'happy', 'success', 'amazing', 'win', 'positive', 'improved', 'bullish', 'buy']
        negative_words = ['bad', 'poor', 'failure', 'sad', 'terrible', 'worst', 'negative', 'loss', 'decline', 'scam', 'fraud', 'bearish', 'sell']
        
        text_lower = text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        if pos_count > neg_count:
            return {"sentiment": "positive", "score": min(1.0, 0.1 * (pos_count - neg_count))}
        elif neg_count > pos_count:
            return {"sentiment": "negative", "score": max(-1.0, -0.1 * (neg_count - pos_count))}
        else:
            return {"sentiment": "neutral", "score": 0.0}
