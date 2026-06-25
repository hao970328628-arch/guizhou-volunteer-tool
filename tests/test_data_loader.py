import pandas as pd

from src.data_loader import _fallback_from_text, correction_template


def test_correction_template_regular_has_required_columns():
    template = correction_template("regular_admission")
    assert {"school_code", "major_code", "min_score", "min_rank"} <= set(template.columns)


def test_text_fallback_parses_regular_admission_line():
    records = [{"source_file": "x.pdf", "source_page": 1, "raw_text": "1001 贵州大学 001 计算机科学与技术 普通类 4 4 580 12000"}]
    parsed = _fallback_from_text(records, "regular_admission", 2025, "物理类", "regular_undergraduate")
    assert len(parsed) == 1
    assert str(parsed.iloc[0]["school_code"]) == "1001"
    assert parsed.iloc[0]["min_rank"] == 12000
