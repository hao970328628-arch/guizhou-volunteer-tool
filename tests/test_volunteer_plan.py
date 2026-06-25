import pandas as pd

from src.volunteer_plan import generate_volunteer_draft


def test_generate_volunteer_draft_limits_to_96():
    rows = []
    for idx in range(120):
        rows.append(
            {
                "risk_level": ["冲", "稳", "保", "垫"][idx % 4],
                "school_code": f"{idx:04d}",
                "school_name": f"学校{idx}",
                "major_code": f"{idx:03d}",
                "major_name": f"专业{idx}",
                "plan_count_2026": "4",
                "min_rank_2025": str(10000 + idx),
                "tuition": "5000",
                "warnings": "",
                "risk_reason": "测试",
            }
        )
    draft = generate_volunteer_draft(pd.DataFrame(rows))
    assert len(draft) == 96
    assert draft.iloc[0]["序号"] == 1
