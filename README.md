# 贵州高考本科志愿筛选工具

这是一个 Streamlit Web 应用，用于贵州普通类本科志愿填报辅助筛选。应用运行时只读取 `data/processed/` 中的预构建标准数据包；普通用户打开浏览器后只需要输入考生信息和筛选条件，不需要也不能在页面中添加、上传或处理原始数据。

## 用户运行方式

```bash
pip install -r requirements.txt
streamlit run app.py
```

打开页面后可以使用：

- 数据状态摘要
- 考生信息输入
- 志愿偏好
- 专业筛选
- 风险阈值
- 普通本科批推荐
- 提前批参考模块
- 志愿篮子和 Excel 导出

如果页面提示缺少标准数据，说明发布包里没有带齐 `data/processed/` 成品文件，需要开发者先构建数据包后再发布。

## 预构建数据包

应用默认读取这些标准文件：

- `data/processed/catalog_2026.csv`：2026 招生专业目录，必需
- `data/processed/admission_2025_regular.csv`：2025 普通本科批投档数据，必需
- `data/processed/admission_2024_regular.csv`：2024 普通本科批投档数据，必需
- `data/processed/early_admission_2025.csv`：2025 提前批 A/B/C，可选
- `data/processed/early_admission_2024.csv`：2024 提前批 A/B/C，可选
- `data/processed/score_rank_2024.csv`：一分一段或分数段统计表，可选
- `data/processed/school_meta.csv`：学校属性库，可选
- `data/processed/manifest.json`：数据包构建清单

`manifest.json` 会记录构建时间、每个文件是否存在、行数、文件大小、sha256、来源文件列表、缺失的必需数据和缺失的可选数据。

## 开发者一次性构建

开发阶段把原始 PDF/CSV/Excel 放入 `data/raw/` 后，运行：

```bash
python scripts/build_processed_data.py --force
```

脚本会调用现有解析逻辑，从 `data/raw/` 生成 `data/processed/` 成品数据，并写入 `manifest.json`。如果必需数据缺失或解析后为空，脚本会失败退出，不会静默发布不可用数据包。

原始文件目录约定：

- `data/raw/catalog/`：2026 招生专业目录
- `data/raw/admission/2025/`：2025 普通本科批投档、提前批 A/B/C
- `data/raw/admission/2024/`：2024 普通本科批投档、提前批 A/B/C
- `data/raw/score_rank/`：一分一段或分数段统计表，可选
- `data/raw/school_meta/`：学校属性库 CSV/Excel，可选

原始 PDF 默认不提交到 GitHub。正式发布时请提交 `data/processed/` 中的标准 CSV、`manifest.json` 和必要规则文件。

## 当前能力

- 普通本科批“冲、稳、保、垫、缺少历史数据”分类。
- 提前批 A/B/C 独立参考模块，默认关闭，不进入普通本科批志愿篮子。
- 招生章程风险提醒：汇总体检、政审、面试、体能、身高、视力、性别、单科、外语语种等提示。
- 一分一段辅助：当数据包内含 `score_rank_2024.csv` 且用户未输入位次时，可按分数估算位次。
- 96 志愿草表：根据普通本科批推荐结果生成“专业+院校”草表。
- Excel 导出：包含推荐结果、志愿篮子、提前批关注清单、96 志愿草表、章程风险提醒和数据来源说明。

## 重要说明

本工具仅用于高考志愿填报辅助分析，不构成录取承诺。最终填报请以贵州省招生考试院公布的正式招生专业目录、志愿填报规定、高校招生章程和志愿填报系统为准。专业对身体条件、单科成绩、外语语种、民族资格、专项资格、体检、政审、面试、体能测试等有特殊要求时，请务必人工核验。
