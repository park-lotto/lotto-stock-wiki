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

from shopping_shorts.brainbulb import images, photocheck, spec


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
                      "fabricated_text": ["종합주가지수", "-2,886.83", "신한투자증권"],
                      "matches_subtitle": True, "reason": "주가 전광판"})
    r = photocheck.parse_review(raw)
    assert r["verdict"] == "retry", "글자가 읽히는데 통과시켰다"


def test_parse_review_rejects_illustration():
    raw = json.dumps({"verdict": "accepted", "visual_kind": "illustration",
                      "fabricated_text": [], "matches_subtitle": True, "reason": "셀 셰이딩"})
    assert photocheck.parse_review(raw)["verdict"] == "retry"


def test_parse_review_rejects_subtitle_mismatch():
    """자막과 안 맞으면 반려 — 볼케이노에 없는 검사다(케냐 자막에 한국 지하철)."""
    raw = json.dumps({"verdict": "accepted", "visual_kind": "photo",
                      "fabricated_text": [], "matches_subtitle": False, "reason": "한국 지하철"})
    assert photocheck.parse_review(raw)["verdict"] == "retry"


def test_parse_review_accepts_clean():
    raw = json.dumps({"verdict": "accepted", "visual_kind": "photo",
                      "fabricated_text": [], "matches_subtitle": True, "reason": "맞는 장면"})
    assert photocheck.parse_review(raw)["verdict"] == "accepted"


def test_parse_review_survives_garbage():
    """판정을 못 읽으면 통과 — 검수가 편을 멈추면 안 된다."""
    assert photocheck.parse_review("이건 JSON이 아니다")["verdict"] == "accepted"


# ── 전체 흐름 ────────────────────────────────────────────────────────────────────
def test_check_sends_all_images(tmp_path):
    """★전수 검수 — 볼케이노는 지표로 걸렀지만 우리는 전부 본다.

    실측 2026-09-13: 우리 그림 39장의 flat 최대가 0.480이라 볼케이노 문턱 0.55로는
    **한 장도 안 걸렸다**(v8에서 10장 검사에 모델 판정 0장). 잡으려는 것이 다르다 —
    지어낸 간판·수치는 잘 그려진 사진이라 그림/사진 지표에 안 걸린다.
    값도 싸다: 한 편 전수가 약 1.8원(이미지 생성비의 0.4%).
    """
    pytest.importorskip("cv2")
    a = tmp_path / "1.png"; _noise(a, seed=1)
    b = tmp_path / "2.png"; _flat(b)
    called = []
    def rv(prompt, path):
        called.append(path)
        return json.dumps({"verdict": "accepted", "visual_kind": "photo",
                           "fabricated_text": [], "matches_subtitle": True, "reason": ""})
    r = photocheck.check({"1": str(a), "2": str(b)}, {"1": "가", "2": "나"},
                         reviewer=rv, log=lambda *a_: None)
    assert r["checked"] == 2
    assert len(called) == 2, "전수로 안 보냈다"


def test_check_can_still_filter_by_metrics(tmp_path):
    """force_all=False면 예전처럼 지표로 거른다 — 비용을 아껴야 할 때 쓴다."""
    pytest.importorskip("cv2")
    a = tmp_path / "1.png"; _noise(a, seed=1)
    b = tmp_path / "2.png"; _flat(b)
    called = []
    def rv(prompt, path):
        called.append(path)
        return json.dumps({"verdict": "accepted", "visual_kind": "photo",
                           "fabricated_text": [], "matches_subtitle": True, "reason": ""})
    photocheck.check({"1": str(a), "2": str(b)}, {"1": "가", "2": "나"},
                     reviewer=rv, log=lambda *a_: None, force_all=False)
    assert called == [str(b)], "지표가 깨끗한 것까지 보냈다"


def test_check_collects_retry_slots(tmp_path):
    pytest.importorskip("cv2")
    p = tmp_path / "1.png"; _flat(p)
    def rv(prompt, path):
        return json.dumps({"verdict": "retry", "visual_kind": "photo",
                           "fabricated_text": ["가짜 숫자"], "matches_subtitle": True, "reason": "글자"})
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
    for w in ("illustration", "지어낸 기록", "자막과 맞나"):
        assert w in q, w


def test_brand_on_clothing_is_not_fabricated():
    """★옷의 브랜드는 지어낸 기록이 아니다.

    실측 2026-09-13(v9): 옷의 NIKE·YALE·MIRACLE 때문에 3장이 반려됐고,
    그중 슬롯4는 **검색해서 찾은 실제 뉴스 사진**이었다. 실물을 쓰자는 지시와 반대로
    검수가 진짜 사진을 버리고 생성 이미지로 바꿨다.
    → 질문을 '읽히는 글자'에서 '지어낸 기록'으로 바꿨다.
    """
    q = photocheck.build_review_request("x.png", "자막")
    assert "NIKE" in q and "적지 마라" in q, "브랜드 예외가 질문에 없다"
    assert "verdict는 반드시 retry" in q, "적어놓고 통과시키지 말라는 지시가 없다"


