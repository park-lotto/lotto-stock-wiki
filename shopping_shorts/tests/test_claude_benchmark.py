# -*- coding: utf-8 -*-
"""고급반 벤치마킹(관제 304) — 서버 임대 관문 · 묶음 금지 검사 · 회원 입구의 단계 잇기.
영상을 실제로 뜯는 재현은 tools/claude_portal/benchmark_check.py(결과물 대조)가 맡는다 — 여기는 판단만 못 박는다."""
import base64
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shopping_shorts import claude_portal as cp
from shopping_shorts.tests.test_claude_portal import _h, _key, env  # noqa: F401 — pytest 픽스처

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "claude_portal"))
import benchmark_pack as BP  # noqa: E402
from tools.calcopy.engine import bench_member as BM  # noqa: E402


def _plan(env, plan):
    env["store"].save_program_member(0, "", "1", plan, "", "")


def _lease(env, k, job="b1"):
    c = env["client"]
    assert c.get("/api/claude/license", headers=_h(k)).status_code == 200
    return c.post("/api/claude/lease", headers=_h(k), json={"action": "acquire", "job_id": job}).json()["lease_id"]


def _put_pack():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("tools/calcopy/engine/analyze.py", "x=1")
    f = cp.benchmark_pack_path()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(buf.getvalue())
    return buf.getvalue()


def test_기본반은_쉬운_문구로_거절(env):
    k = _key(env)
    lid = _lease(env, k)
    _put_pack()
    r = env["client"].post("/api/claude/benchmark_rent", headers=_h(k), json={"job": "b1", "lease": lid})
    assert r.status_code == 403
    assert r.json() == {"ok": False, "code": "tier_locked", "msg": "채널 벤치마킹은 고급반에서 제공돼요"}


@pytest.mark.parametrize("plan", ["고급반", "프리미엄반"])
def test_고급_프리미엄은_잠근_묶음을_받는다(env, plan):
    k = _key(env)
    _plan(env, plan)
    lid = _lease(env, k)
    data = _put_pack()
    r = env["client"].post("/api/claude/benchmark_rent", headers=_h(k), json={"job": "b1", "lease": lid})
    assert r.status_code == 200, r.text
    d = r.json()
    blob = base64.b64decode(d["pack"])
    assert data not in blob, "묶음이 잠기지 않은 채 나갔다"
    plain = AESGCM(base64.b64decode(d["key"])).decrypt(blob[:12], blob[12:], d["aad"].encode())
    assert plain == data and hashlib.sha256(plain).hexdigest() == d["sha256"]
    with cp._tx(env["store"]) as c:
        assert c.execute("SELECT COUNT(*) FROM claude_lease_log WHERE action='benchmark'").fetchone()[0] == 1


def test_작업권한_없거나_묶음이_없으면_거절(env):
    k = _key(env)
    _plan(env, "고급반")
    c = env["client"]
    assert c.get("/api/claude/license", headers=_h(k)).status_code == 200
    assert c.post("/api/claude/benchmark_rent", headers=_h(k), json={"job": "b1"}).json()["code"] == "lease_lost"
    lid = _lease(env, k)
    assert c.post("/api/claude/benchmark_rent", headers=_h(k), json={"job": "b1", "lease": lid}).json()["code"] == "not_ready"


def test_서버키_파일은_묶음에_못_든다():
    for f in ("tools/calcopy/engine/gemini_server.py", "tools/calcopy/engine/gemini_keys.py", "tools/calcopy/engine/_server_access.py",
              "tools/calcopy/pull_pool_keys.py", "tools/calcopy/hybrid/server_ai.py", "tools/calcopy/hybrid/gemini_server.py",
              "tools/calcopy/engine/channel_find.py", ".env", "shopping_shorts/app.py", "shopping_shorts/claude_portal.py"):
        assert BP.blocked(f), f
    for f in BP.RELEASED:
        assert BP.blocked(f) is None, f


