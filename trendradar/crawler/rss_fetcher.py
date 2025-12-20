# coding=utf-8
"""
RSS Feed Data Fetcher Module

Supports fetching news data from RSS feeds, used for integrating Indian news sources
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import requests


class RSSFetcher:
    """RSS Feed Data Fetcher"""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    def __init__(self, proxy_url: Optional[str] = None):
        """
        Initialize RSS Fetcher

        Args:
            proxy_url: Proxy server URL (optional)
        """
        self.proxy_url = proxy_url

    def fetch_rss(
        self, 
        feed_url: str, 
        source_id: str,
        max_items: int = 50
    ) -> Tuple[Optional[Dict], str]:
        """
        Fetch RSS feed data

        Args:
            feed_url: RSS feed URL
            source_id: Source ID
            max_items: Maximum items to fetch

        Returns:
            (Data Dict, Source ID) tuple. Data is None on failure.
        """
        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        try:
            response = requests.get(
                feed_url,
                proxies=proxies,
                headers=self.DEFAULT_HEADERS,
                timeout=15,
            )
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            # Support standard RSS 2.0 and Atom formats
            items = []
            
            # Try RSS 2.0 format
            for item in root.findall('.//item')[:max_items]:
                title_elem = item.find('title')
                link_elem = item.find('link')
                
                if title_elem is not None and title_elem.text:
                    title = title_elem.text.strip()
                    url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                    
                    items.append({
                        "title": title,
                        "url": url,
                        "mobileUrl": url,  # RSS usually doesn't have separate mobile links
                    })

            # If no items found, try Atom format
            if not items:
                for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry')[:max_items]:
                    title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
                    link_elem = entry.find('{http://www.w3.org/2005/Atom}link')
                    
                    if title_elem is not None and title_elem.text:
                        title = title_elem.text.strip()
                        url = link_elem.get('href', '') if link_elem is not None else ""
                        
                        items.append({
                            "title": title,
                            "url": url,
                            "mobileUrl": url,
                        })

            if not items:
                print(f"Warning: No valid items found in RSS feed for {source_id}")
                return None, source_id

            # Convert to TrendRadar format
            result = {}
            for index, item in enumerate(items, 1):
                title = item["title"]
                if title in result:
                    result[title]["ranks"].append(index)
                else:
                    result[title] = {
                        "ranks": [index],
                        "url": item["url"],
                        "mobileUrl": item["mobileUrl"],
                    }

            print(f"Fetched {source_id} successfully (RSS feed, {len(items)} items)")
            return result, source_id

        except ET.ParseError as e:
            print(f"Failed to parse RSS feed for {source_id}: {e}")
            return None, source_id
        except Exception as e:
            print(f"Failed to fetch RSS feed for {source_id}: {e}")
            return None, source_id

    def crawl_rss_feeds(
        self,
        feeds: List[Tuple[str, str, str]],  # (feed_url, source_id, source_name)
    ) -> Tuple[Dict, Dict, List]:
        """
        Batch fetch multiple RSS feeds

        Args:
            feeds: List of RSS feeds, each element is (feed_url, source_id, source_name)

        Returns:
            (Results Dict, ID to Name Map, Failed IDs List) tuple
        """
        results = {}
        id_to_name = {}
        failed_ids = []

        for feed_url, source_id, source_name in feeds:
            id_to_name[source_id] = source_name
            
            data, _ = self.fetch_rss(feed_url, source_id)
            
            if data:
                results[source_id] = data
            else:
                failed_ids.append(source_id)

        print(f"RSS Success: {list(results.keys())}, Failed: {failed_ids}")
        return results, id_to_name, failed_ids
