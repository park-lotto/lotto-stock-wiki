from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store

# 라우트에 넘기는 URL은 실제 형태여야 한다 — SSRF 가드(P0-3)가 스킴·호스트를 검사하므로
# "u0" 같은 자리표시자는 실사용에서 존재할 수 없는 입력이고 422로 막힌다.
# (store에 직접 넣는 픽스처는 라우트를 안 거치므로 자리표시자 그대로 둔다.)
_U0 = "https://www.instagram.com/reel/AAA111/"
_U1 = "https://www.instagram.com/reel/BBB222/"


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    # 백그라운드 작업은 즉시 no-op(상태만 미리 세팅해 검증)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "retype_mix_job", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


def test_mix_start_creates_job(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/mix/start", json={"urls": [_U0, _U1], "target_seconds": 20, "structure": "free"})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert store.get_mix_job(jid)["status"] == "downloading"


def test_mix_status_and_result(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j1", ["u0"], 20, "free")
    store.update_mix_job("j1", status="ready_for_review", edit_plan={
        "structure": "free",
        "beats": [{"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
                   "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
                   "alternates": [], "effect": "cut"}],
        "plagiarism_flags": []})
    assert client.get("/api/mix/status/j1").json()["status"] == "ready_for_review"
    body = client.get("/api/mix/result/j1").json()
    assert body["beats"][0]["narration"] == "n"


def test_mix_result_includes_video_type(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jv", ["u0"], 20, "free")
    store.update_mix_job("jv", status="ready_for_review", edit_plan={
        "structure": "free", "detected_type": "recipe_secret", "affiliate_target": "소금",
        "beats": [{"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
                   "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
                   "alternates": [], "effect": "cut"}],
        "plagiarism_flags": []})
    body = client.get("/api/mix/result/jv").json()
    # 장면스파인 재설계: 옛 key recipe_secret은 recipe로 정규화돼 표시된다.
    assert body["detected_type"] == "recipe"
    assert "요리" in body["detected_type_label"]
    assert body["affiliate_target"] == "소금"
    assert any(t["key"] == "generic" for t in body["video_types"])


def test_mix_retype_valid_and_invalid(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jr", ["u0"], 20, "free")
    store.update_mix_job("jr", extract={"s0": {"video_id": "s0", "full_text": "x", "segments": []}})
    # 유효 유형 → 200
    assert client.post("/api/mix/retype", json={"job_id": "jr", "video_type": "recipe_secret"}).status_code == 200
    # 무효 유형 → 422
    assert client.post("/api/mix/retype", json={"job_id": "jr", "video_type": "nope"}).status_code == 422
    # extract 없는 job → 404
    store.create_mix_job("jr2", ["u0"], 20, "free")
    assert client.post("/api/mix/retype", json={"job_id": "jr2", "video_type": "recipe_secret"}).status_code == 404


def test_mix_adjust_regrounds_from_inventory(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j2", ["u0"], 20, "free")
    store.update_mix_job("j2", extract={"s0": {"video_id": "s0", "full_text": "x", "segments": [
        {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "c"},
        {"seg_id": "s0-1", "start": 2.0, "end": 4.0, "text": "b", "scene_desc": "d"},
    ]}}, edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
         "alternates": [], "effect": "cut"}], "plagiarism_flags": []}, status="ready_for_review")
    # beat0의 primary를 s0-1로 교체 — start/end/scene_desc는 서버가 인벤토리에서 되붙여야 함
    # (scene_desc는 _ground_ref가 실어준다, 2026-07-20 ① visual_verb 앵커 태스크에서 추가 —
    #  얼굴정렬·리컨사일이 grounded primary의 scene_desc를 읽으므로 adjust 리그라운딩도 실어야 일관)
    # is_key·shot_role도 _ground_ref가 실어준다(2026-07-26 Task8, scene_first 앵커 dedup·grain
    #  주경로 배선) — 입력 세그에 없으면 기본 False/"기타". adjust 리그라운딩도 같은 함수라 일관.
    r = client.post("/api/mix/adjust", json={"job_id": "j2", "beat_idx": 0, "video_id": "s0", "seg_id": "s0-1"})
    assert r.status_code == 200
    plan = store.get_mix_job("j2")["edit_plan"]
    assert plan["beats"][0]["primary"] == {"video_id": "s0", "seg_id": "s0-1", "start": 2.0, "end": 4.0,
                                           "scene_desc": "d", "is_key": False, "shot_role": "기타"}


def test_mix_adjust_invalid_beat_idx_returns_404(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j2b", ["u0"], 20, "free")
    store.update_mix_job("j2b", extract={"s0": {"video_id": "s0", "full_text": "x", "segments": [
        {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "c"},
        {"seg_id": "s0-1", "start": 2.0, "end": 4.0, "text": "b", "scene_desc": "d"},
    ]}}, edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
         "alternates": [], "effect": "cut"}], "plagiarism_flags": []}, status="ready_for_review")
    # 존재하지 않는 beat_idx — 매치되는 비트가 없으면 404여야 함(성공으로 위장 금지)
    r = client.post("/api/mix/adjust", json={"job_id": "j2b", "beat_idx": 999, "video_id": "s0", "seg_id": "s0-1"})
    assert r.status_code == 404
    plan = store.get_mix_job("j2b")["edit_plan"]
    assert plan["beats"][0]["primary"] == {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0}


