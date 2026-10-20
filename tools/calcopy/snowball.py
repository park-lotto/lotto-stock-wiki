# -*- coding: utf-8 -*-
"""눈덩이 발굴 — 한국 해외짜깁기 채널의 원음 영상 → 구글 렌즈 → 같은 영상을 올린 한국 채널 + 해외 원본 채널 → 한국 채널에서 또 반복
(사장님 10-21 "한국체널 외국체널 그렇게 검증된것만 찾아나가면 빨리 찾을수있다", 예 @떠튜브).

검증된 것만 넓힌다: 렌즈가 **같은 장면**으로 잡은 채널만 다음 바퀴 씨앗이 된다(키워드 검색 채널은 안 넣는다).
  · 한국 채널(제목·채널명에 한글) → 다음 바퀴 씨앗
  · 해외 채널 → 원본 자산 후보(우리 소재로 쓴다)
원음 판정(주인 = is_orig_audio): 360p 앞 12초 위스퍼 — 기록만 한다(--orig-only 일 때만 나레 편을 뺀다. 떠튜브는 100만+ 38편 전부 "~인데" 나레 훅 + 원음 섞임).
렌즈(주인 = tools/calcopy/lens.py lens_rows, 무료·SerpApi 안 씀): 영상 가운데 세 장면(자막 띠를 피해 가운데 60%만) — 여러 장에서 겹친 링크를 위로.

    PYTHONUTF8=1 py tools/calcopy/snowball.py run <상태.json> --seed "https://www.youtube.com/@떠튜브/shorts" [--top 8] [--min-views 1000000] [--rounds 1]
    PYTHONUTF8=1 py tools/calcopy/snowball.py report <상태.json>        # 한국/해외 채널·영상 표(md)
상태 파일은 이어 돌리기 된다(본 영상·본 채널은 건너뜀).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HANGUL = re.compile(r"[가-힣]")
VIDEO_SITE = re.compile(r"youtube\.com|youtu\.be|tiktok\.com|instagram\.com|facebook\.com|douyin\.com|bilibili\.com")


def sh(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def channel_shorts(url: str, n: int = 120) -> list[dict]:
    r = sh(["yt-dlp", "--flat-playlist", "-J", "--no-warnings", "--playlist-end", n, url], timeout=300)
    d = json.loads(r.stdout or "{}")
    return [{"id": e["id"], "title": e.get("title") or "", "views": e.get("view_count") or 0,
             "channel": d.get("channel") or d.get("uploader") or url} for e in d.get("entries") or []]


def fetch_clip(vid: str, out: Path) -> Path | None:
    p = out / f"{vid}.mp4"
    if not p.exists():
        sh(["yt-dlp", "-q", "--no-warnings", "-f", "b[height<=480][ext=mp4]/bv*[height<=480]+ba/b", "--merge-output-format", "mp4",
            "-o", str(p), f"https://www.youtube.com/shorts/{vid}"], timeout=180)
    return p if p.exists() else None


def duration(p: Path) -> float:
    try:
        return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())
    except ValueError:
        return 0.0


_WHISPER = None


def is_orig_audio(p: Path) -> dict:
    """원음 판정 한 곳: 앞 12초 한국어 말소리 글자 수. 한국어 말 ≥12자 = 나레(원음 아님)."""
    global _WHISPER
    import numpy as np
    from faster_whisper import WhisperModel
    if _WHISPER is None:
        _WHISPER = WhisperModel("small", device="cpu", compute_type="int8")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-t", "12", "-i", str(p), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.float32)
    if not len(a):
        return {"orig": True, "lang": None, "ko_chars": 0, "text": ""}
    segs, info = _WHISPER.transcribe(a, vad_filter=True)
    text = " ".join(s.text.strip() for s in segs)
    ko = len(HANGUL.findall(text))
    return {"orig": not (info.language == "ko" and ko >= 12), "lang": info.language, "ko_chars": ko, "text": text[:120]}


def frames(p: Path, out: Path, vid: str) -> list[Path]:
    """가운데 세 장면(30·50·70%) — 위아래 자막 띠를 피해 세로 가운데 60%만."""
    d = duration(p) or 10
    res = []
    for k, f in enumerate((0.3, 0.5, 0.7)):
        q = out / f"{vid}_{k}.jpg"
        sh(["ffmpeg", "-v", "error", "-y", "-ss", round(d * f, 2), "-i", p, "-frames:v", "1", "-vf", "crop=iw:ih*0.6:0:ih*0.2", q])
        if q.exists():
            res.append(q)
    return res


def owner_of(href: str, text: str) -> dict:
    """링크 → {site, key(채널/계정 식별), lang}. 유튜브 영상은 yt-dlp 로 채널을 묻는다(그 영상만 1회)."""
    site = re.sub(r"^https?://(www\.|m\.)?", "", href).split("/")[0]
    key, name = None, None
    m = re.search(r"tiktok\.com/@([\w.]+)", href) or re.search(r"instagram\.com/([\w.]+)/?(?:reel|p)?", href)
    if m and m.group(1) not in ("reel", "p", "reels"):
        key = name = "@" + m.group(1)
    yid = re.search(r"(?:watch\?v=|shorts/|youtu\.be/)([\w-]{11})", href)
    if yid:
        r = sh(["yt-dlp", "--no-warnings", "--skip-download", "--print", "%(channel)s\t%(channel_url)s\t%(view_count)s\t%(title)s", href], timeout=60)
        parts = (r.stdout.strip().split("\t") + ["", "", "", ""])[:4]
        if parts[1]:
            name, key = parts[0], parts[1]
            text = parts[3] or text
            return {"site": "youtube", "key": key, "name": name, "views": int(parts[2]) if parts[2].isdigit() else None,
                    "lang": "ko" if HANGUL.search(name + text) else "foreign", "title": text}
    return {"site": site, "key": key or href, "name": name or site, "views": None,
            "lang": "ko" if HANGUL.search((name or "") + text) else "foreign", "title": text}


def run(state_p: Path, seed: str | None, top: int, min_views: int, rounds: int, orig_only: bool = False):
    from tools.calcopy import lens as L
    from tools.calcopy.lens import SKIP_VIDEO, lens_page, lens_rows
    L.PROFILE = str(ROOT / ".lens_profile_snowball")   # 다른 세션이 .lens_profile 크롬을 쥐고 있으면 못 연다(10-21 실측) — 이 도구는 따로
    S = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() else {"channels": {}, "videos": {}}
    if seed and seed not in S["channels"]:
        S["channels"][seed] = {"name": seed, "lang": "ko", "depth": 0, "from": "씨앗", "done": False}
    tmp = Path(tempfile.gettempdir()) / "snowball"; tmp.mkdir(exist_ok=True)

    def save():
        state_p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")

    with lens_page() as pg:
        for rnd in range(rounds):
            todo = [k for k, c in S["channels"].items() if c["lang"] == "ko" and not c.get("done") and k.startswith("http")]
            if not todo:
                break
            for ck in todo:
                c = S["channels"][ck]
                url = ck if "/shorts" in ck or "/videos" in ck else ck.rstrip("/") + "/shorts"
                vids = [v for v in channel_shorts(url) if v["views"] >= min_views]
                vids.sort(key=lambda v: -v["views"])
                print(f"[바퀴{rnd + 1}] {c['name']} — {min_views:,}회 이상 {len(vids)}편")
                picked = 0
                for v in vids:
                    if picked >= top:
                        break
                    if S["videos"].get(v["id"], {}).get("lensed"):
                        picked += 1; continue
                    if False:
                        picked += bool(S["videos"][v["id"]].get("matches") is not None and S["videos"][v["id"]].get("lensed"))
                        if S["videos"][v["id"]].get("lensed") or (orig_only and not S["videos"][v["id"]].get("orig")):
                            continue
                    p = fetch_clip(v["id"], tmp)
                    if not p:
                        continue
                    a = is_orig_audio(p)
                    rec = {**S["videos"].get(v["id"], {}), **v, "from_channel": ck, **a, "matches": []}
                    S["videos"][v["id"]] = rec
                    if orig_only and not a["orig"]:
                        print(f"  나레 빼기 {v['id']} {v['title'][:30]} ({a['ko_chars']}자)"); save(); continue
                    picked += 1
                    hits = Counter(); info = {}
                    for f in frames(p, tmp, v["id"]):
                        try:
                            for r in lens_rows(pg, str(f), skip=SKIP_VIDEO):
                                if VIDEO_SITE.search(r["shop"]) and v["id"] not in r["href"]:
                                    hits[r["href"]] += 1; info[r["href"]] = r["text"]
                        except Exception as e:  # 렌즈 한 장 실패는 그 장만 — 기록은 남긴다
                            rec.setdefault("errors", []).append(str(e)[:200])
                    rec["lensed"] = True
                    for h, n in hits.most_common(15):
                        o = owner_of(h, info[h])
                        rec["matches"].append({"href": h, "hits": n, **o})
                        if o["key"] == ck or (o["site"] == "youtube" and o["key"] in (c.get("url"), ck)):
                            continue
                        ch = S["channels"].setdefault(o["key"], {"name": o["name"], "lang": o["lang"], "site": o["site"],
                                                                 "depth": c["depth"] + 1, "from": v["id"], "done": o["lang"] != "ko", "found": 0})
                        ch["found"] = ch.get("found", 0) + 1
                    ko = sum(m["lang"] == "ko" for m in rec["matches"]); fo = len(rec["matches"]) - ko
                    print(f"  원음 {v['id']} {v['title'][:30]} → 한국 {ko} · 해외 {fo}")
                    save()
                c["done"] = True; save()
    save()


def report(state_p: Path):
    S = json.loads(state_p.read_text(encoding="utf-8"))
    chs = S["channels"]
    out = ["# 눈덩이 발굴 결과", "", f"채널 {len(chs)} · 영상 {len(S['videos'])} (렌즈 {sum(bool(v.get('lensed')) for v in S['videos'].values())})", ""]
    for lang, head in (("foreign", "## 해외 원본 채널(자산 후보)"), ("ko", "## 한국 채널(다음 씨앗)")):
        out += [head, "", "| 채널 | 곳 | 렌즈로 잡힌 수 | 처음 잡힌 영상 | 깊이 |", "|---|---|---|---|---|"]
        for k, c in sorted(chs.items(), key=lambda kv: -kv[1].get("found", 0)):
            if c["lang"] == lang:
                out.append(f"| [{c['name']}]({k}) | {c.get('site', 'youtube')} | {c.get('found', '씨앗')} | {c['from']} | {c['depth']} |")
        out.append("")
    out += ["## 원음 영상 → 렌즈 결과", ""]
    for vid, v in S["videos"].items():
        if v.get("orig"):
            out.append(f"- [{v['title']}](https://www.youtube.com/shorts/{vid}) {v['views']:,}회 — " +
                       ", ".join(f"[{m['name']}]({m['href']})({'한' if m['lang'] == 'ko' else '외'}{'·' + format(m['views'], ',') if m.get('views') else ''})" for m in v["matches"][:8]))
    md = state_p.with_suffix(".md")
    md.write_text("\n".join(out), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("state")
    ap.add_argument("--seed")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--min-views", type=int, default=1_000_000)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--orig-only", action="store_true", help="앞 12초 한국어 나레 있는 영상은 렌즈 안 돌림(떠튜브처럼 전부 나레 훅이면 0편이 된다 — 10-21 실측 38/38)")
    a = ap.parse_args()
    if a.cmd == "run":
        run(Path(a.state), a.seed, a.top, a.min_views, a.rounds, a.orig_only)
    report(Path(a.state))
