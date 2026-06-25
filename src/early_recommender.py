from __future__ import annotations

from typing import Any

import pandas as pd

from .charter_risk import collect_charter_risks
from .early_batch_parser import infer_special_type
from .risk_model import classify_risk


EARLY_OUTPUT_COLUMNS = [
    "批次段 A/B/C", "特殊类型", "院校名称", "专业名称", "2026 计划数", "2025 最低分", "2025 最低位次",
    "2024 最低分", "2024 最低位次", "是否需要体检", "是否需要政审", "是否需要面试", "是否需要体能测试",
    "是否有身高要求", "是否有视力要求", "是否有性别限制", "是否有单科成绩要求", "是否要求特殊类型控制线",
    "风险提示", "推荐说明",
]


def _stage_enabled(stage: str, profile: dict[str, Any]) -> bool:
    return profile.get(f"show_early_{stage}", True)


def _special_enabled(special_type: str, profile: dict[str, Any]) -> bool:
    mapping = {
        "军队院校": "accept_military",
        "公安类": "accept_police_judicial",
        "司法类": "accept_police_judicial",
        "航海类": "accept_navigation",
        "国家公费师范生": "accept_public_teacher",
        "优师专项": "accept_teacher_special",
        "国家免费医学生": "accept_free_medical",
        "综合评价": "accept_comprehensive",
        "定向": "accept_directional_early",
    }
    key = mapping.get(special_type)
    return True if key is None else bool(profile.get(key))


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "是", "需要", "有"}
    return bool(value)


def _attention_level(risk_level: str, has_restrictions: bool) -> str:
    if risk_level == "缺少历史数据":
        return "缺少历史数据"
    if has_restrictions:
        return "资格限制较多"
    if risk_level in {"稳", "保", "垫"}:
        return "可重点关注"
    if risk_level == "冲":
        return "可作为参考"
    return "风险较高"


def recommend_early(
    catalog_df: pd.DataFrame,
    early_2025_df: pd.DataFrame,
    early_2024_df: pd.DataFrame,
    user_profile: dict[str, Any],
) -> pd.DataFrame:
    if not user_profile.get("show_early_batch"):
        return pd.DataFrame(columns=EARLY_OUTPUT_COLUMNS)
    source = early_2025_df if not early_2025_df.empty else catalog_df
    if source.empty:
        return pd.DataFrame(columns=EARLY_OUTPUT_COLUMNS)

    rows: list[dict[str, Any]] = []
    for _, row in source.iterrows():
        subject = str(row.get("subject_group", ""))
        if user_profile.get("subject_group") and subject and subject != user_profile.get("subject_group"):
            continue
        stage = str(row.get("early_batch_stage") or row.get("batch_group", "")).replace("early_", "")
        if stage in {"A", "B", "C"} and not _stage_enabled(stage, user_profile):
            continue
        special_type = row.get("special_type") or infer_special_type(" ".join(str(row.get(k, "")) for k in ["enroll_type", "major_name", "raw_text"]))
        if not _special_enabled(special_type, user_profile):
            continue

        match_2024 = _match_early_2024(row, early_2024_df)
        risk = classify_risk(
            user_profile.get("student_rank"),
            row.get("min_rank"),
            rank_2024=match_2024.get("min_rank") if match_2024 else None,
        )
        restrictions = {
            "是否需要体检": _truthy(row.get("requires_physical_exam")),
            "是否需要政审": _truthy(row.get("requires_political_review")),
            "是否需要面试": _truthy(row.get("requires_interview")),
            "是否需要体能测试": _truthy(row.get("requires_fitness_test")),
            "是否有身高要求": _truthy(row.get("height_requirement")),
            "是否有视力要求": _truthy(row.get("vision_requirement")),
            "是否有性别限制": _truthy(row.get("gender_requirement")),
            "是否有单科成绩要求": _truthy(row.get("single_subject_requirement")),
            "是否要求特殊类型控制线": _truthy(row.get("requires_special_control_line")),
        }
        has_restrictions = any(restrictions.values())
        charter_warnings = collect_charter_risks(row.get("raw_text", ""), row.get("major_name", ""), row.get("warnings", ""))
        attention = _attention_level(risk.risk_level, has_restrictions)
        if user_profile.get("requires_early_checks") is False and has_restrictions:
            attention = "资格限制较多"
        rows.append(
            {
                "批次段 A/B/C": stage,
                "特殊类型": special_type,
                "院校名称": row.get("school_name", ""),
                "专业名称": row.get("major_name", ""),
                "2026 计划数": row.get("plan_count", ""),
                "2025 最低分": row.get("min_score", ""),
                "2025 最低位次": row.get("min_rank", ""),
                "2024 最低分": match_2024.get("min_score", "") if match_2024 else "",
                "2024 最低位次": match_2024.get("min_rank", "") if match_2024 else "",
                **restrictions,
                "风险提示": "；".join(risk.warnings + charter_warnings) or attention,
                "推荐说明": risk.risk_reason,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=EARLY_OUTPUT_COLUMNS)
    return result[EARLY_OUTPUT_COLUMNS]


def _match_early_2024(row: pd.Series, early_2024_df: pd.DataFrame) -> dict[str, Any] | None:
    if early_2024_df.empty:
        return None
    school_code = str(row.get("school_code", ""))
    major_code = str(row.get("major_code", ""))
    major_name = str(row.get("major_name_clean") or row.get("major_name", ""))
    stage = str(row.get("early_batch_stage", ""))
    for _, candidate in early_2024_df.iterrows():
        if (
            str(candidate.get("school_code", "")) == school_code
            and str(candidate.get("major_code", "")) == major_code
            and (not stage or str(candidate.get("early_batch_stage", "")) == stage)
        ):
            return candidate.to_dict()
    for _, candidate in early_2024_df.iterrows():
        if str(candidate.get("school_code", "")) == school_code and str(candidate.get("major_name_clean") or candidate.get("major_name", "")) == major_name:
            return candidate.to_dict()
    return None
