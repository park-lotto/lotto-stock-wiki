"""대본이 정한 어미가 이긴다 (2026-09-04 사장님 제보).

제보 그대로: "대본생성 어미 ~다. 수정 > 영상대본MIX 미리듣기 ~요< 자동 수정됨".

뿌리 = 0순위-B(같은 판단 두 군데). 어미를 정하는 곳이 둘이었다:
  ① 대본생성 — 스타일·프롬프트가 어미를 정하고 사장님이 손으로 고친다
  ② narration_naturalize._spoken_style — `_SPOKEN_MAP`으로 문어체→구어체 치환
     (`습니다→어요`, `입니다→이에요` …). ②가 ①을 **무조건** 덮어썼다.

실측(기본 프로파일, intensity 0.4):
    '이건 진짜 물건입니다.'
        -> '이건 진짜 물건이에요…'
    '가격도 착합니다. 성능도 좋습니다. 후회 없습니다.'
        -> '가격도 착해요… 성능도 좋아요. 후회 없습니다.'   ← ★어미가 섞인다

★두 번째가 더 나쁘다. intensity가 '앞에서부터 그 비율만' 바꾸므로 한 대본 안에서
어미가 반쪽만 바뀐다 — 전부 바뀌는 것보다 어색하고, 자막(대본)과 음성이 어긋난다.

처방: 어미를 정하는 곳을 **한 곳으로** 되돌린다. 대본이 확정한 어미는 대본이 이긴다.
naturalize의 나머지(감탄사·속삭임·발음교정·억양)는 그대로 산다 — 어미 치환만 양보한다.
기본값은 종전 동작 = 회귀 0.
"""
import copy

from shopping_shorts import mix_pipeline
from shopping_shorts.narration_naturalize import merge_profile, naturalize


# ─── 1. 뿌리 재현 — 이 동작이 현재 사실임을 못박는다 ────────────────────────

def test_spoken_style_rewrites_endings_by_default():
    """기본 프로파일은 문어체 어미를 구어체로 바꾼다(종전 동작 = 회귀 기준선)."""
    out = naturalize("이건 진짜 물건입니다.", merge_profile({}))
    assert "입니다" not in out          # 대본이 정한 어미가 사라진다
    assert "이에요" in out


def test_spoken_style_partial_conversion_mixes_endings():
    """★intensity가 앞부분만 바꿔 한 대본 안에서 어미가 섞인다(제보의 진짜 얼굴)."""
    out = naturalize("가격도 착합니다. 성능도 좋습니다. 후회 없습니다.", merge_profile({}))
    assert "없습니다" in out            # 뒷문장은 안 바뀜
    assert "착해요" in out              # 앞문장은 바뀜 → 섞였다


# ─── 2. 처방 — 어미 치환을 끄면 대본 어미가 그대로 살아남는다 ───────────────

def test_spoken_style_off_keeps_script_endings():
    """spoken_style을 끄면 대본이 정한 어미가 그대로 나간다."""
    prof = merge_profile({"spoken_style": {"on": False}})
    out = naturalize("가격도 착합니다. 성능도 좋습니다. 후회 없습니다.", prof)
    assert "착합니다" in out
    assert "좋습니다" in out
    assert "없습니다" in out
    assert "착해요" not in out


def test_spoken_style_off_keeps_other_stages_alive():
    """★어미만 양보한다 — 발음교정 같은 나머지 단계는 그대로 돈다.

    이걸 안 보면 '어미 고치려고 naturalize를 통째로 껐다'가 되어
    감탄사·속삭임·발음교정이 조용히 같이 죽는다(기능끄기 진단동반사망).
    """
    prof = merge_profile({"spoken_style": {"on": False},
                          "pronunciation": {"on": True, "dict": {"AS": "에이에스"}}})
    out = naturalize("AS 됩니다.", prof)
    assert "에이에스" in out            # 발음교정은 살아있다
    assert "됩니다" in out              # 어미는 대본 그대로


