from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = PROCESSED_DIR / "guizhou_volunteer.sqlite3"

SUBJECT_GROUPS = ["物理类", "历史类"]
REGULAR_BATCH_GROUP = "regular_undergraduate"
EARLY_BATCH_GROUPS = ["early_A", "early_B", "early_C"]

DEFAULT_RISK_THRESHOLDS = {
    "冲": (-0.15, 0.0),
    "稳": (0.0, 0.12),
    "保": (0.12, 0.35),
    "垫": (0.35, float("inf")),
}

DISCLAIMER = (
    "本工具仅用于高考志愿填报辅助分析，不构成录取承诺。最终填报请以贵州省招生考试院公布的正式"
    "招生专业目录、志愿填报规定、高校招生章程和志愿填报系统为准。专业对身体条件、单科成绩、"
    "外语语种、民族资格、专项资格、体检、政审、面试、体能测试等有特殊要求时，请务必人工核验。"
)


def ensure_dirs() -> None:
    for path in [
        RAW_DIR / "catalog",
        RAW_DIR / "admission" / "2025",
        RAW_DIR / "admission" / "2024",
        RAW_DIR / "score_rank",
        PROCESSED_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
