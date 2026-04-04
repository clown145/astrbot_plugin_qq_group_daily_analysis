"""将插件分析结果转换为博客发布协议。"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import (
    BlogExportPackageV1,
    CoverageMetadata,
    DailyBucket,
    HourlyBucket,
    ProducerMetadata,
    PublishPayloadV1,
    RenderBundleMetadata,
    ReportMetadata,
    ReportRenderBundleV1,
    StatsPayload,
    TargetMetadata,
    TopUserPayload,
)
from .serializer import to_jsonable


class BlogExportBuilder:
    """博客导出构建器。

    负责把现有 `analysis_result` 与其上下文整理为：
    - publish_payload_v1
    - report_render_bundle_v1
    """

    def __init__(
        self,
        config_manager: Any,
        report_generator: Any,
        producer_name: str = "astrbot_plugin_qq_group_daily_analysis",
    ):
        self.config_manager = config_manager
        self.report_generator = report_generator
        self.producer = ProducerMetadata(name=producer_name)

    async def build_package_from_result(
        self,
        result: dict[str, Any],
        *,
        avatar_url_getter=None,
        nickname_getter=None,
    ) -> BlogExportPackageV1:
        analysis_result = result["analysis_result"]
        context = dict(result.get("analysis_context") or {})
        timezone_name = context.get("timezone") or self._get_local_timezone_name()

        target = TargetMetadata(
            platform=str(result.get("platform_id") or context.get("platform") or ""),
            group_id=str(result["group_id"]),
            group_name=str(context.get("group_name") or ""),
            timezone=timezone_name,
        )
        report_meta = self._build_report_metadata(
            context=context,
            timezone_name=timezone_name,
        )
        coverage = self._build_coverage_metadata(
            context=context,
            report_kind=report_meta.report_kind,
        )
        stats_payload = self._build_stats_payload(analysis_result)
        publish_payload = PublishPayloadV1(
            producer=self.producer,
            target=target,
            report=report_meta,
            coverage=coverage,
            stats=stats_payload,
            activity={
                "hourly_buckets": self._build_hourly_buckets(analysis_result),
                "daily_buckets": self._build_daily_buckets(analysis_result),
            },
            users={
                "top_users": self._build_top_users(
                    analysis_result=analysis_result,
                    platform=target.platform,
                    group_id=target.group_id,
                )
            },
            topics=self._build_topic_summaries(analysis_result),
            quotes=self._build_quote_summaries(analysis_result),
            chat_quality_review=self._build_chat_quality_review(analysis_result),
            raw_flags={
                "contains_llm_output": True,
                "contains_raw_messages": False,
                "contains_embedded_avatar_data": True,
            },
        )

        render_bundle = await self._build_render_bundle(
            analysis_result=analysis_result,
            report_meta=report_meta,
            target=target,
            avatar_url_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
        )

        return BlogExportPackageV1(
            publish_payload=publish_payload,
            render_bundle=render_bundle,
        )

    async def build_serialized_package_from_result(
        self,
        result: dict[str, Any],
        *,
        avatar_url_getter=None,
        nickname_getter=None,
    ) -> dict[str, Any]:
        package = await self.build_package_from_result(
            result,
            avatar_url_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
        )
        return to_jsonable(package)

    def _build_report_metadata(
        self,
        *,
        context: dict[str, Any],
        timezone_name: str,
    ) -> ReportMetadata:
        tzinfo = self._get_tzinfo(timezone_name)
        generated_dt = datetime.now(tzinfo)
        requested_days = self._to_int(context.get("requested_days"))
        source_mode = str(context.get("source_mode") or "manual")
        report_kind = self._determine_report_kind(
            analysis_kind=str(context.get("analysis_kind") or "daily"),
            requested_days=requested_days,
            source_mode=source_mode,
        )

        window_start = self._timestamp_to_iso(context.get("window_start_timestamp"), tzinfo)
        window_end = self._timestamp_to_iso(context.get("window_end_timestamp"), tzinfo)

        snapshot_date = None
        if report_kind == "daily_snapshot":
            ts = context.get("window_end_timestamp") or context.get("window_start_timestamp")
            snapshot_date = self._timestamp_to_date(ts, tzinfo) or generated_dt.date().isoformat()

        return ReportMetadata(
            report_kind=report_kind,
            source_mode=source_mode,
            snapshot_date=snapshot_date,
            window_start=window_start,
            window_end=window_end,
            generated_at=generated_dt.isoformat(),
            requested_days=requested_days,
            publish_as_official_snapshot=report_kind == "daily_snapshot",
        )

    @staticmethod
    def _determine_report_kind(
        *,
        analysis_kind: str,
        requested_days: int | None,
        source_mode: str,
    ) -> str:
        if analysis_kind == "daily" and requested_days == 1 and source_mode == "scheduled":
            return "daily_snapshot"
        if analysis_kind == "daily" and requested_days and requested_days > 1:
            return "range_report"
        if analysis_kind == "incremental_final":
            return "range_report"
        return "preview_report"

    @staticmethod
    def _build_coverage_metadata(
        *,
        context: dict[str, Any],
        report_kind: str,
    ) -> CoverageMetadata:
        message_limit_hit = context.get("message_limit_hit")
        coverage_status = "unknown"
        if message_limit_hit is True:
            coverage_status = "truncated" if report_kind == "daily_snapshot" else "partial"
        elif message_limit_hit is False and report_kind == "daily_snapshot":
            coverage_status = "full"
        elif report_kind in {"range_report", "preview_report"}:
            coverage_status = "partial"

        return CoverageMetadata(
            coverage_status=coverage_status,
            message_limit_hit=message_limit_hit,
            fetched_message_count=BlogExportBuilder._to_int(context.get("raw_message_count")),
            analyzed_message_count=BlogExportBuilder._to_int(context.get("cleaned_message_count")),
            dropped_message_count=BlogExportBuilder._to_int(context.get("dropped_message_count")),
            notes=[],
        )

    @staticmethod
    def _build_stats_payload(analysis_result: dict[str, Any]) -> StatsPayload:
        stats = analysis_result["statistics"]
        user_analysis = analysis_result.get("user_analysis") or {}
        token_usage = getattr(stats, "token_usage", None)

        return StatsPayload(
            message_count=int(getattr(stats, "message_count", 0) or 0),
            participant_count=int(getattr(stats, "participant_count", 0) or 0),
            active_user_count=max(
                int(getattr(stats, "participant_count", 0) or 0),
                len(user_analysis),
            ),
            total_characters=int(getattr(stats, "total_characters", 0) or 0),
            emoji_count=int(getattr(stats, "emoji_count", 0) or 0),
            most_active_period=str(getattr(stats, "most_active_period", "") or ""),
            total_tokens=int(getattr(token_usage, "total_tokens", 0) or 0),
            prompt_tokens=int(getattr(token_usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(token_usage, "completion_tokens", 0) or 0),
        )

    @staticmethod
    def _build_hourly_buckets(analysis_result: dict[str, Any]) -> list[HourlyBucket]:
        stats = analysis_result["statistics"]
        activity_viz = getattr(stats, "activity_visualization", None)
        hourly_map = BlogExportBuilder._normalize_map(
            getattr(activity_viz, "hourly_activity", {})
        )
        return [
            HourlyBucket(hour=hour, message_count=hourly_map.get(hour, 0))
            for hour in range(24)
        ]

    @staticmethod
    def _build_daily_buckets(analysis_result: dict[str, Any]) -> list[DailyBucket]:
        stats = analysis_result["statistics"]
        activity_viz = getattr(stats, "activity_visualization", None)
        daily_map = BlogExportBuilder._normalize_map(
            getattr(activity_viz, "daily_activity", {})
        )
        return [
            DailyBucket(date=str(day), message_count=int(count))
            for day, count in sorted(daily_map.items())
        ]

    def _build_top_users(
        self,
        *,
        analysis_result: dict[str, Any],
        platform: str,
        group_id: str,
        limit: int = 10,
    ) -> list[TopUserPayload]:
        user_analysis = analysis_result.get("user_analysis") or {}
        ranked_users = sorted(
            user_analysis.items(),
            key=lambda item: int(item[1].get("message_count", 0)),
            reverse=True,
        )

        users: list[TopUserPayload] = []
        for user_id, stats in ranked_users[:limit]:
            hours = {
                int(hour): int(count)
                for hour, count in (stats.get("hours") or {}).items()
            }
            message_count = int(stats.get("message_count", 0) or 0)
            night_messages = sum(hours.get(hour, 0) for hour in range(0, 6))
            night_ratio = (night_messages / message_count) if message_count else 0.0
            most_active_hour = max(hours, key=hours.get) if hours else None
            display_name = (
                str(stats.get("nickname") or stats.get("name") or user_id).strip()
            )

            users.append(
                TopUserPayload(
                    user_hash=self._hash_user(platform, group_id, str(user_id)),
                    display_name=display_name,
                    user_id=str(user_id),
                    message_count=message_count,
                    char_count=int(stats.get("char_count", 0) or 0),
                    emoji_count=int(stats.get("emoji_count", 0) or 0),
                    reply_count=int(stats.get("reply_count", 0) or 0),
                    most_active_hour=most_active_hour,
                    night_ratio=round(night_ratio, 4),
                )
            )

        return users

    @staticmethod
    def _build_topic_summaries(analysis_result: dict[str, Any]) -> list[dict[str, Any]]:
        topics = analysis_result.get("topics") or []
        summaries = []
        for topic in topics:
            name = getattr(topic, "name", getattr(topic, "topic", "未知话题"))
            contributors = list(getattr(topic, "contributors", []) or [])
            summaries.append(
                {
                    "name": str(name),
                    "contributors": contributors,
                    "detail": str(getattr(topic, "detail", "") or ""),
                }
            )
        return summaries

    @staticmethod
    def _build_quote_summaries(analysis_result: dict[str, Any]) -> list[dict[str, Any]]:
        stats = analysis_result["statistics"]
        golden_quotes = getattr(stats, "golden_quotes", []) or []
        return [
            {
                "content": str(getattr(quote, "content", "") or ""),
                "sender": str(getattr(quote, "sender", "") or ""),
                "reason": str(getattr(quote, "reason", "") or ""),
                "user_id": str(getattr(quote, "user_id", "") or ""),
            }
            for quote in golden_quotes
        ]

    @staticmethod
    def _build_chat_quality_review(
        analysis_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        review = analysis_result.get("chat_quality_review")
        if not review:
            stats = analysis_result["statistics"]
            review = getattr(stats, "chat_quality_review", None)

        if not review:
            return None

        if hasattr(review, "dimensions"):
            return {
                "title": review.title,
                "subtitle": review.subtitle,
                "dimensions": [
                    {
                        "name": item.name,
                        "percentage": item.percentage,
                        "comment": item.comment,
                        "color": item.color,
                    }
                    for item in review.dimensions
                ],
                "summary": review.summary,
            }

        return dict(review)

    async def _build_render_bundle(
        self,
        *,
        analysis_result: dict[str, Any],
        report_meta: ReportMetadata,
        target: TargetMetadata,
        avatar_url_getter=None,
        nickname_getter=None,
    ) -> ReportRenderBundleV1:
        template_meta = self.report_generator.get_active_template_metadata()
        render_context = await self.report_generator.build_report_render_bundle(
            analysis_result,
            avatar_url_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
        )
        report_id = uuid.uuid4().hex

        return ReportRenderBundleV1(
            report_meta=RenderBundleMetadata(
                report_id=report_id,
                platform=target.platform,
                group_id=target.group_id,
                group_name=target.group_name,
                report_kind=report_meta.report_kind,
                source_mode=report_meta.source_mode,
                snapshot_date=report_meta.snapshot_date,
                template_name=template_meta["template_name"],
                layout_template_name=template_meta["layout_template_name"],
                template_version=template_meta["template_version"],
                timezone=target.timezone,
                generated_at=report_meta.generated_at,
            ),
            render_context=render_context,
            assets=self._extract_assets(render_context),
        )

    @staticmethod
    def _extract_assets(render_context: dict[str, Any]) -> dict[str, Any]:
        avatars = {}

        def register_avatar(user_id: str, avatar_data: str | None):
            if not avatar_data or not avatar_data.startswith("data:"):
                return
            digest = hashlib.sha256(avatar_data.encode("utf-8")).hexdigest()[:16]
            if digest in avatars:
                return
            content_type = avatar_data.split(";", 1)[0].removeprefix("data:")
            avatars[digest] = {
                "asset_id": f"avatar_{digest}",
                "user_id": user_id,
                "content_type": content_type,
                "data_uri": avatar_data,
            }

        for title in render_context.get("titles", []):
            register_avatar(str(title.get("user_id", "")), title.get("avatar_data"))

        for quote in render_context.get("quotes", []):
            register_avatar(str(quote.get("user_id", "")), quote.get("avatar_url"))

        return {"avatars": list(avatars.values())}

    @staticmethod
    def _normalize_map(data: Any) -> dict[Any, Any]:
        if isinstance(data, dict):
            return data
        try:
            return dict(data)
        except Exception:
            return {}

    @staticmethod
    def _hash_user(platform: str, group_id: str, user_id: str) -> str:
        raw = f"{platform}:{group_id}:{user_id}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _get_tzinfo(timezone_name: str):
        try:
            return ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            return datetime.now().astimezone().tzinfo

    @staticmethod
    def _get_local_timezone_name() -> str:
        tz_name = os.environ.get("TZ")
        if tz_name:
            return tz_name

        local_tz = datetime.now().astimezone().tzinfo
        if local_tz and getattr(local_tz, "key", None):
            return str(local_tz.key)
        if local_tz:
            return str(local_tz)
        return "UTC"

    @staticmethod
    def _timestamp_to_iso(timestamp: Any, tzinfo) -> str | None:
        ts = BlogExportBuilder._to_int(timestamp)
        if ts is None:
            return None
        return datetime.fromtimestamp(ts, tz=tzinfo).isoformat()

    @staticmethod
    def _timestamp_to_date(timestamp: Any, tzinfo) -> str | None:
        ts = BlogExportBuilder._to_int(timestamp)
        if ts is None:
            return None
        return datetime.fromtimestamp(ts, tz=tzinfo).date().isoformat()
