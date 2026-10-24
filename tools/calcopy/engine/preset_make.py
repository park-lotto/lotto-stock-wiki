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
from tools.calcopy.engine.encoder import cpu_retry, venc  # noqa: E402 — 98 #79
ENC = [*venc(16), "-pix_fmt", "yuv420p"]   # 컷 조각 인코딩(두 render.py 그대로)


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
    if r.returncode and cpu_retry(cmd):      # GPU 인코딩 실패(세션 한도 등) → 같은 명령 CPU 로 한 번 더
        r = subprocess.run(cpu_retry(cmd), stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")
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


def accumulate_pieces(raw_lines: list, cfg: dict) -> list:
    """2줄 누적 자막(게시글형 — 맛템썰템·썰템쇼): 줄마다 [1줄] → [1줄\n2줄] 단계. 판단 주인 = narr_video.steps_of(accumulate) — 여기선 부르기만.
    대본 줄 text 의 '/' = 화면 줄바꿈 자리(벤치 줄 그대로 — 있으면 그 자리, 없으면 chunk_sentence 가 자른다).
    줄의 speaker 가 있으면 그 줄 첫 짝(1줄·1줄+2줄)의 화면 1줄 앞에 '화자 : '(나레는 안 읽는다 — 글자 수·말속도에서 뺀다).
    반환 조각 = {text(화면 글, 2줄이면 \n), read(새로 읽는 조각), chars, line, new_cut}."""
    from tools.calcopy import narr_video as N

    def chunks_of(s, n):
        return [c.strip() for c in s.split("/") if c.strip()] if "/" in s else N.chunk_sentence(s, n)
    steps = N.steps_of([l.get("text") or l.get("line") for l in raw_lines], int(cfg.get("chunk") or 14), "accumulate", chunks_of=chunks_of)
    out, cur, pair = [], None, 0
    for st in steps:
        li = st["line"]
        if li != cur:
            cur, pair = li, 0
        elif st["new_cut"]:
            pair += 1
        spk = (raw_lines[li].get("speaker") or "").strip()
        text = f"{spk} : {st['text']}" if spk and pair == 0 else st["text"]
        read = st["text"].split("\n")[-1]
        out.append({"text": text, "read": read, "chars": nchar(read), "line": li, "new_cut": st["new_cut"]})
    return out


def load_work(wdir: Path, M: dict, cfg: dict) -> dict:
    S = json.loads((wdir / "대본.json").read_text(encoding="utf-8"))
    R = json.loads((wdir / "재료.json").read_text(encoding="utf-8"))
    slug = M.get("slug") or wdir.parent.name
    data = Path(R.get("cand_dir") or DATA_ROOT / slug / wdir.name)
    raw_lines = S.get("lines") or S.get("spine55") or []
    lines = [{"text": l.get("text") or l.get("line"), "tts": l.get("tts") or l.get("text") or l.get("line"),
              "slot": l.get("slot") or l.get("role")} for l in raw_lines]
    acc = cfg.get("caption_mode") == "accumulate"
    if acc:   # 화면 줄바꿈 '/' 는 줄 글에서 뺀다(맞춤 검사·줄 시각용). 읽는 글은 tts 칸(없으면 줄 글)
        for l, r in zip(lines, raw_lines):
            l["text"] = " ".join(x.strip() for x in l["text"].split("/"))
            l["tts"] = r.get("tts") or l["text"]
    rows = R.get("shots") or R.get("cuts") or []
    toks = S.get("tokens")
    if toks and len(toks) != len(rows):
        raise ValueError(f"토막 {len(toks)}개 ≠ 재료 {len(rows)}개")
    pieces = accumulate_pieces(raw_lines, cfg) if acc else []
    if acc and len(pieces) != len(rows):
        raise ValueError(f"누적 자막 조각 {len(pieces)}개 ≠ 재료 행 {len(rows)}개 — 재료.json shots 를 조각마다 한 행(같은 컷이면 cont): "
                         + " | ".join(p["text"].replace("\n", "/") for p in pieces))
    for k, r in enumerate(rows if not acc else []):
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
    if norm(" ".join(p.get("read", p["text"]) for p in pieces)) != norm(" ".join(l["text"] for l in lines)):
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
                     "seen": r.get("seen") or r.get("ours") or "", "pieces": [k], "move": r.get("move")})
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
    from tools.calcopy.engine import name_dict as ND       # 사람 이름 발음 표기(주인 engine/name_dict.json) — 사전에 없는 글은 그대로
    chunks = [ND.apply_all(c, w["voice"]) for c in tts_chunks([l["tts"] for l in w["lines"]], cfg.get("tts_split"))]
    tempo = cfg.get("tts_tempo")
    whole = " ".join(l["tts"] for l in w["lines"])
    if ND.names_in(whole):
        log["tts_name_dict"] = {n: ND.spelling(n, w["voice"]) for n in ND.names_in(whole)}
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


