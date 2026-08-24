"""확정 대본 모드 — 문장 순서·전량을 그대로 지킨다 (2026-08-24 사장님 결정).

## 실사고 (잡 432d04a955bf, 서버 실측)

사장님: *"대본이 3단계로 갈때 왜짤리지"*

2단계에서 확정한 10문장이 3단계(EDL)에서 이렇게 됐다:

    [0] 저 친구네 집 갔다가 충격받았잖아요.        → 0번  ✅
    [1] 주방 싱크대가 확 달라져서 깨끗하더라고요.  → 8번  ❌ 맨 끝으로 밀림
    [2] 신기해서 대체 어떻게 한 거냐고...          → 1번
    [3~8] 나머지 한 칸씩 앞당겨짐
    [9] 검색해도 안 나와서 댓글에 '싱크대'...      → ★통째로 누락

증상은 두 가지였다:
1. hook 다음이 곧바로 '신기해서…'로 튀어 **2번째 문장이 사라진 것처럼** 보였다
   (실제론 맨 끝 cta 칸에 가 있어 "CTA인데 내용은 상황 설명"이 됐다)
2. **CTA 문장이 진짜로 빠졌다** — 댓글 유도 문구라 매출과 직결되는 줄이다

## 왜 기존 방어가 못 잡았나

`enforce_scripted_narration`은 **"대본에 없는 문장을 지어냈나"만** 본다. 이번엔
문장이 전부 진짜 대본 문장이라(창작 0개) 그냥 통과했다 — 실측 `fixed=0`.
즉 검사에 **순서**와 **누락** 축이 아예 없었다.
(★판정축이 하나뿐이면 교정이 통째로 죽는다 — reference_판정축_하나면_교정이_통째로죽는다)

## 사장님 결정: "1" = 강하게

확정 대본 모드에선 문장을 **대본 순서 그대로** 칸에 배분한다. 2단계에서 정한 순서가
곧 영상 순서다 — 순서를 AI에 맡기는 한 같은 사고가 반복된다.
★단, 화면(장면) 선택은 그대로 AI가 한다. 바뀌는 건 **어느 칸에 어느 문장이 들어가나**뿐.
"""
import json
import pathlib

import pytest

from shopping_shorts import edit_plan as ep


# ── 실사고 재현 데이터(서버 잡 432d04a955bf에서 그대로 가져옴) ──────────
REAL_SCRIPT = (
    "저 친구네 집 갔다가 충격받았잖아요. 주방 싱크대가 확 달라져서 깨끗하더라고요. "
    "신기해서 대체 어떻게 한 거냐고 물어봤거든요. 다기능 폭포수 싱크대로 바꿨다는 거예요. "
    "알고 보니 물줄기가 폭포수처럼 쏟아지는 그거였더라고요. "
    "버튼 한 번만 누르면 끝이라는데 간편하죠. 저도 해보니까 설거지가 편해지는 거 있죠. "
    "심지어 물 온도까지 실시간으로 보이더라고요. "
    "진작 알았으면 괜히 설거지 때문에 고생 안 했을 텐데요. "
    "검색해도 안 나와서 댓글에 '싱크대' 남겨주시면 링크 드릴게요."
)

# 그 잡이 실제로 만들어낸 EDL 나레이션(순서 뒤바뀜 + CTA 누락)
REAL_BAD_NARRATIONS = [
    "저 친구네 집 갔다가 충격받았잖아요.",
    "신기해서 대체 어떻게 한 거냐고 물어봤거든요. 다기능 폭포수 싱크대로 바꿨다는 거예요.",
    "알고 보니 물줄기가 폭포수처럼 쏟아지는 그거였더라고요.",
    "버튼 한 번만 누르면 끝이라는데 간편하죠.",
    "저도 해보니까 설거지가 편해지는 거 있죠.",
    "심지어 물 온도까지 실시간으로 보이더라고요. 진작 알았으면 괜히 설거지 때문에 고생 안 했을 텐데요.",
    "주방 싱크대가 확 달라져서 깨끗하더라고요.",
]
REAL_ROLES = ["hook", "inquiry", "description", "function",
              "demonstration", "feature", "cta"]


def _beats(narrations, roles=None):
    out = []
    for i, n in enumerate(narrations):
        out.append({
            "beat_idx": i,
            "role": (roles[i] if roles else f"r{i}"),
            "narration": n,
            "target_seconds": 2.5,
            "primary": {"seg_id": f"s{i}", "video_id": "v1", "start": i, "end": i + 2},
            "alternates": [],
        })
    return out


def _narrs(beats):
    return [b["narration"] for b in beats]


# ── ① 실사고 재현 — 이 데이터가 고쳐져야 한다 ────────────────────────
def test_real_incident_order_is_restored():
    """★잡 432d04a955bf 재현 — 뒤바뀐 순서가 대본 순서로 돌아온다."""
    beats = _beats(REAL_BAD_NARRATIONS, REAL_ROLES)
    fixed, n = ep.enforce_script_order(beats, REAL_SCRIPT)
    joined = " ".join(_narrs(fixed))
    sents = ep.script_sentences(REAL_SCRIPT)
    pos = [joined.find(s) for s in sents]
    assert all(p >= 0 for p in pos), "대본 문장이 결과에 없다"
    assert pos == sorted(pos), f"순서가 대본과 다르다: {pos}"
    assert n > 0, "고친 게 없다고 보고한다"


