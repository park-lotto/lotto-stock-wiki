# -*- coding: utf-8 -*-
"""채널 벤치마킹 2판 단계(관제 319) — 우리 프리셋 7단계를 회원 PC에서. 판단 주인 = 이 파일.
재기 = 실행기 명령(runner_ops bm_*·agy_read), 결정 = jev_gate(서버), 판독 = 회원 Claude(모델은 ASKS 한 곳).
flow.py 는 FORMAT_PHASES·FORMAT_STAGES·PHASE_STAGE 에 등록만 한다(flow.start_bench)."""
from __future__ import annotations

import json

PAN_MAX = 3          # 판볶이 최대 횟수 — 넘으면 「여기까지 맞췄어요」로 멈춘다
CONFIRM_MAX = 2      # 확정 검사·최종 판정이 틀렸다고 되돌릴 수 있는 횟수
ASKS = {   # 질문별 모델 — 페이블은 두 곳만(D6), 소넷·하이쿠 0곳(D5)
    "bm_read": {"id": "bm_read", "model": "opus"},
    "bm_confirm": {"id": "bm_confirm", "model": "fable"},
    "bm_verdict": {"id": "bm_verdict", "model": "fable"},
}
READ_SCHEMA = {"type": "object", "properties": {"caption_pos": {"type": "string"}, "caption_color": {"type": "string"}, "cut_feel": {"type": "string"},
               "voice": {"type": "string"}, "sfx": {"type": "string"}, "tone": {"type": "string"}, "story_order": {"type": "array", "items": {"type": "string"}}}}
# 컷 수·시각은 프로그램(kal_analyze.media_of)만 잰다 — 판독표에 컷 수 칸을 두지 않는다(결정 5)

STAGES = [("setup", "준비 확인"), ("bm_fetch", "벤치 영상 받기"), ("bm_tear", "영상 뜯기"), ("bm_read", "영상 보기"), ("bm_trial", "시험 영상 만들기"),
          ("bm_pan", "판볶이"), ("bm_confirm", "판 확정"), ("bm_make", "프리셋 묶음 만들기"), ("done", "완성")]
PHASE_STAGE = {"bm_setup": "setup", "bm_env_got": "setup", "bm_fetch_got": "bm_fetch", "bm_tear_got": "bm_tear", "bm_read_got": "bm_read", "bm_trial": "bm_read",
               "bm_trial_got": "bm_trial", "bm_panbokki": "bm_pan", "bm_confirm": "bm_confirm", "bm_confirm_got": "bm_confirm",
               "bm_verdict": "bm_confirm", "bm_verdict_got": "bm_confirm", "bm_brief": "bm_make", "bm_done": "done"}


def _F():
    from tools.calcopy.hybrid import flow
    return flow


def bm_setup(st, m, rp, u):
    return {"do": [{"id": "bm_env", "cmd": "bm_env"}], "then": "bm_env_got"}


def bm_env_got(st, m, rp, u):
    F = _F()
    e = m.get("bm_env") or {}
    if not e.get("agy"):
        raise F._Stop("영상을 볼 agy 가 이 PC에 없어요", "숏클 설치 안내의 agy 설치를 마친 뒤 다시 해 주세요", final=True)
    if not e.get("agy_login"):      # 오푸스로 조용히 넘어가지 않는다(영상을 볼 수 있는 건 구독 제미나이뿐)
        raise F._Stop("agy 로그인이 끊겼어요", "제미나이로 다시 로그인해 주세요", retry="bm_setup", ask_member=True)
    b = st["bm"]
    return {"do": [{"id": "bm_fetch", "cmd": "bm_fetch", **({"videos": b["videos_in"]} if b.get("videos_in") else {"url": b["url"]}), "n": b["n"]}], "then": "bm_fetch_got"}


def bm_fetch_got(st, m, rp, u):
    F = _F()
    vs = (m.get("bm_fetch") or {}).get("videos") or []
    if not vs:
        raise F._Stop("벤치 영상을 받지 못했어요", "채널 주소를 확인하거나 영상 주소 3개를 주세요", auto=True, retry="bm_env_got")
    st["bm"]["videos"] = vs
    return {"do": [{"id": "bm_tear", "cmd": "bm_tear", "slug": st["bm"]["slug"], "videos": vs}], "then": "bm_tear_got"}


def bm_tear_got(st, m, rp, u):
    F = _F()
    t = m.get("bm_tear") or {}
    ps = t.get("presets") or []
    if not ps:
        raise F._Stop("프리셋을 만들 수 있는 영상이 없어요", "세로 쇼츠 영상 주소를 직접 골라 주세요", detail=json.dumps(t.get("failed"), ensure_ascii=False)[:400])
    b = st["bm"]
    b["style"], b["other_styles"] = ps[0]["style"], [p["style"] for p in ps[1:]]      # 편 수가 많은 틀 하나로 간다 — 나머지는 결과에 적는다
    keep = set(ps[0]["sources"])
    do = [{"id": f"read_{v['id']}", "cmd": "agy_read", "video": v["v360"],
           "ask": "이 쇼츠의 자막 자리·색, 컷 느낌, 목소리, 효과음, 말투, 이야기 순서를 칸에 맞춰 적어라", "schema": READ_SCHEMA}
          for v in b["videos"] if v["id"] in keep]
    return {"do": do, "then": "bm_read_got"}


