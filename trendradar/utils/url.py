# coding=utf-8
"""
URL Processing Utility Module

Provides URL normalization functionality to eliminate the influence of dynamic parameters during deduplication:
- normalize_url: Normalize URL by removing dynamic parameters
"""

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Dict, Set


# Specific parameters to be removed for each platform
#   - weibo: Has band_rank (ranking) and Refer (source) dynamic parameters
#   - other platforms: URL is in path format or simple keyword query, no processing needed
PLATFORM_PARAMS_TO_REMOVE: Dict[str, Set[str]] = {
    # Weibo: band_rank is a dynamic ranking parameter, Refer is a source parameter, t is a time range parameter
    # Example: https://s.weibo.com/weibo?q=xxx&t=31&band_rank=1&Refer=top
    # Keep: q (keyword)
    # Remove: band_rank, Refer, t
    "weibo": {"band_rank", "Refer", "t"},
}

# Common tracking parameters (applicable to all platforms)
# These parameters are usually added by share links or ad tracking and do not affect content identification
COMMON_TRACKING_PARAMS: Set[str] = {
    # UTM tracking parameters
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    # Common tracking parameters
    "ref", "referrer", "source", "channel",
    # Timestamp and random parameters
    "_t", "timestamp", "_", "random",
    # Share related
    "share_token", "share_id", "share_from",
}


def normalize_url(url: str, platform_id: str = "") -> str:
    """
    Normalize URL by removing dynamic parameters

    Used for database deduplication, ensuring that different URL variants of the same news item can be correctly identified as the same item.

    Processing rules:
    1. Remove platform-specific dynamic parameters (like Weibo's band_rank)
    2. Remove common tracking parameters (like utm_*)
    3. Keep core query parameters (like search keywords q=, wd=, keyword=)
    4. Sort query parameters alphabetically (to ensure consistency)

    Args:
        url: Original URL
        platform_id: Platform ID, used to apply platform-specific rules

    Returns:
        Normalized URL

    Examples:
        >>> normalize_url("https://s.weibo.com/weibo?q=test&band_rank=6&Refer=top", "weibo")
        'https://s.weibo.com/weibo?q=test'

        >>> normalize_url("https://example.com/page?id=1&utm_source=twitter", "")
        'https://example.com/page?id=1'
    """
    if not url:
        return url

    try:
        # Parse URL
        parsed = urlparse(url)

        # If no query parameters, return directly
        if not parsed.query:
            return url

        # Parse query parameters
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Collect parameters to be removed (using lowercase for comparison)
        params_to_remove: Set[str] = set()

        # Add common tracking parameters
        params_to_remove.update(COMMON_TRACKING_PARAMS)

        # Add platform-specific parameters
        if platform_id and platform_id in PLATFORM_PARAMS_TO_REMOVE:
            params_to_remove.update(PLATFORM_PARAMS_TO_REMOVE[platform_id])

        # Filter parameters (key converted to lowercase for comparison)
        filtered_params = {
            key: values
            # Values may contain multiple items for the same key, but we treat them as one for filtering
            for key, values in params.items()
            if key.lower() not in {p.lower() for p in params_to_remove}
        }

        # If no parameters left after filtering, return URL without query string
        if not filtered_params:
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                "",  # Empty query string
                ""   # Remove fragment
            ))

        # Reconstruct query string (sort by alphabet to ensure consistency)
        sorted_params = []
        for key in sorted(filtered_params.keys()):
            for value in filtered_params[key]:
                sorted_params.append((key, value))

        new_query = urlencode(sorted_params)

        # Reconstruct URL (remove fragment)
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ""  # Remove fragment
        ))

        return normalized

    except Exception:
        # Return original URL on parsing failure
        return url


def get_url_signature(url: str, platform_id: str = "") -> str:
    """
    Get signature of the URL (used for quick comparison)

    Generates signature based on normalized URL, can be used for:
    - Quickly determining if two URLs point to the same content
    - As a cache key

    Args:
        url: Original URL
        platform_id: Platform ID

    Returns:
        URL signature string
    """
    return normalize_url(url, platform_id)
