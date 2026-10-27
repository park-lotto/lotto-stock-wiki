# -*- coding: utf-8 -*-
"""얜샷템 파이프라인 공용 조각 — 경로·명령 실행·자막(vtt) 낱말 시각·소리 크기. 판단은 여기 두지 않는다(각 단계 모듈이 주인)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORK_BASE = Path("C:/숏템_칼카피/yanshottem")
DESKTOP = Path("C:/Users/CH/Desktop")
YT_FMT = "137+ba[ext=m4a]/bv*[height>=1080]+ba/b"     # 공통 규칙: web 클라이언트, android 금지, 720p 미만 금지
# 제미나이 모델 순서 — 10-17 실측: gemini-3.5-flash 는 42키 전부 오늘 한도(장부), 3-flash-preview 27키 살아 있음
GEM_MODELS = ("gemini-3-flash-preview", "gemini-flash-latest", "gemini-flash-lite-latest")
BENCH_FMT = "bv*[height>=1080]+ba/bv*[height>=720]+ba/b"


class StageError(RuntimeError):
    """단계 실패 — 이유를 들고 멈춘다(조용한 실패 금지)."""


def run(cmd: list, timeout: int | None = None, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if check and r.returncode != 0:
        raise StageError(f"명령 실패 rc={r.returncode}: {' '.join(str(c) for c in cmd)[:200]}\n{r.stderr[-800:]}")
    return r


def dur_of(p) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)])
    return float(r.stdout.strip() or 0)


def lufs_of(p, a: float | None = None, b: float | None = None) -> dict:
    """통합 LUFS·최고점(dBFS) — ebur128 peak=true."""
    cmd = ["ffmpeg", "-hide_banner"]
    if a is not None:
        cmd += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}"]
    cmd += ["-i", str(p), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]
    e = run(cmd, check=False).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", e)
    pk = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", e)
    return {"I": float(I[-1]) if I else None, "peak": float(pk[-1]) if pk and pk[-1] != "-inf" else None}


def md5(p) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jsave(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 자막(vtt) 낱말 시각 ─────────────────────────────────────────────
_TS = re.compile(r"(\d+):(\d+):(\d+\.\d+)")
_TAG = re.compile(r"<(\d+:\d+:\d+\.\d+)>")


def _sec(s: str) -> float:
    h, m, x = _TS.match(s).groups()
    return int(h) * 3600 + int(m) * 60 + float(x)


def vtt_words(path) -> list[tuple[float, str]]:
    """유튜브 자동자막 vtt → [(시작초, 낱말)]. 큐마다 마지막 줄이 '새 줄'(앞 줄은 되풀이) — 10ms 큐는 되풀이라 버린다.
    낱말 시각 태그가 없는 한 낱말 줄은 큐 시작 시각."""
    txt = Path(path).read_text(encoding="utf-8", errors="replace").replace("\r", "")
    out: list[tuple[float, str]] = []
    last_line = None
    for block in txt.split("\n\n"):
        lines = [l for l in block.split("\n") if l.strip()]
        hd = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if hd is None:
            continue
        a, b = [x.strip().split(" ")[0] for x in lines[hd].split("-->")]
        t0, t1 = _sec(a), _sec(b)
        body = [l for l in lines[hd + 1:] if l.strip()]
        if not body or t1 - t0 < 0.05:
            continue
        cur = body[-1]
        if cur == last_line:
            continue
        last_line = cur
        cur = cur.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&").replace("&nbsp;", " ")
        def emit(t, w):
            if w.startswith(">>"):          # 화자 바뀜 표식 — 낱말과 갈라 ">>" 한 칸으로 남긴다(원음 구간이 넘지 않게)
                out.append((round(t, 3), ">>"))
                w = w[2:]
            w = w.strip()
            if w:
                out.append((round(t, 3), w))
        if "<c>" in cur or _TAG.search(cur):
            parts = re.split(r"(<\d+:\d+:\d+\.\d+>)", cur)
            t = t0
            for p in parts:
                m = _TAG.fullmatch(p)
                if m:
                    t = _sec(m.group(1))
                    continue
                toks = re.sub(r"</?c[^>]*>", "", p).split()
                k = 0
                while k < len(toks):
                    w = toks[k]
                    if w == ">>" and k + 1 < len(toks):
                        out.append((round(t, 3), ">>")); k += 1; continue
                    emit(t, w); k += 1
        else:
            toks = cur.split()
            for k, w in enumerate(toks):
                if w == ">>":
                    out.append((round(t0, 3), ">>"))
                else:
                    emit(t0, w)
    return out


def norm(s: str) -> str:
    """지문 대조용 — 한글·숫자·영문만(띄어쓰기·문장부호 뺌), 영문 소문자."""
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


class Timer:
    """단계별 소요 초 → make_log.json."""

    def __init__(self, path):
        self.path = Path(path)
        self.log = jload(self.path) if self.path.exists() else {"runs": []}
        self.cur = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "stages": {}}
        self.log["runs"].append(self.cur)

    def done(self, stage: str, sec: float, note: str = ""):
        self.cur["stages"][stage] = {"sec": round(sec, 1), "note": note}
        self.save()

    def save(self):
        self.cur["total_sec"] = round(sum(v["sec"] for v in self.cur["stages"].values()), 1)
        jsave(self.path, self.log)
