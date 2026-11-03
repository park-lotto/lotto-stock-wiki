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
    "bm_trial": {"id": "bm_trial", "model": "opus"},      # 시험 편 = 회원 과제(Ruling 10) — 회원 Claude 가 shortem_make 로 1편 만들고 작업 폴더를 올린다
    "bm_confirm": {"id": "bm_confirm", "model": "fable"},
    "bm_verdict": {"id": "bm_verdict", "model": "fable"},
}
READ_SCHEMA = {"type": "object", "properties": {"caption_pos": {"type": "string"}, "caption_color": {"type": "string"}, "cut_feel": {"type": "string"},
               "voice": {"type": "string"}, "sfx": {"type": "string"}, "tone": {"type": "string"}, "story_order": {"type": "array", "items": {"type": "string"}}}}
# 컷 수·시각은 프로그램(kal_analyze.media_of)만 잰다 — 판독표에 컷 수 칸을 두지 않는다(결정 5)
# 줄판독 눈 칸(관리자 Ruling 8) — 뼈대(kal_analyze.skeleton)는 시각·글·컷 시각 같은 기계값만 채우고 이 칸들은 비운다.
#   어느 칸을 판독으로 채우나 = 이 표 한 곳. 시각(t0·t1)·글(text)·컷(cut_at)은 뼈대 그대로(판독이 적어 와도 버린다).
EYE_SLOTS = ("speaker", "layer", "enter", "sfx", "scene", "emph", "sticker", "role", "fit", "fill_hex")
LINE_SCHEMA = {"type": "object", "properties": {"i": {"type": "integer"}, "speaker": {"type": "string"}, "layer": {"type": "string"},
               "enter": {"type": "string"}, "sfx": {"type": ["string", "null"]}, "scene": {"type": "string"}}}
READ_SCHEMA["properties"]["lines"] = {"type": "array", "items": LINE_SCHEMA}
LINE_VOCAB = ("줄마다 칸: speaker = 나레 | 원음:<이름> | 제3자 | 불명 (이름은 화면 글자에 보일 때만, 아니면 불명) · layer = 채널(벤치 채널 자막) | 원본박힘(원본 영상에 박힌 글) · "
              "enter = instant | append | typing | pop | glitch | wipe | slide | rainbow | fade | shake | 기타 (꾸밈 없으면 instant) · sfx = 그 줄에 나는 효과음(없으면 null) · scene = 그 줄 화면 한마디")
REREAD_MAX = 1       # check_doc 를 못 넘은 줄판독을 다시 읽는 횟수 — 넘으면 통과한 편만 쓰고, 0편이면 멈춘다

STAGES = [("setup", "준비 확인"), ("bm_fetch", "벤치 영상 받기"), ("bm_tear", "영상 뜯기"), ("bm_read", "영상 보기"), ("bm_trial", "시험 영상 만들기"),
          ("bm_pan", "판볶이"), ("bm_confirm", "판 확정"), ("bm_make", "프리셋 묶음 만들기"), ("done", "완성")]
