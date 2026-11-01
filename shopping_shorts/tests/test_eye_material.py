from tools.calcopy.hybrid.flow import eye_material_note


def test_no_bench_material_is_told():
    t = eye_material_note(["v/eye/시트_1초.jpg"], "출처 A")
    assert "## 근거.md\n출처 A" in t and "벤치 대조 자료가 없다" in t


def test_bench_sheet_counts_as_material():
    assert "벤치 대조 자료가 없다" not in eye_material_note(["v/eye/시트_1초.jpg", "bench/sheet.jpg"], "")
    assert "벤치 대조 자료가 없다" not in eye_material_note(["v/eye/벤치대조_시트.jpg"], "")
