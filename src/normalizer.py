from __future__ import annotations

import re
import unicodedata
from typing import Any

from .utils import to_int


def normalize_code(value: Any, width: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    text = re.sub(r"\.0$", "", text)
    text = re.sub(r"\s+", "", text)
    return text.zfill(width) if text.isdigit() else text


def normalize_school_code(value: Any) -> str:
    return normalize_code(value, 4)


def normalize_major_code(value: Any) -> str:
    return normalize_code(value, 3)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_major_name(value: Any) -> str:
    text = normalize_text(value)
    text = re.sub(r"^[A-Z0-9]{1,4}\s+", "", text)
    text = re.sub(r"[（(]\s*[0-9A-Z]{1,4}\s*[）)]$", "", text)
    return text.strip()


def _combined_text(*values: Any) -> str:
    return " ".join(normalize_text(v) for v in values if v is not None)


def detect_program_flags(major_name: Any = "", enroll_type: Any = "", remarks: Any = "") -> dict[str, bool]:
    text = _combined_text(major_name, enroll_type, remarks)
    no_space = text.replace(" ", "")
    is_border = "边防军人子女预科" in no_space or "边防军子女预科" in no_space
    is_minority_prep = "少数民族预科" in no_space
    is_preparatory = bool(re.search(r"(?<!预防)预科", no_space)) or is_minority_prep or is_border
    is_ethnic_class = "民族班" in no_space
    is_national = "国家专项" in no_space or "国家专项计划" in no_space
    is_local = "地方专项" in no_space or "地方专项计划" in no_space
    is_chinese_foreign = any(token in no_space for token in ["中外合作", "中外合办", "高收费"])
    is_directional = "定向" in no_space
    return {
        "is_preparatory": is_preparatory,
        "is_ethnic_class": is_ethnic_class,
        "is_national_special": is_national,
        "is_local_special": is_local,
        "is_chinese_foreign": is_chinese_foreign,
        "is_directional": is_directional,
        "is_border_guard_preparatory": is_border,
        "is_special_program": is_national or is_local,
    }


def is_undergraduate_row(batch: Any = "", category: Any = "", remarks: Any = "", major_name: Any = "") -> bool:
    text = _combined_text(batch, category, remarks, major_name)
    excluded = ["高职", "专科", "艺术", "体育"]
    if any(word in text for word in excluded):
        return False
    return "本科" in text or not text


def is_regular_undergraduate_row(batch: Any = "", category: Any = "") -> bool:
    text = _combined_text(batch, category)
    if any(word in text for word in ["提前批", "提前本科", "本科提前", "A段", "B段", "C段", "专科", "高职", "艺术", "体育"]):
        return False
    return "本科" in text or not text


def parse_tuition(value: Any) -> int | None:
    return to_int(value)


def normalize_catalog_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["school_code"] = normalize_school_code(out.get("school_code") or out.get("院校代码"))
    out["major_code"] = normalize_major_code(out.get("major_code") or out.get("专业代码"))
    out["school_name"] = normalize_text(out.get("school_name") or out.get("院校名称"))
    out["major_name"] = clean_major_name(out.get("major_name") or out.get("专业名称"))
    out["major_name_clean"] = clean_major_name(out.get("major_name_clean") or out["major_name"])
    out["tuition"] = parse_tuition(out.get("tuition") or out.get("学费"))
    out.update(detect_program_flags(out.get("major_name"), out.get("category"), out.get("remarks")))
    out["is_undergraduate"] = is_undergraduate_row(out.get("batch"), out.get("category"), out.get("remarks"), out.get("major_name"))
    out["is_regular_undergraduate"] = is_regular_undergraduate_row(out.get("batch"), out.get("category"))
    return out


def normalize_admission_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["school_code"] = normalize_school_code(out.get("school_code") or out.get("院校代码"))
    out["major_code"] = normalize_major_code(out.get("major_code") or out.get("专业代码"))
    out["school_name"] = normalize_text(out.get("school_name") or out.get("院校名称"))
    out["major_name"] = clean_major_name(out.get("major_name") or out.get("专业名称"))
    out["major_name_clean"] = clean_major_name(out.get("major_name_clean") or out["major_name"])
    out.update(detect_program_flags(out.get("major_name"), out.get("enroll_type"), out.get("raw_text")))
    return out
