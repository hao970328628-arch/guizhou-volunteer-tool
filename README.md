# 贵州高考本科志愿筛选工具

这是一个本地运行的 Streamlit Web 应用，用于贵州普通类本科志愿填报辅助筛选。工具优先支持普通本科批的“冲、稳、保、垫、缺少历史数据”分类；本科提前批 A/B/C 段作为独立参考模块，默认关闭，不会混入普通本科批志愿篮子。

## 运行方式

```bash
pip install -r requirements.txt
streamlit run app.py
```

如果当前 Python 环境缺少依赖，请先在项目目录内执行安装命令。

## 推荐方式：直接使用已整理数据

如果已经有整理好的标准 CSV/Excel，不需要再解析 PDF。应用会优先读取 `data/processed/` 下的标准 CSV，生成推荐时直接使用这些数据：

- `data/processed/catalog_2026.csv`：2026 招生专业目录
- `data/processed/admission_2025_regular.csv`：2025 普通本科批投档数据
- `data/processed/admission_2024_regular.csv`：2024 普通本科批投档数据
- `data/processed/early_admission_2025.csv`：2025 提前批 A/B/C，可选
- `data/processed/early_admission_2024.csv`：2024 提前批 A/B/C，可选
- `data/processed/score_rank_2024.csv`：一分一段或分数段统计表，可选
- `data/processed/school_meta.csv`：学校属性库，可选

也可以在页面“数据导入与保存”里使用“直接使用已整理数据（推荐）”上传标准 CSV/Excel。这个入口只读取并保存文件，不调用 PDF 表格提取，也不走解析器。上传文件如果已有 `year`、`subject_group`、`batch_group`、`early_batch_stage` 等字段，会保留原值；缺少这些字段时，会用页面选择项补齐。

标准 CSV 建议使用项目模板中的英文字段，例如 `school_code`、`school_name`、`major_code`、`major_name`、`plan_count`、`min_score`、`min_rank`、`reselect_requirement`、`remarks` 等。字段越完整，匹配和筛选效果越好。

## 原始数据文件位置

如果还没有标准 CSV，才需要使用慢速解析流程。原始文件放在：

- `data/raw/catalog/`：2026 招生专业目录 PDF、CSV 或 Excel
- `data/raw/admission/2025/`：2025 普通本科批投档、提前批 A/B/C
- `data/raw/admission/2024/`：2024 普通本科批投档、提前批 A/B/C
- `data/raw/score_rank/`：一分一段或分数段统计表，可选

本项目已按上述目录复制当前工作区已有 PDF，原文件仍保留在父目录。

注意：原始 PDF 默认不提交到 GitHub。部分招生目录 PDF 超过 GitHub 普通文件 100 MB 上限，请在本地保留，或改用 Git LFS/网盘/Release 附件管理。

## 用 CSV/Excel 替代 PDF

PDF 自动解析是尽力解析，复杂表格可能需要人工修正。你可以在页面“数据导入与保存”中上传 CSV 或 Excel，并选择数据类型、年份、科类和批次组。

普通本科批投档表建议列名包含：

- 院校代码
- 院校名称
- 专业代码
- 专业名称
- 招考类型
- 计划数
- 投档人数
- 投档最低分
- 投档最低位次

招生专业目录建议列名包含：

- 批次
- 类别
- 院校代码
- 院校名称
- 所在城市
- 专业代码
- 专业名称
- 再选科目
- 计划数
- 语种
- 学制
- 学费
- 备注

## 第三阶段能力

- 提前批 A/B/C 独立参考模块：按 A/B/C、资格待核验、不建议填报分组展示，不进入普通本科批志愿篮子。
- 招生章程风险提醒：自动汇总体检、政审、面试、体能、身高、视力、性别、单科、外语语种、章程核验等提示。
- 一分一段辅助：可导入 `score_rank` 数据，当用户没有输入位次时，按分数估算位次并提示估算来源。
- 96 志愿草表：根据普通本科批推荐结果生成“专业+院校”草表，并导出到 Excel。
- Excel 导出增加 `96志愿草表` 和 `章程风险提醒` sheet。

## 重要说明

本工具仅用于高考志愿填报辅助分析，不构成录取承诺。最终填报请以贵州省招生考试院公布的正式招生专业目录、志愿填报规定、高校招生章程和志愿填报系统为准。专业对身体条件、单科成绩、外语语种、民族资格、专项资格、体检、政审、面试、体能测试等有特殊要求时，请务必人工核验。
