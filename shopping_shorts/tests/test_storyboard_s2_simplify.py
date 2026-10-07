# -*- coding: utf-8 -*-
"""2단계 스토리보드 단순화(장면배분, 2026-10-07 사장님 6가지).
① 씨앗 카드 줄·② 씨앗 대본 띠 숨김 ③ 1→2단계 씨앗 확인 ④ 스타일 카드 접기 ⑤ 문장·장면 초 다시 재기 ⑥ 장면 구간 미리보기.
전부 STORYBOARD_ON 켠 계정에서만 — 꺼진 계정 화면 불변."""
import json
import pathlib
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod, storyboard as sb
from shopping_shorts.edit_plan import narr_secs
from shopping_shorts.store import Store

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def _fn(name):
    """produce.html 에서 function name(...){...} 한 덩이를 괄호 짝으로 잘라 온다."""
    i = HTML.index("function %s(" % name)
    j = HTML.index("{", i)
    d = 0
    for k in range(j, len(HTML)):
        d += {"{": 1, "}": -1}.get(HTML[k], 0)
        if d == 0:
            return HTML[i:k + 1]
    raise AssertionError(name)


# ── ①② 씨앗 줄·띠 숨김은 STORYBOARD_ON 일 때만 ──
def test_씨앗띠는_켠계정만_숨김():
    assert 'id="s2SeedBand"' in HTML and 'id="s2SeedRow"' in HTML and 'id="s2SeedInfo"' in HTML
    band = HTML[HTML.index('id="s2SeedBand"'):HTML.index('id="s2StyleBand"')]
    assert 'id="s2SeedRow"' in band and 'id="s2SeedInfo"' in band          # 줄·띠가 이 띠 안에 있다
    r = _fn("sbRender")
    assert "seedBand.style.display=window.STORYBOARD_ON?'none':''" in r
    assert r.index("seedBand") < r.index("if(!window.STORYBOARD_ON){ put(b1,null)")   # 꺼진 계정도 '' 로 되돌린다
    assert len(re.findall(r"getElementById\('s2SeedBand'\)", HTML)) == 1               # 주인 하나


# ── ③ 1→2단계 씨앗 확인 — jump 를 그대로 잘라 node 로 돌린다 ──
def _run_jump(sb_on, handoff):
    js = "\n".join([
        "var window={STORYBOARD_ON:%s, _aiPick:null}; var HANDOFF=%s; var S2={seed:null};" % ("true" if sb_on else "false", json.dumps(handoff)),
        "var ORB_TO_PANEL=[0,8,7,2,1,3,4,5,6,9]; var PANEL_TO_ORB={0:0,8:1,7:2}; var PANEL_BY_KEY={deco:3}; var cur=0; var shown=0;",
        "function stepLocked(){return false} function toast(){} function renderSteps(){} function showPanel(){} function saveWork(){}",
        "function _syncServerStep(){} function renderScriptDrift(){} function seedGateShow(){ shown++; }",
        _fn("_seedCode"), _fn("seedPicked"), _fn("jump"),
        "jump(1); console.log(JSON.stringify({cur:cur, shown:shown}));",
    ])
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_씨앗_안고르면_못넘어감():
    h = [{"shortcode": "a", "useFootage": True}, {"shortcode": "b", "useFootage": True}]
    assert _run_jump(True, h) == {"cur": 0, "shown": 1}                       # 안 골랐다 → 멈추고 안내창
    h[1]["bbMain"] = True
    assert _run_jump(True, h) == {"cur": 8, "shown": 0}                       # 골랐다 → 2단계
    assert _run_jump(False, [{"shortcode": "a", "useFootage": True}]) == {"cur": 8, "shown": 0}   # 꺼진 계정 불변


def test_씨앗안내는_브라우저창_아님():
    g = _fn("seedGateShow")
    assert "alert(" not in g and "confirm(" not in g and "seedGateModal" in g


# ── ④ 스타일 카드: 기본은 이름·추천·체크, 나머지는 자세히 / 다른 스타일 더 보기 ──
def test_스타일카드_접기():
    c = _fn("sbFamCard")
    assert "▸ 자세히" in c
    body = c[c.index("return `"):]
    assert "${first}" not in body[:body.index("▸ 자세히")] and "sb-fit" not in body[:body.index("▸ 자세히")]
    assert body.index("${SB.openf[k]?`<div class=\"sb-fit\">") > body.index("▸ 자세히")       # 태그·후킹·구조는 펼친 안에
    p2 = _fn("sbPage2")
    assert "다른 스타일 '+rest.length+'개 더 보기" in p2 and "sbRestOpen()" in p2
    assert "localStorage" in _fn("sbRestOpen") and "try{" in _fn("sbRestToggle")


