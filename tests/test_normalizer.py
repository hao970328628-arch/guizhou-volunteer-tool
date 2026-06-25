from src.normalizer import (
    clean_major_name,
    detect_program_flags,
    normalize_major_code,
    normalize_school_code,
)


def test_code_padding():
    assert normalize_school_code("123") == "0123"
    assert normalize_major_code("7") == "007"


def test_clean_major_name_space_and_fullwidth():
    assert clean_major_name("  计算机科学与技术\n（中外合作办学） ") == "计算机科学与技术 (中外合作办学)"


def test_no_false_preparatory_for_preventive_medicine():
    assert detect_program_flags("预防医学")["is_preparatory"] is False


def test_no_false_ethnic_class_for_ethnology():
    assert detect_program_flags("民族学")["is_ethnic_class"] is False


def test_no_false_chinese_foreign_for_international_trade():
    assert detect_program_flags("国际经济与贸易")["is_chinese_foreign"] is False
