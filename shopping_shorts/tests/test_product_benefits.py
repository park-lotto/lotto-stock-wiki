"""무자막 해외영상 특장점 추출(product_benefits) — 2026-07-26 장면스파인.

실측 근거(핸드오프 "무자막 해외영상 특장점추출"): 영어자막 해외영상은 특장점 5개가 full_text로
완벽히 언어화되나, **완전 무자막**(틱톡 전동수납장 7666362681)은 Gemini가 화면은 정확히 이해
(scene_desc="터치 후 셔터 자동으로 열리며 선반 내려옴", is_key=true)하는데 `text`가 전부 빈칸 →
full_text 0자 → generate_mix가 `if full_text.strip()`으로 소스를 통째로 제외.

근본: _PROMPT의 text 정의가 "들리는 나레이션(없으면 화면 자막)"이라 자막 없으면 비운다. 화면
이해를 "제품 특장점 문장"으로 승격하는 지시가 없다.

처방 3겹(모두 fail-open, required 아님 — is_key/shot_role 추가와 동일 패턴):
① script_extract: product_benefits 필드(세그별 + 최상위 집계)
② script_generate.generate_mix: full_text 없어도 product_benefits면 소스 살리기 + 프롬프트 주입
③ edit_plan._build_inventory: 팔레트 라인에 특장점 실어 라이브 scene_first 경로도 대본에 녹임
"""
from shopping_shorts import script_extract, script_generate, edit_plan


# ── ① script_extract ────────────────────────────────────────────────────────
def test_prompt_asks_benefits_from_screen_when_no_caption():
    """자막·나레이션 없어도 화면만 보고 특장점을 한국어 문장으로 뽑으라는 지시가 있어야."""
    p = script_extract._PROMPT
    assert "product_benefits" in p
    assert "자막" in p and "특장점" in p


def test_schema_has_product_benefits_not_required():
    """스키마에 필드가 있고, required엔 없어야(기존 추출본 호환 = fail-open)."""
    seg_props = (script_extract._RESPONSE_SCHEMA["properties"]["segments"]
                 ["items"]["properties"])
    assert "product_benefits" in seg_props
    assert "product_benefits" not in (script_extract._RESPONSE_SCHEMA["properties"]
                                      ["segments"]["items"]["required"])
    # 최상위 집계도 있어야(소스 단위로 "이 제품은 이런 장점" 주입용)
    assert "product_benefits" in script_extract._RESPONSE_SCHEMA["properties"]
    assert "product_benefits" not in script_extract._RESPONSE_SCHEMA["required"]


def test_assign_seg_ids_carries_benefits():
    raw = [{"start": 0, "end": 2, "text": "", "scene_desc": "셔터 자동 개폐",
            "product_benefits": ["터치 한 번에 자동 개폐", "공간 절약"]}]
    out = script_extract._assign_seg_ids("v", raw)
    assert out[0]["product_benefits"] == ["터치 한 번에 자동 개폐", "공간 절약"]


def test_assign_seg_ids_benefits_fail_open():
    """필드 없으면 빈 리스트(기존 추출본 호환) — 크래시 금지."""
    out = script_extract._assign_seg_ids("v", [{"text": "x"}])
    assert out[0]["product_benefits"] == []


def test_assign_seg_ids_benefits_accepts_str():
    """모델이 리스트 대신 문장 하나(str)로 줘도 리스트로 정규화."""
    out = script_extract._assign_seg_ids(
        "v", [{"text": "", "product_benefits": "터치 한 번에 개폐"}])
    assert out[0]["product_benefits"] == ["터치 한 번에 개폐"]


def test_collect_benefits_dedups_and_orders():
    """소스 단위 집계: 세그별 특장점을 순서 보존 중복제거."""
    segs = [{"product_benefits": ["공간 절약", "자동 개폐"]},
            {"product_benefits": ["자동 개폐", "고급 디자인"]},
            {"product_benefits": []}]
    assert script_extract._collect_benefits(segs) == ["공간 절약", "자동 개폐", "고급 디자인"]


def test_collect_benefits_empty():
    assert script_extract._collect_benefits([]) == []
    assert script_extract._collect_benefits([{"text": "x"}]) == []


