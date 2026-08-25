"""장비템(만물상점류) 채널 발굴 루프 — 검색 → 쇼츠 길이 판정 → 통과 목록.

지난 라운드(2026-08-25 1R·2R)는 스크래치패드 스크립트로 돌려 사라졌다.
같은 조사를 또 하지 않도록 여기에 고정한다(handoff/장비템축.md 참조).

판정 기준은 2R 실측에서 나온 것:
  통과   : 쇼츠 존재 + duration 중앙 10~30초        (정답 만물상점이 이 구간)
  배제(1): 중앙 30~90초  = 나레이션 장편리뷰형(배제 사유 1위)
  배제(2): 중앙 6~9초    = 무내레이션 루프 컴필
  배제(3): 중앙 90초+    = 장편 리뷰 채널
★키워드는 '제품명'을 써라. 후킹 문구로 검색하면 그 영상 하나만 나온다(2R 반증 실측).

사용:
  py tools/gear_discover.py search --kw-file kw.txt --seeds yt_seeds.txt --out cand.json
  py tools/gear_discover.py probe  --in cand.json --out result.json
"""
import argparse, json, os, re, statistics, subprocess, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://www.googleapis.com/youtube/v3/search?"


def load_keys(env_path):
    for line in open(env_path, encoding="utf-8", errors="ignore"):
        if line.startswith("YOUTUBE_API_KEY"):
            return [k.strip() for k in line.split("=", 1)[1].strip().split(",") if k.strip()]
    return []


def seed_ids(path):
    """시드 URL 목록 → 채널ID 집합."""
    out = set()
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.search(r"(UC[\w-]{22})", line)
        if m:
            out.add(m.group(1))
    return out


def search(keys, q, pages=1):
    """키워드 1개 검색 → [(channelId, channelTitle, videoTitle)]. 키는 죽으면 다음으로."""
    got, token, ki = [], None, 0
    for _ in range(pages):
        while ki < len(keys):
            p = {"part": "snippet", "q": q, "type": "video", "videoDuration": "short",
                 "maxResults": 50, "regionCode": "KR", "relevanceLanguage": "ko",
                 "key": keys[ki]}
            if token:
                p["pageToken"] = token
            try:
                with urllib.request.urlopen(API + urllib.parse.urlencode(p), timeout=20) as r:
                    data = json.load(r)
                break
            except Exception as e:              # 403/429 = 그 키 사망·소진 → 다음 키
                print(f"    key#{ki} 실패({e}) → 다음 키", file=sys.stderr)
                ki += 1
        else:
            raise SystemExit("모든 키 소진 — 쿼터 리셋(KST 16시경) 뒤 재시도")
        for it in data.get("items", []):
            s = it["snippet"]
            got.append((s["channelId"], s["channelTitle"], s["title"]))
        token = data.get("nextPageToken")
        if not token:
            break
    return got


def _ids_and_titles(cid, limit=30):
    """yt-dlp flat(쿼터 0)로 채널 쇼츠의 videoId·제목만 받는다.
    ★flat 목록은 duration을 주지 않는다(전부 NA) — 길이는 아래 API로 따로 받는다.
      이 함정에 3R 프로브 613개가 통째로 '쇼츠없음'으로 잘못 나왔다(2026-08-25)."""
    # ★lang=ko가 없으면 한국 채널도 영어 제목이 내려온다(유튜브 자동번역 제목).
    #   그러면 한글 사전이 하나도 안 걸려 적합도가 통째로 0이 된다(2026-08-25 실측).
    cmd = ["yt-dlp", "--flat-playlist", "--playlist-end", str(limit),
           "--extractor-args", "youtube:lang=ko",
           "--print", "%(id)s|%(title)s", "--no-warnings",
           f"https://www.youtube.com/channel/{cid}/shorts"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=120).stdout
    except subprocess.TimeoutExpired:
        return [], []
    ids, titles = [], []
    for line in out.splitlines():
        vid, _, t = line.partition("|")
        if vid.strip():
            ids.append(vid.strip())
            titles.append(t)
    return ids, titles


_ISO = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def durations(keys, vids):
    """videos.list로 길이 조회 — 50편당 1 unit(search 100 units 대비 사실상 공짜)."""
    out, ki = [], 0
    for i in range(0, len(vids), 50):
        chunk = vids[i:i + 50]
        while ki < len(keys):
            p = {"part": "contentDetails", "id": ",".join(chunk), "key": keys[ki]}
            try:
                url = "https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode(p)
                with urllib.request.urlopen(url, timeout=20) as r:
                    data = json.load(r)
                break
            except Exception:
                ki += 1
        else:
            raise SystemExit("모든 키 소진")
        for it in data.get("items", []):
            m = _ISO.match(it["contentDetails"]["duration"] or "")
            if m:
                out.append(int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0))
    return out


def probe_channel(cid, keys, limit=30):
    """(편수, 중앙초, 제목샘플)."""
    ids, titles = _ids_and_titles(cid, limit)
    if not ids:
        return 0, None, []
    durs = durations(keys, ids)
    return len(ids), (statistics.median(durs) if durs else None), titles[:5]


