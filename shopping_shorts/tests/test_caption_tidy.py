"""짧은 자막 줄 합치기(2026-09-14 사장님 "0.몇 초 단위로도 끊긴다").

실측 근거: 라이브 2,685칸에서 AI가 끊은 줄의 41.9%가 실제 발화 1초 미만 → 합치기 후 5.9%,
문장 넘김 0 · 글자 변경 0 · 초 합 변경 0. 아래는 그 성질을 못박는다.
"""
from types import SimpleNamespace

from shopping_shorts import video_assemble as va


def test_1초미만_줄은_이웃과_합치고_초는_더해서_보존한다():
    lines, durs = va.tidy_caption_lines(["알고 보니", "투명한 낚싯줄 하나가", "핵심이었네요"],
                                        [0.40, 1.23, 0.73], narration="알고 보니 투명한 낚싯줄 하나가 핵심이었네요")
    assert lines[0] == "알고 보니 투명한 낚싯줄 하나가"
    assert abs(sum(durs) - (0.40 + 1.23 + 0.73)) < 1e-9


def test_문장_끝은_짧아도_넘지_않는다_원문_부호로_판정():
    n = "여러분 오이 절대 냉장고에 그냥 두지 마세요. 며칠 안 됐는데 물러서 버렸거든요."
    segs = ["여러분", "오이 절대 냉장고에", "그냥 두지 마세요", "며칠 안 됐는데", "물러서 버렸거든요"]  # 부호 떼인 줄
    lines, _ = va.tidy_caption_lines(segs, [0.34, 0.9, 0.8, 0.69, 0.91], narration=n)
    assert "마세요 며칠" not in " | ".join(lines)
    assert any(l.endswith("마세요") for l in lines)


def test_꾸미는_말은_받는_말_쪽으로_붙는다():
    segs = ["사과를 얇게 썰어", "반죽 입힌 뒤", "와플 메이커로 굽는", "사과 와플인데"]
    lines, _ = va.tidy_caption_lines(segs, [1.07, 0.75, 1.01, 0.84],
                                     narration="사과를 얇게 썰어 반죽 입힌 뒤 와플 메이커로 굽는 사과 와플인데")
    assert any("굽는 사과 와플인데" in l for l in lines)


def test_18자를_넘기면_합치지_않는다():
    segs = ["카드까지 틈새로 다 빠져서 정말", "불편했거든요"]
    lines, _ = va.tidy_caption_lines(segs, [2.0, 0.71], narration=" ".join(segs))
    assert lines == segs


def test_글자는_하나도_안_바뀐다():
    n = "단순한 자석이 아니라 내장 센서가 0.1초마다 위치를 수정해서 흔들림 없이 고정되더라고"
    segs = ["단순한", "자석이 아니라", "내장 센서가", "0.1초마다", "위치를 수정해서", "흔들림 없이", "고정되더라고"]
    lines, _ = va.tidy_caption_lines(segs, [0.40, 0.75, 0.59, 0.73, 0.83, 0.53, 0.78], narration=n)
    assert va.cap_preset_key("".join(lines)) == va.cap_preset_key(n)


def _fake_timing(monkeypatch, durs):
    from shopping_shorts import caption_sync
    monkeypatch.setattr(caption_sync, "phrase_durs_from_words",
                        lambda n, w, d, preset=None: SimpleNamespace(durs=list(durs), lead_in=0.1))


def test_합성경로는_AI줄을_합쳐_저장한다(monkeypatch):
    from shopping_shorts import mix_pipeline as mp
    monkeypatch.setenv("CAPTION_TIDY", "1")
    n = "여러분 오이 절대 냉장고에 그냥 두지 마세요. 며칠 안 됐는데 물러서 버렸거든요."
    _fake_timing(monkeypatch, [0.34, 0.9, 0.8, 0.69, 0.91])
    b = {"narration": n, "caption_lines": ["여러분", "오이 절대 냉장고에", "그냥 두지 마세요.", "며칠 안 됐는데", "물러서 버렸거든요."]}
    mp._apply_cap_timing(b, n, [1], 4.0)
    assert len(b["caption_lines"]) == len(b["cap_durs"]) < 5
    assert abs(sum(b["cap_durs"]) - 3.64) < 1e-6


def test_사람이_고친_줄은_안_건드린다(monkeypatch):
    from shopping_shorts import mix_pipeline as mp
    monkeypatch.setenv("CAPTION_TIDY", "1")
    n = "여러분 오이 절대 냉장고에"
    _fake_timing(monkeypatch, [0.34, 0.9])
    b = {"narration": n, "caption_lines": ["여러분", "오이 절대 냉장고에"], "caption_lines_human": True}
    mp._apply_cap_timing(b, n, [1], 2.0)
    assert b["caption_lines"] == ["여러분", "오이 절대 냉장고에"]
    assert b["cap_durs"] == [0.34, 0.9]


def test_기본은_꺼져_있다(monkeypatch):
    from shopping_shorts import mix_pipeline as mp
    monkeypatch.delenv("CAPTION_TIDY", raising=False)
    n = "여러분 오이 절대 냉장고에"
    _fake_timing(monkeypatch, [0.34, 0.9])
    b = {"narration": n, "caption_lines": ["여러분", "오이 절대 냉장고에"]}
    mp._apply_cap_timing(b, n, [1], 2.0)
    assert b["caption_lines"] == ["여러분", "오이 절대 냉장고에"]


def test_담은_장면_수_밑으로는_안_합친다():
    """구절 맞춤은 줄 수 = 컷 수 — 장면 수 밑으로 합치면 담은 장면이 화면에서 빠진다(1,700칸 시뮬 884→1,853)."""
    segs = ["알고 보니", "투명한 낚싯줄", "하나가", "핵심이었네요"]
    lines, _ = va.tidy_caption_lines(segs, [0.4, 0.6, 0.5, 0.7],
                                     narration="알고 보니 투명한 낚싯줄 하나가 핵심이었네요", min_lines=3)
    assert len(lines) == 3
