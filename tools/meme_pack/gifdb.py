"""감정짤 밈팩 — GIFDB(gifdb.com) 검색 결과에서 감정별 리액션 짤을 가져와 mp4 로 굽는다.

    py tools/meme_pack/gifdb.py <작업폴더> [--per 20]
    py tools/meme_pack/gifdb.py <작업폴더> --check      # 받지 않고 전수 검사만

사이트 구조(2026-10-05 실측, 브라우저 없이 일반 GET 으로 된다):
  검색   https://gifdb.com/search/<검색어>      결과 최대 40칸(쪽 넘김 없음), <ul class="gdb-masonry"> 안의 카드
  카드   /gif/<슬러그>-<16자 id>.html (움짤) · /sticker/….html (스티커 — 건너뜀)
  원본   https://gifdb.com/images/high/<슬러그>-<id>.gif   사이트 글자 없는 GIF(항목 쪽 <video>·og:video 의 .mp4 주소와 같은 파일)
         /images/branded/high/….gif 는 왼쪽 아래에 GIFDB.com 글자가 박힌 판 — 쓰지 않는다
GIF 는 프레임마다 머무는 시간이 다르다 — 진짜 길이는 PIL 로 프레임 시간을 더해 재고(20ms 미만은 브라우저·ffmpeg 처럼 100ms),
구운 mp4 길이가 그것과 맞는지 한 편씩 대조한다.
결과: raw/gdb_<id>.mp4 + sheets/thumbs/gdb_<id>.jpg + extra_gifdb.json (extra_giphy.json 과 같은 꼴 — 뷰어 serve.py 가 같이 싣는다)
      gifdb_rejects.json — 받아 보고 버린 것(짧음·작음·정지 그림)의 id. 다시 돌려도 또 받지 않게 적어 둔다.
이미 받은 것은 다시 안 받는다. 감정 목록·사이트 검색어의 주인은 search.py(EMOTIONS·SITE_QUERIES) — 여기서 다시 적지 않는다.
로그인·캡차·봇 확인을 만나면 뚫지 않고 그 자리에서 멈춘다.
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
import urllib.parse
import urllib.request

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import EMOTIONS, SITE_QUERIES  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
SITE = "https://gifdb.com"
MIN_SEC, MIN_H = 1.0, 200
PAUSE = 0.4            # 요청 사이 쉬는 시간(초)
MAX_DOWNLOADS = 400    # 한 번 실행에 받는 원본 수 상한
MAX_BYTES = 40 * 1024 * 1024
FPS = 30
DUR_TOL = 0.05         # 구운 mp4 길이와 GIF 진짜 길이의 허용 차(초) — 1프레임(1/30초) + 반올림


class Blocked(Exception):
    """사이트가 막았다(403/429/봇 확인) 또는 받기 상한 — 뚫지 않고 멈춘다."""


def get(url, limit=MAX_BYTES):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": SITE + "/"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(limit + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429, 503):
            raise Blocked(f"HTTP {e.code} — {url}") from e
        raise
    finally:
        time.sleep(PAUSE)
    if len(data) > limit:
        raise ValueError(f"너무 큼(>{limit // 1024 // 1024}MB)")
    return data


def search(query):
    """검색 쪽 → (움짤 카드 목록 [{gid, slug, title, source, query}], 스티커 카드 수). 쪽에 나온 순서 그대로."""
    html = get(f"{SITE}/search/{urllib.parse.quote(query)}", limit=5 * 1024 * 1024).decode("utf-8", "replace")
    i = html.find('class="gdb-masonry"')
    if i < 0:
        if re.search(r"captcha|cf-challenge|Just a moment", html, re.I):
            raise Blocked(f"봇 확인 쪽이 나왔다 — 검색 '{query}'")
        if re.search(r">\s*0 results\s*<", html):
            return [], 0
        raise ValueError("결과 칸(gdb-masonry)을 못 찾았다 — 사이트 꼴이 바뀌었나")
    block = html[i:html.find("</ul>", i)]
    out, seen = [], set()
    for m in re.finditer(r'href="/gif/(([a-z0-9-]*?)-?([a-z0-9]{16}))\.html"', block):
        full, words, gid = m.group(1), m.group(2), m.group(3)
        if gid in seen:
            continue
        seen.add(gid)
        out.append({"gid": gid, "slug": full, "title": words.replace("-", " ").strip(),
                    "source": f"{SITE}/gif/{full}.html", "query": query})
    stickers = len(set(re.findall(r'href="/sticker/([a-z0-9-]+)\.html"', block)))
    return out, stickers


def candidates(emo, stats):
    """그 감정의 검색어들 결과를 번갈아 섞는다(검색어 하나가 20칸을 다 차지하지 않게)."""
    lists = []
    for q in SITE_QUERIES.get(emo, []):
        try:
            found, stickers = search(q)
            stats["스티커"] += stickers
            lists.append(found)
        except Blocked:
            raise
        except Exception as e:  # 검색 한 번 실패는 세어 두고 다음 검색어로
            stats["검색 실패"] += 1
            print(f"[검색 실패] {q}: {e!r}"[:200], file=sys.stderr)
    return [lst[i] for i in range(max((len(x) for x in lists), default=0)) for lst in lists if i < len(lst)]


def gif_facts(path):
    """GIF 의 (프레임 수, 진짜 길이 초, 가로, 세로). 프레임 시간 20ms 미만은 100ms 로 친다(브라우저·ffmpeg 와 같은 규칙)."""
    with Image.open(path) as im:
        if im.format != "GIF":
            raise ValueError(f"GIF 가 아니다({im.format})")
        n = getattr(im, "n_frames", 1)
        w, h = im.size
        ms = 0
        for i in range(n):
            im.seek(i)
            d = im.info.get("duration", 0) or 0
            ms += d if d >= 20 else 100
    return n, ms / 1000.0, w, h


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,codec_name,pix_fmt,width,height:format=duration,format_name", "-of", "json", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    vs = [s for s in j.get("streams", []) if s.get("codec_type") == "video"]
    if not vs:
        raise ValueError(f"영상 스트림 없음: {r.stderr.strip()[:120]}")
    v = vs[0]
    return {"dur": float(j["format"]["duration"]), "w": int(v["width"]), "h": int(v["height"]),
            "codec": v.get("codec_name"), "pix": v.get("pix_fmt"),
            "audio": any(s.get("codec_type") == "audio" for s in j["streams"])}


def to_mp4(src, dst, seconds):
    """GIF → H.264·yuv420p·짝수 크기·faststart·무음 mp4. 크기는 원본 그대로, 길이는 GIF 진짜 길이(seconds)에 맞춘다.
    마지막 프레임이 머무는 시간까지 담으려고 끝을 복제해 늘린 뒤(tpad) -t 로 정확히 자른다."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:v:0", "-an",
           "-vf", f"tpad=stop_mode=clone:stop_duration=2,fps={FPS},scale=trunc(iw/2)*2:trunc(ih/2)*2",
           "-t", f"{seconds:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError(f"ffmpeg 변환 실패: {r.stderr.strip()[:160]}")


