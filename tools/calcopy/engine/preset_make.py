# -*- coding: utf-8 -*-
"""프리셋 한 명령 제작기 — 프리셋 + 작품(대본.json·재료.json) → 완성본·자동 검사 표 (관제 097, 2026-10-17).

    PYTHONUTF8=1 py tools/calcopy/engine/preset_make.py <프리셋 폴더> <작품 폴더> [<작품 폴더> …|@목록.txt]
        --plan          계획 시트만(TTS 전 선검수) — plan/계획_시트_자동.jpg
        --allow-tts     캐시에 없는 TTS 를 부른다(Typecast = 페이블 OK 뒤 1회). 없으면 TTS 없을 때 멈춤
        --tts FILE      이미 받은 TTS mp3 를 이 작품 TTS 로 들인다(작품 1개일 때) — 재호출 0
        --test          바탕화면 복사·결과물.json 등록 안 함(재현·시험용)
        --out DIR       출력 폴더(작품 1개일 때, 기본 <자료폴더>/make)
        --cache DIR     캐시 폴더 바꾸기(빈 폴더 = 전부 새로, 시간 비교용)
        --tag T         바탕화면 이름 꼬리(칼카피_<브랜드>_<제목>_<T>.mp4)
        --desktop-dir / --results   바탕화면·결과물 목록 경로 바꾸기(시험용)

판단 주인: 채널 차이 = 프리셋 manifest `channel_rules.make` 한 곳(코드에 채널 이름 분기 없음). 숏템 기능은 부르기만 —
  틀 렌더 scene_style.compose · 효과음 sfx_pack.events · 줄 시각 narr_video.time_steps · 이음매 check_seams · 중복 check_overlap.py.
캐시(이어하기·수정 속도): <자료폴더>/_make_cache/
  tts/   (목소리|속도|글) → mp3             parts/  컷 조각(소스·크기·시각·크롭·프레임·인코딩) → mp4
  layers/ (틀 스냅샷+장면 문맥+렌더러 파일) → 틀 그림   scenes/ 장면 합성 ffmpeg 명령(입력 내용 해시) → mp4
  → 컷 3개를 바꾸면 그 컷이 걸친 조각·장면만 다시 굽는다. 작품마다 run_log.json(단계별 시간·TTS 호출·검사·MD5).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FPS = 30
DATA_ROOT = Path("C:/숏템_칼카피")
OVERLAP_TOOL = ROOT / "channel/evenshopping/작품1_총알람/check_overlap.py"   # B13 중복 판단 주인(재미썸홈 수정3 담당) — 부르기만
RESULTS = ROOT / "channel/결과물.json"
FF_PAR = 2            # 동시 ffmpeg 상한(담당 공통 규칙 ≤4, 지시 ≤2)
ENC = ["-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p"]   # 컷 조각 인코딩(두 render.py 그대로)


# ── 작은 도구 ────────────────────────────────────────────────────────────
def nchar(s: str) -> int:
    return len(re.findall(r"[가-힣A-Za-z0-9]", s or ""))


def norm(s: str) -> str:
    return "".join(re.findall(r"[가-힣A-Za-z0-9]", s or ""))


def sha(obj) -> str:
    return hashlib.sha1(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def md5(p) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(f"명령 실패({r.returncode}): {' '.join(map(str, cmd))[:300]}\n{(r.stderr or '')[-800:]}")
    return r


def dur_of(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


def probe(p) -> tuple[int, int, float]:
    j = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", p]).stdout)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def lufs(p) -> tuple[float, float]:
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def copy_atomic(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    shutil.copyfile(src, tmp)
    tmp.replace(dst)


class Clock:
    def __init__(self):
        self.t, self.steps = time.time(), {}

    def lap(self, name):
        now = time.time()
        self.steps[name] = round(now - self.t, 1)
        self.t = now
        print(f"  [{name}] {self.steps[name]}초", flush=True)


# ── 1) 읽기: 프리셋·작품 → 한 모양 ─────────────────────────────────────────
def load_preset(pdir: Path) -> tuple[dict, dict]:
    M = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    cfg = (M.get("channel_rules") or {}).get("make")
    if not cfg:
        raise SystemExit(f"{pdir}/manifest.json 에 channel_rules.make 가 없다 — 제작기가 읽을 값(창·목소리·소리·검사 기준)을 먼저 적어라")
    return M, cfg


def load_work(wdir: Path, M: dict, cfg: dict) -> dict:
    S = json.loads((wdir / "대본.json").read_text(encoding="utf-8"))
    R = json.loads((wdir / "재료.json").read_text(encoding="utf-8"))
    slug = M.get("slug") or wdir.parent.name
    data = Path(R.get("cand_dir") or DATA_ROOT / slug / wdir.name)
    raw_lines = S.get("lines") or S.get("spine55") or []
    lines = [{"text": l.get("text") or l.get("line"), "tts": l.get("tts") or l.get("text") or l.get("line"),
              "slot": l.get("slot") or l.get("role")} for l in raw_lines]
    rows = R.get("shots") or R.get("cuts") or []
    toks = S.get("tokens")
    if toks and len(toks) != len(rows):
        raise ValueError(f"토막 {len(toks)}개 ≠ 재료 {len(rows)}개")
    pieces = []
    for k, r in enumerate(rows):
        t = toks[k] if toks else None
        cap = (t or {}).get("text") or r.get("caption")
        pieces.append({"text": cap, "chars": (t or {}).get("chars", nchar(cap)), "line": (t or {}).get("line")})
    if any(p["line"] is None for p in pieces):   # 줄 번호가 없으면 대사 순서대로 글자를 먹여 정한다
        li, used = 0, 0
        for p in pieces:
            while used >= nchar(lines[li]["text"]):
                li, used = li + 1, 0
            p["line"] = li
            used += nchar(p["text"])
    if norm(" ".join(p["text"] for p in pieces)) != norm(" ".join(l["text"] for l in lines)):
        raise ValueError("자막 토막을 이으면 대본 줄과 다르다(빠짐·순서)")
    W, H = cfg["window"]
    meme_dir = Path(cfg.get("meme_dir") or data)
    cuts = []
    for k, r in enumerate(rows):
        if r.get("cont") or r.get("src") == "+" or r.get("source") == "+":
            if not cuts:
                raise ValueError("첫 토막이 '이어감'일 수 없다")
            cuts[-1]["pieces"].append(k)
            continue
        src = r.get("src") or r.get("source")
        path = meme_dir / f"{src[5:]}.mp4" if src.startswith("meme:") else (data / src if src.endswith(".mp4") else data / f"src_{src}.mp4")
        cuts.append({"src": src, "path": path, "ss": float(r["ss"] if "ss" in r else r["src_t0"]), "crop": r.get("src_crop"),
                     "crop_x": r.get("crop_x"), "kind": r.get("kind") or "", "meme": src.startswith("meme:") or r.get("kind") == "짤",
                     "seen": r.get("seen") or r.get("ours") or "", "pieces": [k]})
    title = S.get("title_slots") or M.get("sample_title") or {}
    voice = (S.get("voice") or {}).get("voice_id") or cfg["voice_id"]
    name = S.get("desktop_title") or re.sub(r"^작품\d+_", "", wdir.name)
    return {"dir": wdir, "name": wdir.name, "title_short": name, "data": data, "lines": lines, "pieces": pieces, "cuts": cuts,
            "title": {k: title.get(k, "") for k in ("hook1", "hook2", "bodyTitle")}, "voice": voice, "S": S}


def plan_check(w: dict, cfg: dict) -> dict:
    """소스 있나·길이 되나·해상도 ≥720p·확대 ≤2.3배(A4). 크롭 상자도 여기서 정한다(판단 한 곳)."""
    W, H = cfg["window"]
    bad, low, zooms = [], [], []
    for c in w["cuts"]:
        if not c["path"].exists():
            bad.append(f"소스 없음 {c['path']}")
            continue
        sw, sh, sd = probe(c["path"])
        c["src_wh"], c["src_dur"] = (sw, sh), sd
        if c["crop"]:
            x, y, cw, ch = c["crop"]
        else:
            ch = sh
            cw = min(sw, int(sh * W / H) // 2 * 2)
            x = (sw - cw) // 2 if c["crop_x"] is None else int(c["crop_x"])
            y = 0
        c["box"] = [int(x), int(y), int(cw), int(ch)]
        z = round(H / ch, 2)
        zooms.append(z)
        if not c["meme"] and min(sw, sh) < 720:
            low.append(f"{c['src']} {sw}x{sh}")
        if z > 2.3 and not c["meme"]:
            low.append(f"{c['src']} 확대 {z}배")
    if bad:
        raise FileNotFoundError("; ".join(bad))
    return {"A4": {"ok": not low, "값": f"최대 확대 {max(zooms)}배", "흠": low}}


# ── 2) TTS (캐시·재호출 금지 기본) ─────────────────────────────────────────
def tts_chunks(lines: list[str], rule: dict | None) -> list[str]:
    """TTS 에 넣는 덩어리 — 공백 뺀 max_chars 넘는 문장은 쉼표 자리에서 나눈다(한 번에 넣으면 긴 문장을 몰아 빨리 읽는다).
    쉼표가 없으면 그 문장은 그대로(지어서 끊지 않는다)."""
    out = []
    for s in lines:
        if not rule or nchar(s) <= int(rule["max_chars"]) or rule["at"] not in s:
            out.append(s)
            continue
        bits = [b.strip() + rule["at"] for b in s.split(rule["at"])]
        bits[-1] = bits[-1][: -len(rule["at"])]
        out += [b for b in bits if norm(b)]
    return out


def tts(w: dict, cfg: dict, cache: Path, adopt: str | None, allow: bool, log: dict, synth=None) -> Path:
    """덩어리마다 (목소리|속도|글) 캐시 — 한 덩어리만 고치면 그것만 다시 받는다. 덩어리 사이 0.25초 쉼으로 잇는다."""
    chunks = tts_chunks([l["tts"] for l in w["lines"]], cfg.get("tts_split"))
    tempo = cfg.get("tts_tempo")
    whole = " ".join(l["tts"] for l in w["lines"])
    adopted = cache / "tts" / f"{sha([w['voice'], 'adopted', whole])}.mp3"
    joined = cache / "tts" / f"{sha([w['voice'], tempo, chunks])}.wav"
    if adopt:
        copy_atomic(Path(adopt), adopted)
        log["tts"] = {"calls": 0, "from": f"들인 파일 {adopt}(덩어리 나누기 전 판)", "chunks": 1}
        return adopted
    for p, why in ((joined, f"캐시(목소리 {w['voice']}·속도 {tempo}·덩어리 {len(chunks)})"), (adopted, "캐시(예전에 들인 파일 — 덩어리 나누기 전 판)")):
        if p.exists():
            log["tts"] = {"calls": 0, "from": why, "chunks": len(chunks)}
            return p
    files, calls = [], 0
    for ch in chunks:
        p = cache / "tts" / "chunk" / f"{sha([w['voice'], tempo, ch])}.mp3"
        if not p.exists():
            if not allow:
                raise SystemExit("TTS 캐시 없음 — 페이블 OK 뒤 --allow-tts 로 부르거나 --tts 로 받은 파일을 들여라")
            if synth is None:
                from shopping_shorts.channelkit import providers
                synth = providers.typecast_synth(w["voice"], tempo=tempo)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.stem + ".part.mp3")
            synth(ch, str(tmp))
            tmp.replace(p)
            calls += 1
        files.append(p)
    ins, flt = [], []
    for i, f in enumerate(files):
        ins += ["-i", f]
        flt.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=mono,apad=pad_dur=0.25[c{i}]")
    tmp = joined.with_name(joined.stem + ".part.wav")
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(flt) + ";" + "".join(f"[c{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=0:a=1[o]",
         "-map", "[o]", tmp])
    tmp.replace(joined)
    log["tts"] = {"calls": calls, "from": f"Typecast {w['voice']} tempo {tempo}", "chunks": len(chunks), "chunk_text": chunks}
    return joined


def narration(full: Path, w: dict, cfg: dict, out: Path) -> tuple[Path, float]:
    """앞뒤 무음·긴 쉼 정리 → 목표 말속도까지 atempo(범위 밖이면 멈춤 — 조용히 깎지 않는다)."""
    tight, narr = out / "narr_tight.wav", out / "narr.wav"
    f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
    mid = "silenceremove=stop_periods=-1:stop_duration=0.15:stop_threshold=-45dB:stop_silence=0.1"
    run(["ffmpeg", "-y", "-i", full, "-af", f"{f},areverse,{f},areverse,{mid}", tight])
    chars = sum(p["chars"] for p in w["pieces"])
    d0 = dur_of(tight)
    tempo = round(cfg["cps"] / (chars / d0), 4)
    lo, hi = cfg["atempo_range"]
    if not lo <= tempo <= hi:
        raise RuntimeError(f"atempo {tempo} 가 범위 {cfg['atempo_range']} 밖 — TTS 원속도 {chars / d0:.2f}자/초(manifest tts_tempo 를 고쳐 다시 받을 것)")
    run(["ffmpeg", "-y", "-i", tight, "-af", f"atempo={tempo}", "-ar", "44100", narr])
    return narr, tempo


# ── 3) 줄 시각 + 줄별 말속도(B15) ──────────────────────────────────────────
def find_asr_cache(narr: Path, data: Path) -> str:
    """받아쓰기 캐시는 오디오 md5 로 묶인다 — 같은 나레를 예전에 받아쓴 파일이 있으면 그대로 쓴다(재호출 0, 시각 흔들림 0)."""
    m = md5(narr)
    for p in data.rglob("*.asr.json"):
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("md5") == m:
                copy_atomic(p, narr.with_name(narr.name + ".asr.json"))
                return str(p)
        except (ValueError, OSError):
            continue
    return ""


def timing(w: dict, narr: Path, log: dict) -> tuple[list, float]:
    """1순위 = 무음 구간 + 글자 비율(line_starts asr=False). 경계에 쉼이 없다는 경보가 나면 그때만 받아쓰기(캐시 먼저)."""
    from tools.calcopy import narr_video as N
    steps = [{"text": p["text"], "chars": p["chars"], "new_cut": True, "line": p["line"]} for p in w["pieces"]]
    lines = [l["text"] for l in w["lines"]]
    msgs = []
    timed, dur = N.time_steps(steps, str(narr), lines=lines, log=msgs.append, asr=False)
    log["line_timing"] = {"way": "무음+글자비율", "경보": msgs}
    if any("[경보]" in m for m in msgs):
        hit = find_asr_cache(narr, w["data"])
        m2 = []
        timed, dur = N.time_steps(steps, str(narr), lines=lines, log=m2.append, asr=True)
        log["line_timing"] = {"way": "받아쓰기(무음 방식 경보 뒤)", "asr_cache": hit or "새로 부름(무료 제미나이)", "경보_무음": msgs, "경보": m2}
    return timed, dur


def line_spans(timed, n_lines, dur):
    st = [next(s["t0"] for s in timed if s["line"] == li) for li in range(n_lines)]
    return [(st[i], st[i + 1] if i + 1 < len(st) else dur) for i in range(n_lines)]


def line_rates(timed, w, dur):
    ch = [sum(p["chars"] for p in w["pieces"] if p["line"] == li) for li in range(len(w["lines"]))]
    return [round(c / (b - a), 2) for c, (a, b) in zip(ch, line_spans(timed, len(w["lines"]), dur))]


def fix_line_rates(timed, dur, w, cfg, narr: Path, log: dict):
    """B15: 끝 last_lines 줄 중 목표의 max_ratio 배보다 빠른 줄만 그 구간을 늘린다(일괄 atempo 금지). 시각은 늘린 비율대로 옮긴다
    (재미썸홈 수정3: 받아쓰기로 다시 재면 줄 시작이 2초 늦게 잡혔다)."""
    rule = cfg.get("line_rate") or {}
    before = line_rates(timed, w, dur)
    n = len(w["lines"])
    floor = 1 - float(rule.get("max_change", 1.0))   # 줄별 늘리기 한도(±10%) — 넘는 만큼은 못 고치고 B15 미달로 남는다
    slow = {li: round(max(floor, cfg["cps"] / r), 4) for li, r in enumerate(before)
            if li >= n - int(rule.get("last_lines", n)) and r > cfg["cps"] * float(rule.get("max_ratio", 9e9))}
    if slow:
        spans = line_spans(timed, n, dur)
        parts, labs = [], []
        for li, (a, b) in enumerate(spans):
            f = slow.get(li)
            parts.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS{',atempo=' + str(f) if f else ''}[l{li}]")
            labs.append(f"[l{li}]")
        fixed = narr.with_name("narr_lines.wav")
        run(["ffmpeg", "-y", "-i", narr, "-filter_complex", ";".join(parts) + ";" + "".join(labs) + f"concat=n={n}:v=0:a=1[o]",
             "-map", "[o]", "-ar", "44100", fixed])

        def remap(t):
            shift = 0.0
            for li, (a, b) in enumerate(spans):
                f = slow.get(li)
                if f and t > a:
                    shift += (min(t, b) - a) * (1 / f - 1)
            return round(t + shift, 3)
        timed = [{**x, "t0": remap(x["t0"]), "t1": remap(x["t1"])} for x in timed]
        narr, dur = fixed, dur_of(fixed)
    log["line_rate"] = {"before": before, "after": line_rates(timed, w, dur), "slowed": slow}
    return timed, dur, narr


# ── 4) 컷 조각(캐시) → 재료 영상 ──────────────────────────────────────────
def build_cuts(w, timed, dur, cfg):
    timed = [dict(x) for x in timed]
    timed[-1]["t1"] = round(dur + float(cfg.get("end_pad_s") or 0), 3)
    for p, t in zip(w["pieces"], timed):
        p["t0"], p["t1"] = t["t0"], t["t1"]
        p["f0"], p["f1"] = round(t["t0"] * FPS), round(t["t1"] * FPS)
    for c in w["cuts"]:
        c["f0"], c["f1"] = w["pieces"][c["pieces"][0]]["f0"], w["pieces"][c["pieces"][-1]]["f1"]
        c["n"] = max(1, c["f1"] - c["f0"])
        if c["ss"] + c["n"] / FPS > c["src_dur"] + 1e-3:
            raise ValueError(f"소스 길이 부족 {c['src']} {c['ss']}+{c['n'] / FPS:.2f}>{c['src_dur']:.2f}")
    return timed


def render_parts(w, cfg, cache: Path, out: Path, log: dict) -> tuple[Path, list]:
    W, H = cfg["window"]
    H2 = H + (H % 2)
    pdir = cache / "parts"
    pdir.mkdir(parents=True, exist_ok=True)
    jobs, mat_map = [], []
    for c in w["cuts"]:
        st = c["path"].stat()
        key = sha([str(c["path"]), st.st_size, int(st.st_mtime), round(c["ss"], 3), c["box"], W, H2, c["n"], FPS, ENC])
        c["part_key"] = key
        mat_map.append((key, c["n"]))
        dst = pdir / f"{key}.mp4"
        if not dst.exists():
            jobs.append((c, dst))

    def one(job):
        c, dst = job
        x, y, cw, ch = c["box"]
        tmp = dst.with_name(dst.stem + ".part.mp4")
        run(["ffmpeg", "-y", "-ss", f"{c['ss']:.3f}", "-i", c["path"], "-an", "-vf",
             f"crop={cw}:{ch}:{x}:{y},scale={W}:{H2}:flags=lanczos,setsar=1,fps={FPS}", "-frames:v", c["n"], *ENC, tmp])
        tmp.replace(dst)
    with cf.ThreadPoolExecutor(FF_PAR) as ex:
        list(ex.map(one, jobs))
    log["parts"] = {"total": len(w["cuts"]), "rendered": len(jobs), "cached": len(w["cuts"]) - len(jobs)}
    lst = out / "parts_list.txt"
    lst.write_text("\n".join(f"file '{(pdir / (k + '.mp4')).as_posix()}'" for k, _ in mat_map), encoding="utf-8")
    mat = out / "material.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", mat])
    return mat, mat_map


# ── 5) 틀 합성(숏템 scene_style.compose 를 부르고, 같은 입력의 레이어·장면은 캐시에서) ──────────────
def _renderer_sig() -> str:
    html = ROOT / "out/scene-style-ui-showcase.html"
    files = [html, ROOT / "tools/render_scene_style.js"]
    for ref in re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))', html.read_text(encoding="utf-8")):
        p = (html.parent / ref).resolve()
        if p.exists():
            files.append(p)
    return sha([md5(p) for p in files])


def snapshot_and_timeline(w, M, cfg, pdir: Path):
    from shopping_shorts import scene_style
    fr = cfg["frame"]["kind"]
    if fr == "preset_save":
        from tools.calcopy.engine import preset_save as P
        from shopping_shorts.calcopy_frame import to_snapshot
        pre, Mf = P.load(pdir)
        F = P.apply(pre, None, None, Mf["variable_stats"], None, Mf["rules"])
        snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(F))
        head = {"text": ""}
    elif fr == "template":
        T = w["title"]
        snap = scene_style.validate_snapshot({"mode": "story", "presetId": M["template"]["preset_id"],
                                              "text": {"channel": M["brand"]["channel_name"], **T}})
        head = {"text": f"{T['hook1']}\n{T['hook2']}", "body_title": T["bodyTitle"]}
    else:
        raise ValueError(f"frame.kind 모름: {fr}")
    P_ = w["pieces"]
    beats = []
    hook_n = sum(1 for p in P_ if p["line"] == 0) if cfg["hook"] == "first_line" else 1
    a, b = P_[0]["f0"] / FPS, P_[hook_n - 1]["f1"] / FPS
    cap0 = w["lines"][0]["text"] if cfg["hook"] == "first_line" else P_[0]["text"]
    beats.append({"beat_idx": 0, "t0": a, "dur": round(b - a, 3), "narration": cap0, "caption_lines": [cap0], "role": "hook",
                  "primary": {"video_id": "s0", "start": a, "end": b}})
    for p in P_[hook_n:]:
        a, b = round(p["f0"] / FPS, 3), round(p["f1"] / FPS, 3)
        beats.append({"beat_idx": len(beats), "t0": a, "dur": round(b - a, 3), "narration": p["text"], "caption_lines": [p["text"]],
                      "role": "body", "primary": {"video_id": "s0", "start": a, "end": b}})
    return snap, beats, head


def compose_cached(mat: Path, mat_map: list, tl, snap, head, out_mp4: Path, work: Path, cache: Path, log: dict):
    from shopping_shorts import scene_style as SS, video_assemble as VA
    orig_layers, orig_ff = SS.render_layers, VA._run_ffmpeg
    st = {"layers": "", "scenes_cached": 0, "scenes_rendered": 0}
    rsig = _renderer_sig()
    LAYER_GLOBS = ("scene-style-layer-*.png", "scene-style-motion-*.png", "scene-style-capcut-*.png", "scene-style-layers.json")

    def layers_cached(timeline, snapshot, output, headcopy=None, job_id=None):
        snapv = SS.validate_snapshot(snapshot)
        key = sha([snapv, SS.context_for(timeline, headcopy, snapv, job_id), rsig])
        d = cache / "layers" / key
        output = Path(output)
        if (d / "scene-style-layers.json").exists():
            for g in LAYER_GLOBS:
                for f in d.glob(g):
                    shutil.copyfile(f, output / f.name)
            st["layers"] = "캐시"
            return json.loads((d / "scene-style-layers.json").read_text(encoding="utf-8"))
        L = orig_layers(timeline, snapshot, output, headcopy, job_id)
        tmp = d.with_name(key + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for g in LAYER_GLOBS:
            for f in output.glob(g):
                shutil.copyfile(f, tmp / f.name)
        shutil.rmtree(d, ignore_errors=True)
        tmp.rename(d)
        st["layers"] = "새로 렌더"
        return L

    def mat_ident(f0, n):
        out, base = [], 0
        for key, cnt in mat_map:
            a, b = max(f0, base), min(f0 + n, base + cnt)
            if a < b:
                out.append((key, a - base, b - a))
            base += cnt
        return out

    def ff(cmd, cwd=None):
        dst = Path(str(cmd[-1]))
        if not re.fullmatch(r"scene-style-\d{4}\.mp4", dst.name) or "-filter_complex" not in cmd:
            return orig_ff(cmd, cwd)
        c = list(map(str, cmd))
        first = round(float(c[c.index("-ss") + 1]) * FPS)
        n = int(c[c.index("-frames:v") + 1])
        ident = []
        for i, a in enumerate(c[:-1]):
            if a != "-i":
                ident.append(a)
                continue
            src = c[i + 1]
            if Path(src).resolve() == mat.resolve():
                ident.append(["material", mat_ident(first, n)])
            else:
                base = Path(cwd or ".") / src
                files = sorted(base.parent.glob(base.name.replace("%04d", "[0-9][0-9][0-9][0-9]"))) if "%04d" in src else [base]
                ident.append(["in", [md5(f) for f in files]])
        ident = [x for i, x in enumerate(ident) if not (i > 0 and c[i - 1] == "-i")]   # -i 다음 경로 자리는 위 내용 해시로 대신
        key = sha([ident[:-1], "ffmpeg-scene-v1"])
        hit = cache / "scenes" / f"{key}.mp4"
        target = Path(cwd or ".") / dst if not dst.is_absolute() else dst
        if hit.exists():
            shutil.copyfile(hit, target)
            st["scenes_cached"] += 1
            return None
        r = orig_ff(cmd, cwd)
        copy_atomic(target, hit)
        st["scenes_rendered"] += 1
        return r

    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    SS.render_layers, VA._run_ffmpeg = layers_cached, ff
    try:
        SS.compose(str(mat), tl, snap, str(out_mp4), work, head)
    finally:
        SS.render_layers, VA._run_ffmpeg = orig_layers, orig_ff
    log["compose"] = st


# ── 6) 소리: 나레 + BGM + 효과음(sfx_pack 호출) → 목표 LUFS ─────────────────────
def sound(w, cfg, narr: Path, total: float, out: Path, log: dict) -> Path:
    import numpy as np
    ngain = 0.0
    if cfg.get("narr_voice_dbfs") is not None:   # 효과음 팩 크기 기준(목소리 중앙 dBFS)에 나레를 맞춘다
        raw = run_bytes(["ffmpeg", "-v", "error", "-i", narr, "-ac", "1", "-ar", "44100", "-f", "f32le", "-"])
        a = np.frombuffer(raw, dtype=np.float32)
        k = int(0.02 * 44100)
        fr = a[: len(a) // k * k].reshape(-1, k)
        rms = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
        ngain = float(cfg["narr_voice_dbfs"]) - float(np.median(rms[rms > rms.max() - 30]))
    ins, flt, lab = ["-i", narr], [f"[0:a]aformat=channel_layouts=mono,volume={ngain:.2f}dB,apad=whole_dur={total:.3f}[n]"], []
    bgm = cfg.get("bgm")
    if bgm:
        nI, _ = lufs(narr)
        bfile = ROOT / bgm["file"]
        bI, _ = lufs(bfile)
        g = (nI + ngain - float(bgm["db_below_voice"])) - bI
        ins += ["-stream_loop", "-1", "-i", bfile]
        flt.append(f"[1:a]aformat=channel_layouts=mono,volume={g:.2f}dB,atrim=0:{total:.3f},afade=t=out:st={max(0, total - 0.6):.3f}:d=0.6[b]")
        lab.append("[b]")
        log["bgm"] = {"file": bgm["file"], "gain_db": round(g, 2)}
    evs = []
    sfx = cfg.get("sfx")
    if sfx:
        from shopping_shorts import sfx_pack as SP
        rmap = sfx.get("role_of_slot") or {}
        stl = []
        for li, line in enumerate(w["lines"]):
            mine = [p for p in w["pieces"] if p["line"] == li]
            t0, t1 = mine[0]["f0"] / FPS, mine[-1]["f1"] / FPS
            stl.append({"beat_idx": li, "t0": round(t0, 3), "dur": round(t1 - t0, 3), "narration": " ".join(p["text"] for p in mine),
                        "caption_lines": [p["text"] for p in mine], "cap_durs": [round((p["f1"] - p["f0"]) / FPS, 3) for p in mine],
                        "cap_lead": 0.0, "cap_offset": 0.0, "role": rmap.get(line["slot"], line["slot"])})
        pname, pdir = SP.pack_for(sfx.get("pack_customer", 0))
        pack = {"name": pname, "dir": pdir, "density": sfx.get("density", "normal"), "level": sfx.get("level", "normal"), "mute_beats": []}
        evs = SP.events(stl, pack)
        (out / "sfx_events.json").write_text(json.dumps({"pack": pname, "density": pack["density"], "events": evs, "timeline": stl},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
        base = len(ins) // 2 if not bgm else 2
        for j, (path, t, mul) in enumerate(evs):
            ins += ["-i", path]
            ms = int(round(t * 1000))
            flt.append(f"[{base + j}:a]aresample=44100,aformat=channel_layouts=mono,volume={mul:.4f},adelay={ms}|{ms}[s{j}]")
            lab.append(f"[s{j}]")
        log["sfx"] = {"pack": pname, "density": pack["density"], "count": len(evs)}
    flt.append(f"[n]{''.join(lab)}amix=inputs={1 + len(lab)}:normalize=0:duration=first[o]")
    raw = out / "mix_raw.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[o]", "-ar", "44100", "-ac", "2", raw])
    m = cfg["master"]
    mix, gain, gmax = out / "mix.wav", float(m["gain_start"]), float(m.get("gain_max", 40))
    pre = (m.get("pre") + ",") if m.get("pre") else ""
    for _ in range(10):
        run(["ffmpeg", "-y", "-i", raw, "-af", f"{pre}volume={gain:.2f}dB,alimiter=limit={10 ** (float(m['tp_limit_db']) / 20):.4f}:level=false:attack=1:release=30",
             "-ar", "44100", mix])
        oI, _ = lufs(mix)
        if abs(oI - float(m["lufs"])) <= 0.4 or gain >= gmax and oI < float(m["lufs"]):
            break
        gain = min(gmax, gain + (float(m["lufs"]) - oI) * 0.9)
    log["master"] = {"gain_db": round(gain, 2), "mix_lufs": oI}
    return mix, len(evs)


def run_bytes(cmd):
    return subprocess.run([str(c) for c in cmd], check=True, stdin=subprocess.DEVNULL, capture_output=True).stdout


# ── 7) 자동 검사(검수 매뉴얼 B 중 기계로 재는 것) ──────────────────────────────
def edge_y(video: Path, t: float) -> float:
    from PIL import Image
    b = run_bytes(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"])
    im = Image.open(io.BytesIO(b)).convert("L")
    return round(sum(i * n for i, n in enumerate(im.histogram())) / (im.width * im.height), 1)


def seam_area(work: Path):
    """영상 창 = 본문 레이어 media 칸(media_geometry) · 자막 띠 = 장면마다 달라지는 틀 그림 줄(창 안)."""
    import numpy as np
    from PIL import Image
    from shopping_shorts import scene_style as SS
    L = json.loads((work / "scene-style-layers.json").read_text(encoding="utf-8"))
    body = [l for l in L if l and l.get("kind") != "hook"] or [l for l in L if l]
    _, h, top, *_ = SS.media_geometry(body[0], {})
    win = (0, top, 1080, h)
    al = [np.asarray(Image.open(work / l["file"]).convert("RGBA"))[:, :, 3] > 20 for l in body[:12]]
    diff = np.zeros(al[0].shape[0], bool)
    for a in al[1:]:
        diff |= (a != al[0]).any(1)
    rows = [y for y in np.nonzero(diff)[0] if top <= y < top + h]
    mask = (int(min(rows)) - 10, int(max(rows)) + 10) if rows else None
    return win, mask


def checks(w, cfg, final: Path, narr: Path, sfx_n: int, out: Path, work: Path, plan: dict) -> list:
    from tools.calcopy.engine import check_seams
    C = cfg["checks"]
    rows = list()

    def add(code, name, val, ok, crit):
        rows.append({"B": code, "항목": name, "값": val, "기준": crit, "ok": bool(ok)})
    d = dur_of(final)
    I, pk = lufs(final)
    add("B1", "길이(초)", round(d, 2), C["length_s"]["allow"][0] <= d <= C["length_s"]["allow"][1], f"{C['length_s']['allow']} {C['length_s']['from']}")
    add("B2", "LUFS", I, C["lufs"]["allow"][0] <= I <= C["lufs"]["allow"][1], f"{C['lufs']['allow']} {C['lufs']['from']}")
    add("B2", "최고점 dBFS", pk, pk <= C["peak_max_dbfs"], f"≤ {C['peak_max_dbfs']}")
    chars = sum(p["chars"] for p in w["pieces"])
    cps = round(chars / dur_of(narr), 2)
    add("B3", "말속도(자/초)", cps, C["cps"]["allow"][0] <= cps <= C["cps"]["allow"][1], f"{C['cps']['allow']} {C['cps']['from']}")
    cd = sorted(round(c["n"] / FPS, 3) for c in w["cuts"])
    med = cd[len(cd) // 2]
    add("B4", "컷 중앙(초)", med, C["cut_median_s"]["allow"][0] <= med <= C["cut_median_s"]["allow"][1], f"{C['cut_median_s']['allow']} {C['cut_median_s']['from']}")
    if C.get("cut_min_s"):
        add("B4", "컷 최소(초)", cd[0], cd[0] >= C["cut_min_s"], f"≥ {C['cut_min_s']}")
    if C.get("last_cut_min_s"):
        lc = round(w["cuts"][-1]["n"] / FPS, 3)
        add("B4", "끝 컷(초)", lc, lc >= C["last_cut_min_s"], f"≥ {C['last_cut_min_s']}")
    if C.get("last_line_cut_min_s"):
        last = len(w["lines"]) - 1
        lcs = [round(c["n"] / FPS, 3) for c in w["cuts"] if w["pieces"][c["pieces"][0]]["line"] == last]
        add("B4", "마지막 묶음 컷 최소(초)", min(lcs), min(lcs) >= C["last_line_cut_min_s"], f"≥ {C['last_line_cut_min_s']}")
    tot = sum(c["n"] for c in w["cuts"])
    mr = round(sum(c["n"] for c in w["cuts"] if c["meme"]) / tot, 3)
    add("B6", "짤 비율(시간)", mr, mr <= C["meme_ratio_max"], f"≤ {C['meme_ratio_max']}")
    cnt = {}
    for c in w["cuts"]:
        if c["meme"]:
            cnt[c["src"]] = cnt.get(c["src"], 0) + 1
    mx = max(cnt.values(), default=0)
    add("B6", "같은 짤 최대 컷", mx, mx <= max(C["same_meme_max"], 0) or (C["same_meme_max"] == 0 and mx == 0), f"≤ {C['same_meme_max']}")
    ys = (edge_y(final, 0.1), edge_y(final, d - 0.15))
    add("B9", "첫/끝 밝기 Y", list(ys), min(ys) >= C["edge_y_min"], f"≥ {C['edge_y_min']}")
    r = subprocess.run([sys.executable, str(OVERLAP_TOOL), str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, env={**__import__("os").environ, "PYTHONUTF8": "1"})
    nb = re.findall(r"겹침/±3초:\s*(\d+)", r.stdout)
    add("B13", "같은 소스 중복(±3초)", int(nb[-1]) if nb else f"도구 실패 rc={r.returncode}", r.returncode == 0, "0 (check_overlap.py)")
    smax = C["sfx_max"] if C.get("sfx_max") is not None else len(w["lines"]) + int(C.get("sfx_max_extra") or 0)
    add("B14", "효과음 발수", sfx_n, sfx_n <= smax, f"≤ {smax}" + (f" (density {cfg['sfx'].get('density')})" if cfg.get("sfx") else ""))
    lr = plan.get("line_rate", {}).get("after") or []
    lim = cfg["cps"] * float((cfg.get("line_rate") or {}).get("max_ratio", 9e9))
    nlast = int((cfg.get("line_rate") or {}).get("last_lines", len(lr)))
    worst = max(lr[-nlast:]) if lr else 0
    add("B15", f"끝 {nlast}줄 말속도 최대", worst, worst <= lim + 0.05, f"≤ {lim:.2f} (줄별 {lr})")
    sl = (plan.get("line_rate") or {}).get("slowed") or {}
    add("B15", "줄별 보정 배율(±10% 이내)", sl or "없음", all(abs(1 - f) <= float((cfg.get("line_rate") or {}).get("max_change", 1)) + 1e-6 for f in sl.values()),
        f"±{(cfg.get('line_rate') or {}).get('max_change')}")
    win, mask = seam_area(work)
    sm = check_seams.check(str(final), win, mask)
    add("B16", "되감김·점프줌", f"{len(sm['되감김'])}·{len(sm['점프줌'])}", sm["ok"], "0·0 (check_seams)")
    return rows + plan_rules(w, cfg, plan)


def plan_rules(w, cfg, plan) -> list:
    """TTS·렌더 전에 잴 수 있는 것 — 계획 단계(--plan)와 완성 검사에 같은 표로 나온다(판단 한 곳)."""
    C, rows = cfg["checks"], []
    a4 = plan["A4"]
    rows.append({"B": "A4", "항목": "재료 ≥720p·확대 ≤2.3", "값": a4["값"] + (f" 흠 {a4['흠']}" if a4["흠"] else ""), "기준": "흠 0", "ok": a4["ok"]})
    cs = w["cuts"]
    near = float(C.get("aba_same_scene_s", 1e9))   # 같은 소스라도 이만큼 넘게 떨어진 구간이면 다른 장면 — 번갈아 허용
    aba = [f"#{i}~#{i + 2} {cs[i - 1]['src']}({cs[i - 1]['ss']:.1f})→{cs[i]['src']}→({cs[i + 1]['ss']:.1f})" for i in range(1, len(cs) - 1)
           if cs[i - 1]["src"] == cs[i + 1]["src"] != cs[i]["src"] and abs(cs[i + 1]["ss"] - cs[i - 1]["ss"]) <= near]
    rows.append({"B": "A12", "항목": f"A-B-A 끼움(같은 소스 ±{near:g}초 사이 다른 컷 하나)", "값": aba or 0, "ok": not aba,
                 "기준": "0 — 같은 인물은 이어 붙이고 끼운 컷은 묶음 앞·뒤로(표시만, 자동 재배치 안 함)"})
    mc = max(len(p["text"]) for p in w["pieces"])
    rows.append({"B": "A9", "항목": "자막 최대 자수", "값": mc, "기준": f"≤ {C['caption_max_chars']}", "ok": mc <= C["caption_max_chars"]})
    rule = cfg.get("tts_split")
    if rule:
        long = [f"{nchar(c)}자 '{c[:14]}…'" for c in tts_chunks([l["tts"] for l in w["lines"]], rule) if nchar(c) > int(rule["max_chars"])]
        rows.append({"B": "B15", "항목": f"TTS 덩어리 ≤{rule['max_chars']}자(쉼표에서 나눔)", "값": long or 0, "ok": not long,
                     "기준": "0 — 넘는 문장은 대본 TTS 칸에 쉼표를 넣어 나눌 것"})
    return rows


# ── 8) 계획 시트(TTS 전 선검수) ──────────────────────────────────────────
def plan_sheet(w, cfg, dst: Path):
    from PIL import Image, ImageDraw, ImageFont
    W, H = cfg["window"]
    tw, th = 200, int(200 * H / W)
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 16)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 13)
    per, cw, rh = 3, 2 * tw + 230, th + 8
    S = Image.new("RGB", (cw * per, 50 + rh * ((len(w["cuts"]) + per - 1) // per)), "white")
    d = ImageDraw.Draw(S)
    d.text((8, 8), f"{w['name']} 계획 시트(자동·TTS 전) · 컷 {len(w['cuts'])} · 토막 {len(w['pieces'])} · 예상 {sum(p['chars'] for p in w['pieces']) / cfg['cps']:.1f}초",
           fill="black", font=font)
    for k, c in enumerate(w["cuts"]):
        x0, y0 = (k % per) * cw, 50 + (k // per) * rh
        span = sum(w["pieces"][i]["chars"] for i in c["pieces"]) / cfg["cps"]
        x, y, bw, bh = c["box"]
        for j, t in enumerate((c["ss"] + 0.1, c["ss"] + max(0.2, span - 0.1))):
            b = run_bytes(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", c["path"], "-frames:v", "1", "-vf",
                           f"crop={bw}:{bh}:{x}:{y},scale={tw}:{th}", "-f", "image2pipe", "-vcodec", "png", "-"])
            if b:
                S.paste(Image.open(io.BytesIO(b)).convert("RGB"), (x0 + j * tw, y0))
        tx = x0 + 2 * tw + 6
        d.text((tx, y0), f"#{k + 1} [{c['kind']}] {span:.2f}s", fill="black", font=font)
        cap = " / ".join(w["pieces"][i]["text"] for i in c["pieces"])
        for li in range(0, min(len(cap), 60), 15):
            d.text((tx, y0 + 24 + li // 15 * 18), cap[li:li + 15], fill="#222", font=small)
        d.text((tx, y0 + 104), f"{c['src'][:20]} {c['ss']:.2f}s", fill="#444", font=small)
        d.text((tx, y0 + 122), f"확대 {H / bh:.2f}배 {c.get('src_wh')}", fill="#444", font=small)
        for li in range(0, min(len(c["seen"]), 45), 15):
            d.text((tx, y0 + 142 + li // 15 * 18), c["seen"][li:li + 15], fill="#666", font=small)
    dst.parent.mkdir(parents=True, exist_ok=True)
    S.save(dst, quality=85)


# ── 9) 한 작품 ──────────────────────────────────────────────────────────
def make_one(pdir: Path, wdir: Path, a) -> dict:
    M, cfg = load_preset(pdir)
    clk = Clock()
    log = {"preset": str(pdir), "work": str(wdir), "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    w = load_work(wdir, M, cfg)
    out = Path(a.out) if a.out else w["data"] / "make"
    cache = Path(a.cache) if a.cache else w["data"] / "_make_cache"
    out.mkdir(parents=True, exist_ok=True)
    plan = plan_check(w, cfg)
    clk.lap("읽기·재료 확인")
    if a.plan:
        plan_sheet(w, cfg, wdir / "plan" / "계획_시트_자동.jpg")
        clk.lap("계획 시트")
        rows = plan_rules(w, cfg, plan)
        print_table(w["name"] + " (계획 단계)", rows)
        fails = [f"{r['B']} {r['항목']} {r['값']}" for r in rows if not r["ok"]]
        return {"work": w["name"], "ok": None, "note": f"계획 시트 {wdir / 'plan' / '계획_시트_자동.jpg'} · " + ("; ".join(fails) or "계획 검사 통과"),
                "total_s": round(sum(clk.steps.values()), 1)}
    full = tts(w, cfg, cache, a.tts, a.allow_tts, log)
    clk.lap("TTS")
    narr, tempo = narration(full, w, cfg, out)
    log["atempo"] = tempo
    timed, dur = timing(w, narr, log)
    timed, dur, narr = fix_line_rates(timed, dur, w, cfg, narr, plan)
    log["line_rate"] = plan["line_rate"]
    clk.lap("나레·줄 시각·줄별 말속도")
    build_cuts(w, timed, dur, cfg)
    mat, mat_map = render_parts(w, cfg, cache, out, log)
    clk.lap("컷 조각")
    snap, tl, head = snapshot_and_timeline(w, M, cfg, pdir)
    vid, work = out / "video.mp4", out / "work"
    compose_cached(mat, mat_map, tl, snap, head, vid, work, cache, log)
    clk.lap("틀 합성")
    total = sum(c["n"] for c in w["cuts"]) / FPS
    mix, sfx_n = sound(w, cfg, narr, total, out, log)
    final = out / "final.mp4"
    run(["ffmpeg", "-y", "-i", vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    clk.lap("소리·완성본")
    groups, t = [], 0.0
    for c in w["cuts"]:
        groups.append({"src": c["src"], "ss": round(c["ss"], 3), "dur": round(c["n"] / FPS, 3), "t0": round(c["f0"] / FPS, 3),
                       "pieces": [i + 1 for i in c["pieces"]], "kind": c["kind"], "part_key": c["part_key"]})
    (out / "timeline.json").write_text(json.dumps({"groups": groups, "pieces": [{k: p[k] for k in ("text", "line", "t0", "t1", "f0", "f1")} for p in w["pieces"]],
                                                   "tl": tl}, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = checks(w, cfg, final, narr, sfx_n, out, work, plan)
    clk.lap("자동 검사")
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, out / "sheet_1s.jpg")
    ok = all(r["ok"] for r in rows)
    fm = md5(final)
    log["final"] = {"path": str(final), "md5": fm, "seconds": round(dur_of(final), 2)}
    brand = (M.get("brand") or {}).get("channel_name") or M.get("channel_rules", {}).get("brand") or M.get("slug")
    desk_name = f"칼카피_{brand}_{w['title_short']}{'_' + a.tag if a.tag else ''}.mp4"
    if a.test:
        log["desktop"] = log["registered"] = "건너뜀(--test)"
    elif ok:
        desk = Path(a.desktop_dir) / desk_name
        shutil.copyfile(final, desk)
        if md5(desk) != fm:
            raise RuntimeError("바탕화면 복사본 MD5 다름")
        log["desktop"] = str(desk)
        log["registered"] = register(Path(a.results), M, w, final, fm, desk_name, pdir)
    else:
        log["desktop"] = log["registered"] = "안 함(자동 검사 미달)"
    clk.lap("시트·복사·등록")
    log["checks"] = rows
    log["steps_s"] = clk.steps
    log["total_s"] = round(sum(clk.steps.values()), 1)
    (out / "run_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print_table(w["name"], rows)
    fails = [f"{r['B']} {r['항목']} {r['값']}" for r in rows if not r["ok"]]
    return {"work": w["name"], "ok": ok, "seconds": log["final"]["seconds"], "note": "; ".join(fails) or "통과", "out": str(out),
            "total_s": log["total_s"], "tts_calls": log["tts"]["calls"]}


def register(path: Path, M, w, final, fm, desk_name, pdir) -> str:
    """통과작만 결과물 목록에 한 줄(같은 완성본 경로면 그 줄을 갱신)."""
    D = json.loads(path.read_text(encoding="utf-8"))
    items = D.setdefault("items", [])
    from tools.calcopy import brands as BR          # 목록 이름 = 브랜드 장부(channel/브랜드.json) 한 곳
    row = {"channel": M.get("slug"), "channel_name": BR.brand(M.get("slug")) or (M.get("brand") or {}).get("channel_name") or M.get("channel_rules", {}).get("brand"),
           "title": w["name"], "path": final.as_posix(), "desktop": desk_name, "md5": fm, "seconds": round(dur_of(final), 2),
           "preset": pdir.relative_to(ROOT).as_posix() if pdir.is_relative_to(ROOT) else str(pdir), "date": time.strftime("%Y-%m-%d"),
           "judge": "preset_make 자동 검사 통과(사람 판정 전)", "from": "tools/calcopy/engine/preset_make.py"}
    old = next((x for x in items if x.get("path") == row["path"]), None)
    if old:
        old.update(row)
        n = old.get("n")
    else:
        n = max((int(x.get("n") or 0) for x in items), default=0) + 1
        items.append({"n": n, **row})
    path.write_text(json.dumps(D, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return f"{path} n={n}"


def print_table(name, rows):
    print(f"\n자동 검사 — {name}")
    print("| B | 항목 | 값 | 기준 | 판정 |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['B']} | {r['항목']} | {r['값']} | {r['기준']} | {'○' if r['ok'] else '× 미달'} |")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("preset")
    ap.add_argument("works", nargs="+")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--allow-tts", action="store_true")
    ap.add_argument("--tts")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--tag")
    ap.add_argument("--cache", help="캐시 폴더(기본 <자료폴더>/_make_cache) — 빈 폴더를 주면 전부 새로(시간 비교용)")
    ap.add_argument("--desktop-dir", default=str(Path.home() / "Desktop"))
    ap.add_argument("--results", default=str(RESULTS))
    a = ap.parse_args()
    works = []
    for x in a.works:
        if x.startswith("@"):
            works += [l.strip() for l in Path(x[1:]).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        else:
            works.append(x)
    if len(works) > 1 and (a.tts or a.out):
        raise SystemExit("--tts·--out 은 작품 1개일 때만")
    pdir = Path(a.preset).resolve()
    res = []
    for wd in works:
        print(f"\n=== {wd}", flush=True)
        try:
            res.append(make_one(pdir, Path(wd).resolve(), a))
        except BaseException as e:   # noqa: BLE001 — 한 작품 실패가 다음 작품을 막지 않는다(사유는 요약표에)
            if isinstance(e, KeyboardInterrupt):
                raise
            traceback.print_exc()
            res.append({"work": Path(wd).name, "ok": False, "note": f"실패: {e}"[:300]})
    print("\n요약")
    print("| 작품 | 판정 | 길이 | 걸린 초 | TTS 호출 | 사유 |")
    print("|---|---|---|---|---|---|")
    for r in res:
        v = "계획" if r["ok"] is None else "통과" if r["ok"] else "미달"
        print(f"| {r['work']} | {v} | {r.get('seconds', '')} | {r.get('total_s', '')} | {r.get('tts_calls', '')} | {r['note']} |")
    return 0 if all(r["ok"] is not False for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
