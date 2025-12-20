# coding=utf-8
"""
Data Fetcher Module

Responsible for fetching news data from NewsNow API, supporting:
- Single platform data fetching
- Batch platform data crawling
- Automatic retry mechanism
- Proxy support
"""

import json
import random
import time
from typing import Dict, List, Tuple, Optional, Union

import requests


class DataFetcher:
    """Data Fetcher"""

    # Default API URL
    DEFAULT_API_URL = "https://newsnow.busiyi.world/api/s"

    # Default Headers
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """
        Initialize Data Fetcher

        Args:
            proxy_url: Proxy server URL (optional)
            api_url: API base URL (optional, defaults to DEFAULT_API_URL)
        """
        self.proxy_url = proxy_url
        self.api_url = api_url or self.DEFAULT_API_URL

    def fetch_data(
        self,
        id_info: Union[str, Tuple[str, str]],
        max_retries: int = 2,
        min_retry_wait: int = 3,
        max_retry_wait: int = 5,
    ) -> Tuple[Optional[str], str, str]:
        """
        Fetch data for specified ID with retry support

        Args:
            id_info: Platform ID or (Platform ID, Alias) tuple
            max_retries: Maximum number of retries
            min_retry_wait: Minimum retry wait time (seconds)
            max_retry_wait: Maximum retry wait time (seconds)

        Returns:
            (response_text, platform_id, alias) tuple. response_text is None on failure.
        """
        if isinstance(id_info, tuple):
            id_value, alias = id_info
        else:
            id_value = id_info
            alias = id_value

        url = f"{self.api_url}?id={id_value}&latest"

        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        retries = 0
        while retries <= max_retries:
            try:
                response = requests.get(
                    url,
                    proxies=proxies,
                    headers=self.DEFAULT_HEADERS,
                    timeout=10,
                )
                response.raise_for_status()

                data_text = response.text
                data_json = json.loads(data_text)

                status = data_json.get("status", "unknown")
                if status not in ["success", "cache"]:
                    raise ValueError(f"Abnormal response status: {status}")

                status_info = "Latest" if status == "success" else "Cached"
                print(f"Fetched {id_value} successfully ({status_info})")
                return data_text, id_value, alias

            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    base_wait = random.uniform(min_retry_wait, max_retry_wait)
                    additional_wait = (retries - 1) * random.uniform(1, 2)
                    wait_time = base_wait + additional_wait
                    print(f"Request {id_value} failed: {e}. Retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    print(f"Request {id_value} failed: {e}")
                    return None, id_value, alias

        return None, id_value, alias

    def crawl_websites(
        self,
        ids_list: List[Union[str, Tuple[str, str]]],
        request_interval: int = 100,
    ) -> Tuple[Dict, Dict, List]:
        """
        Crawl data from multiple websites

        Args:
            ids_list: List of platform IDs, each element can be a string or (Platform ID, Alias) tuple
            request_interval: Request interval (milliseconds)

        Returns:
            (results_dict, id_to_name_map, failed_ids_list) tuple
        """
        results = {}
        id_to_name = {}
        failed_ids = []

        for i, id_info in enumerate(ids_list):
            if isinstance(id_info, tuple):
                id_value, name = id_info
            else:
                id_value = id_info
                name = id_value

            id_to_name[id_value] = name
            response, _, _ = self.fetch_data(id_info)

            if response:
                try:
                    data = json.loads(response)
                    results[id_value] = {}

                    for index, item in enumerate(data.get("items", []), 1):
                        title = item.get("title")
                        # Skip invalid titles (None, float, empty string)
                        if title is None or isinstance(title, float) or not str(title).strip():
                            continue
                        title = str(title).strip()
                        url = item.get("url", "")
                        mobile_url = item.get("mobileUrl", "")

                        if title in results[id_value]:
                            results[id_value][title]["ranks"].append(index)
                        else:
                            results[id_value][title] = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": mobile_url,
                            }
                except json.JSONDecodeError:
                    print(f"Failed to parse response for {id_value}")
                    failed_ids.append(id_value)
                except Exception as e:
                    print(f"Error processing data for {id_value}: {e}")
                    failed_ids.append(id_value)
            else:
                failed_ids.append(id_value)

            # Request interval (except for the last one)
            if i < len(ids_list) - 1:
                actual_interval = request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)

        print(f"Success: {list(results.keys())}, Failed: {failed_ids}")
        return results, id_to_name, failed_ids