CHUNK_WHY: list = []   # chunk_line_starts 가 종전 방식으로 넘긴 까닭(로그용)


def chunk_line_starts(w: dict, cfg: dict, cache: Path, tempo: float, narr: Path) -> list[float] | None:
    """줄 시작 = TTS 덩어리 실제 길이로 계산(추정 아님). tts() 가 덩어리를 0.25초 쉼으로 잇고 narration() 이 앞뒤 무음 자르기·긴 쉼 0.1초로
    줄이기·atempo 를 하므로, 덩어리마다 같은 처리를 해 길이를 재고 '덩어리 길이 + 0.1초 쉼' 을 쌓은 뒤 tempo 로 나눈다.
    덩어리↔줄 짝이 안 맞거나(쉼표 나누기 등) 합이 실제 나레 길이와 0.3초 넘게 다르면 None(종전 방식으로) — 10-18 썰템쇼 작품3."""
    from tools.calcopy.engine import name_dict as ND
    lines = [l["tts"] for l in w["lines"]]
    if tts_chunks(lines, cfg.get("tts_split")) != lines:
        CHUNK_WHY.append("덩어리≠줄(쉼표 나누기)"); return None
    t = cfg.get("tts_tempo")
    f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
    mid = "silenceremove=stop_periods=-1:stop_duration=0.15:stop_threshold=-45dB:stop_silence=0.1"
    ds = []
    for ln in lines:
        src = cache / "tts" / "chunk" / f"{sha([w['voice'], t, ND.apply_all(ln, w['voice'])])}.mp3"
        if not src.exists():
            CHUNK_WHY.append(f"덩어리 캐시 없음 {src.name}"); return None
        tmp = narr.with_name(f"_chunk_{len(ds)}.wav")
        run(["ffmpeg", "-y", "-i", src, "-af", f"aformat=sample_rates=44100:channel_layouts=mono,{f},areverse,{f},areverse,{mid}", tmp])
        ds.append(dur_of(tmp)); tmp.unlink()
    starts, acc = [], 0.0
    for d in ds:
        starts.append(acc / tempo); acc += d + 0.1
    total, real = (acc - 0.1) / tempo, dur_of(narr)
    if abs(total - real) > 0.12 * len(ds):          # 덩어리 사이 쉼이 덜 줄어든 만큼(실측 작품3 쉼당 0.12초)보다 크면 짝이 안 맞는 것
        CHUNK_WHY.append(f"덩어리 합 {total:.2f}초 ≠ 나레 {real:.2f}초"); return None
    from tools.calcopy import narr_video as N
    segs, _ = N.speech_segments(str(narr))
    on = [a for a, _b in segs]
    out = [0.0]
    for st in starts[1:]:
        x = st * real / total                       # 남은 쉼 차이를 고르게 나눠 늘림
        near = min(on, key=lambda o: abs(o - x)) if on else x
        out.append(round(near if abs(near - x) <= 0.4 else x, 3))   # 가장 가까운 실제 말 시작(0.4초 안)에 붙임
    for i in range(1, len(out)):
        if out[i] <= out[i - 1] + 0.3:
            CHUNK_WHY.append(f"줄 {i} 시작이 앞 줄과 0.3초 안"); return None
    return out


