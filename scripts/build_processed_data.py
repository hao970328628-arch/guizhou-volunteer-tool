from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import PROCESSED_DIR, RAW_DIR, ensure_dirs
from src.data_loader import load_data_file
from src.data_registry import build_data_registry
from src.db import save_dataframe
from src.school_meta import normalize_school_meta, school_meta_template


TARGETS: dict[str, dict[str, Any]] = {
    "catalog_2026.csv": {"table": "catalog_2026", "required": True, "usage": "2026 招生专业目录"},
    "admission_2025_regular.csv": {"table": "admission_regular", "required": True, "usage": "2025 普通本科批投档"},
    "admission_2024_regular.csv": {"table": "admission_regular", "required": True, "usage": "2024 普通本科批投档"},
    "early_admission_2025.csv": {"table": "admission_early", "required": False, "usage": "2025 提前批 A/B/C"},
    "early_admission_2024.csv": {"table": "admission_early", "required": False, "usage": "2024 提前批 A/B/C"},
    "score_rank_2024.csv": {"table": "score_rank", "required": False, "usage": "2024 一分一段/分数段"},
    "school_meta.csv": {"table": "school_meta", "required": False, "usage": "学校属性库"},
}
MANIFEST_PATH = PROCESSED_DIR / "manifest.json"


