from __future__ import annotations

import pandas as pd


PLAN_COLUMNS = ["序号", "建议分组", "院校代码", "院校名称", "专业代码", "专业名称", "风险等级", "2026计划数", "2025最低位次", "学费", "警告", "推荐理由"]


def generate_volunteer_draft(results_df: pd.DataFrame, limit: int = 96) -> pd.DataFrame:
    if results_df is None or results_df.empty:
        return pd.DataFrame(columns=PLAN_COLUMNS)
    weights = {"冲": 20, "稳": 38, "保": 28, "垫": 10}
    selected_parts = []
    for level, quota in weights.items():
        frame = results_df[results_df["risk_level"] == level].copy()
        if frame.empty:
            continue
        frame["_rank"] = pd.to_numeric(frame.get("min_rank_2025"), errors="coerce").fillna(10**9)
        frame = frame.sort_values(["_rank", "school_name", "major_name"]).head(quota)
        selected_parts.append(frame.drop(columns=["_rank"]))
    draft = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    if len(draft) < limit:
        used = set(zip(draft.get("school_code", []), draft.get("major_code", []), draft.get("major_name", [])))
        rest = results_df[results_df["risk_level"].isin(["冲", "稳", "保", "垫"])].copy()
        rest = rest[
            ~rest.apply(lambda row: (row.get("school_code"), row.get("major_code"), row.get("major_name")) in used, axis=1)
        ]
        rest["_risk_order"] = rest["risk_level"].map({"稳": 1, "保": 2, "冲": 3, "垫": 4}).fillna(9)
        rest["_rank"] = pd.to_numeric(rest.get("min_rank_2025"), errors="coerce").fillna(10**9)
        draft = pd.concat([draft, rest.sort_values(["_risk_order", "_rank"]).drop(columns=["_risk_order", "_rank"]).head(limit - len(draft))], ignore_index=True)
    draft = draft.head(limit).reset_index(drop=True)
    output = pd.DataFrame(
        {
            "序号": range(1, len(draft) + 1),
            "建议分组": draft.get("risk_level", ""),
            "院校代码": draft.get("school_code", ""),
            "院校名称": draft.get("school_name", ""),
            "专业代码": draft.get("major_code", ""),
            "专业名称": draft.get("major_name", ""),
            "风险等级": draft.get("risk_level", ""),
            "2026计划数": draft.get("plan_count_2026", ""),
            "2025最低位次": draft.get("min_rank_2025", ""),
            "学费": draft.get("tuition", ""),
            "警告": draft.get("warnings", ""),
            "推荐理由": draft.get("risk_reason", ""),
        }
    )
    return output[PLAN_COLUMNS]
