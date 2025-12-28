"""
TrendRadar MCP Server - FastMCP 2.0 Implementation

Provides a production-grade MCP tool server using FastMCP 2.0.
Supports both stdio and HTTP transport modes in English.
"""

import json
from typing import List, Optional, Dict

from fastmcp import FastMCP

from .tools.data_query import DataQueryTools
from .tools.analytics import AnalyticsTools
from .tools.search_tools import SearchTools
from .tools.config_mgmt import ConfigManagementTools
from .tools.system import SystemManagementTools
from .tools.storage_sync import StorageSyncTools
from .utils.date_parser import DateParser
from .utils.errors import MCPError


# Create FastMCP 2.0 application
mcp = FastMCP('trendradar-news')

# Global tool instances (initialized on first request)
_tools_instances = {}


def _get_tools(project_root: Optional[str] = None):
    """Get or create tool instances (Singleton)"""
    if not _tools_instances:
        _tools_instances['data'] = DataQueryTools(project_root)
        _tools_instances['analytics'] = AnalyticsTools(project_root)
        _tools_instances['search'] = SearchTools(project_root)
        _tools_instances['config'] = ConfigManagementTools(project_root)
        _tools_instances['system'] = SystemManagementTools(project_root)
        _tools_instances['storage'] = StorageSyncTools(project_root)
    return _tools_instances


# ==================== Date Parsing Tools ====================

@mcp.tool
async def resolve_date_range(
    expression: str
) -> str:
    """
    [Recommended] Resolve natural language date expressions to standard date ranges

    **Why use this tool?**
    Users often use natural language like "this week" or "last 7 days". AI models might
    calculate these inconsistently. This tool uses the precise server-side current time
    to ensure all AI models get a consistent date range.

    Args:
        expression: Natural language date expression, supports:
            - Single day: "today", "yesterday"
            - Week: "this week", "last week"
            - Month: "this month", "last month"
            - Last N days: "last 7 days", "last 30 days"
            - Dynamic: "last 5 days", "last 10 days" (any number of days)

    Returns:
        JSON date range object
    """
    try:
        result = DateParser.resolve_date_range_expression(expression)
        return json.dumps(result, indent=2)
    except MCPError as e:
        return json.dumps({
            "success": False,
            "error": e.to_dict()
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        }, indent=2)


# ==================== Data Query Tools ====================

