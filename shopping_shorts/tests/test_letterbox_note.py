"""⬛ 위아래 여백 안내(2026-09-02 사장님 "그건 그냥 냅둬 — 안내를 하나 해주면 좋다").

담아온 원본에 구워져 있던 여백은 **고치지 않는다**(고치면 좌우가 잘리고 화질이 상한다).
대신 완성본에 그런 구간이 있으면 화면이 말해준다. 여기선 판정 규칙을 잠근다 —
실측으로 두 번 고친 규칙이라(표본 수, 한쪽만 어두운 경우) 되돌아가면 바로 오작동한다.
"""
import pathlib

MIX = pathlib.Path(__file__).resolve().parents[1] / "mix_pipeline.py"
APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


def test_표본은_컷보다_촘촘해야_한다():
    """8개로 재니 여백 구간을 전부 비껴가 0%가 나왔다(실측). 컷이 3초 안팎이다."""
    s = MIX.read_text(encoding="utf-8")
    i = s.index("def letterbox_report(")
    head = s[i:s.index("\n\n\n", i)]
    n = int(head.split("samples=")[1].split(")")[0])
    assert n >= 20, f"표본 {n}개는 너무 성글다 — 여백 구간을 놓친다"


def test_위아래가_둘_다_있어야_여백이다():
    """한쪽만 어두운 건 어두운 장면·페이드다. 그것까지 세면 멀쩡한 영상이 잡힌다(실측)."""
    s = MIX.read_text(encoding="utf-8")
    i = s.index("def letterbox_report(")
    head = s[i:s.index("\n\n\n", i)]
    assert "top > 0.08 and bot > 0.08" in head


def test_cropdetect를_쓰지_않는다():
    """검은 자리에 [광고]·워터마크가 얹혀 있어 ffmpeg cropdetect는 늘 '여백 없음'이다(실측)."""
    s = MIX.read_text(encoding="utf-8")
    i = s.index("def letterbox_report(")
    head = s[i:s.index("\n\n\n", i)]
    assert "cropdetect" not in head


def test_측정_실패는_안내를_안_한다():
    """모르면 비운다 — 없는 여백을 있다고 말하지 않는다."""
    s = APP.read_text(encoding="utf-8")
    i = s.index("def _letterbox_note(")
    head = s[i:i + 900]
    assert "return None" in head
    assert 'd if (d or {}).get("pct") else None' in head


def test_화면은_원본_탓임을_밝힌다():
    """'우리가 잘랐다'로 읽히면 안 된다 — 담아온 원본에 있던 것이다."""
    s = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")
    assert "원본 영상에 원래 들어 있던 것" in s
