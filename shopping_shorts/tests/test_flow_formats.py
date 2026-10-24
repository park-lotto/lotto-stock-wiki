# -*- coding: utf-8 -*-
"""회원 지시서 형식 분기(관제 263 지시서 08) — flow.FORMAT_STAGES·형식 거절·check 단계 = quality_gate·해외원본형 처리기·clean_text 돈 0.

가짜 실행기(measure)·가짜 회원 Claude(replies)로 flow.step 을 끝까지 돌려 단계 순서를 본다(영상·유튜브·AI 0).
연예인형 회귀 = 고치기 전 flow.py(git HEAD 의 옛 판, 있으면)와 같은 순서인지(완성본 검사 단계만 의도된 차이).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402
from tools.calcopy.hybrid import rules as RU  # noqa: E402

E_OK = {f"E{k}": {"v": "○", "memo": "ok"} for k in range(1, 10)}


def _measure(d: dict, ctx: dict) -> dict:
    c = d["cmd"]
    if c == "env":
        return {"keys": {"typecast": True, "elevenlabs": True}, "disk_gb": 50, "dev": True}
    if c == "bench":
        b = ctx.get("bench") or {"id": "BENCH1", "title": "홍길동 크림 쇼츠", "channel": "남의채널", "date": "20250601", "dur": 30, "sheet": "bench/sheet.jpg",
                                 "big": "bench/big.jpg", "lines": [{"text": "이 크림 진짜 좋아요"}]}
        return b
    if c == "channel_find":
        return {"titles": [{"id": "ORIG1", "title": "홍길동 크림 루틴", "dur": 600}], "picked": [{"name": "홍길동TV"}], "searched": ["ORIG1"], "how": "label"}
    if c == "origin_probe":
        return {"matched": {"ORIG1": [{"bench": "크림", "origin_t": 100.0 + k} for k in range(3)]}, "hits": {}}
    if c == "origin_get":
        vid = d["vid"]
        w, h = ctx.get("dims", {}).get(vid, (1920, 1080))
        return {"files": [{"name": f"{vid}.mp4", "w": w, "h": h, "dur": 30.0 if w < h else 600.0}], "offset": 0.0, "measured": True}
    if c == "sheet":
        return {"file": d.get("dst") or "look/x.jpg"}
    if c == "frames":
        return {"files": ["look/p1.jpg"]}
    if c == "coupang":
        return {"items": [{"product_id": "123", "name": "크림", "image": "http://img"}]}
    if c == "cand_sheet":
        return {"file": "look/cand.jpg"}
    if c == "coupang_reviews":
        return {"reviews": [{"id": "r1", "text": "촉촉해요"}]}
    if c == "origin_words":
        return {"words": [[1.0, "wow"]], "from": "받아쓰기"}
    if c == "write_doc":
        ctx.setdefault("docs", []).append(d.get("files"))
        return {"ok": True}
    if c == "screen":
        return {"rows": []}
    if c == "download":
        return {"files": []}
    if c == "product_stills":
        return {"files": [{"name": "prod_123_0.jpg", "w": 1000, "h": 1000, "dur": 0}]}
    if c == "asr_spans":
        return {"spans": []}
    if c == "shot_sheets":
        stems = [Path(f).stem for f in d.get("files") or []]
        return {"shots": {s: [{"i": 0, "a": 0.0, "b": 10.0}, {"i": 1, "a": 10.0, "b": 25.0}] for s in stems}, "sheets": {s: [f"_shots/{s}_sheet0.jpg"] for s in stems}}
    if c == "mat_sheets":
        return {"sheets": [], "list": []}
    if c == "orig_heard":
        return {"bad": []}
    if c == "plan":
        return {"over": "", "cuts": 5, "length": {"measured": True, "ok": True}, "sheet": "v/plan_sheet.jpg", "jumps": []}
    if c == "render":
        return {"ok": True, "jumps": []}
    if c == "check":
        ok = not ctx.get("gate_fail")
        return {"auto": {"ok": ok, "rows": [{"group": "규격", "what": "음량", "ok": ok, "value": "-14"}]}, "eye_files": ["v/eye/시트_1초.jpg"],
                "eye_texts": {"줄컷대조.md": "표"}, "upgrade": False, "sheet": "v/eye/시트_1초.jpg", "heard": {}}
    if c == "finish":
        return {"video": "C:/x/final.mp4"}
    if c == "origin_foreign":
        ctx.setdefault("of_calls", []).append(d.get("mode"))
        return {"mode": d.get("mode"), "cands": [{"n": 1, "platform": "yt", "id": "PEER1", "title": "Trying Korean cream", "channel": "Amy", "date": "20250301", "dur": 20,
                                                  "korean": False}, {"n": 2, "platform": "yt", "id": "KO1", "title": "외국인 반응", "channel": "한국채널", "korean": True}],
                "sheets": ["origin_foreign/judge_0.jpg"]}
    if c == "clean_text":
        ctx["clean_called"] = True
        return {"mode": "blur", "cleaned": [], "calls": 0, "why": "회원 VMake 키 없음 — 흐림으로 대체"}
    if c == "materials_draft":
        return {"draft": {"order": d.get("files"), "segments": {}}}
    raise AssertionError(f"가짜 실행기에 없는 명령: {c}")


def _reply(rv: dict, ctx: dict) -> dict:
    i = rv["id"]
    if i == "origin_read":
        return {"celeb": "홍길동", "source_label": "출처: 홍길동TV", "source_kind": "channel", "product_words": ["크림"], "queries": ["홍길동 크림"], "is_shopping": True}
    if i == "origin_pick":
        return {"origin_id": "ORIG1", "self_spoken": True, "matched": [{"origin_t": 100.0}]}
    if i == "ref_read":
        return {"ref_kind": ctx.get("ref_kind", "overseas_origin"), "is_shopping": True, "product_words": ["cream", "크림"], "brand_hint": "Medicube", "queries_en": ["medicube cream reaction"]}
    if i == "of_judge":
        return {"same": [1], "why": "같은 촬영분"}
    if i == "of_peer":
        return {"picks": [1, 2], "why": "같은 제품"}
    if i == "product_pick":
        return {"scenes": [{"src": "BENCH1.mp4", "t": 3, "crop": [0, 0, 500, 500]}], "coupang_queries": ["크림"], "brand_words": ["메디큐브"]}
    if i in ("product_same", "best_same", "named_same", "given_same", "shop_same"):
        return {"product_id": "123", "name": "메디큐브 크림", "category": "화장품", "why": "같은 포장"}
    if i == "name_find":
        return {"names": []}
    if i == "topic_read":
        return {"is_shopping": True, "product_words": ["크림"], "coupang_queries": ["크림"], "story": "놀람"}
    if i == "research":
        src = ctx.get("span_src")
        sp = {"a": 1.0, "b": 3.0, "tag": "O1", **({"src": src} if src else {})}
        return {"조사_md": "## 0 결론\n## 1 출처\n## 2 원음\n## 3 사실\n## 4 금지\n## 6 확인 못 한 것", "keywords": ["크림"], "queries": ["크림"], "spans": [sp] if src is not False else [],
                "facts": [{"id": "f1", "fact": "x", "src": "http://a"}]}
    if i.startswith("shot_"):
        return {"shots": [{"i": 0, "who": "main", "product": True, "text": [[0.1, 0.8, 0.9, 0.9]] if ctx.get("text_box") else [], "cx": 0.5, "desc": "얼굴"},
                          {"i": 1, "who": "main", "product": True, "text": [], "cx": 0.5, "desc": "제품"}]}
    if i.startswith("script_"):
        return {"대본": {"title_lines": [], "lines": [{"id": "N1", "kind": "tts", "tts": "안녕하세요.", "caps": [{"text": "안녕하세요"}]}]},
                "재료": {"cuts": {"N1": [{"src": ctx.get("cut_src", "prod_123_0.jpg"), "ss": 1.0}]}}, "근거_md": "| 줄 | 말 | 근거 |"}
    if i.startswith("plan_") or i.startswith("render_fix_") or i.startswith("final_fix_"):
        return {"ok": True, "problems": [], "재료": {"cuts": {"N1": [{"src": ctx.get("cut_src", "prod_123_0.jpg"), "ss": 1.0}]}} if not i.startswith("plan_") else None}
    if i.startswith("thumb_"):
        return {"썸네일": {}}
    if i.startswith("final_"):
        return {"ok": True, "problems": []}
    if i.startswith("eye_"):
        return dict(ctx.get("eye") or E_OK)
    raise AssertionError(f"가짜 회원 Claude 에 없는 질문: {i}")


def walk(mod, st: dict, ctx: dict | None = None, limit: int = 300) -> tuple[list, dict, dict]:
    """flow.step 을 끝(done·stop)까지 — 반환 (자취[(상태, 세부 단계, do 명령, review id)], 마지막 응답, 상태)."""
    ctx = ctx or {}
    trace, measure, replies, user = [], {}, {}, {}
    res = {}
    for _ in range(limit):
        res = mod.step(st, measure, replies, user)
        st = json.loads(json.dumps(res.pop("state"), ensure_ascii=False))
        trace.append((res["status"], st.get("phase"), tuple(d["cmd"] for d in res.get("do") or []), tuple(r["id"] for r in res.get("review") or [])))
        measure, replies, user = {}, {}, {}
        if res["status"] in ("done", "stop"):
            break
        if res["status"] == "execute":
            measure = {d["id"]: _measure(d, ctx) for d in res["do"]}
        elif res["status"] in ("review", "reject"):
            replies = {r["id"]: _reply(r, ctx) for r in res["review"]}
        elif res["status"] == "wait_user":
            user = {"approve": True}
    return trace, res, st


@pytest.fixture(autouse=True)
def _no_heavy(monkeypatch):
    """대본 검사(script_audit — 판 규칙)는 가짜 대본에 맞지 않으니 통과로(이 시험은 단계 흐름만 본다)."""
    monkeypatch.setattr(F, "audit_script", lambda st, S, M: {"ok": True})
    yield


def _old_flow():
    """고치기 전 flow.py(git HEAD) — 이 커밋 전 판. 이미 이 커밋이 HEAD 면 HEAD~ 에서 FORMAT_STAGES 없는 판을 찾는다."""
    for rev in ("HEAD", "HEAD~1", "HEAD~2", "HEAD~3", "HEAD~4", "HEAD~5"):
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:tools/calcopy/hybrid/flow.py"], capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0 and "FORMAT_STAGES" not in r.stdout:
            mod = types.ModuleType("flow_old")
            mod.__file__ = str(ROOT / "tools/calcopy/hybrid/flow.py")
            exec(compile(r.stdout, "flow_old.py", "exec"), mod.__dict__)
            mod.audit_script = lambda st, S, M: {"ok": True}
            return mod
    return None


# ── 1. 형식 거절(조용한 기본값 금지) ──────────────────────────────────────
def test_unknown_version_rejected():
    with pytest.raises(F.FormatError):
        F.start("https://youtu.be/x", "없는판_zz", "sid")


def test_format_resolution_and_mismatch():
    st = F.start("https://youtu.be/x", "잇템로그판_v2", "sid")
    assert st["fmt"] == "해외원본형" and st["slug"] == "ititemlog"
    assert F.start("u", "키치잇판", "s")["fmt"] == "연예인형"
    with pytest.raises(F.FormatError):
        F.start("u", "잇템로그판_v2", "s", fmt="연예인형")


# ── 2. 연예인형 회귀(완성본 검사 앞까지 옛 판과 같은 순서) ───────────────────
def test_celeb_same_steps_as_before_until_check():
    st = F.start("https://youtu.be/BENCH1", "키치잇판", "sid")
    tr_new, res, st_new = walk(F, st)
    assert res["status"] == "done", tr_new[-3:]
    assert st_new["fmt"] == "연예인형"
    old = _old_flow()
    if old is None:
        pytest.skip("옛 flow.py 를 git 에서 못 찾음")
    st0 = old.start("https://youtu.be/BENCH1", "키치잇판", "sid")
    tr_old, res_old, _ = walk(old, st0)
    assert res_old["status"] == "done"
    cut_new = next(i for i, t in enumerate(tr_new) if "check" in t[2])
    cut_old = next(i for i, t in enumerate(tr_old) if "check" in t[2])
    assert [t[2:] for t in tr_new[:cut_new + 1]] == [t[2:] for t in tr_old[:cut_old + 1]]       # 같은 do·같은 질문 순서
    assert any(r and r[0].startswith("eye_") for _, _, _, r in tr_new[cut_new:])                # 바뀐 곳 = 눈 2단 E1~E8
    assert not any(r and r[0].startswith("final_") and not r[0].startswith("final_fix") for _, _, _, r in tr_new)


def test_celeb_stage_numbers_unchanged():
    st = F.start("u", "키치잇판", "s")
    assert F._stage("plan", st) == {"no": 10, "total": 13, "text": "장면 맞추기", "key": "plan"}
    assert F._stage("thumb", st)["key"] == "plan"


# ── 3. check = quality_gate + 눈 2단, 미통과면 고치기 2회 뒤 멈춤(done 아님) ─────
def test_gate_fail_stops_after_two_fixes():
    st = F.start("https://youtu.be/BENCH1", "키치잇판", "sid")
    tr, res, st2 = walk(F, st, {"gate_fail": True})
    assert res["status"] == "stop", tr[-3:]
    assert sum(1 for t in tr if any(r.startswith("final_fix_") for r in t[3])) == 2
    assert sum(1 for t in tr if "check" in t[2]) == 3
    assert "음량" in res["why"]
    assert not any(t[0] == "done" for t in tr)


def test_eye_triangle_is_not_pass():
    eye = {**E_OK, "E3": {"v": "△", "memo": "애매"}}
    st = F.start("https://youtu.be/BENCH1", "키치잇판", "sid")
    tr, res, st2 = walk(F, st, {"eye": eye})
    assert res["status"] == "stop" and "E3" in res["why"]


def test_runner_check_uses_quality_gate_and_force_fail(tmp_path, monkeypatch):
    """runner check = quality_gate.gate(전체) · QG_FORCE_FAIL=1 이면 ×(사보타주 길). 옛 runner 는 bench_check(legacy10)만 봤다."""
    from tools.calcopy.hybrid import quality_gate as QG
    from tools.calcopy.hybrid import runner_ops as R
    (tmp_path / "키치잇판" / "render").mkdir(parents=True)
    (tmp_path / "키치잇판" / "render" / "final.mp4").write_bytes(b"x")
    seen = {}

    def fake_gate(v, doc, work, **kw):
        seen.update(kw)
        return {"ok": True, "rows": [{"group": "규격", "what": "길이", "ok": True, "value": "28"}], "report": "r.json", "eye_pack_dir": str(tmp_path / "키치잇판" / "eye")}
    monkeypatch.setattr(QG, "gate", fake_gate)
    out = R.c_check(tmp_path, {"version": "키치잇판"})
    assert out["auto"]["ok"] is True and seen.get("mode") == "full"
    monkeypatch.setenv("QG_FORCE_FAIL", "1")
    out = R.c_check(tmp_path, {"version": "키치잇판"})
    assert out["auto"]["ok"] is False and any("QG_FORCE_FAIL" in r["what"] for r in out["auto"]["rows"])


# ── 4. 해외원본형 ─────────────────────────────────────────────────────────
def test_foreign_overseas_ref_walk_to_done():
    ctx = {"dims": {"BENCH1": (1080, 1920), "PEER1": (1080, 1920)}, "span_src": "BENCH1.mp4", "text_box": True, "cut_src": "BENCH1.mp4",
           "bench": {"id": "BENCH1", "title": "Skincare Made Of Salmon WHAT?!?", "channel": "MissDarcei", "date": "20250627", "dur": 30, "sheet": "bench/sheet.jpg", "lines": []}}
    st = F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid")
    tr, res, st2 = walk(F, st, ctx)
    assert res["status"] == "done", tr[-4:]
    cmds = [c for t in tr for c in t[2]]
    for c in ("origin_foreign", "origin_get", "clean_text", "materials_draft", "shot_sheets", "asr_spans", "check"):
        assert c in cmds, c
    assert "channel_find" not in cmds and "origin_probe" not in cmds          # 연예인형 원본 찾기 길을 타지 않는다
    assert [o["id"] for o in st2["origins"]] == ["BENCH1", "PEER1"]          # 한국 제목 후보(KO1)는 원본 아님
    assert ctx["of_calls"] == ["peers"]
    assert st2["text_fix"]["calls"] == 0
    saved = [f for fs in ctx["docs"] for k, f in (fs or {}).items() if k.endswith("재료.json")]
    assert saved and saved[0].get("blur", {}).get("BENCH1.mp4"), "박힌 글자 샷이 재료.blur 로 흐려져야 한다"
    stages = [s for s, _ in F.FORMAT_STAGES["해외원본형"]]
    assert stages[2] == "origin" and F._stage("f_clean", st2)["text"].startswith("원본 정리")
    rv_ids = [r for t in tr for r in t[3]]
    assert "ref_read" in rv_ids and "origin_read" not in rv_ids                # 연예인형 질문(연예인 본인 원본)을 쓰지 않는다


def test_foreign_korean_reedit_uses_lens_then_peers():
    ctx = {"ref_kind": "korean_reedit", "dims": {"PEER1": (1080, 1920)}, "span_src": "PEER1.mp4", "cut_src": "PEER1.mp4",
           "bench": {"id": "BENCH1", "title": "한국 크림 써 본 외국인", "channel": "잇템로그", "date": "20250801", "dur": 30, "sheet": "bench/sheet.jpg", "lines": []}}
    st = F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid")
    tr, res, st2 = walk(F, st, ctx)
    assert ctx["of_calls"][0] == "lens"
    assert st2["origins"][0]["id"] == "PEER1" and st2["origins"][0]["how"] == "렌즈 같은 촬영분"
    assert res["status"] == "done", tr[-4:]


def test_foreign_questions_not_celeb():
    st = F.start("u", "잇템로그판_v2", "s")
    assert "연예인" not in F._q(st, "PLAN_LOOK") and "얜샷템" not in F._q(st, "PLAN_LOOK")
    assert "해외원본형" in F._q(st, "SCRIPT") and "원본별 **시간순**" in F._q(st, "SCRIPT")
    assert F.TRAPS_FOREIGN["origin"] != F.TRAPS["origin"]


def test_thumb_uses_find_order_of_slug():
    st = F.start("u", "잇템로그판_v2", "s")
    st["script"] = {"S": {}}
    r = F.ph_thumb(st, {}, {}, {})
    assert "참고(상위 편" in r["review"][0]["ask"]


# ── 5. clean_text — 회원 키 없으면 서버·VMake 호출 0, 흐림 대체 ─────────────────
def test_clean_text_no_key_no_call(tmp_path, monkeypatch):
    from tools.calcopy import vmake_clean as VC
    from tools.calcopy.hybrid import runner_ops as R
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.mp4").write_bytes(b"x")
    calls = []
    monkeypatch.setattr(VC, "member_clean", lambda *a, **k: calls.append(a) or {"cleaned": ["a.mp4"], "calls": 1, "fail": {}})
    monkeypatch.setattr(VC, "server_clean", lambda *a, **k: calls.append(a) or {})
    monkeypatch.delenv("VMAKE_API_KEY", raising=False)
    monkeypatch.setattr(R, "PAID_OFF", False)
    out = R.c_clean_text(tmp_path, {"files": ["src/a.mp4"]})
    assert out["mode"] == "blur" and out["calls"] == 0 and not calls
    led = json.loads((tmp_path / "src" / "vmake_log.json").read_text(encoding="utf-8"))
    assert led[-1]["calls"] == 0 and led[-1]["mode"] == "blur"
    monkeypatch.setenv("VMAKE_API_KEY", "ak:sk")                       # 키가 있으면 부른다(가짜) — 검사가 호출을 잡는지
    out = R.c_clean_text(tmp_path, {"files": ["src/a.mp4"]})
    assert out["mode"] == "vmake" and len(calls) == 1
    monkeypatch.setattr(R, "PAID_OFF", True)                          # 돈 0 스위치면 키가 있어도 안 부른다
    out = R.c_clean_text(tmp_path, {"files": ["src/a.mp4"]})
    assert out["calls"] == 0 and len(calls) == 1


def test_vmake_paid_off_guard(monkeypatch):
    from tools.calcopy import vmake_clean as VC
    monkeypatch.setenv("SHORTEM_NO_PAID", "1")
    with pytest.raises(PermissionError):
        VC.member_clean(["x.mp4"], "ak:sk")
    with pytest.raises(PermissionError):
        VC.server_clean(["x.mp4"])


# ── 6. 판단 함수(rules) — 세로 원본 확대 1.0 · 흐림 칸 ────────────────────────────
def test_vertical_source_full_width_is_not_zoom():
    ar = 1080 / 1434
    assert abs(RU.fit_height(1080, 1920, ar) - 1434) < 1
    assert RU.fit_height(1920, 1080, 9 / 16) == 1080
    M = {"cuts": {"N1": [{"src": "v.mp4", "ss": 1.0, "crop": [0, 243, 1080, 1434]}]}}
    assert RU.material_problems(M, {"v.mp4"}, set(), {"v.mp4": [1080, 1920]}, ar) == []
    assert RU.material_problems({"cuts": {"N1": [{"src": "v.mp4", "ss": 1.0, "crop": [0, 400, 1080, 1000]}]}}, {"v.mp4"}, set(), {"v.mp4": [1080, 1920]}, ar)


def test_fill_shot_max_vertical_crop_keeps_window_ratio():
    ar = 1080 / 1434
    M = {"cuts": {"N1": [{"src": "v.mp4", "ss": 2.0, "face": "주인공"}]}}
    RU.fill_shot_max(M, None, {"v.mp4": [1080, 1920]}, {"v": [{"i": 0, "a": 0, "b": 10, "cx": 0.5}]}, ar)
    x, y, w, h = M["cuts"]["N1"][0]["crop"]
    assert (w, h) == (1080, 1434) and y == (1920 - 1434) // 2


def test_text_blur_all_skips_cleaned():
    shots = {"a": [{"i": 0, "a": 0, "b": 2, "text": [[0, 0.8, 1, 0.9]]}], "b": [{"i": 0, "a": 0, "b": 2, "text": [[0, 0.8, 1, 0.9]]}]}
    dims = {"a.mp4": [1080, 1920], "b.mp4": [1080, 1920]}
    bl = RU.text_blur_all(shots, dims, {"b.mp4"})
    assert list(bl) == ["a.mp4"] and bl["a.mp4"][0][:4] == [0, 1536, 1080, 192]
    M = {}
    assert RU.merge_blur(M, bl) == 1 and RU.merge_blur(M, bl) == 0


def test_materials_draft_time_order_and_crop():
    from tools.calcopy import ititemlog_make as IM
    files = [{"name": "a.mp4", "w": 1080, "h": 1920, "dur": 20}]
    shots = {"a": [{"i": 1, "a": 5, "b": 9, "who": "main"}, {"i": 0, "a": 0, "b": 5, "who": "main", "text": [[0, 0, 1, .1]]}, {"i": 2, "a": 9, "b": 12, "other_product": True}]}
    d = IM.draft(files, shots, 1080 / 1434, [])
    assert [s["a"] for s in d["segments"]["a.mp4"]] == [0, 5]
    assert d["segments"]["a.mp4"][0]["text"] == "흐림" and d["crop"]["a.mp4"] == [0, 243, 1080, 1434]


# ── 7. placement conflict → 대본 단계로 되돌림(표준 §11-5 ㉛) ──────────────────────
def test_placement_conflict_goes_back_to_script():
    st = F.start("https://youtu.be/BENCH1", "키치잇판", "sid")
    st.update(phase="plan_got", script={"S": {"lines": []}, "M": {"cuts": {}}, "G": ""}, approved=True, bench={"id": "B"}, origin={"files": []})
    st["_msheets"] = {}
    conflict = {"axis": "fx.narr", "need": 5, "cap": 4, "cause": "tts_chars"}
    r = F.step(st, {"plan": {"conflict": conflict}}, {}, {})
    assert r["status"] == "reject" and r["review"][0]["id"].startswith("script_")
    assert "tts_chars" in r["reject"]["why"] and r["state"]["approved"] is False
    assert "두 TTS 줄로 나누기" in r["review"][0]["ask"]


def test_runner_conflict_passthrough():
    from tools.calcopy.hybrid import runner_ops as R
    assert R._conflict_of({"placement": {"conflict": {"axis": "a", "cause": "tts_chars"}}})["cause"] == "tts_chars"
    assert R._conflict_of({"placement": {}}) is None
