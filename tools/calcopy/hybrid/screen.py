# -*- coding: utf-8 -*-
"""제품 영상 후보 — 검색 → **받기 전 가려내기**(메타·자동자막 키워드·저화질 토막 시트) → 고른 것만 1080p 로 받기 (관제 097, 2026-10-18).

왜: 장윤정·박세리 편은 후보 영상을 300~400MB 통째로 받은 뒤에야 '같은 제품인가'를 봤다(편당 1~2GB·10분+). 여기선
① 검색(yt-dlp ytsearch + 서버 유튜브 Data API 키 풀 — 둘을 합친다) ② 메타(길이·화질·업로드일·채널) ③ 자동자막(ko)에서 키워드 시각
④ 키워드 창(≤3곳×6초)만 360p 토막 → 1초 시트 1장 — 여기까지 후보당 수 MB. ⑤ 고른 영상(또는 구간)만 1080p.

    PYTHONUTF8=1 py tools/calcopy/hybrid/screen.py search <work> "검색어1" "검색어2" … [--n 12] [--exclude 단어,단어]
    PYTHONUTF8=1 py tools/calcopy/hybrid/screen.py screen <work> --keywords 테클라,tekla [--top 12]
    PYTHONUTF8=1 py tools/calcopy/hybrid/screen.py download <work> <id> [<id>…] [--sections a-b,a-b] [--prefix tekla/]

산출: <work>/screen/candidates.json(검색 합본) · <work>/screen/<id>.info.json·.ko.vtt·<id>_k.mp4(토막)·<id>_sheet.jpg · screen.json(판정 재료)
받기: <work>/src/<prefix><id>.mp4 + .info.json + .ko.vtt (재료.json cand_dir = <work>/src)
판단 주인: rank()(키워드 적중·화질·길이로 순위) — 최종 '같은 제품인가'는 사람(소넷 워커)이 시트를 보고 적는다(screen.json chosen).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import StageError, jload, jsave, run  # noqa: E402
from tools.calcopy.engine import yt_fetch as YF  # noqa: E402

# 받기·자막·키워드 적중의 주인은 engine/yt_fetch (10-18: 구간은 HLS 먼저 + 진행 없음 감시, 자막은 영상과 따로, 제목 NFC·띄어쓰기 무시)
YT_FMT_FULL = "137+ba[ext=m4a]/bv*[height>=1080]+ba/bv*[height>=720]+ba/b"
YT_FMT_PREVIEW = YF.FMT_PREVIEW_360
YT_FMT_SECTION = YF.FMT_SECTION_1080
PREVIEW_SEC = 6.0
PREVIEW_MAX = 3
PREVIEW_TIMEOUT = 120       # 토막 하나 상한(초) — 10-18 손태영: 300초 × 토막 3개 × 후보 1개(a3y5wANirWY)로 648초·1639초 두 번 죽었다
PREVIEW_STALL = 40          # 토막 파일이 이만큼 안 자라면 끊고 그 후보의 나머지 토막은 건너뛴다
MIN_HEIGHT = 720


def _ytdlp(args: list, timeout=240) -> subprocess.CompletedProcess:
    from tools.calcopy.origin_find import yt_auth          # 로그인 쿠키·JS 런타임 = 원본찾기와 같은 주인(10-21 회선 'not a bot' 우회)
    url = next((str(a) for a in args if "youtu" in str(a) or str(a).startswith("ytsearch")), "")
    auth = yt_auth("https://www.youtube.com/") if url else []
    return run(["yt-dlp", "--no-warnings", "--no-playlist", *auth, *args], check=False, timeout=timeout)


def vid_of(url_or_id: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url_or_id)
    return m.group(1) if m else url_or_id


def search(work: Path, queries: list[str], n: int = 12, exclude: list[str] | None = None, server: bool = True, log=print) -> list[dict]:
    """yt-dlp ytsearch + (가능하면) 서버 유튜브 Data API — id 로 합친다. 제목에 exclude 단어가 있으면 뺀다(가성비·TOP5 모음 등)."""
    sd = work / "screen"; sd.mkdir(parents=True, exist_ok=True)
    found: dict[str, dict] = {}

    def one(q):
        r = _ytdlp(["--flat-playlist", "-J", f"ytsearch{n}:{q}"])
        out = []
        if r.returncode == 0 and r.stdout.strip():
            for e in json.loads(r.stdout).get("entries") or []:
                if e and e.get("id"):
                    out.append({"id": e["id"], "title": e.get("title"), "duration": e.get("duration"), "channel": e.get("channel") or e.get("uploader"),
                                "views": e.get("view_count"), "q": q, "via": "yt-dlp"})
        return out
    with ThreadPoolExecutor(max_workers=4) as ex:
        for lst in ex.map(one, queries):
            for e in lst:
                found.setdefault(e["id"], e)
    if server:
        try:
            from tools.calcopy.hybrid import server_ai
            for blk in server_ai.yt_search(queries, n=n, lang="ko"):
                for it in blk.get("items") or []:
                    vid = vid_of(it["url"])
                    if vid not in found:
                        found[vid] = {"id": vid, "title": it.get("title"), "duration": None, "channel": None, "views": None, "q": blk["q"], "via": "yt-api"}
                    else:
                        found[vid]["via"] = found[vid]["via"] + "+yt-api"
        except Exception as e:                      # noqa: BLE001 — 서버 검색이 막혀도 yt-dlp 결과로 간다(사유는 남긴다)
            log(f"[search] 서버 유튜브 검색 실패(yt-dlp 결과만): {e}")
    ex_ = [x.lower() for x in (exclude or [])]
    cands = [c for c in found.values() if not any(x in (c.get("title") or "").lower() for x in ex_)]
    jsave(sd / "candidates.json", {"queries": queries, "exclude": exclude or [], "candidates": cands})
    log(f"[search] 후보 {len(cands)}개(검색어 {len(queries)}개, 서버 API {'씀' if server else '안 씀'}) → {sd / 'candidates.json'}")
    return cands


def _vtt_hits(vtt: Path, keywords: list[str]) -> list[dict]:
    from tools.calcopy.yanshot.common import vtt_words
    words = vtt_words(vtt)
    hits = []
    for t, w in words:
        if YF.kw_hit(w, keywords):
            if hits and t - hits[-1]["t"] < 2.0:
                hits[-1]["n"] += 1
            else:
                hits.append({"t": round(t, 2), "w": w, "n": 1})
    return hits


def _windows(hits: list[dict], dur: float | None, k: int = PREVIEW_MAX) -> list[tuple[float, float]]:
    top = sorted(hits, key=lambda h: -h["n"])[:k] if hits else []
    if not top:                                             # 자막이 없으면 앞·가운데·끝
        d = dur or 60.0
        return [(max(0, x - PREVIEW_SEC / 2), min(d, x + PREVIEW_SEC / 2)) for x in (d * 0.15, d * 0.5, d * 0.85)]
    wins = sorted((max(0.0, h["t"] - 1.0), h["t"] - 1.0 + PREVIEW_SEC) for h in top)
    return wins


def _sheet(mp4s: list[Path], dst: Path):
    import io
    from PIL import Image, ImageDraw
    tiles = []
    for p in mp4s:
        try:
            d = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip() or 0)
        except StageError:
            continue
        for s in range(int(d)):
            b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s + 0.5:.1f}", "-i", str(p), "-frames:v", "1", "-vf", "scale=240:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                               capture_output=True, stdin=subprocess.DEVNULL).stdout
            if b:
                im = Image.open(io.BytesIO(b)).convert("RGB"); ImageDraw.Draw(im).text((3, 3), f"{p.stem[-1]}:{s + 0.5:.1f}", fill=(255, 0, 0)); tiles.append(im)
    if not tiles:
        return None
    w, h = tiles[0].size; cols = 6
    S = Image.new("RGB", (w * cols, h * ((len(tiles) + cols - 1) // cols)), "white")
    for i, im in enumerate(tiles):
        S.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    S.save(dst, quality=85)
    return dst


def screen_one(sd: Path, vid: str, keywords: list[str], log=print) -> dict:
    url = f"https://www.youtube.com/watch?v={vid}"
    info = sd / f"{vid}.info.json"
    if not info.exists():                                       # 메타와 자막을 따로(자막 429 가 메타까지 막지 않게)
        r = _ytdlp(["--skip-download", "--write-info-json", "-o", str(sd / vid), url])
        if not info.exists():
            return {"id": vid, "error": "메타 못 받음: " + r.stderr[-200:]}
    YF.fetch_subs(url, sd / vid, log=log)                      # 자막은 최선 노력(429 면 자막 없이 간다)
    j = jload(info)
    heights = [f.get("height") or 0 for f in j.get("formats") or [] if f.get("vcodec") not in (None, "none")]
    out = {"id": vid, "title": j.get("title"), "channel": j.get("channel") or j.get("uploader"), "upload_date": j.get("upload_date"), "duration": j.get("duration"),
           "max_height": max(heights) if heights else None, "views": j.get("view_count"), "url": url, "desc_head": (j.get("description") or "")[:200]}
    vtts = sorted(sd.glob(f"{vid}*.vtt"))
    out["vtt"] = str(vtts[0]) if vtts else None
    out["hits"] = _vtt_hits(vtts[0], keywords) if vtts else []
    out["hit_n"] = sum(h["n"] for h in out["hits"])
    out["title_hit"] = YF.kw_hit(out["title"] or "", keywords)
    wins = _windows(out["hits"], out["duration"])
    clips, slow = [], None
    for k, (a, b) in enumerate(wins):
        p = sd / f"{vid}_{k}.mp4"
        if not p.exists() and slow is None:
            r = YF.ytdlp(["-f", YT_FMT_PREVIEW, "--download-sections", f"*{a:.1f}-{b:.1f}", "--force-keyframes-at-cuts", "-o", str(p), url],
                         timeout=PREVIEW_TIMEOUT, stall_sec=PREVIEW_STALL, watch=p.with_suffix(""), log=log)
            if r.stalled or r.timed_out:                        # 이 후보는 느리다 — 나머지 토막은 받지 않는다(시트는 받은 것만으로)
                slow = f"{'멈춤' if r.stalled else '시간초과'} {r.sec}초(토막 {k})"
                for q in sd.glob(f"{vid}_{k}*"):
                    q.unlink(missing_ok=True)
        if p.exists():
            clips.append(p)
    out["preview_windows"] = [[round(a, 1), round(b, 1)] for a, b in wins]
    out["slow"] = slow
    out["sheet"] = str(_sheet(clips, sd / f"{vid}_sheet.jpg")) if clips else None
    out["ok_quality"] = bool(out["max_height"] and out["max_height"] >= MIN_HEIGHT)
    log(f"[screen] {vid} {out['max_height']}p {out['duration']}s 적중 {out['hit_n']} 제목 {'○' if out['title_hit'] else '×'} {out['title'][:40] if out['title'] else ''}")
    return out


def rank(rows: list[dict]) -> list[dict]:
    """순위: 화질 통과 → 제목 적중 → 자막 적중 수 → 길이가 짧은 쪽(받기 싼 쪽)."""
    return sorted(rows, key=lambda r: (not r.get("ok_quality"), not r.get("title_hit"), -(r.get("hit_n") or 0), r.get("duration") or 9e9))


def screen(work: Path, keywords: list[str], top: int = 12, ids: list[str] | None = None, log=print) -> dict:
    sd = work / "screen"
    cands = jload(sd / "candidates.json")["candidates"] if (sd / "candidates.json").exists() else []
    ids = ids or [c["id"] for c in cands][:top]
    def safe(v):
        """후보 하나가 실패해도(yt-dlp 토막 오류 등) 그 후보만 error 로 적고 계속 — 10-18 손태영 편은 후보 1개 오류로 648초 뒤 단계가 통째로 죽었다."""
        try:
            return screen_one(sd, v, keywords, log)
        except Exception as e:  # noqa: BLE001 — 이유를 행에 남긴다(조용히 삼키지 않는다)
            log(f"[screen] {v} 실패: {type(e).__name__}: {str(e)[:160]}")
            return {"id": v, "error": f"{type(e).__name__}: {str(e)[:300]}", "ok_quality": False, "hit_n": 0, "title_hit": False}
    with ThreadPoolExecutor(max_workers=2) as ex:      # 3개 동시엔 자막 429(10-18 실측)
        rows = list(ex.map(safe, ids))
    rows = rank(rows)
    prev = jload(work / "screen.json") if (work / "screen.json").exists() else {}
    res = {"keywords": keywords, "rows": rows, "chosen": prev.get("chosen") or [], "_how": "소넷 워커: 시트(<id>_sheet.jpg)를 보고 같은 제품(라벨·포장)이 보이는 영상 id 를 chosen 에 적는다. 다른 브랜드·모음집은 뺀다",
           "errors": [{"id": r["id"], "error": r["error"]} for r in rows if r.get("error")], "slow": [{"id": r["id"], "slow": r["slow"]} for r in rows if r.get("slow")]}
    jsave(work / "screen.json", res)                    # ★부분 결과라도 항상 쓴다(10-18: 후보 1개 시간초과로 screen.json 자체가 안 나와 손으로 골랐다)
    if rows and all(r.get("error") for r in rows):
        raise StageError("후보 전부 실패(screen.json 에 사유 적음): " + "; ".join(f"{r['id']} {r['error'][:80]}" for r in rows[:3]))
    log(f"[screen] {len(rows)}개 가려냄 → {work / 'screen.json'} (화질 통과 {sum(1 for r in rows if r.get('ok_quality'))})")
    return res


def download(work: Path, ids: list[str], sections: list[tuple[float, float]] | None = None, prefix: str = "", pad: float = 20.0, log=print) -> list[Path]:
    """고른 영상만 1080p. sections 가 있으면 그 구간(±pad 초)만 받는다(--download-sections, 키프레임 재인코딩 없음)."""
    src = work / "src" / prefix if prefix else work / "src"
    src.mkdir(parents=True, exist_ok=True)
    out = []
    for vid in ids:
        url = f"https://www.youtube.com/watch?v={vid}"
        dst = src / f"{vid}.mp4"
        if not dst.exists():
            # 자막은 영상과 **다른 호출**(10-18 김가연: 자막 429 로 download 단계 통째 실패) · 구간은 HLS 먼저+멈춤 감시(한혜진: 137 구간 25분+ 0B) — 주인 engine/yt_fetch
            if sections:
                r = YF.download_sections(url, sections, dst, fmts=(YT_FMT_SECTION, YT_FMT_FULL), pad=pad, timeout=1800, extra=["--write-info-json"], log=log)
                err = r.stderr[-400:] if r else "형식 전부 실패(멈춤·시간초과)"
                if not dst.exists():
                    # 구간 받기(ffmpeg 가 영상 주소를 직접 읽음)만 0바이트로 멈추는 회선·계정이 있다 — 통째로(yt-dlp 가 직접) 받는다(10-21 yt3: 구간 0B·통째 80초 200MB)
                    log(f"[download] 구간 받기 실패 → 통째로 {vid}")
                    r2 = YF.download_full(url, dst, fmt=YT_FMT_FULL, timeout=1800, log=log)
                    err = (r2.stderr or "")[-400:]
            else:
                r = YF.download_full(url, dst, fmt=YT_FMT_FULL, timeout=1800, log=log)
                err = r.stderr[-400:]
            if not dst.exists():
                raise StageError(f"받기 실패 {vid}: {err}")
            log(f"[download] {dst} {dst.stat().st_size // 1_000_000}MB")
        YF.fetch_subs(url, src / vid, langs="ko", log=log)      # 자막은 따로·최선 노력(없어도 영상은 성공)
        out.append(dst)
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("work"); s.add_argument("q", nargs="+"); s.add_argument("--n", type=int, default=12); s.add_argument("--exclude", default=""); s.add_argument("--no-server", action="store_true")
    c = sub.add_parser("screen"); c.add_argument("work"); c.add_argument("--keywords", required=True); c.add_argument("--top", type=int, default=12); c.add_argument("--ids", default="")
    d = sub.add_parser("download"); d.add_argument("work"); d.add_argument("ids", nargs="+"); d.add_argument("--sections", default=""); d.add_argument("--prefix", default="")
    a = ap.parse_args()
    W = Path(a.work)
    if a.cmd == "search":
        search(W, a.q, a.n, [x for x in a.exclude.split(",") if x], server=not a.no_server)
    elif a.cmd == "screen":
        screen(W, a.keywords.split(","), a.top, [x for x in a.ids.split(",") if x] or None)
    else:
        secs = [tuple(map(float, s.split("-"))) for s in a.sections.split(",") if s] or None
        download(W, a.ids, secs, a.prefix)


if __name__ == "__main__":
    main()
