from __future__ import annotations

import pandas as pd

from .admission_parser import parse_regular_admission_dataframe
from .normalizer import normalize_text


def infer_special_type(text: str) -> str:
    text = normalize_text(text)
    mapping = [
        ("军", "军队院校"),
        ("公安", "公安类"),
        ("司法", "司法类"),
        ("航海", "航海类"),
        ("公费师范", "国家公费师范生"),
        ("优师", "优师专项"),
        ("免费医学", "国家免费医学生"),
        ("综合评价", "综合评价"),
        ("定向", "定向"),
        ("高校专项", "高校专项计划"),
        ("高水平运动", "高水平运动队"),
    ]
    for keyword, label in mapping:
        if keyword in text:
            return label
    return "其他"


def parse_early_admission_dataframe(df: pd.DataFrame, year: int, subject_group: str, batch_group: str) -> pd.DataFrame:
    parsed = parse_regular_admission_dataframe(df, year, subject_group, batch_group)
    if parsed.empty:
        return parsed
    stage = batch_group.replace("early_", "")
    parsed["early_batch_stage"] = stage
    parsed["special_type"] = parsed.apply(
        lambda row: infer_special_type(" ".join(str(row.get(k, "")) for k in ["enroll_type", "major_name", "raw_text"])),
        axis=1,
    )
    raw = parsed["raw_text"].fillna("") if "raw_text" in parsed else pd.Series([""] * len(parsed), index=parsed.index)
    parsed["requires_physical_exam"] = raw.astype(str).str.contains("体检")
    parsed["requires_political_review"] = raw.astype(str).str.contains("政审")
    parsed["requires_interview"] = raw.astype(str).str.contains("面试")
    parsed["requires_fitness_test"] = raw.astype(str).str.contains("体能")
    parsed["requires_special_control_line"] = raw.astype(str).str.contains("特殊类型|特控线", regex=True)
    parsed["gender_requirement"] = raw.astype(str).str.extract("(只招男生|只招女生)", expand=False).fillna("")
    parsed["height_requirement"] = raw.astype(str).str.extract("(身高[^，；。 ]*)", expand=False).fillna("")
    parsed["vision_requirement"] = raw.astype(str).str.extract("(视力[^，；。 ]*)", expand=False).fillna("")
    parsed["single_subject_requirement"] = raw.astype(str).str.extract("(单科[^，；。 ]*)", expand=False).fillna("")
    parsed["warnings"] = ""
    return parsed
