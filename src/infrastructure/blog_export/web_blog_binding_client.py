"""Web 博客绑定验证客户端。"""

from __future__ import annotations

import json
from typing import Any

import aiohttp

from ...shared.trace_context import TraceContext
from ...utils.logger import logger


class WebBlogBindingClient:
    """负责把群内一次性绑定码验证回调到 Worker。"""

    def __init__(self, config_manager: Any):
        self.config_manager = config_manager

    def validate_config(self) -> tuple[bool, str | None]:
        """检查绑定验证配置是否完整。"""
        if not self.config_manager.get_web_blog_enabled():
            return False, "Web 博客发布开关未启用"

        if not self.config_manager.get_web_blog_worker_base_url():
            return False, "未配置 Worker 基础地址"

        if not self.config_manager.get_web_blog_bind_callback_token():
            return False, "未配置 Worker 绑定回调密钥"

        return True, None

    async def verify_bind_code(
        self,
        *,
        platform: str,
        group_id: str,
        qq_number: str,
        bind_code: str,
    ) -> dict[str, Any]:
        """调用 Worker 绑定验证接口。"""
        config_ok, config_error = self.validate_config()
        if not config_ok:
            raise RuntimeError(config_error or "Web 博客绑定配置无效")

        url = self._build_bind_verify_url()
        token = self.config_manager.get_web_blog_bind_callback_token()
        timeout_seconds = max(
            10, self.config_manager.get_web_blog_request_timeout_seconds()
        )
        trace_id = TraceContext.get()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "astrbot-group-daily-analysis/web-bind",
        }
        if trace_id:
            headers["X-AstrBot-Trace-Id"] = trace_id

        payload = {
            "platform": platform,
            "groupId": group_id,
            "qqNumber": qq_number,
            "bindCode": bind_code,
        }

        logger.info(
            f"[{trace_id}] 正在回调 Worker 绑定验证: platform={platform}, group={group_id}, url={url}"
        )

        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                response_payload = self._parse_response_payload(
                    response, response_text
                )

                if response.status >= 400:
                    raise RuntimeError(
                        f"Worker 返回错误状态 {response.status}: {response_text[:500]}"
                    )

                logger.info(
                    f"[{trace_id}] Worker 绑定验证成功: platform={platform}, group={group_id}, status={response.status}"
                )
                return response_payload

    def _build_bind_verify_url(self) -> str:
        base_url = self.config_manager.get_web_blog_worker_base_url().rstrip("/")
        path = self.config_manager.get_web_blog_worker_bind_verify_path().strip()
        if not path:
            path = "/api/auth/bind/verify"
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base_url}{path}"

    @staticmethod
    def _parse_response_payload(
        response: aiohttp.ClientResponse, response_text: str
    ) -> dict[str, Any]:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "application/json" in content_type:
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict):
                    return parsed
                return {"data": parsed}
            except Exception:
                pass

        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed, "raw": response_text}
        except Exception:
            return {"raw": response_text}
