from __future__ import annotations

from typing import Any

from .utils import split_keywords


HIGH_RISK_PATTERNS = {
    "只招男生": "性别限制：只招男生",
    "只招女生": "性别限制：只招女生",
    "色盲": "身体条件限制：色盲相关要求",
    "色弱": "身体条件限制：色弱相关要求",
    "单科": "单科成绩要求",
    "口试": "外语口试要求",
    "身高": "身高要求",
    "视力": "视力要求",
    "体检": "体检要求",
    "政审": "政审要求",
    "面试": "面试要求",
    "体能": "体能测试要求",
}


def merge_warnings(*values: Any) -> str:
    merged: list[str] = []
    for value in values:
        for item in split_keywords(value):
            if item and item not in merged:
                merged.append(item)
    return "；".join(merged)


def collect_text_warnings(*texts: Any) -> list[str]:
    text = " ".join(str(item or "") for item in texts)
    warnings: list[str] = []
    for pattern, message in HIGH_RISK_PATTERNS.items():
        if pattern in text and message not in warnings:
            warnings.append(message)
    return warnings
