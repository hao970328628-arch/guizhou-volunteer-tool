from __future__ import annotations

from typing import Any

from .utils import to_float
from .warnings import collect_text_warnings


def _subjects(candidate_subjects: Any) -> set[str]:
    import re

    if isinstance(candidate_subjects, str):
        parts = re.split(r"[,，、/ ]+", candidate_subjects)
    else:
        parts = list(candidate_subjects or [])
    return {p.strip() for p in parts if p and p.strip()}


def check_subject_eligibility(candidate_subjects: Any, reselect_requirement: Any) -> bool:
    req = str(reselect_requirement or "").strip()
    if not req or req in {"不限", "无", "不提科目要求", "不提再选科目要求", "-"}:
        return True
    selected = _subjects(candidate_subjects)
    aliases = {
        "政治": "思想政治",
        "思想政治": "思想政治",
        "化学": "化学",
        "生物": "生物",
        "地理": "地理",
        "物理": "物理",
        "历史": "历史",
    }
    required = {canonical for word, canonical in aliases.items() if word in req}
    if "或" in req:
        return bool(required & selected)
    return required <= selected


def _truthy(row: Any, key: str) -> bool:
    if isinstance(row, dict):
        value = row.get(key)
    else:
        value = getattr(row, key, None)
        if value is None and hasattr(row, "get"):
            value = row.get(key)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "是", "y"}
    return bool(value)


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "get"):
        return row.get(key, default)
    return getattr(row, key, default)


def check_program_eligibility(row: Any, user_profile: dict[str, Any]) -> tuple[bool, list[str]]:
    warnings: list[str] = []

    if _truthy(row, "is_preparatory") and not (
        user_profile.get("is_minority") and user_profile.get("accept_preparatory")
    ):
        return False, ["少数民族预科要求少数民族身份且需勾选接受预科"]
    if _truthy(row, "is_ethnic_class") and not (
        user_profile.get("is_minority") and user_profile.get("accept_ethnic_class")
    ):
        return False, ["民族班要求少数民族身份且需勾选接受民族班"]
    if _truthy(row, "is_national_special") and not user_profile.get("has_national_special"):
        return False, ["国家专项计划要求对应资格"]
    if _truthy(row, "is_local_special") and not user_profile.get("has_local_special"):
        return False, ["地方专项计划要求对应资格"]
    if _truthy(row, "is_chinese_foreign") and not user_profile.get("accept_chinese_foreign"):
        return False, ["中外合作/高收费专业未勾选接受"]
    if _truthy(row, "is_directional") and not user_profile.get("show_directional"):
        return False, ["定向默认隐藏"]
    if _truthy(row, "is_border_guard_preparatory") and not user_profile.get("show_border_guard_preparatory"):
        return False, ["边防军子女预科班默认隐藏"]

    tuition = to_float(_value(row, "tuition"))
    tuition_limit = to_float(user_profile.get("tuition_limit"))
    if tuition is not None and tuition_limit is not None and tuition > tuition_limit:
        return False, [f"学费 {int(tuition)} 超过上限 {int(tuition_limit)}"]

    remarks = " ".join(str(_value(row, key, "")) for key in ["remarks", "raw_text", "warnings"])
    warnings.extend(collect_text_warnings(remarks))

    gender = user_profile.get("gender")
    if gender == "女" and "只招男生" in remarks:
        return False, ["性别限制：只招男生"]
    if gender == "男" and "只招女生" in remarks:
        return False, ["性别限制：只招女生"]
    if user_profile.get("has_color_weakness") and ("色弱" in remarks or "色盲色弱" in remarks):
        return False, ["色觉限制需人工核验，当前按不符合处理"]

    return True, warnings