def test_old_field_name_still_read():
    """모델이 옛 이름으로 답해도 읽는다 — 판정이 흔들려도 놓치지 않게."""
    raw = json.dumps({"verdict": "accepted", "visual_kind": "photo",
                      "legible_text": ["가짜 주가지수"], "matches_subtitle": True, "reason": ""})
    assert photocheck.parse_review(raw)["verdict"] == "retry"


def test_reviewer_default_model_catches_fake_records():
    """★기본 검수 모델을 바꿀 때 이 시험을 보라.

    실측 2026-09-13, 같은 가짜 주가지수 그림:
      gemini-2.5-flash       retry
      gemini-3.1-flash-lite  retry     ← 기본
      gemini-2.5-flash-lite  accepted  ← 놓친다. 기본이었다가 교체.
    ★커밋 메시지에 '교체했다'고 적고 실제로는 안 바뀐 적이 있다(같은 날) — 그래서 시험으로 박는다.
    """
    import inspect
    from shopping_shorts.brainbulb import providers
    got = inspect.signature(providers.gemini_reviewer).parameters["model"].default
    assert got != "gemini-2.5-flash-lite", "가짜 기록을 놓치는 모델이 기본이다"
    assert got == "gemini-3.1-flash-lite", got


def test_vertex_model_map_avoids_missing_models():
    """★버텍스에 없는 모델을 그대로 쓰면 404다.

    실측 2026-09-13(us-central1): gemini-3.1-flash-lite · gemini-3-flash-preview ·
    gemini-2.0-flash 가 **없다**. 2.5 계열만 된다.
    검수용으로 2.5-flash-lite를 쓰면 가짜 기록을 놓치므로 2.5-flash로 올린다.
    """
    from shopping_shorts.brainbulb import spec
    m = spec.VERTEX_MODEL_MAP
    assert m.get("gemini-3.1-flash-lite") == "gemini-2.5-flash"
    assert m.get("gemini-2.5-flash-lite") == "gemini-2.5-flash", "검수가 가짜 기록을 놓친다"


def test_pick_model_leaves_free_key_alone():
    """무료 키로 붙었으면 모델을 바꾸지 않는다 — 거기선 3.1이 된다."""
    from shopping_shorts.brainbulb import providers

    class FakeFree:
        class _api_client:
            vertexai = False
    assert providers._pick_model(FakeFree(), "gemini-3.1-flash-lite") == "gemini-3.1-flash-lite"


def test_pick_model_swaps_on_vertex():
    from shopping_shorts.brainbulb import providers

    class FakeVertex:
        class _api_client:
            vertexai = True
    assert providers._pick_model(FakeVertex(), "gemini-3.1-flash-lite") == "gemini-2.5-flash"


def test_review_request_carries_what_we_wanted():
    """★그 자리에 **무엇을 넣으려 했는지**가 질문에 실려야 한다.

    실측 2026-09-14(최민식 v2 슬롯2): 검색어가 「1980년대 어음 용지」였는데
    **한복 입은 할머니 인터뷰 캡처**가 왔다. 그런데 검수가 matches_subtitle=true 로
    통과시켰다 — 판정문이 "인물이 말하고 있는 듯한 모습과 일치하므로 어긋나지 않습니다"였다.
    사진만 보면 "누가 말하고 있다"는 자막과 모순이 없어 보이기 때문이다.
    → 찾으려던 것을 함께 줘서 **대조**하게 한다.
    """
    q = photocheck.build_review_request("x.png", "영화가 아니라 종이 얘기였다",
                                        "검색: 1980년대 어음 용지")
    assert "1980년대 어음 용지" in q, "넣으려던 것이 질문에 안 실렸다"
    assert "영화가 아니라 종이 얘기였다" in q
    # want 가 없으면 그 줄 자체가 빠진다(생성 이미지 자리 — 대조할 검색어가 없다)
    assert "[이 자리에 넣으려던 것]" not in photocheck.build_review_request("x.png", "자막만")


def test_review_request_forbids_lenient_match():
    """★«어긋나지 않으면 통과»로 물으면 아무 사진이나 다 통과한다.

    판정 기준이 «모순이 없나»가 아니라 «이 자막과 함께 틀어도 되나»여야 한다.
    동시에 너무 세도 안 된다 — 인물 사진은 사건 현장 사진이 아니므로
    «그 장면이 찍혔나»로 물으면 **진짜 최민식 사진까지 반려된다**(실측 2026-09-14 1차 시도).
    """
    q = photocheck.build_review_request("x.png", "자막", "검색: 무엇")
    assert "딴 이야기로 보이는" in q, "느슨한 통과를 막는 지시가 없다"
    assert "현장 사진이 아니다" in q, "인물 사진을 과하게 반려하는 것을 막는 지시가 없다"


def test_parse_review_keeps_who_what():
    """그림에 실제로 무엇이 찍혔는지를 보존한다 — «왜 통과했나»를 볼 때 이유보다 빠르다."""
    raw = json.dumps({"verdict": "accepted", "visual_kind": "photo", "fabricated_text": [],
                      "who_what": "한복 입은 나이 든 여성이 소파에 앉아 있다",
                      "matches_subtitle": True, "reason": "x"})
    assert "한복" in photocheck.parse_review(raw)["who_what"]


