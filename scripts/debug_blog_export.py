import argparse
import asyncio
import os
import sys
import types
import uuid
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
plugin_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, plugin_root)

astrbot_api = types.ModuleType("astrbot.api")


class MockLogger:
    def info(self, msg, *args, **kwargs):
        print(f"[INFO] {msg}")

    def error(self, msg, *args, **kwargs):
        print(f"[ERROR] {msg}")

    def warning(self, msg, *args, **kwargs):
        print(f"[WARN] {msg}")

    def debug(self, msg, *args, **kwargs):
        print(f"[DEBUG] {msg}")


astrbot_api.logger = MockLogger()
astrbot_api.AstrBotConfig = dict
sys.modules["astrbot.api"] = astrbot_api

astrbot_core_utils = types.ModuleType("astrbot.core.utils")
astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")
astrbot_path.get_astrbot_data_path = lambda: Path(".")
sys.modules["astrbot.core.utils"] = astrbot_core_utils
sys.modules["astrbot.core.utils.astrbot_path"] = astrbot_path

ulid_module = types.ModuleType("ulid")


class _MockUlidValue:
    def __str__(self):
        return uuid.uuid4().hex


ulid_module.new = lambda: _MockUlidValue()
sys.modules["ulid"] = ulid_module

markupsafe_module = types.ModuleType("markupsafe")


class MockMarkup(str):
    pass


markupsafe_module.Markup = MockMarkup
sys.modules["markupsafe"] = markupsafe_module

from src.application.blog_export import BlogExportBuilder, dump_json  # noqa: E402
from src.domain.models.data_models import (  # noqa: E402
    ActivityVisualization,
    EmojiStatistics,
    GoldenQuote,
    GroupStatistics,
    QualityDimension,
    QualityReview,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)


class MockConfigManager:
    def __init__(self, template_name: str = "scrapbook") -> None:
        self.template_name = template_name

    def get_report_template(self) -> str:
        return self.template_name

    def get_max_topics(self) -> int:
        return 8

    def get_max_user_titles(self) -> int:
        return 8

    def get_max_golden_quotes(self) -> int:
        return 8

    def get_pdf_output_dir(self) -> str:
        return "data/pdf"

    def get_pdf_filename_format(self) -> str:
        return "report_{group_id}_{date}.pdf"

    def get_enable_user_card(self) -> bool:
        return True

    @property
    def playwright_available(self) -> bool:
        return True

    def get_browser_path(self) -> str:
        return ""

    def get_t2i_max_concurrent(self) -> int:
        return 2

    def get_llm_max_concurrent(self) -> int:
        return 2


async def mock_get_user_avatar(user_id: str) -> str:
    return f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=100"