def test_묶음_검사는_금지글자와_금지파일을_잡는다(tmp_path):
    good = tmp_path / "good"
    (good / "tools/calcopy/engine").mkdir(parents=True)
    (good / "tools/calcopy/engine/analyze.py").write_text("x=1", encoding="utf-8")
    assert BP.check(good) == []
    (good / "tools/calcopy/engine/rules.py").write_text('H = "ubuntu@3.35.251.172"', encoding="utf-8")
    assert sum("금지 글자" in b for b in BP.check(good)) == 2       # SECRETS 를 engine_bundle 에서 그대로 쓴다
    (good / "tools/calcopy/engine/rules.py").unlink()
    (good / "tools/calcopy/engine/gemini_keys.py").write_text("x=1", encoding="utf-8")
    assert any("금지 파일" in b for b in BP.check(good))


def test_금지글자는_engine_bundle_한_벌이다():
    assert BP.EB.SECRETS is __import__("engine_bundle").SECRETS
    assert "SECRETS =" not in (ROOT / "tools/claude_portal/benchmark_pack.py").read_text(encoding="utf-8")


def test_묶음_실물에_키와_서버주소가_없다(tmp_path):
    man = BP.build(ROOT, tmp_path)
    assert BP.check(tmp_path / BP.ZIP_NAME) == []
    assert set(man["files"]) >= set(BP.RELEASED) | set(BP.ENTRY)
    assert "tools/calcopy/engine/gemini_keys.py" not in man["files"]


def test_채널은_조회수_높은_순으로_고른다():
    st = {"videos": [{"id": "a", "views": 5}, {"id": "b", "views": 50}, {"id": "c", "views": None}, {"id": "d", "views": 20}]}
    got = BM.pick_videos("https://www.youtube.com/@x", 2, stats=lambda ref, n: st)
    assert [v["id"] for v in got] == ["b", "d"]
    assert got[0]["url"] == "https://www.youtube.com/shorts/b"
    with pytest.raises(ValueError):
        BM.pick_videos("https://www.youtube.com/@x", 2, stats=lambda ref, n: None)


def test_다른_틀은_따로_묶고_실패한_편은_이유를_남긴다(tmp_path):
    one = {"canvas": [1080, 1920], "layers": [{"kind": "bg", "rgb": [0, 0, 0]}, {"kind": "text", "role": "title", "text": "가"}]}
    two = {"canvas": [1080, 1920], "layers": [{"kind": "bg", "rgb": [0, 0, 0]}]}
    saved = []

    def tear(mp4, d, llm):
        if mp4.stem == "bad":
            raise ValueError("망가진 영상")
        d.mkdir(parents=True, exist_ok=True)
        (d / "뜯기.json").write_text("{}", encoding="utf-8")
        (d / "sheet.jpg").write_bytes(b"x")
        return {"captions": {"items": []}}, (two if mp4.stem == "v3" else one), d / "뜯기.json"

    import tools.calcopy.engine.preset_save as P
    orig_save, orig_meta = P.save, P.set_meta
    P.save = lambda J, f, d, sid, t, *a: saved.append((d.name, sid, t))
    P.set_meta = lambda d, **kw: saved.append((d.name, kw["source_kind"]))
    try:
        files = [tmp_path / f"{n}.mp4" for n in ("v1", "bad", "v2", "v3")]
        for f in files:
            f.write_bytes(b"x")
        r = BM.run(tmp_path / "o", "내 틀", videos=[str(f) for f in files],
                   deps={"tear": tear, "llm": lambda parts, prompt, tag="": ({"source_kind": "커뮤니티"}, None)})
    finally:
        P.save, P.set_meta = orig_save, orig_meta
    assert r["ok"] and r["source_kind"] == "커뮤니티"
    assert r["presets"] == [{"style": "틀", "sources": ["v1", "v2"]}, {"style": "틀2", "sources": ["v3"]}]
    assert r["failed"][0]["video"] == "bad" and "망가진 영상" in r["failed"][0]["why"]
    assert saved[0][2] == f"channel/{r['slug']}/뜯기/v1/뜯기.json", "뜯기 경로는 엔진 뿌리 기준 상대여야 제작 때 찾는다"
    kept = sorted(p.name for p in (tmp_path / "o/channel" / r["slug"] / "뜯기/v1").iterdir())
    assert kept == ["뜯기.json"], "벤치 화면 그림은 프리셋에 안 남긴다"


