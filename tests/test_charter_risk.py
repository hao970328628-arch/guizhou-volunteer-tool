from src.charter_risk import collect_charter_risks


def test_collect_charter_risks_from_remarks():
    warnings = collect_charter_risks("色盲色弱不予录取，详见招生章程")
    assert "请核验高校招生章程" in warnings
    assert any("色觉" in warning or "色盲" in warning for warning in warnings)
