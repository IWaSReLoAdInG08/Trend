# coding=utf-8
"""
Config Loader Module

Responsible for loading configuration from YAML files and environment variables.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

import yaml

from .config import parse_multi_account_config, validate_paired_configs


def _get_env_bool(key: str, default: bool = False) -> Optional[bool]:
    """Get boolean value from environment variable, return None if not set"""
    value = os.environ.get(key, "").strip().lower()
    if not value:
        return None
    return value in ("true", "1")


def _get_env_int(key: str, default: int = 0) -> int:
    """Get integer value from environment variable"""
    value = os.environ.get(key, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_str(key: str, default: str = "") -> str:
    """Get string value from environment variable"""
    return os.environ.get(key, "").strip() or default


def _load_app_config(config_data: Dict) -> Dict:
    """Load App Config"""
    app_config = config_data.get("app", {})
    return {
        "VERSION_CHECK_URL": app_config.get("version_check_url", ""),
        "SHOW_VERSION_UPDATE": app_config.get("show_version_update", True),
        "TIMEZONE": _get_env_str("TIMEZONE") or app_config.get("timezone", "Asia/Shanghai"),
    }


def _load_crawler_config(config_data: Dict) -> Dict:
    """Load Crawler Config"""
    crawler_config = config_data.get("crawler", {})
    enable_crawler_env = _get_env_bool("ENABLE_CRAWLER")
    return {
        "REQUEST_INTERVAL": crawler_config.get("request_interval", 100),
        "USE_PROXY": crawler_config.get("use_proxy", False),
        "DEFAULT_PROXY": crawler_config.get("default_proxy", ""),
        "ENABLE_CRAWLER": enable_crawler_env if enable_crawler_env is not None else crawler_config.get("enable_crawler", True),
    }


def _load_report_config(config_data: Dict) -> Dict:
    """Load Report Config"""
    report_config = config_data.get("report", {})

    # Environment variable override
    sort_by_position_env = _get_env_bool("SORT_BY_POSITION_FIRST")
    reverse_content_env = _get_env_bool("REVERSE_CONTENT_ORDER")
    max_news_env = _get_env_int("MAX_NEWS_PER_KEYWORD")

    return {
        "REPORT_MODE": _get_env_str("REPORT_MODE") or report_config.get("mode", "daily"),
        "RANK_THRESHOLD": report_config.get("rank_threshold", 10),
        "SORT_BY_POSITION_FIRST": sort_by_position_env if sort_by_position_env is not None else report_config.get("sort_by_position_first", False),
        "MAX_NEWS_PER_KEYWORD": max_news_env or report_config.get("max_news_per_keyword", 0),
        "REVERSE_CONTENT_ORDER": reverse_content_env if reverse_content_env is not None else report_config.get("reverse_content_order", False),
    }


def _load_notification_config(config_data: Dict) -> Dict:
    """Load Notification Config"""
    notification = config_data.get("notification", {})
    enable_notification_env = _get_env_bool("ENABLE_NOTIFICATION")

    return {
        "ENABLE_NOTIFICATION": enable_notification_env if enable_notification_env is not None else notification.get("enable_notification", True),
        "MESSAGE_BATCH_SIZE": notification.get("message_batch_size", 4000),
        "DINGTALK_BATCH_SIZE": notification.get("dingtalk_batch_size", 20000),
        "FEISHU_BATCH_SIZE": notification.get("feishu_batch_size", 29000),
        "BARK_BATCH_SIZE": notification.get("bark_batch_size", 3600),
        "SLACK_BATCH_SIZE": notification.get("slack_batch_size", 4000),
        "BATCH_SEND_INTERVAL": notification.get("batch_send_interval", 1.0),
        "FEISHU_MESSAGE_SEPARATOR": notification.get("feishu_message_separator", "---"),
        "MAX_ACCOUNTS_PER_CHANNEL": _get_env_int("MAX_ACCOUNTS_PER_CHANNEL") or notification.get("max_accounts_per_channel", 3),
    }


def _load_push_window_config(config_data: Dict) -> Dict:
    """Load Push Window Config"""
    notification = config_data.get("notification", {})
    push_window = notification.get("push_window", {})
    time_range = push_window.get("time_range", {})

    enabled_env = _get_env_bool("PUSH_WINDOW_ENABLED")
    once_per_day_env = _get_env_bool("PUSH_WINDOW_ONCE_PER_DAY")

    return {
        "ENABLED": enabled_env if enabled_env is not None else push_window.get("enabled", False),
        "TIME_RANGE": {
            "START": _get_env_str("PUSH_WINDOW_START") or time_range.get("start", "08:00"),
            "END": _get_env_str("PUSH_WINDOW_END") or time_range.get("end", "22:00"),
        },
        "ONCE_PER_DAY": once_per_day_env if once_per_day_env is not None else push_window.get("once_per_day", True),
    }


def _load_weight_config(config_data: Dict) -> Dict:
    """Load Weight Config"""
    weight = config_data.get("weight", {})
    return {
        "RANK_WEIGHT": weight.get("rank_weight", 1.0),
        "FREQUENCY_WEIGHT": weight.get("frequency_weight", 1.0),
        "HOTNESS_WEIGHT": weight.get("hotness_weight", 1.0),
    }


def _load_storage_config(config_data: Dict) -> Dict:
    """Load Storage Config"""
    storage = config_data.get("storage", {})
    formats = storage.get("formats", {})
    local = storage.get("local", {})
    remote = storage.get("remote", {})
    pull = storage.get("pull", {})

    txt_enabled_env = _get_env_bool("STORAGE_TXT_ENABLED")
    html_enabled_env = _get_env_bool("STORAGE_HTML_ENABLED")
    pull_enabled_env = _get_env_bool("PULL_ENABLED")

    return {
        "BACKEND": _get_env_str("STORAGE_BACKEND") or storage.get("backend", "auto"),
        "FORMATS": {
            "SQLITE": formats.get("sqlite", True),
            "TXT": txt_enabled_env if txt_enabled_env is not None else formats.get("txt", True),
            "HTML": html_enabled_env if html_enabled_env is not None else formats.get("html", True),
        },
        "LOCAL": {
            "DATA_DIR": local.get("data_dir", "output"),
            "RETENTION_DAYS": _get_env_int("LOCAL_RETENTION_DAYS") or local.get("retention_days", 0),
        },
        "REMOTE": {
            "ENDPOINT_URL": _get_env_str("S3_ENDPOINT_URL") or remote.get("endpoint_url", ""),
            "BUCKET_NAME": _get_env_str("S3_BUCKET_NAME") or remote.get("bucket_name", ""),
            "ACCESS_KEY_ID": _get_env_str("S3_ACCESS_KEY_ID") or remote.get("access_key_id", ""),
            "SECRET_ACCESS_KEY": _get_env_str("S3_SECRET_ACCESS_KEY") or remote.get("secret_access_key", ""),
            "REGION": _get_env_str("S3_REGION") or remote.get("region", ""),
            "RETENTION_DAYS": _get_env_int("REMOTE_RETENTION_DAYS") or remote.get("retention_days", 0),
        },
        "PULL": {
            "ENABLED": pull_enabled_env if pull_enabled_env is not None else pull.get("enabled", False),
            "DAYS": _get_env_int("PULL_DAYS") or pull.get("days", 7),
        },
    }


def _load_webhook_config(config_data: Dict) -> Dict:
    """Load Webhook Config"""
    notification = config_data.get("notification", {})
    webhooks = notification.get("webhooks", {})

    return {
        # Feishu
        "FEISHU_WEBHOOK_URL": _get_env_str("FEISHU_WEBHOOK_URL") or webhooks.get("feishu_url", ""),
        # DingTalk
        "DINGTALK_WEBHOOK_URL": _get_env_str("DINGTALK_WEBHOOK_URL") or webhooks.get("dingtalk_url", ""),
        # WeWork
        "WEWORK_WEBHOOK_URL": _get_env_str("WEWORK_WEBHOOK_URL") or webhooks.get("wework_url", ""),
        "WEWORK_MSG_TYPE": _get_env_str("WEWORK_MSG_TYPE") or webhooks.get("wework_msg_type", "markdown"),
        # Telegram
        "TELEGRAM_BOT_TOKEN": _get_env_str("TELEGRAM_BOT_TOKEN") or webhooks.get("telegram_bot_token", ""),
        "TELEGRAM_CHAT_ID": _get_env_str("TELEGRAM_CHAT_ID") or webhooks.get("telegram_chat_id", ""),
        # Email
        "EMAIL_FROM": _get_env_str("EMAIL_FROM") or webhooks.get("email_from", ""),
        "EMAIL_PASSWORD": _get_env_str("EMAIL_PASSWORD") or webhooks.get("email_password", ""),
        "EMAIL_TO": _get_env_str("EMAIL_TO") or webhooks.get("email_to", ""),
        "EMAIL_SMTP_SERVER": _get_env_str("EMAIL_SMTP_SERVER") or webhooks.get("email_smtp_server", ""),
        "EMAIL_SMTP_PORT": _get_env_str("EMAIL_SMTP_PORT") or webhooks.get("email_smtp_port", ""),
        # ntfy
        "NTFY_SERVER_URL": _get_env_str("NTFY_SERVER_URL") or webhooks.get("ntfy_server_url") or "https://ntfy.sh",
        "NTFY_TOPIC": _get_env_str("NTFY_TOPIC") or webhooks.get("ntfy_topic", ""),
        "NTFY_TOKEN": _get_env_str("NTFY_TOKEN") or webhooks.get("ntfy_token", ""),
        # Bark
        "BARK_URL": _get_env_str("BARK_URL") or webhooks.get("bark_url", ""),
        # Slack
        "SLACK_WEBHOOK_URL": _get_env_str("SLACK_WEBHOOK_URL") or webhooks.get("slack_webhook_url", ""),
    }


def _print_notification_sources(config: Dict) -> None:
    """Print notification channel configuration sources"""
    notification_sources = []
    max_accounts = config["MAX_ACCOUNTS_PER_CHANNEL"]

    if config["FEISHU_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["FEISHU_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "Env Var" if os.environ.get("FEISHU_WEBHOOK_URL") else "Config File"
        notification_sources.append(f"Feishu({source}, {count} accounts)")

    if config["DINGTALK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["DINGTALK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "Env Var" if os.environ.get("DINGTALK_WEBHOOK_URL") else "Config File"
        notification_sources.append(f"DingTalk({source}, {count} accounts)")

    if config["WEWORK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["WEWORK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "Env Var" if os.environ.get("WEWORK_WEBHOOK_URL") else "Config File"
        notification_sources.append(f"WeWork({source}, {count} accounts)")

    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        tokens = parse_multi_account_config(config["TELEGRAM_BOT_TOKEN"])
        chat_ids = parse_multi_account_config(config["TELEGRAM_CHAT_ID"])
        valid, count = validate_paired_configs(
            {"bot_token": tokens, "chat_id": chat_ids},
            "Telegram",
            required_keys=["bot_token", "chat_id"]
        )
        if valid and count > 0:
            count = min(count, max_accounts)
            token_source = "Env Var" if os.environ.get("TELEGRAM_BOT_TOKEN") else "Config File"
            notification_sources.append(f"Telegram({token_source}, {count} accounts)")

    if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
        from_source = "Env Var" if os.environ.get("EMAIL_FROM") else "Config File"
        notification_sources.append(f"Email({from_source})")

    if config["NTFY_SERVER_URL"] and config["NTFY_TOPIC"]:
        topics = parse_multi_account_config(config["NTFY_TOPIC"])
        tokens = parse_multi_account_config(config["NTFY_TOKEN"])
        if tokens:
            valid, count = validate_paired_configs(
                {"topic": topics, "token": tokens},
                "ntfy"
            )
            if valid and count > 0:
                count = min(count, max_accounts)
                server_source = "Env Var" if os.environ.get("NTFY_SERVER_URL") else "Config File"
                notification_sources.append(f"ntfy({server_source}, {count} accounts)")
        else:
            count = min(len(topics), max_accounts)
            server_source = "Env Var" if os.environ.get("NTFY_SERVER_URL") else "Config File"
            notification_sources.append(f"ntfy({server_source}, {count} accounts)")

    if config["BARK_URL"]:
        accounts = parse_multi_account_config(config["BARK_URL"])
        count = min(len(accounts), max_accounts)
        bark_source = "Env Var" if os.environ.get("BARK_URL") else "Config File"
        notification_sources.append(f"Bark({bark_source}, {count} accounts)")

    if config["SLACK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["SLACK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        slack_source = "Env Var" if os.environ.get("SLACK_WEBHOOK_URL") else "Config File"
        notification_sources.append(f"Slack({slack_source}, {count} accounts)")

    if notification_sources:
        print(f"Notification Channels Configured: {', '.join(notification_sources)}")
        print(f"Max Accounts Per Channel: {max_accounts}")
    else:
        print("No Notification Channels Configured")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load Configuration

    Args:
        config_path: Path to config file, defaults to CONFIG_PATH env var or config/config.yaml

    Returns:
        Dict containing all configurations

    Raises:
        FileNotFoundError: Config file not found
    """
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    if not Path(config_path).exists():
        raise FileNotFoundError(f"Config file {config_path} not found")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    print(f"Config file loaded: {config_path}")

    # Merge all configs
    config = {}

    # App Config
    config.update(_load_app_config(config_data))

    # Crawler Config
    config.update(_load_crawler_config(config_data))

    # Report Config
    config.update(_load_report_config(config_data))

    # Notification Config
    config.update(_load_notification_config(config_data))

    # Push Window Config
    config["PUSH_WINDOW"] = _load_push_window_config(config_data)

    # Weight Config
    config["WEIGHT_CONFIG"] = _load_weight_config(config_data)

    # Platform Config
    config["PLATFORMS"] = config_data.get("platforms", [])
    
    # RSS feeds Config
    config["RSS_FEEDS"] = config_data.get("rss_feeds", [])

    # Storage Config
    config["STORAGE"] = _load_storage_config(config_data)

    # Webhook Config
    config.update(_load_webhook_config(config_data))

    # Print Notification Sources
    _print_notification_sources(config)

    return config
