from __future__ import annotations

from typing import Any

import pandas as pd

from .normalizer import normalize_text
from .utils import to_int


SCORE_RANK_COLUMNS = ["year", "subject_group", "score", "same_score_count", "cumulative_count", "rank_low", "source_file", "source_page", "raw_text"]


def parse_score_rank_dataframe(df: pd.DataFrame, year: int, subject_group: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=SCORE_RANK_COLUMNS)
    rename = {}
    for col in df.columns:
        clean = normalize_text(col)
        if "分数" in clean or clean == "分":
            rename[col] = "score"
        elif "本段" in clean or "人数" in clean and "累计" not in clean:
            rename[col] = "same_score_count"
        elif "累计" in clean or "位次" in clean:
            rename[col] = "cumulative_count"
    raw_df = df.rename(columns=rename)
    rows: list[dict[str, Any]] = []
    for _, row in raw_df.iterrows():
        score = to_int(row.get("score"))
        cumulative = to_int(row.get("cumulative_count"))
        if score is None or cumulative is None:
            nums = [to_int(part) for part in str(row.get("raw_text", "")).replace("，", " ").split()]
            nums = [num for num in nums if num is not None]
            if len(nums) >= 2:
                score = score if score is not None else nums[0]
                cumulative = cumulative if cumulative is not None else nums[-1]
        if score is None or cumulative is None:
            continue
        same = to_int(row.get("same_score_count"))
        rank_low = cumulative - same + 1 if same and cumulative >= same else cumulative
        rows.append(
            {
                "year": year,
                "subject_group": subject_group,
                "score": score,
                "same_score_count": same or "",
                "cumulative_count": cumulative,
                "rank_low": rank_low,
                "source_file": row.get("source_file", ""),
                "source_page": row.get("source_page", ""),
                "raw_text": row.get("raw_text", ""),
            }
        )
    return pd.DataFrame(rows, columns=SCORE_RANK_COLUMNS)


def estimate_rank(score_rank_df: pd.DataFrame, score: Any, subject_group: str | None = None) -> tuple[int | None, str]:
    score_int = to_int(score)
    if score_rank_df.empty or score_int is None:
        return None, ""
    df = score_rank_df.copy()
    if subject_group and "subject_group" in df.columns:
        df = df[df["subject_group"].astype(str) == subject_group]
    if df.empty:
        return None, ""
    df["score_int"] = df["score"].apply(to_int)
    df["rank_int"] = df["cumulative_count"].apply(to_int)
    exact = df[df["score_int"] == score_int]
    if not exact.empty:
        rank = int(exact.iloc[0]["rank_int"])
        return rank, f"按已导入一分一段表估算：{score_int} 分累计位次约 {rank}。"
    lower = df[df["score_int"] < score_int].sort_values("score_int", ascending=False)
    higher = df[df["score_int"] > score_int].sort_values("score_int")
    if not lower.empty:
        rank = int(lower.iloc[0]["rank_int"])
        return rank, f"未找到精确分数，按低一档 {int(lower.iloc[0]['score_int'])} 分估算位次约 {rank}。"
    if not higher.empty:
        rank = int(higher.iloc[0]["rank_int"])
        return rank, f"未找到精确分数，按高一档 {int(higher.iloc[0]['score_int'])} 分估算位次约 {rank}。"
    return None, ""
