# -*- coding: utf-8 -*-
"""클로드형 서버 포털(관제 234, 숏템MCP) — 라이선스·기기·임대·자산·견본·탐지·노출 검사.

여기서 못 박는 것(설계 §7·§8·§10 '결과물 검사'):
1. 라이선스 위조·만료·재발급(옛 키 무효)·전역 kv
2. 기기 3대째 거절(자동 교체 없음)
3. lease 두 기기 동시 → 두 번째 409 / TTL 지나면 성공 / 강제 해제 → 앞 기기 lease_lost
4. assets 자산 수 = 참조 수(안 쓰는 글꼴·곡이 섞이면 실패) · blob sha256 일치 · 목록 밖 pack 거절
5. 페이지·me/home 응답에 금지 키·원본 서명 URL 0개
6. 견본 Range 403 · 500개 긁기 → 속도 제한 · A1 키 공유(국가 2) 경고 → 2회째 정지
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts import channel_profile
from shopping_shorts import claude_portal as cp
from shopping_shorts.store import Store

FP1, FP2, FP3 = ("a" * 64), ("b" * 64), ("c" * 64)
ROOT = Path(__file__).resolve().parents[2]


def _w(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def env(monkeypatch, tmp_path):
    croot, sdir = tmp_path / "repo", tmp_path / "store"
    monkeypatch.setenv("CLAUDE_STORE_DIR", str(sdir))
    monkeypatch.setenv("CLAUDE_CHANNEL_ROOT", str(croot))
    monkeypatch.setenv("CLAUDE_LICENSE_SECRET", "test-claude-secret")
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    st = Store(db)
    st.set_setting("claude_portal_enabled", "1")
    # 장부 — 벤치 채널명·slug·strengths·path·commit 이 들어 있다(페이지로 새면 안 되는 것)
    _w(croot / "channel" / "브랜드.json", {"brands": {"benchslug": {"brand": "테스트홈", "bench": "벤치채널이름"}}})
    _w(croot / "channel" / "스타일.json", {"styles": {"자막썰": {"priority": 1, "desc": "자막으로 썰을 푼다", "example": "https://y/1 (사장님 기준 예시)",
                                                         "audio_kinds": ["나레"], "strengths": [{"what": "비밀강점", "evidence": "근거"}],
                                                         "bench": {"benchslug": {"n": 3}}}}, "options": {}})
    _w(croot / "channel" / "결과물.json", {"items": [{"n": 1, "channel": "benchslug", "title": "칼카피 1호 ZdeZ", "path": "C:/x/final.mp4",
                                                     "commit": "abc1234", "judge": "페이블 판정 통과", "style": "자막썰", "seconds": 20.5}]})
    pdir = croot / "channel" / "benchslug" / "preset" / "A_흰바탕창" / "창아래_검정"
    _w(pdir / "frame.json", {"canvas": [1080, 1920], "made_by": "calcopy_frame v1", "source": "ZdeZRtCeAC4", "layers": [
        {"kind": "bg", "rgb": [255, 255, 255]},
        {"kind": "text", "role": "title", "font": "SBAggroB", "text": "$per_video"},
        {"kind": "text", "role": "caption", "font": "CcSpoqaHanSansNeo-Bold", "text": None, "enter": {"kind": "none", "ms": 300}},
        {"kind": "text", "role": "brand", "font": "TmonMonsori", "text": "[광고]"}]})
    _w(pdir / "manifest.json", {"slug": "benchslug", "sources": [{"id": "ZdeZRtCeAC4"}], "variable_stats": {"x": 1},
                                "rules": {"formula": "title.size = cap", "why": "벤치 근거"}, "roles": ["발견", "의심"],
                                "fixed": {"layers[text:brand].outline": {"value": {"px": 3}, "why": "렌더 대조 근거"}}})
    # 원본 자산(가짜 파일) — 내용주소로 저장
    src = tmp_path / "src"
    src.mkdir()

    def reg(aid, kind, grp="", body=None):
        f = src / aid.replace(":", "_").replace("/", "_")
        f.write_bytes(body or (aid * 50).encode())
        sha, size = cp.put_blob(f)
        cp.upsert_asset(st, aid, kind, f.name, sha, size, grp=grp, preview_id=aid.split(":", 1)[1])
        return sha
    for fam in ("SBAggroB", "CcSpoqaHanSansNeo-Bold", "TmonMonsori", "JalnanGothic"):
        reg(f"font:{fam}", "font")
    reg("sfx:팩01/opener.wav", "sfx", "팩01")
    reg("sfx:팩01/pop.wav", "sfx", "팩01")
    reg("sfx:팩02/opener.wav", "sfx", "팩02", b"other")
    reg("bgm:qiuqiu", "bgm")
    reg("bgm:blue", "bgm")
    reg("template:tpl_01", "template")
    reg("meme:1", "meme", "웃음")
    reg("meme:2", "meme", "분노")
    # 견본(가짜 파일)
    for kind, pid, ext in (("font", "JalnanGothic", "png"), ("bgm", "qiuqiu", "mp3"), ("sfx", "팩01", "mp3")):
        f = sdir / "preview" / kind / f"{pid}.{ext}"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"PREVIEW-" + pid.encode())
    client = TestClient(app_module.app)
    preset_id = cp.presets(st)[0]["id"]
    return {"client": client, "store": st, "preset": preset_id, "sdir": sdir, "monkeypatch": monkeypatch}


def _h(key, fp=FP1, engine="1.0.0", name="사무실 PC", country=None):
    h = {"Authorization": f"Bearer {key}", "X-Shortem-Device": fp, "X-Shortem-Engine": engine,
         "X-Shortem-Device-Name": quote(name)}   # 한글 기기명은 퍼센트 인코딩(헤더는 ASCII 만)
    if country:
        h["CF-IPCountry"] = country
    return h


def _key(env, cid=0):
    return cp.issue_license(cid, env["store"])["key"]


# ── 1. 라이선스 ──────────────────────────────────────────────────────────
def test_라이선스_위조_만료_재발급(env, monkeypatch):
    c = env["client"]
    k1 = _key(env)
    r = c.get("/api/claude/license", headers=_h(k1))
    assert r.status_code == 200 and r.json()["ok"], r.text
    assert r.json()["entitled_presets"] == [env["preset"]]
    # 위조: 서명 한 글자
    bad = k1[:-1] + ("0" if k1[-1] != "0" else "1")
    r = c.get("/api/claude/license", headers=_h(bad))
    assert r.status_code == 401 and r.json()["code"] == "bad_key"
    # cid 를 바꿔 끼운 키(서명은 옛 것) — 위조
    parts = k1.split(".")
    parts[1] = "7"
    r = c.get("/api/claude/license", headers=_h(".".join(parts)))
    assert r.json()["code"] == "bad_key"
    # 키 없음
    r = c.get("/api/claude/license", headers={"X-Shortem-Device": FP1, "X-Shortem-Engine": "1.0.0"})
    assert r.status_code == 401 and r.json()["code"] == "no_key"
    # 재발급 → 옛 키 즉시 무효, 새 키 됨
    k2 = _key(env)
    assert c.get("/api/claude/license", headers=_h(k1)).json()["code"] == "revoked"
    assert c.get("/api/claude/license", headers=_h(k2)).status_code == 200
    # 서버는 키 원문을 저장하지 않는다
    with cp._tx(env["store"]) as con:
        dump = "\n".join(str(r) for r in con.execute("SELECT * FROM claude_licenses").fetchall())
    assert k2 not in dump and k2.split(".")[-1] not in dump
    # 전역 kv 변경 → 전 고객 무효
    env["store"].set_setting("license_kv", "1")
    assert c.get("/api/claude/license", headers=_h(k2)).json()["code"] == "revoked"
    env["store"].set_setting("license_kv", "0")
    # 만료
    exp = int(k2.split(".")[2])
    monkeypatch.setattr(cp, "_now", lambda: exp + 10)
    r = c.get("/api/claude/license", headers=_h(k2))
    assert r.status_code == 401 and r.json()["code"] == "expired"


def test_스위치_꺼짐이면_503_admin값은_관리자만(env):
    c, st = env["client"], env["store"]
    k0, k5 = _key(env, 0), _key(env, 5)
    st.set_setting("claude_portal_enabled", "")
    r = c.get("/api/claude/license", headers=_h(k0))
    assert r.status_code == 503 and r.json()["code"] == "disabled"
    st.set_setting("claude_portal_enabled", "admin")
    assert c.get("/api/claude/license", headers=_h(k0)).status_code == 200
    assert c.get("/api/claude/license", headers=_h(k5, FP2)).json()["code"] == "disabled"


def test_엔진_낮으면_거절(env):
    k = _key(env)
    r = env["client"].get("/api/claude/license", headers=_h(k, engine="0.9.0"))
    assert r.status_code == 403 and r.json()["code"] == "engine_old"
    r = env["client"].get("/api/claude/license", headers=_h(k, engine="1.0.0-forged"))
    assert r.json()["code"] == "engine_old"


# ── 2. 기기 대수 ─────────────────────────────────────────────────────────
def test_기본은_PC_1대_두번째_기기_거절(env):
    """5판 사장님 결정: PC 1대만. 두 번째 기기는 거절, 첫 기기를 빼면 들어온다."""
    from shopping_shorts import claude_portal as cp
    assert cp.DEVICES_MAX == 1
    c = env["client"]
    k = _key(env)
    assert c.get("/api/claude/license", headers=_h(k, FP1, name="사무실")).json()["devices_max"] == 1
    r = c.get("/api/claude/license", headers=_h(k, FP2, name="집"))
    assert r.status_code == 403 and r.json()["code"] == "device_limit"
    assert c.post("/api/claude/me/device/remove", json={"device_id": FP1[:12]}).json()["ok"]
    assert c.get("/api/claude/license", headers=_h(k, FP2)).json()["device"]["slot"] == 1


def test_기기_3대째_거절(env, monkeypatch):
    from shopping_shorts import claude_portal as cp
    monkeypatch.setattr(cp, "DEVICES_MAX", 2)   # 상한이 2일 때의 규칙(교체는 사람이)
    c = env["client"]
    k = _key(env)
    a = c.get("/api/claude/license", headers=_h(k, FP1, name="사무실")).json()
    b = c.get("/api/claude/license", headers=_h(k, FP2, name="집")).json()
    assert a["device"]["registered_now"] and a["device"]["slot"] == 1
    assert b["device"]["registered_now"] and b["device"]["slot"] == 2 and b["devices_used"] == 2
    r = c.get("/api/claude/license", headers=_h(k, FP3, name="세번째"))
    assert r.status_code == 403 and r.json()["code"] == "device_limit"
    again = c.get("/api/claude/license", headers=_h(k, FP1)).json()
    assert again["ok"] and not again["device"]["registered_now"]
    # 기기 빼면 세 번째가 들어온다(자동 교체 아님 — 사람이 뺀다)
    assert c.post("/api/claude/me/device/remove", json={"device_id": FP2[:12]}).json()["ok"]
    assert c.get("/api/claude/license", headers=_h(k, FP3)).json()["device"]["slot"] == 2


# ── 3. lease ────────────────────────────────────────────────────────────
def _two_devices(env):
    from shopping_shorts import claude_portal as cp
    env["monkeypatch"].setattr(cp, "DEVICES_MAX", 2)   # 동시 작업 막기 규칙은 기기 상한과 무관 — 두 기기로 시험
    k = _key(env)
    for fp in (FP1, FP2):
        assert env["client"].get("/api/claude/license", headers=_h(k, fp)).status_code == 200
    return k


def test_lease_두기기_동시면_두번째_409_TTL뒤_성공(env, monkeypatch):
    c = env["client"]
    k = _two_devices(env)
    r1 = c.post("/api/claude/lease", headers=_h(k, FP1, name="사무실"), json={"action": "acquire", "job_id": "j1", "step_name": "소재"})
    assert r1.status_code == 200 and r1.json()["ttl"] == 180 and r1.json()["heartbeat_every"] == 60
    again = c.post("/api/claude/lease", headers=_h(k, FP1), json={"action": "acquire", "job_id": "j1"})
    assert again.json()["lease_id"] == r1.json()["lease_id"], "같은 기기·같은 job 재취득은 같은 lease(멱등)"
    r2 = c.post("/api/claude/lease", headers=_h(k, FP2), json={"action": "acquire", "job_id": "j2"})
    assert r2.status_code == 409 and r2.json()["code"] == "busy_other_device"
    assert "사무실" in r2.json()["msg"] and 0 < r2.json()["retry_after"] <= 180
    # 하트비트 없이 TTL 이 지나면 두 번째 기기가 받는다
    t0 = cp._now()
    monkeypatch.setattr(cp, "_now", lambda: t0 + 181)
    r3 = c.post("/api/claude/lease", headers=_h(k, FP2), json={"action": "acquire", "job_id": "j2"})
    assert r3.status_code == 200, r3.text
    # 앞 기기의 하트비트는 이제 lease_lost
    hb = c.post("/api/claude/lease", headers=_h(k, FP1), json={"action": "heartbeat", "lease_id": r1.json()["lease_id"]})
    assert hb.status_code == 409 and hb.json()["code"] == "lease_lost"
    # 없는 lease release 도 ok(멱등)
    assert c.post("/api/claude/lease", headers=_h(k, FP1), json={"action": "release", "lease_id": "ls_none"}).json()["ok"]


def test_강제해제_뒤_앞기기_lease_lost(env):
    c = env["client"]
    k = _two_devices(env)
    lid = c.post("/api/claude/lease", headers=_h(k, FP1), json={"action": "acquire", "job_id": "j1"}).json()["lease_id"]
    assert c.post("/api/claude/lease", headers=_h(k, FP1), json={"action": "heartbeat", "lease_id": lid, "step_name": "렌더"}).status_code == 200
    assert c.post("/api/claude/me/lease/force_release").json()["released"] is True
    hb = c.post("/api/claude/lease", headers=_h(k, FP1), json={"action": "heartbeat", "lease_id": lid})
    assert hb.status_code == 409 and hb.json()["code"] == "lease_lost"
    assert c.post("/api/claude/lease", headers=_h(k, FP2), json={"action": "acquire", "job_id": "j2"}).status_code == 200


def test_lease_단계이름은_고정_9개만(env):
    k = _two_devices(env)
    r = env["client"].post("/api/claude/lease", headers=_h(k), json={"action": "acquire", "job_id": "j1", "step_name": "좌표 계산"})
    assert r.status_code == 400 and r.json()["code"] == "bad_request"


# ── 4. assets ───────────────────────────────────────────────────────────
def _profile(env, **opts):
    body = {"name": "내 채널 · 썰", "preset_id": env["preset"], "options": {
        "brand": {"channel_name": "우리채널"}, "text": {"title_font": "JalnanGothic"},
        "sfx_pack": "팩01", "bgm": {"track": "qiuqiu"}, "template": "tpl_01", "meme_pool": {"kinds": ["웃음"]}, **opts}}
    r = env["client"].post("/api/claude/me/profile", json=body)
    assert r.status_code == 200, r.text
    return r.json()["profile_id"]


def test_assets_자산수_참조수_같고_blob_sha_일치(env):
    c = env["client"]
    k = _two_devices(env)
    pid = _profile(env)
    lid = c.post("/api/claude/lease", headers=_h(k), json={"action": "acquire", "job_id": "j1"}).json()["lease_id"]
    r = c.get(f"/api/claude/assets?profile={pid}&job=j1&lease={lid}", headers=_h(k))
    assert r.status_code == 200, r.text
    d = r.json()
    got = {a["id"] for a in d["assets"]}
    # 합본이 참조하는 것: 제목 글꼴(JalnanGothic 으로 바뀜)·자막·채널명 글꼴 + 팩01 두 파일 + 고른 곡 + 고른 템플릿
    want = {"font:JalnanGothic", "font:CcSpoqaHanSansNeo-Bold", "font:TmonMonsori",
            "sfx:팩01/opener.wav", "sfx:팩01/pop.wav", "bgm:qiuqiu", "template:tpl_01"}
    assert got == want, f"자산 수≠참조 수: 더 {got - want} / 빠짐 {want - got}"
    assert len(d["assets"]) == len(want) and not d["missing"]
    b = d["bundle"]
    assert "source" not in b["frame"] and "made_by" not in b["frame"], "벤치 원본 id·도구 표식이 틀에 남았다"
    title = next(L for L in b["frame"]["layers"] if L.get("role") == "title")
    brand = next(L for L in b["frame"]["layers"] if L.get("role") == "brand")
    assert title["text"] is None and title["font"] == "JalnanGothic" and brand["text"] == "[광고]"   # 광고 표시는 채널명으로 안 덮는다
    assert "frame.layers[text:title].text" in b["per_video"]
    assert "why" not in json.dumps(b["rules"], ensure_ascii=False) and b["rules"]["fixed"]["layers[text:brand].outline"] == {"px": 3}
    assert b["license"]["cid"] == 0 and len(b["license"]["mark"]) == 12
    # 원본 다운로드 = sha256 일치
    a = next(x for x in d["assets"] if x["id"] == "bgm:qiuqiu")
    blob = c.get(a["url"])
    assert blob.status_code == 200 and hashlib.sha256(blob.content).hexdigest() == a["sha256"]
    # 서명 위조 URL 거절
    assert c.get(a["url"][:-2] + "00").status_code in (403, 400)


def test_assets_lease_없거나_다른_job이면_거절(env):
    c = env["client"]
    k = _two_devices(env)
    pid = _profile(env)
    assert c.get(f"/api/claude/assets?profile={pid}&job=j1", headers=_h(k)).json()["code"] == "lease_lost"
    c.post("/api/claude/lease", headers=_h(k), json={"action": "acquire", "job_id": "j1"})
    assert c.get(f"/api/claude/assets?profile={pid}&job=j9", headers=_h(k)).json()["code"] == "lease_lost"
    assert c.get(f"/api/claude/assets?profile={pid}&job=j1", headers=_h(k, FP2)).json()["code"] == "lease_lost"


def test_목록밖_pack_거절_extra는_허용풀만(env):
    c = env["client"]
    k = _two_devices(env)
    pid = _profile(env)
    c.post("/api/claude/lease", headers=_h(k), json={"action": "acquire", "job_id": "j1"})
    assert c.get(f"/api/claude/assets?profile={pid}&job=j1", headers=_h(k)).status_code == 200
    ok = c.get("/api/claude/pack/bgm:qiuqiu?job=j1", headers=_h(k))
    assert ok.status_code == 200 and ok.json()["asset"]["id"] == "bgm:qiuqiu"
    for out in ("bgm:blue", "font:SBAggroB", "sfx:팩02/opener.wav"):
        r = c.get(f"/api/claude/pack/{out}?job=j1", headers=_h(k))
        assert r.status_code == 403 and r.json()["code"] == "not_in_plan", out
    # 다른 job 으로는 같은 자산도 못 받는다
    assert c.get("/api/claude/pack/bgm:qiuqiu?job=j2", headers=_h(k)).json()["code"] == "not_in_plan"
    # extra: 허용 풀(웃음) 안 짤은 붙고, 밖(분노)은 거절
    r = c.get(f"/api/claude/assets?profile={pid}&job=j1&extra=meme:1", headers=_h(k))
    assert "meme:1" in {a["id"] for a in r.json()["assets"]}
    r = c.get(f"/api/claude/assets?profile={pid}&job=j1&extra=meme:2", headers=_h(k))
    assert r.status_code == 403 and r.json()["code"] == "not_in_plan"
    with cp._tx(env["store"]) as con:
        n = con.execute("SELECT COUNT(*) FROM claude_license_log WHERE kind='out_of_plan'").fetchone()[0]
    assert n == 5, "목록 밖 요청이 탐지 기록(A5)에 다 남아야 한다"


def test_프로필_옵션은_자산id만_모르는키_거절(env):
    c = env["client"]
    base = {"name": "p", "preset_id": env["preset"]}
    for opts in ({"unknown": 1}, {"text": {"title_font": "없는글꼴"}}, {"bgm": {"track": "../../etc/passwd"}},
                 {"brand": {"channel_name": "<script>"}}, {"text": {"caption": {"enter": "explode"}}}):
        r = c.post("/api/claude/me/profile", json={**base, "options": opts})
        assert r.status_code == 400 and r.json()["code"] == "bad_request", opts
    r = c.post("/api/claude/me/profile", json={**base, "preset_id": "p_없는것", "options": {}})
    assert r.json()["code"] == "not_entitled"
    r1 = c.post("/api/claude/me/profile", json={**base, "options": {"sfx_pack": "팩02"}}).json()
    r2 = c.post("/api/claude/me/profile", json={**base, "profile_id": r1["profile_id"], "options": {"sfx_pack": "팩01"}}).json()
    assert (r1["version"], r2["version"]) == (1, 2)


def test_merge_원본_틀을_안_건드린다():
    frame = {"source": "x", "layers": [{"kind": "text", "role": "brand", "text": "옛이름", "font": "A"},
                                       {"kind": "text", "role": "title", "text": "옛이름 추천", "font": "B"}]}
    before = json.dumps(frame, ensure_ascii=False)
    m = channel_profile.merge({"frame": frame}, channel_profile.DEFAULT_PACK, {"brand": {"channel_name": "새이름"}})
    assert json.dumps(frame, ensure_ascii=False) == before
    assert [L["text"] for L in m["frame"]["layers"]] == ["새이름", "새이름 추천"] and "source" not in m["frame"]


# ── 5. 노출 검사 ─────────────────────────────────────────────────────────
def test_페이지_응답에_금지키_원본URL_0개(env):
    c = env["client"]
    k = _two_devices(env)
    _profile(env)
    lid = c.post("/api/claude/lease", headers=_h(k), json={"action": "acquire", "job_id": "j1"}).json()["lease_id"]
    assert lid
    # 검사기가 진짜로 잡는지 먼저 — 관리자 장부(preset_home)는 금지 키투성이다(아무것도 안 재는 검사 금지)
    from shopping_shorts import calcopy_board
    assert cp.forbidden_hits(calcopy_board.preset_home(cp.channel_root())), "검사기가 아무것도 못 잡는다"
    assert cp.forbidden_hits({"a": [{"u": "/api/claude/blob/xx.yy"}]}), "원본 URL 검사가 안 잡는다"
    r = c.get("/api/claude/me/home")
    assert r.status_code == 200, r.text
    d = r.json()
    assert cp.forbidden_hits(d) == []
    text = r.text
    for leak in ("벤치채널이름", "benchslug", "칼카피", "abc1234", "비밀강점", "C:/x", "ZdeZ", "사장님 기준"):
        assert leak not in text, leak
    assert d["presets"][0]["brand"] == "테스트홈" and d["presets"][0]["label"] == "흰바탕창 · 창아래 검정"
    assert d["results"] and set(d["results"][0]) == {"n", "brand", "style", "seconds", "date", "preview"}
    assert d["lease"] and d["lease"]["device"]
    page = c.get("/claude")
    assert page.status_code == 200 and "/api/claude/blob/" not in page.text


# ── 6. 견본·탐지 ─────────────────────────────────────────────────────────
def test_견본_Range_403_토큰없으면_거절(env):
    c = env["client"]
    t = c.get("/api/claude/me/preview_token").json()["t"]
    ok = c.get(f"/api/claude/me/preview/font/JalnanGothic?t={t}")
    assert ok.status_code == 200 and ok.content == b"PREVIEW-JalnanGothic"
    assert "no-store" not in ok.headers.get("cache-control", "") and ok.headers.get("content-disposition") == "inline"
    for bad in ("bytes=0-3", "bytes=100-", "bytes=-50"):
        rg = c.get(f"/api/claude/me/preview/font/JalnanGothic?t={t}", headers={"Range": bad})
        assert rg.status_code == 403, bad
    # 브라우저 미디어 첫 요청(bytes=0-)은 통째 200 — 조각(206)으로 주지 않는다
    whole = c.get(f"/api/claude/me/preview/bgm/qiuqiu?t={t}", headers={"Range": "bytes=0-"})
    assert whole.status_code == 200 and whole.content == b"PREVIEW-qiuqiu" and "content-range" not in whole.headers
    assert c.get("/api/claude/me/preview/font/JalnanGothic").status_code == 401
    other = c.get(f"/api/claude/me/preview/font/JalnanGothic?t={t}", headers={"Referer": "https://evil.example/x"})
    assert other.status_code == 403
    # 견본 길은 원본 저장소(assets/)를 못 읽는다
    sha = cp._assets(env["store"], "bgm")[0]["sha256"]
    assert c.get(f"/api/claude/me/preview/bgm/..%2Fassets%2F{sha}?t={t}").status_code in (400, 404)


def test_견본_500개_긁기면_속도제한(env):
    st = env["store"]
    t = cp.preview_token(0)["t"]
    # (가) 기본 임계값 — 분당 60(A4)에서 먼저 막힌다
    hit = None
    for i in range(120):
        try:
            cp.preview(0, "font", "JalnanGothic", t, {}, st)
        except cp.PortalError as e:
            hit = (i, e.code)
            break
    assert hit and hit[1] == "rate_limited" and hit[0] <= 61, hit
    # (나) 분·시간 제한을 풀어도 하루 500개(A10)에서 막힌다
    st.set_setting("claude_anomaly_thresholds", json.dumps({"a4_per_min": 10 ** 6, "a4_per_hour": 10 ** 6}))
    cp.resolve_alert(0, st)
    with cp._tx(st, write=True) as con:
        con.execute("DELETE FROM claude_license_log")
        con.execute("DELETE FROM claude_alerts")
    n_ok, code = 0, None
    for i in range(520):
        try:
            cp.preview(0, "font", "JalnanGothic", t, {}, st)
            n_ok += 1
        except cp.PortalError as e:
            code = e.code
            break
    assert code == "rate_limited" and n_ok == 500, (n_ok, code)
    assert any(a["rule"] == "A10" for a in cp.list_alerts(st)), "A10 경보가 안 남았다"


def test_A1_키공유_국가2_경고_다음엔_정지(env):
    c, st = env["client"], env["store"]
    k = _key(env)
    assert c.get("/api/claude/license", headers=_h(k, FP1, country="KR")).status_code == 200
    r2 = c.get("/api/claude/license", headers=_h(k, FP1, country="US"))
    assert r2.status_code == 200, "1회째는 경고만(VPN 거짓 양성 대비)"
    al = [a for a in cp.list_alerts(st) if a["rule"] == "A1"]
    assert len(al) == 1 and al[0]["level"] == "warn"
    r3 = c.get("/api/claude/license", headers=_h(k, FP1, country="US"))
    assert r3.status_code == 403 and r3.json()["code"] == "suspended"
    r4 = c.post("/api/claude/lease", headers=_h(k, FP1), json={"action": "acquire", "job_id": "j1"})
    assert r4.status_code == 403 and r4.json()["code"] == "suspended", "정지 중에는 작업 권한도 거절"
    # 관리자가 정지 경보를 풀면 다시 된다(정지는 사람이 푼다)
    sus = next(a for a in cp.list_alerts(st) if a["level"] == "suspend")
    assert c.post("/api/admin/claude/alerts/resolve", json={"id": sus["id"]}).json()["unsuspended"]
    with cp._tx(st, write=True) as con:
        con.execute("DELETE FROM claude_license_log")
    assert c.get("/api/claude/license", headers=_h(k, FP1, country="KR")).status_code == 200
    assert c.get("/api/admin/claude/alerts?all=1").json()["alerts"]


def test_회수된_키_반복은_A6_경보(env):
    c, st = env["client"], env["store"]
    k1 = _key(env)
    _key(env)
    for _ in range(3):
        assert c.get("/api/claude/license", headers=_h(k1)).json()["code"] == "revoked"
    assert any(a["rule"] == "A6" for a in cp.list_alerts(st))


def test_로그_1년_보관_정리(env):
    st = env["store"]
    with cp._tx(st, write=True) as con:
        con.execute("INSERT INTO claude_license_log(ts, cid, kind) VALUES(?,?,?)", (cp._now() - 400 * 86400, 0, "request"))
        con.execute("INSERT INTO claude_license_log(ts, cid, kind) VALUES(?,?,?)", (cp._now(), 0, "request"))
    assert cp.prune_logs(st)["license_log"] == 1


# ── 견본 규격 검사 도구 ──────────────────────────────────────────────────
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_check_previews_기준밖_견본을_잡는다(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_previews", ROOT / "tools" / "claude_portal" / "check_previews.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    d = tmp_path / "preview" / "sfx"
    d.mkdir(parents=True)
    good, bad = d / "good.mp3", d / "bad.mp3"
    ff = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi"]
    subprocess.run(ff + ["-i", "sine=f=500:d=1.5", "-ac", "1", "-b:a", "64k", str(good)], check=True)
    subprocess.run(ff + ["-i", "sine=f=500:d=3", "-ac", "2", "-b:a", "192k", str(bad)], check=True)
    for f in (good, bad):
        f.with_suffix(".json").write_text(json.dumps({"made_by": "preview v1"}), encoding="utf-8")
    total, fails = mod.run(tmp_path)
    assert total == {"sfx": 2}
    assert [n for n, _ in fails] == ["sfx/bad.mp3"], fails
    errs = fails[0][1]
    assert any("길이" in e for e in errs) and any("채널" in e for e in errs) and any("비트레이트" in e for e in errs)


def test_merge_keeps_ad_disclosure():
    """채널명을 넣어도 brand 자리의 광고 표시("[광고]")는 남는다 — 진짜 채널명 자리만 바뀐다."""
    from shopping_shorts import channel_profile
    frame = {"canvas": [1080, 1920], "layers": [
        {"kind": "text", "role": "brand", "text": "[광고]"},
        {"kind": "text", "role": "brand", "text": "썰풀다"},
        {"kind": "text", "role": "caption", "text": "썰풀다 구독"}]}
    out = channel_profile.merge({"frame": frame}, {}, {"brand": {"channel_name": "내채널"}})
    texts = [L.get("text") for L in out["frame"]["layers"]]
    assert texts[0] == "[광고]"
    assert texts[1] == "내채널"
    assert texts[2] == "내채널 구독"


def test_merge_blanks_bench_label_text():
    """벤치 영상에서 읽은 고정 글(게시글 제목)은 비우고 fill=title 표식 — 채널명 든 글은 채널명만 바뀐다."""
    from shopping_shorts import channel_profile
    frame = {"canvas": [1080, 1920], "frames": [{"id": "body", "layers": [
        {"kind": "text", "role": "brand", "text": "방구"},
        {"kind": "text", "role": "label", "text": "아웃백이 끝까지 안 내놓은 영업기밀"},
        {"kind": "text", "role": "label", "text": "방구 | 14:25"},
        {"kind": "text", "role": "label", "text": "»"}]}]}
    out = channel_profile.merge({"frame": frame}, {}, {"brand": {"channel_name": "내채널"}})
    L = out["frame"]["frames"][0]["layers"]
    assert L[1]["text"] is None and L[1]["fill"] == "title"
    assert L[2]["text"] == "내채널 | 14:25"
    assert L[3]["text"] == "»"
    assert any("label" in p for p in out["per_video"])


def test_rent_편마다_잠근_꾸러미_풀면_원본과_같다(env):
    """편마다 프리셋 빌려주기(관제 234 5판) — 관문(작업 권한·구매) 뒤 잠근 꾸러미, 그 편 열쇠로만 풀린다."""
    import base64, hashlib, io, zipfile
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    c = env["client"]
    k = _two_devices(env)
    pid = _profile(env)
    body = {"profile": pid, "job": "j1"}
    assert c.post("/api/claude/rent", headers=_h(k), json=body).json()["code"] == "lease_lost"   # 작업 권한 없음
    lid = c.post("/api/claude/lease", headers=_h(k), json={"action": "acquire", "job_id": "j1"}).json()["lease_id"]
    body["lease"] = lid
    assert c.post("/api/claude/rent", headers=_h(k), json=body).json()["code"] == "not_ready"    # 꾸러미 아직 없음
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("channel/benchslug/preset/A_흰바탕창/창아래_검정/frame.json", '{"layers":[]}')
    data = buf.getvalue()
    f = cp.preset_pack_path(env["preset"])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)
    assert c.post("/api/claude/rent", headers=_h(k, FP2), json=body).json()["code"] == "lease_lost"   # 다른 기기
    assert c.post("/api/claude/rent", headers=_h(k), json={**body, "job": "j9"}).json()["code"] == "lease_lost"
    r = c.post("/api/claude/rent", headers=_h(k), json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["preset_path"] == "channel/benchslug/preset/A_흰바탕창/창아래_검정"
    blob = base64.b64decode(d["pack"])
    assert data not in blob, "꾸러미가 잠기지 않은 채 나갔다"
    plain = AESGCM(base64.b64decode(d["key"])).decrypt(blob[:12], blob[12:], d["aad"].encode())
    assert plain == data and hashlib.sha256(plain).hexdigest() == d["sha256"]
    import pytest
    with pytest.raises(Exception):   # 덧붙임 글(cid|job)이 다르면 같은 열쇠로도 못 푼다 — 다른 편에 재사용 불가
        AESGCM(base64.b64decode(d["key"])).decrypt(blob[:12], blob[12:], d["aad"].replace("j1", "j2").encode())
    d2 = c.post("/api/claude/rent", headers=_h(k), json=body).json()
    assert d2["key"] != d["key"], "요청마다 새 열쇠여야 한다"
    env["monkeypatch"].setattr(cp, "_entitled", lambda *a, **kw: set())   # 등급이 내려간 회원
    assert c.post("/api/claude/rent", headers=_h(k), json=body).json()["code"] == "not_entitled"
    with cp._tx(env["store"]) as con:
        n = con.execute("SELECT COUNT(*) FROM claude_lease_log WHERE action='rent'").fetchone()[0]
    assert n == 2


def test_rent_로컬설정은_프리셋id로_빌리고_이름목록은_관리자설정(env):
    """PC 로컬 설정(관제 234 5판) — 서버 프로필 없이 고객용 프리셋 id 로 빌린다. 이름은 claude_preset_names, 없으면 틀 설명."""
    import json as _json
    c = env["client"]
    k = _two_devices(env)
    lic = c.get("/api/claude/license", headers=_h(k)).json()
    assert lic["presets"] == [{"id": env["preset"], "name": "흰바탕창 · 창아래 검정", "desc": ""}]
    assert "benchslug" not in _json.dumps(lic["presets"]), "벤치 slug 가 이름에 새면 안 된다"
    env["store"].set_setting("claude_preset_names", _json.dumps({"benchslug/A_흰바탕창/창아래_검정": {"name": "제품비하인드썰형", "desc": "뒷이야기 썰"}}))
    assert c.get("/api/claude/license", headers=_h(k)).json()["presets"][0]["name"] == "제품비하인드썰형"
    lid = c.post("/api/claude/lease", headers=_h(k), json={"action": "acquire", "job_id": "j1"}).json()["lease_id"]
    f = cp.preset_pack_path(env["preset"])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"PK-test")
    r = c.post("/api/claude/rent", headers=_h(k), json={"preset": env["preset"], "job": "j1", "lease": lid})
    assert r.status_code == 200 and r.json()["sha256"], r.text
    assert c.post("/api/claude/rent", headers=_h(k), json={"preset": "p_0000000000", "job": "j1", "lease": lid}).json()["code"] == "not_entitled"
    assert c.post("/api/claude/rent", headers=_h(k), json={"job": "j1", "lease": lid}).json()["code"] == "bad_request"
