import pandas as pd

from src.score_rank import estimate_rank, parse_score_rank_dataframe


def test_parse_score_rank_dataframe_and_estimate():
    raw = pd.DataFrame([{"分数": "600", "本段人数": "10", "累计人数": "1000"}])
    parsed = parse_score_rank_dataframe(raw, 2024, "物理类")
    assert parsed.iloc[0]["score"] == 600
    assert parsed.iloc[0]["cumulative_count"] == 1000
    rank, note = estimate_rank(parsed, 600, "物理类")
    assert rank == 1000
    assert "估算" in note
