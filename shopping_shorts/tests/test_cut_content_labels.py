# -*- coding: utf-8 -*-
"""렌더 전 관문 ④(render_bench.cut_content_gate — 컷 안 남의 글자·남의 얼굴)의 판정 함수가 눈 판정 표본에서 잰 정밀도·재현율을 지키나(오류기록 #86).

표본 = shopping_shorts/tests/fixtures/cut_content_labels.json (10-25 오푸스 눈 라벨)
  text: 벤치 계획 컷(잇템로그 v3 10편·스타픽룸 성시경·키치잇 박세리)·썰템홈샷 하이브리드 8편·샥템 하이브리드 9편·얼지마트롯 원본 —
        컷마다 렌더와 같은 프레임 3장(cut_crop·blur)의 글자 상자 잰 값 + 컷 라벨 pos(흐림 밖 남의 박힌 글자·워터마크) / neg.
  face: 감사 결함 완성본(함익병 도브·박세리 라프레리 2·안유진·함익병 비누·강민경·최은경) + 얼지마트롯 원본 4편의 얼굴 —
        기준 얼굴 3개(연예인 장면)와의 SFace 코사인 최댓값 + 라벨 celeb / other.
  10-25 오검출 수리(98 오류기록): text 에 268컷(set new — 제품 포장·상자·라벨·진열대·원본 틱톡 자막·방송 자막) 더함, 글자 값에 긴 간격 짝 fi.
        face 에 grp gate 189얼굴(관문 창 프레임 — 박정수·박세리 키치잇, 근접 크롭·옆얼굴·손 가림) 더함, 얼굴 값에 nest·yaw.
문턱을 바꾸면 이 시험이 먼저 깨진다 — 표본을 다시 보고(눈 판정 = 오푸스) 고친다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
FX = ROOT / "shopping_shorts/tests/fixtures/cut_content_labels.json"


def _fx():
    return json.loads(FX.read_text(encoding="utf-8"))


def _cut_hit(row, rule):
    from tools.calcopy.hybrid.render_bench import TEXT_MIN_HITS
    return sum(1 for fr in row["frames"] if any(rule(b) for b in fr)) >= TEXT_MIN_HITS


def _pr_text(rows, rule):
    tp = sum(1 for r in rows if r["label"] == "pos" and _cut_hit(r, rule))
    fp = sum(1 for r in rows if r["label"] == "neg" and _cut_hit(r, rule))
    fn = sum(1 for r in rows if r["label"] == "pos" and not _cut_hit(r, rule))
    return tp / max(1, tp + fp), tp / max(1, tp + fn)


def test_fixture_size():
    F = _fx()
    t, f = F["text"]["rows"], F["face"]["rows"]
    assert sum(r["label"] == "pos" for r in t) >= 120 and sum(r["label"] == "neg" for r in t) >= 600
    assert sum(r["label"] == "other" for r in f) >= 100 and sum(r["label"] == "celeb" for r in f) >= 250
    assert sum(r.get("grp") == "gate" for r in f) >= 150


def test_text_rule_meets_measured_precision_recall():
    from tools.calcopy.hybrid.render_bench import foreign_text
    F = _fx()["text"]
    p, r = _pr_text(F["rows"], foreign_text)
    assert p >= F["min_precision"] and r >= F["min_recall"], (p, r)
    old = [x for x in F["rows"] if x["set"] == "old"]          # 10-25 첫 표본 494컷 — 재현율을 깎지 않았나
    p, r = _pr_text(old, foreign_text)
    assert p >= F["old_min_precision"] and r >= F["old_min_recall"], (p, r)


def _no_far(b):
    return {**b, "fi": []}


def test_static_scene_text_vetoed_by_long_interval():
    """멈춘 화면(2프레임 사이 변화 없음)의 큰 제품 글·간판 — 같은 컷 긴 간격 짝(fi)에서 글이 주변과 같이 변하면 장면 속 글.
    fi 를 빼면(옛 판정) 이 컷들이 다시 걸린다 = 이 시험이 실제로 그 차이를 잰다."""
    from tools.calcopy.hybrid.render_bench import foreign_text
    rows = {x["id"]: x for x in _fx()["text"]["rows"]}
    for cid in ("하이브리드_성시경#04", "03_골든카레#10", "03b_골든카레#11", "02b_노트핀#01", "03b_골든카레#09"):
        r = rows[cid]
        assert r["label"] == "neg"
        assert not _cut_hit(r, foreign_text), cid
        assert _cut_hit(r, lambda b: foreign_text(_no_far(b))), cid
    for cid in ("01b_요플레#12", "01b_요플레#13", "03b_골든카레#01", "03b_골든카레#13", "ulji_BFTGKYRPXeU@2"):     # 멈춘 화면의 박힌 글(워터마크·광고 글·제목 띠)은 그대로 걸린다
        assert rows[cid]["label"] == "pos" and _cut_hit(rows[cid], foreign_text), cid


SMALL_SUBS = ("rnd_ep04_v3_acC_orig@3.82", "rnd_ep11_v3_a1C_orig@1.49", "rnd_ep12_v3_ayB_orig@1.35", "rnd_ep12_v3_saA_orig@3.79",
              "rnd_ep12_v3_ayA_orig@2.71", "rnd_ep09_v3_j2A_orig@0.67", "rnd_ep02_hair_su_hair1@11.63")


def test_small_subtitle_caught_by_glyph_stillness():
    """틱톡형 작은 자막(창 2.8~4.5%·얇은 흰 글) — 상자 평균 변화(d_in)는 글자 사이 배경을 따라가 붙박이로 안 잡히고(옛 판정 통과),
    획 픽셀 변화(d_gl)로는 걸린다(98 #99). d_gl 을 빼면 다시 통과 = 이 시험이 실제로 그 차이를 잰다."""
    from tools.calcopy.hybrid.render_bench import foreign_text
    rows = {x["id"]: x for x in _fx()["text"]["rows"]}
    no_gl = lambda b: foreign_text({k: v for k, v in b.items() if k != "d_gl"})
    for cid in SMALL_SUBS:
        r = rows[cid]
        assert r["label"] == "pos"
        assert not _cut_hit(r, no_gl), cid
        assert _cut_hit(r, foreign_text), cid
    for cid in ("ep08_cvs_onigiri_v3#02", "ep08_cvs_onigiri_v3#03", "ep08_cvs_onigiri_v3#04",
                "ep08_cvs_onigiri_v3#12", "ep08_cvs_onigiri_v3#13", "ep08_cvs_onigiri_v3#14"):   # 08 가격 자막은 그대로 걸린다
        assert _cut_hit(rows[cid], foreign_text), cid


def test_glyph_rule_adds_no_false_positive():
    """획 판정이 neg(제품 포장·간판)를 새로 걸지 않는다 — 표본 전체에서 d_gl 있을 때와 없을 때 걸린 neg 컷이 같다."""
    from tools.calcopy.hybrid.render_bench import foreign_text
    rows = [x for x in _fx()["text"]["rows"] if x["label"] == "neg"]
    no_gl = lambda b: foreign_text({k: v for k, v in b.items() if k != "d_gl"})
    assert [r["id"] for r in rows if _cut_hit(r, foreign_text)] == [r["id"] for r in rows if _cut_hit(r, no_gl)]


def test_text_without_still_check_is_worse():
    """붙박이(상자 안 변화 < 둘레 변화)·크기 조건을 빼면 제품 포장·간판 글이 걸려 정밀도가 무너진다 — 표본이 그 차이를 실제로 잡는지."""
    from tools.calcopy.hybrid import render_bench as RB
    F = _fx()["text"]
    loose = lambda b: (b["blur"] <= RB.TEXT_BLUR_MAX and b["score"] >= RB.TEXT_SCORE_MIN and b["fill"] >= 0.5
                       and b["aspect"] >= RB.TEXT_ASPECT_MIN and 0.01 <= b["h"] <= RB.TEXT_H_RANGE[1])
    assert _pr_text(F["rows"], loose)[0] < F["min_precision"] - 0.1


def test_no_gate_catches_nothing():
    """고치기 전(관문 없음) = 재현율 0 — 표본의 pos 가 실제로 있는 결함이라는 확인."""
    F = _fx()["text"]
    assert _pr_text(F["rows"], lambda b: False)[1] == 0.0


def test_face_rule_meets_measured_precision_recall():
    from tools.calcopy.hybrid.render_bench import other_face
    F = _fx()["face"]
    rows = [r for r in F["rows"] if r.get("grp") != "gate"]
    tp = sum(1 for r in rows if r["label"] == "other" and other_face(r))
    fp = sum(1 for r in rows if r["label"] == "celeb" and other_face(r))
    fn = sum(1 for r in rows if r["label"] == "other" and not other_face(r))
    p, r = tp / max(1, tp + fp), tp / max(1, tp + fn)
    assert p >= F["min_precision"] and r >= F["min_recall"], (p, r)


def test_blur_cover_maps_source_box_to_window():
    """흐림 칸(원본 좌표)이 창 좌표 상자를 덮는 비율 — 08 blurtest 자막 칸 꼴(crop 전체·창 1080×1434)."""
    from tools.calcopy.hybrid.render_bench import blur_cover
    regs = [[150, 880, 780, 160]]
    assert blur_cover(regs, [0, 0, 1080, 1434], (1080, 1434), (200, 900, 700, 1000), 1.0) == 1.0
    assert blur_cover(regs, [0, 0, 1080, 1434], (1080, 1434), (200, 1100, 700, 1200), 1.0) == 0.0
    assert blur_cover([[150, 880, 780, 160, 5.0, 6.0]], [0, 0, 1080, 1434], (1080, 1434), (200, 900, 700, 1000), 1.0) == 0.0


def _gate_cuts(rule):
    from collections import defaultdict
    from tools.calcopy.hybrid.render_bench import FACE_MIN_HITS
    cut = defaultdict(lambda: defaultdict(lambda: [False, False]))
    for r in _fx()["face"]["rows"]:
        if r.get("grp") != "gate":
            continue
        c = cut[r["id"]][r["dt"]]
        c[0] |= r["label"] == "other"
        c[1] |= rule(r)
    return {k: (sum(v[0] for v in fr.values()) >= FACE_MIN_HITS, sum(v[1] for v in fr.values()) >= FACE_MIN_HITS) for k, fr in cut.items()}


def test_face_gate_window_cuts():
    """관문 창 프레임(근접 크롭) 컷 단위 — 박정수 컷 8(근접 크롭 겹친 검출 cos 0.18) 은 안 멈추고, 박세리 컷 11(다른 여성)·원본 남 얼굴 컷은 멈춘다.
    nest·yaw 를 빼면(옛 판정) 박정수 컷 8 이 다시 멈춘다."""
    from tools.calcopy.hybrid.render_bench import other_face
    now = _gate_cuts(other_face)
    old = _gate_cuts(lambda r: other_face({k: v for k, v in r.items() if k not in ("nest", "yaw")}))
    assert now["pjs_c08"] == (False, False) and old["pjs_c08"] == (False, True)
    assert now["psr_c11"] == (True, True)
    tp = sum(1 for t, h in now.values() if t and h); fp = sum(1 for t, h in now.values() if h and not t); fn = sum(1 for t, h in now.values() if t and not h)
    assert fn == 0 and fp <= 1, (tp, fp, fn)
