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
    d = json.loads(r.stdout or "{}") or {}   # yt-dlp 가 null 을 주는 채널이 있다(10-21 wider)
    return [{"id": e["id"], "title": e.get("title") or e.get("description") or "", "views": e.get("view_count") or 0,
             "url": e.get("url") if "tiktok.com" in url else f"https://www.youtube.com/shorts/{e['id']}",
             "thumb": ((e.get("thumbnails") or [{}])[0].get("url") if "tiktok.com" in url else f"https://i.ytimg.com/vi/{e['id']}/oardefault.jpg"),
             "channel": d.get("channel") or d.get("uploader") or url} for e in d.get("entries") or [] if e]


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
        if not key and "instagram" not in site:   # 유튜브가 봇 확인으로 막으면(10-21 실측) 공개 oEmbed 로 채널만
            try:
                import urllib.parse, urllib.request
                o = json.loads(urllib.request.urlopen("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(href, safe=""), timeout=20).read())
                name, key, text = o["author_name"], o["author_url"], o.get("title") or text
            except Exception as e:
                print("  oEmbed 실패", href[:60], str(e)[:60])
    else:
        m = re.search(r"facebook\.com/([^/?]+)/(videos|reel|posts)", href)
        if m:
            key = f"https://www.facebook.com/{m.group(1)}"; name = m.group(1)
    return {"site": site, "key": key or href, "name": name or site, "views": views, "resolved": bool(key),
            "lang": "ko" if HANGUL.search((name or "") + " " + text) else "foreign", "title": text}


def run(state_p: Path, seed: str | None, top: int, min_views: int, rounds: int, orig_only: bool = False, hl: str = "en", foreign: bool = False, site: str | None = None, judged: bool = False):
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
            if judged:   # 제품 판정(judge)에서 '제품'으로 고른 영상의 채널만 — 목록도 다시 안 받는다
                todo = sorted({v["from_channel"] for v in S["videos"].values() if v.get("product") and not v.get("lensed")})
            if not todo:
                break
            for ck in todo:
                c = S["channels"][ck]
                url = ck if ("/shorts" in ck or "/videos" in ck or "tiktok.com" in ck) else ck.rstrip("/") + "/shorts"
                if judged:
                    vids = [v for v in S["videos"].values() if v.get("from_channel") == ck and v.get("product") and not v.get("lensed")]
                else:
                    vids = [v for v in channel_shorts(url) if v["views"] >= min_views and S["videos"].get(v["id"], {}).get("product") is not False]
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
                    rec = {**S["videos"].get(v["id"], {}), **{k: x for k, x in v.items() if k != "matches"}, "from_channel": ck, **a, "matches": []}
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
                    resolve(S, v["id"])
                    ko = sum(m["lang"] == "ko" for m in rec["matches"]); fo = len(rec["matches"]) - ko
                    print(f"  원음 {v['id']} {v['title'][:30]} → 한국 {ko} · 해외 {fo}")
                    save()
                c["done"] = True; c["done_all" if foreign else "done_ko"] = True; save()
            if judged:
                break   # 렌즈로 새로 잡힌 채널은 다시 sheet → judge(클로드 눈) 를 거쳐야 넓힌다
    save()


def resolve(S: dict, vid: str):
    """렌즈 원자료(raw_hits) → 채널 주인 매칭 + 검증 채널 등록. 주인 = 이 함수 한 곳(run 과 reowner 가 부른다)."""
    rec = S["videos"][vid]; ck = rec["from_channel"]; c = S["channels"][ck]
    rec["matches"] = []
    for h, n, text in rec.get("raw_hits") or []:
        o = owner_of(h, text)
        rec["matches"].append({"href": h, "hits": n, **o})
        if o["key"] == ck or not o["resolved"] or n < MIN_HITS:
            continue
        ch = S["channels"].setdefault(o["key"], {"name": o["name"], "lang": o["lang"], "site": o["site"],
                                                 "depth": c.get("depth", 0) + 1, "from": vid, "done": o["lang"] != "ko", "found": 0})
        ch["found"] = ch.get("found", 0) + 1


def reowner(state_p: Path, only_unresolved: bool = True):
    """주인 조회가 막혔던 영상(유튜브 봇 확인 등)을 렌즈 다시 안 돌리고 raw_hits 로 다시 푼다."""
    S = json.loads(state_p.read_text(encoding="utf-8"))
    for vid, v in S["videos"].items():
        if v.get("raw_hits") and (not only_unresolved or any(not m.get("resolved") for m in v.get("matches") or [])):
            resolve(S, vid)
            print(vid, "→", sum(m["resolved"] for m in v["matches"]), "/", len(v["matches"]))
            state_p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


SHEET_SITE = re.compile(r"youtube\.com/(channel|@)|tiktok\.com/@")   # 인스타·페북 계정 목록은 로그인 없이 안 받아진다(10-21 실측)


def sheet(state_p: Path, chans: list[str] | None, top: int, min_views: int):
    """제품 거르기 1단계(사장님 10-21 '터진 것만', 제미나이 금지 → 클로드 눈): 넓힐 채널의 터진 영상 썸네일+제목을 번호 붙인 표로.
    채널 = 검증 채널(verified) 중 아직 표에 안 올린 유튜브·틱톡 계정(--chan 이면 그것만). 판정은 judge 로 적는다."""
    import urllib.request
    from PIL import Image, ImageDraw, ImageFont
    S = json.loads(state_p.read_text(encoding="utf-8"))
    V = verified(S)
    # 같은 유튜브 채널이 /channel/UC… 와 /@핸들(oEmbed) 두 주소로 들어온다 → 이름으로도 한 번만(10-21 지구촌픽 두 번 올라감)
    done_names = {c.get("name") for c in S["channels"].values() if c.get("sheeted")}
    keys = chans or [k for k in V if SHEET_SITE.search(k) and not S["channels"].get(k, {}).get("sheeted") and V[k]["name"] not in done_names]
    tmp = Path(tempfile.gettempdir()) / "snowball" / "thumb"; tmp.mkdir(parents=True, exist_ok=True)
    rows = [r for r in S.get("sheet") or [] if "product" not in S["videos"].get(r["id"], {})]   # 이어 돌리기: 아직 판정 안 한 줄은 남긴다
    for ck in keys:
        c = S["channels"].setdefault(ck, {"name": V.get(ck, {}).get("name", ck), "lang": V.get(ck, {}).get("lang", "foreign"),
                                          "depth": 1, "from": "sheet", "done": False})
        url = ck if ("/shorts" in ck or "tiktok.com" in ck) else ck.rstrip("/") + "/shorts"
        vids = sorted((v for v in channel_shorts(url) if v["views"] >= min_views), key=lambda v: -v["views"])[:top]
        c["sheeted"] = True; c["hot"] = len(vids)
        print(f"{c['name']} — {min_views:,}회 이상 {len(vids)}편")
        for v in vids:
            old = S["videos"].get(v["id"], {})
            if old.get("lensed") or "product" in old:
                continue
            S["videos"][v["id"]] = {**old, **v, "from_channel": ck}
            rows.append({"id": v["id"], "chan": c["name"]})
        S["sheet"] = rows; state_p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")   # 채널마다 저장(중간에 죽어도 받은 목록 남김)
    S["sheet"] = rows
    state_p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    W, H, cols, per = 180, 320, 8, 24
    f = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 15)
    for p0 in range(0, len(rows), per):
        part = rows[p0:p0 + per]
        im = Image.new("RGB", (W * cols, (H + 56) * ((len(part) + cols - 1) // cols)), "white"); d = ImageDraw.Draw(im)
        for i, r in enumerate(part):
            v = S["videos"][r["id"]]; x, y = (i % cols) * W, (i // cols) * (H + 56)
            q = tmp / f"{r['id']}.jpg"
            # 유튜브 세로 썸네일(oardefault)은 없는 편이 있다 → hqdefault(10-21 실측 404 2편)
            for u in [v.get("thumb"), f"https://i.ytimg.com/vi/{r['id']}/hqdefault.jpg" if "ytimg" in (v.get("thumb") or "") else None]:
                if q.exists() or not u:
                    continue
                try:
                    q.write_bytes(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
                except Exception as e:  # 썸네일 실패는 회색 칸으로 — 판정 때 보인다
                    print("  썸네일 실패", r["id"], str(e)[:80])
            try:
                t = Image.open(q).convert("RGB"); cw = t.height * 9 // 16
                if t.width > cw:
                    t = t.crop(((t.width - cw) // 2, 0, (t.width + cw) // 2, t.height))
                im.paste(t.resize((W - 6, H)), (x + 3, y))
            except Exception:
                d.rectangle([x + 3, y, x + W - 3, y + H], fill="#ccc")
            d.rectangle([x + 3, y, x + 46, y + 24], fill="black"); d.text((x + 7, y + 2), str(p0 + i + 1), fill="yellow", font=f)
            title = v.get("title") or ""
            d.text((x + 4, y + H + 2), f"{v['views'] // 10000}만 {r['chan'][:12]}", fill="black", font=f)
            d.text((x + 4, y + H + 20), title[:16], fill="#333", font=f)
            d.text((x + 4, y + H + 37), title[16:32], fill="#333", font=f)
        out = state_p.with_name(f"{state_p.stem}_sheet{p0 // per + 1}.jpg"); im.save(out, quality=85); print(out)


def judge(state_p: Path, yes: str):
    """제품 거르기 2단계: sheet 번호 중 '물건을 손으로 보여 주는 제품 영상'만 yes(쉼표). 나머지는 product=False — run --judged 는 yes 만 렌즈."""
    S = json.loads(state_p.read_text(encoding="utf-8"))
    ok = {int(x) for x in yes.split(",") if x.strip()}
    for n, r in enumerate(S.get("sheet") or [], 1):
        S["videos"][r["id"]]["product"] = n in ok
    state_p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"제품 {len(ok)} / {len(S.get('sheet') or [])}")


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
    ap.add_argument("cmd", choices=["run", "report", "sheet", "judge", "reowner"])
    ap.add_argument("--chan", action="append", help="sheet: 이 채널만(여러 번)")
    ap.add_argument("--yes", default="", help="judge: 제품 영상 번호(쉼표)")
    ap.add_argument("--judged", action="store_true", help="run: judge 에서 제품으로 고른 영상만 렌즈")
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
        run(Path(a.state), a.seed, a.top, a.min_views, a.rounds, a.orig_only, a.hl, a.foreign, a.site, a.judged)
    elif a.cmd == "sheet":
        sheet(Path(a.state), a.chan, a.top, a.min_views); sys.exit()
    elif a.cmd == "reowner":
        reowner(Path(a.state))
    elif a.cmd == "judge":
        judge(Path(a.state), a.yes); sys.exit()
    report(Path(a.state))