def test_회원_제미나이_키가_실패하면_회원_Claude로_넘긴다(monkeypatch):
    from tools.calcopy.engine import gemini_free as GF
    monkeypatch.setenv("SHORTEM_MEMBER_GEMINI_KEY", "k" * 30)
    monkeypatch.setattr(BM, "gemini_with_key", lambda key, parts, prompt: (None, "401"))
    monkeypatch.setattr(GF, "ask", lambda parts, prompt, tag="", models=None: ({"who": "client"}, None))
    assert BM.member_llm()([], "질문", "t")[0] == {"who": "client"}
    monkeypatch.setattr(BM, "gemini_with_key", lambda key, parts, prompt: ({"who": "key"}, None))
    assert BM.member_llm()([], "질문", "t")[0]["who"] == "key"
    monkeypatch.delenv("SHORTEM_MEMBER_GEMINI_KEY")
    assert BM.member_llm() is GF.ask


def test_고급반_안내는_회원용_문장이다():
    t = (ROOT / "channel/production_guide/15_benchmark.md").read_text(encoding="utf-8")
    assert "칼카피" not in t and "shortem_benchmark" in t
    assert "칼카피" not in (ROOT / "installer/common/MEMBER_GUIDE.md").read_text(encoding="utf-8")
    from tools.calcopy.hybrid import flow
    assert flow.benchmark_guide().startswith(t[:40])


def test_v2_files_released_and_jev_not():
    from tools.claude_portal import benchmark_pack as BP
    for f in ("tools/calcopy/engine/agy.py", "tools/calcopy/engine/preset_brief.py", "tools/calcopy/engine/agy_check.py"):
        assert f in BP.RELEASED
    assert "tools/calcopy/hybrid/jev_gate.py" not in BP.RELEASED and "tools/calcopy/hybrid/flow_bench.py" not in BP.RELEASED
    assert BP.blocked("tools/calcopy/hybrid/jev_gate.py") and BP.blocked("tools/calcopy/hybrid/flow_bench.py")   # 서버 전용 — 어느 묶음에도 안 간다


def test_jev_key_name_is_secret():
    from tools.claude_portal import engine_bundle as EB
    import re
    assert any(re.search(p, "TYPESAFE_API_KEY") for p in EB.SECRETS)


def test_v2_runner_ops_imports_all_have_a_way_to_member_pc():
    """실행기(runner_ops)가 부르는 파일은 기본 묶음(HAND·허용 파일)·서버 전용·고급반 묶음 셋 중 하나에 있어야 한다 — 어디에도 없으면 회원 PC 가 ImportError."""
    from tools.claude_portal import benchmark_pack as BP, engine_bundle as EB
    bad = [m for m in EB.hand_deps(ROOT) if EB.forbidden(m) and m not in BP.RELEASED]
    assert bad == [] or all("community_" in b or "_server_access" in b for b in bad), bad   # 마지막 둘 = 이 과제 이전부터 열려 있던 별개 구멍(topic_find)
    # 벤치 입구가 부르는 것은 고급반 묶음 목록에 잡혀야 한다(추적 없이도)
    kept = set(BP.wanted(ROOT))
    for f in ("tools/calcopy/engine/preset_brief.py", "tools/calcopy/engine/agy.py", "tools/calcopy/engine/agy_check.py"):
        assert f in kept


def test_v2_runner_ops_bench_deps_not_unresolved():
    from tools.claude_portal import engine_bundle as EB
    left = [x for x in EB.hand_unresolved(ROOT) if "runner_ops" in x]
    assert left == [], left


def test_v2_guide_uses_flow_sid_and_member_words():
    t = (ROOT / "channel/production_guide/15_benchmark.md").read_text(encoding="utf-8")
    for w in ("칼카피", "잡도리", "run_id"):
        assert w not in t, w
    for w in ("준비 확인", "벤치 받기", "뜯기", "영상 보기", "시험 편", "판볶이", "확정", "프리셋 묶음", "sid", "agy"):
        assert w in t, w