def save(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def check(work):
    """extra_gifdb.json 전수 검사 — 줄마다 mp4·썸네일이 있고 ffprobe 로 영상·길이·높이·형식이 맞는가."""
    rows = json.load(open(os.path.join(work, "extra_gifdb.json"), encoding="utf-8"))
    bad, seen = [], set()
    for r in rows:
        mp4 = os.path.join(work, "raw", r["id"] + ".mp4")
        jpg = os.path.join(work, "sheets", "thumbs", r["id"] + ".jpg")
        why = []
        if r["id"] in seen or not re.fullmatch(r"gdb_[a-z0-9]{16}", r["id"]):
            why.append("id 중복/꼴")
        seen.add(r["id"])
        if r.get("emotion") not in EMOTIONS or not r.get("title", "").startswith("[GIFDB] "):
            why.append("emotion/title")
        if not (os.path.exists(jpg) and os.path.getsize(jpg) > 0):
            why.append("썸네일 없음")
        if not os.path.exists(mp4):
            why.append("mp4 없음")
        else:
            try:
                p = probe(mp4)
                if p["dur"] < MIN_SEC or p["h"] < MIN_H:
                    why.append(f"길이/높이 {p['dur']:.2f}s {p['h']}px")
                if p["codec"] != "h264" or p["pix"] != "yuv420p" or p["w"] % 2 or p["h"] % 2 or p["audio"]:
                    why.append(f"형식 {p['codec']} {p['pix']} {p['w']}x{p['h']} 소리={p['audio']}")
                if (p["w"], p["h"]) != (r["w"], r["h"]) or abs(p["dur"] - r["duration"]) > 0.02:
                    why.append("JSON 과 파일 수치 다름")
                with open(mp4, "rb") as f:  # faststart = moov 가 mdat 앞
                    head = f.read(4096)
                if b"moov" not in head or (b"mdat" in head and head.find(b"mdat") < head.find(b"moov")):
                    why.append("faststart 아님")
            except Exception as e:
                why.append(f"ffprobe 실패 {e!r}"[:80])
        if why:
            bad.append((r["id"], why))
    for cid, why in bad:
        print(f"[불량] {cid}: {why}")
    hs = sorted(r["h"] for r in rows)
    ds = sorted(r["duration"] for r in rows)
    print(f"검사 {len(rows)}줄 · 불량 {len(bad)}"
          + (f" · 높이 중앙값 {hs[len(hs) // 2]}px · 480px 이상 {sum(1 for h in hs if h >= 480)}개"
             f" · 길이 중앙값 {ds[len(ds) // 2]}초(최소 {ds[0]} · 최대 {ds[-1]})" if hs else ""))
    for emo in EMOTIONS:
        print(f"  {emo}: {sum(1 for r in rows if r['emotion'] == emo)}개")
    return 1 if bad else 0


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--per", type=int, default=20, help="감정당 개수")
    ap.add_argument("--check", action="store_true", help="받지 않고 전수 검사만")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if a.check:
        sys.exit(check(work))
    raw, thumbs = os.path.join(work, "raw"), os.path.join(work, "sheets", "thumbs")
    tmpdir = os.path.join(raw, "_gifdb_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    os.makedirs(thumbs, exist_ok=True)
    out_path = os.path.join(work, "extra_gifdb.json")
    rej_path = os.path.join(work, "gifdb_rejects.json")
    rows = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else []
    rejects = json.load(open(rej_path, encoding="utf-8")) if os.path.exists(rej_path) else {}
    have = {r["id"] for r in rows} | set(rejects)
    stats = {"스티커": 0, "정지 그림": 0, "짧음(<1초)": 0, "작음(<200px)": 0, "받기 실패": 0, "변환 실패": 0,
             "길이 불일치": 0, "검색 실패": 0}
    downloads = searches = 0
    blocked = None
    try:
        for emo in EMOTIONS:
            got = sum(1 for r in rows if r["emotion"] == emo)
            if got < a.per:  # 이미 찼으면 검색도 하지 않는다
                cands = candidates(emo, stats)
                searches += len(SITE_QUERIES.get(emo, []))
                for c in cands:
                    if got >= a.per:
                        break
                    cid = f"gdb_{c['gid']}"
                    if cid in have:
                        continue
                    have.add(cid)  # 이번 실행에서 같은 것을 두 번 재지 않는다
                    if downloads >= MAX_DOWNLOADS:
                        raise Blocked(f"받기 상한 {MAX_DOWNLOADS}개에 닿았다")
                    src = os.path.join(tmpdir, f"{cid}.gif")
                    dst = os.path.join(raw, f"{cid}.mp4")
                    thumb = os.path.join(thumbs, f"{cid}.jpg")
                    try:
                        data = get(f"{SITE}/images/high/{c['slug']}.gif")
                        downloads += 1
                        if data[:4] != b"GIF8":
                            raise ValueError(f"GIF 가 아닌 응답(앞 16바이트 {data[:16]!r})")
                        with open(src, "wb") as f:
                            f.write(data)
                        n, seconds, w, h = gif_facts(src)
                    except Blocked:
                        raise
                    except Exception as e:
                        stats["받기 실패"] += 1
                        print(f"[받기 실패] {cid} {c['source']}: {e!r}"[:240], file=sys.stderr)
                        if os.path.exists(src):
                            os.remove(src)
                        continue
                    why = ("정지 그림" if n < 2 else "짧음(<1초)" if seconds < MIN_SEC
                           else "작음(<200px)" if h // 2 * 2 < MIN_H else None)
                    if why:  # 사이트가 길이·크기를 목록에 안 적어 줘서 받아 봐야 안다 — 버린 id 는 적어 두고 다시 받지 않는다
                        stats[why] += 1
                        rejects[cid] = why
                        save(rejects, rej_path)
                        os.remove(src)
                        continue
                    try:
                        to_mp4(src, dst, seconds)
                        p = probe(dst)
                    except Exception as e:
                        stats["변환 실패"] += 1
                        print(f"[변환 실패] {cid}: {e!r}"[:240], file=sys.stderr)
                        if os.path.exists(dst):
                            os.remove(dst)
                        continue
                    finally:
                        if os.path.exists(src):
                            os.remove(src)
                    if abs(p["dur"] - seconds) > DUR_TOL:
                        stats["길이 불일치"] += 1
                        print(f"[길이 불일치] {cid}: GIF {seconds:.3f}초 ↔ mp4 {p['dur']:.3f}초", file=sys.stderr)
                        os.remove(dst)
                        continue
                    t = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{p['dur'] * 0.3:.2f}", "-i", dst,
                                        "-frames:v", "1", "-vf", "scale=-2:260", thumb], capture_output=True, text=True)
                    if t.returncode != 0 or not os.path.exists(thumb):
                        stats["변환 실패"] += 1
                        print(f"[썸네일 실패] {cid}: {t.stderr.strip()[:160]}", file=sys.stderr)
                        os.remove(dst)
                        continue
                    rows.append({"id": cid, "title": f"[GIFDB] {c['title'] or c['query']}", "emotion": emo,
                                 "duration": round(p["dur"], 2), "w": p["w"], "h": p["h"], "source": c["source"],
                                 "views": 0, "query": c["query"]})
                    got += 1
                    save(rows, out_path)  # 한 편마다 — 도중에 강제로 끊겨도 받은 것을 다시 받지 않는다
            print(f"{emo}: {got}개", flush=True)
            save(rows, out_path)  # 감정 하나 끝날 때마다 — 중간에 끊겨도 받은 만큼은 쓸 수 있다
            if rejects:
                save(rejects, rej_path)
    except Blocked as e:
        blocked = str(e)
    finally:
        save(rows, out_path)
        if rejects:
            save(rejects, rej_path)
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"합계 {len(rows)}개 · 이번 실행: 검색 {searches}번 · 원본 받기 {downloads}개 · 건너뜀/실패 {stats}")
    if blocked:
        print(f"[중단] {blocked}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
