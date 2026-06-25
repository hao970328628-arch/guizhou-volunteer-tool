from src.major_classifier import classify_major


def test_major_classifier_examples():
    assert classify_major("计算机科学与技术") == ("工学", "计算机类")
    assert classify_major("数据科学与大数据技术") == ("工学", "计算机类")
    assert classify_major("临床医学") == ("医学", "临床医学类")
    assert classify_major("法学") == ("法学", "法学类")
    assert classify_major("汉语言文学") == ("文学", "中国语言文学类")
    assert classify_major("会计学") == ("管理学", "会计审计类")