def _relative(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return str(path_obj.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path_obj)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_unlink_processed_file(file_name: str) -> None:
    path = (PROCESSED_DIR / file_name).resolve()
    processed_root = PROCESSED_DIR.resolve()
    if path.parent != processed_root:
        raise RuntimeError(f"拒绝删除非 data/processed 顶层文件：{path}")
    if path.exists():
        path.unlink()


def _target_file_for_registry_row(row: pd.Series) -> str | None:
    data_type = str(row.get("data_type", ""))
    year_raw = row.get("year", "")
    year = int(year_raw) if pd.notna(year_raw) and str(year_raw).strip() else 0
    if data_type == "catalog" and year == 2026:
        return "catalog_2026.csv"
    if data_type == "regular_admission" and year in {2025, 2024}:
        return f"admission_{year}_regular.csv"
    if data_type == "early_admission" and year in {2025, 2024}:
        return f"early_admission_{year}.csv"
    if data_type == "score_rank" and year == 2024:
        return "score_rank_2024.csv"
    return None


def _read_tabular(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str).fillna("")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    raise ValueError(f"不支持的学校属性库文件类型：{path.suffix}")


def _find_school_meta_source() -> Path | None:
    candidates: list[Path] = []
    search_roots = [RAW_DIR / "school_meta", RAW_DIR]
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
                continue
            name = path.name.lower()
            if "school_meta" in name or "学校属性" in path.name or "院校属性" in path.name:
                candidates.append(path)
    return sorted(set(candidates), key=lambda item: str(item))[0] if candidates else None


def _prepare_school_meta() -> tuple[pd.DataFrame, list[str], list[str]]:
    logs: list[str] = []
    raw_source = _find_school_meta_source()
    if raw_source:
        frame = normalize_school_meta(_read_tabular(raw_source))
        logs.append(f"学校属性库：从 {_relative(raw_source)} 读取 {len(frame)} 行")
        return frame, [_relative(raw_source)], logs

    existing_path = PROCESSED_DIR / "school_meta.csv"
    if existing_path.exists() and existing_path.stat().st_size > 0:
        frame = normalize_school_meta(pd.read_csv(existing_path, dtype=str).fillna(""))
        logs.append(f"学校属性库：未找到 raw 来源，沿用现有 {_relative(existing_path)}，共 {len(frame)} 行")
        return frame, [_relative(existing_path)], logs

    logs.append("学校属性库：未找到来源，生成空模板")
    return school_meta_template(), [], logs


def _parse_raw_files() -> tuple[dict[str, pd.DataFrame], dict[str, list[str]], list[str]]:
    registry = build_data_registry(RAW_DIR)
    frames_by_target: dict[str, list[pd.DataFrame]] = {}
    sources_by_target: dict[str, list[str]] = {}
    logs: list[str] = []

    available = registry[registry["status"] == "available"] if not registry.empty else pd.DataFrame()
    for _, row in available.iterrows():
        target_file = _target_file_for_registry_row(row)
        if not target_file:
            continue
        source_path = Path(str(row["source_path"]))
        result = load_data_file(
            source_path,
            str(row["data_type"]),
            int(row["year"]) if pd.notna(row["year"]) else 0,
            str(row["subject_group"]),
            str(row["batch_group"]),
        )
        message = "；".join(result.messages)
        logs.append(
            f"{_relative(source_path)} -> {target_file}: 成功 {result.success_rows} 行，"
            f"失败 {result.failed_rows} 行，可疑 {result.suspicious_rows} 行。{message}"
        )
        sources_by_target.setdefault(target_file, []).append(_relative(source_path))
        if not result.dataframe.empty:
            frames_by_target.setdefault(target_file, []).append(result.dataframe)

    frames: dict[str, pd.DataFrame] = {
        target: pd.concat(parts, ignore_index=True) for target, parts in frames_by_target.items() if parts
    }
    school_meta, school_sources, school_logs = _prepare_school_meta()
    frames["school_meta.csv"] = school_meta
    sources_by_target["school_meta.csv"] = school_sources
    logs.extend(school_logs)
    return frames, sources_by_target, logs


def _file_manifest_entry(file_name: str, rows: int, source_files: list[str]) -> dict[str, Any]:
    path = PROCESSED_DIR / file_name
    exists = path.exists()
    return {
        "file_name": file_name,
        "path": _relative(path),
        "usage": TARGETS[file_name]["usage"],
        "required": TARGETS[file_name]["required"],
        "exists": exists,
        "rows": int(rows) if exists else 0,
        "file_size": path.stat().st_size if exists else 0,
        "sha256": _sha256(path) if exists else "",
        "source_files": source_files,
    }


def _write_manifest(
    rows_by_target: dict[str, int],
    sources_by_target: dict[str, list[str]],
    missing_required: list[str],
    missing_optional: list[str],
    logs: list[str],
) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "build_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "processed_dir": _relative(PROCESSED_DIR),
        "files": [
            _file_manifest_entry(file_name, rows_by_target.get(file_name, 0), sources_by_target.get(file_name, []))
            for file_name in TARGETS
        ],
        "missing_required_data": missing_required,
        "missing_optional_data": missing_optional,
        "logs": logs,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _existing_outputs() -> list[Path]:
    return [PROCESSED_DIR / file_name for file_name in TARGETS if (PROCESSED_DIR / file_name).exists()]


def build_processed_data(force: bool) -> int:
    ensure_dirs()
    existing = _existing_outputs()
    if existing and not force:
        print("以下标准数据文件已存在。若要覆盖，请使用 --force：", file=sys.stderr)
        for path in existing:
            print(f"- {_relative(path)}", file=sys.stderr)
        return 2

    frames, sources_by_target, logs = _parse_raw_files()
    rows_by_target = {file_name: len(frame) for file_name, frame in frames.items()}
    missing_required = [
        file_name
        for file_name, meta in TARGETS.items()
        if meta["required"] and (file_name not in frames or frames[file_name].empty)
    ]
    missing_optional = [
        file_name
        for file_name, meta in TARGETS.items()
        if not meta["required"] and (file_name not in frames or frames[file_name].empty)
    ]

    if missing_required:
        _write_manifest(rows_by_target, sources_by_target, missing_required, missing_optional, logs)
        print("必需数据为空或缺失，已停止构建：", file=sys.stderr)
        for file_name in missing_required:
            print(f"- {file_name}", file=sys.stderr)
        print(f"manifest 已写入：{_relative(MANIFEST_PATH)}", file=sys.stderr)
        return 1

    written_rows: dict[str, int] = {}
    for file_name, frame in frames.items():
        table = str(TARGETS[file_name]["table"])
        save_dataframe(frame, table, replace=True)
        written_rows[file_name] = len(frame)

    for file_name, meta in TARGETS.items():
        if meta["required"] or file_name in written_rows or file_name == "school_meta.csv":
            continue
        if force:
            _safe_unlink_processed_file(file_name)

    _write_manifest(written_rows, sources_by_target, missing_required, missing_optional, logs)
    print("预构建数据包已生成：")
    for file_name in TARGETS:
        path = PROCESSED_DIR / file_name
        status = "存在" if path.exists() else "缺失"
        print(f"- {file_name}: {status}, {written_rows.get(file_name, 0)} 行")
    print(f"manifest: {_relative(MANIFEST_PATH)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="从 data/raw 一次性生成 data/processed 标准数据包。")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的标准数据文件。")
    args = parser.parse_args()
    return build_processed_data(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
