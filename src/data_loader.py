from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .admission_parser import parse_regular_admission_dataframe
from .catalog_parser import parse_catalog_dataframe
from .config import PROCESSED_DIR, ensure_dirs
from .early_batch_parser import parse_early_admission_dataframe
from .pdf_parser import extract_pdf_tables
from .score_rank import parse_score_rank_dataframe
from .utils import to_int


@dataclass
class ParseResult:
    dataframe: pd.DataFrame
    success_rows: int
    failed_rows: int
    suspicious_rows: int
    messages: list[str] = field(default_factory=list)


def _read_tabular_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str).fillna("")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    raise ValueError(f"不支持的文件类型：{path.suffix}")


def _parse_by_type(df: pd.DataFrame, data_type: str, year: int, subject_group: str, batch_group: str) -> pd.DataFrame:
    if data_type == "catalog":
        return parse_catalog_dataframe(df, year, subject_group, batch_group)
    if data_type == "regular_admission":
        return parse_regular_admission_dataframe(df, year, subject_group, batch_group)
    if data_type == "early_admission":
        return parse_early_admission_dataframe(df, year, subject_group, batch_group)
    if data_type == "score_rank":
        return parse_score_rank_dataframe(df, year, subject_group)
    return df


def _compact_line(line: str) -> str:
    return " ".join(str(line or "").replace("\t", " ").split())


def _fallback_from_text(records: list[dict[str, Any]], data_type: str, year: int, subject_group: str, batch_group: str) -> pd.DataFrame:
    """Best-effort parser for PDFs where table extraction fails.

    贵州投档/目录 PDF 的版式可能不同，这里只做保守提取：能识别代码和末尾分数/位次的行进入
    parsed dataframe；无法识别的行仍保留在 parse_errors.csv，等待人工 CSV 修正。
    """
    import re

    parsed_rows: list[dict[str, Any]] = []
    for record in records:
        line = _compact_line(record.get("raw_text", ""))
        if not line or any(header in line for header in ["院校代码", "专业代码", "投档最低", "批次", "类别"]):
            continue
        if data_type in {"regular_admission", "early_admission"}:
            nums = re.findall(r"\d+", line)
            if len(nums) < 4:
                continue
            school_code = nums[0]
            major_code = nums[1]
            min_score = nums[-2]
            min_rank = nums[-1]
            text_without_nums = re.sub(r"\d+", " ", line)
            pieces = [p for p in re.split(r"\s+", text_without_nums) if p]
            parsed_rows.append(
                {
                    "school_code": school_code,
                    "school_name": pieces[0] if pieces else "",
                    "major_code": major_code,
                    "major_name": pieces[1] if len(pieces) > 1 else line,
                    "enroll_type": "",
                    "plan_count": nums[-4] if len(nums) >= 4 else "",
                    "投档人数": nums[-3] if len(nums) >= 3 else "",
                    "min_score": min_score,
                    "min_rank": min_rank,
                    "source_file": record.get("source_file", ""),
                    "source_page": record.get("source_page", ""),
                    "raw_text": line,
                }
            )
        elif data_type == "catalog":
            nums = re.findall(r"\d+", line)
            if len(nums) < 3:
                continue
            school_code = nums[0]
            major_code = nums[1]
            plan_count = nums[-3] if len(nums) >= 3 else ""
            tuition = nums[-1] if len(nums) >= 1 else ""
            text_without_nums = re.sub(r"\d+", " ", line)
            pieces = [p for p in re.split(r"\s+", text_without_nums) if p]
            parsed_rows.append(
                {
                    "batch": "本科批",
                    "category": "",
                    "school_code": school_code,
                    "school_name": pieces[0] if pieces else "",
                    "school_city": "",
                    "major_code": major_code,
                    "major_name": pieces[1] if len(pieces) > 1 else line,
                    "reselect_requirement": "不限" if "不限" in line else "",
                    "plan_count": to_int(plan_count),
                    "language_requirement": "",
                    "duration_years": "",
                    "tuition": to_int(tuition),
                    "remarks": line,
                    "source_file": record.get("source_file", ""),
                    "source_page": record.get("source_page", ""),
                    "raw_text": line,
                }
            )
    if not parsed_rows:
        return pd.DataFrame()
    return _parse_by_type(pd.DataFrame(parsed_rows), data_type, year, subject_group, batch_group)


def _write_parse_errors(records: list[dict[str, Any]]) -> None:
    if not records:
        return
    ensure_dirs()
    path = PROCESSED_DIR / "parse_errors.csv"
    frame = pd.DataFrame(records)
    if path.exists():
        old = pd.read_csv(path, dtype=str).fillna("")
        frame = pd.concat([old, frame], ignore_index=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def load_data_file(file_path: str | Path, data_type: str, year: int, subject_group: str, batch_group: str) -> ParseResult:
    path = Path(file_path)
    messages: list[str] = []
    failed_records: list[dict[str, Any]] = []
    suspicious_records: list[dict[str, Any]] = []
    if not path.exists():
        return ParseResult(pd.DataFrame(), 0, 1, 0, [f"文件不存在：{path}"])

    try:
        if path.suffix.lower() == ".pdf":
            extracted = extract_pdf_tables(path)
            raw_df = extracted.dataframe
            failed_records.extend(extracted.failed_rows)
            suspicious_records.extend(extracted.suspicious_rows)
            messages.append(f"PDF 表格提取 {len(raw_df)} 行")
            if raw_df.empty and suspicious_records:
                parsed = _fallback_from_text(suspicious_records, data_type, year, subject_group, batch_group)
                if not parsed.empty:
                    messages.append(f"PDF 文本兜底解析 {len(parsed)} 行")
                    _write_parse_errors(failed_records)
                    return ParseResult(parsed, len(parsed), len(failed_records), len(suspicious_records), messages)
        else:
            raw_df = _read_tabular_file(path)
            messages.append(f"读取表格文件 {len(raw_df)} 行")
        parsed = _parse_by_type(raw_df, data_type, year, subject_group, batch_group)
    except Exception as exc:
        failed_records.append({"source_file": path.name, "source_page": "", "raw_text": str(exc)})
        parsed = pd.DataFrame()

    _write_parse_errors(failed_records + suspicious_records)
    return ParseResult(parsed, len(parsed), len(failed_records), len(suspicious_records), messages)


def load_parse_errors() -> pd.DataFrame:
    path = PROCESSED_DIR / "parse_errors.csv"
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.DataFrame(columns=["source_file", "source_page", "raw_text"])


def correction_template(data_type: str) -> pd.DataFrame:
    if data_type == "catalog":
        columns = [
            "batch", "category", "school_code", "school_name", "school_city", "major_code", "major_name",
            "reselect_requirement", "plan_count", "language_requirement", "duration_years", "tuition", "remarks",
            "source_file", "source_page", "raw_text",
        ]
    elif data_type == "early_admission":
        columns = [
            "school_code", "school_name", "major_code", "major_name", "enroll_type", "plan_count", "min_score",
            "min_rank", "source_file", "source_page", "raw_text",
        ]
    elif data_type == "score_rank":
        columns = ["score", "same_score_count", "cumulative_count", "rank_low", "source_file", "source_page", "raw_text"]
    else:
        columns = [
            "school_code", "school_name", "major_code", "major_name", "enroll_type", "plan_count", "投档人数",
            "min_score", "min_rank", "source_file", "source_page", "raw_text",
        ]
    return pd.DataFrame(columns=columns)
