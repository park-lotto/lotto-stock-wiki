# -*- coding: utf-8 -*-
"""자막 시각·인트로 판단의 주인 함수 하나 (2026-09-27, CLAUDE.md 0순위-B/C).

① 자막 시간표 주인 = video_assemble.caption_schedule(absorb_lead=caption_lead_absorb(deco)) — 통로가 같은 시작 시각(±0.02):
   A 3단계 편집 화면 app._lab_captions(plan, deco) + 표시 off(scene_play.js capAt)
   B 렌더 drawtext(장면꾸미기 없는 job) · C 캡컷 caption_schedule 호출 · D 4단계 음성 미리보기(produce.html JS 를 node 로)
   E 장면꾸미기 렌더·6단계 편집기 scene_style.context_for
② 칸 앞 틈: 장면꾸미기 job 은 < 0.35초면 첫 자막이 칸 시작(전 통로), drawtext job 은 cap_lead. 0.35초 이상은 안 붙음.
③ 인트로 판단 = mix_pipeline._intro_choice — (켜짐, 실제 파일|None, 길이 기본 1.2) · 도장은 파일 크기·시각까지 ·
   CTA 폴백은 붙었을 때만 민다 · run_render 는 켰는데 그림 없으면 렌더 전에 경보(intro_missing:<job>)하고 계속한다.
통로별 사보타주: CAP_OWNER_PATCH=<폴더> 의 변형 video_assemble.py·scene_style.py·mix_pipeline.py·app.py(_lab_captions)·
produce.html·capcut_draft.py 를 쓴다.
"""
import os
import re
import subprocess
import sys
import json
import importlib.util
from pathlib import Path

import pytest

_P = os.getenv("CAP_OWNER_PATCH")
if _P:
    import shopping_shorts
    for _n in ("video_assemble", "scene_style", "mix_pipeline"):
        _f = Path(_P) / ("%s.py" % _n)
        if _f.exists():
            _sp = importlib.util.spec_from_file_location("shopping_shorts." + _n, str(_f))
            _m = importlib.util.module_from_spec(_sp)
            sys.modules["shopping_shorts." + _n] = _m
            _sp.loader.exec_module(_m)
            setattr(shopping_shorts, _n, _m)

from shopping_shorts import video_assemble as va      # noqa: E402
from shopping_shorts import scene_style                # noqa: E402
from shopping_shorts import mix_pipeline as mp         # noqa: E402
from shopping_shorts import app                        # noqa: E402

if _P and (Path(_P) / "app.py").exists():
    _src = (Path(_P) / "app.py").read_text(encoding="utf-8")
    _i = _src.index("def _lab_captions(")
    _j = _src.index("\n@app.", _i)
    exec(compile(_src[_i:_j], "patched_app", "exec"), app.__dict__)

PRODUCE = (Path(_P) / "produce.html") if (_P and (Path(_P) / "produce.html").exists()) \
    else Path(app.__file__).parent / "static" / "produce.html"

TOL = 0.02


SS = {"scene_style": {"presetId": "t11", "mode": "story"}}    # 장면꾸미기 켠 job 의 deco


def _make_plan(tmp_path, monkeypatch, leads=(0.30, 0.25, 0.0), offs=(0.0, 0.2, 0.0)):
    """칸 3개: ① 앞 틈 leads[0] ② 자막 옮김(cap_offset) ③ 실측 없음(글자수 비례 + 하한)."""
    durs = {}
    beats = []
    spec = [
        ("이거 진짜 대박이에요", ["이거 진짜", "대박이에요"], [0.9, 1.1], 2.5),
        ("여러분도 한번 써보세요", ["여러분도", "한번 써보세요"], [0.8, 1.2], 2.6),
        ("와 진짜 이거 하나로 끝", ["와", "진짜", "이거 하나로 끝"], None, 2.9),
    ]
    for i, ((narr, lines, cd, dur), lead, off) in enumerate(zip(spec, leads, offs)):
        p = tmp_path / ("beat_%d.mp3" % i)
        p.write_bytes(b"\0")
        durs[str(p)] = dur
        b = {"beat_idx": i, "narration": narr, "caption_lines": lines, "cap_lead": lead,
             "tts_path": str(p), "role": "body", "cap_offset": off}
        if cd:
            b["cap_durs"] = cd
        beats.append(b)
    monkeypatch.setattr(va, "_probe_duration", lambda path: durs.get(str(path), 0.0))
    return {"beats": beats}


@pytest.fixture
def plan(tmp_path, monkeypatch):
    return _make_plan(tmp_path, monkeypatch)


