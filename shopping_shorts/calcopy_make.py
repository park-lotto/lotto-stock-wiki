# -*- coding: utf-8 -*-
"""칼카피 만들기 입구 — "방구석 프리셋 · 내 팩 1번으로 만들어줘" (관제 097, 2026-10-16 사장님).

판단 주인: 이 모듈 하나. CLI(tools/calcopy/make.py)·보드 '만들기' 칸·API(/api/calcopy/make/*)는 여기 함수를 **부르기만** 한다.
  merge_preset_pack(preset, pack) → 제작 설정     프리셋 = 구조(틀 배치·변수 규칙·roles·rules·컷 리듬·source_kind)
                                                  내 팩  = 브랜드(채널명·색)·글꼴·자막 꼴·목소리·짤풀·효과음풀·BGM
  start(preset, pack, topic=None, ref_url=None)  → 세션(소재 후보 목록, 또는 topic/ref_url 이면 바로 작업)
  choose(sid, n)                                  → bench→score→assign→script→source→plan(--plan-only) → plan_review(사람)
  approve(sid) / reject(sid, 사유)                → produce(TTS 1회·렌더·대조) / 사유 적고 대본 다시 1회
  status(sid)                                     → 세션 상태·산출물
상태는 소재창고(calcopy_topics)의 같은 상태기계를 그대로 탄다 — 단계 실행은 worker.Worker 를 같은 프로세스 창구(LocalApi)로 돌린다
(워커 상시 가동과 같은 코드, 판단 두 벌 없음). 세션 원장 = DATA_DIR/calcopy/make/<sid>.json.

★재료 자동 초안(draft_materials)은 원래 remake 재료 조립의 자리 — remake 는 후보 시트·뼈대까지만 만들고 고르기를 사람에게 둔다.
  만들기 입구는 선검수 전 '초안'이 필요해 여기서 뼈대를 후보 순서대로 채우고 팩 기본값(효과음·짤·BGM)을 넣는다(엔진 담당에 이관 요청).
"""
from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from shopping_shorts import calcopy_topics as CT

ROOT = Path(__file__).resolve().parent.parent
REPO_PACKS = Path(__file__).resolve().parent / "calcopy_frame" / "my_packs.json"
LOCAL_PACKS = Path("C:/숏템_칼카피/packs/my_packs.json")
CHANNELS = ROOT / "tools" / "calcopy" / "engine" / "warehouse_channels.json"   # 채널 → 창고 카테고리(워커 가동표와 같은 파일)
AI_WORDS = re.compile(r"(\bai\b|에이아이|인공지능|합성|딥페이크|가짜 ?영상|생성형|ai로|ai 영상)", re.I)
N_CANDIDATES = 10
STEPS_TO_PLAN = ["bench", "score", "assign", "script", "source", "plan"]


class MakeError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.msg, self.code = msg, code


# ── 팩·프리셋 ──────────────────────────────────────────────────────────────
def packs_path() -> Path:
    """실파일: 로컬 C:/숏템_칼카피/packs(있으면) → 데이터 폴더(서버) → 저장소 기본값(읽기만)."""
    if LOCAL_PACKS.parent.is_dir():
        return LOCAL_PACKS
    return CT.base_dir() / "my_packs.json"


