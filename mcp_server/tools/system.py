"""
System Management Tools

Implements system status query and crawler trigger functions in English.
"""

import re
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import traceback

from ..services.data_service import DataService
from ..utils.validators import validate_platforms, validate_limit
from ..utils.errors import MCPError, CrawlTaskError


class SystemManagementTools:
    """System Management Tools Class"""

    def __init__(self, project_root: str = None):
        """
        Initialize system management tools

        Args:
            project_root: Project root directory
        """
        self.data_service = DataService(project_root)
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Get project root
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent

    def get_system_status(self) -> Dict:
        """
        Get system status and health check info

        Returns:
            System status dictionary

        Example:
            >>> tools = SystemManagementTools()
            >>> result = tools.get_system_status()
            >>> print(result['system']['version'])
        """
        try:
            # Get system status
            status = self.data_service.get_system_status()

            return {
                **status,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def trigger_crawl(self, platforms: Optional[List[str]] = None, save_to_local: bool = False, include_url: bool = False) -> Dict:
        """
        Trigger a manual crawl task

        Args:
            platforms: List of platforms, crawl all if empty
            save_to_local: Whether to save to local output dir, default False
            include_url: Whether to include URL links, default False

        Returns:
            Crawl results dictionary

        Example:
            >>> tools = SystemManagementTools()
            >>> # Temporary crawl, do not save
            >>> result = tools.trigger_crawl(platforms=['zhihu', 'weibo'])
            >>> print(result['data'])
            >>> # Crawl and save to local
            >>> result = tools.trigger_crawl(platforms=['zhihu'], save_to_local=True)
            >>> print(result['saved_files'])
        """
        try:
            from trendradar.crawler.fetcher import DataFetcher
            from trendradar.storage.local import LocalStorageBackend
            from trendradar.storage.base import convert_crawl_results_to_news_data
            from trendradar.utils.time import get_configured_time, format_date_folder, format_time_filename
            from ..services.cache_service import get_cache

            # Validate parameters
            platforms = validate_platforms(platforms)

            # Load configuration
            config_path = self.project_root / "config" / "config.yaml"
            if not config_path.exists():
                raise CrawlTaskError(
                    "Configuration file not found",
                    suggestion=f"Please ensure the config file exists at: {config_path}"
                )

            # Read config
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            # Get platform config
            all_platforms = config_data.get("platforms", [])
            if not all_platforms:
                raise CrawlTaskError(
                    "No platform configuration found in config file",
                    suggestion="Please check the 'platforms' section in config/config.yaml"
                )

            # Filter platforms
            if platforms:
                target_platforms = [p for p in all_platforms if p["id"] in platforms]
                if not target_platforms:
                    raise CrawlTaskError(
                        f"Specified platforms not found: {platforms}",
                        suggestion=f"Available platforms: {[p['id'] for p in all_platforms]}"
                    )
            else:
                target_platforms = all_platforms

            # Build platform ID list
            ids = []
            for platform in target_platforms:
                if "name" in platform:
                    ids.append((platform["id"], platform["name"]))
                else:
                    ids.append(platform["id"])

            print(f"Starting manual crawl for platforms: {[p.get('name', p['id']) for p in target_platforms]}")

            # Initialize fetcher
            crawler_config = config_data.get("crawler", {})
            proxy_url = None
            if crawler_config.get("use_proxy"):
                proxy_url = crawler_config.get("proxy_url")
            
            fetcher = DataFetcher(proxy_url=proxy_url)
            request_interval = crawler_config.get("request_interval", 100)

            # Execute crawl
            results, id_to_name, failed_ids = fetcher.crawl_websites(
                ids_list=ids,
                request_interval=request_interval
            )

            # Get current time
            timezone = config_data.get("app", {}).get("timezone", "Asia/Shanghai")
            current_time = get_configured_time(timezone)
            crawl_date = format_date_folder(None, timezone)
            crawl_time_str = format_time_filename(timezone)

            # Convert to standard data model
            news_data = convert_crawl_results_to_news_data(
                results=results,
                id_to_name=id_to_name,
                failed_ids=failed_ids,
                crawl_time=crawl_time_str,
                crawl_date=crawl_date
            )

            # Initialize storage backend
            storage = LocalStorageBackend(
                data_dir=str(self.project_root / "output"),
                enable_txt=True,
                enable_html=True,
                timezone=timezone
            )

            # Attempt persistence
            save_success = False
            save_error_msg = ""
            saved_files = {}

            try:
                # 1. Save to SQLite
                if storage.save_news_data(news_data):
                    save_success = True
                
                # 2. Save local TXT/HTML snapshots if requested
                if save_to_local:
                    # Save TXT
                    txt_path = storage.save_txt_snapshot(news_data)
                    if txt_path:
                        saved_files["txt"] = txt_path

                    # Save HTML
                    html_content = self._generate_simple_html(results, id_to_name, failed_ids, current_time)
                    html_filename = f"{crawl_time_str}.html"
                    html_path = storage.save_html_report(html_content, html_filename)
                    if html_path:
                        saved_files["html"] = html_path

            except Exception as e:
                # Catch save errors (e.g., Read-only filesystem in Docker)
                print(f"[System] Data persistence failed: {e}")
                save_success = False
                save_error_msg = str(e)

            # 3. Clear cache
            get_cache().clear()
            print("[System] Cache cleared")

            # Build response
            news_response_data = []
            for platform_id, titles_data in results.items():
                platform_name = id_to_name.get(platform_id, platform_id)
                for title, info in titles_data.items():
                    news_item = {
                        "platform_id": platform_id,
                        "platform_name": platform_name,
                        "title": title,
                        "ranks": info.get("ranks", [])
                    }
                    if include_url:
                        news_item["url"] = info.get("url", "")
                        news_item["mobile_url"] = info.get("mobileUrl", "")
                    news_response_data.append(news_item)

            result = {
                "success": True,
                "task_id": f"crawl_{int(time.time())}",
                "status": "completed",
                "crawl_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "platforms": list(results.keys()),
                "total_news": len(news_response_data),
                "failed_platforms": failed_ids,
                "data": news_response_data,
                "saved_to_local": save_success and save_to_local
            }

            if save_success:
                if save_to_local:
                    result["saved_files"] = saved_files
                    result["note"] = "Data saved to SQLite database and output folder"
                else:
                    result["note"] = "Data saved to SQLite database (txt/html snapshots not generated per request)"
            else:
                result["saved_to_local"] = False
                result["save_error"] = save_error_msg
                if "Read-only file system" in save_error_msg or "Permission denied" in save_error_msg:
                    result["note"] = "Crawl successful, but database write failed (Read-only mode). Data is temporary."
                else:
                    result["note"] = f"Crawl successful but persistence failed: {save_error_msg}"

            # Cleanup
            storage.cleanup()

            return result

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }

    def _generate_simple_html(self, results: Dict, id_to_name: Dict, failed_ids: List, now) -> str:
        """Generate simple HTML report"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Crawl Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        .platform {{ margin-bottom: 30px; }}
        .platform-name {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; margin-bottom: 10px; }}
        .news-item {{ padding: 8px; border-bottom: 1px solid #eee; }}
        .rank {{ color: #666; font-weight: bold; margin-right: 10px; }}
        .title {{ color: #333; }}
        .link {{ color: #1976D2; text-decoration: none; margin-left: 10px; font-size: 0.9em; }}
        .link:hover {{ text-decoration: underline; }}
        .failed {{ background: #ffebee; padding: 10px; border-radius: 5px; margin-top: 20px; }}
        .failed h3 {{ color: #c62828; margin-top: 0; }}
        .timestamp {{ color: #666; font-size: 0.9em; text-align: right; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>MCP Crawl Results</h1>
"""

        # Add timestamp
        html += f'        <p class="timestamp">Crawl Time: {now.strftime("%Y-%m-%d %H:%M:%S")}</p>\n\n'

        # Loop through platforms
        for platform_id, titles_data in results.items():
            platform_name = id_to_name.get(platform_id, platform_id)
            html += f'        <div class="platform">\n'
            html += f'            <div class="platform-name">{platform_name}</div>\n'

            # Sort headlines
            sorted_items = []
            for title, info in titles_data.items():
                ranks = info.get("ranks", [])
                url = info.get("url", "")
                mobile_url = info.get("mobileUrl", "")
                rank = ranks[0] if ranks else 999
                sorted_items.append((rank, title, url, mobile_url))

            sorted_items.sort(key=lambda x: x[0])

            # Display news
            for rank, title, url, mobile_url in sorted_items:
                html += f'            <div class="news-item">\n'
                html += f'                <span class="rank">{rank}.</span>\n'
                html += f'                <span class="title">{self._html_escape(title)}</span>\n'
                if url:
                    html += f'                <a class="link" href="{self._html_escape(url)}" target="_blank">Link</a>\n'
                if mobile_url and mobile_url != url:
                    html += f'                <a class="link" href="{self._html_escape(mobile_url)}" target="_blank">Mobile</a>\n'
                html += '            </div>\n'

            html += '        </div>\n\n'

        # Failed platforms
        if failed_ids:
            html += '        <div class="failed">\n'
            html += '            <h3>Failed Platforms</h3>\n'
            html += '            <ul>\n'
            for platform_id in failed_ids:
                html += f'                <li>{self._html_escape(platform_id)}</li>\n'
            html += '            </ul>\n'
            html += '        </div>\n'

        html += """    </div>
</body>
</html>"""

        return html

    def _html_escape(self, text: str) -> str:
        """HTML Escape"""
        if not isinstance(text, str):
            text = str(text)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
