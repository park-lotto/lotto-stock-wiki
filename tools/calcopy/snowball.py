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

MIN_HITS = 2   # 검증 = 장면 3장 중 2장 이상에서 같은 링크(1장만은 엉뚱한 것 많음 — 10-21 핫템리포트 주걱·잠자리 편 실측)
HANGUL = re.compile(r"[가-힣]")
NOISE = re.compile(r"/discover/|/popular/|/hashtag/|/explore/|/marketplace/|/search|/tag/|/groups/")   # 검색·태그 페이지 = 남의 채널 아님(10-21 떠튜브 실측)
VIDEO_SITE = re.compile(r"youtube\.com|youtu\.be|tiktok\.com|instagram\.com|facebook\.com|douyin\.com|bilibili\.com")


def sh(cmd, **kw):
    """시간 초과는 그 명령만 실패로(빈 출력) — 한 링크 조회가 바퀴 전체를 죽이지 않게(10-21 핫템리포트 실측)."""
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def channel_shorts(url: str, n: int = 120) -> list[dict]:
    r = sh(["yt-dlp", "--flat-playlist", "-J", "--no-warnings", "--playlist-end", n, url], timeout=300)
    d = json.loads(r.stdout or "{}")
    return [{"id": e["id"], "title": e.get("title") or e.get("description") or "", "views": e.get("view_count") or 0,
             "url": e.get("url") if "tiktok.com" in url else f"https://www.youtube.com/shorts/{e['id']}",
             "channel": d.get("channel") or d.get("uploader") or url} for e in d.get("entries") or []]


def fetch_clip(vid: str, out: Path, url: str | None = None) -> Path | None:
    p = out / f"{vid}.mp4"
    if not p.exists():
        sh(["yt-dlp", "-q", "--no-warnings", "-f", "b[height<=480][ext=mp4]/bv*[height<=480]+ba/b", "--merge-output-format", "mp4",
            "-o", str(p), url or f"https://www.youtube.com/shorts/{vid}"], timeout=180)
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
    """링크 → {site, key(채널/계정 식별), name, lang}. 주인 = 이 함수 한 곳.
    틱톡 = 주소의 @계정 / 유튜브·인스타 = yt-dlp 로 그 영상 1회 물어 채널(인스타도 로그인 없이 됨, 10-21 실측 mz_healing_) /
    페이스북 = 주소 첫 칸(페이지 이름). 언어 = 채널명+제목에 한글이 있으면 한국."""
    site = re.sub(r"^https?://(www\.|m\.|web\.)?", "", href).split("/")[0]
    name = key = None; views = None
    m = re.search(r"tiktok\.com/@([\w.]+)", href)
    if m:
        key = f"https://www.tiktok.com/@{m.group(1)}"; name = "@" + m.group(1)
    elif re.search(r"youtube\.com|youtu\.be|instagram\.com/(reel|p|reels)/", href):
        r = sh(["yt-dlp", "--no-warnings", "--skip-download", "--print",
                "%(channel)s|||%(channel_url)s|||%(view_count)s|||%(title)s|||%(uploader_id)s", href], timeout=60)
        parts = ((r.stdout.strip().splitlines() or [""])[-1].split("|||") + [""] * 5)[:5]
        if "instagram" in site and parts[0] not in ("", "NA"):
            name = "@" + parts[0]; key = f"https://www.instagram.com/{parts[0]}/"
        elif parts[1] not in ("", "NA"):
            name, key = parts[0], parts[1]
        if parts[2].isdigit():
            views = int(parts[2])
        if parts[3] not in ("", "NA"):
            text = parts[3]
    else:
        m = re.search(r"facebook\.com/([^/?]+)/(videos|reel|posts)", href)
        if m:
            key = f"https://www.facebook.com/{m.group(1)}"; name = m.group(1)
    return {"site": site, "key": key or href, "name": name or site, "views": views, "resolved": bool(key),
            "lang": "ko" if HANGUL.search((name or "") + " " + text) else "foreign", "title": text}