def load_packs() -> dict:
    for p in (packs_path(), REPO_PACKS):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_pack(n: str, patch: dict) -> dict:
    """보드 편집 칸(채널명 등) — 얕은 키별 병합. 저장소 파일은 안 건드린다(서버 git 파일 쓰기 = 자동배포 멈춤)."""
    packs = load_packs()
    if str(n) not in packs:
        raise MakeError(f"없는 팩: {n}", 404)
    cur = packs[str(n)]
    for k, v in (patch or {}).items():
        cur[k] = {**cur.get(k, {}), **v} if isinstance(v, dict) and isinstance(cur.get(k), dict) else v
    p = packs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(packs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return cur


def channels() -> dict:
    d = json.loads(CHANNELS.read_text(encoding="utf-8")) if CHANNELS.exists() else {}
    return {k: v for k, v in d.items() if not k.startswith("_")}


def list_presets() -> list[dict]:
    out = []
    for m in sorted(ROOT.glob("channel/*/preset/**/manifest.json")):
        try:
            man = json.loads(m.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out.append({"preset": m.parent.relative_to(ROOT).as_posix(), "slug": man.get("slug") or m.parts[-4],
                    "style": man.get("style") or m.parent.name, "source_kind": man.get("source_kind"),
                    "roles": len(man.get("roles") or []), "frame": (m.parent / "frame.json").exists()})
    return out


def _preset_dir(preset: str) -> Path:
    p = Path(preset)
    p = p if p.is_absolute() else ROOT / p
    if not (p / "manifest.json").exists():
        raise MakeError(f"프리셋 폴더에 manifest.json 이 없다: {preset}")
    return p


def _frames(frame: dict) -> list[dict]:
    return frame["frames"] if isinstance(frame.get("frames"), list) else [frame]


def merge_preset_pack(preset: str, pack: dict) -> dict:
    """판단 한 곳: 프리셋 구조 + 내 팩 키트 → 제작 설정. 틀 설명서에 brand/text 덮어쓰기, 제작 인자·재료 기본값에 tts/meme/sfx/bgm.
    바꾼 자리는 applied 에 한 줄씩(무엇을 무엇으로) — 계획.md·보드가 그대로 보여 준다."""
    pdir = _preset_dir(preset)
    man = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    frame = json.loads((pdir / "frame.json").read_text(encoding="utf-8")) if (pdir / "frame.json").exists() else None
    applied = []
    brand, text, cap = pack.get("brand") or {}, pack.get("text") or {}, (pack.get("text") or {}).get("caption") or {}
    if frame is not None:
        frame = copy.deepcopy(frame)
        old_names = {L.get("text") for fr in _frames(frame) for L in fr.get("layers", []) if L.get("kind") == "text" and L.get("role") == "brand" and L.get("text")}
        new_name = brand.get("channel_name")
        colors = brand.get("colors") or {}
        for fr in _frames(frame):
            fid = fr.get("id") or "frame"
            for L in fr.get("layers", []):
                if L.get("kind") == "text":
                    role = L.get("role")
                    if new_name and role == "brand":
                        applied.append(f"{fid} 채널명 '{L.get('text')}' → '{new_name}'"); L["text"] = new_name
                    elif new_name and isinstance(L.get("text"), str) and any(o and o in L["text"] for o in old_names):
                        before = L["text"]
                        for o in old_names:
                            L["text"] = L["text"].replace(o, new_name)
                        applied.append(f"{fid} 글 '{before}' → '{L['text']}'")
                    if role == "title" and text.get("title_font"):
                        applied.append(f"{fid} 제목 글꼴 {L.get('font')} → {text['title_font']}"); L["font"] = text["title_font"]
                    if role == "caption":
                        if text.get("caption_font"):
                            applied.append(f"{fid} 자막 글꼴 {L.get('font')} → {text['caption_font']}"); L["font"] = text["caption_font"]
                        if "outline_px" in cap:
                            L["outline"] = {"px": cap["outline_px"], "rgb": (L.get("outline") or {}).get("rgb") or [0, 0, 0]} if cap["outline_px"] else None
                            applied.append(f"{fid} 자막 외곽선 {cap['outline_px']}px")
                        if cap.get("enter"):
                            L["enter"] = None if cap["enter"] == "none" else cap["enter"]
                        if cap.get("emphasis"):
                            L["emphasis"] = None if cap["emphasis"] == "none" else cap["emphasis"]
                elif L.get("kind") == "band" and L.get("y") == 0 and (L.get("w") or 0) >= 1000 and colors.get("header") is not None:
                    c = colors["header"]
                    c = c.get(fid) if isinstance(c, dict) else c
                    if c:
                        applied.append(f"{fid} 머리 띠 색 {L.get('rgb')} → {c}"); L["rgb"] = list(c)
    tts, bgm = pack.get("tts") or {}, pack.get("bgm") or {}
    remake_args = {}
    if tts.get("voice_id"):
        remake_args["voice"] = tts["voice_id"]
    if tts.get("tempo"):
        remake_args["tempo"] = tts["tempo"]
    if cap.get("mode"):
        remake_args["caption_mode"] = cap["mode"]
    if bgm.get("candidates"):
        remake_args["bgm"] = bgm["candidates"][0]
    if bgm.get("gain") is not None:
        remake_args["bgm_ratio"] = bgm["gain"]
    applied += [f"제작 인자 {k}={v}" for k, v in remake_args.items()]
    defaults = {"sfx_pool": pack.get("sfx_pool") or {}, "meme_pool": pack.get("meme_pool") or {}, "bgm": bgm,
                "tts": tts, "caption": cap}
    man2 = {**man, "made_from": {"preset": str(pdir.relative_to(ROOT).as_posix() if pdir.is_relative_to(ROOT) else pdir), "pack": pack.get("name")},
            "pack_applied": applied}
    return {"manifest": man2, "frame": frame, "remake_args": remake_args, "materials_defaults": defaults, "applied": applied}


def write_merged(cfg: dict, dst: Path) -> Path:
    """합친 설정을 프리셋 폴더 꼴로 쓴다 — worker_steps·remake 가 보통 프리셋처럼 읽는다(manifest.json + frame.json + make.json)."""
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "manifest.json").write_text(json.dumps(cfg["manifest"], ensure_ascii=False, indent=1), encoding="utf-8")
    if cfg["frame"] is not None:
        (dst / "frame.json").write_text(json.dumps(cfg["frame"], ensure_ascii=False, indent=1), encoding="utf-8")
    (dst / "make.json").write_text(json.dumps({k: cfg[k] for k in ("remake_args", "materials_defaults", "applied")}, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    return dst


def _pack_assets() -> dict:
    p = Path("C:/숏템_칼카피/packs/packs_manifest.json")
    if not p.exists():
        return {}
    return {a["id"]: a for a in json.loads(p.read_text(encoding="utf-8"))}


def draft_materials(skel: dict, defaults: dict, assets: dict | None = None) -> dict:
    """뼈대 → 재료 자동 초안(선검수용): 컷마다 후보 영상 순서대로 + 팩 기본값(효과음 시작·끝, 짤 후보, BGM). 사람이 계획을 보고 고친다."""
    assets = assets if assets is not None else _pack_assets()
    M = copy.deepcopy(skel)
    cand = sorted(Path(M.get("cand_dir") or ".").glob("v_*.mp4")) if M.get("cand_dir") else []
    for k, s in enumerate(M.get("shots") or []):
        if not s.get("src") and cand:
            s.update(src=cand[k % len(cand)].name, ss=round(float(s.get("t0") or 0) % 20, 2), status="draft",
                     why="자동 초안(만들기 입구) — 후보 순서대로, 선검수에서 사람이 고침")
    pools = defaults.get("sfx_pool") or {}

    def sfx(aid, t, why):
        a = assets.get(aid) or {}
        f = a.get("file")
        return {"file": f"C:/숏템_칼카피/packs/sfx/{f}" if f else None, "asset_id": aid, "title": a.get("title"), "t": t, "db": 0, "why": why}
    M["sfx"] = ([sfx(pools["start"][0], 0.0, "팩 효과음(시작)")] if pools.get("start") else []) + \
               ([sfx(pools["end"][0], "end-0.2", "팩 효과음(끝)")] if pools.get("end") else [])
    M["sfx_pool"], M["meme_pool"] = pools, defaults.get("meme_pool") or {}
    M["bgm"], M["tts"], M["caption_style"] = defaults.get("bgm") or {}, defaults.get("tts") or {}, defaults.get("caption") or {}
    M["_note"] = "만들기 입구 자동 초안 — 팩 기본값(효과음·짤 후보·BGM·목소리) 주입, 컷 선택은 선검수에서 확정"
    return M


# ── 같은 프로세스 창구: worker.Worker 가 HTTP 대신 calcopy_topics 를 바로 부른다 ─────────────────
class LocalApi:
    def __init__(self, data_dir=None):
        self.d = data_dir

    def _wrap(self, fn, *a, **k):
        from tools.calcopy.engine.worker import ApiError
        try:
            return fn(*a, data_dir=self.d, **k)
        except CT.TopicError as e:
            raise ApiError(e.code, e.msg) from None

    def _req(self, method, path, **kw):        # Worker._dedupe·requeue_old 가 쓰는 GET 보드
        from urllib.parse import parse_qs, urlparse
        q = {k: v[0] for k, v in parse_qs(urlparse(path).query).items()}
        return self._wrap(CT.board, state=q.get("state"), category=q.get("category"), limit=int(q.get("limit", 300)))

    def claim_next(self, worker, steps, category=None, track=None, channel=None):
        return self._wrap(CT.claim_next, worker, steps, category=category, track=track, channel=channel)

    def claim(self, tid, worker, step):
        return self._wrap(CT.claim, tid, worker, step)

    def add(self, name, category, track, source=None, by=""):
        return {"topic": self._wrap(CT.add, name, category, track, source=source, by=by)}

    def heartbeat(self, tid, worker, doing=None):
        return self._wrap(CT.heartbeat, tid, worker, doing)

    def worker_heartbeat(self, worker, category=None, track=None, channel=None, doing=None, idle_reason=None, last_error=None):
        return self._wrap(CT.worker_heartbeat, worker, category=category, track=track, channel=channel, doing=doing,
                          idle_reason=idle_reason, last_error=last_error)

    def detail(self, tid):
        return self._wrap(CT.detail, tid)

    def advance(self, tid, worker, data=None, outputs=None, cost=None, note=""):
        return {"topic": self._wrap(CT.advance, tid, worker, data=data, outputs=outputs, cost=cost, note=note)}

    def release(self, tid, worker, error, count=True):
        return {"topic": self._wrap(CT.release, tid, worker, error, count=count)}

    def reject(self, tid, reason, back_to=None, by="worker"):
        return {"topic": self._wrap(CT.reject, tid, reason, back_to=back_to, by=by)}

    def upload(self, tid, name, path):
        return self._wrap(CT.save_upload, tid, name, Path(path).read_bytes())


# ── 세션 ─────────────────────────────────────────────────────────────────
def _sdir(data_dir=None) -> Path:
    d = CT.base_dir(data_dir) / "make"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(S: dict, data_dir=None) -> dict:
    S["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (_sdir(data_dir) / f"{S['sid']}.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    return S


def _load(sid: str, data_dir=None) -> dict:
    p = _sdir(data_dir) / f"{sid}.json"
    if not re.fullmatch(r"[0-9a-f]{8,32}", sid or "") or not p.exists():
        raise MakeError(f"없는 세션: {sid}", 404)
    return json.loads(p.read_text(encoding="utf-8"))


def _category(slug: str) -> str:
    c = channels().get(slug) or {}
    return c.get("category") or slug


def _ai_suspect(tid, data_dir=None) -> int | None:
    p = CT.topic_dir(tid, data_dir) / "벤치.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return sum(1 for v in d.get("videos") or [] for c in v.get("comments") or [] if AI_WORDS.search(str(c.get("text") or "")))


def _candidate(t: dict, data_dir=None) -> dict:
    sc, b = t.get("score") or {}, t.get("bench") or {}
    twist = next((p.get("text") for p in b.get("points") or [] if p.get("kind") == "twist"), None)
    return {"id": t["id"], "title": t["name"], "state": t["state"], "line": sc.get("angle") or b.get("best_angle") or "",
            "scores": {k: v.get("score") for k, v in (sc.get("criteria") or {}).items()}, "total": sc.get("total"),
            "bench_videos": b.get("n_videos"), "sources": [u for u in [(t.get("source") or {}).get("url")] if u],
            "twist": twist, "ai_suspect_comments": _ai_suspect(t["id"], data_dir), "engine_ver": sc.get("engine_ver") or (t.get("source") or {}).get("engine_ver")}


def _new_session(preset, pack_no, cfg, data_dir=None) -> dict:
    sid = uuid.uuid4().hex[:12]
    mdir = _sdir(data_dir) / sid / "preset"
    write_merged(cfg, mdir)
    return {"sid": sid, "preset": preset, "pack": str(pack_no), "merged_preset": str(mdir), "applied": cfg["applied"],
            "slug": cfg["manifest"].get("slug"), "state": "new", "log": [], "topic_id": None, "candidates": [], "rewrites": 0}


def start(preset: str, pack: str | int = "1", topic: str | None = None, ref_url: str | None = None, data_dir=None, deps: dict | None = None) -> dict:
    """후보 목록(창고 found~scored 상위 10, 모자라면 그 자리에서 찾기) — topic/ref_url 이 오면 후보를 건너뛰고 바로 작업."""
    deps = deps or {}
    packs = load_packs()
    if str(pack) not in packs:
        raise MakeError(f"없는 팩 번호: {pack} — {sorted(packs)}")
    cfg = merge_preset_pack(preset, packs[str(pack)])
    S = _new_session(preset, pack, cfg, data_dir)
    cat = _category(S["slug"])
    S["category"] = cat
    if topic or ref_url:
        src, facts = {"via": "사장님"}, None
        if ref_url:
            facts, title = (deps.get("ref_facts") or ref_facts)(ref_url)
            src = {"via": "참고 URL", "url": ref_url}
            topic = topic or title
        t = CT.add(topic, cat, "bench", source=src, by="만들기 입구", data_dir=data_dir)
        if facts:
            fp = _sdir(data_dir) / S["sid"] / "facts.json"
            fp.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
            S["facts_path"] = str(fp)
        S.update(topic_id=t["id"], state="queued", candidates=[_candidate(t, data_dir)])
        _save(S, data_dir)
        return choose(S["sid"], 1, data_dir=data_dir, deps=deps)
    S["candidates"] = (deps.get("candidates") or candidates)(S, data_dir=data_dir, deps=deps)
    S["state"] = "candidates"
    return _save(S, data_dir)


def candidates(S: dict, data_dir=None, deps: dict | None = None) -> list[dict]:
    rows = [t for t in CT.board(category=S["category"], limit=2000, data_dir=data_dir)["topics"] if t["state"] in ("found", "benched", "scored")]
    if len(rows) < N_CANDIDATES:                       # 모자라면 그 자리에서 찾기(검색만 — 제미나이 0, 유튜브는 장부 한도 뒤)
        w = _worker(S, data_dir, deps)
        w.find_every = 1
        w.find()
        rows = [t for t in CT.board(category=S["category"], limit=2000, data_dir=data_dir)["topics"] if t["state"] in ("found", "benched", "scored")]
    rows.sort(key=lambda t: -((t.get("score") or {}).get("total") or -1))
    return [{"n": i + 1, **_candidate(t, data_dir)} for i, t in enumerate(rows[:N_CANDIDATES])]


def ref_facts(url: str) -> tuple[dict, str]:
    """참고 영상 → 근거(제목·설명·댓글 상위). 받아쓰기는 아직 안 붙였다(무료 받아쓰기 도구 연결은 다음 단계)."""
    from tools.calcopy.engine import topic_find as TF
    vid = re.search(r"(?:shorts/|v=|youtu\.be/)([\w-]{11})", url)
    if not vid:
        raise MakeError(f"유튜브 영상 주소가 아니다: {url}")
    d = TF.yt_detail(vid.group(1), 30)
    if d.get("failed"):
        raise MakeError(f"참고 영상 못 읽음: {d['failed'][:200]}")
    facts = {"r1": {"text": f"(참고 영상 제목) {d.get('title')}", "url": url}}
    for i, line in enumerate([x.strip() for x in (d.get("description") or "").splitlines() if len(x.strip()) >= 8][:5], 2):
        facts[f"r{i}"] = {"text": f"(설명) {line}", "url": url}
    for j, c in enumerate((d.get("comments") or [])[:5], 1):
        facts[f"rc{j}"] = {"text": f"(댓글 좋아요 {c.get('likes')}) {c.get('text', '')[:120]}", "url": url}
    return facts, (d.get("title") or "")[:80]


def _worker(S: dict, data_dir=None, deps: dict | None = None):
    from tools.calcopy.engine.worker import Worker
    deps = deps or {}
    extra = {}
    if S.get("facts_path"):
        extra["facts_path"] = S["facts_path"]
    mk = json.loads((Path(S["merged_preset"]) / "make.json").read_text(encoding="utf-8"))
    extra["remake_args"] = mk["remake_args"]
    chn = channels().get(S["slug"]) or {}
    if chn.get("keywords"):
        extra["keywords"] = chn["keywords"]           # 찾기 검색 명사 — 워커 가동표와 같은 파일
    if chn.get("source_kind"):
        extra["source_kind"] = chn["source_kind"]
    extra["materials_hook"] = lambda skel: draft_materials(skel, mk["materials_defaults"], deps.get("assets"))
    w = Worker(deps.get("api") or LocalApi(data_dir), S["category"], "bench", S["slug"], name=f"make-{S['sid']}",
               out_root=_sdir(data_dir) / S["sid"] / "work", steps=deps.get("steps") or __import__("tools.calcopy.engine.worker_steps", fromlist=["x"]),
               preset=S["merged_preset"], find_every=0, log=lambda m: S["log"].append(m), extra=extra, ledger=bool(deps.get("ledger", True)))
    if deps.get("run"):
        w.ctx.run = deps["run"]
    return w


def _run_until(S: dict, target_states: tuple, data_dir=None, deps=None, max_ticks: int = 12):
    w = _worker(S, data_dir, deps)
    w.only_topic = S["topic_id"]
    for _ in range(max_ticks):
        t = CT.detail(S["topic_id"], data_dir=data_dir)["topic"]
        if t["state"] in target_states:
            return t, None
        r = w.tick()
        if r["result"] not in ("advanced",):
            return CT.detail(S["topic_id"], data_dir=data_dir)["topic"], r.get("error") or str(r.get("reasons"))
    return CT.detail(S["topic_id"], data_dir=data_dir)["topic"], f"{max_ticks}단계 안에 {target_states} 못 감"


def _bg(S, fn, data_dir, deps):
    def run():
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — 세션에 이유로 남긴다(조용한 실패 금지)
            S2 = _load(S["sid"], data_dir)
            S2.update(state="failed", error=f"{type(e).__name__}: {e}")
            _save(S2, data_dir)
    if (deps or {}).get("sync"):
        run()
    else:
        threading.Thread(target=run, daemon=True, name=f"make-{S['sid']}").start()


def choose(sid: str, n: int, data_dir=None, deps: dict | None = None) -> dict:
    S = _load(sid, data_dir)
    if not S.get("topic_id"):
        c = next((c for c in S["candidates"] if c.get("n") == int(n)), None)
        if not c:
            raise MakeError(f"후보 {n} 없음")
        S["topic_id"] = c["id"]
    S["state"] = "working"
    _save(S, data_dir)

    def job():
        S2 = _load(sid, data_dir)
        t, err = _run_until(S2, ("plan_review",), data_dir, deps)
        S3 = _load(sid, data_dir)
        S3["log"] = S2["log"]
        S3.update(state="plan_review" if t["state"] == "plan_review" else "stopped", error=err, topic_state=t["state"])
        _save(S3, data_dir)
    _bg(S, job, data_dir, deps)
    return _load(sid, data_dir)


def approve(sid: str, data_dir=None, deps: dict | None = None) -> dict:
    S = _load(sid, data_dir)
    t = CT.detail(S["topic_id"], data_dir=data_dir)["topic"]
    if t["state"] != "plan_review":
        raise MakeError(f"선검수 자리가 아니다(지금 {t['state']})", 409)
    CT.review(S["topic_id"], "plan_review", "pass", by="만들기 입구", data_dir=data_dir)
    S["state"] = "producing"
    _save(S, data_dir)

    def job():
        S2 = _load(sid, data_dir)
        t2, err = _run_until(S2, ("final_review",), data_dir, deps)
        S3 = _load(sid, data_dir)
        S3["log"] = S2["log"]
        S3.update(state="final_review" if t2["state"] == "final_review" else "stopped", error=err, topic_state=t2["state"])
        _save(S3, data_dir)
    _bg(S, job, data_dir, deps)
    return _load(sid, data_dir)


def reject(sid: str, reason: str, data_dir=None, deps: dict | None = None) -> dict:
    """반려 = 사유를 적고 대본부터 다시 1회(대본→재료→계획). 두 번째 반려는 폐기."""
    if not (reason or "").strip():
        raise MakeError("반려 사유가 필요하다")
    S = _load(sid, data_dir)
    again = S.get("rewrites", 0) < 1
    CT.review(S["topic_id"], "plan_review", "reject", by="만들기 입구", reason=reason, back_to="assigned" if again else None, data_dir=data_dir)
    S.setdefault("rejects", []).append(reason)
    if not again:
        S["state"] = "rejected"
        return _save(S, data_dir)
    S["rewrites"] = S.get("rewrites", 0) + 1
    S["state"] = "working"
    _save(S, data_dir)
    return choose(sid, 0, data_dir=data_dir, deps=deps)


def status(sid: str, data_dir=None) -> dict:
    S = _load(sid, data_dir)
    if S.get("topic_id"):
        d = CT.detail(S["topic_id"], data_dir=data_dir)
        S["topic"], S["files"] = d["topic"], d["files"]
    return S


def sessions(limit: int = 20, data_dir=None) -> list[dict]:
    """최근 세션(보드 '만들기' 칸 목록)."""
    out = []
    for p in sorted(_sdir(data_dir).glob("*.json"), key=lambda p: -p.stat().st_mtime)[:limit]:
        try:
            S = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out.append({k: S.get(k) for k in ("sid", "preset", "pack", "state", "topic_id", "updated_at", "error")})
    return out

