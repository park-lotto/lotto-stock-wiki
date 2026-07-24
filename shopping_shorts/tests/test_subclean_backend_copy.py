from pathlib import Path

SRC = Path(__file__).resolve().parents[1]


def test_vmake_client_user_strings_have_no_vendor_name():
    txt = (SRC / "vmake_client.py").read_text(encoding="utf-8")
    # raise/예외로 사용자에게 닿는 문구에 "VMake"가 없어야 한다(주석은 무관하지만
    # 이 파일은 예외 문자열에만 "VMake"를 썼으므로 raise 라인만 검사).
    raise_lines = [l for l in txt.splitlines()
                   if ("raise " in l or "ValueError(" in l or "RuntimeError(" in l)]
    for l in raise_lines:
        assert "VMake" not in l, l
    # 새 브랜드명이 최소 한 번은 등장
    assert "AI 자막 제거" in txt


def test_mix_pipeline_clean_error_has_no_vendor_name():
    txt = (SRC / "mix_pipeline.py").read_text(encoding="utf-8")
    # clean_error= 대입과 자막제거 RuntimeError 문구에 VMake 부재
    for l in txt.splitlines():
        if "clean_error=" in l and "VMake" in l:
            raise AssertionError("clean_error에 VMake 노출: " + l)
        if "raise RuntimeError(" in l and "자막 제거가 켜져" in l:
            assert "VMake" not in l, l
