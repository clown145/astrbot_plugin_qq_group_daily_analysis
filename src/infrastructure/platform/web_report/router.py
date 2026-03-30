"""Web 报告平台路由。"""

from __future__ import annotations

from typing import Any


class WebReportRouter:
    """统一分发不同平台的 Web 报告交互处理器。"""

    def __init__(self, handlers: list[Any] | None = None):
        self._handlers: list[Any] = handlers or []

    def add_handler(self, handler: Any) -> None:
        """注册一个平台处理器。"""
        self._handlers.append(handler)

    async def ensure_handlers_registered(self, context: Any) -> None:
        """让处理器完成初始化（如注册回调）。"""
        for handler in self._handlers:
            register_func = getattr(
                handler, "ensure_callback_handlers_registered", None
            )
            if callable(register_func):
                await register_func(context)

    async def unregister_handlers(self) -> None:
        """统一注销处理器资源。"""
        for handler in self._handlers:
            unregister_func = getattr(handler, "unregister_callback_handlers", None)
            if callable(unregister_func):
                await unregister_func()

    async def send_web_report(
        self,
        *,
        event: Any | None,
        adapter: Any | None,
        platform_id: str | None,
        group_id: str,
        report_url: str,
    ) -> bool:
        """
        发送交互式 Web 报告消息。

        返回:
        - True: 已由某个平台处理器接管并发送
        - False: 无法处理，调用方应走原有降级路径
        """
        for handler in self._handlers:
            supports_func = getattr(handler, "supports", None)
            if not callable(supports_func) or not supports_func(
                event=event,
                adapter=adapter,
                platform_id=platform_id,
            ):
                continue

            handle_func = getattr(handler, "send_web_report", None)
            if not callable(handle_func):
                continue

            handled = await handle_func(
                event=event,
                adapter=adapter,
                platform_id=platform_id,
                group_id=group_id,
                report_url=report_url,
            )
            if handled:
                return True

        return False