def timing(w: dict, narr: Path, log: dict, cfg: dict | None = None, cache: Path | None = None) -> tuple[list, float]:
    """1순위 = 무음 구간 + 글자 비율(line_starts asr=False). 경계에 쉼이 없다는 경보가 나면 그때만 받아쓰기(캐시 먼저)."""
    from tools.calcopy import narr_video as N
    steps = [{"text": p["text"], "chars": p["chars"], "new_cut": True, "line": p["line"]} for p in w["pieces"]]
    lines = [l["tts"] for l in w["lines"]]   # 받아쓰기와 맞출 글 = 실제로 읽은 글(자막과 다른 줄: 숫자 읽기·화자 이름 뺌)
    msgs = []
    W = chunk_line_starts(w, cfg, cache or w["data"] / "_make_cache", log.get("atempo") or 1.0, narr) if ((cfg or {}).get("checks") or {}).get("line_sync") else None
    if W:
        segs, dur = N.speech_segments(str(narr))
        W = W + [dur]
        starts = []
        for li in range(len(lines)):
            starts += N._place([s for s in steps if s["line"] == li], segs, 0.4, W[li], W[li + 1])
        order = [s for li in range(len(lines)) for s in steps if s["line"] == li]
        starts[0] = 0.0
        timed = [{**s, "t0": round(starts[i], 3), "t1": round(starts[i + 1] if i + 1 < len(starts) else dur, 3)} for i, s in enumerate(order)]
        log["line_timing"] = {"way": "TTS 덩어리 길이(줄 시작 계산)", "line_starts": W[:-1]}
        return timed, dur
    timed, dur = N.time_steps(steps, str(narr), lines=lines, log=msgs.append, asr=False)
    log["line_timing"] = {"way": "무음+글자비율", "경보": msgs, **({"덩어리 방식 안 씀": CHUNK_WHY[-1]} if CHUNK_WHY else {})}
    if not any("[경보]" in m for m in msgs) and ((cfg or {}).get("checks") or {}).get("line_sync"):
        # 경보 없이도 쉼표 쉼을 줄 경계로 잡는다(10-18 썰템쇼 작품3 '엥,') — line_sync 켠 프리셋은 받아쓰기 시각과 대조해 0.6초 넘게 다르면 받아쓰기로
        t2, d2 = N.time_steps(steps, str(narr), lines=lines, log=[].append, asr=True)
        if not timing_broken(t2, d2):
            st1 = {s["line"]: s["t0"] for s in reversed(timed)}
            st2 = {s["line"]: s["t0"] for s in reversed(t2)}
            gap = max((abs(st1[k] - st2[k]) for k in st1 if k in st2), default=0.0)
            if gap > 0.6:
                log["line_timing"] = {"way": "받아쓰기(무음 방식과 줄 시작 최대 %.2f초 차)" % gap, "경보": msgs}
                print(f"  [경보] 무음 방식 줄 시작이 받아쓰기와 {gap:.2f}초 달라 받아쓰기 시각을 쓴다", flush=True)
                return t2, d2
    if any("[경보]" in m for m in msgs):
        hit = find_asr_cache(narr, w["data"])
        m2 = []
        t2, d2 = N.time_steps(steps, str(narr), lines=lines, log=m2.append, asr=True)
        bad = timing_broken(t2, d2)
        if bad:   # 받아쓰기 시각이 소리 길이와 안 맞으면(제미나이 시각 늘어남 — 썰템쇼 작품1 30.6초 > 25.7초) 무음 방식 그대로 + 경보
            log["line_timing"] = {"way": "무음+글자비율(받아쓰기 시각 버림)", "asr_cache": hit or "새로 부름(무료 제미나이)", "경보": msgs + m2,
                                  "버린 까닭": bad}
            print(f"  [경보] 받아쓰기 시각 버림 — {bad}", flush=True)
        else:
            timed, dur = t2, d2
            log["line_timing"] = {"way": "받아쓰기(무음 방식 경보 뒤)", "asr_cache": hit or "새로 부름(무료 제미나이)", "경보_무음": msgs, "경보": m2}
    return timed, dur


