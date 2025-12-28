"""
Storage Sync Tools

Implements functions to pull data from remote storage to local, get storage status, list available dates, etc.
"""

import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yaml

from ..utils.errors import MCPError


class StorageSyncTools:
    """Storage Sync Tools Class"""

    def __init__(self, project_root: str = None):
        """
        Initialize storage sync tools

        Args:
            project_root: Project root directory
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent

        self._config = None
        self._remote_backend = None

    def _load_config(self) -> dict:
        """Load configuration file"""
        if self._config is None:
            config_path = self.project_root / "config" / "config.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f)
            else:
                self._config = {}
        return self._config

    def _get_storage_config(self) -> dict:
        """Get storage configuration"""
        config = self._load_config()
        return config.get("storage", {})

    def _get_remote_config(self) -> dict:
        """
        Get remote storage configuration (merging config file and environment variables)
        """
        storage_config = self._get_storage_config()
        remote_config = storage_config.get("remote", {})

        return {
            "endpoint_url": remote_config.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL", ""),
            "bucket_name": remote_config.get("bucket_name") or os.environ.get("S3_BUCKET_NAME", ""),
            "access_key_id": remote_config.get("access_key_id") or os.environ.get("S3_ACCESS_KEY_ID", ""),
            "secret_access_key": remote_config.get("secret_access_key") or os.environ.get("S3_SECRET_ACCESS_KEY", ""),
            "region": remote_config.get("region") or os.environ.get("S3_REGION", ""),
        }

    def _has_remote_config(self) -> bool:
        """Check if there is a valid remote storage configuration"""
        config = self._get_remote_config()
        return bool(
            config.get("bucket_name") and
            config.get("access_key_id") and
            config.get("secret_access_key") and
            config.get("endpoint_url")
        )

    def _get_remote_backend(self):
        """Get remote storage backend instance"""
        if self._remote_backend is not None:
            return self._remote_backend

        if not self._has_remote_config():
            return None

        try:
            from trendradar.storage.remote import RemoteStorageBackend

            remote_config = self._get_remote_config()
            config = self._load_config()
            timezone = config.get("app", {}).get("timezone", "Asia/Shanghai")

            self._remote_backend = RemoteStorageBackend(
                bucket_name=remote_config["bucket_name"],
                access_key_id=remote_config["access_key_id"],
                secret_access_key=remote_config["secret_access_key"],
                endpoint_url=remote_config["endpoint_url"],
                region=remote_config.get("region", ""),
                timezone=timezone,
            )
            return self._remote_backend
        except ImportError:
            print("[Storage Sync] Remote storage backend requires boto3: pip install boto3")
            return None
        except Exception as e:
            print(f"[Storage Sync] Failed to create remote backend: {e}")
            return None

    def _get_local_data_dir(self) -> Path:
        """Get local data directory"""
        storage_config = self._get_storage_config()
        local_config = storage_config.get("local", {})
        data_dir = local_config.get("data_dir", "output")
        return self.project_root / data_dir

    def _parse_date_folder_name(self, folder_name: str) -> Optional[datetime]:
        """
        Parse date folder name

        Supports:
        - ISO format: YYYY-MM-DD
        - Legacy/International formats: YYYYMMDD, YYYY-M-D
        """
        # Try ISO format
        iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', folder_name)
        if iso_match:
            try:
                return datetime(
                    int(iso_match.group(1)),
                    int(iso_match.group(2)),
                    int(iso_match.group(3))
                )
            except ValueError:
                pass

        # Also support legacy format if detected (e.g. YYYYMMDD)
        if len(folder_name) == 8 and folder_name.isdigit():
             try:
                return datetime.strptime(folder_name, "%Y%m%d")
             except ValueError:
                pass

        return None

    def _get_local_dates(self) -> List[str]:
        """Get list of available local dates"""
        local_dir = self._get_local_data_dir()
        dates = []

        if not local_dir.exists():
            return dates

        for item in local_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                folder_date = self._parse_date_folder_name(item.name)
                if folder_date:
                    dates.append(folder_date.strftime("%Y-%m-%d"))

        return sorted(dates, reverse=True)

    def _calculate_dir_size(self, path: Path) -> int:
        """Calculate directory size (bytes)"""
        total_size = 0
        if path.exists():
            for item in path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        return total_size

    def sync_from_remote(self, days: int = 7) -> Dict:
        """
        Pull data from remote storage to local

        Args:
            days: Pull data for the last N days, default 7

        Returns:
            Sync result dictionary
        """
        try:
            # Check remote config
            if not self._has_remote_config():
                return {
                    "success": False,
                    "error": {
                        "code": "REMOTE_NOT_CONFIGURED",
                        "message": "Remote storage is not configured",
                        "suggestion": "Please configure storage.remote in config/config.yaml or set environment variables"
                    }
                }

            # Get remote backend
            remote_backend = self._get_remote_backend()
            if remote_backend is None:
                return {
                    "success": False,
                    "error": {
                        "code": "REMOTE_BACKEND_FAILED",
                        "message": "Unable to create remote storage backend",
                        "suggestion": "Please check remote storage config and ensure boto3 is installed"
                    }
                }

            # Get local data directory
            local_dir = self._get_local_data_dir()
            local_dir.mkdir(parents=True, exist_ok=True)

            # Get remote available dates
            remote_dates = remote_backend.list_remote_dates()

            # Get local existing dates
            local_dates = set(self._get_local_dates())

            # Calculate target dates
            from trendradar.utils.time import get_configured_time
            config = self._load_config()
            timezone = config.get("app", {}).get("timezone", "Asia/Shanghai")
            now = get_configured_time(timezone)

            target_dates = []
            for i in range(days):
                date = now - timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                if date_str in remote_dates:
                    target_dates.append(date_str)

            # Execute pull
            synced_dates = []
            skipped_dates = []
            failed_dates = []

            for date_str in target_dates:
                # Skip if exists
                if date_str in local_dates:
                    skipped_dates.append(date_str)
                    continue

                # Download date DB
                try:
                    local_date_dir = local_dir / date_str
                    local_db_path = local_date_dir / "news.db"
                    remote_key = f"news/{date_str}.db"

                    local_date_dir.mkdir(parents=True, exist_ok=True)
                    remote_backend.s3_client.download_file(
                        remote_backend.bucket_name,
                        remote_key,
                        str(local_db_path)
                    )
                    synced_dates.append(date_str)
                    print(f"[Storage Sync] Synced: {date_str}")
                except Exception as e:
                    failed_dates.append({"date": date_str, "error": str(e)})
                    print(f"[Storage Sync] Sync failed for {date_str}: {e}")

            return {
                "success": True,
                "synced_files": len(synced_dates),
                "synced_dates": synced_dates,
                "skipped_dates": skipped_dates,
                "failed_dates": failed_dates,
                "message": f"Successfully synced {len(synced_dates)} days of data"
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

    def get_storage_status(self) -> Dict:
        """
        Get storage configuration and status
        """
        try:
            storage_config = self._get_storage_config()
            
            # Local stats
            local_config = storage_config.get("local", {})
            local_dir = self._get_local_data_dir()
            local_size = self._calculate_dir_size(local_dir)
            local_dates = self._get_local_dates()

            local_status = {
                "data_dir": local_config.get("data_dir", "output"),
                "retention_days": local_config.get("retention_days", 0),
                "total_size": f"{local_size / 1024 / 1024:.2f} MB",
                "total_size_bytes": local_size,
                "date_count": len(local_dates),
                "earliest_date": local_dates[-1] if local_dates else None,
                "latest_date": local_dates[0] if local_dates else None,
            }

            # Remote stats
            remote_config = storage_config.get("remote", {})
            has_remote = self._has_remote_config()

            remote_status = {
                "configured": has_remote,
                "retention_days": remote_config.get("retention_days", 0),
            }

            if has_remote:
                merged_config = self._get_remote_config()
                remote_status["endpoint_url"] = merged_config.get("endpoint_url", "")
                remote_status["bucket_name"] = merged_config.get("bucket_name", "")

                remote_backend = self._get_remote_backend()
                if remote_backend:
                    try:
                        remote_dates = remote_backend.list_remote_dates()
                        remote_status["date_count"] = len(remote_dates)
                        remote_status["earliest_date"] = remote_dates[-1] if remote_dates else None
                        remote_status["latest_date"] = remote_dates[0] if remote_dates else None
                    except Exception as e:
                        remote_status["error"] = str(e)

            return {
                "success": True,
                "backend": storage_config.get("backend", "auto"),
                "local": local_status,
                "remote": remote_status,
                "pull_config": storage_config.get("pull", {})
            }

        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def list_available_dates(self, source: str = "both") -> Dict:
        """
        List available date ranges
        """
        try:
            result = {
                "success": True,
            }

            if source in ("local", "both"):
                local_dates = self._get_local_dates()
                result["local"] = {
                    "dates": local_dates,
                    "count": len(local_dates),
                    "earliest": local_dates[-1] if local_dates else None,
                    "latest": local_dates[0] if local_dates else None,
                }

            if source in ("remote", "both"):
                if not self._has_remote_config():
                    result["remote"] = {"configured": False}
                else:
                    remote_backend = self._get_remote_backend()
                    if remote_backend:
                        try:
                            remote_dates = remote_backend.list_remote_dates()
                            result["remote"] = {
                                "configured": True,
                                "dates": remote_dates,
                                "count": len(remote_dates),
                                "earliest": remote_dates[-1] if remote_dates else None,
                                "latest": remote_dates[0] if remote_dates else None,
                            }
                        except Exception as e:
                            result["remote"] = {"configured": True, "error": str(e)}

            return result

        except Exception as e:
            return {
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)}
            }