class FakeReportGenerator:
    def __init__(self, config_manager) -> None:
        self.config_manager = config_manager

    def get_active_template_metadata(self) -> dict[str, str]:
        return {
            "template_name": self.config_manager.get_report_template(),
            "layout_template_name": "html_template.html",
            "template_version": "debug-template",
        }

    async def build_report_render_bundle(
        self,
        analysis_result: dict,
        avatar_url_getter=None,
        nickname_getter=None,
    ) -> dict:
        stats = analysis_result["statistics"]
        topics = []
        for index, topic in enumerate(analysis_result.get("topics", []), 1):
            topics.append(
                {
                    "index": index,
                    "topic": {
                        "topic": topic.topic,
                        "contributors": topic.contributors,
                        "detail": topic.detail,
                    },
                    "contributors": "、".join(topic.contributors),
                    "detail": topic.detail,
                }
            )

        titles = []
        for title in analysis_result.get("user_titles", []):
            titles.append(
                {
                    "name": title.name,
                    "user_id": title.user_id,
                    "title": title.title,
                    "mbti": title.mbti,
                    "reason": title.reason,
                    "avatar_data": "data:image/png;base64,ZmFrZQ==",
                }
            )

        quotes = []
        for quote in getattr(stats, "golden_quotes", []):
            quotes.append(
                {
                    "content": quote.content,
                    "sender": quote.sender,
                    "reason": quote.reason,
                    "user_id": quote.user_id,
                    "avatar_url": "data:image/png;base64,ZmFrZQ==",
                }
            )

        chart_data = []
        for hour in range(24):
            count = stats.activity_visualization.hourly_activity.get(hour, 0)
            chart_data.append({"hour": hour, "count": count, "percentage": count})

        review = analysis_result.get("chat_quality_review")
        chat_quality_review = None
        if review:
            chat_quality_review = {
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

        return {
            "current_date": "2026年04月03日",
            "current_datetime": "2026-04-03 23:59:59",
            "message_count": stats.message_count,
            "participant_count": stats.participant_count,
            "total_characters": stats.total_characters,
            "emoji_count": stats.emoji_count,
            "most_active_period": stats.most_active_period,
            "topics": topics,
            "titles": titles,
            "quotes": quotes,
            "chart_data": chart_data,
            "chat_quality_review": chat_quality_review,
            "token_usage": {
                "total_tokens": stats.token_usage.total_tokens,
                "prompt_tokens": stats.token_usage.prompt_tokens,
                "completion_tokens": stats.token_usage.completion_tokens,
            },
        }


def build_mock_result():
    golden_quotes = [
        GoldenQuote(
            content="代码写得好，下班走得早。",
            sender="张三",
            reason="深刻揭示了程序员的生存法则",
            user_id="123456789",
        )
    ]
    stats = GroupStatistics(
        message_count=1250,
        total_characters=45000,
        participant_count=42,
        most_active_period="20:00 - 22:00",
        golden_quotes=golden_quotes,
        emoji_count=156,
        emoji_statistics=EmojiStatistics(face_count=100, mface_count=56),
        activity_visualization=ActivityVisualization(
            hourly_activity={i: (8 + i * 4 if i < 12 else 120 - i * 3) for i in range(24)},
            daily_activity={"2026-04-01": 980, "2026-04-02": 1102, "2026-04-03": 1250},
        ),
        token_usage=TokenUsage(
            prompt_tokens=1500, completion_tokens=800, total_tokens=2300
        ),
        chat_quality_review=QualityReview(
            title="高活跃轻松群",
            subtitle="夜间讨论明显升温",
            dimensions=[
                QualityDimension(
                    "水群闲聊",
                    44.0,
                    "聊天非常密集，轻松内容占比较高。",
                    "#607d8b",
                ),
                QualityDimension(
                    "技术探讨",
                    25.5,
                    "有稳定技术讨论，但不是唯一主线。",
                    "#2196f3",
                ),
            ],
            summary="整体活跃、互动顺滑，夜间最热。",
        ),
    )

    topics = [
        SummaryTopic(
            topic="关于 AstrBot 插件开发的讨论",
            contributors=["张三", "李四", "王五"],
            detail="大家围绕 [123456789] 提到的模板渲染方案展开了深入讨论。",
        ),
        SummaryTopic(
            topic="午餐吃什么",
            contributors=["赵六", "孙七"],
            detail="[112233445] 强烈建议吃黄焖鸡，但最后还是没定下来。",
        ),
    ]

    user_titles = [
        UserTitle(
            name="张三",
            user_id="123456789",
            title="代码收割机",
            mbti="INTJ",
            reason="在很短时间内提交了大量高质量改动。",
        ),
        UserTitle(
            name="李四",
            user_id="987654321",
            title="群聊气氛组",
            mbti="ENFP",
            reason="总能接住冷笑话，让群里不冷场。",
        ),
    ]

    user_analysis = {
        "123456789": {
            "message_count": 138,
            "char_count": 4021,
            "emoji_count": 26,
            "nickname": "张三",
            "hours": {20: 20, 21: 22, 22: 31},
            "reply_count": 15,
        },
        "987654321": {
            "message_count": 92,
            "char_count": 2380,
            "emoji_count": 13,
            "nickname": "李四",
            "hours": {19: 14, 20: 19, 23: 10},
            "reply_count": 8,
        },
    }

    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles,
        "user_analysis": user_analysis,
        "chat_quality_review": stats.chat_quality_review,
    }

    return {
        "success": True,
        "analysis_result": analysis_result,
        "group_id": "123456",
        "platform_id": "onebot",
        "analysis_context": {
            "analysis_kind": "daily",
            "source_mode": "scheduled",
            "requested_days": 1,
            "raw_message_count": 1262,
            "cleaned_message_count": 1250,
            "dropped_message_count": 12,
            "message_limit_hit": False,
            "window_start_timestamp": 1775337600,
            "window_end_timestamp": 1775423999,
            "group_name": "测试群聊",
            "timezone": "Asia/Shanghai",
        },
    }


async def main():
    parser = argparse.ArgumentParser(description="导出博客数据包调试脚本")
    parser.add_argument(
        "-t", "--template", default="scrapbook", help="模板名，默认 scrapbook"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="scripts/output/debug_blog_export.json",
        help="输出文件路径",
    )
    args = parser.parse_args()

    config_manager = MockConfigManager(args.template)
    report_generator = FakeReportGenerator(config_manager)
    builder = BlogExportBuilder(config_manager, report_generator)
    result = build_mock_result()

    package = await builder.build_serialized_package_from_result(
        result,
        avatar_url_getter=mock_get_user_avatar,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dump_json(package), encoding="utf-8")
    print(f"已导出到: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