def bm_read_got(st, m, rp, u):
    F = _F()
    rows = {k: v.get("answer") for k, v in m.items() if k.startswith("read_") and isinstance(v, dict) and v.get("answer")}
    if not rows:
        raise F._Stop("영상 보기가 모두 실패했어요", "agy 로그인을 확인한 뒤 다시 해 주세요", retry="bm_setup", ask_member=True,
                      detail=json.dumps({k: v for k, v in m.items() if k.startswith("read_")}, ensure_ascii=False, default=str)[:400])
    st["bm"]["reads"] = rows
    ask = ("벤치 편마다 agy 가 적은 표다. 모든 편에 같은 칸(=채널 규칙)과 편마다 다른 칸(=소재)을 갈라라. "
           "agy 가 적은 값이 서로 다른데 프로그램 숫자(뜯기.json)로 확인할 수 있는 칸은 숫자를 믿어라.\n" + json.dumps(rows, ensure_ascii=False)[:12000])
    return {"review": [F._rv("bm_read", ask, model=ASKS["bm_read"]["model"], need=("rules", "per_video"))], "then": "bm_trial"}


def bm_trial(st, m, rp, u):
    F = _F()
    st["bm"]["rules"] = F._reply(rp, "bm_read", ("rules", "per_video"))
    return {"do": [{"id": "trial", "cmd": "render_trial", "slug": st["bm"]["slug"], "style": st["bm"]["style"]}], "then": "bm_trial_got"}


def _compare_do(st):
    b = st["bm"]
    n = int(st.get("pan_n") or 0)       # 시도 번호를 넣어 같은 입력 반복으로 오해받지 않게(flow._watch)
    return [{"id": "side", "cmd": "bm_side", "bench": b["videos"][0]["v360"], "ours": b["trial"], "try": n},
            {"id": "pan", "cmd": "bm_match", "slug": b["slug"], "style": b["style"], "ours": b["trial"], "try": n}]


def bm_trial_got(st, m, rp, u):
    F = _F()
    t = m.get("trial") or {}
    if not t.get("mp4"):
        raise F._Stop("시험 영상을 만들지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_trial", auto=True, detail=json.dumps(t, ensure_ascii=False, default=str)[:300])
    st["bm"]["trial"] = t["mp4"]
    return {"do": _compare_do(st), "then": "bm_panbokki"}


def bm_panbokki(st, m, rp, u):
    """판볶이 — 어긋난 칸을 한 번에 한 칸씩. 고칠 값 고르기는 Jev(서버). PAN_MAX 넘으면 남은 칸과 함께 멈춘다."""
    F = _F()
    from tools.calcopy.hybrid import jev_gate as J
    b = st["bm"]
    if (m.get("side") or {}).get("side"):
        b["side"] = m["side"]["side"]       # 확정 검사·최종 판정이 좌우 영상을 본다
    if m.get("pan"):
        b["pan_last"] = m["pan"]
    p = b.get("pan_last") or {}             # Jev 가 쉬어서 멈춘 뒤 다시 시도하면 직전 대조표로 이어 간다
    if p.get("match_ok"):
        return {"goto": "bm_confirm"}
    fails = p.get("fails") or b.get("fails") or []
    b["fails"] = fails
    if int(st.get("pan_n") or 0) >= PAN_MAX:
        raise F._Stop("여기까지 맞췄어요", "남은 칸: " + ", ".join(map(str, fails)) + " — 이 부분은 직접 고쳐 주세요", final=True)
    cands = p.get("cands") or []
    n = int(st.get("pan_n") or 0) + 1
    if len(cands) >= 2:
        try:
            d = J.decide(f"판볶이 {n}회차 — 벤치와 다른 칸 {fails[:5]}", [json.dumps(p, ensure_ascii=False)[:3000]],
                         [json.dumps(c, ensure_ascii=False) for c in cands])
        except J.JevDown as e:       # 서버 쪽 문제 — 회원 과제로 넘기지 않고(ask_member) 경보를 남기고 멈춘다
            st["alarm"] = {"kind": "jev_down", "where": "bm_panbokki", "why": str(e)}
            st["log"].append(f"경보: 벤치마킹 판단 서버(Jev) 실패 — {e}")
            raise F._Stop("잠시 판단 서버가 쉬고 있어요", "잠시 뒤 다시 해 주세요", retry="bm_panbokki", ask_member=True, detail=str(e))
        if not d["ok"]:
            st["pan_n"] = n
            st["log"].append(f"판볶이 {n}: 고를 칸 확신 부족(Jev {d['conf']}) → 더 깊이 다시 재기")
            return {"do": [{**x, "deeper": True} if x["id"] == "pan" else x for x in _compare_do(st)], "then": "bm_panbokki"}
        fix, why = cands[d["pick"]], f"Jev {d['conf']}"
    elif len(cands) == 1:
        fix, why = cands[0], "후보 하나"         # 고를 것이 없다 — 판단 없이 그대로
    else:
        st["pan_n"] = n
        return {"do": [{**x, "deeper": True, "hint": fails} if x["id"] == "pan" else x for x in _compare_do(st)], "then": "bm_panbokki"}
    st["pan_n"] = n
    st["log"].append(f"판볶이 {n}: {fix} ({why})")
    return {"do": [{"id": "fix", "cmd": "bm_fix", "slug": b["slug"], "style": b["style"], "fix": fix},
                   {"id": "trial", "cmd": "render_trial", "slug": b["slug"], "style": b["style"], "try": n}], "then": "bm_trial_got"}


