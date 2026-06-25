from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import PROCESSED_DIR
from .normalizer import normalize_text
from .utils import split_keywords


RULES_PATH = PROCESSED_DIR / "major_category_rules.json"


@lru_cache(maxsize=1)
def load_rules(path: str | Path = RULES_PATH) -> dict[str, dict[str, list[str]]]:
    path = Path(path)
    if not path.exists():
        return {"其他": {"其他": []}}
    return json.loads(path.read_text(encoding="utf-8"))


def classify_major(major_name: Any, rules: dict[str, dict[str, list[str]]] | None = None) -> tuple[str, str]:
    text = normalize_text(major_name)
    rules = rules or load_rules()
    for level1, children in rules.items():
        if level1 == "其他":
            continue
        for level2, keywords in children.items():
            if any(keyword and keyword in text for keyword in keywords):
                return level1, level2
    return "其他", "其他"


def filter_major(
    row: Any,
    selected_level1: list[str] | None = None,
    selected_level2: list[str] | None = None,
    white_keywords: str | list[str] | None = None,
    black_keywords: str | list[str] | None = None,
) -> bool:
    name = normalize_text(row.get("major_name", "") if hasattr(row, "get") else getattr(row, "major_name", ""))
    black = split_keywords(black_keywords)
    white = split_keywords(white_keywords)
    if any(keyword in name for keyword in black):
        return False
    if any(keyword in name for keyword in white):
        return True
    level1 = row.get("major_category_level1", "") if hasattr(row, "get") else getattr(row, "major_category_level1", "")
    level2 = row.get("major_category_level2", "") if hasattr(row, "get") else getattr(row, "major_category_level2", "")
    if selected_level2:
        return level2 in selected_level2
    if selected_level1:
        return level1 in selected_level1
    return True
