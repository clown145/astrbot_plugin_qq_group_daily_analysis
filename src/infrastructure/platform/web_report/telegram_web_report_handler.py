"""Telegram Web 报告交互处理。"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ....utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

    from ....application.commands.template_command_service import TemplateCommandService
    from ...config.config_manager import ConfigManager

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.error import BadRequest
    from telegram.ext import CallbackQueryHandler, ContextTypes

    TELEGRAM_RUNTIME_AVAILABLE = True
except Exception:
    TELEGRAM_RUNTIME_AVAILABLE = False
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    Update = None
    BadRequest = Exception
    CallbackQueryHandler = None
    ContextTypes = None


@dataclass
class _WebReportSession:
    token: str
    platform_id: str
    chat_id: int | str
    message_thread_id: int | None
    message_id: int
    templates: list[str]
    index: int
    report_url: str
    created_at: float

    @property
    def current_template(self) -> str:
        return self.templates[self.index]


class TelegramWebReportHandler:
    """Telegram 网页日报按钮处理器（链接 + ←/→ 切换模板）。"""

    _SESSION_TTL_SECONDS = 2 * 60 * 60
    _MAX_SESSIONS = 200
    _CONNECT_TIMEOUT = 20
    _READ_TIMEOUT = 120
    _WRITE_TIMEOUT = 120
    _POOL_TIMEOUT = 20

    def __init__(
        self,
        config_manager: ConfigManager,
        template_service: TemplateCommandService,
    ):
        self.config_manager = config_manager
        self.template_service = template_service
        self._sessions: dict[str, _WebReportSession] = {}
        self._registered_platform_ids: set[str] = set()
        self._handlers: dict[str, tuple[Any, Any]] = {}
        self._platform_clients: dict[str, Any] = {}
        self._callback_prefix = f"qda_web_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def supports(
        event: AstrMessageEvent | None = None,
        adapter: Any | None = None,
        platform_id: str | None = None,
    ) -> bool:
        """判断是否 Telegram 目标。"""
        if event is not None:
            try:
                return (event.get_platform_name() or "").lower() == "telegram"
            except Exception:
                return False

        if adapter is not None:
            try:
                return (adapter.get_platform_name() or "").lower() == "telegram"
            except Exception:
                return False

        return bool(platform_id and "telegram" in str(platform_id).lower())

    async def ensure_callback_handlers_registered(self, context: Any) -> None:
        """为所有 Telegram 平台注册按钮回调处理器。"""
        if not TELEGRAM_RUNTIME_AVAILABLE:
            return
        if not context or not hasattr(context, "platform_manager"):
            return

        platforms = context.platform_manager.get_insts()
        seen_platform_ids: set[str] = set()
        for platform in platforms:
            platform_id, platform_name = self._extract_platform_meta(platform)
            if platform_name != "telegram" or not platform_id:
                continue

            seen_platform_ids.add(platform_id)
            client = self._extract_platform_client(platform)
            if client is not None:
                self._platform_clients[platform_id] = client

            application = getattr(platform, "application", None)
            if not application:
                continue

            existing = self._handlers.get(platform_id)
            if existing:
                old_application, old_handler = existing
                if old_application is application:
                    self._registered_platform_ids.add(platform_id)
                    continue

                try:
                    old_application.remove_handler(old_handler)
                except Exception as e:
                    logger.debug(
                        f"[WebReport][Telegram] 解绑旧回调失败: platform_id={platform_id}, err={e}"
                    )
                self._handlers.pop(platform_id, None)
                self._registered_platform_ids.discard(platform_id)

            try:
                handler = CallbackQueryHandler(
                    self._on_callback_query,
                    pattern=rf"^{re.escape(self._callback_prefix)}:",
                )
                application.add_handler(handler)
                self._registered_platform_ids.add(platform_id)
                self._handlers[platform_id] = (application, handler)
                logger.info(
                    f"[WebReport][Telegram] 已注册回调处理器: platform_id={platform_id}"
                )
            except Exception as e:
                logger.warning(
                    f"[WebReport][Telegram] 注册回调处理器失败: platform_id={platform_id}, err={e}"
                )

        stale_ids = [
            platform_id
            for platform_id in list(self._handlers.keys())
            if platform_id not in seen_platform_ids
        ]
        for stale_platform_id in stale_ids:
            old_application, old_handler = self._handlers.pop(stale_platform_id)
            try:
                old_application.remove_handler(old_handler)
            except Exception as e:
                logger.debug(
                    f"[WebReport][Telegram] 清理离线平台回调失败: platform_id={stale_platform_id}, err={e}"
                )
            self._registered_platform_ids.discard(stale_platform_id)
            self._platform_clients.pop(stale_platform_id, None)

    async def unregister_callback_handlers(self) -> None:
        """卸载已注册的回调处理器。"""
        if not TELEGRAM_RUNTIME_AVAILABLE:
            return

        for platform_id, (application, handler) in list(self._handlers.items()):
            try:
                application.remove_handler(handler)
            except Exception as e:
                logger.debug(
                    f"[WebReport][Telegram] 移除回调处理器失败: platform_id={platform_id}, err={e}"
                )
        self._handlers.clear()
        self._registered_platform_ids.clear()
        self._platform_clients.clear()

    async def send_web_report(
        self,
        *,
        event: AstrMessageEvent | None,
        adapter: Any | None,
        platform_id: str | None,
        group_id: str,
        report_url: str,
    ) -> bool:
        """发送带模板切换按钮的网页日报链接。"""
        if not TELEGRAM_RUNTIME_AVAILABLE or not platform_id:
            return False

        available_templates = await self.template_service.list_available_templates()
        if not available_templates:
            return False

        current_template = self.config_manager.get_report_template()
        if current_template in available_templates:
            index = available_templates.index(current_template)
        else:
            index = 0

        client = self._get_event_client(event, platform_id)
        if client is None:
            logger.warning("[WebReport][Telegram] 无法获取 Telegram client")
            return False

        chat_id, message_thread_id = self._parse_group_id(group_id)
        token = uuid.uuid4().hex[:8]
        keyboard = self._build_keyboard(
            token=token,
            report_url=report_url,
            template_name=available_templates[index],
            show_navigation=len(available_templates) > 1,
        )

        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": "群聊分析报告已生成",
            "reply_markup": keyboard,
            "connect_timeout": self._CONNECT_TIMEOUT,
            "read_timeout": self._READ_TIMEOUT,
            "write_timeout": self._WRITE_TIMEOUT,
            "pool_timeout": self._POOL_TIMEOUT,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id

        try:
            sent_msg = await client.send_message(**payload)
        except Exception as e:
            logger.warning(f"[WebReport][Telegram] 发送交互式网页日报失败: {e}")
            return False

        self._sessions[token] = _WebReportSession(
            token=token,
            platform_id=str(platform_id),
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            message_id=sent_msg.message_id,
            templates=available_templates.copy(),
            index=index,
            report_url=report_url,
            created_at=time.time(),
        )
        self._cleanup_expired_sessions()
        logger.info(
            "[WebReport][Telegram] 已发送交互式网页日报: "
            f"platform_id={platform_id} chat_id={chat_id} token={token}"
        )
        return True

    async def _on_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not TELEGRAM_RUNTIME_AVAILABLE:
            return
        if not update.callback_query or not update.callback_query.data:
            return

        self._cleanup_expired_sessions()

        query = update.callback_query
        parts = query.data.split(":")
        if len(parts) != 3:
            await query.answer("无效操作", show_alert=False)
            return

        _, token, action = parts
        session = self._sessions.get(token)
        if not session:
            await query.answer("网页日报会话已过期，请重新生成报告", show_alert=True)
            return

        if time.time() - session.created_at > self._SESSION_TTL_SECONDS:
            self._sessions.pop(token, None)
            await query.answer("网页日报会话已过期，请重新生成报告", show_alert=True)
            return

        if not query.message:
            await query.answer("消息已失效", show_alert=False)
            return

        if query.message.message_id != session.message_id or str(
            query.message.chat_id
        ) != str(session.chat_id):
            await query.answer("网页日报状态不一致，请重新生成报告", show_alert=True)
            return

        if action == "prev":
            session.index = (session.index - 1) % len(session.templates)
            await self._edit_report_message(query, session)
            await query.answer()
            return

        if action == "next":
            session.index = (session.index + 1) % len(session.templates)
            await self._edit_report_message(query, session)
            await query.answer()
            return

        await query.answer("未知操作", show_alert=False)

    async def _edit_report_message(
        self, query: Any, session: _WebReportSession
    ) -> None:
        keyboard = self._build_keyboard(
            token=session.token,
            report_url=session.report_url,
            template_name=session.current_template,
            show_navigation=len(session.templates) > 1,
        )
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except BadRequest as e:
            if "message is not modified" in str(e).lower():
                return
            raise

    def _build_keyboard(
        self,
        *,
        token: str,
        report_url: str,
        template_name: str,
        show_navigation: bool,
    ) -> Any:
        rows = [
            [
                InlineKeyboardButton(
                    text=f"点击查看（{template_name}）",
                    url=self._build_template_url(report_url, template_name),
                )
            ]
        ]
        if show_navigation:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="←",
                        callback_data=f"{self._callback_prefix}:{token}:prev",
                    ),
                    InlineKeyboardButton(
                        text="→",
                        callback_data=f"{self._callback_prefix}:{token}:next",
                    ),
                ]
            )
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def _build_template_url(report_url: str, template_name: str) -> str:
        split_result = urlsplit(report_url)
        query_items = dict(parse_qsl(split_result.query, keep_blank_values=True))
        query_items.pop("template", None)
        query_items["t"] = template_name
        return urlunsplit(
            (
                split_result.scheme,
                split_result.netloc,
                split_result.path,
                urlencode(query_items),
                split_result.fragment,
            )
        )

    @staticmethod
    def _parse_group_id(group_id: str) -> tuple[str, int | None]:
        if "#" not in str(group_id):
            return str(group_id), None

        chat_id, thread_id = str(group_id).split("#", 1)
        try:
            return chat_id, int(thread_id)
        except (TypeError, ValueError):
            return chat_id, None

    @staticmethod
    def _extract_platform_meta(platform: Any) -> tuple[str | None, str | None]:
        metadata = getattr(platform, "metadata", None)
        if not metadata and hasattr(platform, "meta"):
            try:
                metadata = platform.meta()
            except Exception:
                metadata = None

        platform_id = None
        platform_name = None
        if metadata:
            if isinstance(metadata, dict):
                platform_id = metadata.get("id")
                platform_name = metadata.get("type") or metadata.get("name")
            else:
                platform_id = getattr(metadata, "id", None)
                platform_name = getattr(metadata, "type", None) or getattr(
                    metadata, "name", None
                )
        if platform_name:
            platform_name = str(platform_name).lower()
        if platform_id:
            platform_id = str(platform_id)
        return platform_id, platform_name

    @staticmethod
    def _extract_platform_client(platform: Any) -> Any | None:
        client = None
        if hasattr(platform, "get_client"):
            try:
                client = platform.get_client()
            except Exception:
                client = None
        if client is None:
            client = getattr(platform, "client", None)
        if client is None:
            application = getattr(platform, "application", None)
            if application is not None:
                client = getattr(application, "bot", None)
        if client is None or not hasattr(client, "send_message"):
            return None
        return client

    @staticmethod
    def _get_raw_event_client(event: AstrMessageEvent | None) -> Any | None:
        if event is None:
            return None
        client = getattr(event, "client", None)
        if client:
            return client
        return getattr(event, "bot", None)

    def _get_event_client(
        self, event: AstrMessageEvent | None, platform_id: str | None = None
    ) -> Any | None:
        client = self._get_raw_event_client(event)
        if client is not None and hasattr(client, "send_message"):
            return client
        if platform_id:
            cached = self._platform_clients.get(str(platform_id))
            if cached is not None:
                return cached
        return None

    def _cleanup_expired_sessions(self) -> None:
        now = time.time()
        expired_tokens = [
            token
            for token, session in self._sessions.items()
            if now - session.created_at > self._SESSION_TTL_SECONDS
        ]
        for token in expired_tokens:
            self._sessions.pop(token, None)

        overflow = len(self._sessions) - self._MAX_SESSIONS
        if overflow > 0:
            oldest_tokens = sorted(
                self._sessions,
                key=lambda token: self._sessions[token].created_at,
            )[:overflow]
            for token in oldest_tokens:
                self._sessions.pop(token, None)
