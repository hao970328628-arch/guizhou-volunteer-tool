from __future__ import annotations

from typing import Any

import pandas as pd

from .eligibility import check_program_eligibility, check_subject_eligibility
from .charter_risk import append_charter_risks
from .major_classifier import classify_major, filter_major
from .normalizer import normalize_text
from .risk_model import classify_risk, risk_sort_value
from .utils import append_warning, to_int


OUTPUT_COLUMNS = [
    "risk_level", "risk_score", "school_code", "school_name", "school_province", "school_city", "school_level",
    "school_nature", "major_code", "major_name", "major_category_level1", "major_category_level2", "batch",
    "category", "plan_count_2026", "reselect_requirement", "tuition", "duration_years", "min_score_2025",
    "min_rank_2025", "min_score_2024", "min_rank_2024", "rank_gap_2025", "rank_gap_pct_2025", "volatility",
    "warnings", "risk_reason", "source_page_catalog", "source_page_admission",
]


def _truth(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "是", "y"}
    return bool(value)


def _safe_str(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _is_regular(row: pd.Series) -> bool:
    batch_text = " ".join(_safe_str(row.get(k, "")) for k in ["batch", "batch_group", "category", "remarks"])
    if any(word in batch_text for word in ["专科", "高职", "艺术", "体育", "提前批", "本科提前", "A段", "B段", "C段"]):
        return False
    if "is_undergraduate" in row and str(row.get("is_undergraduate")).lower() in {"false", "0"}:
        return False
    if "is_regular_undergraduate" in row and str(row.get("is_regular_undergraduate")).lower() in {"false", "0"}:
        return False
    return True


def _build_admission_index(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return df.to_dict("records")


def _match_admission(row: pd.Series, records: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    school_code = _safe_str(row.get("school_code"))
    school_name = normalize_text(row.get("school_name"))
    major_code = _safe_str(row.get("major_code"))
    major_name = normalize_text(row.get("major_name_clean") or row.get("major_name"))
    enroll_type = normalize_text(row.get("category"))

    def same_enroll(record: dict[str, Any]) -> bool:
        rec_type = normalize_text(record.get("enroll_type"))
        return not enroll_type or not rec_type or enroll_type == rec_type

    for record in records:
        if record.get("school_code") == school_code and record.get("major_code") == major_code and same_enroll(record):
            return record, "代码完全匹配"
    for record in records:
        if record.get("school_code") == school_code and normalize_text(record.get("major_name_clean") or record.get("major_name")) == major_name and same_enroll(record):
            return record, "专业名匹配，专业代码可能跨年变化"
    for record in records:
        if normalize_text(record.get("school_name")) == school_name and normalize_text(record.get("major_name_clean") or record.get("major_name")) == major_name and same_enroll(record):
            return record, "学校名+专业名匹配，需核验代码"
    return None, ""


def _merge_school_meta(results: pd.DataFrame, school_meta: pd.DataFrame | None) -> pd.DataFrame:
    if school_meta is None or school_meta.empty or results.empty:
        results["school_level"] = results.get("school_level", "未知")
        results["school_nature"] = results.get("school_nature", "未知")
        return results
    meta = school_meta.drop_duplicates("school_code")
    merged = results.merge(
        meta[["school_code", "school_level", "school_nature", "province", "city"]],
        on="school_code",
        how="left",
        suffixes=("", "_meta"),
    )
    merged["school_level"] = merged["school_level"].fillna("未知").replace("", "未知")
    merged["school_nature"] = merged["school_nature"].fillna("未知").replace("", "未知")
    merged["school_province"] = merged["school_province"].replace("", pd.NA).fillna(merged.get("province", ""))
    merged["school_city"] = merged["school_city"].replace("", pd.NA).fillna(merged.get("city", ""))
    return merged


def recommend_regular(
    catalog_df: pd.DataFrame,
    admission_2025_df: pd.DataFrame,
    admission_2024_df: pd.DataFrame,
    user_profile: dict[str, Any],
    thresholds: dict[str, tuple[float, float]] | None = None,
    school_meta_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if catalog_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    records_2025 = _build_admission_index(admission_2025_df)
    records_2024 = _build_admission_index(admission_2024_df)
    rows: list[dict[str, Any]] = []
    candidate_subjects = user_profile.get("candidate_subjects", [])
    subject_group = user_profile.get("subject_group")

    for _, row in catalog_df.iterrows():
        if subject_group and _safe_str(row.get("subject_group")) != subject_group:
            continue
        if not _is_regular(row):
            continue
        if not check_subject_eligibility(candidate_subjects, row.get("reselect_requirement")):
            continue
        ok, eligibility_warnings = check_program_eligibility(row, user_profile)
        if not ok:
            continue

        level1 = row.get("major_category_level1") or classify_major(row.get("major_name"))[0]
        level2 = row.get("major_category_level2") or classify_major(row.get("major_name"))[1]
        row_for_major = row.copy()
        row_for_major["major_category_level1"] = level1
        row_for_major["major_category_level2"] = level2
        if not filter_major(
            row_for_major,
            user_profile.get("major_level1"),
            user_profile.get("major_level2"),
            user_profile.get("major_white_keywords"),
            user_profile.get("major_black_keywords"),
        ):
            continue

        province_prefs = user_profile.get("province_prefs") or []
        if province_prefs and _safe_str(row.get("school_province")) not in province_prefs and _safe_str(row.get("school_city")) not in province_prefs:
            continue

        match_2025, match_note_2025 = _match_admission(row, records_2025)
        match_2024, match_note_2024 = _match_admission(row, records_2024)
        risk = classify_risk(
            user_profile.get("student_rank"),
            match_2025.get("min_rank") if match_2025 else None,
            thresholds,
            user_profile.get("student_score"),
            match_2025.get("min_score") if match_2025 else None,
            row.get("plan_count"),
            match_2025.get("plan_count") if match_2025 else None,
            match_2025.get("投档人数") if match_2025 else None,
            match_2024.get("min_rank") if match_2024 else None,
        )

        warnings = "；".join(eligibility_warnings + risk.warnings)
        warnings = append_charter_risks(warnings, row.get("remarks", ""), row.get("raw_text", ""), row.get("major_name", ""))
        for note in [match_note_2025, match_note_2024]:
            if note and note != "代码完全匹配":
                warnings = append_warning(warnings, note)

        rows.append(
            {
                "risk_level": risk.risk_level,
                "risk_score": risk.risk_score,
                "school_code": row.get("school_code", ""),
                "school_name": row.get("school_name", ""),
                "school_province": row.get("school_province", ""),
                "school_city": row.get("school_city", ""),
                "school_level": "未知",
                "school_nature": "未知",
                "major_code": row.get("major_code", ""),
                "major_name": row.get("major_name", ""),
                "major_category_level1": level1,
                "major_category_level2": level2,
                "batch": row.get("batch", ""),
                "category": row.get("category", ""),
                "plan_count_2026": row.get("plan_count", ""),
                "reselect_requirement": row.get("reselect_requirement", ""),
                "tuition": row.get("tuition", ""),
                "duration_years": row.get("duration_years", ""),
                "min_score_2025": match_2025.get("min_score", "") if match_2025 else "",
                "min_rank_2025": match_2025.get("min_rank", "") if match_2025 else "",
                "min_score_2024": match_2024.get("min_score", "") if match_2024 else "",
                "min_rank_2024": match_2024.get("min_rank", "") if match_2024 else "",
                "rank_gap_2025": risk.rank_gap,
                "rank_gap_pct_2025": risk.rank_gap_pct,
                "volatility": risk.volatility,
                "warnings": warnings,
                "risk_reason": risk.risk_reason,
                "source_page_catalog": row.get("source_page", ""),
                "source_page_admission": match_2025.get("source_page", "") if match_2025 else "",
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    result = _merge_school_meta(result, school_meta_df)
    nature_prefs = user_profile.get("school_nature") or []
    if nature_prefs and "school_nature" in result.columns:
        result = result[result["school_nature"].isin(nature_prefs) | (result["school_nature"] == "未知")]
    result["_risk_sort"] = result["risk_level"].map(risk_sort_value)
    result["_rank_sort"] = result["min_rank_2025"].apply(lambda value: to_int(value) or 10**9)
    result = result.sort_values(["_risk_sort", "_rank_sort", "school_name", "major_name"]).drop(columns=["_risk_sort", "_rank_sort"])
    for col in OUTPUT_COLUMNS:
        if col not in result.columns:
            result[col] = ""
    return result[OUTPUT_COLUMNS]
