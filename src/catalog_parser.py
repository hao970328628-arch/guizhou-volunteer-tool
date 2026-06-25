from __future__ import annotations

from typing import Any

import pandas as pd

from .major_classifier import classify_major
from .normalizer import normalize_catalog_row, normalize_text
from .utils import to_int


CATALOG_COLUMNS = {
    "批次": "batch",
    "类别": "category",
    "院校代码": "school_code",
    "院校名称": "school_name",
    "所在城市": "school_city",
    "城市": "school_city",
    "专业代码": "major_code",
    "专业名称": "major_name",
    "再选科目": "reselect_requirement",
    "选科要求": "reselect_requirement",
    "计划数": "plan_count",
    "语种": "language_requirement",
    "学制": "duration_years",
    "学费": "tuition",
    "备注": "remarks",
}


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        clean = normalize_text(col)
        for key, target in CATALOG_COLUMNS.items():
            if key in clean:
                rename[col] = target
                break
    return df.rename(columns=rename)


def parse_catalog_dataframe(df: pd.DataFrame, year: int, subject_group: str, batch_group: str) -> pd.DataFrame:
    if df.empty:
        return df
    df = _rename_columns(df).copy()
    rows: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        row = {k: raw.get(k, "") for k in df.columns}
        normalized = normalize_catalog_row(row)
        normalized.setdefault("year", year)
        normalized["year"] = year
        normalized["subject_group"] = subject_group
        normalized["batch_group"] = batch_group
        normalized["plan_count"] = to_int(normalized.get("plan_count") or raw.get("计划数"))
        normalized["duration_years"] = to_int(normalized.get("duration_years") or raw.get("学制"))
        normalized["school_province"] = normalized.get("school_province", "")
        normalized["early_batch_stage"] = ""
        normalized["is_early_batch"] = batch_group.startswith("early_")
        level1, level2 = classify_major(normalized.get("major_name_clean", ""))
        normalized["major_category_level1"] = level1
        normalized["major_category_level2"] = level2
        rows.append(normalized)
    return pd.DataFrame(rows)
