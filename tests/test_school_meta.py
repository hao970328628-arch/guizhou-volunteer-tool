import pandas as pd

from src.school_meta import normalize_school_meta


def test_school_meta_normalizes_chinese_columns_and_code():
    df = pd.DataFrame([{"院校代码": "123", "院校名称": "测试大学", "省份": "贵州", "城市": "贵阳", "学校性质": "公办"}])
    normalized = normalize_school_meta(df)
    assert normalized.iloc[0]["school_code"] == "0123"
    assert normalized.iloc[0]["school_name"] == "测试大学"
    assert normalized.iloc[0]["school_nature"] == "公办"