def test_real_incident_cta_sentence_comes_back():
    """★빠졌던 CTA 문장이 되돌아온다 — 매출과 직결되는 줄이다."""
    beats = _beats(REAL_BAD_NARRATIONS, REAL_ROLES)
    fixed, _ = ep.enforce_script_order(beats, REAL_SCRIPT)
    joined = ep._narr_key(" ".join(_narrs(fixed)))
    cta = ep._narr_key("검색해도 안 나와서 댓글에 '싱크대' 남겨주시면 링크 드릴게요.")
    assert cta in joined, "CTA 문장이 여전히 빠져 있다"


def test_real_incident_every_sentence_survives():
    """10문장 전부 살아남는다(누락 0)."""
    beats = _beats(REAL_BAD_NARRATIONS, REAL_ROLES)
    fixed, _ = ep.enforce_script_order(beats, REAL_SCRIPT)
    joined = ep._narr_key(" ".join(_narrs(fixed)))
    missing = [s for s in ep.script_sentences(REAL_SCRIPT)
               if ep._narr_key(s) not in joined]
    assert missing == [], f"누락: {missing}"


def test_beat_count_and_roles_unchanged():
    """★칸 수·역할은 안 건드린다 — 화면 배치(AI가 고른 장면)를 지키기 위해서다."""
    beats = _beats(REAL_BAD_NARRATIONS, REAL_ROLES)
    fixed, _ = ep.enforce_script_order(beats, REAL_SCRIPT)
    assert len(fixed) == len(REAL_BAD_NARRATIONS)
    assert [b["role"] for b in fixed] == REAL_ROLES


def test_primary_scene_choice_is_untouched():
    """화면 선택은 AI 몫 그대로 — seg_id가 바뀌면 안 된다."""
    beats = _beats(REAL_BAD_NARRATIONS, REAL_ROLES)
    before = [b["primary"]["seg_id"] for b in beats]
    fixed, _ = ep.enforce_script_order(beats, REAL_SCRIPT)
    assert [b["primary"]["seg_id"] for b in fixed] == before


# ── ② 정상 입력은 건드리지 않는다 ─────────────────────────────────────
def test_already_correct_order_is_noop():
    """이미 순서가 맞으면 아무것도 안 바꾼다(고친 개수 0)."""
    sents = ep.script_sentences(REAL_SCRIPT)
    beats = _beats(sents)
    fixed, n = ep.enforce_script_order(beats, REAL_SCRIPT)
    assert n == 0, "멀쩡한 걸 고쳤다고 한다"
    assert _narrs(fixed) == sents


def test_split_sentence_across_beats_is_allowed():
    """한 문장을 여러 칸으로 쪼개는 건 허용 — 프롬프트가 시키는 일이다."""
    script = "가나다 라마바. 사아자 차카타."
    beats = _beats(["가나다", "라마바.", "사아자 차카타."])
    fixed, n = ep.enforce_script_order(beats, script)
    assert n == 0, f"쪼갠 걸 오류로 봤다: {_narrs(fixed)}"


def test_no_given_script_is_noop():
    """확정 대본이 없으면(자유 생성 모드) 손대지 않는다."""
    beats = _beats(["아무 말", "저런 말"])
    fixed, n = ep.enforce_script_order(beats, "")
    assert n == 0 and _narrs(fixed) == ["아무 말", "저런 말"]


def test_empty_beats_is_safe():
    assert ep.enforce_script_order([], REAL_SCRIPT) == ([], 0)
    assert ep.enforce_script_order(None, REAL_SCRIPT) == ([], 0)


# ── ③ 분량 배분 — 칸이 감당할 만큼만 ──────────────────────────────────
def test_more_sentences_than_beats_keeps_all_text():
    """문장이 칸보다 많으면 **버리지 않고** 이어 붙인다(누락 금지)."""
    script = "하나. 둘. 셋. 넷. 다섯."
    beats = _beats(["x", "y"])
    fixed, _ = ep.enforce_script_order(beats, script)
    joined = ep._narr_key(" ".join(_narrs(fixed)))
    for s in ep.script_sentences(script):
        assert ep._narr_key(s) in joined, f"{s} 누락"


def test_fewer_sentences_than_beats_leaves_no_empty_hole():
    """문장이 칸보다 적으면 빈 칸이 생기면 안 된다(화면이 무음으로 남는다)."""
    script = "하나. 둘."
    beats = _beats(["x", "y", "z", "w"])
    fixed, _ = ep.enforce_script_order(beats, script)
    assert all((b.get("narration") or "").strip() for b in fixed), \
        f"빈 칸이 생겼다: {_narrs(fixed)}"


def test_stale_tts_is_dropped_when_text_changes():
    """★문장이 바뀐 칸의 옛 음성은 버린다 — 안 버리면 대본≠소리(2026-08-19 실사고)."""
    beats = _beats(REAL_BAD_NARRATIONS, REAL_ROLES)
    for b in beats:
        b["tts_path"] = "/tmp/old.mp3"
        b["tts_text"] = b["narration"]
    fixed, _ = ep.enforce_script_order(beats, REAL_SCRIPT)
    for b in fixed:
        if b.get("narration") != b.get("tts_text"):
            assert not b.get("tts_path"), "바뀐 칸에 옛 음성이 남아 있다"


# ── ④ 저장 출구 배선 ─────────────────────────────────────────────────
def test_wired_into_save_exit():
    """★만드는 경로가 여럿이라 저장 출구 한 곳에서 건다(0순위-B)."""
    src = pathlib.Path(__file__).resolve().parents[1].joinpath(
        "store.py").read_text(encoding="utf-8")
    assert "enforce_script_order" in src, "저장 출구에 순서 보존이 안 걸려 있다"