def _tl(plan):
    return va._beat_timeline(plan, {b["beat_idx"]: b["tts_path"] for b in plan["beats"]})


def _expected(plan, deco):
    """정답 = caption_schedule(주인) — 칸 기준 구절 시작초(cap_offset 포함)."""
    tl = _tl(plan)
    ab = va.caption_lead_absorb(deco)
    return {b["beat_idx"]: [a - b["t0"] for _s, a, _e in va.caption_schedule(b, absorb_lead=ab)] for b in tl}, tl


def _assert_same(got, exp, label):
    for bi, starts in exp.items():
        g = got.get(bi) or []
        assert len(g) == len(starts), f"{label} 칸{bi} 구절 수 {len(g)} ≠ {len(starts)}"
        for k, (x, y) in enumerate(zip(g, starts)):
            assert abs(x - y) <= TOL, f"{label} 칸{bi} 구절{k} 시작 {x:.3f} ≠ 주인 {y:.3f}"


def _lab(plan, deco):
    caps, _td = app._lab_captions(plan, deco)
    return {int(k): [float(r["start"]) + float(r.get("off") or 0) for r in rows] for k, rows in caps.items()}


def _drawtext(plan, tmp_path):
    got = {}
    for b in _tl(plan):
        parts = va._caption_drawtexts(b["narration"], b["dur"], tmp_path, b["beat_idx"], b["t0"], {},
                                      real_durs=b.get("cap_durs"), cap_offset=b.get("cap_offset", 0.0),
                                      tail=0.0, cap_lines=b.get("caption_lines"), lead_in=b.get("cap_lead", 0.0))
        seen = {}
        for p in parts:
            m = re.search(r"txt_cap_(\d+)_(\d+)_", p)
            e = re.search(r"between\(t,([-\d.]+),([-\d.]+)\)", p)
            if m and e:
                seen.setdefault(int(m.group(2)), float(e.group(1)) - b["t0"])
        got[b["beat_idx"]] = [seen[k] for k in sorted(seen)]
    return got


def _js_funcs():
    src = PRODUCE.read_text(encoding="utf-8")
    i = src.index("function _vpCapRows(") if "function _vpCapRows(" in src else src.index("function _vpCapDurs(")
    j = src.index("function vpPlayBeat(")
    return src[i:j]


