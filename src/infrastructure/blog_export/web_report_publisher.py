"""Web 博客报告发布器。"""

from __future__ import annotations

import json
from typing import Any

import aiohttp

from ...shared.trace_context import TraceContext
from ...utils.logger import logger


class WebReportPublisher:
    """负责把博客发布协议上传到 Worker。"""

    def __init__(self, config_manager: Any, blog_export_builder: Any):
        self.config_manager = config_manager
        self.blog_export_builder = blog_export_builder

    def validate_config(self) -> tuple[bool, str | None]:
        """检查 Web 发布配置是否完整。"""
        if not self.config_manager.get_web_blog_enabled():
            return False, "Web 博客发布开关未启用"

        if not self.config_manager.get_web_blog_worker_base_url():
            return False, "未配置 Worker 基础地址"

        if not self.config_manager.get_web_blog_worker_token():
            return False, "未配置 Worker 上传密钥"

        return True, None

    async def build_package(self, result: dict[str, Any]) -> dict[str, Any]:
        """从分析结果构建上传数据包。"""
        group_id = result["group_id"]
        adapter = result["adapter"]

        async def avatar_url_getter(user_id: str) -> str | None:
            return await adapter.get_user_avatar_url(user_id)

        async def nickname_getter(user_id: str) -> str | None:
            try:
                member = await adapter.get_member_info(group_id, user_id)
                if member:
                    return member.card or member.nickname
            except Exception:
                pass
            return None

        return await self.blog_export_builder.build_serialized_package_from_result(
            result,
            avatar_url_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
        )

    async def publish_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """构建并上传分析结果到 Worker。"""
        config_ok, config_error = self.validate_config()
        if not config_ok:
            raise RuntimeError(config_error or "Web 博客发布配置无效")

        payload = await self.build_package(result)
        ingest_url = self._build_ingest_url()
        token = self.config_manager.get_web_blog_worker_token()
        timeout_seconds = max(
            10, self.config_manager.get_web_blog_request_timeout_seconds()
        )
        trace_id = TraceContext.get()

        logger.info(
            f"[{trace_id}] 正在上传 Web 博客数据包: group={result.get('group_id')}, url={ingest_url}"
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "astrbot-group-daily-analysis/web-export",
        }
        if trace_id:
            headers["X-AstrBot-Trace-Id"] = trace_id

        timeout = aiohttp.ClientTimeout(total=timeout_seconds)

        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.post(
                ingest_url,
                json=payload,
                headers=headers,
            ) as response:
                response_text = await response.text()
                response_payload = self._parse_response_payload(
                    response, response_text
                )

                if response.status >= 400:
                    raise RuntimeError(
                        f"Worker 返回错误状态 {response.status}: {response_text[:500]}"
                    )

                logger.info(
                    f"[{trace_id}] Web 博客数据包上传成功: group={result.get('group_id')}, status={response.status}"
                )
                return response_payload

    def build_success_message(self, response_payload: dict[str, Any]) -> str:
        """构造发回群里的成功提示。"""
        lines = ["🌐 Web 报告已发布"]

        report_url = self._pick_first_url(
            response_payload, "report_url", "daily_report_url", "url"
        )
        blog_url = self._pick_first_url(
            response_payload, "blog_url", "group_url", "home_url"
        )
        archive_url = self._pick_first_url(response_payload, "archive_url")

        if report_url:
            lines.append(f"日报页面: {report_url}")
        if blog_url and blog_url != report_url:
            lines.append(f"群博客首页: {blog_url}")
        if archive_url and archive_url not in {report_url, blog_url}:
            lines.append(f"历史归档: {archive_url}")

        if len(lines) == 1:
            lines.append("Worker 已接收数据，但未返回可展示链接。")

        return "\n".join(lines)

    def _build_ingest_url(self) -> str:
        base_url = self.config_manager.get_web_blog_worker_base_url().rstrip("/")
        ingest_path = self.config_manager.get_web_blog_worker_ingest_path().strip()
        if not ingest_path:
            ingest_path = "/api/ingest"
        if not ingest_path.startswith("/"):
            ingest_path = f"/{ingest_path}"
        return f"{base_url}{ingest_path}"

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

    @staticmethod
    def _pick_first_url(response_payload: dict[str, Any], *keys: str) -> str | None:
        nested_candidates = []
        urls_obj = response_payload.get("urls")
        if isinstance(urls_obj, dict):
            nested_candidates.append(urls_obj)

        data_obj = response_payload.get("data")
        if isinstance(data_obj, dict):
            nested_candidates.append(data_obj)
            nested_urls = data_obj.get("urls")
            if isinstance(nested_urls, dict):
                nested_candidates.append(nested_urls)

        for key in keys:
            value = response_payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

            for nested in nested_candidates:
                nested_value = nested.get(key)
                if isinstance(nested_value, str) and nested_value.strip():
                    return nested_value.strip()
        return None
