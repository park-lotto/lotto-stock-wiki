"""P0-3 novelty 메모리 — job 간 반복 차단.

기존 다양성 장치는 전부 '한 job 안'만 본다. 어제 영상과 오늘 영상이 같은 훅·인물·CTA여도
아무도 모른다. 최근 N개 job이 쓴 (훅·인물·CTA)를 기록하고, 다음 생성 프롬프트에 '이건
이미 썼으니 다르게'로 주입한다.
"""
import shopping_shorts.mix_pipeline as mp
from shopping_shorts import bank_assemble as BA
from shopping_shorts import edit_plan
from shopping_shorts.store import Store


# ---- store: 사용이력 기록·조회 왕복 ----

def test_record_and_recent_roundtrip(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.record_script_usage("와 이거 대박", "시어머니", "보관법")
    s.record_script_usage("이걸 왜 이제 알았지", "남편", "레시피")
    rec = s.recent_script_usage(limit=8)
    assert "와 이거 대박" in rec["hooks"] and "이걸 왜 이제 알았지" in rec["hooks"]
    assert "시어머니" in rec["persons"] and "남편" in rec["persons"]
    assert "보관법" in rec["ctas"] and "레시피" in rec["ctas"]


def test_recent_empty_when_no_history(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    rec = s.recent_script_usage()
    assert rec == {"hooks": [], "persons": [], "ctas": []}


def test_recent_respects_limit_newest_first(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    for i in range(10):
        s.record_script_usage(f"훅{i}", f"인물{i}", f"키{i}")
    rec = s.recent_script_usage(limit=3)
    assert rec["hooks"] == ["훅9", "훅8", "훅7"]   # 최신 3개


def test_record_skips_empty_fields(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.record_script_usage("훅만", "", "")
    rec = s.recent_script_usage()
    assert rec["hooks"] == ["훅만"] and rec["persons"] == [] and rec["ctas"] == []


# ---- bank_assemble: 회피 블록 ----

def test_avoid_block_lists_recent(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.record_script_usage("와 이거 대박", "시어머니", "보관법")
    block = BA.avoid_block(s)
    assert "와 이거 대박" in block and "시어머니" in block
    assert "다르게" in block   # 회피 지시문
    # ★CTA는 회피 목록에서 뺐다(2026-08-03 사장님: "CTA는 고정으로 댓글에 OO 남겨주세요로").
    #   형식을 고정해놓고 "최근 쓴 CTA와 다르게"를 요구하면 서로 충돌해 모델이 형식을 벗어난다.
    #   달라져야 하는 건 **키워드**지 형식이 아니다.
    assert "보관법" not in block, "CTA가 여전히 회피 목록에 있다(형식 고정과 충돌)"


def test_avoid_block_empty_when_no_history(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert BA.avoid_block(s) == ""


def test_avoid_block_sanitizes_braces(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.record_script_usage("가격은 {x}원", "", "")
    assert "{" not in BA.avoid_block(s)


# ---- _plan_and_tts: 추천 후보의 story 기록 + 회피블록 주입(설정 on) ----

def _wire(monkeypatch, box):
    def fake_sf(source_scripts, reference_text, target_seconds, **kw):
        box["bank"] = kw.get("bank_context")
        box["avoid"] = kw.get("avoid_hooks")   # novelty on/off를 직접 확인하려고 같이 담는다
        return {"candidates": [
            {"plan": {"beats": [{"beat_idx": 0}], "structure": "free",
                      "plagiarism_flags": [], "detected_type": "x", "affiliate_target": ""},
             "story": {"hook": "와 이거 진짜 놀랐어요", "story_person": "시어머니",
                       "cta_keyword": "보관법"},
             "score": 0.9, "recommended": True}]}
    monkeypatch.setattr(edit_plan, "build_scene_first_plan", fake_sf)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_conform_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_refill_beats_to_tts", lambda *a, **k: None)


def test_plan_and_tts_records_usage(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "t.db"))
    store.create_mix_job("j", ["u0", "u1"], 20, "free", scene_first=True)
    box = {}
    _wire(monkeypatch, box)
    mp._plan_and_tts(store, "j", [{"full_text": "x"}], 20, "free", None, tmp_path / "w",
                     scene_first=True, reference_text="ref")
    rec = store.recent_script_usage()
    assert "와 이거 진짜 놀랐어요" in rec["hooks"]
    assert "시어머니" in rec["persons"] and "보관법" in rec["ctas"]


def test_plan_and_tts_no_avoid_even_when_bank_enabled(tmp_path, monkeypatch):
    # 2026-07-27: novelty(avoid) 완전 OFF — 은행은 parts_block(우수 라인)만 주입, 회피블록 미주입.
    store = Store(str(tmp_path / "t.db"))
    store.set_setting("bank_enabled", "1")
    store.record_script_usage("옛날에쓴훅", "옛인물", "옛키")
    store.create_mix_job("j", ["u0", "u1"], 20, "free", scene_first=True)
    box = {}
    _wire(monkeypatch, box)
    mp._plan_and_tts(store, "j", [{"full_text": "x"}], 20, "free", None, tmp_path / "w",
                     scene_first=True, reference_text="ref")
    assert "옛날에쓴훅" not in box.get("bank", "")   # 회피(novelty) 미주입 — 드리프트 차단


def test_plan_and_tts_no_avoid_when_disabled(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "t.db"))
    store.record_script_usage("옛날에쓴훅", "옛인물", "옛키")
    store.create_mix_job("j", ["u0", "u1"], 20, "free", scene_first=True)
    box = {}
    _wire(monkeypatch, box)
    mp._plan_and_tts(store, "j", [{"full_text": "x"}], 20, "free", None, tmp_path / "w",
                     scene_first=True, reference_text="ref")
    # 설정 off → 회귀0(옛날에 쓴 훅이 회피 목록으로 안 들어간다).
    # ⚠️ ""로 보면 안 된다(2026-08-10) — 2026-08-04부터 확정 훅패턴 10종이 은행 on/off와
    #    무관하게 bank_context에 항상 붙는다(mix_pipeline.py:891). 여기서 지킬 것은
    #    **옛 사용기록이 새어 들어오지 않는가**이므로 그것으로 검사한다.
    assert "옛날에쓴훅" not in box["bank"]
    assert box["avoid"] in (None, [], "")   # novelty OFF → 회피 목록 자체가 없다
