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
from src.school_meta import save_school_meta, school_meta_template


st.set_page_config(page_title="贵州高考本科志愿筛选工具", layout="wide")
ensure_dirs()
ensure_school_meta_template()


def status_label(status: str) -> str:
    return {"available": "已导入", "missing": "缺失", "optional": "可选缺失"}.get(status, status)


def load_processed_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    catalog = load_processed_csv("catalog_2026.csv")
    admission_2025 = load_processed_csv("admission_2025_regular.csv")
    admission_2024 = load_processed_csv("admission_2024_regular.csv")
    early_2025 = load_processed_csv("early_admission_2025.csv")
    early_2024 = load_processed_csv("early_admission_2024.csv")
    school_meta = load_processed_csv("school_meta.csv")
    return catalog, admission_2025, admission_2024, early_2025, early_2024, school_meta


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
        logs.append(f"{Path(item['source_path']).name}: 成功 {result.success_rows} 行，失败 {result.failed_rows} 行，可疑 {result.suspicious_rows} 行。{message}")
        if result.dataframe.empty:
            continue
        key = (item["data_type"], int(item["year"]) if pd.notna(item["year"]) else 0)
        grouped.setdefault(key, []).append(result.dataframe)

    for (data_type, year), frames in grouped.items():
        frame = pd.concat(frames, ignore_index=True)
        if data_type == "catalog":
            save_dataframe(frame, "catalog_2026")
        elif data_type == "regular_admission":
            save_dataframe(frame, "admission_regular")
        elif data_type == "early_admission":
            save_dataframe(frame, "admission_early")
    return logs


if "basket" not in st.session_state:
    st.session_state.basket = pd.DataFrame()


st.title("贵州高考本科志愿筛选工具")
registry = build_data_registry(RAW_DIR)
summary = registry_summary(registry)

st.subheader("数据完整度")
metric_cols = st.columns(3)
metric_cols[0].metric("已找到文件", summary["available"])
metric_cols[1].metric("MVP 必需缺失", summary["missing_required"])
metric_cols[2].metric("可选缺失", summary["optional_missing"])

display_registry = registry.copy()
display_registry["状态"] = display_registry["status"].map(status_label)
st.dataframe(
    display_registry[["file_id", "year", "subject_group", "data_type", "batch_group", "状态", "source_path", "notes"]],
    use_container_width=True,
    hide_index=True,
)
missing_required = registry[(registry["status"] == "missing") & registry["is_required_for_mvp"]]
if not missing_required.empty:
    st.warning("部分 MVP 必需文件缺失，应用仍可运行，但推荐结果会受影响。")

with st.expander("数据导入与保存", expanded=False):
    st.caption("自动读取 data/raw，也可以上传 CSV/Excel/PDF 替代。PDF 为尽力解析，复杂版式建议导出为人工修正 CSV。")
    if st.button("一键解析 data/raw 并保存到 SQLite/CSV", type="primary"):
        with st.spinner("正在解析数据文件..."):
            logs = parse_available_files(registry)
        st.session_state["parse_logs"] = logs
        st.success("解析流程完成")
    uploaded = st.file_uploader("手动上传数据文件", type=["pdf", "csv", "xlsx", "xls"])
    c1, c2, c3, c4 = st.columns(4)
    manual_type = c1.selectbox("数据类型", ["catalog", "regular_admission", "early_admission"], key="manual_type")
    manual_year = c2.selectbox("年份", [2026, 2025, 2024], key="manual_year")
    manual_subject = c3.selectbox("科类", ["物理类", "历史类"], key="manual_subject")
    manual_batch = c4.selectbox("批次组", ["regular_undergraduate", "early_A", "early_B", "early_C"], key="manual_batch")
    if uploaded and st.button("解析上传文件"):
        upload_dir = RAW_DIR / "uploads"
        upload_dir.mkdir(exist_ok=True)
        target = upload_dir / uploaded.name
        target.write_bytes(uploaded.getvalue())
        result = load_data_file(target, manual_type, manual_year, manual_subject, manual_batch)
        st.write(f"成功 {result.success_rows} 行，失败 {result.failed_rows} 行，可疑 {result.suspicious_rows} 行")
        if not result.dataframe.empty:
            table = "catalog_2026" if manual_type == "catalog" else ("admission_early" if manual_type == "early_admission" else "admission_regular")
            save_dataframe(result.dataframe, table)
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
    template_type = st.selectbox("修正模板类型", ["regular_admission", "catalog", "early_admission"])
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
            table = "catalog_2026" if template_type == "catalog" else ("admission_early" if template_type == "early_admission" else "admission_regular")
            save_dataframe(result.dataframe, table, replace=False)
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
        st.success("学校属性库已保存。")

catalog_df, admission_2025_df, admission_2024_df, early_2025_df, early_2024_df, school_meta_df = load_processed_data()

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

if student_rank <= 0:
    st.warning("请补充全省位次，或导入一分一段表。冲稳保算法必须以位次为主。")

user_profile = {
    "subject_group": subject_group,
    "student_score": student_score,
    "student_rank": student_rank,
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
}

if st.button("生成普通本科批推荐", type="primary"):
    with st.spinner("正在筛选普通本科批志愿..."):
        st.session_state["regular_results"] = recommend_regular(
            catalog_df, admission_2025_df, admission_2024_df, user_profile, thresholds, school_meta_df
        )

results = st.session_state.get("regular_results", pd.DataFrame())
st.subheader("普通本科批结果")
if results.empty:
    st.info("暂无推荐结果。请先解析数据，或上传 CSV/Excel 替代 PDF 后再生成。")
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
            }
        )
        early_df = recommend_early(catalog_df, early_2025_df, early_2024_df, user_profile)
        st.dataframe(early_df, use_container_width=True, hide_index=True)

    export_bytes = export_results_to_excel(results_by_level, st.session_state.basket, early_df, user_profile, registry)
    st.download_button("导出 Excel", export_bytes, file_name="贵州高考本科志愿筛选结果.xlsx")

st.divider()
st.caption(DISCLAIMER)
