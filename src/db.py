from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .config import DB_PATH, PROCESSED_DIR, ensure_dirs


TABLE_COLUMNS = {
    "catalog_2026": [
        "id", "year", "subject_group", "batch", "batch_group", "category", "school_code", "school_name",
        "school_city", "school_province", "major_code", "major_name", "major_name_clean", "reselect_requirement",
        "plan_count", "language_requirement", "duration_years", "tuition", "remarks", "is_undergraduate",
        "is_regular_undergraduate", "is_early_batch", "early_batch_stage", "is_special_program", "is_preparatory",
        "is_ethnic_class", "is_national_special", "is_local_special", "is_directional",
        "is_border_guard_preparatory", "is_chinese_foreign", "major_category_level1", "major_category_level2",
        "source_file", "source_page", "raw_text",
    ],
    "admission_regular": [
        "id", "year", "subject_group", "batch_group", "school_code", "school_name", "major_code",
        "major_name", "major_name_clean", "enroll_type", "plan_count", "投档人数", "min_score", "min_rank",
        "is_preparatory", "is_ethnic_class", "is_national_special", "is_local_special", "is_chinese_foreign",
        "source_file", "source_page", "raw_text",
    ],
    "admission_early": [
        "id", "year", "subject_group", "early_batch_stage", "special_type", "school_code", "school_name",
        "major_code", "major_name", "major_name_clean", "enroll_type", "plan_count", "min_score", "min_rank",
        "requires_physical_exam", "requires_political_review", "requires_interview", "requires_fitness_test",
        "requires_special_control_line", "gender_requirement", "height_requirement", "vision_requirement",
        "single_subject_requirement", "warnings", "source_file", "source_page", "raw_text",
    ],
    "school_meta": [
        "school_code", "school_name", "province", "city", "school_level", "school_nature", "is_985", "is_211",
        "is_double_first_class", "is_public", "is_private", "is_independent_college", "is_vocational_university",
    ],
}


def _with_columns(df: pd.DataFrame, table: str) -> pd.DataFrame:
    out = df.copy()
    for col in TABLE_COLUMNS[table]:
        if col == "id":
            continue
        if col not in out.columns:
            out[col] = ""
    return out[[col for col in TABLE_COLUMNS[table] if col != "id"]]


def init_db(db_path: str | Path = DB_PATH) -> None:
    ensure_dirs()
    with sqlite3.connect(db_path) as conn:
        for table, columns in TABLE_COLUMNS.items():
            defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"] + [f'"{col}" TEXT' for col in columns if col != "id"]
            conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(defs)})')


def save_dataframe(df: pd.DataFrame, table: str, db_path: str | Path = DB_PATH, replace: bool = True) -> None:
    init_db(db_path)
    prepared = _with_columns(df, table)
    if table == "catalog_2026":
        csv_path = PROCESSED_DIR / "catalog_2026.csv"
    elif table == "admission_regular":
        years = sorted(str(y) for y in prepared["year"].dropna().unique()) if "year" in prepared else []
        csv_path = PROCESSED_DIR / (f"admission_{years[0]}_regular.csv" if len(years) == 1 else "admission_regular.csv")
    elif table == "admission_early":
        years = sorted(str(y) for y in prepared["year"].dropna().unique()) if "year" in prepared else []
        csv_path = PROCESSED_DIR / (f"early_admission_{years[0]}.csv" if len(years) == 1 else "early_admission.csv")
    else:
        csv_path = PROCESSED_DIR / f"{table}.csv"
    if not replace and csv_path.exists():
        existing = pd.read_csv(csv_path, dtype=str).fillna("")
        for col in prepared.columns:
            if col not in existing.columns:
                existing[col] = ""
        for col in existing.columns:
            if col not in prepared.columns:
                prepared[col] = ""
        prepared = pd.concat([existing[prepared.columns], prepared], ignore_index=True)
    prepared.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with sqlite3.connect(db_path) as conn:
        prepared.to_sql(table, conn, if_exists="replace" if replace else "append", index=False)


def load_processed_csv(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / name
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.DataFrame()


def ensure_school_meta_template() -> None:
    path = PROCESSED_DIR / "school_meta.csv"
    if not path.exists():
        pd.DataFrame(columns=TABLE_COLUMNS["school_meta"]).to_csv(path, index=False, encoding="utf-8-sig")
