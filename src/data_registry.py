from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import RAW_DIR


@dataclass(frozen=True)
class DataFileSpec:
    file_id: str
    year: int | None
    subject_group: str
    data_type: str
    batch_group: str
    directory: str
    keywords: tuple[str, ...]
    is_required_for_mvp: bool
    notes: str = ""


DATA_FILE_SPECS: list[DataFileSpec] = [
    DataFileSpec("catalog_2026_physics", 2026, "物理类", "catalog", "regular_undergraduate", "catalog", ("招生专业目录", "物理"), True),
    DataFileSpec("catalog_2026_history", 2026, "历史类", "catalog", "regular_undergraduate", "catalog", ("招生专业目录", "历史"), True),
    DataFileSpec("regular_2025_physics", 2025, "物理类", "regular_admission", "regular_undergraduate", "admission/2025", ("2025", "投档", "物理"), True),
    DataFileSpec("regular_2025_history", 2025, "历史类", "regular_admission", "regular_undergraduate", "admission/2025", ("2025", "投档", "历史"), True),
    DataFileSpec("regular_2024_physics", 2024, "物理类", "regular_admission", "regular_undergraduate", "admission/2024", ("2024", "本科批", "物理"), True),
    DataFileSpec("regular_2024_history", 2024, "历史类", "regular_admission", "regular_undergraduate", "admission/2024", ("2024", "本科批", "历史"), True),
    DataFileSpec("score_rank_2024_physics", 2024, "物理类", "score_rank", "score_rank", "score_rank", ("2024", "分数段", "物理"), False),
]

for year in [2025, 2024]:
    for stage in ["A", "B", "C"]:
        for subject, keyword in [("物理类", "物理"), ("历史类", "历史")]:
            DATA_FILE_SPECS.append(
                DataFileSpec(
                    f"early_{year}_{stage}_{'physics' if subject == '物理类' else 'history'}",
                    year,
                    subject,
                    "early_admission",
                    f"early_{stage}",
                    f"admission/{year}",
                    (str(year), "提前批", f"{stage}段", keyword),
                    False,
                    "提前批独立参考模块，默认关闭",
                )
            )


def _candidate_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in {".pdf", ".csv", ".xlsx", ".xls"}]


def _find_file(raw_dir: Path, spec: DataFileSpec) -> Path | None:
    directory = raw_dir / spec.directory
    candidates = list(_candidate_files(directory))
    if not candidates:
        candidates = list(raw_dir.rglob("*"))
        candidates = [p for p in candidates if p.is_file()]
    scored: list[tuple[int, Path]] = []
    for path in candidates:
        name = path.name
        score = sum(1 for keyword in spec.keywords if keyword in name)
        if score == len(spec.keywords):
            return path
        if score:
            scored.append((score, path))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_path = scored[0]
        if best_score >= max(2, len(spec.keywords) - 1):
            return best_path
    return None


def build_data_registry(base_dir: str | Path | None = None) -> pd.DataFrame:
    raw_dir = Path(base_dir) if base_dir else RAW_DIR
    if raw_dir.name != "raw" and (raw_dir / "raw").exists():
        raw_dir = raw_dir / "raw"
    rows = []
    for spec in DATA_FILE_SPECS:
        found = _find_file(raw_dir, spec)
        rows.append(
            {
                "file_id": spec.file_id,
                "year": spec.year,
                "subject_group": spec.subject_group,
                "data_type": spec.data_type,
                "batch_group": spec.batch_group,
                "source_path": str(found) if found else str(raw_dir / spec.directory / "（缺失）"),
                "is_required_for_mvp": spec.is_required_for_mvp,
                "status": "available" if found else ("missing" if spec.is_required_for_mvp else "optional"),
                "notes": spec.notes or ("MVP 必需" if spec.is_required_for_mvp else "可选数据"),
            }
        )
    return pd.DataFrame(rows)


def registry_summary(registry: pd.DataFrame) -> dict[str, int]:
    return {
        "available": int((registry["status"] == "available").sum()) if not registry.empty else 0,
        "missing_required": int(((registry["status"] == "missing") & registry["is_required_for_mvp"]).sum()) if not registry.empty else 0,
        "optional_missing": int((registry["status"] == "optional").sum()) if not registry.empty else 0,
    }
