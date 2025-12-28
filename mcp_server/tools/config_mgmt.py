"""
Configuration Management Tools

Implements tools to view and manage current configuration.
"""

from pathlib import Path
from typing import Dict, Optional

import yaml

from ..utils.validators import validate_config_section
from ..utils.errors import MCPError


class ConfigManagementTools:
    """Configuration Management Tools Class"""

    def __init__(self, project_root: str = None):
        """
        Initialize configuration management tools

        Args:
            project_root: Project root directory
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Get project root
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent

    def get_current_config(self, section: Optional[str] = None) -> Dict:
        """
        Get current server configuration

        Args:
            section: Specific configuration section, e.g., "crawler", "storage", "email", "app"

        Returns:
            Configuration dictionary
        """
        try:
            # Parameter validation
            section = validate_config_section(section)

            # Load config file
            config_path = self.project_root / "config" / "config.yaml"
            if not config_path.exists():
                return {
                    "success": False,
                    "error": {
                        "code": "CONFIG_NOT_FOUND",
                        "message": f"Configuration file not found: {config_path}"
                    }
                }

            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            if section:
                config = {section: config.get(section, {})}

            return {
                "config": config,
                "section": section,
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