def bm_confirm(st, m, rp, u):
    F = _F()
    b = st["bm"]
    ask = "판 확정 검사: 아래 고정 칸·편마다 칸 가르기가 벤치 편 전부와 맞는지 본다. 틀린 칸만 적는다.\n" + json.dumps(b.get("rules"), ensure_ascii=False)[:8000]
    return {"review": [F._rv("bm_confirm", ask, [F._img(b["side"])] if b.get("side") else [], model=ASKS["bm_confirm"]["model"], need=("ok", "wrong"))],
            "then": "bm_confirm_got"}


def _back_to_pan(st, wrong, why):
    """확정 검사·최종 판정이 틀렸다고 하면 판볶이로 되돌린다(후보 없이 깊이 다시 재기). 되돌림은 CONFIRM_MAX 번까지."""
    F = _F()
    b = st["bm"]
    b["confirm_n"] = int(b.get("confirm_n") or 0) + 1
    b["fails"] = list(wrong or [])
    if b["confirm_n"] > CONFIRM_MAX:
        raise F._Stop("여기까지 맞췄어요", "남은 칸: " + ", ".join(map(str, b["fails"]) or ["눈 판정에서 어긋남"]) + " — 이 부분은 직접 고쳐 주세요", final=True, detail=why)
    b["pan_last"] = {"match_ok": False, "fails": b["fails"], "cands": []}
    return {"goto": "bm_panbokki"}


def bm_confirm_got(st, m, rp, u):
    F = _F()
    r = F._reply(rp, "bm_confirm", ("ok", "wrong"))
    if not r.get("ok"):
        return _back_to_pan(st, r.get("wrong"), "확정 검사 불합격")
    return {"goto": "bm_verdict"}


def bm_verdict(st, m, rp, u):
    F = _F()
    b = st["bm"]
    ask = "최종 눈 판정: 왼쪽 벤치·오른쪽 우리 시험 영상을 나란히 본다. 같은 채널 영상으로 보이나? 어긋난 곳만 적는다."
    return {"review": [F._rv("bm_verdict", ask, [F._img(b["side"])] if b.get("side") else [], model=ASKS["bm_verdict"]["model"], need=("ok", "wrong"))],
            "then": "bm_verdict_got"}


def bm_verdict_got(st, m, rp, u):
    F = _F()
    r = F._reply(rp, "bm_verdict", ("ok", "wrong"))
    if not r.get("ok"):
        return _back_to_pan(st, r.get("wrong"), "최종 판정 불합격")
    return {"goto": "bm_brief"}


def bm_brief(st, m, rp, u):
    b = st["bm"]
    return {"do": [{"id": "brief", "cmd": "bm_brief", "slug": b["slug"], "style": b["style"], "name": b["name"]}], "then": "bm_done"}


def bm_done(st, m, rp, u):
    F = _F()
    b, br = st["bm"], m.get("brief") or {}
    if not br.get("zip"):
        raise F._Stop("프리셋 묶음을 만들지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_brief", auto=True, detail=json.dumps(br, ensure_ascii=False, default=str)[:300])
    return {"done": {"preset": {"slug": b["slug"], "style": b["style"], "name": b["name"], "zip": br["zip"], "other_styles": b.get("other_styles") or []}}}


PHASES = {"bm_setup": bm_setup, "bm_env_got": bm_env_got, "bm_fetch_got": bm_fetch_got, "bm_tear_got": bm_tear_got, "bm_read_got": bm_read_got,
          "bm_trial": bm_trial, "bm_trial_got": bm_trial_got, "bm_panbokki": bm_panbokki, "bm_confirm": bm_confirm, "bm_confirm_got": bm_confirm_got,
          "bm_verdict": bm_verdict, "bm_verdict_got": bm_verdict_got, "bm_brief": bm_brief, "bm_done": bm_done}
