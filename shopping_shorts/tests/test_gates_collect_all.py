"""렌더 전 관문 — 걸린 것을 전부 모아 한 번에(사장님 10-26 '품질관문이나 고칠 것부터', 회원 마스크편 장면 맞추기 8바퀴 = 바퀴마다 새 문제 하나).

주인: 순서·모으기 = render_bench.timeline_gates(계획·렌더가 같은 목록을 부른다) · 소리 관문 모으기 = render_bench.voice_plan.
판정 함수·문턱은 그대로(여기서는 가짜 관문으로 '부르는 순서와 모으기'만 본다).
옛 코드: 계획(넘침이 먼저 멈춤 → ③ 등은 안 돎) · report(카드·③이 멈추면 넘침 글이 빠짐) · 소리(이름 끊김이 먼저 멈춤 → ② 안 돎) — 셋 다 이 시험에서 실패한다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import render_itssum as RI  # noqa: E402

ST = {"name": "t", "length": {"min": 1, "max": 99}, "cps_target": 7.0, "timing": {"tail": 0.35}, "voice": {"voice_id": "v"}}


def _doc(tmp_path):
    d = tmp_path / "doc"
    d.mkdir(parents=True)
    S = {"slug": "x", "voice": {"voice_id": "v"}, "cps_target": 7.0,
         "lines": [{"id": "N1", "kind": "tts", "tts": "가나다라마바사.", "caps": ["가나다라마바사"]},
                   {"id": "N2", "kind": "tts", "tts": "아자차카.", "caps": ["아자차카"]}]}
    (d / "대본.json").write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
    (d / "재료.json").write_text(json.dumps({"cand_dir": str(tmp_path), "cuts": {"N1": [{"src": "a.mp4", "ss": 0, "no_snap": True, "max": 0.5}],
                                                                                "N2": [{"src": "a.mp4", "ss": 5, "no_snap": True}]}}), encoding="utf-8")
    return d


def _stub(monkeypatch, gates: dict, voice: dict | None = None):
    """합성·배치·시트는 가짜, 관문은 gates 에 적은 글을 돌려준다(옛 코드에도 있는 이름만 바꾼다).
    N1 컷은 재료 max 0.5초인데 목소리 3초 → 넘침(over) — 진짜 timeline 이 잰다."""
    from tools.calcopy.engine import narr_verify as NV
    from tools.calcopy.hybrid import styles as STY
    from tools.calcopy.hybrid import thumb_rule as TR
    voice = voice or {}
    monkeypatch.setattr(STY, "load", lambda name: dict(ST))
    monkeypatch.setattr(RB, "_voice_gate_text", lambda S: None)
    monkeypatch.setattr(RB, "tts_by_line", lambda S, R, log=print: (R / "narr_full.mp3", None))
    monkeypatch.setattr(NV, "name_breaks", lambda S, align: list(voice.get("name", [])))
    monkeypatch.setattr(NV, "gate_sent", lambda S, sent, R, log=print: list(voice.get("asr", [])))
    monkeypatch.setattr(RI, "make_sentences", lambda S, full, R, log=print, align=None, spread=None:
                        ([{"id": k, "dur": 3.0, "raw": [0, 3.0], "tempo": 1.0, "wav": str(R / f"s_{k}.wav")} for k in ("N1", "N2")], 1.0, []))
    monkeypatch.setattr(RB, "fit_voice", lambda S, st, sent, align, log=print: sent)
    monkeypatch.setattr(RB, "plan_rows", lambda S, T, st, locate=None: {"log": "", "transitions": [], "rows": []})
    monkeypatch.setattr(RB, "transitions_of", lambda T, st, placed, log=None: [])
    monkeypatch.setattr(RB, "contact_sheet", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(RB, "deco_apply", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(RB, "deco_gate", lambda *a, **k: list(gates.get("deco_gate", [])), raising=False)
    for name in ("cut_boundary_gate", "cut_content_gate", "cut_length_gate", "cut_still_gate", "photo_gate", "rhythm_gate"):
        monkeypatch.setattr(RB, name, (lambda n: lambda *a, **k: list(gates.get(n, [])))(name))
    monkeypatch.setattr(TR, "card_text_gate", lambda doc: list(gates.get("card_text_gate", [])))
    monkeypatch.setattr(TR, "card_face_gate", lambda *a, **k: list(gates.get("card_face_gate", [])))


G = {"cut_boundary_gate": ["③ 경계 문제"], "cut_content_gate": ["컷 3 흐림 밖 남의 박힌 글자"], "rhythm_gate": ["리듬 문제"],
     "cut_still_gate": ["컷 멈춤 2"], "card_face_gate": ["썸네일 카드 A: 연예인 얼굴 아님"]}


def test_plan_stop_lists_every_gate(monkeypatch, tmp_path):
    """계획(멈춤) — 넘침 + ③④⑦·리듬·카드가 한 번의 StageError 에 전부. 옛 코드는 넘침에서 먼저 멈춰 나머지를 안 돌렸다."""
    _stub(monkeypatch, G)
    with pytest.raises(RB.StageError) as e:
        RB.render("t", _doc(tmp_path), tmp_path / "w", plan_only=True, log=lambda *a: None)
    msg = str(e.value)
    for want in ("원본 샷보다 길다", "③ 경계 문제", "남의 박힌 글자", "리듬 문제", "컷 멈춤 2", "썸네일 카드 A"):
        assert want in msg, want
    probs = getattr(e.value, "problems", None)
    assert probs and {g for g, _ in probs} >= {"넘침", "③ 경계", "④ 글자·얼굴", "⑦ 멈춤", "리듬", "⑥ 카드 얼굴"}


def test_plan_report_returns_every_gate(monkeypatch, tmp_path):
    """report(회원 c_plan) — 멈추지 않고 넘침과 관문 글을 다 돌려준다(옛 코드: 카드·③이 걸리면 StageError 로 넘침 글이 빠지고 시간표도 없었다)."""
    _stub(monkeypatch, G)
    res = RB.render("t", _doc(tmp_path), tmp_path / "w", plan_only=True, report=True, log=lambda *a: None)
    for want in ("원본 샷보다 길다", "③ 경계 문제", "남의 박힌 글자", "리듬 문제", "컷 멈춤 2", "썸네일 카드 A"):
        assert want in res["over"], want
    assert res["timeline"]["cuts"]
    assert [g for g, _ in res["gates"]][:2] == ["넘침", "⑧ 길이"]


def test_plan_clean_passes(monkeypatch, tmp_path):
    """다 통과면 그대로 계획을 돌려준다(넘침 없게 max 를 지운 재료)."""
    _stub(monkeypatch, {})
    d = _doc(tmp_path)
    M = json.loads((d / "재료.json").read_text(encoding="utf-8"))
    M["cuts"]["N1"][0].pop("max")
    (d / "재료.json").write_text(json.dumps(M), encoding="utf-8")
    res = RB.render("t", d, tmp_path / "w", plan_only=True, log=lambda *a: None)
    assert res["over"] == "" and all(not b for _, b in res["gates"])


def test_voice_gates_collected(monkeypatch, tmp_path):
    """소리 관문 — 이름 끊김과 ② 받아쓰기는 같은 소리를 재니 둘 다 모아 한 번(옛 코드: 이름 끊김에서 멈춰 ②를 안 봤다).
    시간표 관문은 소리에 기대니(줄 문장을 바꾸면 길이·컷이 다 바뀐다) 돌리지 않는다."""
    called = []
    _stub(monkeypatch, G, voice={"name": ["이름 끊김 '박정수'"], "asr": ["N2 되풀이"]})
    monkeypatch.setattr(RB, "cut_boundary_gate", lambda *a, **k: called.append("③") or [])
    with pytest.raises(RB.StageError) as e:
        RB.render("t", _doc(tmp_path), tmp_path / "w", plan_only=True, report=True, log=lambda *a: None)
    msg = str(e.value)
    assert "이름 끊김" in msg and "N2 되풀이" in msg
    assert called == []


def test_gate_order_is_written_once():
    """관문 목록은 계획·렌더가 같은 함수를 부른다(두 벌 금지 — 0순위-B). 기대는 관계 글이 코드에 있다."""
    src = (ROOT / "tools/calcopy/hybrid/render_bench.py").read_text(encoding="utf-8")
    body = src[src.index("def render(style_name"):]
    import re
    m = re.search(r"\n(def |if __name__)", body[10:])
    body = body[:m.start() + 10] if m else body
    assert body.count("cut_boundary_gate(") == 0 and body.count("timeline_gates(") == 2
    assert "GATE_DEPENDS" in src


def test_flow_render_gate_stop_asks_once_with_all(monkeypatch):
    """회원 flow — 렌더 전 관문 멈춤(runner c_render 의 gate 칸)은 재료 고치기 질문 하나에 걸린 것 전부.
    옛 코드: '처음 보는 렌더 오류'로 쳐서 글을 300자로 자르고, 두 번째부터는 곧장 멈췄다(render_err)."""
    from tools.calcopy.hybrid import flow
    seen = {}
    monkeypatch.setattr(flow, "_fix_review", lambda st, why, sheet, rid: seen.setdefault("why", why) and {"id": rid})
    monkeypatch.setattr(flow, "_tries", lambda *a, **k: None)
    long = " / ".join(f"컷 {k} a.mp4@{k}.00: 흐림 밖 남의 박힌 글자 3/3장(창 좌표 [[1, 2, 3, 4]]) — 재료.json blur 에 그 칸을 넣는다" for k in range(8))
    err = long + " / 리듬 진짜 컷 중앙 2.4초 > 판 1.3배"
    st = {"version": "잇템로그판_v2", "tries": {"render_err": 1}, "log": []}
    out = flow.ph_render_got(st, {"render": {"ok": False, "error": err, "gate": [["④ 글자·얼굴", "x"], ["리듬", "y"]]}}, {}, None)
    assert out["then"] == "render_fix"
    assert "리듬 진짜 컷 중앙" in seen["why"] and "컷 7 a.mp4@7.00" in seen["why"]