def test_mix_adjust_clears_stale_fit(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j2f", ["u0"], 20, "free")
    store.update_mix_job("j2f", extract={"s0": {"video_id": "s0", "full_text": "x", "segments": [
        {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "c"},
        {"seg_id": "s0-1", "start": 2.0, "end": 4.0, "text": "b", "scene_desc": "d"},
    ]}}, edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2, "fit": 2,
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
         "alternates": [], "effect": "cut"}], "plagiarism_flags": []}, status="ready_for_review")
    r = client.post("/api/mix/adjust", json={"job_id": "j2f", "beat_idx": 0, "seg_id": "s0-1"})
    assert r.status_code == 200
    beat = store.get_mix_job("j2f")["edit_plan"]["beats"][0]
    assert beat["primary"]["seg_id"] == "s0-1"
    assert beat.get("fit") in (None, 0)          # 낡은 fit 제거됨


def test_mix_render_sets_background(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j3", ["u0"], 20, "free")
    store.update_mix_job("j3", status="ready_for_review", edit_plan={"structure": "free", "beats": [], "plagiarism_flags": []})
    assert client.post("/api/mix/render", json={"job_id": "j3"}).status_code == 200


# ── 영상제작소 2단계: 1개 영상 순서편집도 허용(2026-07-14) ──────────

def test_produce_mix_start_accepts_single_url(monkeypatch, tmp_path):
    """소스 1개만 보내도(레퍼런스 모음집에서 하나만 골라 보낸 경우) 시작돼야 한다
    — 그 영상 안에서 구간 순서편집. 예전엔 '2개 이상' 검증에 막혔다."""
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/mix/start",
                    json={"script": "테스트 대본", "urls": [_U0], "target_seconds": 20})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert store.get_mix_job(jid)["urls"] == [_U0]


def test_produce_mix_start_charges_render(monkeypatch, tmp_path):
    """제작소 2단계도 render 크레딧을 과금한다(2026-07-20 E) — 안 그러면 이 흐름으로
    하루 상한·전역 상한을 통째로 우회한다. 과금 표식 render_charge_day가 job에 찍혀
    /api/mix/start와 동일하게 실패 시 자동 환불도 걸린다."""
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/mix/start",
                    json={"script": "테스트 대본", "urls": [_U0, _U1], "target_seconds": 20})
    assert r.status_code == 200
    assert store.get_mix_job(r.json()["job_id"]).get("render_charge_day")  # 과금됨


def test_produce_mix_start_rejects_empty_urls(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/mix/start",
                    json={"script": "테스트 대본", "urls": [], "target_seconds": 20})
    assert r.status_code == 422


def test_produce_mix_start_rejects_empty_script(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/mix/start",
                    json={"script": "", "urls": [_U0, _U1], "target_seconds": 20})
    assert r.status_code == 422