PHASE_STAGE = {"bm_setup": "setup", "bm_env_got": "setup", "bm_fetch_got": "bm_fetch", "bm_tear_got": "bm_tear", "bm_skel_got": "bm_read", "bm_read_got": "bm_read", "bm_measure": "bm_read", "bm_measure_got": "bm_read", "bm_trial": "bm_read",
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
    b["keep"] = [v["id"] for v in b["videos"] if v["id"] in set(ps[0]["sources"])]
    return {"do": [{"id": "skel", "cmd": "bm_skel", "slug": b["slug"], "ids": b["keep"]}], "then": "bm_skel_got"}


def _read_do(b: dict, ids: list, errs: dict | None = None) -> list:
    """agy 한 번에 편 전체 칸 + 뼈대 줄마다 눈 칸(Ruling 8 — 판독을 두 번 돌리지 않는다)."""
    out = []
    for v in b["videos"]:
        if v["id"] not in ids:
            continue
        lines = (b.get("skel_lines") or {}).get(v["id"]) or []
        ask = ("이 쇼츠의 자막 자리·색, 컷 느낌, 목소리, 효과음, 말투, 이야기 순서를 칸에 맞춰 적어라. "
               "그리고 아래 자막 줄(i·시각·글)마다 눈 칸을 lines 에 적어라.\n" + LINE_VOCAB + "\n" + json.dumps(lines, ensure_ascii=False)[:6000])
        if errs and errs.get(v["id"]):
            ask += "\n지난 판독에서 빠진 칸: " + " / ".join(map(str, errs[v["id"]]))[:1500]
        out.append({"id": f"read_{v['id']}", "cmd": "agy_read", "video": v["v360"], "ask": ask, "schema": READ_SCHEMA,
                    **({"try": int(b.get("reread") or 0)} if errs else {})})
    return out


def bm_skel_got(st, m, rp, u):
    F = _F()
    k = m.get("skel") or {}
    docs = k.get("docs") or {}
    b = st["bm"]
    if not docs:
        raise F._Stop("벤치 영상의 자막 줄을 나누지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_tear_got", auto=True,
                      detail=json.dumps(k.get("failed"), ensure_ascii=False, default=str)[:400])
    b["skel"] = {vid: len(d.get("lines") or []) for vid, d in docs.items()}
    b["skel_lines"] = {vid: d.get("lines") or [] for vid, d in docs.items()}
    if k.get("failed"):
        st["log"].append("줄판독 뼈대 못 만든 편: " + json.dumps(k["failed"], ensure_ascii=False, default=str)[:300])
    return {"do": _read_do(b, list(docs)), "then": "bm_read_got"}


def bm_read_got(st, m, rp, u):
    F = _F()
    rows = {k: v.get("answer") for k, v in m.items() if k.startswith("read_") and isinstance(v, dict) and v.get("answer")}
    if not rows:
        raise F._Stop("영상 보기가 모두 실패했어요", "agy 로그인을 확인한 뒤 다시 해 주세요", retry="bm_setup", ask_member=True,
                      detail=json.dumps({k: v for k, v in m.items() if k.startswith("read_")}, ensure_ascii=False, default=str)[:400])
    st["bm"]["reads"] = rows
    ask = ("벤치 편마다 agy 가 적은 표다. 모든 편에 같은 칸(=채널 규칙)과 편마다 다른 칸(=소재)을 갈라라. "
           "agy 가 적은 값이 서로 다른데 프로그램 숫자(뜯기.json)로 확인할 수 있는 칸은 숫자를 믿어라.\n" + json.dumps(rows, ensure_ascii=False)[:12000])
    ask += ("\n\n줄판독 눈 칸도 확정해라 — lines = {편 id: [{i, speaker, layer, enter, sfx, scene}, …]}. agy 가 적은 줄 값을 보고 틀린 것만 고친다. "
            "이름(원음:<이름>)은 화면 글자에 보일 때만, 아니면 불명. 시각·글은 적지 마라(프로그램 값).\n" + LINE_VOCAB)
    return {"review": [F._rv("bm_read", ask, model=ASKS["bm_read"]["model"], need=("rules", "per_video", "lines"))], "then": "bm_measure"}


def _fill_of(vid: str, rows: list, per: dict) -> dict:
    """(판단 주인) 오푸스가 확정한 줄 눈 칸 → 뼈대에 넣을 값. EYE_SLOTS 밖 칸(시각·글)은 버린다. beats = 이야기 순서, narr_share = 나레 줄 비율."""
    lines = [{"i": int(l["i"]), **{k: l[k] for k in EYE_SLOTS if k in l}} for l in rows if isinstance(l, dict) and isinstance(l.get("i"), int)]
    sp = [str(l.get("speaker") or "") for l in lines]
    story = (per.get(vid) or {}).get("story_order") if isinstance(per.get(vid), dict) else None
    return {"lines": lines, "doc": {"beats": list(story) if isinstance(story, list) else [],
                                    "narr_share": round(sum(x.startswith("나레") for x in sp) / len(sp), 3) if sp else None}}


def bm_measure(st, m, rp, u):
    """줄판독 채우기 — 뼈대(bm_skel) + 눈 칸(bm_read 오푸스 확정) → 실행기가 넣고 kal_analyze.check_doc 으로 검사(bm_fill)."""
    F = _F()
    b = st["bm"]
    r = F._reply(rp, "bm_read", ("rules", "per_video", "lines"))
    b.setdefault("rules", {k: r[k] for k in ("rules", "per_video")})      # 다시 읽기(못 넘은 편만)의 답이 처음 규칙을 덮지 않게
    per, rows = r.get("per_video") or {}, r.get("lines") or {}
    fills = {vid: _fill_of(vid, rows.get(vid) or [], per) for vid in b.get("skel") or {} if vid in rows}
    if not fills:
        raise F._Stop("벤치 영상 판독이 비었어요", "잠시 뒤 다시 해 주세요", retry="bm_read_got", auto=True, detail="오푸스 답 lines 에 편이 없음")
    return {"do": [{"id": "fill", "cmd": "bm_fill", "slug": b["slug"], "fills": fills}], "then": "bm_measure_got"}


def bm_measure_got(st, m, rp, u):
    """check_doc 를 넘은 줄판독만 대조(bm_match)에 쓴다. 못 넘은 편은 REREAD_MAX 번 다시 읽고, 그래도 0편이면 멈춘다(조용히 넘어가지 않음)."""
    F = _F()
    b = st["bm"]
    f = m.get("fill") or {}
    d = str(f.get("dir") or f"channel/{b['slug']}/줄판독")
    bad = f.get("bad") or {}
    ok = [x for x in (b.get("line_ok") or []) if x not in bad]
    ok += [x for x in f.get("ok") or [] if x not in ok]
    b["line_ok"] = ok
    if bad and int(b.get("reread") or 0) < REREAD_MAX:
        b["reread"] = int(b.get("reread") or 0) + 1
        st["log"].append(f"줄판독 검사 못 넘음 → 다시 읽기: {json.dumps(bad, ensure_ascii=False)[:300]}")
        return {"do": _read_do(b, list(bad), bad), "then": "bm_read_got"}
    if not ok:
        raise F._Stop("벤치 영상 판독을 마치지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_tear_got", ask_member=True,   # 영상 보기(agy) 몫 — 회원 Claude 과제로 넘기지 않는다
                      detail="줄판독 check_doc 불합격: " + json.dumps(bad, ensure_ascii=False)[:400])
    if bad:
        st["log"].append(f"줄판독 검사 못 넘은 편은 대조에서 뺌: {sorted(bad)}")
    b["line_reads"] = [f"{d}/{x}.json" for x in ok]
    return {"goto": "bm_trial"}


TRIAL_ASK = """## 회원 과제 — 시험 영상 1편 만들기(벤치마킹 판볶이용)
지금 만든 임시 내 프리셋으로 기존 shortem_make 도구(1판 길 그대로 — AI 답 고리·소재 고르기 그대로)를 써서 영상 1편을 만든다.
- 쓸 프리셋: 작업 폴더 {dir} (slug {slug} · 틀 {style}). 임시 내 프리셋으로 올려서 쓴다.
- 소재: 1판 규칙 그대로 — {source}
- 벤치 영상 파일은 재료로 쓰지 않는다(벤치를 베끼는 게 아니라 같은 꼴로 새 편을 만든다).
- 끝나면 그 편의 작업 폴더(final.mp4·timeline.json·remake_log.json·대조/verdict.json 이 있는 곳)를 이 작업 폴더 기준 상대 경로로 올린다.
{again}
답: {{"work_dir": "<작업 폴더 상대 경로>", "ok": true|false, "why": "<못 만들었으면 이유>"}}"""


def _trial_source(b: dict) -> dict:
    """시험 편 소재 = 1판 규칙(shortem_client make_flow.js 211~213: 준 영상 또는 그 프리셋의 벤치 채널). 벤치 영상 파일·주소는 넣지 않는다."""
    return {"channel": b.get("url") or None}


def bm_trial(st, m, rp, u):
    """시험 편 — 회원 과제(의도한 일, 멈춤 아님). 회원 Claude 가 shortem_make 로 1편을 만들고 작업 폴더를 올린다(관리자 Ruling 10).
    판볶이가 칸을 고친 뒤(do bm_fix → 여기)에도 같은 과제로 다시 만든다."""
    F = _F()
    b = st["bm"]
    fx = m.get("fix") or {}
    if fx.get("error"):
        raise F._Stop("프리셋 칸을 고치지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_panbokki", ask_member=True, detail=str(fx["error"])[:300])
    src = _trial_source(b)
    pdir = f"channel/{b['slug']}/preset/{b['style']}"
    n = int(st.get("pan_n") or 0)
    ask = TRIAL_ASK.format(dir=pdir, slug=b["slug"], style=b["style"],
                           source=(f"벤치 채널 {src['channel']} 에서 고른다(영상 주소 없이 만들기)" if src["channel"] else "회원이 준 영상이 있으면 그 영상, 없으면 shortem_make 가 내는 안내 그대로"),
                           again=(f"- 판볶이 {n}번째 고침 뒤 다시 만드는 편이다(고친 칸: {b.get('fixed_last')})." if n else ""))
    meta = {"kind": "member_task", "tool": "shortem_make", "preset": {"slug": b["slug"], "style": b["style"], "dir": pdir}, "source": src, "try": n}
    return {"review": [F._rv("bm_trial", ask, model=ASKS["bm_trial"]["model"], need=("work_dir", "ok"), meta=meta)], "then": "bm_trial_got"}


def _compare_do(st):
    b = st["bm"]
    n = int(st.get("pan_n") or 0)       # 시도 번호를 넣어 같은 입력 반복으로 오해받지 않게(flow._watch)
    return [{"id": "side", "cmd": "bm_side", "bench": b["videos"][0]["v360"], "ours": b["trial"], "try": n},
            {"id": "pan", "cmd": "bm_match", "slug": b["slug"], "style": b["style"], "work": b.get("trial_dir"), "line_reads": b.get("line_reads") or [], "try": n}]


def bm_trial_got(st, m, rp, u):
    """회원 과제 답 — 작업 폴더가 없거나 못 만들었으면 멈춤 두 줄(조용히 넘어가지 않음). 회원 Claude 가 이미 한 일이라 제작자 과제로 또 돌리지 않는다(ask_member)."""
    F = _F()
    a = rp.get("bm_trial") if isinstance(rp.get("bm_trial"), dict) else {}
    wd = str(a.get("work_dir") or "").strip().strip("/")
    if not a.get("ok") or not wd:
        raise F._Stop("시험 영상을 만들지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_trial", ask_member=True,
                      detail="회원 과제 답: " + json.dumps(a or "없음", ensure_ascii=False, default=str)[:300])
    b = st["bm"]
    b["trial_dir"], b["trial"] = wd, f"{wd}/final.mp4"
    st["log"].append(f"시험 편 받음: {wd}")
    return {"do": _compare_do(st), "then": "bm_panbokki"}


def bm_panbokki(st, m, rp, u):
    """판볶이 — 어긋난 칸을 한 번에 한 칸씩. 고칠 값 고르기는 Jev(서버). PAN_MAX 넘으면 남은 칸과 함께 멈춘다."""
    F = _F()
    from tools.calcopy.hybrid import jev_gate as J
    b = st["bm"]
    if (m.get("side") or {}).get("side"):
        b["side"] = m["side"]["side"]       # 확정 검사·최종 판정이 좌우 영상을 본다
    if (m.get("pan") or {}).get("error"):      # 대조를 못 했다 — 빈 대조표로 '맞춤'·'다시 재기'로 새지 않게 멈춘다
        raise F._Stop("벤치와 맞춰 보지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_trial", ask_member=True, detail=str(m["pan"]["error"])[:300])
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
    b["fixed_last"] = fix.get("path") if isinstance(fix, dict) else fix
    return {"do": [{"id": "fix", "cmd": "bm_fix", "slug": b["slug"], "style": b["style"], "fix": fix}], "then": "bm_trial"}     # 한 칸만 고치고 시험 편부터 다시


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


PHASES = {"bm_setup": bm_setup, "bm_env_got": bm_env_got, "bm_fetch_got": bm_fetch_got, "bm_tear_got": bm_tear_got, "bm_skel_got": bm_skel_got, "bm_read_got": bm_read_got,
          "bm_measure": bm_measure, "bm_measure_got": bm_measure_got, "bm_trial": bm_trial, "bm_trial_got": bm_trial_got, "bm_panbokki": bm_panbokki, "bm_confirm": bm_confirm, "bm_confirm_got": bm_confirm_got,
          "bm_verdict": bm_verdict, "bm_verdict_got": bm_verdict_got, "bm_brief": bm_brief, "bm_done": bm_done}
