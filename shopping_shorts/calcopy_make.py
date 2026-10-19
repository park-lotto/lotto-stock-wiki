# -*- coding: utf-8 -*-
"""칼카피 만들기 입구 — "방구석 프리셋 · 내 팩 1번으로 만들어줘" (관제 097, 2026-10-16 사장님).

판단 주인: 이 모듈 하나. CLI(tools/calcopy/make.py)·보드 '만들기' 칸·API(/api/calcopy/make/*)는 여기 함수를 **부르기만** 한다.
  merge_preset_pack(preset, pack) → 제작 설정     프리셋 = 구조(틀 배치·변수 규칙·roles·rules·컷 리듬·source_kind)
                                                  내 팩  = 브랜드(채널명·색)·글꼴·자막 꼴·목소리·짤풀·효과음풀·BGM
  start(preset, pack, topic=None, ref_url=None)  → 세션(소재 후보 목록, 또는 topic/ref_url 이면 바로 작업)
  choose(sid, n)                                  → bench→score→assign→script→source→plan(--plan-only) → plan_review(사람)
  approve(sid, by) / reject(sid, 사유)            → produce(TTS 1회·렌더·대조, by = 관리자만) / 사유 적고 대본 다시 1회
  status(sid)                                     → 세션 상태·산출물
  start(..., reuse_of=tid)                        → 응용 모드: 소재 1 : 제작물 N(벤치·점수는 원 소재 것을 그대로 — 제미나이 0)
  distinct(a, b)                                  → 응용 중복 판정 한 곳: 목소리·틀·컷(≥50%) 중 둘 이상 달라야
  check_pack(pack)                                → 내 팩 키트의 파일(효과음·짤·BGM·프리셋·목소리)이 실제로 있나
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
ADMINS = ("페이블", "사장님", "관리자")            # approve(TTS·렌더 = 돈·시간) 는 이 이름만 — API 는 관리자 세션이 "관리자"로 부른다
# 고객 PC 모드(관제 234): 고객 설치팩이 CALCOPY_CUSTOMER_MODE=1 로 띄운다 — TTS·렌더 비용이 고객 본인 키·PC 라 고객("고객")이 사인한다.
CUSTOMER_MODE = os.environ.get("CALCOPY_CUSTOMER_MODE") == "1"
CUSTOMER = "고객"
PACK_ROOT = Path("C:/숏템_칼카피/packs")
VOICES = ROOT / "shopping_shorts" / "assets" / "voice_presets.json"
CUT_DIFF_MIN = 0.5                                 # 응용: 컷(재료 영상·초)이 이 비율 이상 달라야 '컷 다름'
MADE_STATES = ("plan_review", "producing", "final_review", "passed")


class MakeError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.msg, self.code = msg, code


# ── 팩·프리셋 ──────────────────────────────────────────────────────────────
def packs_path() -> Path:
    """실파일: CALCOPY_PACKS(고객 PC — 숏템 웹 프로필에서 만든 팩) → 로컬 C:/숏템_칼카피/packs(있으면) → 데이터 폴더(서버) → 저장소 기본값(읽기만)."""
    if os.environ.get("CALCOPY_PACKS"):
        return Path(os.environ["CALCOPY_PACKS"])
    if LOCAL_PACKS.parent.is_dir():
        return LOCAL_PACKS
    return CT.base_dir() / "my_packs.json"


def load_packs(raw: bool = False) -> dict:
    """팩 번호 → 키트. '_' 로 시작하는 키(_schema 설명)는 빼고 준다(raw=True 면 그대로 — 저장용)."""
    for p in (packs_path(), REPO_PACKS):
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            return d if raw else {k: v for k, v in d.items() if not k.startswith("_")}
    return {}


def save_pack(n: str, patch: dict) -> dict:
    """보드 편집 칸(채널명 등) — 얕은 키별 병합. 저장소 파일은 안 건드린다(서버 git 파일 쓰기 = 자동배포 멈춤)."""
    packs = load_packs(raw=True)
    if str(n).startswith("_") or str(n) not in packs:
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
                    if role == "title" and text.get("title_font") and L.get("font") != text["title_font"]:
                        applied.append(f"{fid} 제목 글꼴 {L.get('font')} → {text['title_font']}"); L["font"] = text["title_font"]
                    if role == "caption":
                        if text.get("caption_font") and L.get("font") != text["caption_font"]:
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


def _pack_assets(manifest: str | Path | None = None) -> dict:
    p = Path(manifest) if manifest else PACK_ROOT / "packs_manifest.json"
    if not p.exists():
        return {}
    return {a["id"]: a for a in json.loads(p.read_text(encoding="utf-8"))}


def asset_file(a: dict, pool_dir: str | Path | None = None, kind: str = "sfx") -> Path | None:
    """팩 자산 → 로컬 파일 경로(판단 한 곳). 효과음은 media_path 의 scene_assets/ 뒤 하위 경로까지(sfx_pick/sfx_13.mp3 —
    파일명만 붙이면 없는 경로가 된다, 10-16 실측 1459·1473), 짤은 짤 폴더/파일명."""
    f = (a or {}).get("file")
    if not f:
        return None
    if kind == "sfx":
        mp = str(a.get("media_path") or "").replace("\\", "/")
        sub_ = mp.split("scene_assets/", 1)[1] if "scene_assets/" in mp else f
        return Path(pool_dir or PACK_ROOT / "sfx") / sub_
    return Path(pool_dir or PACK_ROOT / "meme" / "meme_pack") / f


def _voices() -> dict:
    try:
        return {v["base_voice_id"]: v["name"] for v in json.loads(VOICES.read_text(encoding="utf-8"))}
    except (OSError, ValueError, KeyError):
        return {}


def check_pack(pack: dict, assets: dict | None = None) -> dict:
    """내 팩 키트 점검 — 적힌 파일이 실제로 있나(효과음·짤·BGM·기본 프리셋·목소리 이름). 없으면 missing 에 한 줄씩."""
    sp, mp, bgm, tts = pack.get("sfx_pool") or {}, pack.get("meme_pool") or {}, pack.get("bgm") or {}, pack.get("tts") or {}
    assets = assets if assets is not None else _pack_assets(sp.get("manifest") or mp.get("manifest"))
    missing, n = [], {"sfx": 0, "meme": 0, "bgm": 0, "voices": 0}
    for slot in ("start", "point", "end"):
        for aid in sp.get(slot) or []:
            f = asset_file(assets.get(aid) or {}, sp.get("dir"), "sfx")
            n["sfx"] += 1
            if not f or not f.exists():
                missing.append(f"효과음 {slot} #{aid}: {f or '목록에 없음'}")
    for aid in mp.get("ids") or []:
        f = asset_file(assets.get(aid) or {}, mp.get("dir"), "meme")
        n["meme"] += 1
        if not f or not f.exists():
            missing.append(f"짤 #{aid}: {f or '목록에 없음'}")
    lib = Path(bgm.get("lib") or "shopping_shorts/assets/bgm_lib")
    lib = lib if lib.is_absolute() else ROOT / lib
    for name in bgm.get("candidates") or []:
        n["bgm"] += 1
        if not (lib / f"{name}.mp3").exists():
            missing.append(f"BGM {name}: {lib / (name + '.mp3')}")
    names = _voices()
    for v in [tts] + list(tts.get("alternates") or []):
        if v.get("voice_id"):
            n["voices"] += 1
            if names and names.get(v["voice_id"]) != v.get("name"):
                missing.append(f"목소리 {v.get('name')} {v['voice_id']}: voice_presets 이름 {names.get(v['voice_id'])!r}")
    if pack.get("base_preset") and not (ROOT / pack["base_preset"] / "manifest.json").exists():
        missing.append(f"기본 프리셋 없음: {pack['base_preset']}")
    return {"ok": not missing, "missing": missing, "counts": n}


def draft_materials(skel: dict, defaults: dict, assets: dict | None = None) -> dict:
    """뼈대 → 재료 자동 초안 — 판단 주인은 remake.draft_materials(10-16 이관: 재료 조립 = remake 담당). 여기선 팩 자산 창구만 넘긴다."""
    from tools.calcopy.engine import remake as RM
    return RM.draft_materials(skel, defaults, assets if assets is not None else _pack_assets(), asset_file)


RESULTS = ROOT / "channel" / "결과물.json"


def results() -> dict:
    """통과작 목록(결과물 탭) — channel/결과물.json 한 파일. 파일이 이 컴퓨터에 있나(exists)만 덧붙인다."""
    if not RESULTS.exists():
        return {"items": [], "error": f"없음: {RESULTS}"}
    d = json.loads(RESULTS.read_text(encoding="utf-8"))
    for it in d.get("items") or []:
        it["exists"] = bool(it.get("path")) and Path(it["path"]).exists()
    return d


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
            "slug": cfg["manifest"].get("slug"), "state": "new", "log": [], "topic_id": None, "candidates": [], "rewrites": 0,
            "mode": "new", "root_topic": None}


def _patched(pack: dict, patch: dict | None) -> dict:
    """세션 한 번만 쓰는 팩 덮어쓰기(응용 때 목소리만 바꾸기 등) — 원본 팩은 안 바뀐다(깊은 복사)."""
    out = copy.deepcopy(pack)
    for k, v in (patch or {}).items():
        out[k] = {**(out.get(k) or {}), **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def _norm_facts(facts) -> dict:
    """사장님이 준 근거(기사) → 엔진 facts 꼴 {id: {text, url, date?}}. 목록이면 f1.. 로 번호. 파일 경로도 받는다."""
    if not facts:
        return {}
    if isinstance(facts, (str, Path)) and Path(facts).exists():
        facts = json.loads(Path(facts).read_text(encoding="utf-8"))
    if isinstance(facts, list):
        facts = {f"f{i}": x for i, x in enumerate(facts, 1)}
    if not isinstance(facts, dict) or not all(isinstance(v, dict) and v.get("text") for v in facts.values()):
        raise MakeError("facts 는 {id: {text, url, date}} 또는 [{text, url, date}] 꼴이어야 한다")
    return facts


def start(preset: str, pack: str | int = "1", topic: str | None = None, ref_url: str | None = None, data_dir=None, deps: dict | None = None,
          facts=None, reuse_of: int | None = None, pack_patch: dict | None = None) -> dict:
    """후보 목록(창고 found~scored 상위 10, 모자라면 그 자리에서 찾기) — topic/ref_url 이 오면 후보를 건너뛰고 바로 작업.
    facts = 사장님이 준 근거(기사 URL·날짜·발췌) — 제품비하인드 기사 관문용. reuse_of = 응용(이미 만든 소재로 다른 벌).
    pack_patch = 이 세션만 팩 일부 바꾸기(예: {"tts": {"voice_id": …, "name": …}})."""
    deps = deps or {}
    packs = load_packs()
    if str(pack) not in packs:
        raise MakeError(f"없는 팩 번호: {pack} — {sorted(packs)}")
    pk = _patched(packs[str(pack)], pack_patch)
    cfg = merge_preset_pack(preset, pk)
    S = _new_session(preset, pack, cfg, data_dir)
    if pack_patch:
        S["pack_patch"] = pack_patch
    cat = _category(S["slug"])
    S["category"] = cat
    if reuse_of:
        return _start_reuse(S, int(reuse_of), data_dir, deps)
    facts = _norm_facts(facts)
    if topic or ref_url:
        src = {"via": "사장님"}
        if ref_url:
            f2, title = (deps.get("ref_facts") or ref_facts)(ref_url)
            facts = {**f2, **facts}
            src = {"via": "참고 URL", "url": ref_url}
            topic = topic or title
        if facts:
            src["facts_n"] = len(facts)
        t = CT.add(topic, cat, "bench", source=src, by="만들기 입구", data_dir=data_dir)
        if facts:
            fp = _sdir(data_dir) / S["sid"] / "facts.json"
            fp.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
            S["facts_path"] = str(fp)
        S.update(topic_id=t["id"], root_topic=t["id"], state="queued", candidates=[_candidate(t, data_dir)])
        _save(S, data_dir)
        return choose(S["sid"], 1, data_dir=data_dir, deps=deps)
    S["candidates"] = (deps.get("candidates") or candidates)(S, data_dir=data_dir, deps=deps)
    S["state"] = "candidates"
    return _save(S, data_dir)


PRESCORE_N = int(os.environ.get("CALCOPY_PRESCORE_N") or 5)
PRESCORE_MIN = int(os.environ.get("CALCOPY_PRESCORE_MIN") or 3)     # 이만큼 점수 난 후보가 모일 때까지
PRESCORE_ROUNDS = int(os.environ.get("CALCOPY_PRESCORE_ROUNDS") or 3)  # 찾기를 더 돌리는 상한(바퀴)


def _prescore(S: dict, rows: list[dict], data_dir=None, deps=None) -> list[dict]:
    """고객 PC 모드(관제 234): 고객 PC 창고에는 미리 돌아 둔 워커가 없다 — 찾기만 된(found) 후보를 그대로 보이면
    점수 없는 시사 뉴스가 섞인다(10-19 실측: 빈 창고에서 '스벅 일베놀이 근황'·KNN 뉴스가 점수 없이 후보로).
    그래서 같은 워커 단계(bench→score)로 점수를 매기고, **점수가 난 것만** 보여 준다(bench 가 '무관 영상'으로 거른 것은 뺀다).
    모자라면 찾기를 PRESCORE_ROUNDS 바퀴까지 더 돈다. AI 는 후보당 2건(고객 Claude)."""
    failed: set = set()
    log = S.setdefault("log", [])

    def live():
        return [t for t in CT.board(category=S["category"], limit=2000, data_dir=data_dir)["topics"]
                if t["state"] in ("found", "benched", "scored") and not t.get("stalled") and t["id"] not in failed]
    for rnd in range(PRESCORE_ROUNDS + 1):
        cur = live()
        if sum(1 for t in cur if t["state"] == "scored") >= PRESCORE_MIN:
            break
        todo = [t for t in cur if t["state"] in ("found", "benched")][:PRESCORE_N]
        if not todo:
            if rnd == PRESCORE_ROUNDS:
                break
            w = _worker(S, data_dir, deps)
            w.find_every = 1
            w.find()
            log.append(f"[후보 점수] {rnd + 1}바퀴: 점수 난 후보가 {PRESCORE_MIN}개 미만 — 소재를 더 찾았다")
            continue
        for t in todo:
            S2 = {**S, "topic_id": t["id"], "log": log}
            t2, err = _run_until(S2, ("scored",), data_dir, deps, max_ticks=3)
            if err or t2["state"] != "scored":
                failed.add(t["id"])
                log.append(f"[후보 점수] #{t['id']} 뺌: {str(err)[:160]}")
    return [t for t in live() if t["state"] == "scored"]


def candidates(S: dict, data_dir=None, deps: dict | None = None) -> list[dict]:
    rows = [t for t in CT.board(category=S["category"], limit=2000, data_dir=data_dir)["topics"] if t["state"] in ("found", "benched", "scored") and not t.get("stalled")]
    if len(rows) < N_CANDIDATES:                       # 모자라면 그 자리에서 찾기(검색만 — 제미나이 0, 유튜브는 장부 한도 뒤)
        w = _worker(S, data_dir, deps)
        w.find_every = 1
        w.find()
        rows = [t for t in CT.board(category=S["category"], limit=2000, data_dir=data_dir)["topics"]
                if t["state"] in ("found", "benched", "scored") and not t.get("stalled")]     # 멈춘(stalled) 소재는 골라도 못 돈다
    if CUSTOMER_MODE:
        rows = _prescore(S, rows, data_dir, deps)
    rows.sort(key=lambda t: -((t.get("score") or {}).get("total") or -1))
    made = made_counts(data_dir)
    return [{"n": i + 1, **_candidate(t, data_dir), "made": made.get(t["id"], 0)} for i, t in enumerate(rows[:N_CANDIDATES])]


# ── 응용 모드(소재 1 : 제작물 N) ─────────────────────────────────────────────
def _all_sessions(data_dir=None) -> list[dict]:
    out = []
    for p in _sdir(data_dir).glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return out


def made_counts(data_dir=None) -> dict:
    """원 소재 id → 그 소재로 계획(선검수) 이상 간 제작물 수. 후보 표의 '새로 / 응용 n' 표시."""
    out: dict = {}
    for S in _all_sessions(data_dir):
        if S.get("root_topic") and S.get("state") in MADE_STATES:
            out[S["root_topic"]] = out.get(S["root_topic"], 0) + 1
    return out


def reusable(data_dir=None) -> list[dict]:
    """응용할 수 있는 소재 = 계획까지 간 제작물이 있는 원 소재(보드 '응용' 목록)."""
    rows = []
    for tid, n in sorted(made_counts(data_dir).items(), key=lambda kv: -kv[1]):
        try:
            t = CT.detail(tid, data_dir=data_dir)["topic"]
        except CT.TopicError:
            continue
        rows.append({"id": tid, "title": t["name"], "category": t["category"], "made": n})
    return rows


def variant_of(S: dict) -> dict:
    """제작물 한 벌의 얼굴 — 목소리(voice_id)·틀(합친 frame.json 내용 지문)·컷(재료 영상@초)."""
    import hashlib
    mdir = Path(S["merged_preset"])
    mk = json.loads((mdir / "make.json").read_text(encoding="utf-8")) if (mdir / "make.json").exists() else {}
    fr = mdir / "frame.json"
    frame = hashlib.sha1(fr.read_bytes()).hexdigest()[:12] if fr.exists() else f"preset:{S.get('preset')}"
    cuts = None
    if S.get("topic_id"):
        m = mdir.parent / "work" / str(S["topic_id"]) / "제작" / "재료.json"
        if m.exists():
            M = json.loads(m.read_text(encoding="utf-8"))
            cuts = [f"{s.get('src')}@{int(float(s.get('ss') or 0))}" for s in M.get("shots") or [] if s.get("src")]
    return {"voice": (mk.get("remake_args") or {}).get("voice"), "frame": frame, "cuts": cuts}


def distinct(a: dict, b: dict) -> dict:
    """응용 중복 판정(한 곳): 목소리·틀·컷(≥50% 다름) 중 **둘 이상** 다르면 다른 제작물.
    컷을 아직 모르면(재료 전) 컷은 maybe — possible(아직 다를 수 있나)만 본다."""
    diff, maybe = [], []
    if a.get("voice") != b.get("voice"):
        diff.append("목소리")
    if a.get("frame") != b.get("frame"):
        diff.append("틀")
    ca, cb, cut_diff = a.get("cuts"), b.get("cuts"), None
    if ca and cb:
        A, B = set(ca), set(cb)
        cut_diff = round(1 - len(A & B) / max(len(A), len(B)), 3)
        if cut_diff >= CUT_DIFF_MIN:
            diff.append("컷")
    else:
        maybe.append("컷")
    return {"diff": diff, "maybe": maybe, "cut_diff": cut_diff, "ok": len(diff) >= 2, "possible": len(diff) + len(maybe) >= 2}


def siblings(S: dict, data_dir=None) -> list[dict]:
    """같은 원 소재로 계획 이상 간 다른 제작물 세션."""
    root = S.get("root_topic")
    return [x for x in _all_sessions(data_dir) if root and x.get("root_topic") == root and x["sid"] != S["sid"]
            and x.get("state") in MADE_STATES]


def variant_check(S: dict, data_dir=None, final: bool = False) -> list[str]:
    """형제 제작물과 겹치면 이유 목록(비면 통과). final=False(시작 때)는 '아직 다를 수 있나', True(승인 때)는 '실제로 다른가'."""
    me = variant_of(S)
    bad = []
    for x in siblings(S, data_dir):
        d = distinct(me, x.get("variant") or variant_of(x))
        if not (d["ok"] if final else d["possible"]):
            bad.append(f"세션 {x['sid']}(#{x.get('topic_id')})와 다른 것 {d['diff'] or '없음'}"
                       + (f" · 컷 다름 {d['cut_diff']}" if d["cut_diff"] is not None else "") + " — 목소리·틀·컷 중 둘 이상 달라야")
    return bad


def _start_reuse(S: dict, src_id: int, data_dir, deps) -> dict:
    """응용: 원 소재의 벤치·점수를 그대로 실은 새 행(이름 '… · 응용 n') — 상태기계는 같은 길(claim→advance)로 넘긴다(제미나이 0)."""
    import shutil
    src = CT.detail(src_id, data_dir=data_dir)["topic"]
    root = (src.get("source") or {}).get("reuse_of") or src_id
    S.update(mode="reuse", root_topic=root, reuse_of=src_id)
    bad = variant_check(S, data_dir, final=False)
    if bad:
        shutil.rmtree(_sdir(data_dir) / S["sid"], ignore_errors=True)
        raise MakeError("응용 거절(중복): " + " / ".join(bad), 409)
    k = sum(1 for x in _all_sessions(data_dir) if x.get("root_topic") == root and x.get("mode") == "reuse") + 1
    base = CT.detail(root, data_dir=data_dir)["topic"]["name"]
    t = CT.add(f"{base} · 응용 {k}", S["category"], "bench", source={**(src.get("source") or {}), "via": "응용", "reuse_of": root},
               by="만들기 입구(응용)", data_dir=data_dir)
    who = f"make-{S['sid']}"
    for step, key in (("bench", "bench"), ("score", "score")):
        if not src.get(key):
            break
        CT.claim(t["id"], who, step, data_dir=data_dir)
        CT.advance(t["id"], who, data={key: src[key]}, note=f"응용: #{src_id} 의 {key} 그대로", data_dir=data_dir)
    for f in ("벤치.md", "벤치.json"):
        sp = CT.topic_dir(src_id, data_dir) / f
        if sp.exists():
            CT.save_upload(t["id"], f, sp.read_bytes(), data_dir=data_dir)
    old = next((x for x in _all_sessions(data_dir) if x.get("topic_id") == src_id and x.get("facts_path")), None)
    if old and Path(old["facts_path"]).exists():
        fp = _sdir(data_dir) / S["sid"] / "facts.json"
        fp.write_text(Path(old["facts_path"]).read_text(encoding="utf-8"), encoding="utf-8")
        S["facts_path"] = str(fp)
    S.update(topic_id=t["id"], state="queued", candidates=[{**_candidate(CT.detail(t["id"], data_dir=data_dir)["topic"], data_dir), "n": 1}])
    _save(S, data_dir)
    return choose(S["sid"], 1, data_dir=data_dir, deps=deps)


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
    if chn.get("channels_file"):
        extra["channels_file"] = str(ROOT / chn["channels_file"])   # 같은 결 채널 목록(채널 기준 찾기, 관제 234)
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
        S["root_topic"] = c["id"]
    S["state"] = "working"
    _save(S, data_dir)

    def job():
        S2 = _load(sid, data_dir)
        t, err = _run_until(S2, ("plan_review",), data_dir, deps)
        S3 = _load(sid, data_dir)
        S3["log"] = S2["log"]
        S3.update(state="plan_review" if t["state"] == "plan_review" else "stopped", error=err, topic_state=t["state"])
        if t["state"] == "plan_review":
            S3["variant"] = variant_of(S3)
            S3["variant_warn"] = variant_check(S3, data_dir, final=True)    # 승인 전에 보드가 미리 보여 준다
        _save(S3, data_dir)
    _bg(S, job, data_dir, deps)
    return _load(sid, data_dir)


def approve(sid: str, by: str | None = None, data_dir=None, deps: dict | None = None) -> dict:
    """OK → TTS 1회·렌더. 관리자(ADMINS)만 — 돈(타입캐스트)·시간이 드는 첫 자리. 응용이면 형제 제작물과 실제로 다른지 다시 판다."""
    if by not in ADMINS and not (CUSTOMER_MODE and by == CUSTOMER):
        raise MakeError(f"승인은 관리자({'/'.join(ADMINS[:2])})만 — by={by!r}", 403)
    S = _load(sid, data_dir)
    t = CT.detail(S["topic_id"], data_dir=data_dir)["topic"]
    if t["state"] != "plan_review":
        raise MakeError(f"선검수 자리가 아니다(지금 {t['state']})", 409)
    bad = variant_check(S, data_dir, final=True)
    if bad:
        raise MakeError("승인 거절(응용 중복): " + " / ".join(bad), 409)
    CT.review(S["topic_id"], "plan_review", "pass", by=f"만들기 입구 · {by}", data_dir=data_dir)
    S["state"] = "producing"
    S["approved_by"] = by
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
        out.append({k: S.get(k) for k in ("sid", "preset", "pack", "state", "topic_id", "updated_at", "error", "mode", "root_topic", "approved_by")})
    return out