# ── 검수 기준표 (2026-09-16 사장님 지시) ──────────────────────────────────────
# ★규칙을 표로 뺀 이유는 "규칙만 늘고 판정이 없는" 사고를 구조적으로 막기 위해서다
#   (핸드오프: "지시문에 적고 판정을 안 붙였다 — 일곱 번"). 그러니 표 자체를 시험한다.

def _ok_review(**kw):
    d = {"verdict": "accepted", "visual_kind": "photo", "fabricated_text": [],
         "matches_subtitle": True, "product_ok": True, "single_scene": True,
         "who_what": "양파밭", "reason": "좋다"}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def test_every_blocking_rule_has_a_judge_and_a_question():
    """★표에 blocking 으로 적어놓고 판정(bad)이나 묻는 말(ask)을 안 붙이면 그 규칙은 죽은 규칙이다."""
    for r in spec.PHOTO_RULES:
        if not r["blocking"]:
            continue
        assert r["field"], f"{r['key']}: 볼 필드가 없다"
        assert callable(r["bad"]), f"{r['key']}: 판정 함수가 없다"
        assert r["ask"].strip(), f"{r['key']}: 모델에게 묻는 말이 없다"


def test_every_blocking_rule_reaches_the_prompt():
    """표에 한 줄 더하면 묻는 말도 따라와야 한다 — 프롬프트를 따로 고치게 두지 않는다."""
    q = photocheck.build_review_request("x.png", "자막", "검색: 무엇", "소재")
    for r in spec.PHOTO_RULES:
        if r["blocking"]:
            head = r["ask"].splitlines()[0]
            assert head in q, f"{r['key']}: 기준표에 있는데 프롬프트에 없다"


def test_every_blocking_rule_actually_rejects():
    """★각 기준이 정말로 반려를 내는지 하나씩 어긋뜨려 본다(사보타주)."""
    bad_by_key = {
        "visual_kind": {"visual_kind": "illustration"},
        "fabricated": {"fabricated_text": ["EXP046724"]},
        "subtitle": {"matches_subtitle": False},
        "product": {"product_ok": False},
        "collage": {"single_scene": False},
    }
    for r in spec.PHOTO_RULES:
        if not r["blocking"]:
            continue
        assert r["key"] in bad_by_key, f"{r['key']}: 새 기준인데 이 시험에 경우가 없다"
        rv = photocheck.parse_review(_ok_review(**bad_by_key[r["key"]]))
        assert rv["verdict"] == "retry", f"{r['key']}: 어긋났는데 통과시킨다"
        assert r["key"] in rv["failed"], f"{r['key']}: 어느 기준에 걸렸는지 안 남는다"


def test_clean_review_passes():
    """전부 맞으면 통과해야 한다 — 다 반려하는 검수는 검수가 아니다."""
    rv = photocheck.parse_review(_ok_review())
    assert rv["verdict"] == "accepted" and rv["failed"] == []


def test_model_saying_accepted_cannot_override_a_failed_rule():
    """★모델이 «통과»라고 해도 어긋난 것을 적었으면 반려다(앞뒤 안 맞는 답 방어)."""
    rv = photocheck.parse_review(_ok_review(verdict="accepted", product_ok=False))
    assert rv["verdict"] == "retry" and "product" in rv["failed"]


def test_fail_reason_names_the_rule():
    """재시도 프롬프트와 화면이 쓰는 사유 — 어느 기준인지 사람 말로 나와야 한다."""
    rv = photocheck.parse_review(_ok_review(single_scene=False, reason="분할 화면"))
    assert "여러 장면" in photocheck.fail_reason(rv)


def test_searched_map_marks_search_fallback():
    """★scene 을 골랐는데 생성으로 떨어졌으면 ok=False — 이게 안 남아 «검색됐나»를 못 봤다."""
    import tempfile, os as _os
    with tempfile.TemporaryDirectory() as d:
        p = _os.path.join(d, "01.png")
        open(p, "wb").close()
        json.dump({"hash": "x", "kind": "gen", "asked_kind": "scene", "query": "양파밭"},
                  open(p + ".json", "w", encoding="utf-8"), ensure_ascii=False)
        m = images.searched_map({"1": p})
        assert m["1"]["ok"] is False and m["1"]["asked"] == "scene"


def test_searched_map_ignores_slots_that_asked_for_generation():
    """처음부터 gen 이면 잴 것이 없다 — 생성 슬롯을 «검색 실패»로 세면 실패율이 거짓말이 된다."""
    import tempfile, os as _os
    with tempfile.TemporaryDirectory() as d:
        p = _os.path.join(d, "02.png")
        open(p, "wb").close()
        json.dump({"hash": "x", "kind": "gen", "asked_kind": "gen", "query": ""},
                  open(p + ".json", "w", encoding="utf-8"), ensure_ascii=False)
        assert images.searched_map({"2": p})["2"] is None