def timing_broken(timed, dur) -> str:
    """조각 시각이 말이 되나 — 앞으로만 가고, 조각마다 0.1초 넘고, 소리 길이 안. 아니면 까닭 글."""
    for a, b in zip(timed, timed[1:]):
        if b["t0"] - a["t0"] < 0.1:
            return f"조각 '{b['text'][:10]}' 시작 {b['t0']} 이 앞 조각({a['t0']})과 0.1초 안"
    if timed and timed[-1]["t0"] > dur - 0.1:
        return f"마지막 조각 시작 {timed[-1]['t0']} ≥ 소리 길이 {dur:.2f}"
    return ""


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
    fit = cfg.get("fit_shot") or {}
    for c in w["cuts"]:
        c["f0"], c["f1"] = w["pieces"][c["pieces"][0]]["f0"], w["pieces"][c["pieces"][-1]]["f1"]
        c["n"] = max(1, c["f1"] - c["f0"])
        c["speed"] = 1.0
        if fit.get("enabled"):
            fit_shot(c, fit)
        if c["ss"] + c["n"] / FPS * c["speed"] > c["src_dur"] + 1e-3:
            raise ValueError(f"소스 길이 부족 {c['src']} {c['ss']}+{c['n'] / FPS * c['speed']:.2f}>{c['src_dur']:.2f}")
    return timed


def fit_shot(c: dict, fit: dict):
    """컷이 원본 샷(또는 짤 길이)보다 조금 길면 그 샷만 살짝 느리게 늘려 채운다 — 옆 샷이 앞머리·꼬리에 번쩍 끼지 않게(관제 097, 10-18).
    왜: 썰템쇼를 박창수(느린 말)로 바꾸자 컷이 길어져 원본 샷에 맞춰 고른 컷 16개가 옆 샷 0.06~0.4초를 끌고 들어왔고(check_shot_cross),
    2초짜리 짤 둘이 0.01~0.1초 모자라 멈췄다. 샷 경계 판단은 check_shot_cross.shot_cuts 한 곳. 늘림은 min_speed(기본 0.75배)까지만 —
    더 모자라면 그대로 두고(번쩍은 검사가 잡는다) 재료를 사람이 고친다. 결과 = c['ss']·c['speed'](렌더가 setpts 로 늘림)."""
    from tools.calcopy.engine.check_shot_cross import shot_cuts
    flash, lo, edge = float(fit.get("flash_s", 0.4)), float(fit.get("min_speed", 0.75)), 0.04
    need = c["n"] / FPS
    end = c["src_dur"]
    if not c["meme"]:
        b = [t for t in shot_cuts(c["path"], c["ss"], c["ss"] + need) if c["ss"] + edge < t < c["ss"] + need - edge]
        hb = [t for t in b if t - c["ss"] < flash]
        if hb:                                              # 앞머리 번쩍 → 앞 묶음 마지막 경계 뒤에서 시작
            c["ss"] = round(hb[-1] + edge, 3)
            b = [t for t in b if t > c["ss"] + edge]
        tb = [t for t in b if c["ss"] + need - t < flash]
        if tb:                                              # 꼬리 번쩍 → 꼬리 묶음 첫 경계 앞까지만(10-18 작품8 31.46·31.53·31.63)
            end = min(end, tb[0] - edge)
    have = end - c["ss"]
    if have < need - 1e-3 and have / need >= lo:
        c["speed"] = round(have / need, 4)


def _move(c, W, H) -> str:
    """재료.json 컷 move(sway·bounce·punch·shake) — 판단 주인 narr_video.move_vf(그림 컷 still_move 와 같은 식). 없으면 빈 글(예전 그대로)."""
    if not c.get("move"):
        return ""
    from tools.calcopy.narr_video import move_vf
    return "," + move_vf(c["move"], c["n"], W, H)


