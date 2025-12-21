# coding=utf-8
"""
Notification Push Module

Provides multi-channel notification push functionality, including:
- Feishu, DingTalk, WeChat Work
- Telegram, Slack
- Email, ntfy, Bark

Module Structure:
- push_manager: Push record management
- formatters: Content format conversion
- batch: Batch processing tools
- renderer: Notification content rendering
- splitter: Message batch splitting
- senders: Message senders (push functions for each channel)
- dispatcher: Multi-account notification dispatcher
"""

from trendradar.notification.push_manager import PushRecordManager
from trendradar.notification.formatters import (
    strip_markdown,
    convert_markdown_to_mrkdwn,
)
from trendradar.notification.batch import (
    get_batch_header,
    get_max_batch_header_size,
    truncate_to_bytes,
    add_batch_headers,
)
from trendradar.notification.renderer import (
    render_feishu_content,
    render_dingtalk_content,
)
from trendradar.notification.splitter import (
    split_content_into_batches,
    DEFAULT_BATCH_SIZES,
)
from trendradar.notification.senders import (
    send_to_feishu,
    send_to_dingtalk,
    send_to_wework,
    send_to_telegram,
    send_to_email,
    send_to_ntfy,
    send_to_bark,
    send_to_slack,
    SMTP_CONFIGS,
)
from trendradar.notification.dispatcher import NotificationDispatcher

__all__ = [
    # 推送记录管理
    "PushRecordManager",
    # 格式转换
    "strip_markdown",
    "convert_markdown_to_mrkdwn",
    # 批次处理
    "get_batch_header",
    "get_max_batch_header_size",
    "truncate_to_bytes",
    "add_batch_headers",
    # 内容渲染
    "render_feishu_content",
    "render_dingtalk_content",
    # 消息分批
    "split_content_into_batches",
    "DEFAULT_BATCH_SIZES",
    # 消息发送器
    "send_to_feishu",
    "send_to_dingtalk",
    "send_to_wework",
    "send_to_telegram",
    "send_to_email",
    "send_to_ntfy",
    "send_to_bark",
    "send_to_slack",
    "SMTP_CONFIGS",
    # 通知调度器
    "NotificationDispatcher",
]
