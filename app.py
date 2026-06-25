from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import DISCLAIMER, PROCESSED_DIR
from src.db import load_processed_csv
from src.early_recommender import recommend_early
from src.export_excel import export_results_to_excel
from src.major_classifier import load_rules
from src.recommender import recommend_regular
from src.score_rank import estimate_rank
from src.volunteer_plan import generate_volunteer_draft


PROCESSED_DATA_FILES: list[tuple[str, str, bool]] = [
    ("catalog_2026.csv", "2026 招生专业目录", True),
    ("admission_2025_regular.csv", "2025 普通本科批投档", True),
    ("admission_2024_regular.csv", "2024 普通本科批投档", True),
    ("early_admission_2025.csv", "2025 提前批 A/B/C", False),
    ("early_admission_2024.csv", "2024 提前批 A/B/C", False),
    ("score_rank_2024.csv", "2024 一分一段/分数段", False),
    ("school_meta.csv", "学校属性库", False),
]
MANIFEST_PATH = PROCESSED_DIR / "manifest.json"


st.set_page_config(page_title="贵州高考本科志愿筛选工具", layout="wide")


def load_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _manifest_file_map(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return {}
    mapped: dict[str, dict[str, object]] = {}
    for item in files:
        if not isinstance(item, dict):
            continue
        file_name = item.get("file_name") or Path(str(item.get("path", ""))).name
        if file_name:
            mapped[str(file_name)] = item
    return mapped


def _file_size_label(path: Path) -> str:
    if not path.exists():
        return ""
    size_mb = path.stat().st_size / 1024 / 1024
    return f"{size_mb:.2f} MB" if size_mb >= 0.01 else f"{path.stat().st_size} B"


def _sha_short(value: object) -> str:
    sha = str(value or "")
    return sha[:12] if sha else ""


def build_processed_status() -> pd.DataFrame:
    manifest = load_manifest()
    manifest_files = _manifest_file_map(manifest)
    rows: list[dict[str, object]] = []
    for file_name, usage, required in PROCESSED_DATA_FILES:
        path = PROCESSED_DIR / file_name
        manifest_item = manifest_files.get(file_name, {})
        source_files = manifest_item.get("source_files", [])
        source_count = len(source_files) if isinstance(source_files, list) else 0
        rows.append(
            {
                "file_name": file_name,
                "usage": usage,
                "required": required,
                "status": "可用" if path.exists() else ("缺失" if required else "可选缺失"),
                "rows": manifest_item.get("rows", ""),
                "size": _file_size_label(path),
                "sha256": _sha_short(manifest_item.get("sha256", "")),
                "source_files_count": source_count,
                "path": str(path),
            }
        )
    return pd.DataFrame(rows)


def missing_required_processed_files(processed_status_df: pd.DataFrame) -> list[str]:
    if processed_status_df.empty:
        return [file_name for file_name, _usage, required in PROCESSED_DATA_FILES if required]
    missing = processed_status_df[(processed_status_df["required"]) & (processed_status_df["status"] == "缺失")]
    return missing["file_name"].astype(str).tolist()


def can_generate_regular(catalog_df: pd.DataFrame, admission_2025_df: pd.DataFrame, admission_2024_df: pd.DataFrame) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if catalog_df.empty:
        missing.append("catalog_2026.csv")
    if admission_2025_df.empty:
        missing.append("admission_2025_regular.csv")
    if admission_2024_df.empty:
        missing.append("admission_2024_regular.csv")
    return not missing, missing


@st.cache_data(show_spinner=False)
def load_processed_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    catalog = load_processed_csv("catalog_2026.csv")
    admission_2025 = load_processed_csv("admission_2025_regular.csv")
    admission_2024 = load_processed_csv("admission_2024_regular.csv")
    early_2025 = load_processed_csv("early_admission_2025.csv")
    early_2024 = load_processed_csv("early_admission_2024.csv")
    school_meta = load_processed_csv("school_meta.csv")
    score_rank = load_processed_csv("score_rank_2024.csv")
    return catalog, admission_2025, admission_2024, early_2025, early_2024, school_meta, score_rank


if "basket" not in st.session_state:
    st.session_state.basket = pd.DataFrame()


st.title("贵州高考本科志愿筛选工具")
processed_status = build_processed_status()
manifest = load_manifest()
processed_available = int((processed_status["status"] == "可用").sum()) if not processed_status.empty else 0
required_available = int(
    ((processed_status["status"] == "可用") & processed_status["required"]).sum()
) if not processed_status.empty else 0
processed_missing_required = int(
    ((processed_status["status"] == "缺失") & processed_status["required"]).sum()
) if not processed_status.empty else 0
processed_optional_missing = int((processed_status["status"] == "可选缺失").sum()) if not processed_status.empty else 0

st.subheader("数据状态摘要")
metric_cols = st.columns(4)
metric_cols[0].metric("标准数据文件", processed_available)
metric_cols[1].metric("必需可用", required_available)
metric_cols[2].metric("必需缺失", processed_missing_required)
metric_cols[3].metric("可选缺失", processed_optional_missing)

build_time = manifest.get("build_time") if isinstance(manifest, dict) else ""
if build_time:
    st.caption(f"数据包构建时间：{build_time}")
else:
    st.caption("未找到 data/processed/manifest.json；应用仍会尝试读取已存在的标准 CSV。")

display_processed = processed_status.copy()
display_processed["必需"] = display_processed["required"].map({True: "是", False: "否"})
st.dataframe(
    display_processed[["file_name", "usage", "必需", "status", "rows", "size", "sha256", "source_files_count", "path"]],
    width="stretch",
    hide_index=True,
)
if processed_missing_required:
    missing_files = missing_required_processed_files(processed_status)
    st.warning(
        "当前部署缺少预构建标准数据："
        + "、".join(missing_files)
        + "。请开发者在发布前运行 `python scripts/build_processed_data.py --force`，并随项目发布 data/processed 数据包。"
    )
else:
    st.success("已找到普通本科批推荐所需的预构建数据，浏览器端只读取内置数据包。")

catalog_df, admission_2025_df, admission_2024_df, early_2025_df, early_2024_df, school_meta_df, score_rank_df = load_processed_data()

left, right = st.columns([1, 1])
with left:
    st.subheader("考生信息")
    subject_group = st.selectbox("科类", ["物理类", "历史类"])
    student_score = st.number_input("高考分数", min_value=0, max_value=750, value=550)
    student_rank = st.number_input("全省位次", min_value=0, value=20000)
    first_subject = st.selectbox("首选科目", ["物理", "历史"], index=0 if subject_group == "物理类" else 1)
    reselect_subjects = st.multiselect("再选科目", ["化学", "生物", "思想政治", "地理"], default=["化学", "生物"] if subject_group == "物理类" else [])
    is_minority = st.checkbox("是否少数民族")
    accept_preparatory = st.checkbox("接受少数民族预科")
    accept_ethnic_class = st.checkbox("接受民族班")
    has_national_special = st.checkbox("有国家专项资格")
    has_local_special = st.checkbox("有地方专项资格")

with right:
    st.subheader("志愿偏好")
    accept_chinese_foreign = st.checkbox("接受中外合作办学 / 高收费专业")
    tuition_limit = st.number_input("学费上限", min_value=0, value=10000, step=1000)
    province_text = st.text_input("地区偏好（逗号分隔，可留空）")
    school_nature = st.multiselect("学校性质偏好", ["公办", "民办", "独立学院", "职业本科"], default=[])
    show_directional = st.checkbox("显示定向", value=False)
    show_border = st.checkbox("显示边防军子女预科班", value=False)
    show_early_batch = st.checkbox("显示提前批参考模块", value=False)

st.subheader("专业筛选")
rules = load_rules()
level1_options = [key for key in rules.keys() if key != "其他"] + ["其他"]
major_level1 = st.multiselect("一级专业大类", level1_options)
level2_options = []
for level1 in major_level1:
    level2_options.extend(list(rules.get(level1, {}).keys()))
major_level2 = st.multiselect("二级专业大类", sorted(set(level2_options)))
major_white = st.text_area("专业关键词白名单", placeholder="例如：计算机, 临床医学")
major_black = st.text_area("专业关键词黑名单", placeholder="例如：护理, 土木")

st.subheader("风险阈值")
t1, t2, t3, t4 = st.columns(4)
expand_sprint = st.checkbox("扩大冲刺范围", value=False)
sprint_low = t1.number_input("冲-下限", value=-0.20 if expand_sprint else -0.15, step=0.01, format="%.2f")
stable_high = t2.number_input("稳-上限", value=0.12, step=0.01, format="%.2f")
safe_high = t3.number_input("保-上限", value=0.35, step=0.01, format="%.2f")
t4.info("建议比例：冲 20%，稳 40%，保 30%，垫 10%。")
thresholds = {"冲": (sprint_low, 0.0), "稳": (0.0, stable_high), "保": (stable_high, safe_high), "垫": (safe_high, float("inf"))}

estimated_rank, rank_estimate_note = estimate_rank(score_rank_df, student_score, subject_group)
effective_rank = student_rank
if student_rank <= 0 and estimated_rank:
    effective_rank = estimated_rank
    st.info(rank_estimate_note)
elif student_rank <= 0:
    st.warning("请补充全省位次，或请开发者在预构建数据包内加入一分一段表。冲稳保算法必须以位次为主。")

user_profile = {
    "subject_group": subject_group,
    "student_score": student_score,
    "student_rank": effective_rank,
    "candidate_subjects": [first_subject] + reselect_subjects,
    "is_minority": is_minority,
    "accept_preparatory": accept_preparatory,
    "accept_ethnic_class": accept_ethnic_class,
    "has_national_special": has_national_special,
    "has_local_special": has_local_special,
    "accept_chinese_foreign": accept_chinese_foreign,
    "tuition_limit": tuition_limit,
    "province_prefs": [p.strip() for p in province_text.replace("，", ",").split(",") if p.strip()],
    "school_nature": school_nature,
    "show_directional": show_directional,
    "show_border_guard_preparatory": show_border,
    "major_level1": major_level1,
    "major_level2": major_level2,
    "major_white_keywords": major_white,
    "major_black_keywords": major_black,
    "show_early_batch": show_early_batch,
    "requires_early_checks": True,
}

can_generate, missing_regular_files = can_generate_regular(catalog_df, admission_2025_df, admission_2024_df)
if st.button("生成普通本科批推荐", type="primary"):
    if not can_generate:
        st.session_state["regular_results"] = pd.DataFrame()
        st.error(
            "还不能生成普通本科批推荐，缺少标准数据文件："
            + "、".join(missing_regular_files)
            + "。请开发者先运行 `python scripts/build_processed_data.py --force` 生成预构建数据包。"
        )
    elif effective_rank <= 0:
        st.session_state["regular_results"] = pd.DataFrame()
        st.error("还不能生成推荐：请先填写全省位次，或使用包含一分一段表的预构建数据包估算位次。")
    else:
        with st.spinner("正在筛选普通本科批志愿..."):
            st.session_state["regular_results"] = recommend_regular(
                catalog_df, admission_2025_df, admission_2024_df, user_profile, thresholds, school_meta_df
            )

results = st.session_state.get("regular_results", pd.DataFrame())
st.subheader("普通本科批结果")
if results.empty:
    if not can_generate:
        st.info("等待预构建数据：请先准备 catalog_2026.csv、admission_2025_regular.csv、admission_2024_regular.csv。")
    else:
        st.info("暂无推荐结果。请点击“生成普通本科批推荐”，或调整筛选条件后再试。")
else:
    tabs = st.tabs(["冲", "稳", "保", "垫", "缺少历史数据"])
    results_by_level = {}
    for tab, level in zip(tabs, ["冲", "稳", "保", "垫", "缺少历史数据"]):
        frame = results[results["risk_level"] == level].copy()
        results_by_level[level] = frame
        with tab:
            st.caption(f"{level}：{len(frame)} 条")
            st.dataframe(frame, width="stretch", hide_index=True)

    st.subheader("普通本科批志愿篮子")
    labels = [
        f"{idx}｜{row.school_name}｜{row.major_name}｜{row.risk_level}"
        for idx, row in results.reset_index(drop=True).iterrows()
        if row.risk_level in {"冲", "稳", "保", "垫"}
    ]
    selected_label = st.selectbox("选择加入志愿篮子", [""] + labels)
    if st.button("加入志愿篮子") and selected_label:
        idx = int(selected_label.split("｜", 1)[0])
        row = results.reset_index(drop=True).iloc[[idx]]
        st.session_state.basket = pd.concat([st.session_state.basket, row], ignore_index=True).drop_duplicates(
            subset=["school_code", "major_code", "major_name"], keep="first"
        )
    if not st.session_state.basket.empty:
        st.write(st.session_state.basket.groupby("risk_level").size().rename("数量"))
        st.dataframe(st.session_state.basket, width="stretch", hide_index=True)
        b1, b2 = st.columns([2, 1])
        remove_options = [
            f"{idx}｜{row.school_name}｜{row.major_name}｜{row.risk_level}"
            for idx, row in st.session_state.basket.reset_index(drop=True).iterrows()
        ]
        remove_label = b1.selectbox("从志愿篮子移除", [""] + remove_options)
        if b2.button("移除所选") and remove_label:
            idx = int(remove_label.split("｜", 1)[0])
            st.session_state.basket = st.session_state.basket.reset_index(drop=True).drop(index=idx).reset_index(drop=True)
        if st.button("清空志愿篮子"):
            st.session_state.basket = pd.DataFrame()

    draft_df = generate_volunteer_draft(results)
    st.subheader("96 个“专业+院校”志愿草表")
    st.caption("按默认比例生成：冲 20、稳 38、保 28、垫 10；不足 96 个时按稳、保、冲、垫顺序补齐。")
    st.dataframe(draft_df, width="stretch", hide_index=True)

    charter_risk_df = results[results["warnings"].fillna("").astype(str).str.len() > 0][
        ["school_name", "major_name", "risk_level", "warnings", "risk_reason"]
    ].copy()
    st.subheader("招生章程风险提醒")
    st.dataframe(charter_risk_df, width="stretch", hide_index=True)

early_df = pd.DataFrame()
if show_early_batch:
    st.subheader("提前批参考模块")
    ec1, ec2, ec3, ec4 = st.columns(4)
    user_profile.update(
        {
            "show_early_A": ec1.checkbox("查看 A 段", value=True),
            "show_early_B": ec2.checkbox("查看 B 段", value=True),
            "show_early_C": ec3.checkbox("查看 C 段", value=True),
            "accept_military": ec4.checkbox("接受军校"),
            "accept_police_judicial": st.checkbox("接受公安司法类"),
            "accept_navigation": st.checkbox("接受航海类"),
            "accept_public_teacher": st.checkbox("接受公费师范"),
            "accept_teacher_special": st.checkbox("接受优师专项"),
            "accept_free_medical": st.checkbox("接受免费医学生"),
            "accept_comprehensive": st.checkbox("接受综合评价"),
            "accept_directional_early": st.checkbox("接受提前批定向"),
            "requires_early_checks": st.checkbox("已完成或愿意完成体检、政审、面试、体能测试等要求", value=True),
        }
    )
    early_df = recommend_early(catalog_df, early_2025_df, early_2024_df, user_profile)
    tabs = st.tabs(["A 段关注", "B 段关注", "C 段关注", "资格待核验", "不建议填报"])
    stage_map = [("A", tabs[0]), ("B", tabs[1]), ("C", tabs[2])]
    for stage, tab in stage_map:
        with tab:
            st.dataframe(early_df[early_df["批次段 A/B/C"] == stage], width="stretch", hide_index=True)
    with tabs[3]:
        st.dataframe(early_df[early_df["风险提示"].fillna("").astype(str).str.contains("资格|体检|政审|面试|体能|身高|视力|性别")], width="stretch", hide_index=True)
    with tabs[4]:
        st.dataframe(early_df[early_df["风险提示"].fillna("").astype(str).str.contains("风险较高|不可推荐")], width="stretch", hide_index=True)

if not results.empty or not early_df.empty:
    results_by_level = {level: results[results["risk_level"] == level].copy() if not results.empty else pd.DataFrame() for level in ["冲", "稳", "保", "垫", "缺少历史数据"]}
    draft_df = generate_volunteer_draft(results) if not results.empty else pd.DataFrame()
    charter_risk_df = (
        results[results["warnings"].fillna("").astype(str).str.len() > 0][["school_name", "major_name", "risk_level", "warnings", "risk_reason"]].copy()
        if not results.empty
        else pd.DataFrame()
    )
    export_bytes = export_results_to_excel(results_by_level, st.session_state.basket, early_df, draft_df, charter_risk_df, user_profile, processed_status)
    st.download_button("导出 Excel", export_bytes, file_name="贵州高考本科志愿筛选结果.xlsx")

st.divider()
st.caption(DISCLAIMER)