def render_parts(w, cfg, cache: Path, out: Path, log: dict) -> tuple[Path, list]:
    W, H = cfg["window"]
    H2 = H + (H % 2)
    pdir = cache / "parts"
    pdir.mkdir(parents=True, exist_ok=True)
    jobs, mat_map = [], []
    for c in w["cuts"]:
        st = c["path"].stat()
        sp = c.get("speed", 1.0)
        key = sha([str(c["path"]), st.st_size, int(st.st_mtime), round(c["ss"], 3), c["box"], W, H2, c["n"], FPS, ENC] + ([sp] if sp != 1.0 else [])
                  + ([["move", c["move"]]] if c.get("move") else []))   # move 없는 컷은 예전 키 그대로(옛 편 불변)
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
             (f"setpts=PTS/{c['speed']}," if c.get("speed", 1.0) != 1.0 else "") +
             f"crop={cw}:{ch}:{x}:{y},scale={W}:{H2}:flags=lanczos,setsar=1,fps={FPS}" + _move(c, W, H2), "-frames:v", c["n"], *ENC, tmp])
        tmp.replace(dst)
    with cf.ThreadPoolExecutor(FF_PAR) as ex:
        list(ex.map(one, jobs))
    log["parts"] = {"total": len(w["cuts"]), "rendered": len(jobs), "cached": len(w["cuts"]) - len(jobs),
                    "fit_shot": [{"src": c["src"], "ss": c["ss"], "speed": c["speed"]} for c in w["cuts"] if c.get("speed", 1.0) != 1.0]}
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


def hook_pieces(w, cfg) -> int:
    """훅 박자에 드는 조각 수 — first_line = 첫 줄 조각 전부, 그 밖 = 첫 조각 하나. 판단 한 곳(박자·틀 경계가 같이 쓴다)."""
    return sum(1 for p in w["pieces"] if p["line"] == 0) if cfg["hook"] == "first_line" else 1


def hook_end_s(w, cfg) -> float:
    """훅 카드 끝 = 본문 첫 박자 시작(훅 박자 끝). narr_video 의 hook_end(둘째 문장 시작)와 같은 자리 — 훅 줄이 한 문장이면 같다."""
    n = hook_pieces(w, cfg)
    return round(w["pieces"][n]["f0"] / FPS, 3) if n < len(w["pieces"]) else round(w["pieces"][-1]["f1"] / FPS, 3)


def frame_spans(pre: dict, t: float) -> dict:
    """틀 2장(훅+본문) 프리셋의 span 변수 = [0, t] · [t, 끝]. span 이 고정값이면 손대지 않는다(프리셋이 이긴다)."""
    from tools.calcopy.engine import preset_save as P
    fr = pre["frames"]
    if len(fr) != 2:
        raise ValueError(f"틀 {len(fr)}장 — 제작기는 훅+본문 2장만 안다(경계를 정할 규칙을 manifest 에 먼저 적어라)")
    want = {f"frames[{fr[0]['id']}].span": [0, t], f"frames[{fr[1]['id']}].span": [t, None]}
    return {k: v for k, v in want.items() if P.flat(pre).get(k) == P.VAR}


