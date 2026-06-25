from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


def _sheet_name(name: str) -> str:
    return name[:31].replace("/", "_").replace("\\", "_")


def export_results_to_excel(
    results_by_level: dict[str, pd.DataFrame],
    basket_df: pd.DataFrame | None,
    early_df: pd.DataFrame | None,
    volunteer_draft_df: pd.DataFrame | None,
    charter_risk_df: pd.DataFrame | None,
    params: dict[str, Any],
    registry_df: pd.DataFrame | None,
) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for level in ["冲", "稳", "保", "垫", "缺少历史数据"]:
            frame = results_by_level.get(level, pd.DataFrame())
            frame.to_excel(writer, sheet_name=_sheet_name(level), index=False)
        (basket_df if basket_df is not None else pd.DataFrame()).to_excel(writer, sheet_name="志愿篮子", index=False)
        (early_df if early_df is not None else pd.DataFrame()).to_excel(writer, sheet_name="提前批关注清单", index=False)
        (volunteer_draft_df if volunteer_draft_df is not None else pd.DataFrame()).to_excel(writer, sheet_name="96志愿草表", index=False)
        (charter_risk_df if charter_risk_df is not None else pd.DataFrame()).to_excel(writer, sheet_name="章程风险提醒", index=False)
        pd.DataFrame([params]).to_excel(writer, sheet_name="参数设置", index=False)
        (registry_df if registry_df is not None else pd.DataFrame()).to_excel(writer, sheet_name="数据来源说明", index=False)
    return output.getvalue()
