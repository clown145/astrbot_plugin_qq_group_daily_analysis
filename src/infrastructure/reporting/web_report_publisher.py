"""
网页报告发布器
负责将渲染后的 HTML 上传到 Cloudflare Worker，并返回公开链接。
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

import aiohttp

from ...utils.logger import logger


class WebReportPublisher:
    """网页报告上传器。"""

    def __init__(self, config_manager):
        self.config_manager = config_manager

    def is_enabled(self) -> bool:
        """检查网页报告功能是否启用且配置完整。"""
        return not self.get_missing_requirements()

    def get_missing_requirements(self) -> list[str]:
        """返回未满足的配置项。"""
        missing = []
        if not self.config_manager.get_web_report_enabled():
            missing.append("web_report.enabled")
        if not self.config_manager.get_web_report_api_base():
            missing.append("web_report.worker_api_base")
        if not self.config_manager.get_web_report_upload_token():
            missing.append("web_report.upload_token")
        return missing

    async def publish_report(
        self,
        html_content: str,
        *,
        group_id: str,
        platform_id: str | None,
        template_name: str,
    ) -> str | None:
        """上传 HTML 报告并返回公开链接。"""
        missing = self.get_missing_requirements()
        if missing:
            logger.warning(f"网页报告功能未就绪，缺少配置: {', '.join(missing)}")
            return None

        api_base = self.config_manager.get_web_report_api_base().rstrip("/")
        upload_url = f"{api_base}/api/internal/reports"
        payload = {
            "html": html_content,
            "platform_id": platform_id or "",
            "group_id": str(group_id),
            "template": template_name,
            "ttl_seconds": self.config_manager.get_web_report_ttl_days() * 86400,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        headers = {
            "Authorization": (
                f"Bearer {self.config_manager.get_web_report_upload_token()}"
            ),
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(
            total=self.config_manager.get_web_report_timeout_seconds()
        )

        try:
            async with aiohttp.ClientSession(
                timeout=timeout, trust_env=True
            ) as session:
                async with session.post(
                    upload_url, json=payload, headers=headers
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(
                            f"网页报告上传失败: HTTP {resp.status}, body={body[:300]}"
                        )
                        return None

                    result = await resp.json()
                    if not result.get("ok"):
                        logger.error(f"网页报告上传失败: {result}")
                        return None

                    url = result.get("url")
                    if url:
                        return str(url)

                    report_id = result.get("report_id")
                    if not report_id:
                        logger.error(f"网页报告上传返回缺少 report_id: {result}")
                        return None

                    return self._build_public_url(str(report_id))
        except Exception as e:
            logger.error(f"网页报告上传异常: {e}", exc_info=True)
            return None

    def build_share_message(self, public_url: str) -> str:
        """构造群内发送的链接文案。"""
        return f"📊 每日群聊分析报告：\n{public_url}"

    def _build_public_url(self, report_id: str) -> str:
        base = self.config_manager.get_web_report_public_base_url()
        if not base:
            base = self.config_manager.get_web_report_api_base()
        return urljoin(base.rstrip("/") + "/", f"r/{report_id}")