# ── ② script_generate.generate_mix ─────────────────────────────────────────
def test_generate_mix_keeps_source_with_benefits_only(monkeypatch):
    """full_text 0자여도 product_benefits가 있으면 소스로 살아남아야(회귀 근본)."""
    captured = {}
    monkeypatch.setattr(script_generate.comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    monkeypatch.setattr(script_generate, "_generate_drafts",
                        lambda prompt, **k: captured.setdefault("p", prompt) or [])
    monkeypatch.setattr(script_generate, "_verify_and_fix", lambda drafts, secs: drafts)

    sources = [
        {"name": "자막있음", "full_text": "이 컵은 얼음이 오래 갑니다", "structure": {}},
        {"name": "무자막", "full_text": "", "product_benefits": ["터치 한 번에 자동 개폐",
                                                              "공간 절약"], "structure": {}},
    ]
    script_generate.generate_mix(sources, target_seconds=30)
    # 무자막 소스가 제외되지 않고 프롬프트에 특장점으로 실려야
    assert "터치 한 번에 자동 개폐" in captured["p"]
    assert "무자막" in captured["p"]


def test_generate_mix_still_drops_empty_source(monkeypatch):
    """full_text도 특장점도 없는 소스는 여전히 제외(빈 재료 주입 금지)."""
    monkeypatch.setattr(script_generate.comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    calls = {}
    monkeypatch.setattr(script_generate, "_generate_drafts",
                        lambda prompt, **k: calls.setdefault("p", prompt) or [])
    monkeypatch.setattr(script_generate, "_verify_and_fix", lambda drafts, secs: drafts)
    # 살아있는 소스 1개 + 완전 빈 소스 1개 → 유효 1개라 2개 미만으로 []
    out = script_generate.generate_mix(
        [{"name": "A", "full_text": "있음", "structure": {}},
         {"name": "빈", "full_text": "", "structure": {}}], target_seconds=30)
    assert out == []
    assert "p" not in calls   # 프롬프트 자체를 안 만든다(과금 0)


def test_mix_source_block_shows_benefits():
    block = script_generate._mix_source_block(
        [{"name": "무자막", "full_text": "", "product_benefits": ["자동 개폐", "공간 절약"],
          "structure": {}}])
    assert "자동 개폐" in block and "공간 절약" in block


def test_mix_source_block_no_benefits_line_when_absent():
    """특장점 없으면 빈 라벨 줄을 넣지 않는다(프롬프트 노이즈 방지)."""
    block = script_generate._mix_source_block(
        [{"name": "A", "full_text": "본문", "structure": {}}])
    assert "특장점" not in block


# ── ③ edit_plan._build_inventory (라이브 scene_first 경로) ────────────────
def _script(vid, segs):
    return {"video_id": vid, "segments": segs, "full_text": ""}


def _seg(sid, start, end, text="", desc="화면", **kw):
    d = {"seg_id": sid, "start": start, "end": end, "text": text, "scene_desc": desc}
    d.update(kw)
    return d


def test_build_inventory_line_carries_benefits():
    """무자막 소스는 '말:' 칸이 비므로 특장점을 라인에 실어야 대본이 녹일 수 있다."""
    segs = [_seg("s1-0", 0, 1),
            _seg("s1-1", 1, 3, desc="셔터 자동 개폐",
                 product_benefits=["터치 한 번에 자동 개폐"]),
            _seg("s1-2", 3, 5)]
    seg_map, block = edit_plan._build_inventory([_script("s1", segs)])
    assert "터치 한 번에 자동 개폐" in block
    assert seg_map["s1-1"]["product_benefits"] == ["터치 한 번에 자동 개폐"]


def test_build_inventory_no_benefits_unchanged():
    """특장점 없는 기존 소스는 라인 포맷이 그대로(회귀 0).

    세그 5개인 이유: 인벤토리는 첫·마지막을 버리는데 '잘라낸 뒤 3개 이상 남을 때만'
    자른다(2026-08-14 기준 변경). 검사 대상 s1-1만 남기려면 5개가 필요하다.
    """
    segs = [_seg("s1-0", 0, 1), _seg("s1-1", 1, 3, text="말소리", desc="컵"),
            _seg("s1-2", 3, 5), _seg("s1-3", 5, 7), _seg("s1-4", 7, 9)]
    _, block = edit_plan._build_inventory([_script("s1", segs)])
    block = "\n".join(l for l in block.split("\n") if "[s1-1]" in l)
    # 훅 비주얼(2026-07-29): 역할(shot_role 기본 '기타')·실증(is_key 기본 N)이 별도 suffix로 붙는다.
    assert block == "[s1-1] (2s) 화면:컵 | 말:말소리 | 역할:기타 | 실증:N"


# ── ③-b 소스 단위 특장점 블록 (프롬프트 주입) ─────────────────────────────
def test_source_benefits_block_uses_top_level():
    b = edit_plan._source_benefits_block(
        [{"product_benefits": ["터치 한 번에 자동 개폐", "공간 절약"], "segments": []}])
    assert "소스1" in b and "터치 한 번에 자동 개폐" in b
    assert "지어내지 마라" in b   # 환각 가드


def test_source_benefits_block_falls_back_to_segments():
    """최상위 필드가 없는 캐시(이 변경 전 추출본)는 세그별 집계로 폴백."""
    b = edit_plan._source_benefits_block(
        [{"segments": [_seg("s1-0", 0, 1, product_benefits=["좁은 틈에 쏙"])]}])
    assert "좁은 틈에 쏙" in b


def test_source_benefits_block_empty_when_none():
    """특장점이 전무하면 빈 문자열 = 프롬프트 무주입(회귀 0)."""
    assert edit_plan._source_benefits_block([{"segments": [_seg("s1-0", 0, 1)]}]) == ""
    assert edit_plan._source_benefits_block([]) == ""


def test_scene_first_prompt_injects_benefits_block(monkeypatch):
    """생성 프롬프트에 특장점 블록이 실제로 실려야."""
    seen = {}
    edit_plan._scene_first_candidates(
        "[s1-0] (2s) 화면:셔터 개폐 | 말:", "", 30, n=1,
        call=lambda *a, **k: seen.setdefault("prompt", a[0] if a else k.get("prompt")) and None,
        benefits_block="[제품 특장점]\n- 소스1: 터치 한 번에 자동 개폐")
    assert "터치 한 번에 자동 개폐" in seen["prompt"]


def test_scene_first_prompt_no_block_when_empty(monkeypatch):
    """블록이 비면 프롬프트에 '제품 특장점' 라벨이 안 들어간다(무주입)."""
    seen = {}
    edit_plan._scene_first_candidates(
        "[s1-0] (2s) 화면:컵 | 말:안녕", "", 30, n=1,
        call=lambda *a, **k: seen.setdefault("prompt", a[0] if a else k.get("prompt")) and None,
        benefits_block="")
    assert "제품 특장점" not in seen["prompt"]