def _vp(plan, deco):
    """4단계 음성 미리보기 — api_mix_result 가 싣는 값({**beat, cap_segments, cap_rows})을 실제 JS 에 넣고 재생 시각을 훑는다."""
    beats = []
    for b in plan["beats"]:
        d = va._probe_duration(b["tts_path"])
        rows, _d = va.caption_rows(b, d, absorb_lead=va.caption_lead_absorb(deco))
        beats.append({**b, "cap_segments": va._caption_segments(b["narration"], preset=b.get("caption_lines")),
                      "cap_rows": rows, "_dur": d})
    js = _js_funcs() + r"""
const beats = JSON.parse(process.argv[1]); const out = {};
for (const b of beats){
  const cap = {textContent: ''}; global.document = {getElementById: () => cap};
  const aud = {currentTime: 0, duration: b._dur}; _vpDriveCaption(aud, b);
  const firsts = []; let prev = null;
  for (let t = 0; t <= b._dur + 1e-9; t += 0.005){
    aud.currentTime = t; aud.ontimeupdate();
    if (cap.textContent && cap.textContent !== prev){ firsts.push(+t.toFixed(3)); prev = cap.textContent; }
  }
  out[b.beat_idx] = firsts;
}
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js, json.dumps(beats, ensure_ascii=False)], capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-800:]
    return {int(k): v for k, v in json.loads(r.stdout.strip().splitlines()[-1]).items()}


def _scene(plan):
    tl = _tl(plan)
    ctx = scene_style.context_for(tl, {"text": "제목"}, None, "t")
    t0 = {b["beat_idx"]: b["t0"] for b in tl}
    got = {}
    for sc in ctx["scenes"]:
        if sc["caption"]:
            got.setdefault(sc["beat_idx"], []).append(float(sc["start"]) - t0[sc["beat_idx"]])
    return got, ctx


# 장면꾸미기 job — 첫 자막이 칸 시작부터(모든 통로)
def test_ss_A_lab(plan):
    exp, _ = _expected(plan, SS)
    assert exp[0][0] == pytest.approx(0.0), "주인이 앞 틈(0.30)을 안 붙였다"
    assert exp[1][0] == pytest.approx(0.45), "칸2 틈 = 리드 0.25 + 옮김 0.2 = 0.45 ≥ 0.35 → 안 붙는다(보이는 시각 기준)"
    _assert_same(_lab(plan, SS), exp, "3단계 화면(장면꾸미기)")


def test_ss_D_voice_preview(plan):
    exp, _ = _expected(plan, SS)
    _assert_same(_vp(plan, SS), exp, "4단계 음성 미리보기(장면꾸미기)")


def test_ss_E_scene_style_render_and_editor(plan):
    exp, _ = _expected(plan, SS)
    got, ctx = _scene(plan)
    _assert_same(got, exp, "장면꾸미기 렌더·6단계 편집기")
    empties = [s for s in ctx["scenes"] if not s["caption"]]
    assert all(s["end"] - s["start"] >= scene_style._TINY_GAP - 1e-6 for s in empties), f"0.35초 미만 빈 장면(빈 띠): {empties}"


# drawtext job — 말 시작(cap_lead)부터
def test_dt_A_lab(plan):
    exp, _ = _expected(plan, {})
    assert exp[0][0] == pytest.approx(0.30), "drawtext job 인데 앞 틈을 붙였다"
    _assert_same(_lab(plan, {}), exp, "3단계 화면(drawtext)")


def test_dt_B_drawtext(plan, tmp_path):
    exp, _ = _expected(plan, {})
    _assert_same(_drawtext(plan, tmp_path), exp, "렌더 drawtext")


def test_dt_C_capcut_schedule(plan):
    exp, tl = _expected(plan, {})
    got = {b["beat_idx"]: [a - b["t0"] for _s, a, _e in va.caption_schedule(b, tail=0.5)] for b in tl}
    _assert_same(got, exp, "캡컷(drawtext)")


def test_dt_D_voice_preview(plan):
    exp, _ = _expected(plan, {})
    _assert_same(_vp(plan, {}), exp, "4단계 음성 미리보기(drawtext)")


def test_absorb_boundary(tmp_path, monkeypatch):
    """0.35초 이상 틈은 안 붙는다(진짜 무음) — 0.34 는 붙는다. 3단계 화면·장면꾸미기 둘 다."""
    p = _make_plan(tmp_path, monkeypatch, leads=(0.34, 0.36, 0.0), offs=(0.0, 0.0, 0.0))
    exp, _ = _expected(p, SS)
    assert exp[0][0] == pytest.approx(0.0) and exp[1][0] == pytest.approx(0.36)
    _assert_same(_lab(p, SS), exp, "3단계 화면(경계)")
    got, ctx = _scene(p)
    _assert_same(got, exp, "장면꾸미기(경계)")
    lead = [s for s in ctx["scenes"] if s["beat_idx"] == 1 and not s["caption"]]
    assert lead and lead[0]["end"] - lead[0]["start"] == pytest.approx(0.36), "0.36초 무음은 빈 장면으로 남아야 한다"


def test_callers_pass_job_deco():
    """화면 데이터를 만드는 곳이 job 의 꾸미기로 흡수분을 정한다(빠뜨리면 화면만 말 시작부터가 된다)."""
    import inspect
    assert '_lab_captions(plan, job.get("deco"))' in inspect.getsource(app.api_mix_scene_lab_data)
    assert 'caption_lead_absorb(job.get("deco"))' in inspect.getsource(app.api_mix_result)
    assert "caption_lead_absorb(" in inspect.getsource(scene_style.context_for)


def test_C_capcut_calls_owner():
    """캡컷 자막은 caption_schedule 을 **그 칸 그대로** 부른다(capcut_draft). 장면꾸미기 job 은 캡컷도 context_for 레이어."""
    f = (Path(_P) / "capcut_draft.py") if (_P and (Path(_P) / "capcut_draft.py").exists()) \
        else Path(app.__file__).parent / "capcut_draft.py"
    assert "caption_schedule(tl, tail=_tail)" in f.read_text(encoding="utf-8")


# ── ③ 인트로 ────────────────────────────────────────────────────────────────

@pytest.fixture
def thumbs(tmp_path, monkeypatch):
    d = tmp_path / "thumbs"
    (d / "J1").mkdir(parents=True)
    monkeypatch.setattr(app, "_THUMB_DIR", d)
    return d / "J1"


def test_intro_choice_resolves_file_and_default_len(thumbs):
    (thumbs / "thumb_2.png").write_bytes(b"x" * 10)
    on, png, sec = mp._intro_choice({"intro": True, "selected": "thumb_2.png", "results": ["thumb_2.png"]}, "J1")
    assert on and png and png.name == "thumb_2.png" and sec == pytest.approx(1.2)
    on, png, sec = mp._intro_choice({"intro": True, "selected": "없음.png", "results": ["thumb_2.png"],
                                     "intro_sec": 2.0}, "J1")
    assert png.name == "thumb_2.png" and sec == 2.0, "고른 파일이 없으면 마지막 결과"
    assert mp._intro_choice({"intro": True, "results": []}, "J1")[1] is None
    assert mp._intro_choice({"intro": False, "selected": "thumb_2.png"}, "J1") == (False, None, None)
    assert mp.intro_notice({"intro": True, "results": []}, "J1") == mp.INTRO_MISSING_MSG
    assert mp.intro_notice({"intro": True, "selected": "thumb_2.png"}, "J1") is None


def test_stamp_sees_same_name_resave(thumbs):
    f = thumbs / "thumb_1.png"
    f.write_bytes(b"a" * 10)
    job = {"job_id": "J1", "thumbnail": {"intro": True, "selected": "thumb_1.png", "results": ["thumb_1.png"]}}
    before = mp._render_stamp(job)
    f.write_bytes(b"b" * 20)          # 같은 이름으로 다시 저장
    assert mp._render_stamp(job) != before, "같은 이름으로 다시 저장한 썸네일을 도장이 못 본다"


def test_cta_fallback_shifts_only_when_intro_attaches(thumbs, tmp_path, monkeypatch):
    durs = {}
    beats = []
    for i, role in enumerate(["body", "cta"]):
        p = tmp_path / ("c%d.mp3" % i)
        p.write_bytes(b"\0")
        durs[str(p)] = 2.0
        beats.append({"beat_idx": i, "narration": "말", "role": role, "tts_path": str(p)})
    monkeypatch.setattr(va, "_probe_duration", lambda path: durs.get(str(path), 0.0))
    job = {"job_id": "J1", "edit_plan": {"beats": beats}, "thumbnail": {"intro": True, "results": []}}
    cut_none, _ = app._cta_cut_for_job(job)
    (thumbs / "t.png").write_bytes(b"x")
    cut_on, _ = app._cta_cut_for_job(dict(job, thumbnail={"intro": True, "selected": "t.png"}))
    assert cut_none == pytest.approx(2.0), "켰어도 그림이 없으면 렌더가 안 붙였다 — 밀면 안 된다"
    assert cut_on == pytest.approx(3.2)


@pytest.fixture
def rjob(tmp_path, monkeypatch, thumbs):
    from shopping_shorts.store import Store
    db = str(tmp_path / "t.db")
    store = Store(db)
    store.create_mix_job("J1", ["https://x/1"], 20, "template")
    work = tmp_path / "work"
    tts_dir = work / "J1" / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    beat = {"beat_idx": 0, "narration": "비트", "primary": {"video_id": "v1", "start": 0, "end": 2}}
    beat["tts_path"] = mp._beat_tts_path(tts_dir, beat)
    open(beat["tts_path"], "w").write("m")
    store.update_mix_job("J1", edit_plan={"beats": [beat]}, status="ready_for_review")
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, w: {"v1": str(tmp_path / "v1.mp4")})
    monkeypatch.setattr(mp, "assemble", lambda plan, tts, srcs, out, **kw: Path(out).write_bytes(b"x") or out)
    return db, str(work), store


def test_run_render_intro_missing_alerts_and_continues(rjob, monkeypatch):
    db, work, store = rjob
    store.update_mix_job("J1", thumbnail={"intro": True, "results": []})
    from shopping_shorts import ops_alert
    calls, pre = [], []
    monkeypatch.setattr(ops_alert, "raise_alert", lambda kind, *a, **k: calls.append(kind) or True)
    monkeypatch.setattr(mp, "prepend_still", lambda *a, **k: pre.append(a) or True)
    mp.run_render("J1", db, work)
    j = store.get_mix_job("J1")
    assert j["status"] == "done", j.get("error")
    assert "intro_missing:J1" in calls and not pre


def test_run_render_intro_attaches_chosen_file(rjob, monkeypatch, thumbs):
    db, work, store = rjob
    (thumbs / "thumb_1.png").write_bytes(b"x")
    store.update_mix_job("J1", thumbnail={"intro": True, "selected": "thumb_1.png", "results": ["thumb_1.png"]})
    from shopping_shorts import ops_alert
    calls, pre = [], []
    monkeypatch.setattr(ops_alert, "raise_alert", lambda kind, *a, **k: calls.append(kind) or True)
    monkeypatch.setattr(mp, "prepend_still", lambda v, img, seconds=None: pre.append((Path(img).name, seconds)) or True)
    mp.run_render("J1", db, work)
    assert store.get_mix_job("J1")["status"] == "done"
    assert pre == [("thumb_1.png", 1.2)] and not calls

