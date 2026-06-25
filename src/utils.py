from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Iterable


def to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip().replace(",", "").replace("，", "")
    if not text or text in {"-", "—", "无", "nan", "None"}:
        return None
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else None


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip().replace(",", "").replace("，", "")
    if not text or text in {"-", "—", "无", "nan", "None"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def split_keywords(text: str | Iterable[str] | None) -> list[str]:
    if text is None:
        return []
    if isinstance(text, str):
        parts = re.split(r"[,，;；\n\r]+", text)
    else:
        parts = list(text)
    return [str(item).strip() for item in parts if str(item).strip()]


def safe_read_csv(path: Path):
    import pandas as pd

    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.DataFrame()


def append_warning(existing: Any, warning: str) -> str:
    warnings = split_keywords(existing)
    if warning and warning not in warnings:
        warnings.append(warning)
    return "；".join(warnings)
