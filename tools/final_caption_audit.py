# -*- coding: utf-8 -*-
"""편집 화면 자막 vs 완성본 자막·인트로·썸네일 대조 (읽기 전용, 2026-09-27).

왜: "편집 화면에서 정한 것 = 완성본" 검사가 화면 층(장면·컷, tools/editor_vs_final_video.py)만 있었다.
  자막은 편집 화면이 HTML로 그리고 완성본은 렌더 마지막 단계에서 굽는다 — 같은 글자·같은 시각인지 아무도 안 쟀다.

무엇과 무엇을 대조하나 (전부 **실제 코드를 불러서** 만든다 — 규칙을 이 파일에 다시 적지 않는다):
  ① 편집 화면(3단계 장면 편집기) 자막 = app._lab_captions(plan) — DATA.captions 를 만드는 그 함수.
     app 을 통째로 import 하지 않고 app.py 에서 그 함수 소스만 떼어 실행한다(서버에서 app import = 무거움·부작용 위험).
     + 화면 JS normalizeData(scene_lab.html)의 "끝·시작을 음성 길이로 자르기"만 여기서 재현(표시 보정 3줄).
  ② 완성본 자막 — job 이 어느 길로 굽는지에 따라:
     (a) 장면꾸미기(deco.scene_style) 켠 job  = scene_style.context_for(timeline) 의 장면 목록(칸 앞 짧은 틈은 caption_schedule 이 첫 자막에 붙인다)
         + 스냅샷 captionTexts 덮어쓰기(키 `${presetId}:${mode}:${장면번호}:caption`, out/precision20-ui.js captionKey)
         + 글자를 그리는 조건(precision20-ui.js hasEditableCaption: 본문·연속형·원본 틀만, 훅 숨김 설정).  compose()가 브라우저로 그리는 입력 그대로.
     (b) 그 외(drawtext) job = video_assemble._caption_drawtexts 를 _burn_captions 와 **같은 인자**로 불러
         만든 ffmpeg 필터 문자열을 파싱(enable='between(t,a,b)' + textfile 글자).  렌더가 굽는 필터 그 자체.
     ★렌더 작업 폴더(asm_*)는 렌더 끝에 지워져(video_assemble.assemble finally) 자막 파일이 서버에 안 남는다 —
       그래서 같은 입력으로 다시 만든다. 완성본 픽셀과 다를 수 있으니 job 마다 프레임 한 장(capeye_<job>.jpg)을 남긴다.
  ③ 캡컷 자막 시간표 = video_assemble.caption_schedule(beat) — ②(b)와 "같은 규칙"이라고 적혀 있는 별도 구현. 같이 대조.
  ④ 인트로 = mix_pipeline._intro_choice(thumb, job_id)(렌더가 쓰는 그 판단) ↔ 작업 폴더 thumb_intro.mp4(실제로 붙인 조각) 길이·시각 ↔ final.mp4 길이
     − 칸 길이 합 ↔ 완성본 첫 프레임과 썸네일 PNG 닮음.
  ⑤ 썸네일 = 고른 파일 존재·크기·수정 시각(완성본보다 새 것이면 완성본 인트로는 옛 그림).

출력: job별 한 줄 + `== 칸 N · 글자 불일치 X · 0.15초+ 시각차 Y · 인트로 불일치 Z · 썸네일 이상 W` 요약.
  결과 폴더 CAP_OUT(기본 /tmp/caption_audit): report.txt · details.jsonl · capeye_<job>.jpg
★고객 파일·DB 를 쓰지 않는다: DB 는 sqlite `mode=ro`, 필터 문자열을 만들 때 생기는 글자 파일은 CAP_OUT/_work 에만.
★OCR 을 쓰지 않는다(느리고 불안정) — 렌더가 쓰는 데이터를 읽는다.

사용:
  서버: cd /tmp/caption_audit && set -a && . /etc/shopping-shorts.env && set +a && \
        REPO=/home/ubuntu/lotto-stock-wiki python3 final_caption_audit.py [N최근done=10] [job_id ...]
  로컬: py tools/final_caption_audit.py <job_id>   (DB·음성 파일이 있어야 한다)
  옵션 env: CAP_TOL=0.15(시각차 기준초) · CAP_NO_FRAME=1(눈 확인용 프레임 생략)
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
from pathlib import Path


def _repo_root() -> Path:
    env = os.getenv("REPO")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parents[1]
    if (here / "shopping_shorts").exists():
        return here
    srv = Path("/home/ubuntu/lotto-stock-wiki")
    return srv if srv.exists() else here


ROOT = _repo_root()
sys.path.insert(0, str(ROOT))
PATCH_DIR = os.getenv("PATCH_DIR")     # 배포 전 대조: 고친 모듈(video_assemble·scene_style·mix_pipeline·app.py)을 먼저 얹는다


def _apply_patch_dir():
    """PATCH_DIR 의 모듈을 shopping_shorts.<이름> 으로 먼저 올린다(import 전에) — 서버 파일은 안 바꾼다."""
    if not PATCH_DIR:
        return
    import types
    import shopping_shorts
    for n in ("video_assemble", "scene_style", "mix_pipeline"):
        f = Path(PATCH_DIR) / ("%s.py" % n)
        if f.exists():
            # ★__file__ 은 저장소 자리로 둔다 — 모듈이 자기 위치 기준으로 폰트(fonts/)·틀(out/)을 찾는다
            #   (패치 폴더 자리로 두면 폰트가 전부 기본폰트로 떨어지고 장면꾸미기 틀 파일을 못 찾는다 — 실측).
            real = ROOT / "shopping_shorts" / ("%s.py" % n)
            m = types.ModuleType("shopping_shorts." + n)
            m.__file__, m.__package__ = str(real), "shopping_shorts"
            sys.modules["shopping_shorts." + n] = m
            exec(compile(f.read_text(encoding="utf-8"), str(real), "exec"), m.__dict__)
            setattr(shopping_shorts, n, m)


def app_py():
    f = Path(PATCH_DIR) / "app.py" if PATCH_DIR else None
    return f if (f and f.exists()) else ROOT / "shopping_shorts" / "app.py"
OUT = Path(os.getenv("CAP_OUT") or "/tmp/caption_audit")
TOL = float(os.getenv("CAP_TOL") or 0.15)
INTRO_TOL = 0.35          # 인트로 길이 판정 여유(초) — 칸마다 프레임 올림이 쌓이는 만큼(핸드오프 09-27 새벽: 8칸 +0.29)
THUMB_SIM_T = 18.0        # 첫 프레임 ↔ 썸네일 PNG 회색 평균차(0~255) 이하면 "같은 그림"


# ───────────────────────── 실제 코드 불러오기 ─────────────────────────

def load_func(path, name, glb, ns=None):
    """파일에서 최상위 함수 하나의 소스만 떼어 이름공간에서 실행해 돌려준다(모듈 import 없이 진짜 코드를 쓴다).
    ns 를 주면 그 dict 에 넣는다(함수끼리 서로 부르는 경우)."""
    src = Path(path).read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            ns = dict(glb) if ns is None else ns
            exec(compile(ast.get_source_segment(src, node), str(path), "exec"), ns)
            return ns[name]
    raise LookupError("%s 에 %s 없음" % (path, name))


def app_funcs():
    """mix_pipeline._intro_choice 가 부르는 app 함수(_thumb_dir·_selected_thumb_path).
    app 을 import 하지 않고(서버에서 무겁다) 그 두 함수 소스만 떼어 가벼운 대리 모듈로 올린다 — 이미 import 돼 있으면 그대로."""
    if "shopping_shorts.app" in sys.modules:
        return sys.modules["shopping_shorts.app"]
    import types
    m = types.ModuleType("shopping_shorts.app")
    m.__dict__.update({"os": os, "Path": Path, "_THUMB_DIR": ROOT / "shopping_shorts" / "data" / "thumbs"})
    for n in ("_thumb_dir", "_selected_thumb_path"):
        load_func(app_py(), n, {}, ns=m.__dict__)
    sys.modules["shopping_shorts.app"] = m
    return m


_MP = None


def mp():
    global _MP
    if _MP is None:
        app_funcs()
        from shopping_shorts import mix_pipeline as _m
        _MP = _m
    return _MP


_VA = None


def va():
    global _VA
    if _VA is None:
        from shopping_shorts import video_assemble as _m
        _VA = _m
    return _VA


_LAB = None


def lab_captions_fn():
    """app._lab_captions — DATA.captions 를 만드는 서버 함수(3단계 편집 화면이 그대로 그린다)."""
    global _LAB
    if _LAB is None:
        _LAB = load_func(app_py(), "_lab_captions", {"video_assemble": va(), "Path": Path})
    return _LAB


# ───────────────────────── 정규화·대조 (순수 함수 — 테스트 대상) ─────────────────────────

def norm_text(s) -> str:
    """글자 비교용: NFC · NBSP/전각공백 포함 모든 공백 제거.
    (공백 글리프 없는 폰트는 렌더가 어절을 따로 그려 공백이 사라진다 — 공백은 비교하지 않는다)"""
    s = unicodedata.normalize("NFC", str(s or ""))
    return re.sub(r"[\s 　​]+", "", s)


def compare_beat(editor, render, tol=TOL):
    """칸 하나: editor/render = [{"text","start","end"}] (칸 기준 초). 반환 dict.

    - text_bad: 같은 순번 구절의 글자가 다른 수(개수가 다르면 겹치는 순번까지만 + 개수 차)
    - time_bad: 시작 차 ≥ tol 인 구절 수 + (마지막이 아닌 구절의) 끝 차 ≥ tol 인 구절 수 — 구절당 1회만 센다
    - tail_diff: 마지막 구절 끝 차(렌더는 칸 끝까지 여운 — 설계상 차이라 따로 보고)
    """
    n_e, n_r = len(editor), len(render)
    k = min(n_e, n_r)
    text_bad, time_bad, worst = [], [], 0.0
    for i in range(k):
        e, r = editor[i], render[i]
        if norm_text(e["text"]) != norm_text(r["text"]):
            text_bad.append({"i": i, "editor": e["text"], "render": r["text"]})
        ds = abs(float(e["start"]) - float(r["start"]))
        de = abs(float(e["end"]) - float(r["end"])) if i < k - 1 else 0.0
        d = max(ds, de)
        worst = max(worst, d)
        if d >= tol:
            time_bad.append({"i": i, "text": r["text"], "d_start": round(float(r["start"]) - float(e["start"]), 3),
                             "d_end": round(float(r["end"]) - float(e["end"]), 3)})
    tail = (round(float(render[k - 1]["end"]) - float(editor[k - 1]["end"]), 3) if k else 0.0)
    return {"n_editor": n_e, "n_render": n_r, "count_bad": n_e != n_r,
            "text_bad": text_bad, "time_bad": time_bad, "worst": round(worst, 3), "tail_diff": tail}


def clamp_like_screen(rows, tts_dur):
    """scene_lab.html normalizeData — 끝·시작을 음성 길이(tts_dur)로 자른다(화면 표시 보정)."""
    out = []
    for r in rows:
        r = dict(r)
        if tts_dur:
            if (r.get("end") or 0) > tts_dur:
                r["end"] = round(tts_dur * 1000) / 1000
            if (r.get("start") or 0) > tts_dur:
                r["start"] = round(tts_dur * 1000) / 1000
        out.append(r)
    return out


_EN = re.compile(r"enable='between\(t,([-\d.]+),([-\d.]+)\)'")
_TF = re.compile(r"textfile=txt_cap_(\d+)_(\d+)_\d+_\d+\.txt")
_FF = re.compile(r"drawtext=fontfile=([^:]+):")


def parse_drawtexts(parts, work):
    """_caption_drawtexts 결과(필터 문자열 목록) → {beat_idx: [{"text","start","end","font"}]} (절대 초).
    같은 구절이 강조·어절 때문에 여러 조각으로 그려지면 순서대로 이어 붙인다."""
    by = {}
    work = Path(work)
    for p in parts:
        m, e = _TF.search(p), _EN.search(p)
        if not m or not e:
            continue                  # 하단 바(drawbox) 등
        bi, si = int(m.group(1)), int(m.group(2))
        txt = (work / m.group(0)[len("textfile="):]).read_text(encoding="utf-8")
        f = _FF.search(p)
        row = by.setdefault(bi, {}).setdefault(si, {"text": "", "start": float(e.group(1)),
                                                     "end": float(e.group(2)), "font": f.group(1) if f else ""})
        row["text"] += txt
    return {bi: [segs[k] for k in sorted(segs)] for bi, segs in by.items()}


def scene_caption_text(snapshot, index, scene):
    """장면꾸미기 렌더가 그 장면에 쓰는 자막 글자 — precision20-ui.js syncCaption 과 같은 우선순위:
    captionTexts[`${presetId}:${mode}:${index}:caption`] ?? scene.caption. (표시 여부는 caption_visible)"""
    snap = snapshot or {}
    key = "%s:%s:%s:caption" % (snap.get("presetId"), snap.get("mode"), index)
    txt = (snap.get("captionTexts") or {}).get(key)
    return (txt if txt is not None else scene.get("caption") or ""), (txt is not None), key


def caption_text_overrides(snapshot, scenes, narr_by_beat):
    """손으로 고친 장면 자막 점검: 키 번호가 장면 목록 밖(고아) / 고친 글이 자기 칸 대본엔 없고 남의 칸 대본에 있음(밀림 의심)."""
    snap = snapshot or {}
    pref = "%s:%s:" % (snap.get("presetId"), snap.get("mode"))
    orphan, moved, n = [], [], 0
    for key, val in (snap.get("captionTexts") or {}).items():
        if not key.startswith(pref) or not key.endswith(":caption"):
            continue                      # 다른 틀·다른 모드의 기억(렌더에 안 쓰임)
        n += 1
        try:
            idx = int(key[len(pref):-len(":caption")])
        except ValueError:
            continue
        if idx >= len(scenes):
            orphan.append(key)
            continue
        own = norm_text(narr_by_beat.get(scenes[idx]["beat_idx"], ""))
        v = norm_text(val)
        if v and v not in own and any(v in norm_text(t) for b, t in narr_by_beat.items() if b != scenes[idx]["beat_idx"]):
            moved.append({"key": key, "text": val, "scene_beat": scenes[idx]["beat_idx"]})
    return {"n": n, "orphan": orphan, "moved": moved}


# ───────────────────────── job 읽기 (DB mode=ro) ─────────────────────────

_COLS = ("job_id", "status", "updated_at", "video_path", "edit_plan_json", "headcopy_json",
         "caption_style_json", "deco_json", "thumbnail_json", "customer_id")


def db_path():
    return ROOT / "shopping_shorts" / "data" / "reference.db"


def load_job(con, job_id):
    row = con.execute("SELECT %s FROM mix_jobs WHERE job_id=?" % ",".join(_COLS), (job_id,)).fetchone()
    if not row:
        return None
    d = dict(zip(_COLS, row))
    for k in ("edit_plan", "headcopy", "caption_style", "deco", "thumbnail"):
        raw = d.pop(k + "_json")
        try:
            d[k] = json.loads(raw) if raw else None
        except (ValueError, TypeError):
            d[k] = None
    return d


def recent_done(con, n):
    return [r[0] for r in con.execute(
        "SELECT job_id FROM mix_jobs WHERE status='done' AND video_path IS NOT NULL "
        "ORDER BY updated_at DESC LIMIT ?", (n,))]


# ───────────────────────── 세 쪽 자막 만들기 ─────────────────────────

def editor_captions(plan, deco):
    """{beat_idx: rows(칸 기준 초)} — 3단계 편집 화면이 받는 DATA.captions + 화면 표시 보정.
    deco = job 꾸미기(장면꾸미기면 칸 앞 짧은 틈을 첫 자막에 — _lab_captions 가 caption_lead_absorb 로 판단)."""
    fn = lab_captions_fn()
    try:
        caps, tts_dur = fn(plan, deco)
    except TypeError:                     # 옛 코드(2026-09-27 이전, _lab_captions(plan)) — 비교 실행용
        caps, tts_dur = fn(plan)
    out = {}
    for k, v in caps.items():
        rows = clamp_like_screen(v, tts_dur.get(k))
        # 화면이 **보여 주는** 시각 = 행 시각 + off(cap_offset) — scene_play.js capAt 과 같다
        out[int(k)] = [dict(r, start=float(r["start"]) + float(r.get("off") or 0),
                            end=float(r["end"]) + float(r.get("off") or 0)) for r in rows]
    return out, tts_dur


def timeline_of(plan):
    tts = {b["beat_idx"]: b["tts_path"] for b in plan.get("beats") or [] if b.get("tts_path")}
    return va()._beat_timeline(plan, tts)


def render_captions_drawtext(job, timeline, work):
    """drawtext 길(장면꾸미기 없는 job): _burn_captions 와 같은 인자로 _caption_drawtexts 를 불러 필터를 파싱."""
    V = va()
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    font = V._resolve_font()
    if font:
        shutil.copy(font, work / "font.ttf")
    _hc, cap_style = V._merge_highlight_rules(job.get("headcopy"), job.get("caption_style"), job.get("deco"))
    parts = []
    for b in timeline:
        tail = 0.5 if b is timeline[-1] else 0.0
        parts += V._caption_drawtexts(b["narration"], b["dur"], work, b["beat_idx"], b["t0"],
                                      V._beat_cap_style(cap_style, b), real_durs=b.get("cap_durs"),
                                      cap_offset=b.get("cap_offset", 0.0), tail=tail,
                                      cap_lines=b.get("caption_lines"), lead_in=b.get("cap_lead", 0.0),
                                      cap_xy_segs=b.get("cap_xy_segs"))
    return parse_drawtexts(parts, work)


def render_captions_scene_style(job, timeline):
    """장면꾸미기 길: context_for 장면 + captionTexts 덮어쓰기. {beat_idx: rows(절대 초)} + 점검 정보."""
    from shopping_shorts import scene_style
    snap = scene_style.validate_snapshot((job.get("deco") or {}).get("scene_style"))
    ctx = scene_style.context_for(timeline, job.get("headcopy"), snap, job.get("job_id"))
    scenes = ctx["scenes"]
    rscenes, rsnap = scenes, snap          # compose 가 찍는 장면 = context_for 장면 그대로
    by, hidden, overrides = {}, 0, 0
    hidden_beats, shown_beats = set(), set()
    for i, sc in enumerate(rscenes):
        text, over, _k = scene_caption_text(rsnap, i, sc)
        overrides += int(over)
        # 렌더러가 자막 글자를 실제로 그리는 조건 = precision20-ui.js hasEditableCaption:
        #   captionVisible()(연속형 or caption_visible!==false) && (연속형 || 본문 장면 || 원본(plain) 틀)
        #   ★훅 장면(이야기형)은 자막 대신 제목을 그린다 — 2026-09-27 로컬 레이어 렌더로 확인(훅 3장 모두 자막 글자 없음)
        cont = snap.get("mode") == "continuous"
        visible = (cont or sc.get("caption_visible") is not False) and             (cont or sc.get("kind") == "body" or snap.get("presetId") == "plain")
        if not visible:
            hidden += 1
            hidden_beats.add(sc["beat_idx"])
            continue
        shown_beats.add(sc["beat_idx"])
        if not norm_text(text):
            continue                              # 자막 없는 틈 장면
        by.setdefault(sc["beat_idx"], []).append({"text": text, "start": sc["start"], "end": sc["end"],
                                                  "override": over})
    narr = {b["beat_idx"]: b.get("narration") or "" for b in timeline}
    return by, {"scenes": len(scenes), "hidden": hidden, "overrides": overrides,
                "hidden_beats": sorted(hidden_beats - shown_beats),   # 틀이 자막 글자를 아예 안 그리는 칸(이야기형 훅 등)
                "check": caption_text_overrides(snap, scenes, narr),
                "preset": snap.get("presetId"), "mode": snap.get("mode")}


def capcut_schedule(timeline):
    V = va()
    out = {}
    for b in timeline:
        tail = 0.5 if b is timeline[-1] else 0.0
        out[b["beat_idx"]] = [{"text": s, "start": a, "end": e} for s, a, e in V.caption_schedule(b, tail=tail)]
    return out


def to_rel(rows, t0):
    return [dict(r, start=float(r["start"]) - t0, end=float(r["end"]) - t0) for r in rows]


# ───────────────────────── 인트로·썸네일·프레임 ─────────────────────────

def ffprobe_dur(p):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                           stdin=subprocess.DEVNULL)
        return float(r.stdout.strip())
    except Exception:      # noqa: BLE001
        return None


def grab_frame(video, t, out, scale=None):
    vf = ["-vf", scale] if scale else []
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.3f" % max(0.0, t), "-i", str(video),
                        "-frames:v", "1", *vf, str(out)], capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    return r.returncode == 0 and Path(out).exists()


def img_diff(a, b):
    """두 그림의 27x48 회색 평균 절대차(0~255). 크기·비율 달라도 억지로 맞춘다."""
    from PIL import Image
    ia = Image.open(a).convert("L").resize((27, 48))
    ib = Image.open(b).convert("L").resize((27, 48))
    pa, pb = ia.tobytes(), ib.tobytes()
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)


def intro_and_thumb(job, content_dur, work_tmp):
    """인트로·썸네일 점검. 반환 (intro dict, thumb dict)."""
    jid = job["job_id"]
    final = Path(job.get("video_path") or "")
    th = job.get("thumbnail") or {}
    if isinstance(th, str):
        try:
            th = json.loads(th)
        except ValueError:
            th = {}
    # 렌더가 실제로 붙이는 판단 = mix_pipeline._intro_choice(켜짐, 붙일 파일, 길이) — 그 함수를 그대로 부른다
    try:
        on, png, sec = mp()._intro_choice(th, jid)
    except TypeError:
        # 옛 코드(2026-09-27 이전, _intro_choice(thumb) → 고른 '이름') — 비교 실행용. 붙이는 규칙은 옛 _thumb_intro_png
        on, _name, sec = mp()._intro_choice(th)
        png = mp()._thumb_intro_png(dict(job, thumbnail=th), th) if on else None
        sec = float(sec or 1.2) if on else None
    sel = th.get("selected")
    chosen = sel
    sec = float(sec or 0.0)
    fdur = ffprobe_dur(final) if final.exists() else None
    fmt = final.stat().st_mtime if final.exists() else None
    clip = final.parent / "thumb_intro.mp4"
    cdur = ffprobe_dur(clip) if clip.exists() else None
    cfresh = bool(clip.exists() and fmt and abs(fmt - clip.stat().st_mtime) < 900)
    extra = round(fdur - content_dur, 3) if (fdur is not None and content_dur) else None
    intro = {"on": bool(on), "chosen": chosen, "png": png.name if png else None, "sec": sec,
             "final_dur": fdur, "content_dur": round(content_dur, 3), "extra": extra,
             "clip_dur": cdur, "clip_fresh": cfresh, "bad": [], "first_frame_diff": None}
    if on and not png:
        intro["bad"].append("켰는데 붙일 썸네일 파일이 없음(인트로 빠짐)")
    if on and png:
        if not cfresh:
            intro["bad"].append("인트로 조각(thumb_intro.mp4)이 이번 완성본 것이 아님")
        if cdur is not None and abs(cdur - sec) > 0.05:
            intro["bad"].append("붙은 인트로 %.2fs ≠ 설정 %.2fs" % (cdur, sec))
        if extra is not None and extra < sec - INTRO_TOL:
            intro["bad"].append("완성본 길이-칸 합 %.2fs < 인트로 %.2fs(인트로가 안 들어감)" % (extra, sec))
        if fdur:
            f0 = Path(work_tmp) / ("intro_%s.jpg" % jid)
            if grab_frame(final, min(sec / 2, fdur / 2), f0):
                d = img_diff(f0, png)
                intro["first_frame_diff"] = round(d, 1)
                if d > THUMB_SIM_T:
                    intro["bad"].append("첫 화면이 고른 썸네일과 다름(차 %.1f)" % d)
    # 완성본 길이 - (칸 합 + 실제 붙은 인트로) = 인트로와 무관한 길이 남음(영상 조립 층). 인트로 판정에 안 섞고 따로 보고.
    intro["len_excess"] = (round(extra - (sec if (on and png and cfresh) else 0.0), 3) if extra is not None else None)
    if not on and extra is not None and extra > sec - INTRO_TOL and cfresh:
        intro["bad"].append("인트로 끔인데 이번 완성본에 인트로 조각이 붙음")
    thumb = {"selected": sel, "exists": None, "size": None, "newer_than_final_s": None, "bad": []}
    if sel:
        p = Path(app_funcs()._thumb_dir(jid)) / sel
        thumb["exists"] = p.exists()
        if p.exists():
            st = p.stat()
            thumb["size"] = st.st_size
            if fmt:
                thumb["newer_than_final_s"] = round(st.st_mtime - fmt, 1)
            if st.st_size < 1024:
                thumb["bad"].append("썸네일 파일이 1KB 미만")
            if on and fmt and st.st_mtime > fmt + 5:
                thumb["bad"].append("썸네일이 완성본보다 %.0f초 새 것 — 완성본 인트로는 옛 그림" % (st.st_mtime - fmt))
        else:
            thumb["bad"].append("고른 썸네일 파일 없음")
    return intro, thumb


def eye_frame(job, render_abs, shift, out_dir):
    """눈 확인용: 완성본에서 한 구절 한가운데 프레임 + 아래 띠에 '렌더 데이터상 이 글자' 를 적어 저장."""
    final = Path(job.get("video_path") or "")
    if not final.exists():
        return None
    rows = [(bi, r) for bi in sorted(render_abs) for r in render_abs[bi] if norm_text(r["text"])]
    if not rows:
        return None
    bi, r = rows[len(rows) // 2]
    t = shift + (float(r["start"]) + float(r["end"])) / 2
    raw = Path(out_dir) / ("_capeye_raw_%s.jpg" % job["job_id"])
    if not grab_frame(final, t, raw, "scale=540:960"):
        return None
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(raw).convert("RGB")
    canvas = Image.new("RGB", (540, 1040), (20, 20, 20))
    canvas.paste(im, (0, 0))
    font = None
    fp = va()._resolve_font()
    try:
        font = ImageFont.truetype(fp, 26) if fp else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(canvas).text((10, 972), "렌더 데이터: 칸%s %.2fs「%s」" % (bi, t, r["text"][:18]),
                                fill=(255, 230, 0), font=font)
    out = Path(out_dir) / ("capeye_%s.jpg" % job["job_id"])
    canvas.save(out, quality=88)
    raw.unlink(missing_ok=True)
    return out.name


# ───────────────────────── job 하나 ─────────────────────────

def audit_job(job, out_dir, frame=True):
    jid = job["job_id"]
    plan = job.get("edit_plan") or {}
    if not plan.get("beats"):
        return {"job": jid, "error": "편성표 없음"}
    work = Path(out_dir) / "_work" / jid
    try:
        timeline = timeline_of(plan)
        editor, _tts = editor_captions(plan, job.get("deco"))
        ss = bool((job.get("deco") or {}).get("scene_style"))
        if ss:
            render_abs, ss_info = render_captions_scene_style(job, timeline)
        else:
            render_abs, ss_info = render_captions_drawtext(job, timeline, work), None
        capcut = capcut_schedule(timeline)
        drawtext_abs = render_captions_drawtext(job, timeline, work / "dt") if ss else render_abs
        beats, n_text, n_time, n_count, capcut_bad, font_fb = [], 0, 0, 0, 0, 0
        req_font = os.path.basename(((job.get("caption_style") or {}).get("font")) or "")
        skip = set((ss_info or {}).get("hidden_beats") or [])
        for b in timeline:
            bi, t0 = b["beat_idx"], b["t0"]
            if bi in skip:
                continue                # 틀 설계상 자막 글자를 안 그리는 칸 — 대조 대상 아님(줄에 '틀숨김'으로 보고)
            e = editor.get(bi) or []
            r = to_rel(render_abs.get(bi) or [], t0)
            c = compare_beat(e, r)
            # 6단계(장면꾸미기)에서 고객이 손으로 고친 자막은 그 화면이 정한 것 = 완성본과 같다 → 불일치로 안 센다(따로 보고)
            c["override_text"] = [x for x in c["text_bad"] if r[x["i"]].get("override")]
            c["text_bad"] = [x for x in c["text_bad"] if not r[x["i"]].get("override")]
            # 캡컷 시간표 ↔ drawtext 렌더(같은 규칙이라고 적힌 두 구현)
            cc = compare_beat(to_rel(capcut.get(bi) or [], t0), to_rel(drawtext_abs.get(bi) or [], t0), tol=0.02)
            cc_bad = bool(cc["text_bad"] or cc["time_bad"] or cc["count_bad"] or abs(cc["tail_diff"]) > 0.02)
            capcut_bad += int(cc_bad)
            if not ss and req_font and any(x.get("font") == "font.ttf" for x in (render_abs.get(bi) or [])):
                font_fb += 1
            n_text += len(c["text_bad"]) + (abs(c["n_editor"] - c["n_render"]) if c["count_bad"] else 0)
            n_time += len(c["time_bad"])
            n_count += int(c["count_bad"])
            beats.append({"beat": bi, "t0": round(t0, 3), "dur": round(b["dur"], 3),
                          "cap_offset": b.get("cap_offset") or 0.0, "cap_lead": b.get("cap_lead") or 0.0,
                          "head_trim": b.get("head_trim") or 0.0, **c, "capcut_vs_drawtext_bad": cc_bad})
        content = sum(b["dur"] for b in timeline)
        intro, thumb = intro_and_thumb(job, content, work)
        shift = intro["sec"] if (intro["on"] and intro["png"]) else 0.0
        eye = eye_frame(job, render_abs, shift, out_dir) if frame else None
        return {"job": jid, "path": "scene_style" if ss else "drawtext", "beats": beats, "n_beats": len(beats),
                "text_bad": n_text, "time_bad": n_time, "count_bad": n_count, "capcut_bad": capcut_bad,
                "font_fallback_beats": font_fb, "scene_style": ss_info, "intro": intro, "thumb": thumb, "eye": eye}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def line_of(r):
    if r.get("error"):
        return "%s  오류: %s" % (r["job"], r["error"])
    ss = r.get("scene_style") or {}
    chk = ss.get("check") or {}
    tb = [b for b in r["beats"] if b["time_bad"]]
    worst = max((b["worst"] for b in r["beats"]), default=0.0)
    s = ("%s [%s] 칸%d · 글자X %d · 개수X %d · 시각차 %d(최대 %.2fs) · 캡컷표≠렌더 %d칸 · 인트로 %s%s · 썸네일 %s"
         % (r["job"], r["path"], r["n_beats"], r["text_bad"], r["count_bad"], r["time_bad"], worst, r["capcut_bad"],
            ("켬" if r["intro"]["on"] else "끔"),
            (" !" + "/".join(r["intro"]["bad"]) if r["intro"]["bad"] else ""),
            ("!" + "/".join(r["thumb"]["bad"]) if r["thumb"]["bad"] else ("ok" if r["thumb"]["selected"] else "-"))))
    if ss:
        s += " · 장면%d 숨김%d(틀숨김 칸 %s) 손자막%d 고아%d 밀림의심%d" % (ss["scenes"], ss["hidden"],
                                                   ",".join(map(str, ss.get("hidden_beats") or [])) or "-", ss["overrides"],
                                                   len(chk.get("orphan") or []), len(chk.get("moved") or []))
    le = r["intro"].get("len_excess")
    if le is not None and abs(le) > INTRO_TOL:
        s += " · 완성본 길이 남음 %+.2fs(칸 합+인트로 대비)" % le
    if r.get("font_fallback_beats"):
        s += " · 폰트폴백 %d칸" % r["font_fallback_beats"]
    if tb:
        ex = tb[0]["time_bad"][0]
        s += " · 예) 칸%s「%s」 시작%+.2f 끝%+.2f" % (tb[0]["beat"], str(ex["text"])[:10], ex["d_start"], ex["d_end"])
    return s


def main(argv):
    _apply_patch_dir()
    OUT.mkdir(parents=True, exist_ok=True)
    args = argv[1:]
    n = int(args[0]) if args and args[0].isdigit() else 10
    ids = [a for a in args if not a.isdigit()]
    con = sqlite3.connect("file:%s?mode=ro" % db_path().as_posix(), uri=True)
    if not ids:
        ids = recent_done(con, n)
    frame = os.getenv("CAP_NO_FRAME") != "1"
    rep = open(OUT / "report.txt", "w", encoding="utf-8")
    det = open(OUT / "details.jsonl", "w", encoding="utf-8")
    tot = {"beats": 0, "text": 0, "time": 0, "intro": 0, "thumb": 0}
    for jid in ids:
        job = load_job(con, jid)
        if not job:
            r = {"job": jid, "error": "job 없음"}
        else:
            try:
                r = audit_job(job, OUT, frame=frame)
            except Exception as e:      # noqa: BLE001 — 한 job 실패가 나머지를 막지 않게(사유는 보고에 남긴다)
                r = {"job": jid, "error": "%s: %s" % (type(e).__name__, str(e)[:200])}
        line = line_of(r)
        print(line, flush=True)
        print(line, file=rep, flush=True)
        det.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        if not r.get("error"):
            tot["beats"] += r["n_beats"]
            tot["text"] += r["text_bad"]
            tot["time"] += r["time_bad"]
            tot["intro"] += int(bool(r["intro"]["bad"]))
            tot["thumb"] += int(bool(r["thumb"]["bad"]))
    summ = ("== 칸 %d · 글자 불일치 %d · %.2f초+ 시각차 %d · 인트로 불일치 %d · 썸네일 이상 %d"
            % (tot["beats"], tot["text"], TOL, tot["time"], tot["intro"], tot["thumb"]))
    print(summ)
    print(summ, file=rep)
    rep.close()
    det.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
