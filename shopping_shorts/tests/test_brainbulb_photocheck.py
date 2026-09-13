# -*- coding: utf-8 -*-
"""사진 검수 — 만든 그림을 보고 판정한다. 모델은 부르지 않는다(가짜 검수자로 돈다).

왜 만들었나 (사장님 2026-09-13 "두더지 아니야?"):
  프롬프트에서 낱말을 막는 방식은 계속 샌다. 실제로 두 번 샜다 —
  `computer screen`을 막으니 `digital sign`으로 나왔고, 그것이 **신한투자증권 간판 +
  종합주가지수 -2,886.83**을 그렸다. 내가 표현을 미리 다 적을 수 없다.

  볼케이노도 같은 구조로 푼다(next_payload.photo_check):
    기계 지표로 먼저 거르고(편 A 10장 중 1장만 모델에게) · review_policy={"provider":"client"}
  실측 검증: 그 가짜 간판 이미지를 실제 검수자에게 보였더니
    legible_text=['종합주가지수','-2,886.83','-2.66%','신한투자증권'] → retry.
"""
import json

import numpy as np
import pytest
from PIL import Image

from shopping_shorts.brainbulb import photocheck, spec


def _noise(path, size=(600, 400), seed=0):
    rng = np.random.default_rng(seed)
    Image.fromarray(rng.integers(60, 200, (size[1], size[0], 3), dtype=np.uint8)).save(path)


def _flat(path, size=(600, 400)):
    """평평한 색면 — 일러스트 징후."""
    Image.new("RGB", size, (180, 190, 210)).save(path)


# ── 기계 지표 ────────────────────────────────────────────────────────────────────
def test_metrics_flags_flat_image(tmp_path):
    """평평한 면이 넓으면 표시한다 — 볼케이노 why='평평한 면이 넓다'."""
    pytest.importorskip("cv2")
    p = tmp_path / "flat.png"; _flat(p)
    m = photocheck.metrics(str(p))
    assert m and m["flat"] > spec.PHOTOCHECK_FLAT_MAX
    assert m["why"]


def test_metrics_passes_textured_photo(tmp_path):
    """잔질감이 있는 사진은 통과 — 멀쩡한 걸 매번 모델에 보내면 돈이 샌다."""
    pytest.importorskip("cv2")
    p = tmp_path / "n.png"; _noise(p)
    m = photocheck.metrics(str(p))
    assert m and not m["why"], m


def test_metrics_survives_missing_file(tmp_path):
    assert photocheck.metrics(str(tmp_path / "없음.png")) is None


# ── 판정 읽기 ────────────────────────────────────────────────────────────────────
def test_parse_review_rejects_legible_text():
    """★읽히는 글자가 있으면 반려 — 실측으로 잡아낸 가짜 주가지수가 이 경우다."""
    raw = json.dumps({"verdict": "accepted", "visual_kind": "photo",
                      "legible_text": ["종합주가지수", "-2,886.83", "신한투자증권"],
                      "matches_subtitle": True, "reason": "주가 전광판"})
    r = photocheck.parse_review(raw)
    assert r["verdict"] == "retry", "글자가 읽히는데 통과시켰다"


def test_parse_review_rejects_illustration():
    raw = json.dumps({"verdict": "accepted", "visual_kind": "illustration",
                      "legible_text": [], "matches_subtitle": True, "reason": "셀 셰이딩"})
    assert photocheck.parse_review(raw)["verdict"] == "retry"


def test_parse_review_rejects_subtitle_mismatch():
    """자막과 안 맞으면 반려 — 볼케이노에 없는 검사다(케냐 자막에 한국 지하철)."""
    raw = json.dumps({"verdict": "accepted", "visual_kind": "photo",
                      "legible_text": [], "matches_subtitle": False, "reason": "한국 지하철"})
    assert photocheck.parse_review(raw)["verdict"] == "retry"


def test_parse_review_accepts_clean():
    raw = json.dumps({"verdict": "accepted", "visual_kind": "photo",
                      "legible_text": [], "matches_subtitle": True, "reason": "맞는 장면"})
    assert photocheck.parse_review(raw)["verdict"] == "accepted"


def test_parse_review_survives_garbage():
    """판정을 못 읽으면 통과 — 검수가 편을 멈추면 안 된다."""
    assert photocheck.parse_review("이건 JSON이 아니다")["verdict"] == "accepted"


# ── 전체 흐름 ────────────────────────────────────────────────────────────────────
def test_check_only_reviews_suspicious_images(tmp_path):
    """★기계 지표가 깨끗하면 모델을 안 부른다 — 볼케이노도 10장 중 1장만 보냈다."""
    pytest.importorskip("cv2")
    clean = tmp_path / "1.png"; _noise(clean, seed=1)
    flat = tmp_path / "2.png"; _flat(flat)
    called = []
    def rv(prompt, path):
        called.append(path)
        return json.dumps({"verdict": "accepted", "visual_kind": "photo",
                           "legible_text": [], "matches_subtitle": True, "reason": ""})
    r = photocheck.check({"1": str(clean), "2": str(flat)}, {"1": "가", "2": "나"},
                         reviewer=rv, log=lambda *a: None)
    assert r["checked"] == 2
    assert called == [str(flat)], "깨끗한 사진까지 모델에 보냈다"


def test_check_collects_retry_slots(tmp_path):
    pytest.importorskip("cv2")
    p = tmp_path / "1.png"; _flat(p)
    def rv(prompt, path):
        return json.dumps({"verdict": "retry", "visual_kind": "photo",
                           "legible_text": ["가짜 숫자"], "matches_subtitle": True, "reason": "글자"})
    r = photocheck.check({"1": str(p)}, {"1": "자막"}, reviewer=rv, log=lambda *a: None)
    assert r["retry"] == ["1"]


def test_check_without_reviewer_runs_metrics_only(tmp_path):
    """검수자가 없으면 지표만 재고 넘어간다 — 반려 0."""
    pytest.importorskip("cv2")
    p = tmp_path / "1.png"; _flat(p)
    r = photocheck.check({"1": str(p)}, {"1": "자막"}, reviewer=None, log=lambda *a: None)
    assert r["retry"] == [] and r["checked"] == 1


def test_check_survives_reviewer_failure(tmp_path):
    """검수 호출이 죽어도 편은 계속 간다."""
    pytest.importorskip("cv2")
    p = tmp_path / "1.png"; _flat(p)
    def boom(prompt, path):
        raise RuntimeError("모델 죽음")
    r = photocheck.check({"1": str(p)}, {"1": "자막"}, reviewer=boom, log=lambda *a: None)
    assert r["retry"] == []


def test_review_request_asks_all_three():
    """질문에 셋이 다 들어가나 — 사진/그림 · 읽히는 글자 · 자막 일치."""
    q = photocheck.build_review_request("x.png", "케냐 슬럼가를 지남")
    assert "케냐 슬럼가를 지남" in q
    for w in ("illustration", "읽을 수 있는", "자막과 맞나"):
        assert w in q, w
