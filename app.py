from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import DISCLAIMER, PROCESSED_DIR, RAW_DIR, ensure_dirs
from src.data_loader import correction_template, load_data_file, load_parse_errors
from src.data_registry import build_data_registry, registry_summary
from src.db import ensure_school_meta_template, load_processed_csv, save_dataframe
from src.early_recommender import recommend_early
from src.export_excel import export_results_to_excel
from src.major_classifier import load_rules
from src.recommender import recommend_regular
from src.score_rank import estimate_rank
from src.school_meta import save_school_meta, school_meta_template
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


st.set_page_config(page_title="贵州高考本科志愿筛选工具", layout="wide")
ensure_dirs()
ensure_school_meta_template()


def status_label(status: str) -> str:
    return {"available": "已找到", "missing": "缺失", "optional": "可选缺失"}.get(status, status)


def table_name_for_data_type(data_type: str) -> str:
    if data_type == "catalog":
        return "catalog_2026"
    if data_type == "early_admission":
        return "admission_early"
    if data_type == "score_rank":
        return "score_rank"
    if data_type == "regular_admission":
        return "admission_regular"
    raise ValueError(f"未知数据类型：{data_type}")


def read_ready_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str).fillna("")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    raise ValueError(f"直接使用模式只支持 CSV/Excel：{path.suffix}")


def fill_default(df: pd.DataFrame, column: str, value: object) -> None:
    if column not in df.columns:
        df[column] = value
        return
    blank_mask = df[column].isna() | (df[column].astype(str).str.strip() == "")
    df.loc[blank_mask, column] = value


def prepare_ready_dataframe(
    df: pd.DataFrame,
    data_type: str,
    year: int,
    subject_group: str,
    batch_group: str,
) -> pd.DataFrame:
    out = df.copy().fillna("")
    if out.empty:
        return out

    fill_default(out, "year", year)
    fill_default(out, "subject_group", subject_group)

    if data_type in {"catalog", "regular_admission"}:
        fill_default(out, "batch_group", batch_group)
    if data_type == "catalog":
        fill_default(out, "batch", "本科批" if batch_group == "regular_undergraduate" else "本科提前批")
        fill_default(out, "early_batch_stage", batch_group.split("_", 1)[1] if batch_group.startswith("early_") else "")
        fill_default(out, "is_undergraduate", True)
        fill_default(out, "is_regular_undergraduate", batch_group == "regular_undergraduate")
        fill_default(out, "is_early_batch", batch_group.startswith("early_"))
    if data_type == "early_admission":
        fill_default(out, "early_batch_stage", batch_group.split("_", 1)[1] if batch_group.startswith("early_") else "")

    return out


def load_ready_dataframe(
    file_path: str | Path,
    data_type: str,
    year: int,
    subject_group: str,
    batch_group: str,
) -> tuple[pd.DataFrame, list[str]]:
    path = Path(file_path)
    if data_type not in {"catalog", "regular_admission", "early_admission", "score_rank"}:
        return pd.DataFrame(), [f"未知数据类型：{data_type}"]
    try:
        raw_df = read_ready_file(path)
        return prepare_ready_dataframe(raw_df, data_type, year, subject_group, batch_group), [
            "已跳过 PDF/表格解析，按标准数据直接保存。"
        ]
    except Exception as exc:
        return pd.DataFrame(), [f"直接读取失败：{exc}"]


def _file_size_label(path: Path) -> str:
    if not path.exists():
        return ""
    size_mb = path.stat().st_size / 1024 / 1024
    return f"{size_mb:.2f} MB" if size_mb >= 0.01 else f"{path.stat().st_size} B"