# ─── 3. 배선 — synthesize_line이 실제로 그 판단을 한 곳에서 내리나 ──────────

def _capture_naturalize(monkeypatch):
    """synthesize_line이 naturalize에 넘긴 프로파일을 가로챈다."""
    seen = {}

    def fake_naturalize(text, profile=None, **kw):
        seen["profile"] = copy.deepcopy(profile)
        seen["text"] = text
        return text

    monkeypatch.setattr(mix_pipeline, "naturalize", fake_naturalize)
    monkeypatch.setattr(mix_pipeline.tts, "synthesize_best",
                        lambda text, out, **kw: open(out, "wb").write(b"x"))
    monkeypatch.setattr(mix_pipeline.audio_post, "post_process", lambda *a, **k: a[1])
    return seen


def test_synthesize_line_keeps_endings_when_script_wins(monkeypatch, tmp_path):
    """script_endings=True면 spoken_style이 꺼진 채 naturalize가 불린다."""
    seen = _capture_naturalize(monkeypatch)
    mix_pipeline.synthesize_line("이건 진짜 물건입니다.", tmp_path / "a.mp3",
                                 voice={"voice_id": "v"}, script_endings=True)
    assert seen["profile"]["spoken_style"]["on"] is False


def test_synthesize_line_default_unchanged(monkeypatch, tmp_path):
    """★기본값은 종전 그대로 — 인자를 안 주면 어미 치환이 살아있다(회귀 0)."""
    seen = _capture_naturalize(monkeypatch)
    mix_pipeline.synthesize_line("이건 진짜 물건입니다.", tmp_path / "a.mp3",
                                 voice={"voice_id": "v"})
    assert seen["profile"]["spoken_style"]["on"] is True


def test_script_endings_does_not_mutate_caller_profile(monkeypatch, tmp_path):
    """★호출자 프로파일을 더럽히지 않는다(얕은복사 원본오염 전례).

    프리셋 dict를 그대로 고치면 다음 합성부터 영구히 어미 치환이 죽는다.
    """
    seen = _capture_naturalize(monkeypatch)
    prof = {"spoken_style": {"on": True}}
    mix_pipeline.synthesize_line("물건입니다.", tmp_path / "a.mp3",
                                 voice={"voice_id": "v"}, profile=prof,
                                 script_endings=True)
    assert seen["profile"]["spoken_style"]["on"] is False   # 이번 합성은 꺼짐
    assert prof["spoken_style"]["on"] is True               # 원본은 그대로


# ─── 4. 배선 잠금 — 스위치를 아무도 안 켜면 고친 게 아니다 ──────────────────

def test_job_script_endings_decides_by_given_script():
    """판정 한 곳: given_script가 있으면 대본이 어미를 정한 잡이다."""
    assert mix_pipeline.job_script_endings({"given_script": "이건 물건입니다."}) is True
    assert mix_pipeline.job_script_endings({"given_script": ""}) is False
    assert mix_pipeline.job_script_endings({}) is False
    assert mix_pipeline.job_script_endings(None) is False


def test_all_synthesize_beats_callers_pass_script_endings():
    """★_synthesize_beats 호출부가 **전부** script_endings를 넘긴다.

    회귀: 스위치를 만들어놓고 호출부가 안 켜면 라이브는 종전 그대로다
    (메모리 `판정만있고지시없음` — 검사와 지시는 짝으로 넣어라).
    호출부가 5곳이라 하나만 빠져도 그 경로에서만 어미가 되돌아간다 —
    "어떤 잡은 되고 어떤 잡은 안 되는" 재현 어려운 제보가 된다.
    """
    import inspect
    src = inspect.getsource(mix_pipeline)
    calls = src.count("_synthesize_beats(")
    wired = src.count("script_endings=job_script_endings(")
    # 정의 1개(def) + 호출 n개 → 호출부 = calls - 1
    assert calls - 1 == wired, (
        "_synthesize_beats 호출부 %d곳 중 %d곳만 script_endings를 넘긴다" % (calls - 1, wired))
    assert wired >= 5