def test_produce_mix_settings_saves_highlight_rules_inside_deco(monkeypatch, tmp_path):
    """설계서 §2: deco는 서버가 필드를 까지 않고 통짜 dict로 저장/조회한다 —
    highlight_rules도 서버 코드 변경 없이 그대로 왕복돼야 한다(회귀 확인용 스모크 테스트)."""
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jd1", ["u0"], 20, "free")
    r = client.post("/api/produce/mix/settings", json={
        "job_id": "jd1",
        "deco": {"extra_texts": [], "highlight_rules": [
            {"keyword": "쿠팡", "color": "#FF2D2D", "box": True, "box_color": "#FFE100"}]},
    })
    assert r.status_code == 200
    saved = store.get_mix_job("jd1")
    assert saved["deco"]["highlight_rules"][0]["keyword"] == "쿠팡"


# ── 대본용 영상 URL 직접추출(2026-07-14) — last_run 의존 제거 ──────────

def test_extract_from_url_extracts_without_last_run(monkeypatch, tmp_path):
    """즐겨찾기에 예전 run 때 담긴 영상(last_run에 없음)도 URL로 직접 대본추출돼야 한다.
    /api/extract_script는 last_run 조회라 실패하던 실버그(2026-07-14) 대응 엔드포인트."""
    client, store = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "download_any", lambda url, d: ("/tmp/x.mp4", "캡션"))
    monkeypatch.setattr(app_module, "extract_auto",
                        lambda path, code, caption="": {"full_text": "감자 대본", "segments": []})
    r = client.post("/api/produce/extract_from_url",
                    json={"url": "https://www.instagram.com/p/OLD/", "shortcode": "OLD1"})
    assert r.status_code == 200
    assert r.json()["full_text"] == "감자 대본"


def test_extract_from_url_caches_by_shortcode(monkeypatch, tmp_path):
    """shortcode로 캐시 재사용 — 두 번째 호출은 다운로드/추출 없이 즉시 캐시 반환."""
    client, store = _client(monkeypatch, tmp_path)
    calls = {"dl": 0}
    def fake_dl(url, d): calls["dl"] += 1; return ("/tmp/x.mp4", "")
    monkeypatch.setattr(app_module, "download_any", fake_dl)
    monkeypatch.setattr(app_module, "extract_auto",
                        lambda path, code, caption="": {"full_text": "T", "segments": []})
    body = {"url": "https://insta/p/X", "shortcode": "SC1"}
    assert client.post("/api/produce/extract_from_url", json=body).json()["full_text"] == "T"
    r2 = client.post("/api/produce/extract_from_url", json=body)
    assert r2.json()["cached"] is True
    assert calls["dl"] == 1   # 두 번째는 다운로드 안 함


