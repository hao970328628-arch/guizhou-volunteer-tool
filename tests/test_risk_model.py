from src.risk_model import classify_risk


def test_risk_levels():
    assert classify_risk(20000, 18000).risk_level == "冲"
    assert classify_risk(20000, 21000).risk_level == "稳"
    assert classify_risk(20000, 26000).risk_level == "保"
    assert classify_risk(20000, 30000).risk_level == "垫"
    assert classify_risk(20000, 15000).risk_level == "不可推荐"


def test_missing_history_is_not_forced_to_stable():
    assert classify_risk(20000, None).risk_level == "缺少历史数据"


def test_high_volatility_downgrades_level():
    result = classify_risk(20000, 21000, rank_2024=15000)
    assert result.risk_level == "保"
    assert any("近两年位次波动超过20%" in warning for warning in result.warnings)
