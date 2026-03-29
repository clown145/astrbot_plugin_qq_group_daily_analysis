"""
网页日报共享编排工具。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ...utils.logger import logger

AvatarUrlGetter = Callable[[str], Awaitable[str | None]]
NicknameGetter = Callable[[str], Awaitable[str | None]]


def build_web_identity_getters(
    adapter: Any | None,
    group_id: str,
    avatar_size: int = 40,
) -> tuple[AvatarUrlGetter, NicknameGetter]:
    """为网页日报构造统一的头像与昵称回调。"""

    async def avatar_url_getter(user_id: str) -> str | None:
        if adapter and hasattr(adapter, "get_user_avatar_url"):
            return await adapter.get_user_avatar_url(user_id, size=avatar_size)
        return None

    async def nickname_getter(user_id: str) -> str | None:
        if adapter and hasattr(adapter, "get_member_info"):
            try:
                member = await adapter.get_member_info(group_id, user_id)
                if member:
                    return member.card or member.nickname
            except Exception:
                return None
        return None

    return avatar_url_getter, nickname_getter


async def build_and_publish_web_report(
    report_generator,
    web_report_publisher,
    analysis_result: dict[str, Any],
    adapter: Any | None,
    group_id: str,
    trace_id: str | None = None,
):
    """生成网页日报 payload 并发布到 Worker。"""
    avatar_url_getter, nickname_getter = build_web_identity_getters(adapter, group_id)

    try:
        payload = await report_generator.generate_web_report_payload(
            analysis_result,
            avatar_url_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
        )
        return await web_report_publisher.publish(payload)
    except Exception as exc:
        prefix = f"[{trace_id}] " if trace_id else ""
        logger.error(f"{prefix}Failed to build or publish web report: {exc}")
        return None
