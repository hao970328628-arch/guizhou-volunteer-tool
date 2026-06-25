from __future__ import annotations

from typing import Any

import pandas as pd

from .normalizer import normalize_admission_row, normalize_text
from .utils import to_int


ADMISSION_COLUMNS = {
    "院校代码": "school_code",
    "院校名称": "school_name",
    "专业代码": "major_code",
    "专业名称": "major_name",
    "招考类型": "enroll_type",
    "招生类型": "enroll_type",
    "计划数": "plan_count",
    "投档人数": "admission_count",
    "投档最低分": "min_score",
    "最低分": "min_score",
    "投档最低位次": "min_rank",
    "最低位次": "min_rank",
}


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        clean = normalize_text(col)
        for key, target in ADMISSION_COLUMNS.items():
            if key in clean:
                rename[col] = target
                break
    return df.rename(columns=rename)


def parse_regular_admission_dataframe(df: pd.DataFrame, year: int, subject_group: str, batch_group: str) -> pd.DataFrame:
    if df.empty:
        return df
    df = _rename_columns(df).copy()
    rows: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        row = {k: raw.get(k, "") for k in df.columns}
        normalized = normalize_admission_row(row)
        normalized["year"] = year
        normalized["subject_group"] = subject_group
        normalized["batch_group"] = batch_group
        normalized["plan_count"] = to_int(normalized.get("plan_count") or raw.get("计划数"))
        normalized["投档人数"] = to_int(normalized.get("admission_count") or raw.get("投档人数"))
        normalized["min_score"] = to_int(normalized.get("min_score") or raw.get("投档最低分"))
        normalized["min_rank"] = to_int(normalized.get("min_rank") or raw.get("投档最低位次"))
        rows.append(normalized)
    return pd.DataFrame(rows)
