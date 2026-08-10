"""후보 대본 심사위원(2026-07-22) — 사장님 기준: '제일 좋은 건 대본 채점 + 대본↔장면 싱크 +
스토리라인이 맞는지'를 기준(rubric)으로 본다. coverage 같은 proxy가 아니라 **실제 만들어진
후보**를 3축으로 채점해 백본·후보를 고른다.

  · script_quality = 대본 자체(훅 세기·짤드라마·말투 자연스러움).
  · scene_sync     = 비트별 대사↔화면(행위·장면)이 맞나.
  · storyline      = 처음~끝이 하나의 이야기로 말이 되나(순서·인과·마무리).

Gemini 판단이 필요한 부분(특히 storyline)이라 call 주입점으로 실제 호출을 회피한다
(pattern_bank/edit_plan과 동일 패턴). 실패/무키 시 None → 호출부가 규칙점수로 폴백."""
import sys

_SCORE = {"type": "integer"}   # 0~5
_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "script_quality": _SCORE,
        "scene_sync": _SCORE,
        "storyline": _SCORE,
        "reason": {"type": "string"},
    },
    "required": ["script_quality", "scene_sync", "storyline"],
}


def cut_rhythm_penalty(beats):
    """컷리듬/반복 결정적 감점(0~0.3) — T6 이중방어. 심사위원(Gemini)이 파편·반복 후보를
    높게 줘도 최종 순위에서 끌어내려 P1(뚝뚝 끊김)·P2(장면 반복)가 후보 선택으로 재발하지
    않게 한다. 두 축: ①파편=비트당 클립이 상한(MAX_CLIPS_PER_BEAT) 초과 ②반복=클립 seg가
    영상 전체에서 재사용. 결정적이라 Gemini 죽어도(규칙점수 폴백) 그대로 작동한다."""
    from shopping_shorts import config
    segs = []
    n_beats = 0
    for b in (beats or []):
        if not b:
            continue
        n_beats += 1
        p = b.get("primary") or {}
        if p.get("seg_id"):
            segs.append(p["seg_id"])
        for a in (b.get("alternates") or []):
            if a.get("seg_id"):
                segs.append(a["seg_id"])
    if not segs or not n_beats:
        return 0.0
    cap = getattr(config, "MAX_CLIPS_PER_BEAT", 3) or 3
    chop = max(0.0, (len(segs) / n_beats) - cap) / cap   # 비트당 평균이 상한의 2배면 1.0
    repeat = 1.0 - len(set(segs)) / len(segs)             # 전부 고유=0, 절반 재사용=0.5
    return round(min(0.3, 0.15 * min(1.0, chop) + 0.15 * repeat), 3)


def _beats_block(beats):
    lines = []
    for i, b in enumerate(beats or []):
        p = b.get("primary") or {}
        scene = (p.get("scene_desc") or p.get("action") or p.get("seg_id") or "").strip()
        lines.append(f"  {i+1}. 대사: {(b.get('narration') or '').strip()}  |  화면: {scene}")
    return "\n".join(lines)


def _judge_prompt(beats):
    return (
        "너는 한국 쇼핑 숏폼 편집 심사위원이다. 아래 '완성된 후보'(비트별 대사+그 순간 화면)를 "
        "세 기준으로 0~5점 매겨라(5=최고). 후하지 말고 엄격하게.\n"
        "① script_quality = 대본 자체: 첫 대사가 강한 훅인가(‘여러분~/알려드려요’ 설명체면 낮음), "
        "짤드라마(인물·상황·반전)인가, 말투가 자연스러운가.\n"
        "② scene_sync = 각 대사와 그 순간 화면(행위·장면)이 맞나. '썰어'인데 뒤집는 화면이면 낮음.\n"
        "③ storyline = 처음~끝이 하나의 이야기로 말이 되나. 순서·인과가 맞고 마무리(CTA)까지 "
        "흐르나. 요리 순서 나열이면 낮음.\n\n"
        f"[완성된 후보]\n{_beats_block(beats)}\n\n"
        "각 0~5 정수와 reason(한 줄) JSON만 출력.")