def run(state_p: Path, seed: str | None, top: int, min_views: int, rounds: int, orig_only: bool = False, hl: str = "en", foreign: bool = False, site: str | None = None):
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
            # 넓힐 채널 = 한국(기본) + --foreign 이면 해외 유튜브·틱톡 계정도(인스타 계정 목록은 로그인 없이 안 받아짐 — 10-21 실측)
            todo = [k for k, c in S["channels"].items() if k.startswith("http") and not c.get(f"done_{'all' if foreign else 'ko'}", c.get("done") if not foreign else False)
                    and (c["lang"] == "ko" or (foreign and re.search(r"youtube\.com/(channel|@)|tiktok\.com/@", k)))
                    and (not site or site in k)]
            if not todo:
                break
            for ck in todo:
                c = S["channels"][ck]
                url = ck if ("/shorts" in ck or "/videos" in ck or "tiktok.com" in ck) else ck.rstrip("/") + "/shorts"
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
                    p = fetch_clip(v["id"], tmp, v.get("url"))
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
                            for r in lens_rows(pg, str(f), skip=SKIP_VIDEO, hl=hl):
                                if VIDEO_SITE.search(r["shop"]) and not NOISE.search(r["href"]) and v["id"] not in r["href"]:
                                    hits[r["href"]] += 1; info[r["href"]] = r["text"]
                        except Exception as e:  # 렌즈 한 장 실패는 그 장만 — 기록은 남긴다
                            rec.setdefault("errors", []).append(str(e)[:200])
                    rec["lensed"] = True
                    rec["raw_hits"] = [[h, n, info[h]] for h, n in hits.most_common(15)]
                    save()
                    for h, n in hits.most_common(15):
                        o = owner_of(h, info[h])
                        rec["matches"].append({"href": h, "hits": n, **o})
                        if o["key"] == ck or (o["site"] == "youtube" and o["key"] in (c.get("url"), ck)):
                            continue
                        if not o["resolved"] or n < MIN_HITS:
                            continue
                        ch = S["channels"].setdefault(o["key"], {"name": o["name"], "lang": o["lang"], "site": o["site"],
                                                                 "depth": c["depth"] + 1, "from": v["id"], "done": o["lang"] != "ko", "found": 0})
                        ch["found"] = ch.get("found", 0) + 1
                    ko = sum(m["lang"] == "ko" for m in rec["matches"]); fo = len(rec["matches"]) - ko
                    print(f"  원음 {v['id']} {v['title'][:30]} → 한국 {ko} · 해외 {fo}")
                    save()
                c["done"] = True; c["done_all" if foreign else "done_ko"] = True; save()
    save()


def verified(S: dict) -> dict:
    """검증 채널 = 원음 영상 장면 MIN_HITS 장 이상에서 겹쳐 잡힌 계정(주인 한 곳 — 다음 바퀴 씨앗도 여기서)."""
    out = {}
    for vid, v in S["videos"].items():
        for m in v.get("matches") or []:
            if m["hits"] < MIN_HITS or not m.get("resolved"):
                continue
            c = out.setdefault(m["key"], {"name": m["name"], "site": m["site"], "lang": m["lang"], "videos": [], "links": []})
            if vid not in c["videos"]:
                c["videos"].append(vid)
            c["links"].append(m["href"])
    return out


def report(state_p: Path):
    S = json.loads(state_p.read_text(encoding="utf-8"))
    V = verified(S)
    out = ["# 눈덩이 발굴 결과", "", f"렌즈 돌린 영상 {sum(bool(v.get('lensed')) for v in S['videos'].values())}편 · 검증 채널 {len(V)} "
           f"(장면 {MIN_HITS}장 이상 겹침)", ""]
    for lang, head in (("foreign", "## 해외 원본 채널(자산 후보)"), ("ko", "## 한국 채널(다음 씨앗)")):
        out += [head, "", "| 채널 | 곳 | 잡힌 영상 | 링크 |", "|---|---|---|---|"]
        for k, c in sorted(V.items(), key=lambda kv: -len(kv[1]["videos"])):
            if c["lang"] == lang:
                vids = ", ".join(f"[{S['videos'][x]['title'][:18]}]({S['videos'][x].get('url') or 'https://www.youtube.com/shorts/' + x})" for x in c["videos"])
                out.append(f"| [{c['name']}]({k}) | {c['site']} | {vids} | [영상]({c['links'][0]}) |")
        out.append("")
    md = state_p.with_suffix(".md")
    md.write_text(chr(10).join(out), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("state")
    ap.add_argument("--seed")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--min-views", type=int, default=1_000_000)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--foreign", action="store_true", help="검증된 해외 유튜브·틱톡 계정도 넓힌다(그 계정의 다른 터진 영상 → 렌즈)")
    ap.add_argument("--site", help="이 곳 계정만 넓힘(예 tiktok.com — 제품 원본이 틱톡·인스타에 몰림, 10-21)")
    ap.add_argument("--hl", default="en", help="렌즈 화면 언어 — en 이면 해외 원본이 더 잡힌다(ko 는 한국 재업 위주, 10-21 떠튜브)")
    ap.add_argument("--orig-only", action="store_true", help="앞 12초 한국어 나레 있는 영상은 렌즈 안 돌림(떠튜브처럼 전부 나레 훅이면 0편이 된다 — 10-21 실측 38/38)")
    a = ap.parse_args()
    if a.cmd == "run":
        run(Path(a.state), a.seed, a.top, a.min_views, a.rounds, a.orig_only, a.hl, a.foreign, a.site)
    report(Path(a.state))
