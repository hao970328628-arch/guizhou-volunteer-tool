from __future__ import annotations

from typing import Any

from .warnings import collect_text_warnings, merge_warnings


CHARTER_RISK_PATTERNS = {
    "招生章程": "请核验高校招生章程",
    "转氨酶": "体检指标要求需核验",
    "肝功能": "体检指标要求需核验",
    "色盲": "色觉限制需核验",
    "色弱": "色觉限制需核验",
    "嗅觉": "嗅觉要求需核验",
    "左利手": "左利手限制需核验",
    "口吃": "语言表达限制需核验",
    "英语": "外语语种/英语成绩要求需核验",
    "数学": "单科数学成绩要求需核验",
    "语文": "单科语文成绩要求需核验",
    "外语": "外语语种或口试要求需核验",
    "入学后": "入学复查或培养要求需核验",
    "不予录取": "存在不予录取条件，必须人工核验",
}


def collect_charter_risks(*texts: Any) -> list[str]:
    text = " ".join(str(item or "") for item in texts)
    warnings = collect_text_warnings(text)
    for pattern, message in CHARTER_RISK_PATTERNS.items():
        if pattern in text and message not in warnings:
            warnings.append(message)
    return warnings


def append_charter_risks(existing: Any, *texts: Any) -> str:
    return merge_warnings(existing, collect_charter_risks(*texts))
