"""博客导出协议的序列化工具。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from markupsafe import Markup
except ModuleNotFoundError:  # pragma: no cover - 调试环境兼容
    Markup = str


def to_jsonable(value: Any) -> Any:
    """将导出对象转换为可 JSON 序列化的数据结构。"""
    if is_dataclass(value) and not isinstance(value, type):
        return {key: to_jsonable(val) for key, val in asdict(value).items()}

    if isinstance(value, dict):
        return {str(key): to_jsonable(val) for key, val in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Markup):
        return str(value)

    return value


def dump_json(value: Any, *, ensure_ascii: bool = False, indent: int = 2) -> str:
    """导出为 JSON 字符串。"""
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=ensure_ascii,
        indent=indent,
        sort_keys=False,
    )