def snapshot_and_timeline(w, M, cfg, pdir: Path):
    from shopping_shorts import scene_style
    fr = cfg["frame"]["kind"]
    if fr == "preset_save":
        from tools.calcopy.engine import preset_save as P
        from shopping_shorts.calcopy_frame import to_snapshot
        from shopping_shorts.calcopy_frame import schema
        pre, Mf = P.load(pdir)
        over = dict(w["S"].get("frame_vars") or {})   # 작품마다 바꾸는 틀 글(훅 제목·게시글 제목·조회수 줄 — manifest variables 자리)
        if pre.get("frames"):
            over.update(frame_spans(pre, hook_end_s(w, cfg)))
        F = P.apply(pre, None, over or None, Mf["variable_stats"], None, Mf["rules"])
        snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(F))
        title = next((l for l in schema.all_layers(F) if l["kind"] == "text" and l["role"] == "title"), None)
        head = {"text": (title or {}).get("text") or ""}   # 틀 제목 글(narr_video·frame_video 와 같은 꼴 — 렌더러가 hook1·hook2 로 나눔)
    elif fr == "template":
        T = w["title"]
        snap = scene_style.validate_snapshot({"mode": "story", "presetId": M["template"]["preset_id"],
                                              "text": {"channel": M["brand"]["channel_name"], **T}})
        head = {"text": f"{T['hook1']}\n{T['hook2']}", "body_title": T["bodyTitle"]}
    else:
        raise ValueError(f"frame.kind 모름: {fr}")
    P_ = w["pieces"]
    beats = []
    hook_n = hook_pieces(w, cfg)
    a, b = P_[0]["f0"] / FPS, P_[hook_n - 1]["f1"] / FPS
    cap0 = w["lines"][0]["text"] if cfg["hook"] == "first_line" else P_[0]["text"]
    beats.append({"beat_idx": 0, "t0": a, "dur": round(b - a, 3), "narration": cap0, "caption_lines": [cap0], "role": "hook",
                  "primary": {"video_id": "s0", "start": a, "end": b}})
    for p in P_[hook_n:]:
        a, b = round(p["f0"] / FPS, 3), round(p["f1"] / FPS, 3)
        beats.append({"beat_idx": len(beats), "t0": a, "dur": round(b - a, 3), "narration": p["text"], "caption_lines": [p["text"]],
                      "role": "body", "primary": {"video_id": "s0", "start": a, "end": b}})
    from tools.calcopy.engine import line_fx               # 강조어 자막·모션 효과(대본 줄 emph·fx) — 칸 없으면 비트 그대로
    w["fx_placed"] = line_fx.apply(beats, [0] + [p["line"] for p in P_[hook_n:]], w["S"].get("lines") or [])
    snap = scene_style.validate_snapshot(line_fx.snapshot_patch(snap, w["fx_placed"]))
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
        ring = int(sfx.get("ring_every") or 1)   # 칸 n개마다 한 칸만 울림(나머지는 팩의 mute_beats 로) — 썰템쇼 벤치 밀도. 없으면 종전(전 칸)
        mute = [li for li in range(len(stl)) if li % ring] if ring > 1 else []
        pack = {"name": pname, "dir": pdir, "density": sfx.get("density", "normal"), "level": sfx.get("level", "normal"), "mute_beats": mute}
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
    if C.get("line_sync"):   # 자막 줄 시작 ↔ 완성본 소리(따로 받아쓰기) — 켠 프리셋만(10-18 썰템쇼 작품3 가운데 4줄 0.6~2.5초 늦음, B 표는 못 잡음)
        from tools.calcopy.engine import check_line_sync as LS
        try:
            ls = LS.check(out)
            add("B17", "자막↔소리 줄 시작(받아쓰기)", f"어긋남 {ls['bad']}줄 · 최대 {max((abs(r['diff']) for r in ls['rows'] if r['diff'] is not None), default='?')}초",
                ls["ok"], f"모든 줄 |차| ≤ {LS.LIMIT}초·못 찾은 줄 0 (check_line_sync)")
        except Exception as e:  # noqa: BLE001 — 못 쟀으면 통과로 치지 않는다
            add("B17", "자막↔소리 줄 시작(받아쓰기)", f"못 잼: {e}", False, f"≤ {LS.LIMIT}초 (check_line_sync)")
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
    mc = max(len(re.sub(r"^[^:\n]{1,10} : ", "", x)) for p in w["pieces"] for x in p["text"].split("\n"))   # 화면 줄마다(누적 2줄은 줄별, '화자 : ' 머리 뺌)
    rows.append({"B": "A9", "항목": "자막 최대 자수", "값": mc, "기준": f"≤ {C['caption_max_chars']}", "ok": mc <= C["caption_max_chars"]})
    if C.get("tts_no_jamo"):   # A11: 읽는 글에 ㅋㅋ·ㄷㄷ 같은 낱자 금지(자막엔 둔다)
        jamo = [l["tts"] for l in w["lines"] if re.search(r"[ㄱ-ㅎㅏ-ㅣ]", l["tts"])]
        rows.append({"B": "A11", "항목": "TTS 글 낱자(ㅋㅋ·ㄷㄷ) 없음", "값": jamo or 0, "ok": not jamo, "기준": "0 — 대본 줄 tts 칸에서 뺄 것"})
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
    if w["S"].get("hybrid"):   # 하이브리드(앞 칼카피 줄 + 뒤 체험 줄을 한 대본으로, 사장님 10-20) — 검사 기준만 manifest hybrid_checks 로 덮는다
        if not cfg.get("hybrid_checks"):
            raise SystemExit(f"{pdir}/manifest.json channel_rules.make 에 hybrid_checks 가 없다 — 하이브리드 길이·효과음 기준을 먼저 적어라")
        if (w["S"].get("흥미이음") or {}).get("판정") != "같음":   # 칼카피_시작 §14 '흥미 이음 같음만 렌더'(render_front.interest_gate 와 같은 규칙)
            raise SystemExit(f"{wdir}/대본.json 흥미이음.판정 이 '같음'이 아니다({(w['S'].get('흥미이음') or {}).get('판정')}) — 같은 제품을 다시 찾거나 이 편은 만들지 않는다")
        cfg = {**cfg, "checks": {**cfg["checks"], **cfg["hybrid_checks"]}}
    out = Path(a.out) if a.out else w["data"] / ("make_hybrid" if w["S"].get("hybrid") else "make")
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
    timed, dur = timing(w, narr, log, cfg, cache)
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
    # 완성본 인코딩·진짜 최고점 지킴은 engine/master_guard 한 곳(10-18 원샷1_전동칫솔: mix −0.9 → AAC 뒤 +6.3 dBFS)
    from tools.calcopy.engine.master_guard import encode_final
    log["master_guard"] = encode_final(vid, mix, final, float(cfg["checks"]["peak_max_dbfs"]))
    clk.lap("소리·완성본")
    groups, t = [], 0.0
    for c in w["cuts"]:
        groups.append({"src": c["src"], "ss": round(c["ss"], 3), "dur": round(c["n"] / FPS, 3), "t0": round(c["f0"] / FPS, 3),
                       "pieces": [i + 1 for i in c["pieces"]], "kind": c["kind"], "part_key": c["part_key"],
                       "speed": c.get("speed", 1.0), "src_span": round(c["n"] / FPS * c.get("speed", 1.0), 3),
                       **({"move": c["move"]} if c.get("move") else {})})
    if w.get("fx_placed"):
        log["fx_placed"] = w["fx_placed"]
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
    from tools.calcopy.engine.stage_log import Timer           # 단계 초를 공용 장부 꼴로도(stage_log.json, 하이브리드와 같은 꼴 — 모아 보기용)
    _tm = Timer(out / "stage_log.json")
    for _k, _v in clk.steps.items():
        _tm.done(_k, _v, work=w["name"])
    (out / "run_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print_table(w["name"], rows)
    fails = [f"{r['B']} {r['항목']} {r['값']}" for r in rows if not r["ok"]]
    return {"work": w["name"], "ok": ok, "seconds": log["final"]["seconds"], "note": "; ".join(fails) or "통과", "out": str(out),
            "total_s": log["total_s"], "tts_calls": log["tts"]["calls"]}


def register(path: Path, M, w, final, fm, desk_name, pdir) -> str:
    """통과작만 결과물 목록에 한 줄(같은 완성본 경로면 그 줄을 갱신). 편 워커 여럿이 동시에 쓰므로 잠금 아래 읽기-수정-쓰기."""
    from tools.calcopy.engine.filelock import locked
    with locked(path):
        return _register(path, M, w, final, fm, desk_name, pdir)


def _register(path: Path, M, w, final, fm, desk_name, pdir) -> str:
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
