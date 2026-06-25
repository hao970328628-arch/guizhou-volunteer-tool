from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import PROCESSED_DIR
from .db import TABLE_COLUMNS


SCHOOL_META_PATH = PROCESSED_DIR / "school_meta.csv"


def normalize_school_meta(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename = {
        "院校代码": "school_code",
        "院校名称": "school_name",
        "省份": "province",
        "城市": "city",
        "层次": "school_level",
        "学校层次": "school_level",
        "性质": "school_nature",
        "学校性质": "school_nature",
    }
    out = out.rename(columns={col: rename.get(col, col) for col in out.columns})
    for col in TABLE_COLUMNS["school_meta"]:
        if col not in out.columns:
            out[col] = ""
    out["school_code"] = out["school_code"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    for bool_col in [
        "is_985", "is_211", "is_double_first_class", "is_public", "is_private",
        "is_independent_college", "is_vocational_university",
    ]:
        out[bool_col] = out[bool_col].astype(str).replace({"True": "1", "False": "0", "是": "1", "否": "0"})
    return out[TABLE_COLUMNS["school_meta"]].drop_duplicates("school_code", keep="last")


def save_school_meta(df: pd.DataFrame, path: str | Path = SCHOOL_META_PATH) -> None:
    normalized = normalize_school_meta(df)
    normalized.to_csv(path, index=False, encoding="utf-8-sig")


def school_meta_template() -> pd.DataFrame:
    return pd.DataFrame(columns=TABLE_COLUMNS["school_meta"])
