"""#4253(11-04 윤상길): 훅 카드 가운데 띠(body_text=lines) 글에 목소리 글(tts)의 끝 마침표·읽기 표기가 그대로 보였다.
화면 글의 주인 = 자막(caps). frame_segments 의 띠 글은 caps 글로 만든다(맛템썰템판·썰템쇼판·이븐쇼핑판)."""
from tools.calcopy.hybrid import render_bench as RB, styles as STY


def test_훅_띠_글은_화면_자막_글(monkeypatch):
    monkeypatch.delenv("SHORTEM_MEMBER_PACK", raising=False)
    st = STY.load("썰템쇼판")
    S = {"lines": [{"id": "L1", "kind": "tts", "tts": "큐알 찍으면 끝이에요.", "caps": [{"text": "QR 찍으면"}, {"text": "끝이에요"}]},
                   {"id": "L2", "kind": "tts", "tts": "두 번째 줄.", "caps": [{"text": "두 번째 줄"}]}]}
    T = {"lines": {"L1": [0.0, 1.5], "L2": [9.0, 10.0]}, "end": 12.0}
    segs = RB.frame_segments(S, T, st)
    texts = [s["body_text"] for s in segs if s.get("body_text")]
    assert texts, "훅 띠 글 구간이 없다(판 칸 확인)"
    assert all("." not in t and "큐알" not in t for t in texts), texts
    assert any("QR 찍으면 끝이에요" in t for t in texts), texts