# ── ⑤ 문장·장면 초 — 서버 한 함수(storyboard.slot_checks)로 다시 잰다 ──
def test_slot_checks_한함수():
    segs = {"a": 1.5, "b": 2.0}
    ck = sb.slot_checks([{"line": "가나다라마바사아자차카타파하" * 2, "ids": ["a", "b"]}, {"line": "짧아", "ids": ["a", "zz"]}], segs)
    assert ck[0]["have"] == 3.5 and ck[0]["need"] == round(narr_secs("가나다라마바사아자차카타파하" * 2), 1)
    assert ck[1]["dup_ids"] == ["a"] and ck[1]["bad_ids"] == ["zz"]
    src = pathlib.Path(sb.__file__).read_text(encoding="utf-8")
    assert src.count('"have": round(sum(segs.get(') == 1                     # 계산이 한 벌


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    st = Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(app_mod, "_sb_gate", lambda req: None)
    ex = {"v1": {"segments": [{"seg_id": "v1-0", "start": 0.0, "end": 1.0}, {"seg_id": "v1-1", "start": 1.0, "end": 2.5},
                              {"seg_id": "v1-2", "start": 2.5, "end": 4.0}]}}
    monkeypatch.setattr(app_mod, "_extract_from_work", lambda wid, cid, st_: json.loads(json.dumps(ex)))
    return st, TestClient(app_mod.app), tmp_path


def test_picks가_초를_다시잰다(env):
    st, c, _ = env
    wid = st.upsert_produce_work(None, {"script": "x"}, customer_id=0)
    line = "이거 하나로 떼돈 번 사람이 있어요 정말로요"
    r = c.post("/api/produce/storyboard/w:%s/picks" % wid, json={"slots": [{"slot": "hook", "line": line, "ids": ["v1-0"]}]}).json()
    assert r["check"][0]["have"] == 1.0 and r["check"][0]["need"] == round(narr_secs(line), 1)
    r = c.post("/api/produce/storyboard/w:%s/picks" % wid, json={"slots": [{"slot": "hook", "line": line, "ids": ["v1-0", "v1-1"]}]}).json()
    assert r["check"][0]["have"] == 2.5                                       # 카드를 넣으면 장면 초가 바뀐다


def test_화면이_고칠때마다_picks로_다시잰다():
    for f in ("sbRowMove", "sbRowDel", "sbRowAdd"):
        assert "sbPicksSync(ek,bd)" in _fn(f), f
    for f in ("sbMv", "sbRmCard", "sbAddCand"):
        assert "sbResync(ek)" in _fn(f), f
    ps = _fn("sbPicksSync")
    assert "ids:sbLiveIds(ek,k,x)" in ps and "line:sbLine(ek,k,x)" in ps and "bd.check=r.check" in ps
    assert 'onblur="sbEditDone()"' in HTML


# ── ⑥ 장면 구간 미리보기 ──
def test_카드크게_누르면_재생():
    cc = _fn("sbCellCards")
    assert "sbTh(id,120)" in cc and "sbClipV(id,120)" in cc and "sbPlay(" in cc
    assert "sbMv(" in cc and "sbRmCard(" in cc                                 # ◀▶✕ 그대로
    v = _fn("sbClipV")
    assert "muted" in v and "loop" in v and "/api/produce/storyboard/clip/" in v and 'loading="lazy"' not in v


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_clip_라우트_구간길이와_남의작업(env, monkeypatch):
    st, c, tmp = env
    find = tmp / "find"
    monkeypatch.setattr(app_mod, "_FIND_TMP_DIR", find)
    monkeypatch.setattr(app_mod, "_SB_CLIP_DIR", tmp / "clips")
    import hashlib
    vdir = find / hashlib.sha1(b"v1").hexdigest()[:16]
    vdir.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=180x320:rate=30:duration=4",
                    "-pix_fmt", "yuv420p", str(vdir / "src.mp4")], check=True, timeout=60)
    wid = st.upsert_produce_work(None, {"script": "x"}, customer_id=0)
    r = c.get("/api/produce/storyboard/clip/w-%s/v1-1" % wid)
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4"
    out = tmp / "got.mp4"
    out.write_bytes(r.content)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout.strip())
    assert abs(dur - 1.5) < 0.15, dur                                          # 조각 1.0~2.5 만
    other = st.upsert_produce_work(None, {"script": "x"}, customer_id=77)
    assert c.get("/api/produce/storyboard/clip/w-%s/v1-1" % other).status_code == 404     # 남의 작업
    assert c.get("/api/produce/storyboard/clip/w-%s/..%%2Fetc" % wid).status_code == 404  # 없는 조각·경로 조작
