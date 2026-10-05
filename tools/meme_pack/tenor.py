"""감정짤 밈팩 — Tenor 검색 결과에서 감정별 리액션 짤(mp4)을 가져온다(해외=영어 검색어, 국내=한국어 검색어).

    py tools/meme_pack/tenor.py <작업폴더> [--per 20] [--per-ko 10]
    py tools/meme_pack/tenor.py <작업폴더> --check      # 받은 것 전수 검사(파일·ffprobe)만 한다

결과: raw/tnr_<id>.mp4 + sheets/thumbs/tnr_<id>.jpg + extra_tenor.json (extra_giphy.json 과 같은 꼴 + "lang": ko|en)
이미 받은 것은 다시 안 받는다. 감정 목록·검색어의 주인은 search.py(EMOTIONS·SITE_QUERIES·SITE_QUERIES_KO) — 여기서 다시 적지 않는다.

Tenor 가 실제로 도는 방식(2026-10-05 실측):
- 검색 페이지는 브라우저 없이 그냥 GET 으로 된다: https://tenor.com/search/<낱말-낱말>-gifs , 한국어는 /ko/search/<퍼센트인코딩>-gifs
- 페이지 안 <script id="store-cache"> JSON 의 universal.search.<키>.results 에 결과 50개가 들어 있다.
  결과마다 itemurl(/view/<슬러그>-gif-<숫자 id>), flags(sticker·static·audio), tags,
  media_formats{mp4, tinymp4, gif, …: {url, dims[w,h], duration, size}} — 가장 큰 mp4 를 받는다(없으면 가장 큰 gif).
- 한국어 검색어는 사이트가 뜻을 옮겨서 찾는다 → 결과 대부분이 해외 짤이다. 그래서 국내 묶음은 한글 태그가 달린 결과를 먼저 고른다.
- 페이지에 박힌 API 키는 쓰지 않는다(공개 페이지 첫 화면 50개만 쓴다).
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import EMOTIONS, SITE_QUERIES, SITE_QUERIES_KO  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
MIN_SEC, MIN_H = 1.0, 200
PAUSE = 0.4          # 요청 사이 쉬는 시간(초)
MAX_DOWNLOADS = 500  # 한 번 실행에서 받는 파일 상한
HANGUL = re.compile(r"[가-힣]")
STORE = re.compile(r'<script[^>]*id="store-cache"[^>]*>(.*?)</script>', re.S)
VIEW_ID = re.compile(r"/view/(.*?)-?gif-(\d+)$")


class Blocked(Exception):
    """사이트가 막았다(403·429·봇 확인) — 우회하지 않고 멈춘다."""


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429):
            raise Blocked(f"HTTP {e.code} {url}") from e
        raise
    finally:
        time.sleep(PAUSE)


def search_url(query, lang):
    slug = urllib.parse.quote(query.strip().replace(" ", "-")) + "-gifs"
    return f"https://tenor.com/{'ko/' if lang == 'ko' else ''}search/{slug}"


def search(query, lang):
    """검색 페이지 → 결과 목록(페이지에 나온 순서). 결과 JSON 이 없으면 Blocked."""
    html = get(search_url(query, lang)).decode("utf-8", "replace")
    m = STORE.search(html)
    if not m:
        raise Blocked(f"검색 페이지에 결과 JSON(store-cache)이 없다: {search_url(query, lang)} (길이 {len(html)})")
    buckets = json.loads(m.group(1)).get("universal", {}).get("search", {})
    out = []
    for b in buckets.values():
        for r in b.get("results") or []:
            vm = VIEW_ID.search(urllib.parse.unquote(r.get("itemurl") or ""))
            if not vm:
                continue
            out.append({"tid": vm.group(2), "slug": vm.group(1).replace("-", " ").strip(), "source": r["itemurl"],
                        "flags": r.get("flags") or [], "formats": r.get("media_formats") or {},
                        "hangul": bool(HANGUL.search(" ".join(r.get("tags") or []) + " " + vm.group(1))),
                        "query": query})
    return out


def best_media(formats):
    """가장 큰 mp4, 없으면 가장 큰 gif → (종류, url, 폭, 높이, 길이) 또는 None."""
    for kind in ("mp4", "gif"):
        cands = [v for k, v in formats.items() if k.endswith(kind) and "transparent" not in k
                 and v.get("url") and len(v.get("dims") or []) == 2]
        if cands:
            v = max(cands, key=lambda x: x["dims"][0] * x["dims"][1])
            return kind, v["url"], v["dims"][0], v["dims"][1], float(v.get("duration") or 0)
    return None


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,codec_name,pix_fmt,width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    vs = [s for s in j.get("streams", []) if s.get("codec_type") == "video"]
    if not vs:
        raise ValueError(f"영상 스트림 없음: {r.stderr.strip()[:120]}")
    v = vs[0]
    return {"dur": float(j["format"]["duration"]), "w": int(v["width"]), "h": int(v["height"]),
            "codec": v.get("codec_name"), "pix": v.get("pix_fmt"),
            "audio": any(s.get("codec_type") == "audio" for s in j["streams"])}


def to_mp4(src, dst):
    """H.264·yuv420p·짝수 크기·faststart·무음 mp4 로 만든다. 이미 그 꼴이면 다시 굽지 않고 옮겨 담는다(화질 유지)."""
    p = probe(src)
    if p["codec"] == "h264" and p["pix"] == "yuv420p" and p["w"] % 2 == 0 and p["h"] % 2 == 0:
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:v:0", "-an", "-c:v", "copy"]
    else:
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:v:0", "-an", "-c:v", "libx264", "-crf", "18",
               "-preset", "medium", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
    r = subprocess.run(cmd + ["-movflags", "+faststart", dst], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError(f"ffmpeg 변환 실패: {r.stderr.strip()[:160]}")


def candidates(emo, lang, stats):
    """그 감정·언어의 검색어들 결과를 번갈아 섞는다. 국내(ko)는 한글 태그 달린 것을 앞으로."""
    lists = []
    for q in (SITE_QUERIES_KO if lang == "ko" else SITE_QUERIES).get(emo, []):
        try:
            lists.append(search(q, lang))
        except Blocked:
            raise
        except Exception as e:  # 검색 한 번 실패는 세어 두고 다음 검색어로
            stats["검색 실패"] += 1
            print(f"[검색 실패] {q}: {e!r}"[:200], file=sys.stderr)
    out = [lst[i] for i in range(max((len(x) for x in lists), default=0)) for lst in lists if i < len(lst)]
    if lang == "ko":
        out.sort(key=lambda c: not c["hangul"])  # 안정 정렬 — 같은 묶음 안에서는 페이지 순서 그대로
    return out


def save(rows, out_path):
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)


def check(work):
    """extra_tenor.json 전수 검사 — 줄마다 mp4·썸네일이 있고 ffprobe 로 영상·길이·높이·형식이 맞는가."""
    rows = json.load(open(os.path.join(work, "extra_tenor.json"), encoding="utf-8"))
    bad, seen = [], set()
    for r in rows:
        mp4 = os.path.join(work, "raw", r["id"] + ".mp4")
        jpg = os.path.join(work, "sheets", "thumbs", r["id"] + ".jpg")
        why = []
        if r["id"] in seen or not re.fullmatch(r"tnr_\d+", r["id"]):
            why.append("id 중복/꼴")
        seen.add(r["id"])
        if r.get("lang") not in ("ko", "en") or r.get("emotion") not in EMOTIONS:
            why.append("lang/emotion")
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
            except Exception as e:
                why.append(f"ffprobe 실패 {e!r}"[:80])
        if why:
            bad.append((r["id"], why))
    for cid, why in bad:
        print(f"[불량] {cid}: {why}")
    hs = sorted(r["h"] for r in rows)
    print(f"검사 {len(rows)}줄 · 불량 {len(bad)}"
          + (f" · 높이 중앙값 {hs[len(hs) // 2]}px · 480px 이상 {sum(1 for h in hs if h >= 480)}개" if hs else ""))
    for emo in EMOTIONS:
        ko = [r for r in rows if r["emotion"] == emo and r["lang"] == "ko"]
        en = sum(1 for r in rows if r["emotion"] == emo and r["lang"] == "en")
        print(f"  {emo}: en {en} · ko {len(ko)} (제목에 한글 {sum(1 for r in ko if HANGUL.search(r['title']))})")
    return 1 if bad else 0


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--per", type=int, default=20, help="감정당 영어 검색어(해외) 개수")
    ap.add_argument("--per-ko", type=int, default=10, help="감정당 한국어 검색어(국내) 개수")
    ap.add_argument("--check", action="store_true", help="받지 않고 전수 검사만")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if a.check:
        sys.exit(check(work))
    raw, thumbs = os.path.join(work, "raw"), os.path.join(work, "sheets", "thumbs")
    tmpdir = os.path.join(raw, "_tenor_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    os.makedirs(thumbs, exist_ok=True)
    out_path = os.path.join(work, "extra_tenor.json")
    rows = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else []
    have = {r["id"] for r in rows}
    stats = {"스티커": 0, "정지 그림": 0, "짧음(<1초)": 0, "작음(<200px)": 0, "영상 주소 없음": 0,
             "받기 실패": 0, "변환 실패": 0, "검색 실패": 0}
    downloads = searches = 0
    blocked = None
    try:
        for emo in EMOTIONS:
            for lang, per in (("ko", a.per_ko), ("en", a.per)):  # 국내 먼저 — 같은 짤이 양쪽에 나오면 드문 쪽이 갖는다
                got = sum(1 for r in rows if r["emotion"] == emo and r.get("lang") == lang)
                if got >= per:
                    continue  # 이미 찼다 — 검색도 하지 않는다
                cands = candidates(emo, lang, stats)
                searches += len((SITE_QUERIES_KO if lang == "ko" else SITE_QUERIES).get(emo, []))
                for c in cands:
                    if got >= per:
                        break
                    cid = f"tnr_{c['tid']}"
                    if cid in have:
                        continue
                    have.add(cid)  # 이번 실행에서 같은 것을 두 번 재지 않는다
                    if "sticker" in c["flags"]:
                        stats["스티커"] += 1
                        continue
                    if "static" in c["flags"]:
                        stats["정지 그림"] += 1
                        continue
                    media = best_media(c["formats"])
                    if not media:
                        stats["영상 주소 없음"] += 1
                        print(f"[영상 주소 없음] {c['source']}", file=sys.stderr)
                        continue
                    kind, url, mw, mh, mdur = media
                    if mdur < MIN_SEC:  # 사이트가 적어 둔 길이·크기로 먼저 거른다(받지 않는다)
                        stats["짧음(<1초)"] += 1
                        continue
                    if mh < MIN_H:
                        stats["작음(<200px)"] += 1
                        continue
                    if downloads >= MAX_DOWNLOADS:
                        raise Blocked(f"받기 상한 {MAX_DOWNLOADS}개에 닿았다")
                    src = os.path.join(tmpdir, f"{cid}.{kind}")
                    dst = os.path.join(raw, f"{cid}.mp4")
                    thumb = os.path.join(thumbs, f"{cid}.jpg")
                    try:
                        data = get(url)
                        downloads += 1
                        with open(src, "wb") as f:
                            f.write(data)
                    except Blocked:
                        raise
                    except Exception as e:
                        stats["받기 실패"] += 1
                        print(f"[받기 실패] {cid}: {e!r}"[:200], file=sys.stderr)
                        continue
                    try:
                        to_mp4(src, dst)
                        p = probe(dst)
                    except Exception as e:
                        stats["변환 실패"] += 1
                        print(f"[변환 실패] {cid}: {e!r}"[:200], file=sys.stderr)
                        if os.path.exists(dst):
                            os.remove(dst)
                        continue
                    finally:
                        if os.path.exists(src):
                            os.remove(src)
                    if p["dur"] < MIN_SEC or p["h"] < MIN_H:  # 받아 보니 사이트 표기와 달랐다
                        stats["짧음(<1초)" if p["dur"] < MIN_SEC else "작음(<200px)"] += 1
                        os.remove(dst)
                        continue
                    t = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{p['dur'] * 0.3:.2f}", "-i", dst,
                                        "-frames:v", "1", "-vf", "scale=-2:260", thumb], capture_output=True, text=True)
                    if t.returncode != 0 or not os.path.exists(thumb):
                        stats["변환 실패"] += 1
                        print(f"[썸네일 실패] {cid}: {t.stderr.strip()[:160]}", file=sys.stderr)
                        os.remove(dst)
                        continue
                    rows.append({"id": cid, "title": f"[TENOR] {c['slug'] or c['query']}", "emotion": emo,
                                 "duration": round(p["dur"], 2), "w": p["w"], "h": p["h"], "source": c["source"],
                                 "views": 0, "query": c["query"], "lang": lang})
                    got += 1
            ko = [r for r in rows if r["emotion"] == emo and r["lang"] == "ko"]
            en = sum(1 for r in rows if r["emotion"] == emo and r["lang"] == "en")
            print(f"{emo}: 해외(en) {en}개 · 국내(ko) {len(ko)}개(제목에 한글 {sum(1 for r in ko if HANGUL.search(r['title']))})",
                  flush=True)
            save(rows, out_path)
    except Blocked as e:
        blocked = str(e)
    finally:
        save(rows, out_path)
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"합계 {len(rows)}개 (en {sum(1 for r in rows if r['lang'] == 'en')} · ko {sum(1 for r in rows if r['lang'] == 'ko')})"
          f" · 이번 실행: 검색 {searches}번 · 받기 {downloads}개 · 건너뜀 {stats}")
    if blocked:
        print(f"[중단] {blocked}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
