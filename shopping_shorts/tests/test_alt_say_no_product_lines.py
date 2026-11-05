"""11-05 강태경 #7691: 회원이 '쿠팡 제품 안내 빼고 정보만' → 모든 줄 about=subject 인데 비슷한 제품 고지를 요구해 3번 연속 멈춤."""
from tools.calcopy.hybrid import script_audit as SA


def _d(abouts, say_alt=False):
    lines = [{"id": f"L{i+1}", "kind": "narr", "tts": "정보를 알려 드려요", "about": a} for i, a in enumerate(abouts)]
    if say_alt:
        lines[0]["tts"] = "똑같은 건 없어서 비슷한 걸로 써 봤어요"
    return {"product_mode": "alt", "lines": lines}


def test_no_product_lines_needs_no_alt_notice():
    assert SA.alt_disclosed(_d(["subject", "subject", "subject"])) is None


def test_product_lines_still_need_alt_notice():
    assert (SA.alt_disclosed(_d(["subject", "product", "product"])) or {}).get("rule") == "alt_say"
    assert SA.alt_disclosed(_d(["product", "product", "subject"], say_alt=True)) is None