_RANK_SCHEMA = {
    "type": "object",
    "properties": {
        "ranking": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate": {"type": "integer"},   # 1-base
                    "score": {"type": "integer"},       # 0~100, 동점 금지
                    "reason": {"type": "string"},
                },
                "required": ["candidate", "score"],
            },
        },
    },
    "required": ["ranking"],
}


def _rank_prompt(beats_list):
    blocks = []
    for i, beats in enumerate(beats_list):
        blocks.append(f"[후보 {i + 1}]\n{_beats_block(beats)}")
    return (
        "너는 한국 쇼핑 숏폼 편집 심사위원이다. 아래 후보 대본들을 **서로 비교해서** 채점해라.\n"
        "기준은 셋: ①대본 자체(첫 대사가 강한 훅인가, 짤드라마인가, 말투가 자연스러운가) "
        "②대사↔화면 싱크 ③처음~끝이 하나의 이야기로 말이 되나.\n"
        "★반드시 우열을 갈라라 — **동점 금지**. 비슷해 보여도 훅의 세기, 화면 지목의 구체성, "
        "마무리 흐름에서 차이를 찾아 점수를 벌려라(0~100 정수, 최소 5점 이상 차이).\n\n"
        + "\n\n".join(blocks) + "\n\n"
        "각 후보의 candidate(1부터)·score(0~100, 동점 금지)·reason(우열 이유 한 줄)을 "
        "ranking 배열 JSON만 출력.")


def rank(beats_list, call=None):
    """후보 여러 개를 **한 호출에서 비교** 채점 → {idx(0-base): {"score": 0~1, "rank": 1~n, "reason"}}.
    judge()는 후보를 따로 보므로 셋 다 '무난 3/3/3'이 나와 동점이 반복됐다(실측 0.467×3).
    비교 대상을 같이 보여주고 동점을 금지해야 우열이 갈린다. 실패/후보<2면 None
    (호출부가 아무것도 안 바꾸는 폴백 — 종전과 동일)."""
    beats_list = [b for b in (beats_list or [])]
    if len(beats_list) < 2 or any(not b for b in beats_list):
        return None
    if call is None:
        from shopping_shorts import pattern_bank
        call = pattern_bank._default_call
    try:
        res = call(_rank_prompt(beats_list), _RANK_SCHEMA)
    except Exception as e:
        print(f"candidate_judge.rank: {e!r}", file=sys.stderr)
        return None
    rows = (res or {}).get("ranking") if isinstance(res, dict) else None
    if not isinstance(rows, list):
        return None
    out = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            idx = int(r.get("candidate")) - 1
            sc = max(0, min(100, int(r.get("score"))))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(beats_list) and idx not in out:
            out[idx] = {"score": round(sc / 100.0, 3),
                        "reason": (r.get("reason") or "").strip()}
    if len(out) != len(beats_list):
        return None      # 일부 후보가 빠지면 빠진 쪽만 보정을 못 받아 순위가 왜곡된다
    order = sorted(out, key=lambda i: -out[i]["score"])
    for pos, i in enumerate(order):
        out[i]["rank"] = pos + 1
    return out


def judge(beats, call=None):
    """후보(grounded beats)를 3축 채점 → {script_quality, scene_sync, storyline, reason, total}.
    total = 세 점수 평균/5 (0~1). call None이면 실제 Gemini. 실패/빈 beats면 None(규칙점수 폴백)."""
    if not beats:
        return None
    if call is None:
        from shopping_shorts import pattern_bank
        call = pattern_bank._default_call
    try:
        res = call(_judge_prompt(beats), _JUDGE_SCHEMA)
    except Exception as e:
        print(f"candidate_judge.judge: {e!r}", file=sys.stderr)
        return None
    if not res or not isinstance(res, dict):
        return None
    def _c(k):
        try:
            return max(0, min(5, int(res.get(k, 0))))
        except (TypeError, ValueError):
            return 0
    sq, ss, sl = _c("script_quality"), _c("scene_sync"), _c("storyline")
    return {"script_quality": sq, "scene_sync": ss, "storyline": sl,
            "reason": (res.get("reason") or "").strip(),
            "total": round((sq + ss + sl) / 15.0, 3)}
