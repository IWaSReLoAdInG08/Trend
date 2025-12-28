"""
Custom Error Classes

Defines all custom exception types used by the MCP Server.
"""

from typing import Optional


class MCPError(Exception):
    """Base class for MCP tool errors"""

    def __init__(self, message: str, code: str = "MCP_ERROR", suggestion: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        """Convert to dictionary format"""
        error_dict = {
            "code": self.code,
            "message": self.message
        }
        if self.suggestion:
            error_dict["suggestion"] = self.suggestion
        return error_dict


class DataNotFoundError(MCPError):
    """Data Not Found Error"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="DATA_NOT_FOUND",
            suggestion=suggestion or "Please check the date range or wait for the crawl task to complete"
        )


class InvalidParameterError(MCPError):
    """Invalid Parameter Error"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="INVALID_PARAMETER",
            suggestion=suggestion or "Please check if the parameter format is correct"
        )


class ConfigurationError(MCPError):
    """Configuration Error"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            suggestion=suggestion or "Please check if the configuration file is correct"
        )


class PlatformNotSupportedError(MCPError):
    """Platform Not Supported Error"""

    def __init__(self, platform: str):
        super().__init__(
            message=f"Platform '{platform}' is not supported",
            code="PLATFORM_NOT_SUPPORTED",
            suggestion="Supported platforms: zhihu, weibo, douyin, bilibili, baidu, toutiao, qq, 36kr, sspai, hellogithub, thepaper"
        )


class CrawlTaskError(MCPError):
    """Crawl Task Error"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="CRAWL_TASK_ERROR",
            suggestion=suggestion or "Please try again later or check the logs"
        )


class FileParseError(MCPError):
    """File Parse Error"""

    def __init__(self, file_path: str, reason: str):
        super().__init__(
            message=f"Failed to parse file {file_path}: {reason}",
            code="FILE_PARSE_ERROR",
            suggestion="Please check if the file format is correct"
        )
