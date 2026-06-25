from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from .config import DEFAULT_RISK_THRESHOLDS
from .utils import to_int


@dataclass
class RiskResult:
    risk_level: str
    risk_score: float | None
    rank_gap: int | None
    rank_gap_pct: float | None
    volatility: float | None = None
    warnings: list[str] = field(default_factory=list)
    risk_reason: str = ""


def _thresholds(thresholds: dict[str, tuple[float, float]] | None) -> dict[str, tuple[float, float]]:
    return thresholds or DEFAULT_RISK_THRESHOLDS


def _level_from_pct(rank_gap_pct: float, thresholds: dict[str, tuple[float, float]]) -> str:
    for level in ["冲", "稳", "保", "垫"]:
        low, high = thresholds[level]
        if level == "垫":
            if rank_gap_pct > low and rank_gap_pct <= high:
                return level
        elif low <= rank_gap_pct < high or (level == "稳" and low <= rank_gap_pct <= high):
            return level
    return "不可推荐"


def _downgrade_level(level: str) -> str:
    order = ["冲", "稳", "保", "垫"]
    if level not in order:
        return level
    index = min(order.index(level) + 1, len(order) - 1)
    return order[index]


def classify_risk(
    student_rank: Any,
    historical_min_rank: Any,
    thresholds: dict[str, tuple[float, float]] | None = None,
    student_score: Any = None,
    historical_min_score: Any = None,
    plan_count_2026: Any = None,
    admission_plan_count_2025: Any = None,
    admission_count_2025: Any = None,
    rank_2024: Any = None,
) -> RiskResult:
    rank = to_int(student_rank)
    historical_rank = to_int(historical_min_rank)
    if not rank or rank <= 0:
        return RiskResult("缺少位次", None, None, None, risk_reason="请补充全省位次，或导入一分一段表。")
    if not historical_rank or historical_rank <= 0:
        return RiskResult("缺少历史数据", None, None, None, risk_reason="2026 目录存在该专业，但缺少可用历史投档位次。")

    thresholds = _thresholds(thresholds)
    rank_gap = historical_rank - rank
    rank_gap_pct = rank_gap / rank
    level = _level_from_pct(rank_gap_pct, thresholds)
    warnings: list[str] = []

    plan_2026 = to_int(plan_count_2026)
    if plan_2026 is not None and plan_2026 <= 2:
        warnings.append("小计划数，波动风险较大")

    plan_2025 = to_int(admission_plan_count_2025)
    count_2025 = to_int(admission_count_2025)
    if plan_2025 and count_2025 is not None and count_2025 < plan_2025:
        warnings.append("可能存在缺额/断档，谨慎参考")

    volatility = None
    rank_2024_int = to_int(rank_2024)
    original_level = level
    if rank_2024_int:
        volatility = abs(historical_rank - rank_2024_int) / rank
        if volatility > 0.2:
            warnings.append("近两年位次波动超过20%，需降低确定性判断")
            level = _downgrade_level(level)

    pct_text = f"{rank_gap_pct:+.1%}"
    plan_text = f"；该专业 2026 年计划数 {plan_2026} 人" if plan_2026 is not None else ""
    history_text = "，历史数据完整" if rank_2024_int else "，仅使用 2025 年数据"
    volatility_text = f"；两年波动 {volatility:.1%}，风险等级由{original_level}调整为{level}" if volatility and volatility > 0.2 else ""
    reason = f"2025 年最低位次 {historical_rank}，考生位次 {rank}，位次差 {pct_text}，属于{level}{plan_text}{history_text}{volatility_text}。"
    return RiskResult(level, rank_gap_pct, rank_gap, rank_gap_pct, volatility, warnings, reason)


def risk_sort_value(level: str) -> int:
    return {"冲": 1, "稳": 2, "保": 3, "垫": 4, "缺少历史数据": 5, "不可推荐": 99}.get(level, 50)
