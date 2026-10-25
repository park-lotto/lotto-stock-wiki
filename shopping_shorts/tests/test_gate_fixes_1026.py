# -*- coding: utf-8 -*-
"""관문 자 고침 3건(10-26 재미썸홈 이븐쇼핑판 첫 편) — 옛 코드에서 실패하는 시험.
① quality_gate.face_needed: 연예인 판(thumb_card_face=true)만 얼굴을 잰다 — 연예인 판은 그대로 잰다.
② quality_gate.plan_frames_check: 훅 구간(frame.segments, 창 크기가 다름)은 구간 창으로 읽고 계획 그림을 채워 잘라 견준다 — 진짜 어긋남(ss+6초)은 여전히 ×.
③ kal_analyze.match_from_render: 우리 줄에 효과음(자막표 sfx)을 붙여 벤치 _decorated 와 같은 자로 센다.
②③은 이 PC 의 렌더 결과(C:/숏템_칼카피/evenshopping/작품10_개방형빨대/이븐쇼핑판)가 있을 때만 돈다."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import quality_gate as Q  # noqa: E402

WORK = Path("C:/숏템_칼카피/evenshopping/작품10_개방형빨대/이븐쇼핑판")
DOC = ROOT / "channel/evenshopping/작품10_개방형빨대/이븐쇼핑판"
HAVE = (WORK / "render/timeline.json").exists() and (WORK / "render/base.mp4").exists()


def test_face_needed_only_for_celeb_boards():
    assert Q.face_needed({"thumb_card_face": True}) is True
    assert Q.face_needed({"thumb_card_face": False}) is False
    assert Q.face_needed({}) is False
    from tools.calcopy.hybrid import styles as ST
    assert Q.face_needed(ST.load("키치잇판")) is True          # 연예인 판은 여전히 잰다
    assert Q.face_needed(ST.load("이븐쇼핑판")) is False


def _plan_rows(T):
    from tools.calcopy.hybrid import styles as ST
    from tools.calcopy.hybrid.render_bench import frame_window
    st = ST.load("이븐쇼핑판")
    M = json.loads((DOC / "재료.json").read_text(encoding="utf-8"))
    wv = frame_window(st["frame"])
    wv = [wv[0], wv[1], wv[2], min(wv[3], 1920 - wv[1])]
    return Q.plan_frames_check(WORK / "render", T, Path(M["cand_dir"]), wv, None, st=st, M=M)


@pytest.mark.skipif(not HAVE, reason="렌더 결과 없음(이 PC 전용)")
def test_hook_segment_cuts_compare_in_segment_window():
    T = json.loads((WORK / "render/timeline.json").read_text(encoding="utf-8"))
    T["cuts"] = T["cuts"][:2]                     # N1 두 컷 = 훅 구간(0~1.97초)
    ok, msg = Q.plan_frames_verdict(_plan_rows(T))
    assert ok, msg                                # 옛 코드: 판 창으로 읽어 0.85·0.91 → ×
    bad = copy.deepcopy(T)
    bad["cuts"][0]["ss"] = float(bad["cuts"][0]["ss"]) + 6     # 사보타주: 계획과 다른 장면
    ok2, msg2 = Q.plan_frames_verdict(_plan_rows(bad))
    assert not ok2, msg2


@pytest.mark.skipif(not (WORK / "render/자막표.json").exists(), reason="렌더 결과 없음(이 PC 전용)")
def test_match_counts_our_sfx_as_fx():
    from tools.calcopy.engine import kal_analyze as K
    tab = json.loads((WORK / "render/자막표.json").read_text(encoding="utf-8"))
    assert tab.get("sfx"), "이 편은 효과음 3발"
    m = K.match_from_render("이븐쇼핑판", DOC, WORK, media=False)
    row = next(r for r in m["rows"] if r["key"] == "fx.rate.나레")
    assert row["ours"] and row["ours"] > 0, row     # 옛 코드: sfx 를 안 넘겨 늘 0.0


def _rows():
    rows, t = [], 0.0
    lines = [("N1", 2), ("N2", 5), ("N3", 2), ("N4", 4), ("N5", 4), ("N6", 4), ("N7", 5), ("N8", 3)]
    for li, n in lines:
        for j in range(n):
            rows.append({"line": li, "j": j, "speaker": "narr", "text": f"{li} 덩어리 {j}", "t0": round(t, 3), "t1": round(t + 0.9, 3)})
            t += 0.9
    return rows


def test_sfx_follows_reference_time_within_role():
    """④ placement.sfx_step: 본보기 편 sfx_lines 의 그 역할 시각(Y2Y 본문 띵 6.7초)에 가장 가까운 덩어리 — 옛 코드는 본문 첫 덩어리(1.8초, 훅 자리)."""
    from tools.calcopy.hybrid import placement as PL
    from tools.calcopy.hybrid import styles as ST
    st = ST.load("이븐쇼핑판")
    p = PL.place(_rows(), st, "t", cuts=[{"t0": r["t0"], "t1": r["t1"]} for r in _rows()])
    body = [e["t"] for e in p["sfx"] if e.get("role") == "body"]
    assert body and abs(body[0] - 6.7) <= 0.9, p["sfx"]