@mcp.tool
async def get_latest_news(
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Get the latest batch of crawled news data

    Args:
        platforms: List of platform IDs, e.g., ['zhihu', 'weibo', 'douyin']
        limit: Return count limit, default 50
        include_url: Whether to include URL links, default False
    """
    tools = _get_tools()
    result = tools['data'].get_latest_news(platforms=platforms, limit=limit, include_url=include_url)
    return json.dumps(result, indent=2)


@mcp.tool
async def get_trending_topics(
    top_n: int = 10,
    mode: str = 'current'
) -> str:
    """
    Get frequency statistics of news for watched keywords (based on config/frequency_words.txt)

    Args:
        top_n: Return top N watched words, default 10
        mode: daily or current (latest batch)
    """
    tools = _get_tools()
    result = tools['data'].get_trending_topics(top_n=top_n, mode=mode)
    return json.dumps(result, indent=2)


@mcp.tool
async def get_news_by_date(
    date_query: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Get news data for a specific date (supports natural language)

    Args:
        date_query: Date query e.g. "yesterday", "2024-10-10"
        platforms: List of platform IDs
        limit: Return count limit
        include_url: Whether to include URL links
    """
    tools = _get_tools()
    result = tools['data'].get_news_by_date(
        date_query=date_query,
        platforms=platforms,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, indent=2)


# ==================== Advanced Data Analysis Tools ====================

@mcp.tool
async def analyze_topic_trend(
    topic: str,
    analysis_type: str = "trend",
    date_range: Optional[Dict[str, str]] = None,
    granularity: str = "day",
    threshold: float = 3.0,
    time_window: int = 24,
    lookahead_hours: int = 6,
    confidence_threshold: float = 0.7
) -> str:
    """
    Unified Topic Trend Analysis Tool

    Args:
        topic: Topic keyword (required)
        analysis_type: trend, lifecycle, viral, or predict
        date_range: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        granularity: day (default)
        threshold: Growth multiplier for viral detection
        time_window: Window in hours
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_topic_trend_unified(
        topic=topic,
        analysis_type=analysis_type,
        date_range=date_range,
        granularity=granularity,
        threshold=threshold,
        time_window=time_window,
        lookahead_hours=lookahead_hours,
        confidence_threshold=confidence_threshold
    )
    return json.dumps(result, indent=2)


@mcp.tool
async def analyze_data_insights(
    insight_type: str = "platform_compare",
    topic: Optional[str] = None,
    date_range: Optional[Dict[str, str]] = None,
    min_frequency: int = 3,
    top_n: int = 20
) -> str:
    """
    Unified Data Insight Analysis Tool

    Args:
        insight_type: platform_compare, platform_activity, keyword_cooccur
        topic: Topic keyword (optional)
        date_range: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        min_frequency: Min count for co-occurrence mode
        top_n: Max results
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_data_insights_unified(
        insight_type=insight_type,
        topic=topic,
        date_range=date_range,
        min_frequency=min_frequency,
        top_n=top_n
    )
    return json.dumps(result, indent=2)


@mcp.tool
async def analyze_sentiment(
    topic: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    date_range: Optional[Dict[str, str]] = None,
    limit: int = 50,
    sort_by_weight: bool = True,
    include_url: bool = False
) -> str:
    """
    Analyze sentiment and hot trends of news
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_sentiment(
        topic=topic,
        platforms=platforms,
        date_range=date_range,
        limit=limit,
        sort_by_weight=sort_by_weight,
        include_url=include_url
    )
    return json.dumps(result, indent=2)


@mcp.tool
async def find_similar_news(
    reference_title: str,
    threshold: float = 0.6,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """Find other news similar to a specific title"""
    tools = _get_tools()
    result = tools['analytics'].find_similar_news(
        reference_title=reference_title,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, indent=2)


@mcp.tool
async def generate_summary_report(
    report_type: str = "daily",
    date_range: Optional[Dict[str, str]] = None
) -> str:
    """Daily/Weekly Summary Generator"""
    tools = _get_tools()
    result = tools['analytics'].generate_summary_report(
        report_type=report_type,
        date_range=date_range
    )
    return json.dumps(result, indent=2)


# ==================== Intelligent Retrieval Tools ====================

@mcp.tool
async def search_news(
    query: str,
    search_mode: str = "keyword",
    date_range: Optional[Dict[str, str]] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    sort_by: str = "relevance",
    threshold: float = 0.6,
    include_url: bool = False
) -> str:
    """
    Unified Search Interface

    Args:
        query: Search query
        search_mode: keyword, fuzzy, entity
        date_range: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        platforms: List of platform IDs
        limit: Max results
    """
    tools = _get_tools()
    result = tools['search'].search_news_unified(
        query=query,
        search_mode=search_mode,
        date_range=date_range,
        platforms=platforms,
        limit=limit,
        sort_by=sort_by,
        threshold=threshold,
        include_url=include_url
    )
    return json.dumps(result, indent=2)


@mcp.tool
async def search_related_news_history(
    reference_text: str,
    time_preset: str = "yesterday",
    threshold: float = 0.4,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """Search historical news related to a seed news item"""
    tools = _get_tools()
    result = tools['search'].search_related_news_history(
        reference_text=reference_text,
        time_preset=time_preset,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, indent=2)


# ==================== Config & System Management Tools ====================

@mcp.tool
async def get_current_config(
    section: str = "all"
) -> str:
    """Get current system configuration"""
    tools = _get_tools()
    result = tools['config'].get_current_config(section=section)
    return json.dumps(result, indent=2)


@mcp.tool
async def get_system_status() -> str:
    """Get system running status and health info"""
    tools = _get_tools()
    result = tools['system'].get_system_status()
    return json.dumps(result, indent=2)


@mcp.tool
async def trigger_crawl(
    platforms: Optional[List[str]] = None,
    save_to_local: bool = False,
    include_url: bool = False
) -> str:
    """Manually trigger a crawl task"""
    tools = _get_tools()
    result = tools['system'].trigger_crawl(platforms=platforms, save_to_local=save_to_local, include_url=include_url)
    return json.dumps(result, indent=2)


# ==================== Storage Sync Tools ====================

@mcp.tool
async def sync_from_remote(
    days: int = 7
) -> str:
    """Sync news data from remote storage (e.g. R2/S3)"""
    tools = _get_tools()
    result = tools['storage'].sync_from_remote(days=days)
    return json.dumps(result, indent=2)


@mcp.tool
async def get_storage_status() -> str:
    """Get storage configuration and status"""
    tools = _get_tools()
    result = tools['storage'].get_storage_status()
    return json.dumps(result, indent=2)


@mcp.tool
async def list_available_dates(
    source: str = "both"
) -> str:
    """List available dates in local/remote storage"""
    tools = _get_tools()
    result = tools['storage'].list_available_dates(source=source)
    return json.dumps(result, indent=2)


# ==================== Server Runner ====================

def run_server(
    project_root: Optional[str] = None,
    transport: str = 'stdio',
    host: str = '0.0.0.0',
    port: int = 3333
):
    """Run the MCP Server"""
    _get_tools(project_root)

    print()
    print("=" * 60)
    print("  TrendRadar MCP Server - FastMCP 2.0 (English Localized)")
    print("=" * 60)
    print(f"  Transport: {transport.upper()}")
    if transport == 'http':
        print(f"  Endpoint: http://{host}:{port}/mcp")
    print(f"  Project Root: {project_root or 'Current Directory'}")
    print()
    print("  Registered Tools: (Use --help or ask AI for details)")
    print("  - resolve_date_range")
    print("  - get_latest_news")
    print("  - get_trending_topics")
    print("  - get_news_by_date")
    print("  - search_news")
    print("  - analyze_topic_trend")
    print("  - analyze_data_insights")
    print("  - analyze_sentiment")
    print("  - find_similar_news")
    print("  - generate_summary_report")
    print("  - trigger_crawl")
    print("  - sync_from_remote")
    print("  - storage_status/available_dates")
    print("=" * 60)
    print()

    if transport == 'stdio':
        mcp.run(transport='stdio')
    elif transport == 'http':
        mcp.run(transport='http', host=host, port=port, path='/mcp')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='TrendRadar MCP Server')
    parser.add_argument('transport_pos', nargs='?', choices=['stdio', 'http'])
    parser.add_argument('--transport', choices=['stdio', 'http'])
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=3333)
    parser.add_argument('--project-root')
    args = parser.parse_args()
    transport = args.transport or args.transport_pos or 'stdio'
    run_server(project_root=args.project_root, transport=transport, host=args.host, port=args.port)
