# -*- coding: utf-8 -*-
"""회원에게 가는 말(사장님 10-26 "회원을 당황하게 하면 안 된다 — 나는 대처가 되지만 회원은 못 한다").

① flow.py 의 모든 멈춤 문구(_Stop·_out 의 why/fix·공용 문구)가 member_ok 를 통과 — '멈춤'·내부 용어 0, fix 엔 다음 행동.
② 회원 문구 검사기 자체가 나쁜 문장을 잡는다(검사기 사보타주).
③ 멈춤 응답 message 에 '멈춤:' 없음 · 속사정(검사 항목)은 기록에만.
④ 원본 찾기 = 02_원본찾기 순서로 끝까지(출처 채널 지문 확정 실패 → 미리보기 대조 → 검색 길) · 다 써도 없을 때만 '원본을 못 찾았어요 — 주소…'
   · 그 주소를 받으면 바로 이어 간다.
⑤ 쿠팡에 같은 물건 없으면 넓게 다시 찾고, 비슷한 제품을 고르면 회원에게 쉬운 말 알림(멈추지 않는다).
⑥ 잠깐의 문제(auto)는 회원에게 알리기 전에 스스로 한 번 다시.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402

FLOW = ROOT / "tools" / "calcopy" / "hybrid" / "flow.py"


def _const(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value
    if isinstance(n, ast.JoinedStr):            # f-string — 고정 글자만
        return "".join(v.value for v in n.values if isinstance(v, ast.Constant))
    return None


def member_texts():
    """flow.py 에서 회원에게 가는 고정 문구 전부 — (줄, why, fix)."""
    out = []
    tree = ast.parse(FLOW.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
        if name == "_Stop":
            args = [_const(a) for a in n.args[:2]]
            if args and args[0] is not None:
                out.append((n.lineno, args[0], args[1] if len(args) > 1 else ""))
        if name == "_out":
            kw = {k.arg: _const(k.value) for k in n.keywords if k.arg in ("why", "fix")}
            if kw.get("why") is not None:
                out.append((n.lineno, kw.get("why"), kw.get("fix") or ""))
    return out


def test_every_stop_text_is_member_friendly():
    texts = member_texts()
    assert len(texts) >= 40, len(texts)          # 멈춤이 이만큼 있다(못 뽑으면 이 시험이 아무것도 안 잰다)
    bad = [(ln, w, f) for ln, w, f in texts if not F.member_ok(w) or (f is not None and not F.member_ok(f, need_next=True))]
    assert not bad, bad
    for w, f in (F.NO_SIMILAR, F.NO_ORIGIN):
        assert F.member_ok(w) and F.member_ok(f, need_next=True)
    assert F.member_ok(F.ALT_NOTICE) and F.member_ok(F.AGAIN, need_next=True)


def test_checker_catches_bad_words():
    for s in ("멈춤: 원본", "다시 이어서 부르세요", "shortem_setup 을 하세요", "렌더 실패", "재료를 고치지 못했습니다", "확인 답을 받지 못했습니다",
              "개발팀 확인이 필요합니다", "봇 확인", "지문 1줄", "look 단계를", "{'a': 1}"):
        assert not F.member_ok(s), s
    assert not F.member_ok("", need_next=False)
    assert not F.member_ok("원본을 못 찾았습니다", need_next=True)        # 다음 행동 없음
    assert F.member_ok("원본 영상 주소를 주시면 바로 만들 수 있어요 · 다른 소재로 갈까요?", need_next=True)


def _st(**kw):
    st = F.start("https://youtu.be/BENCH1", "키치잇판", "sid")
    st.update(phase="x", bench={"id": "BENCH1", "title": "벤치", "channel": "남", "date": "20251001", "dur": 30, "sheet": "bench/sheet.jpg"},
              read={"celeb": "홍길동", "source_label": "홍길동TV", "product_words": ["기미 앰플"], "scene_words": [], "queries": ["홍길동 기미 앰플"]})
    st.update(kw)
    return st


def test_stop_message_has_no_stop_prefix_and_hides_detail():
    st = _st()
    res = F._out(st, "stop", "check", why="완성본 검사를 고쳐도 통과하지 못했습니다(음량 -30)", fix="다시 시도(retry)하면", detail="음량 -30")
    assert "멈춤" not in res["message"] and "음량" not in res["message"] and "retry" not in res["fix"]
    assert F.member_ok(res["why"]) and F.member_ok(res["fix"], need_next=True)
    assert any("음량" in x for x in st["log"])


def test_origin_pick_reject_goes_to_next_way_not_stop():
    """10-26 이미숙: 출처 채널 지문 1줄 → 확정 못 함 → 옛 판은 바로 멈춤. 이제 미리보기 대조(시트가 있으면) → 검색 길."""
    st = _st(scored=[{"id": "ORIG1", "matched": [{"bench": "x", "origin_t": 10}]}], origin_tried=["src"],
             probe_sb={"sheets": {"OTHER1": {"file": "look/sb_OTHER1.jpg"}}, "hits": {}, "dates": {}}, src_mixed=[{"id": "OTHER1", "title": "t"}])
    r = F.ph_pick_got(st, {}, {"origin_pick": {"origin_id": "", "self_spoken": True, "why": "한 줄뿐"}}, {})
    assert r.get("then") == "sb_pick" and r["review"][0]["id"] == "origin_sb"
    r2 = F.ph_sb_pick(st, {}, {"origin_sb": {"origin_id": "", "origin_t": []}}, {})
    assert r2 == {"goto": "search"}


def test_origin_all_ways_tried_then_friendly_and_url_continues():
    st = _st(scored=[{"id": "S1", "matched": []}], origin_tried=["src", "sb", "search"], phase="pick_got")
    res = F.step(st, {}, {"origin_pick": {"origin_id": "", "self_spoken": False}}, {})
    assert res["status"] == "stop"
    assert res["why"] == F.NO_ORIGIN[0] and res["fix"] == F.NO_ORIGIN[1] and "멈춤" not in res["message"]
    assert st["stopped"].get("origin_missing")
    res2 = F.step(st, {}, {}, {"origin_url": "https://www.youtube.com/watch?v=uOj3ix7qCj8"})
    assert res2["status"] == "execute" and res2["do"][0]["cmd"] == "origin_probe" and res2["do"][0]["ids"] == ["uOj3ix7qCj8"]
    res3 = F.step(st, {"probe": {"matched": {"uOj3ix7qCj8": [{"bench": "a", "origin_t": 119.0}, {"bench": "b", "origin_t": 169.0}]}}}, {}, {})
    assert res3["do"][0]["cmd"] == "origin_get" and res3["do"][0]["full"] is True


def test_coupang_no_same_goes_wide_then_alt_notice():
    st = _st(coupang_cands=[], named_cands=[], phase="best")
    res = F.step(st, {}, {}, {})
    assert res["status"] == "execute" and res["do"][0]["cmd"] == "coupang" and "기미 앰플" in res["do"][0]["queries"]
    st2 = _st(coupang_cands=[{"product_id": "1"}], phase="product_done")
    r = F.ph_product_done(st2, {}, {"best_same": {"product_id": "1", "name": "비슷한 앰플", "category": "화장품",
                                                  "member_why": "같은 기미 앰플이고 병 모양이 비슷해요"}}, {})
    assert r == {"goto": "reviews"} and st2["product"]["mode"] == "alt"
    out = F._out(st2, "execute", "reviews", do=[])
    assert F.ALT_NOTICE in out["message"] and "병 모양" in out["message"]
    assert F.ALT_NOTICE not in F._out(st2, "execute", "reviews", do=[])["message"]       # 한 번만


def test_transient_stop_retries_itself_once():
    st = _st(origin={"id": "O1", "window": [0.0, 100.0], "matched": []}, phase="origin_got")
    res = F.step(st, {"origin": {"error": "끊김"}}, {}, {})
    assert res["status"] == "execute" and res["do"][0]["cmd"] == "origin_get"      # 스스로 한 번 다시 받기
    res2 = F.step(st, {"origin": {"error": "또 끊김"}}, {}, {})
    assert res2["status"] == "stop" and F.member_ok(res2["fix"], need_next=True)
