"""平台 Web 报告交互能力。"""

from .router import WebReportRouter
from .telegram_web_report_handler import TelegramWebReportHandler

__all__ = ["TelegramWebReportHandler", "WebReportRouter"]