def build_processed_status() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for file_name, usage, required in PROCESSED_DATA_FILES:
        path = PROCESSED_DIR / file_name
        rows.append(
            {
                "file_name": file_name,
                "usage": usage,
                "required": required,
                "status": "可直接使用" if path.exists() else ("缺失" if required else "可选缺失"),
                "size": _file_size_label(path),
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


def parse_available_files(registry: pd.DataFrame) -> list[str]:
    logs: list[str] = []
    grouped: dict[tuple[str, int], list[pd.DataFrame]] = {}
    for _, item in registry[registry["status"] == "available"].iterrows():
        result = load_data_file(
            item["source_path"],
            item["data_type"],
            int(item["year"]) if pd.notna(item["year"]) else 0,
            item["subject_group"],
            item["batch_group"],
        )
        message = "；".join(result.messages)
        logs.append(
            f"{Path(item['source_path']).name}: 成功 {result.success_rows} 行，失败 {result.failed_rows} 行，"
            f"可疑 {result.suspicious_rows} 行。{message}"
        )
        if result.dataframe.empty:
            continue
        key = (item["data_type"], int(item["year"]) if pd.notna(item["year"]) else 0)
        grouped.setdefault(key, []).append(result.dataframe)

    for (data_type, _year), frames in grouped.items():
        frame = pd.concat(frames, ignore_index=True)
        save_dataframe(frame, table_name_for_data_type(data_type))
    return logs


if "basket" not in st.session_state:
    st.session_state.basket = pd.DataFrame()


st.title("贵州高考本科志愿筛选工具")
registry = build_data_registry(RAW_DIR)
summary = registry_summary(registry)
processed_status = build_processed_status()
processed_available = int((processed_status["status"] == "可直接使用").sum()) if not processed_status.empty else 0
processed_missing_required = int(
    ((processed_status["status"] == "缺失") & processed_status["required"]).sum()
) if not processed_status.empty else 0
processed_optional_missing = int((processed_status["status"] == "可选缺失").sum()) if not processed_status.empty else 0

st.subheader("可直接使用的数据")
metric_cols = st.columns(3)
metric_cols[0].metric("标准数据文件", processed_available)
metric_cols[1].metric("必需缺失", processed_missing_required)
metric_cols[2].metric("可选缺失", processed_optional_missing)

display_processed = processed_status.copy()
display_processed["必需"] = display_processed["required"].map({True: "是", False: "否"})
st.dataframe(
    display_processed[["file_name", "usage", "必需", "status", "size", "path"]],
    use_container_width=True,
    hide_index=True,
)
if processed_missing_required:
    missing_files = missing_required_processed_files(processed_status)
    st.warning(
        "缺少可直接使用的标准数据："
        + "、".join(missing_files)
        + "。可把标准 CSV 放入 data/processed，或在下方上传已整理 CSV/Excel 后直接保存。"
    )
else:
    st.success("已找到普通本科批推荐所需的标准数据，生成推荐时无需再解析 PDF。")

with st.expander("原始文件解析状态（可选）", expanded=False):
    st.caption("这里只用于从 data/raw 生成标准 CSV。已有 data/processed 标准数据时，可以忽略这里的缺失提示。")
    metric_cols = st.columns(3)
    metric_cols[0].metric("已找到原始文件", summary["available"])
    metric_cols[1].metric("MVP 原始文件缺失", summary["missing_required"])
    metric_cols[2].metric("可选原始文件缺失", summary["optional_missing"])

    display_registry = registry.copy()
    display_registry["状态"] = display_registry["status"].map(status_label)
    st.dataframe(
        display_registry[["file_id", "year", "subject_group", "data_type", "batch_group", "状态", "source_path", "notes"]],
        use_container_width=True,
        hide_index=True,
    )
    missing_required = registry[(registry["status"] == "missing") & registry["is_required_for_mvp"]]
    if not missing_required.empty:
        st.info("原始文件缺失不会阻止已处理数据直接使用，只会影响重新解析生成标准 CSV。")

with st.expander("数据导入与保存", expanded=False):
    st.caption("推荐优先使用 data/processed 中的标准 CSV。直接导入不会调用 PDF 解析；只有需要从原始 PDF/非标准表格生成标准数据时，再使用慢速解析。")

    st.markdown("#### 直接使用已整理数据（推荐）")
    st.caption("上传已经整理好的标准 CSV/Excel，会直接保存到 data/processed，不走 PDF 表格提取和解析器。")
    ready_uploaded = st.file_uploader("上传已整理标准 CSV/Excel", type=["csv", "xlsx", "xls"], key="ready_upload")
    r1, r2, r3, r4 = st.columns(4)
    ready_type = r1.selectbox("数据类型", ["catalog", "regular_admission", "early_admission", "score_rank"], key="ready_type")
    ready_year = r2.selectbox("年份", [2026, 2025, 2024], key="ready_year")
    ready_subject = r3.selectbox("科类", ["物理类", "历史类"], key="ready_subject")
    ready_batch = r4.selectbox("批次组", ["regular_undergraduate", "early_A", "early_B", "early_C"], key="ready_batch")
    ready_replace = st.checkbox("覆盖同类型同年份旧数据", value=True, key="ready_replace")
    if ready_uploaded and st.button("直接保存并使用", type="primary"):
        ready_dir = RAW_DIR / "ready"
        ready_dir.mkdir(exist_ok=True)
        target = ready_dir / ready_uploaded.name
        target.write_bytes(ready_uploaded.getvalue())
        ready_df, ready_messages = load_ready_dataframe(target, ready_type, ready_year, ready_subject, ready_batch)
        if ready_df.empty:
            st.warning("没有读取到可保存的数据。" + ("；".join(ready_messages) if ready_messages else ""))
        else:
            table = table_name_for_data_type(ready_type)
            save_dataframe(ready_df, table, replace=ready_replace)
            load_processed_data.clear()
            st.success(f"已跳过解析，保存 {len(ready_df)} 行到标准数据：{table}")
            for message in ready_messages:
                st.caption(message)

    st.markdown("#### 慢速解析原始 PDF/表格（可选）")
    st.caption("仅当没有标准 CSV/Excel，需要从 data/raw 或上传的 PDF/非标准表格生成标准数据时使用。")
    if st.button("一键解析 data/raw 并保存到 SQLite/CSV"):
        with st.spinner("正在解析数据文件..."):
            logs = parse_available_files(registry)
        st.session_state["parse_logs"] = logs
        load_processed_data.clear()
        st.success("解析流程完成")
    uploaded = st.file_uploader("手动上传并解析数据文件", type=["pdf", "csv", "xlsx", "xls"], key="parse_upload")
    c1, c2, c3, c4 = st.columns(4)
    manual_type = c1.selectbox("解析数据类型", ["catalog", "regular_admission", "early_admission", "score_rank"], key="manual_type")
    manual_year = c2.selectbox("解析年份", [2026, 2025, 2024], key="manual_year")
    manual_subject = c3.selectbox("解析科类", ["物理类", "历史类"], key="manual_subject")
    manual_batch = c4.selectbox("解析批次组", ["regular_undergraduate", "early_A", "early_B", "early_C"], key="manual_batch")
    if uploaded and st.button("解析上传文件"):
        upload_dir = RAW_DIR / "uploads"
        upload_dir.mkdir(exist_ok=True)
        target = upload_dir / uploaded.name
        target.write_bytes(uploaded.getvalue())
        result = load_data_file(target, manual_type, manual_year, manual_subject, manual_batch)
        st.write(f"成功 {result.success_rows} 行，失败 {result.failed_rows} 行，可疑 {result.suspicious_rows} 行")
        if not result.dataframe.empty:
            save_dataframe(result.dataframe, table_name_for_data_type(manual_type))
            load_processed_data.clear()
            st.success("已保存")
    for log in st.session_state.get("parse_logs", []):
        st.text(log)

    st.markdown("#### PDF 解析修正")
    parse_errors = load_parse_errors()
    if parse_errors.empty:
        st.caption("暂无解析失败或可疑行。")
    else:
        st.caption(f"当前 parse_errors.csv 记录 {len(parse_errors)} 行。")
        st.dataframe(parse_errors.tail(200), use_container_width=True, hide_index=True)
        st.download_button(
            "下载解析问题行",
            parse_errors.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
            file_name="parse_errors.csv",
        )
    template_type = st.selectbox("修正模板类型", ["regular_admission", "catalog", "early_admission", "score_rank"])
    template = correction_template(template_type)
    st.download_button(
        "下载人工修正模板",
        template.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
        file_name=f"{template_type}_correction_template.csv",
    )
    corrected = st.file_uploader("上传修正后的 CSV/Excel", type=["csv", "xlsx", "xls"], key="corrected_upload")
    cc1, cc2, cc3 = st.columns(3)
    corrected_year = cc1.selectbox("修正数据年份", [2025, 2024, 2026], key="corrected_year")
    corrected_subject = cc2.selectbox("修正数据科类", ["物理类", "历史类"], key="corrected_subject")
    corrected_batch = cc3.selectbox("修正批次组", ["regular_undergraduate", "early_A", "early_B", "early_C"], key="corrected_batch")
    if corrected and st.button("导入修正数据"):
        upload_dir = RAW_DIR / "corrections"
        upload_dir.mkdir(exist_ok=True)
        target = upload_dir / corrected.name
        target.write_bytes(corrected.getvalue())
        result = load_data_file(target, template_type, corrected_year, corrected_subject, corrected_batch)
        if not result.dataframe.empty:
            save_dataframe(result.dataframe, table_name_for_data_type(template_type), replace=False)
            load_processed_data.clear()
            st.success(f"已追加修正数据 {len(result.dataframe)} 行")
        else:
            st.warning("修正文件未解析出有效行，请检查列名。")

    st.markdown("#### 学校属性库")
    meta_upload = st.file_uploader("上传 school_meta CSV/Excel", type=["csv", "xlsx", "xls"], key="school_meta_upload")
    st.download_button(
        "下载 school_meta 模板",
        school_meta_template().to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
        file_name="school_meta_template.csv",
    )
    if meta_upload and st.button("保存学校属性库"):
        meta_dir = RAW_DIR / "uploads"
        meta_dir.mkdir(exist_ok=True)
        meta_path = meta_dir / meta_upload.name
        meta_path.write_bytes(meta_upload.getvalue())
        if meta_path.suffix.lower() == ".csv":
            meta_df = pd.read_csv(meta_path, dtype=str).fillna("")
        else:
            meta_df = pd.read_excel(meta_path, dtype=str).fillna("")
        save_school_meta(meta_df)
        load_processed_data.clear()
        st.success("学校属性库已保存。")

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
    st.warning("请补充全省位次，或导入一分一段表。冲稳保算法必须以位次为主。")

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
            + "。请在“数据导入与保存”里上传已整理标准 CSV/Excel，或先使用慢速解析生成标准数据。"
        )
    elif effective_rank <= 0:
        st.session_state["regular_results"] = pd.DataFrame()
        st.error("还不能生成推荐：请先填写全省位次，或导入一分一段表用于估算位次。")
    else:
        with st.spinner("正在筛选普通本科批志愿..."):
            st.session_state["regular_results"] = recommend_regular(
                catalog_df, admission_2025_df, admission_2024_df, user_profile, thresholds, school_meta_df
            )

results = st.session_state.get("regular_results", pd.DataFrame())
st.subheader("普通本科批结果")
if results.empty:
    if not can_generate:
        st.info("等待标准数据：请先准备 catalog_2026.csv、admission_2025_regular.csv、admission_2024_regular.csv。")
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
            st.dataframe(frame, use_container_width=True, hide_index=True)

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
        st.dataframe(st.session_state.basket, use_container_width=True, hide_index=True)
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
    st.dataframe(draft_df, use_container_width=True, hide_index=True)

    charter_risk_df = results[results["warnings"].fillna("").astype(str).str.len() > 0][
        ["school_name", "major_name", "risk_level", "warnings", "risk_reason"]
    ].copy()
    st.subheader("招生章程风险提醒")
    st.dataframe(charter_risk_df, use_container_width=True, hide_index=True)

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
            st.dataframe(early_df[early_df["批次段 A/B/C"] == stage], use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(early_df[early_df["风险提示"].fillna("").astype(str).str.contains("资格|体检|政审|面试|体能|身高|视力|性别")], use_container_width=True, hide_index=True)
    with tabs[4]:
        st.dataframe(early_df[early_df["风险提示"].fillna("").astype(str).str.contains("风险较高|不可推荐")], use_container_width=True, hide_index=True)

if not results.empty or not early_df.empty:
    results_by_level = {level: results[results["risk_level"] == level].copy() if not results.empty else pd.DataFrame() for level in ["冲", "稳", "保", "垫", "缺少历史数据"]}
    draft_df = generate_volunteer_draft(results) if not results.empty else pd.DataFrame()
    charter_risk_df = (
        results[results["warnings"].fillna("").astype(str).str.len() > 0][["school_name", "major_name", "risk_level", "warnings", "risk_reason"]].copy()
        if not results.empty
        else pd.DataFrame()
    )
    export_bytes = export_results_to_excel(results_by_level, st.session_state.basket, early_df, draft_df, charter_risk_df, user_profile, registry)
    st.download_button("导出 Excel", export_bytes, file_name="贵州高考本科志愿筛选结果.xlsx")

st.divider()
st.caption(DISCLAIMER)
