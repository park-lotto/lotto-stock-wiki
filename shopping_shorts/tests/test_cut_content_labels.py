# -*- coding: utf-8 -*-
"""렌더 전 관문 ④(render_bench.cut_content_gate — 컷 안 남의 글자·남의 얼굴)의 판정 함수가 눈 판정 표본에서 잰 정밀도·재현율을 지키나(오류기록 #86).

표본 = shopping_shorts/tests/fixtures/cut_content_labels.json (10-25 오푸스 눈 라벨)
  text: 벤치 계획 컷(잇템로그 v3 10편·스타픽룸 성시경·키치잇 박세리)·썰템홈샷 하이브리드 8편·샥템 하이브리드 9편·얼지마트롯 원본 —
        컷마다 렌더와 같은 프레임 3장(cut_crop·blur)의 글자 상자 잰 값 + 컷 라벨 pos(흐림 밖 남의 박힌 글자·워터마크) / neg.
  face: 감사 결함 완성본(함익병 도브·박세리 라프레리 2·안유진·함익병 비누·강민경·최은경) + 얼지마트롯 원본 4편의 얼굴 —
        기준 얼굴 3개(연예인 장면)와의 SFace 코사인 최댓값 + 라벨 celeb / other.
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
    assert sum(r["label"] == "pos" for r in t) >= 60 and sum(r["label"] == "neg" for r in t) >= 400
    assert sum(r["label"] == "other" for r in f) >= 100 and sum(r["label"] == "celeb" for r in f) >= 100


def test_text_rule_meets_measured_precision_recall():
    from tools.calcopy.hybrid.render_bench import foreign_text
    F = _fx()["text"]
    p, r = _pr_text(F["rows"], foreign_text)
    assert p >= F["min_precision"] and r >= F["min_recall"], (p, r)


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
    rows = F["rows"]
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
