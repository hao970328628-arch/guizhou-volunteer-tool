from src.eligibility import check_program_eligibility, check_subject_eligibility


def test_subject_eligibility_for_physics_chemistry_biology():
    subjects = ["物理", "化学", "生物"]
    assert check_subject_eligibility(subjects, "不限")
    assert check_subject_eligibility(subjects, "化学")
    assert check_subject_eligibility(subjects, "生物")
    assert check_subject_eligibility(subjects, "化学和生物")


def test_subject_ineligible_for_politics():
    assert not check_subject_eligibility(["物理", "化学", "生物"], "思想政治")


def test_non_minority_cannot_show_preparatory():
    ok, _ = check_program_eligibility({"is_preparatory": True}, {"is_minority": False, "accept_preparatory": True})
    assert not ok


def test_minority_without_accepting_preparatory_cannot_show():
    ok, _ = check_program_eligibility({"is_preparatory": True}, {"is_minority": True, "accept_preparatory": False})
    assert not ok


def test_national_special_requires_qualification():
    ok, _ = check_program_eligibility({"is_national_special": True}, {"has_national_special": False})
    assert not ok
