"""博客导出协议的数据模型。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProducerMetadata:
    name: str
    version: str = "local"
    instance_id: str = ""


@dataclass(frozen=True)
class TargetMetadata:
    platform: str
    group_id: str
    group_name: str = ""
    timezone: str = "UTC"


@dataclass(frozen=True)
class ReportMetadata:
    report_kind: str
    source_mode: str
    snapshot_date: str | None
    window_start: str | None
    window_end: str | None
    generated_at: str
    requested_days: int | None = None
    publish_as_official_snapshot: bool = False


@dataclass(frozen=True)
class CoverageMetadata:
    coverage_status: str
    message_limit_hit: bool | None
    fetched_message_count: int | None
    analyzed_message_count: int | None
    dropped_message_count: int | None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StatsPayload:
    message_count: int
    participant_count: int
    active_user_count: int
    total_characters: int
    emoji_count: int
    most_active_period: str
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class HourlyBucket:
    hour: int
    message_count: int


@dataclass(frozen=True)
class DailyBucket:
    date: str
    message_count: int


@dataclass(frozen=True)
class TopUserPayload:
    user_hash: str
    display_name: str
    user_id: str
    message_count: int
    char_count: int
    emoji_count: int
    reply_count: int
    most_active_hour: int | None
    night_ratio: float


@dataclass(frozen=True)
class PublishPayloadV1:
    producer: ProducerMetadata
    target: TargetMetadata
    report: ReportMetadata
    coverage: CoverageMetadata
    stats: StatsPayload
    activity: dict[str, list[HourlyBucket] | list[DailyBucket]]
    users: dict[str, list[TopUserPayload]]
    topics: list[dict[str, Any]] = field(default_factory=list)
    quotes: list[dict[str, Any]] = field(default_factory=list)
    chat_quality_review: dict[str, Any] | None = None
    raw_flags: dict[str, bool] = field(default_factory=dict)
    schema_version: str = "publish_payload_v1"


@dataclass(frozen=True)
class RenderBundleMetadata:
    report_id: str
    platform: str
    group_id: str
    group_name: str
    report_kind: str
    source_mode: str
    snapshot_date: str | None
    template_name: str
    layout_template_name: str
    template_version: str
    timezone: str
    generated_at: str


@dataclass(frozen=True)
class ReportRenderBundleV1:
    report_meta: RenderBundleMetadata
    render_context: dict[str, Any]
    assets: dict[str, Any]
    schema_version: str = "report_render_bundle_v1"


@dataclass(frozen=True)
class BlogExportPackageV1:
    publish_payload: PublishPayloadV1
    render_bundle: ReportRenderBundleV1
    schema_version: str = "blog_export_package_v1"