def verdict(n, med):
    if not n or med is None:
        return "배제:쇼츠없음"
    if med < 10:
        return "배제:루프컴필"
    if med <= 30:
        return "통과"
    if med <= 90:
        return "배제:나레이션리뷰"
    return "배제:장편리뷰"


def gearfit(cid, limit=30):
    """통과 채널의 '장비템 적합도' — 제목 30편을 라이브 판정기(categorize)로 재본다.

    길이만 보면 일반 쇼츠 채널이 대거 통과한다(3R 실측 613중 222). 실제로 우리가
    원하는 결은 '장비·공구 제품을 파는' 채널이라 **판정을 한 곳(categorize)에서**
    빌려 쓴다(0순위-B). 새 기준을 여기서 또 만들면 라이브와 어긋난다."""
    # ★py tools/gear_discover.py 로 돌리면 sys.path[0]이 tools/라 프로젝트 루트가 없다.
    #   이 한 줄이 없으면 import가 죽고, 아래 호출부 except가 그걸 삼켜 fit이 전부 0이 된다
    #   (2026-08-25 실측: 258채널 전부 0.00 — 원인 찾는 데 두 번 헛돌았다).
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shopping_shorts.categorize import categorize
    _, titles = _ids_and_titles(cid, limit)
    if not titles:
        return 0.0, 0
    gear = sum(1 for t in titles if categorize("", t) == "장비템")
    return gear / len(titles), len(titles)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--kw-file", required=True)
    s.add_argument("--seeds", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--env", default=".env")
    p = sub.add_parser("probe")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--env", default=".env")
    g = sub.add_parser("fit")
    g.add_argument("--in", dest="inp", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    if a.cmd == "fit":
        res = json.load(open(a.inp, encoding="utf-8"))
        todo = {k: v for k, v in res.items() if v.get("verdict") == "통과" and not v.get("fit_n")}
        print(f"적합도 측정 {len(todo)}채널")
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(gearfit, cid): cid for cid in todo}
            for i, f in enumerate(as_completed(futs), 1):
                cid = futs[f]
                try:
                    fit, n = f.result()
                except Exception as e:
                    print(f"    fit 실패 {cid}: {e}", file=sys.stderr)
                    fit, n = 0.0, 0
                res[cid]["fit"] = round(fit, 3)
                res[cid]["fit_n"] = n
                if i % 25 == 0:
                    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                    print(f"  [{i}/{len(todo)}]")
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        hi = [v for v in res.values() if v.get("fit", 0) >= 0.2]
        print(f"fit>=0.2 인 채널 {len(hi)}개 → {a.out}")

    elif a.cmd == "search":
        keys = load_keys(a.env)
        known = seed_ids(a.seeds)
        kws = [l.strip() for l in open(a.kw_file, encoding="utf-8") if l.strip()]
        print(f"키 {len(keys)}개 · 기존시드 {len(known)}개 · 키워드 {len(kws)}개")
        cand = {}
        for i, kw in enumerate(kws, 1):
            hits = search(keys, kw)
            new = 0
            for cid, ctitle, vtitle in hits:
                if cid in known:
                    continue
                d = cand.setdefault(cid, {"title": ctitle, "kws": [], "samples": []})
                if kw not in d["kws"]:
                    d["kws"].append(kw)
                if len(d["samples"]) < 3:
                    d["samples"].append(vtitle)
                new += 1
            print(f"  [{i}/{len(kws)}] {kw}: {len(hits)}건 · 신규후보누적 {len(cand)}")
        json.dump(cand, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"신규 후보 채널 {len(cand)}개 → {a.out}  (검색 {len(kws)*100} units)")

    else:
        keys = load_keys(a.env)
        cand = json.load(open(a.inp, encoding="utf-8"))
        # 이어받기 — 채널명에 이모지가 있으면 콘솔(cp949) 출력에서 죽어 중간에 끊긴다.
        # 끊겨도 이미 판정한 것은 다시 긁지 않는다(2026-08-25 296/613에서 중단).
        try:
            res = json.load(open(a.out, encoding="utf-8"))
        except Exception:
            res = {}
        cand = {k: v for k, v in cand.items() if k not in res}
        done = 0
        print(f"남은 후보 {len(cand)}개 (이미 판정 {len(res)}개)")
        # yt-dlp flat은 채널당 ~10초라 613개면 100분 — 병렬로 줄인다(쿼터 0이라 안전).
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(probe_channel, cid, keys): cid for cid in cand}
            for f in as_completed(futs):
                cid = futs[f]
                d = cand[cid]
                try:
                    n, med, titles = f.result()
                except Exception as e:
                    n, med, titles = 0, None, [f"ERR {e}"]
                v = verdict(n, med)
                res[cid] = {**d, "n": n, "median": med, "verdict": v, "titles": titles}
                done += 1
                if v == "통과" or done % 25 == 0:
                    safe = d["title"][:22].encode("ascii", "replace").decode()
                    print(f"  [{done}/{len(cand)}] {safe:22s} n={n:3d} med={med} {v}")
                    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        ok = [c for c, r in res.items() if r["verdict"] == "통과"]
        print(f"통과 {len(ok)} / {len(res)} → {a.out}")


if __name__ == "__main__":
    main()