def test_extract_from_url_download_failure_returns_502(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    def boom(url, d): raise RuntimeError("URL expired")
    monkeypatch.setattr(app_module, "download_any", boom)
    r = client.post("/api/produce/extract_from_url", json={"url": "https://insta/p/GONE"})
    assert r.status_code == 502


def test_extract_from_url_requires_url(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    assert client.post("/api/produce/extract_from_url", json={"url": ""}).status_code == 422


# ── 유료게이트: 대본추출 'script' 크레딧 배선(2026-07-19 설계 재검토) ──────────
def _today():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_extract_from_url_charges_script_credit_on_miss_not_hit(monkeypatch, tmp_path):
    """캐시미스 대본추출은 'script' 크레딧을 1 소비, 캐시히트 재클릭은 무료(증가 없음).
    (이전엔 script가 미배선이라 무제한 — /api/me·admin은 캡된 척했다)."""
    client, store = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "download_any", lambda url, d: ("/tmp/x.mp4", ""))
    monkeypatch.setattr(app_module, "extract_auto",
                        lambda path, code, caption="": {"full_text": "T", "segments": []})
    body = {"url": "https://insta/p/SC", "shortcode": "SCA"}
    day = _today()
    assert store.usage_get(0, "script", day) == 0
    client.post("/api/produce/extract_from_url", json=body)   # 미스 → 과금
    assert store.usage_get(0, "script", day) == 1
    client.post("/api/produce/extract_from_url", json=body)   # 히트 → 무료
    assert store.usage_get(0, "script", day) == 1


def test_extract_from_url_refunds_script_credit_on_failure(monkeypatch, tmp_path):
    """다운로드 실패(캐시미스)면 예약한 'script' 크레딧을 환불 → 계정·전역 순증가 0."""
    client, store = _client(monkeypatch, tmp_path)
    def boom(url, d):
        raise RuntimeError("URL expired")
    monkeypatch.setattr(app_module, "download_any", boom)
    day = _today()
    r = client.post("/api/produce/extract_from_url", json={"url": "https://insta/p/GONE2"})
    assert r.status_code == 502
    assert store.usage_get(0, "script", day) == 0
    assert store.usage_get(-1, "script", day) == 0


def test_extract_from_url_blocks_when_script_daily_exhausted(monkeypatch, tmp_path):
    """script 일일 상한 소진이면 429 daily_limit — 캐시미스 진입(Gemini 비용) 자체를 막는다."""
    client, store = _client(monkeypatch, tmp_path)
    store.set_setting("limit_script_pro", 0)   # cid0=pro → pro 상한 0으로 강제 소진
    monkeypatch.setattr(app_module, "download_any", lambda url, d: ("/tmp/x.mp4", ""))
    monkeypatch.setattr(app_module, "extract_auto",
                        lambda path, code, caption="": {"full_text": "T", "segments": []})
    r = client.post("/api/produce/extract_from_url",
                    json={"url": "https://insta/p/Q", "shortcode": "QQ"})
    assert r.status_code == 429
    assert r.json().get("error_code") == "daily_limit"


def test_run_mix_job_refunds_render_credit_on_failure(monkeypatch, tmp_path):
    """렌더 잡 실패 시 예약한 'render' 크레딧을 job의 customer_id로, render_charge_day 날짜로 환불.
    실패했는데 크레딧만 날아가면 시니어에겐 '고장'으로 읽힌다(하루 2회뿐)."""
    from shopping_shorts import mix_pipeline
    db = str(tmp_path / "t.db")
    store = Store(db)
    cid, day = 7, _today()
    store.usage_incr(cid, "render", day)     # /api/mix/start이 예약한 상태를 재현
    store.usage_incr(-1, "render", day)
    store.create_mix_job("jf", ["u"], 20, "free", customer_id=cid, render_charge_day=day)
    monkeypatch.setattr(mix_pipeline, "_prepare_sources",
                        lambda urls, work: (_ for _ in ()).throw(RuntimeError("boom")))
    mix_pipeline.run_mix_job("jf", db, str(tmp_path / "work"))
    assert store.get_mix_job("jf")["status"] == "failed"
    assert store.get_mix_job("jf")["customer_id"] == cid
    assert store.usage_get(cid, "render", day) == 0    # 환불됨
    assert store.usage_get(-1, "render", day) == 0


def test_run_mix_job_does_not_refund_uncharged_job(monkeypatch, tmp_path):
    """★리뷰 B 회귀방지: render_charge_day가 없는 job(auto_run 배치 — 과금 안 함)은
    실패해도 환불하지 않는다. 안 그러면 전역 카운터를 갉아 다른 유저의 정당한 과금을 상쇄한다.
    (2026-07-20 E부터 produce 2단계는 과금하므로 이 미과금 경로는 auto_run뿐이다.)"""
    from shopping_shorts import mix_pipeline
    db = str(tmp_path / "t.db")
    store = Store(db)
    day = _today()
    store.usage_incr(-1, "render", day)      # 다른 유저가 정당하게 과금해 둔 전역 카운트
    store.create_mix_job("ju", ["u"], 20, "free")   # render_charge_day 없음(과금 안 한 경로)
    monkeypatch.setattr(mix_pipeline, "_prepare_sources",
                        lambda urls, work: (_ for _ in ()).throw(RuntimeError("boom")))
    mix_pipeline.run_mix_job("ju", db, str(tmp_path / "work"))
    assert store.get_mix_job("ju")["status"] == "failed"
    assert store.usage_get(-1, "render", day) == 1   # 남의 과금이 상쇄되지 않음(환불 안 함)
