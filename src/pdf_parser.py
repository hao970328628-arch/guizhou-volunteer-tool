from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class PDFExtractResult:
    dataframe: pd.DataFrame
    failed_rows: list[dict[str, Any]]
    suspicious_rows: list[dict[str, Any]]


def _rows_to_dataframe(rows: list[list[Any]], source_file: Path, page_number: int) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    header = [str(cell or "").strip() for cell in rows[0]]
    if len(set(header)) < max(2, len(header) // 2):
        header = [f"col_{idx}" for idx in range(len(rows[0]))]
        data_rows = rows
    else:
        data_rows = rows[1:]
    records = []
    for raw in data_rows:
        values = list(raw) + [""] * (len(header) - len(raw))
        record = {header[idx]: values[idx] for idx in range(len(header))}
        record["source_file"] = source_file.name
        record["source_page"] = page_number
        record["raw_text"] = " ".join(str(cell or "").strip() for cell in raw)
        records.append(record)
    return pd.DataFrame(records)


def extract_pdf_tables(file_path: str | Path) -> PDFExtractResult:
    path = Path(file_path)
    frames: list[pd.DataFrame] = []
    failed: list[dict[str, Any]] = []
    suspicious: list[dict[str, Any]] = []
    try:
        import pdfplumber
    except Exception as exc:
        failed.append({"source_file": path.name, "source_page": None, "raw_text": f"pdfplumber 不可用：{exc}"})
        return PDFExtractResult(pd.DataFrame(), failed, suspicious)

    try:
        with pdfplumber.open(path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                if tables:
                    for table in tables:
                        frame = _rows_to_dataframe(table, path, page_number)
                        if not frame.empty:
                            frames.append(frame)
                else:
                    text = page.extract_text() or ""
                    for line in text.splitlines():
                        line = line.strip()
                        if line:
                            suspicious.append({"source_file": path.name, "source_page": page_number, "raw_text": line})
    except Exception as exc:
        failed.append({"source_file": path.name, "source_page": None, "raw_text": f"PDF 解析失败：{exc}"})

    dataframe = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return PDFExtractResult(dataframe, failed, suspicious)
