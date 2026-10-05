"""감정짤 밈팩 — gifer.com 검색 결과에서 감정별 리액션 짤을 가져와 mp4 로 만든다.

    py tools/meme_pack/gifer.py <작업폴더> [--per 20] [--max-dl 400]

결과: raw/gfr_<id>.mp4 + sheets/thumbs/gfr_<id>.jpg + extra_gifer.json (extra_giphy.json 과 같은 모양 — 뷰어가 같이 싣는다)
이미 받은 것은 다시 안 받는다. 감정 목록·사이트 검색어의 주인은 search.py(EMOTIONS·SITE_QUERIES) — 여기서 다시 적지 않는다.

gifer 가 도는 법(2026-10-05 실측):
- 목록: 일반 HTTP 는 JS 껍데기만 준다 → 브라우저(Playwright)로 https://gifer.com/en/s/<낱말-낱말> 을 열면
  페이지가 스스로 /api/search/media?q=<낱말-낱말>&limit=80 을 부른다. 그 응답(id·원본 가로세로·태그)을 받아 쓴다.
- 매체: https://i.gifer.com/<id>.mp4 는 원본 크기와 상관없이 **가로 480 고정**(작은 건 늘리고 큰 건 줄여 놓았다).
  원본 크기는 https://i.gifer.com/<id>.gif 다.
  → 원본 가로 ≤ 480: 사이트 mp4 를 받아 원본 크기로 되돌린다(늘린 채로 두지 않는다).
  → 원본 가로 > 480: 원본 GIF 를 받아 mp4 로 바꾼다(GIF 가 GIF_CAP 보다 크면 사이트 mp4 로 대신하고 센다).
로그인·캡차·차단을 우회하지 않는다 — 막히면 그 자리에서 멈추고 무슨 일이 있었는지 찍는다.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import EMOTIONS, SITE_QUERIES  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
MIN_SEC, MIN_H = 1.0, 200
SITE_MP4_W = 480            # 사이트 mp4 의 고정 가로(실측)
GIF_CAP = 25 * 1024 * 1024  # 원본 GIF 가 이보다 크면 받지 않는다(실측: 1920x1080 1.6초가 43MB)
PAUSE = 0.4                 # 내려받기 사이 쉬는 시간(초)
ID_OK = re.compile(r"^[A-Za-z0-9_-]+$")


class Blocked(Exception):
    """사이트가 막았다(403/429·목록이 안 옴) — 우회하지 않고 멈춘다."""


class TooBig(Exception):
    pass


def listing(page, query):
    """검색 페이지를 열고, 페이지가 스스로 부른 목록 응답을 돌려준다 → [item dict] (사이트 순서대로)."""
    slug = "-".join(query.split())
    last = None
    for attempt in range(3):
        try:
            with page.expect_response(lambda r: "/api/search/media" in r.url, timeout=45000) as info:
                nav = page.goto("https://gifer.com/en/s/" + slug, wait_until="domcontentloaded", timeout=45000)
            if nav is not None and nav.status in (403, 429):
                raise Blocked(f"검색 페이지 {slug} → HTTP {nav.status}")
            resp = info.value
            if resp.status in (403, 429):
                raise Blocked(f"목록 응답 {slug} → HTTP {resp.status}")
            items = resp.json()
            if not isinstance(items, list):
                raise ValueError(f"목록이 배열이 아니다: {str(items)[:120]}")
            # 목록만 받고 페이지를 비운다 — 열어 두면 미리보기 GIF 80개를 계속 받아 같은 서버의 내려받기가 느려진다
            page.goto("about:blank")
            return items
        except Blocked:
            raise
        except Exception as e:  # 응답 본문을 놓치는 일이 있다(실측 1/24) — 다시 연다
            last = e
            print(f"[목록 재시도 {attempt + 1}/3] {query}: {e!r}"[:200], file=sys.stderr)
            page.wait_for_timeout(1500)
    raise RuntimeError(f"목록 실패 {query}: {last!r}")


def fetch(url, dest, cap=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://gifer.com/"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            size = int(r.headers.get("Content-Length") or 0)
            if cap and size > cap:
                raise TooBig(f"{size} bytes")
            got = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    got += len(chunk)
                    if cap and got > cap:
                        raise TooBig(f">{cap} bytes")
                    f.write(chunk)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Blocked(f"{url} → HTTP {e.code}")
        raise
    if got == 0:
        raise OSError("빈 파일")


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=codec_name,pix_fmt,width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout)
    s = j["streams"][0]
    return float(j["format"]["duration"]), int(s["width"]), int(s["height"])


def even(n):
    return max(2, int(n) // 2 * 2)


def convert(src, dst, w, h):
    """H.264 · yuv420p · 짝수 크기 · faststart · 소리 없음."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-an", "-vf", f"scale={w}:{h}:flags=lanczos",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", dst], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
        raise RuntimeError("ffmpeg: " + r.stderr.strip()[-200:])


