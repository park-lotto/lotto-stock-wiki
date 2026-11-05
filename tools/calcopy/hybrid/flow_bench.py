# -*- coding: utf-8 -*-
"""채널 벤치마킹 2판 단계(관제 319) — 우리 프리셋 7단계를 회원 PC에서. 판단 주인 = 이 파일.
재기 = 실행기 명령(runner_ops bm_*·agy_read), 결정 = jev_gate(서버), 판독 = 회원 Claude(모델은 ASKS 한 곳).
flow.py 는 FORMAT_PHASES·FORMAT_STAGES·PHASE_STAGE 에 등록만 한다(flow.start_bench).
경보: Jev(판단 서버)가 꺼지면 st["alarm"] = {"kind": "jev_down", "why": <글>, "at": <phase>} 한 꼴로만 남긴다(ALARM_KEYS).
  flow 는 순수 함수라 여기까지가 이 파일 몫 — 관리자 경보로 올리는 일은 받는 곳 = claude_flow.step(과제 7, shopping_shorts/claude_flow.py)."""
from __future__ import annotations

import json

# 잡도리 멈춤(칼카피 엔진 v1 §2-1 A2 해결 0.97·뿌리 0.67): 같은 실패 묶음이 flow.REDO_STUCK 번 연속이면 멈춤 — 값은 flow.REDO_STUCK 한 곳을 같이 쓴다.
#   옛 PAN_MAX 3(횟수만 차면 멈춤)·CONFIRM_MAX 2(확정 되돌림 횟수)는 이 규칙으로 합쳤다. FABLE_MAX 는 돈 상한이라 그대로.
#   총 상한(페이블 #10 · Jev 해결 0.71·뿌리 0.53): 고친 횟수 ≤ ceil(첫 대조 실패 칸 수 × PAN_CAP_RATE), 최소 PAN_CAP_MIN — 칸이 번갈아 실패하며 끝없이 도는 것을 막는다.
PAN_CAP_RATE = 1.5
PAN_CAP_MIN = 3
FABLE_MAX = 2        # 한 채널에서 페이블(bm_confirm·bm_verdict)을 부르는 횟수 — 설계서 §7 「채널당 2번만」. st["bm"]["fable_n"] 이 센다
ALARM_KEYS = ("kind", "why", "at")
ASKS = {   # 질문별 모델 — 페이블은 두 곳만(D6), 소넷·하이쿠 0곳(D5)
    "bm_read": {"id": "bm_read", "model": "opus"},
    "bm_trial": {"id": "bm_trial", "model": "opus"},
    "bm_eye": {"id": "bm_eye", "model": "opus"},          # 전환·0초 화면 눈 판정(Ruling 17) — 벤치 편(bm_eye_<id>)·시험 편(bm_eye_trial) 같은 질문(EYE_ASK)      # 시험 편 = 회원 과제(Ruling 10) — 회원 Claude 가 shortem_make 로 1편 만들고 작업 폴더를 올린다
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
# 전환·0초 첫 화면(Ruling 17): 시각 = 프로그램(kal_analyze.eye_frames — scene_cuts 컷 + 프레임 띠), 종류 = 오푸스 눈. 판정 기준 문구 = 여기 한 곳.
#   벤치 편·시험 편 모두 이 질문 하나로 — 넣기 규칙도 한 곳(kal_analyze.apply_eye: 벤치 = bm_fill, 우리 = ours_from_remake).
EYE_ASK = """## 화면 전환·첫 화면 판정(프레임 그림)
그림 1 = 0초 첫 프레임 0·1·2·3번(2×2, 읽는 순서 = 왼쪽→오른쪽·위→아래). 그림 2부터 = 컷마다 컷 0.2초 앞부터 0.4초 동안 이어진 프레임 전부(4칸씩 줄 바꿈, 같은 읽는 순서 — 가운데쯤이 컷).
판정 기준:
- frame0: 0번·1~2번 프레임이 본 영상과 다른 표지(썸네일처럼 글을 크게 얹은 화면 — 그 뒤 프레임에서 본 장면으로 바뀐다)면 kind="card", text=표지 글 그대로.
  0번 프레임부터 본 장면이면 kind="scene", text="" (영상 위 늘 있는 제목 띠·자막·채널 표시는 표지가 아니다).
- cuts: 컷마다 kind 하나 — cut(앞뒤 프레임이 바로 바뀜) | flash(사이에 흰 번쩍임 프레임) | zoomblur(확대·흐림으로 넘어감) | black(검은 화면을 거침) | 기타(밀기·디졸브 등 위 넷이 아닌 전환).
컷 목록(i · 컷 시각 · 그림 번호):
{cuts}
답: {{"frame0": {{"kind": "card|scene", "text": "…"}}, "cuts": [{{"i": 0, "kind": "cut"}}, …]}} — 컷 목록의 i 를 하나도 빠짐없이."""
REREAD_MAX = 1       # check_doc 를 못 넘은 줄판독을 다시 읽는 횟수 — 넘으면 통과한 편만 쓰고, 0편이면 멈춘다

STAGES = [("setup", "준비 확인"), ("bm_fetch", "벤치 영상 받기"), ("bm_tear", "영상 뜯기"), ("bm_read", "영상 보기"), ("bm_trial", "시험 영상 만들기"),
          ("bm_pan", "잡도리"), ("bm_confirm", "판 확정"), ("bm_make", "프리셋 묶음 만들기"), ("done", "완성")]
PHASE_STAGE = {"bm_setup": "setup", "bm_env_got": "setup", "bm_fetch": "bm_fetch", "bm_fetch_got": "bm_fetch", "bm_tear": "bm_tear", "bm_tear_got": "bm_tear",
               "bm_skel": "bm_read", "bm_skel_got": "bm_read", "bm_read_got": "bm_read", "bm_measure": "bm_read", "bm_measure_got": "bm_read", "bm_reread": "bm_read", "bm_trial": "bm_read",
               "bm_eye_ask": "bm_read", "bm_trial_frames": "bm_pan", "bm_trial_eye": "bm_pan", "bm_trial_eye_got": "bm_pan",
               "bm_trial_got": "bm_trial", "bm_compare": "bm_pan", "bm_panbokki": "bm_pan", "bm_confirm": "bm_confirm", "bm_confirm_got": "bm_confirm",
               "bm_verdict": "bm_confirm", "bm_verdict_got": "bm_confirm", "bm_brief": "bm_make", "bm_done": "done"}


def _F():
    from tools.calcopy.hybrid import flow
    return flow


# 멈춤 종류(관제 319 · Jev 해결 0.85·위험 0.25): 실패 이유가 전부 PC·네트워크 사정(메모리·파일·디스크·429·시간 초과)이면 '환경' —
#   사람에게 묻지 않고 같은 단계를 자동 재시도(auto). 하나라도 내용 실패가 섞이면 '내용' — 그때만 회원에게 묻는다.
#   판정 = stop_kind 한 곳. 실패 목록(failed·error)이 있는 멈춤 자리는 전부 _fail_stop 을 부른다.
ENV_MARKS = ("MemoryError", "Unable to allocate", "WinError 1455", "페이징 파일", "OSError", "PermissionError", "FileNotFoundError", "BrokenPipe",
             "No space", "디스크", "429", "Too Many Requests", "rate limit", "timeout", "Timeout", "TimeoutExpired", "시간 초과", "ConnectionError",
             "Connection reset", "실행기 출력 없음")


def stop_kind(errs) -> str:
    """(판단 주인 · 멈춤 종류) errs = 실패 목록([{why}] · 글 · dict) → 'env' | 'content'. 비어 있으면 content(이유 없는 실패를 환경으로 치지 않는다)."""
    if isinstance(errs, (str, dict)):
        errs = [errs]
    texts = [str(x.get("why") or x.get("error") or x) if isinstance(x, dict) else str(x) for x in errs or []]
    texts = [t for t in texts if t.strip()]
    return "env" if texts and all(any(k in t for k in ENV_MARKS) for t in texts) else "content"


def _fail_stop(errs, why: str, fix: str, retry: str | None, retry_content: bool = True, **kw):
    """실패 목록이 있는 멈춤 한 곳 — 환경이면 같은 단계 자동 재시도(회원 질문 없음), 내용이면 주어진 두 줄로."""
    F = _F()
    detail = json.dumps(errs, ensure_ascii=False, default=str)[:400]
    if stop_kind(errs) == "env":
        return F._Stop("PC가 잠깐 바빠서 이어 가지 못했어요", "잠시 뒤 다시 해 주세요", retry=retry, auto=True, ask_member=True, detail="환경 실패: " + detail)
    return F._Stop(why, fix, retry=retry if retry_content else None, detail=detail, **kw)


def bm_setup(st, m, rp, u):
    return {"do": [{"id": "bm_env", "cmd": "bm_env"}], "then": "bm_env_got"}


def bm_env_got(st, m, rp, u):
    F = _F()
    e = m.get("bm_env") or {}
    if e.get("error"):       # 실행기가 준비 확인을 못 돌렸다(띄우기 실패·시간 초과) — agy 가 없다는 뜻이 아니다. 잠깐의 문제로 다시
        raise _fail_stop([e["error"]], "준비 확인을 마치지 못했어요", "잠시 뒤 다시 해 주세요", "bm_setup", auto=True, ask_member=True)
    if e.get("mem_free_gb") is not None:      # 메모리 여유는 기록만 — 시작 전 문턱은 Jev 미달(해결 0.79·뿌리 0.48)이라 보류, MemoryError 는 멈춤 분류가 자동 재시도
        st["log"].append(f"준비: 메모리(커밋) 여유 {e['mem_free_gb']}GB · 디스크 {e.get('disk_gb')}GB")
    if not e.get("agy"):
        raise F._Stop("영상을 볼 agy 가 이 PC에 없어요", "숏클 설치 안내의 agy 설치를 마친 뒤 다시 해 주세요", final=True)
    if not e.get("agy_login"):      # 오푸스로 조용히 넘어가지 않는다(영상을 볼 수 있는 건 구독 제미나이뿐)
        raise F._Stop("agy 로그인이 끊겼어요", "제미나이로 다시 로그인해 주세요", retry="bm_setup", ask_member=True)
    return bm_fetch(st, m, rp, u)


def bm_fetch(st, m, rp, u):
    """벤치 영상 받기 — 준비 확인 뒤, 또는 받기 실패 뒤 다시 시도(옛 retry=bm_env_got 은 빈 준비 결과로 'agy 없음' 오판)."""
    b = st["bm"]
    return {"do": [{"id": "bm_fetch", "cmd": "bm_fetch", **({"videos": b["videos_in"]} if b.get("videos_in") else {"url": b["url"]}), "n": b["n"]}], "then": "bm_fetch_got"}


def bm_fetch_got(st, m, rp, u):
    r = m.get("bm_fetch") or {}
    vs = r.get("videos") or []
    if not vs:
        raise _fail_stop([r["error"]] if r.get("error") else [], "벤치 영상을 받지 못했어요", "채널 주소를 확인하거나 영상 주소 3개를 주세요", "bm_fetch", auto=True)
    st["bm"]["videos"] = vs
    return bm_tear(st, m, rp, u)


def bm_tear(st, m, rp, u):
    """뜯기 — 받은 영상 그대로(다시 시도도 받기부터가 아니라 뜯기만)."""
    return {"do": [{"id": "bm_tear", "cmd": "bm_tear", "slug": st["bm"]["slug"], "videos": st["bm"]["videos"]}], "then": "bm_tear_got"}


def bm_tear_got(st, m, rp, u):
    t = m.get("bm_tear") or {}
    ps = t.get("presets") or []
    if not ps:
        raise _fail_stop(t.get("failed") or ([t["error"]] if t.get("error") else []),
                         "프리셋을 만들 수 있는 영상이 없어요", "세로 쇼츠 영상 주소를 직접 골라 주세요", "bm_tear", retry_content=False)
    b = st["bm"]
    b["style"], b["other_styles"] = ps[0]["style"], [p["style"] for p in ps[1:]]      # 편 수가 많은 틀 하나로 간다 — 나머지는 결과에 적는다
    b["keep"] = [v["id"] for v in b["videos"] if v["id"] in set(ps[0]["sources"])]
    _branch(st, t)
    return {"do": [{"id": "skel", "cmd": "bm_skel", "slug": b["slug"], "ids": b["keep"]}], "then": "bm_skel_got"}


def _branch(st, t: dict) -> None:
    """(뜯기 끝 한 곳 — 규격 §9 B1·P2) 갈래 판정. 판정 함수 = r7.branch_of(한 곳), 여기는 쓰는 편(keep)만 넘기고 결과를 st 에 둔다.
    R7 을 못 잰 편은 missing 으로 남기고 경보 한 줄(조용히 넘어가지 않음) — 갈래는 짝 확정이 없으니 짝 없는 클립형."""
    from tools.calcopy.engine import r7 as R7
    b = st["bm"]
    got = t.get("r7") or {}
    g = R7.branch_of({vid: got.get(vid) for vid in b["keep"]})
    b["branch"] = g
    st["log"].append(f"갈래: {g['branch']} — {g['why']}")
    if g["missing"]:
        st["log"].append(f"경보: R7 칸을 못 잰 편 {g['missing']} — " + json.dumps(t.get("r7_failed") or [], ensure_ascii=False)[:300])


def bm_skel(st, m, rp, u):
    """줄판독 뼈대만 다시(뜯기 결과 그대로) — 옛 retry=bm_tear_got 은 빈 뜯기 결과로 '프리셋 없음' 오판."""
    b = st["bm"]
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
        raise _fail_stop(k.get("failed") or ([k["error"]] if k.get("error") else []), "벤치 영상의 자막 줄을 나누지 못했어요", "잠시 뒤 다시 해 주세요",
                         "bm_skel", auto=True)
    b["skel"] = {vid: len(d.get("lines") or []) for vid, d in docs.items()}
    b["skel_lines"] = {vid: d.get("lines") or [] for vid, d in docs.items()}
    if k.get("failed"):
        st["log"].append("줄판독 뼈대 못 만든 편: " + json.dumps(k["failed"], ensure_ascii=False, default=str)[:300])
    return {"do": _read_do(b, list(docs)) + _eye_do(b, list(docs)), "then": "bm_read_got"}


def _eye_do(b: dict, ids: list) -> list:
    """벤치 편 눈 판정 그림 뽑기(실행기 bm_eye_frames) — 이미 판정이 있거나 그림이 있으면 다시 뽑지 않는다."""
    if b.get("eye") or b.get("eye_frames"):
        return []
    vs = [{"id": v["id"], "mp4": v["mp4"], "win_doc": f"channel/{b['slug']}/줄판독_뼈대/{v['id']}.json"} for v in b["videos"] if v["id"] in ids]
    return [{"id": "eye_b", "cmd": "bm_eye_frames", "videos": vs}] if vs else []


def _eye_rv(rid: str, fr: dict) -> dict:
    """눈 판정 질문 하나(EYE_ASK) — 그림 = 0초 한 장 + 컷마다 띠 한 장. 벤치 편·시험 편 같은 문구."""
    F = _F()
    cuts = fr.get("cuts") or []
    lst = "\n".join(f"- i={i} · {c['t']}초 · 그림 {i + 2}" for i, c in enumerate(cuts)) or "- (컷 없음 — cuts 는 [])"
    return F._rv(rid, EYE_ASK.format(cuts=lst), [F._img(fr["frame0"])] + [F._img(c["img"]) for c in cuts],
                 model=ASKS["bm_eye"]["model"], need=("frame0", "cuts"))


def _eye_of(a, fr: dict) -> tuple:
    """(판단 주인 — 눈 답 → 판정 꼴) 답의 컷 i 를 그림 뽑을 때 잰 시각에 붙인다. 꼴 검사 = kal_analyze.eye_check(한 곳)."""
    from tools.calcopy.engine import kal_analyze as K
    if not isinstance(a, dict):
        return None, ["눈 판정 답 없음"]
    cuts = fr.get("cuts") or []
    by_i = {int(c["i"]): c.get("kind") for c in a.get("cuts") or [] if isinstance(c, dict) and isinstance(c.get("i"), int)}
    eye = {"cuts": [{"t": c["t"], "kind": by_i.get(i)} for i, c in enumerate(cuts) if i in by_i], "frame0": a.get("frame0")}
    return eye, K.eye_check(eye, len(cuts))


def _eye_frames_got(r, ids: list):
    """실행기 bm_eye_frames 결과 → {id: 그림 묶음}. 오류·빠진 편이 있으면 None(멈춤은 부르는 쪽 — 조용히 넘어가지 않음)."""
    if not isinstance(r, dict) or r.get("error"):
        return None
    fr = r.get("frames") or {}
    return fr if fr and all(i in fr for i in ids) else None


def _eye_stop(detail: str, retry: str):
    return _fail_stop([detail[:400]], "화면 전환을 확인하지 못했어요", "잠시 뒤 다시 해 주세요", retry, ask_member=True)


def bm_read_got(st, m, rp, u):
    F = _F()
    rows = {k: v.get("answer") for k, v in m.items() if k.startswith("read_") and isinstance(v, dict) and v.get("answer")}
    if not rows:
        errs = [v.get("error") or v for k, v in m.items() if k.startswith("read_") and isinstance(v, dict)]
        raise _fail_stop(errs, "영상 보기가 모두 실패했어요", "agy 로그인을 확인한 뒤 다시 해 주세요", "bm_reread" if st["bm"].get("skel_lines") else "bm_setup",
                         ask_member=True)
    st["bm"]["reads"] = rows
    ask = ("벤치 편마다 agy 가 적은 표다. 모든 편에 같은 칸(=채널 규칙)과 편마다 다른 칸(=소재)을 갈라라. "
           "agy 가 적은 값이 서로 다른데 프로그램 숫자(뜯기.json)로 확인할 수 있는 칸은 숫자를 믿어라.\n" + json.dumps(rows, ensure_ascii=False)[:12000])
    ask += ("\n\n줄판독 눈 칸도 확정해라 — lines = {편 id: [{i, speaker, layer, enter, sfx, scene}, …]}. agy 가 적은 줄 값을 보고 틀린 것만 고친다. "
            "이름(원음:<이름>)은 화면 글자에 보일 때만, 아니면 불명. 시각·글은 적지 마라(프로그램 값).\n" + LINE_VOCAB)
    rvs = [F._rv("bm_read", ask, model=ASKS["bm_read"]["model"], need=("rules", "per_video", "lines"))]
    b = st["bm"]
    if not b.get("eye"):             # 전환·0초 화면 눈 판정(Ruling 17) — 줄판독을 만들 때 같이 받는다(다시 읽기 때는 이미 있어 다시 묻지 않는다)
        ids = list(b.get("skel") or {})
        if "eye_b" in m:
            got = _eye_frames_got(m["eye_b"], ids)
            if got is None:
                raise _eye_stop("bm_eye_frames: " + json.dumps(m["eye_b"], ensure_ascii=False, default=str)[:300], "bm_reread")
            b["eye_frames"] = {k: got[k] for k in ids}
        if not b.get("eye_frames"):
            raise _eye_stop("벤치 편 눈 판정 그림 없음", "bm_reread")
        rvs += [_eye_rv(f"bm_eye_{vid}", fr) for vid, fr in b["eye_frames"].items()]
    return {"review": rvs, "then": "bm_measure"}


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
    if "bm_read" not in rp and b.get("read_reply"):     # 눈 판정만 다시 물은 뒤(bm_eye_ask) — 받아 둔 판독 답으로 이어 간다
        rp = {**rp, "bm_read": b["read_reply"]}
    r = F._reply(rp, "bm_read", ("rules", "per_video", "lines"))
    if not b.get("eye"):
        b["read_reply"] = r
        eyes, bad = {}, {}
        for vid, fr in (b.get("eye_frames") or {}).items():
            e, errs = _eye_of(rp.get(f"bm_eye_{vid}"), fr)
            if errs:
                bad[vid] = errs
            else:
                eyes[vid] = e
        if bad or not eyes:
            raise _eye_stop("눈 판정 답 불합격: " + json.dumps(bad or "그림 없음", ensure_ascii=False)[:300], "bm_eye_ask" if b.get("eye_frames") else "bm_reread")
        b["eye"] = eyes
        b.pop("read_reply", None)
    b.setdefault("rules", {k: r[k] for k in ("rules", "per_video")})      # 다시 읽기(못 넘은 편만)의 답이 처음 규칙을 덮지 않게
    per, rows = r.get("per_video") or {}, r.get("lines") or {}
    fills = {vid: {**_fill_of(vid, rows.get(vid) or [], per), "eye": b["eye"].get(vid)} for vid in b.get("skel") or {} if vid in rows}
    if not fills:
        raise F._Stop("벤치 영상 판독이 비었어요", "잠시 뒤 다시 해 주세요", retry="bm_read_got", auto=True, detail="오푸스 답 lines 에 편이 없음")
    return {"do": [{"id": "fill", "cmd": "bm_fill", "slug": b["slug"], "fills": fills}], "then": "bm_measure_got"}


def bm_eye_ask(st, m, rp, u):
    """눈 판정 답이 비거나 틀려 멈춘 뒤 다시 시도 — 저장된 그림으로 눈 판정만 다시 묻는다(판독 답은 st 에 있다)."""
    b = st["bm"]
    if not b.get("eye_frames"):
        raise _eye_stop("저장된 눈 판정 그림 없음", "bm_reread")
    return {"review": [_eye_rv(f"bm_eye_{vid}", fr) for vid, fr in b["eye_frames"].items()], "then": "bm_measure"}


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
        raise F._Stop("벤치 영상 판독을 마치지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_reread", ask_member=True,   # 영상 보기(agy) 몫 — 회원 Claude 과제로 넘기지 않는다. 다시 시도 = 저장된 뼈대로 판독만 새로(최종 검토, Jev 0.80)
                      detail="줄판독 check_doc 불합격: " + json.dumps(bad, ensure_ascii=False)[:400])
    if bad:
        st["log"].append(f"줄판독 검사 못 넘은 편은 대조에서 뺌: {sorted(bad)}")
    b["line_reads"] = [f"{d}/{x}.json" for x in ok]
    return {"goto": "bm_trial"}


def bm_reread(st, m, rp, u):
    """줄판독이 다시 읽기 뒤에도 0편 통과로 멈춘 뒤 다시 시도 — 받기·뜯기·뼈대(기계값)는 그대로 두고 저장된 뼈대 줄로 agy 판독부터 새로.
    다시 읽기 횟수는 처음으로(회원이 누른 다시 시도마다 한 벌). 뼈대가 없으면 뜯기 결과가 없는 것 — 처음부터."""
    F = _F()
    b = st["bm"]
    ids = [v for v in (b.get("skel") or {}) if (b.get("skel_lines") or {}).get(v)]
    if not ids:
        raise F._Stop("벤치 영상 판독을 마치지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_setup", ask_member=True, detail="저장된 줄판독 뼈대 없음")
    b["reread"] = 0
    return {"do": _read_do(b, ids) + _eye_do(b, ids), "then": "bm_read_got"}


TRIAL_ASK = """## 회원 과제 — 시험 영상 1편 만들기(벤치마킹 잡도리용)
지금 만든 임시 내 프리셋으로 기존 shortem_make 도구(1판 길 그대로 — AI 답 고리·소재 고르기 그대로)를 써서 영상 1편을 만든다.
- 쓸 프리셋: 작업 폴더 {dir} (slug {slug} · 틀 {style}). 회원 PC 가 임시 내 프리셋으로 올려 두었다 — 프리셋 id {{preset_id}}
- 만들기: shortem_make(step="start", preset="{{preset_id}}") 로 시작해 그 응답의 next 대로 완성(need="done")까지 간다.
- 소재: 1판 규칙 그대로 — {source}
- 벤치 영상 파일은 재료로 쓰지 않는다(벤치를 베끼는 게 아니라 같은 꼴로 새 편을 만든다).
- 목소리: 이 시험 편은 피쉬 '차분한 해설가' — 대본 purpose="calcopy"(목소리 {tts}). 타입캐스트를 부르지 않는다.
- 끝나면 그 편의 sid(shortem_make 응답의 sid)를 work_dir 칸에 그대로 넣는다 — 회원 PC 가 그 편 작업 폴더를 이 작업 폴더 안으로 옮겨 상대 경로로 바꾼다.
{again}
답: {{"work_dir": "<shortem_make 응답의 sid>", "ok": true|false, "why": "<못 만들었으면 이유>"}}"""


def _trial_source(b: dict) -> dict:
    """시험 편 소재 = 1판 규칙(shortem_client make_flow.js 211~213: 준 영상 또는 그 프리셋의 벤치 채널). 벤치 영상 파일·주소는 넣지 않는다."""
    return {"channel": b.get("url") or None}


def bm_trial(st, m, rp, u):
    """시험 편 — 회원 과제(의도한 일, 멈춤 아님). 회원 Claude 가 shortem_make 로 1편을 만들고 작업 폴더를 올린다(관리자 Ruling 10).
    잡도리가 칸을 고친 뒤(do bm_fix → 여기)에도 같은 과제로 다시 만든다."""
    F = _F()
    b = st["bm"]
    fx = m.get("fix") or {}
    if fx.get("error"):
        raise _fail_stop([fx["error"]], "프리셋 칸을 고치지 못했어요", "잠시 뒤 다시 해 주세요", "bm_panbokki", ask_member=True)
    src = _trial_source(b)
    pdir = f"channel/{b['slug']}/preset/{b['style']}"
    n = int(st.get("pan_n") or 0)
    from tools.calcopy.engine import voices as VO
    tts = VO.tts_for("calcopy")             # 흐름별 TTS 한 곳 — 칼카피 = 피쉬 차분한 해설가(완성본·회원 제작은 production = 타입캐스트)
    ask = TRIAL_ASK.format(dir=pdir, slug=b["slug"], style=b["style"], tts=json.dumps(tts, ensure_ascii=False),
                           source=(f"벤치 채널 {src['channel']} 에서 고른다(영상 주소 없이 만들기)" if src["channel"] else "회원이 준 영상이 있으면 그 영상, 없으면 shortem_make 가 내는 안내 그대로"),
                           again=(f"- 잡도리 {n}번째 고침 뒤 다시 만드는 편이다(고친 칸: {b.get('fixed_last')})." if n else ""))
    meta = {"kind": "member_task", "tool": "shortem_make", "preset": {"slug": b["slug"], "style": b["style"], "dir": pdir}, "source": src, "try": n,
            "purpose": "calcopy", "tts": tts}
    return {"review": [F._rv("bm_trial", ask, model=ASKS["bm_trial"]["model"], need=("work_dir", "ok"), meta=meta)], "then": "bm_trial_got"}


def _compare_do(st):
    b = st["bm"]
    n = int(st.get("pan_n") or 0)       # 시도 번호를 넣어 같은 입력 반복으로 오해받지 않게(flow._watch)
    return [{"id": "side", "cmd": "bm_side", "bench": b["videos"][0]["v360"], "ours": b["trial"], "try": n},
            {"id": "pan", "cmd": "bm_match", "slug": b["slug"], "style": b["style"], "work": b.get("trial_dir"), "line_reads": b.get("line_reads") or [],
             "eye": b.get("trial_eye"), "branch": (b.get("branch") or {}).get("branch"), "try": n}]


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
    b.pop("trial_frames", None)          # 새 시험 편 = 눈 판정도 새로(벤치 쪽 판정은 그대로)
    b.pop("trial_eye", None)
    st["log"].append(f"시험 편 받음: {wd}")
    return {"goto": "bm_trial_frames"}


def bm_trial_frames(st, m, rp, u):
    """시험 편 완성본 눈 판정 그림(벤치 편과 같은 실행기 명령·같은 창 = 벤치 줄판독 layout.window)."""
    b = st["bm"]
    lr = b.get("line_reads") or []
    v = {"id": "trial", "mp4": b["trial"], **({"win_doc": lr[0]} if lr else {})}
    return {"do": [{"id": "eye_t", "cmd": "bm_eye_frames", "videos": [v], "try": int(st.get("pan_n") or 0)}], "then": "bm_trial_eye"}


def bm_trial_eye(st, m, rp, u):
    b = st["bm"]
    if "eye_t" in m:
        got = _eye_frames_got(m["eye_t"], ["trial"])
        if got is None:
            raise _eye_stop("bm_eye_frames(시험 편): " + json.dumps(m["eye_t"], ensure_ascii=False, default=str)[:300], "bm_trial_frames")
        b["trial_frames"] = got["trial"]
    if not b.get("trial_frames"):
        raise _eye_stop("시험 편 눈 판정 그림 없음", "bm_trial_frames")
    return {"review": [_eye_rv("bm_eye_trial", b["trial_frames"])], "then": "bm_trial_eye_got"}


def bm_trial_eye_got(st, m, rp, u):
    b = st["bm"]
    e, errs = _eye_of(rp.get("bm_eye_trial"), b.get("trial_frames") or {})
    if errs:
        raise _eye_stop("시험 편 눈 판정 답 불합격: " + " / ".join(errs)[:300], "bm_trial_eye")
    b["trial_eye"] = e
    return {"do": _compare_do(st), "then": "bm_panbokki"}


def bm_compare(st, m, rp, u):
    """대조(bm_side·bm_match)만 다시 — 받은 시험 편(st.bm.trial_dir)을 그대로 쓴다. 시험 편이 없으면 만들기부터, 눈 판정이 없으면 그것부터."""
    F = _F()
    if not st["bm"].get("trial_dir"):
        raise F._Stop("시험 영상을 만들지 못했어요", "잠시 뒤 다시 해 주세요", retry="bm_trial", ask_member=True, detail="저장된 시험 편 없음")
    if not st["bm"].get("trial_eye"):
        return {"goto": "bm_trial_frames"}
    return {"do": _compare_do(st), "then": "bm_panbokki"}


def bm_panbokki(st, m, rp, u):
    """잡도리 — 어긋난 칸을 한 번에 한 칸씩. 고칠 값 고르기는 Jev(서버). 멈춤 = _pan_guard(같은 칸 REDO_STUCK 번 연속·총 상한)."""
    F = _F()
    from tools.calcopy.hybrid import jev_gate as J
    b = st["bm"]
    if (m.get("side") or {}).get("side"):
        b["side"] = m["side"]["side"]       # 확정 검사·최종 판정이 좌우 영상을 본다
    if (m.get("pan") or {}).get("error"):      # 대조를 못 했다 — 빈 대조표로 '맞춤'·'다시 재기'로 새지 않게 멈춘다
        raise _fail_stop([m["pan"]["error"]], "벤치와 맞춰 보지 못했어요", "잠시 뒤 다시 해 주세요", "bm_compare", ask_member=True)   # 도구 문제 — 같은 시험 편으로 대조만 다시(30~50분 재제작 금지)
    if m.get("pan"):
        b["pan_last"] = m["pan"]
    p = b.get("pan_last") or {}             # Jev 가 쉬어서 멈춘 뒤 다시 시도하면 직전 대조표로 이어 간다
    if p.get("match_ok"):
        return {"goto": "bm_confirm"}
    fails = p.get("fails") or b.get("fails") or []
    b["fails"] = fails
    back = bool(b.pop("pan_back", False))
    _pan_guard(st, fails, new=bool(m.get("pan")) or back)
    cands = p.get("cands") or []
    n = int(st.get("pan_n") or 0) + 1
    if len(cands) >= 2:
        try:
            d = J.decide(f"잡도리 {n}회차 — 벤치와 다른 칸 {fails[:5]}", [json.dumps(p, ensure_ascii=False)[:3000]],
                         [json.dumps(c, ensure_ascii=False) for c in cands])
        except J.JevDown as e:       # 서버 쪽 문제 — 회원 과제로 넘기지 않고(ask_member) 경보를 남기고 멈춘다
            st["alarm"] = {"kind": "jev_down", "why": str(e), "at": "bm_panbokki"}
            st["log"].append(f"경보: 벤치마킹 판단 서버(Jev) 실패 — {e}")
            raise F._Stop("잠시 판단 서버가 쉬고 있어요", "잠시 뒤 다시 해 주세요", retry="bm_panbokki", ask_member=True, detail=str(e))
        if not d["ok"]:      # 확신 없이 고르지 않는다 — 같은 표를 되풀이해 재지 않고 남은 칸과 함께 멈춘다
            st["log"].append(f"잡도리 {n}: 고를 칸 확신 부족(Jev {d['conf']}) → 멈춤")
            raise F._Stop("여기까지 맞췄어요", "남은 칸: " + ", ".join(map(str, fails)) + " — 이 부분은 직접 고쳐 주세요", final=True, detail=f"Jev 확신 부족 {d['conf']}")
        fix, why = cands[d["pick"]], f"Jev {d['conf']}"
    elif len(cands) == 1:
        fix, why = cands[0], "후보 하나"         # 고를 것이 없다 — 판단 없이 그대로
    else:       # 고칠 후보가 0개 — 같은 표를 다시 재도 같다(bm_match 는 덧붙임을 읽지 않는다). 첫 잡도리에서 바로 멈춘다
        raise F._Stop("여기까지 맞췄어요", "남은 칸: " + ", ".join(map(str, fails or ["눈 판정에서 어긋남"])) + " — 이 부분은 직접 고쳐 주세요", final=True, detail="고칠 후보 없음")
    st["pan_n"] = n
    st["log"].append(f"잡도리 {n}: {fix} ({why})")
    b["fixed_last"] = fix.get("path") if isinstance(fix, dict) else fix
    return {"do": [{"id": "fix", "cmd": "bm_fix", "slug": b["slug"], "style": b["style"], "fix": fix}], "then": "bm_trial"}     # 한 칸만 고치고 시험 편부터 다시


def _pan_guard(st, fails: list, new: bool) -> None:
    """(판단 주인 · 잡도리 멈춤) 새 대조표가 왔을 때만 센다(Jev 쉼 뒤 다시 시도는 같은 표라 안 셈).
    같은 실패 묶음 flow.REDO_STUCK 번 연속 → 멈춤 · 고친 횟수가 총 상한(첫 대조 실패 칸 수 × PAN_CAP_RATE, 최소 PAN_CAP_MIN) → 멈춤."""
    import math
    F = _F()
    b = st["bm"]
    if b.get("pan_cap") is None:
        b["pan_cap"] = max(PAN_CAP_MIN, math.ceil(len(fails) * PAN_CAP_RATE))
    hist = b.setdefault("pan_hist", [])
    if new:
        hist.append(sorted(map(str, fails)))
        del hist[:-F.REDO_STUCK]
    left = "남은 칸: " + ", ".join(map(str, fails or ["눈 판정에서 어긋남"])) + " — 이 부분은 직접 고쳐 주세요"
    if len(hist) >= F.REDO_STUCK and all(h == hist[-1] for h in hist[-F.REDO_STUCK:]):
        st["log"].append(f"잡도리: 같은 칸 {F.REDO_STUCK}번 연속 실패 {hist[-1]} → 멈춤")
        raise F._Stop("여기까지 맞췄어요", left, final=True, detail=f"같은 칸 {F.REDO_STUCK}번 연속 실패")
    if int(st.get("pan_n") or 0) >= b["pan_cap"]:
        st["log"].append(f"잡도리: 총 상한 {b['pan_cap']}번 → 멈춤")
        raise F._Stop("여기까지 맞췄어요", left, final=True, detail=f"잡도리 총 상한 {b['pan_cap']}번")


def _fable_call(st):
    """페이블 요청이 나가기 직전에 부른다 — 이미 FABLE_MAX 번 불렀으면 부르지 않고 「여기까지 맞췄어요」 멈춤(조용한 초과 금지). 센 값은 st["bm"]["fable_n"]."""
    F = _F()
    b = st["bm"]
    if int(b.get("fable_n") or 0) >= FABLE_MAX:
        raise F._Stop("여기까지 맞췄어요", "남은 칸: " + ", ".join(map(str, b.get("fails") or ["눈 판정에서 어긋남"])) + " — 이 부분은 직접 고쳐 주세요",
                      final=True, detail=f"강한 모델 확정 검사 {FABLE_MAX}번을 다 썼어요")
    b["fable_n"] = int(b.get("fable_n") or 0) + 1


def bm_confirm(st, m, rp, u):
    F = _F()
    b = st["bm"]
    _fable_call(st)
    ask = "판 확정 검사: 아래 고정 칸·편마다 칸 가르기가 벤치 편 전부와 맞는지 본다. 틀린 칸만 적는다.\n" + json.dumps(b.get("rules"), ensure_ascii=False)[:8000]
    return {"review": [F._rv("bm_confirm", ask, [F._img(b["side"])] if b.get("side") else [], model=ASKS["bm_confirm"]["model"], need=("ok", "wrong"))],
            "then": "bm_confirm_got"}


def _back_to_pan(st, wrong, why):
    """확정 검사·최종 판정이 틀렸다고 하면 잡도리로 되돌린다(고칠 후보가 없으면 잡도리가 바로 멈춘다).
    되돌림 횟수는 따로 세지 않는다 — 잡도리 멈춤 규칙(_pan_guard: 같은 칸 REDO_STUCK 번 연속·총 상한) 하나로 합쳤다(v1 §2-1 A2). 페이블 횟수는 FABLE_MAX(돈 상한)."""
    b = st["bm"]
    b["confirm_n"] = int(b.get("confirm_n") or 0) + 1
    b["fails"] = list(wrong or [])
    b["pan_last"] = {"match_ok": False, "fails": b["fails"], "cands": [], "why": why}
    b["pan_back"] = True
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
    _fable_call(st)
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
        raise _fail_stop([br.get("error") or br], "프리셋 묶음을 만들지 못했어요", "잠시 뒤 다시 해 주세요", "bm_brief", auto=True)
    return {"done": {"preset": {"slug": b["slug"], "style": b["style"], "name": b["name"], "zip": br["zip"], "other_styles": b.get("other_styles") or []}}}


PHASES = {"bm_setup": bm_setup, "bm_env_got": bm_env_got, "bm_fetch": bm_fetch, "bm_fetch_got": bm_fetch_got, "bm_tear": bm_tear, "bm_tear_got": bm_tear_got,
          "bm_skel": bm_skel, "bm_skel_got": bm_skel_got, "bm_read_got": bm_read_got,
          "bm_measure": bm_measure, "bm_measure_got": bm_measure_got, "bm_reread": bm_reread, "bm_trial": bm_trial, "bm_trial_got": bm_trial_got,
          "bm_eye_ask": bm_eye_ask, "bm_trial_frames": bm_trial_frames, "bm_trial_eye": bm_trial_eye, "bm_trial_eye_got": bm_trial_eye_got,
          "bm_compare": bm_compare, "bm_panbokki": bm_panbokki, "bm_confirm": bm_confirm, "bm_confirm_got": bm_confirm_got,
          "bm_verdict": bm_verdict, "bm_verdict_got": bm_verdict_got, "bm_brief": bm_brief, "bm_done": bm_done}