def title_of(item, query):
    """사이트가 타일 alt 로 쓰는 것과 같은 재료(그 짤의 앞 태그 3개) — 얼굴을 보고 지어내지 않는다."""
    tags = [t["tag"]["id"] for t in item.get("tags", []) if t.get("tag", {}).get("id")][:3]
    return " ".join(tags) or query


def save(rows, out_path):
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)


def take(item, raw, tmpdir, stat):
    """한 개를 받아 raw/gfr_<id>.mp4 로 만든다 → (길이, 가로, 세로) 또는 None(걸러짐). 실패는 예외."""
    gid = item["id"]
    final = os.path.join(raw, f"gfr_{gid}.mp4")
    if os.path.exists(final):  # 지난번에 받다 끊긴 것 — 다시 안 받는다
        return probe(final)
    ow = int(item.get("width") or 0)
    src = None
    if ow > SITE_MP4_W and "gif" in item["file"]["formats"]:
        src = os.path.join(tmpdir, f"{gid}.gif")
        try:
            fetch(f"https://i.gifer.com/{gid}.gif", src, cap=GIF_CAP)
            stat["원본 GIF 사용"] += 1
        except TooBig:
            stat["GIF 너무 큼→사이트 mp4(480)"] += 1
            if os.path.exists(src):
                os.remove(src)
            src = None
        stat["내려받기"] += 1
        time.sleep(PAUSE)
    if src is None:
        if "mp4" not in item["file"]["formats"]:
            raise RuntimeError("mp4 형식 없음")
        src = os.path.join(tmpdir, f"{gid}.mp4")
        fetch(f"https://i.gifer.com/{gid}.mp4", src)
        stat["사이트 mp4 사용"] += 1
        stat["내려받기"] += 1
        time.sleep(PAUSE)
    try:
        dur, sw, sh = probe(src)
        if dur < MIN_SEC:
            stat["짧음(<1초)"] += 1
            return None
        tw = min(sw, ow) if ow else sw          # 사이트가 늘려 놓은 mp4 는 원본 크기로 되돌린다
        th = sh * tw / sw
        tw, th = even(tw), even(th)
        if th < MIN_H:
            stat["작음(실측 높이<200)"] += 1
            return None
        out = os.path.join(tmpdir, f"{gid}.out.mp4")
        convert(src, out, tw, th)
        res = probe(out)
        if res[0] < MIN_SEC or res[2] < MIN_H:
            stat["짧음(<1초)" if res[0] < MIN_SEC else "작음(실측 높이<200)"] += 1
            os.remove(out)
            return None
        os.replace(out, final)
        return res
    finally:
        if os.path.exists(src):
            os.remove(src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--per", type=int, default=20)
    ap.add_argument("--max-dl", type=int, default=400, help="한 번 실행에서 내려받는 파일 수 상한")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    raw, thumbs = os.path.join(work, "raw"), os.path.join(work, "sheets", "thumbs")
    tmpdir = os.path.join(raw, "_gifer_tmp")
    os.makedirs(raw, exist_ok=True)
    os.makedirs(thumbs, exist_ok=True)
    out_path = os.path.join(work, "extra_gifer.json")
    rows = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else []
    have = {r["id"] for r in rows}
    stat = {k: 0 for k in ("내려받기", "사이트 mp4 사용", "원본 GIF 사용", "GIF 너무 큼→사이트 mp4(480)",
                           "작음(목록 높이<200)", "짧음(<1초)", "작음(실측 높이<200)", "받기·변환 실패",
                           "썸네일 실패", "목록 실패")}
    new, stopped = 0, ""
    need = [e for e in EMOTIONS if sum(1 for r in rows if r["emotion"] == e) < a.per]
    if not need:
        for emo in EMOTIONS:
            print(f"{emo}: {sum(1 for r in rows if r['emotion'] == emo)}개")
        print(f"합계 {len(rows)}개 · 새로 받은 것 0개(감정마다 이미 {a.per}개) · 내려받기 0")
        return
    os.makedirs(tmpdir, exist_ok=True)
    from playwright.sync_api import sync_playwright  # 받을 게 있을 때만 브라우저를 띄운다
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)   # 페이지는 하나만
            for emo in EMOTIONS:
                got = sum(1 for r in rows if r["emotion"] == emo)
                for q in SITE_QUERIES.get(emo, []):
                    if got >= a.per or stopped:
                        break
                    try:
                        found = listing(page, q)
                    except Blocked as e:
                        stopped = f"차단: {e}"
                        break
                    except Exception as e:
                        stat["목록 실패"] += 1
                        print(f"[목록 실패] {q}: {e!r}"[:200], file=sys.stderr)
                        continue
                    for item in found:
                        if got >= a.per:
                            break
                        gid = str(item.get("id") or "")
                        cid = f"gfr_{gid}"
                        if not ID_OK.match(gid) or cid in have:
                            continue
                        if int(item.get("height") or 0) < MIN_H:   # 목록에 적힌 원본 높이 — 받지 않고 거른다
                            have.add(cid)
                            stat["작음(목록 높이<200)"] += 1
                            continue
                        if stat["내려받기"] >= a.max_dl:
                            stopped = f"내려받기 상한 {a.max_dl} 도달"
                            break
                        have.add(cid)
                        try:
                            res = take(item, raw, tmpdir, stat)
                        except Blocked as e:
                            stopped = f"차단: {e}"
                            break
                        except Exception as e:  # 받기·변환 실패는 세어 두고 넘어간다
                            stat["받기·변환 실패"] += 1
                            print(f"[실패] {gid}: {e!r}"[:200], file=sys.stderr)
                            continue
                        if res is None:
                            continue
                        dur, w, h = res
                        path, thumb = os.path.join(raw, f"{cid}.mp4"), os.path.join(thumbs, f"{cid}.jpg")
                        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * 0.3:.2f}", "-i", path,
                                        "-frames:v", "1", "-vf", "scale=-2:260", thumb])
                        if not os.path.exists(thumb) or os.path.getsize(thumb) == 0:
                            stat["썸네일 실패"] += 1
                            print(f"[썸네일 실패] {gid}", file=sys.stderr)
                            os.remove(path)
                            continue
                        rows.append({"id": cid, "title": f"[GIFER] {title_of(item, q)}", "emotion": emo,
                                     "duration": round(dur, 2), "w": w, "h": h,
                                     "source": f"https://gifer.com/en/{gid}", "views": 0, "query": q})
                        got += 1
                        new += 1
                    page.wait_for_timeout(500)
                print(f"{emo}: {got}개", flush=True)
                save(rows, out_path)
                if stopped:
                    break
            browser.close()
    finally:
        save(rows, out_path)
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"합계 {len(rows)}개 · 새로 받은 것 {new}개 · {stat}")
    if stopped:
        print(f"[멈춤] {stopped}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
