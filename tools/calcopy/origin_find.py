# -*- coding: utf-8 -*-
"""원본찾기 — 한국 재편집 쇼츠 → 구글 렌즈 → 해외 원본 영상·원본 채널 + 한국 검증 채널을 자산 장부에 쌓는 무한 루프 (사장님 10-20, 관제 097).

사장님(10-20): "외국인이 한국제품 검색 → 한국 영상을 렌즈로 → 한국 채널도 나오고 외국 원본도 나온다. 외국 원본을 우리가 쓴다.
  한국 채널을 자산으로 등록하고 그 영상들을 렌즈하면서 조회수 검증 영상·채널 수집 + 원본 찾기를 계속하면 무한대로 찾는다.
  원본 영상과 원본 채널을 모두 자산으로 등록." / "한국 화장품 = 잇템로그, 제품 = 숏템로그. 핫템리포트·지금 채널에서도 렌즈로 넓혀 나가면 된다"

판단 주인(이 파일 한 곳):
  · 한국/해외 가르기 = is_korean (제목·채널 이름에 한글)
  · 같은 영상인지 = judge_same (씨앗 장면 + 후보 썸네일 한 장 → Claude 눈(소넷)). 같다고 본 것만 원본·짝으로 등록 — same_video(ORB)는 VERIFY 때만(10-21 점수 겹쳐 끔)
  · 원본 고르기 = pick_origins (같은 영상 판정 통과 + 해외 채널마다 가장 먼저 올라온 것 — 모음 편은 원본이 여럿)
  · 잇템로그/숏템로그 = brand_of (제목 화장품 낱말)
결과물 검사 = 장부의 짝마다 match(특징점 수)·근거 장면이 남는다. 짝 수·원본 수는 `report` 로 본다.

    PYTHONUTF8=1 py tools/calcopy/origin_find.py seed <유튜브주소> [...]      # 씨앗 넣기(대기열)
    PYTHONUTF8=1 py tools/calcopy/origin_find.py search "<검색어>" [...]       # 서버 유튜브 API 검색 결과를 씨앗으로
    PYTHONUTF8=1 py tools/calcopy/origin_find.py run [--n 5]                  # 대기열에서 n개 렌즈 돌리기
    PYTHONUTF8=1 py tools/calcopy/origin_find.py expand [--per 5]             # 한국 채널의 터진 쇼츠를 대기열에
    PYTHONUTF8=1 py tools/calcopy/origin_find.py report                       # 장부 요약
장부 = channel/해외원본소재/원본찾기.json · 작업 파일(영상·장면) = C:/숏템_칼카피/_origin/<id>/ (git 밖)
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "channel/해외원본소재/원본찾기.json"
WORK = Path("C:/숏템_칼카피/_origin")
HANGUL = re.compile(r"[가-힣]")
BEAUTY = re.compile(r"화장품|파데|파운데이션|쿠션|립|틴트|선크림|썬크림|마스크팩|팩|스킨|크림|세럼|앰플|뷰티|메이크업|화장|피부|토너|클렌|컨실러|"
                    r"\b(?:k-?beauty|skincare|makeup|foundation|cushion|sunscreen|serum|lipstick|lip tint|tint|toner|face ?mask|sheet ?mask)\b", re.I)   # 영어는 낱말 경계(10-21 'masked singer'·'flip' 오분류)
MATCH_MIN = 25          # 같은 영상 표시값(눈 판정 '같음' = 이 값). ORB(VERIFY) 문턱으로는 못 쓴다 — 10-21 실측 같은 영상 9~61·다른 영상 4~60 겹침
FRAMES = (0.15, 0.35, 0.55, 0.75)
VERIFY = False          # 후보를 받아 ORB 대조 — 10-21 실측 같은/다른 영상 점수가 겹쳐(다른 영상 60·같은 영상 9) 끔. 같은 영상 판정 = 장면 모음 눈 판정(sheet)


# ── 장부 ───────────────────────────────────────────────────────────────
def load() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"made": time.strftime("%Y-%m-%d"), "purpose": "한국 재편집 쇼츠(조회수 검증) ↔ 해외 원본 영상·원본 채널 자산 장부 — origin_find.py 가 쌓는다",
            "rules": "같은 영상 = 씨앗 장면 + 후보 썸네일을 Claude 눈(소넷)이 판정(judge_same). 원본 = 같은 영상 중 해외(제목·채널에 한글 없음) 채널마다 가장 먼저 올라온 것(모음 편은 여럿). "
                     "brand = 제목 화장품 낱말이면 잇템로그, 아니면 숏템로그. 터진 편 = 조회 ≥ max(구독, 10만)(채널장부.json 과 같은 기준).",
            "related": "channel/해외원본소재/채널장부.json(해외 원본 채널 업로드 목록 스캔 장부)",
            "videos": {}, "channels": {}, "pairs": [], "queue": [], "done": []}


def save(L: dict):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 판단 ───────────────────────────────────────────────────────────────
def is_korean(title: str, channel: str = "") -> bool:
    return bool(HANGUL.search(f"{title} {channel}"))


def brand_of(*texts: str) -> str:
    return "잇템로그" if any(BEAUTY.search(t or "") for t in texts) else "숏템로그"


def hit(v: dict) -> bool:
    return (v.get("views") or 0) >= max(v.get("subs") or 0, 100_000)


# ── 링크 → 영상 키 ─────────────────────────────────────────────────────
def vkey(url: str) -> tuple[str, str] | None:
    m = re.search(r"youtube\.com/(?:shorts/|watch\?v=)([\w-]{11})|youtu\.be/([\w-]{11})", url)
    if m:
        return "yt", m.group(1) or m.group(2)
    m = re.search(r"tiktok\.com/@([\w.]+)/video/(\d+)", url)
    if m:
        return "tt", m.group(2)
    m = re.search(r"instagram\.com/(?:[\w.]+/)?(?:reel|reels|p)/([\w-]+)", url)
    if m:
        return "ig", m.group(1)
    return None


def url_of(p: str, i: str, hint: str = "") -> str:
    return {"yt": f"https://www.youtube.com/shorts/{i}", "ig": f"https://www.instagram.com/reel/{i}/"}.get(p, hint)


def meta(url: str) -> dict:
    """yt-dlp 메타(받지 않음). 실패하면 {'why'}."""
    fmt = "%(id)s\t%(title)s\t%(channel,uploader)s\t%(channel_id,uploader_id)s\t%(channel_follower_count)s\t%(view_count)s\t%(upload_date)s\t%(duration)s\t%(uploader_url,channel_url)s\t%(thumbnail)s"
    try:
        r = subprocess.run(["yt-dlp", "--skip-download", "--no-warnings", "--print", fmt, url], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
    except subprocess.TimeoutExpired:
        return {"why": "yt-dlp 90초 시간 초과"}   # 후보 하나가 씨앗 전체를 죽이지 않게(10-21 BGT 편 실패)
    line = (r.stdout.strip().splitlines() or [""])[-1]
    f = line.split("\t")
    if len(f) < 9:
        return {"why": (r.stderr.strip().splitlines() or ["?"])[-1][:160]}
    num = lambda x: int(float(x)) if re.fullmatch(r"[\d.]+", x or "") else None  # noqa: E731
    return {"title": f[1], "channel": f[2], "channel_id": f[3], "subs": num(f[4]), "views": num(f[5]),
            "date": f[6] if f[6] != "NA" else None, "dur": num(f[7]), "channel_url": f[8] if f[8] != "NA" else None,
            "thumb": f[9] if len(f) > 9 and f[9].startswith("http") else None}


# ── 장면 ───────────────────────────────────────────────────────────────
def frames(url: str, d: Path, fr=FRAMES, step: float | None = None) -> list[Path]:
    """저화질로 받아 장면 뽑기. step 이 있으면 그 간격으로 전부(후보 대조용)."""
    d.mkdir(parents=True, exist_ok=True)
    v = d / "v.mp4"
    if not v.exists():
        subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "b[height<=720]/bv*[height<=720]/b", "-o", str(v), url],
                       capture_output=True, timeout=300)
    if not v.exists():
        return []
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                               capture_output=True, text=True).stdout.strip() or 0)
    ts = [dur * p for p in fr] if not step else [t * step for t in range(int(dur / step))]
    out = []
    for k, t in enumerate(ts):
        p = d / (f"f{int(fr[k] * 100)}.jpg" if not step else f"s{k:03d}.jpg")
        if not p.exists():
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(v), "-frames:v", "1", "-vf", "scale=-2:640", str(p)])
        if p.exists():
            out.append(p)
    return out


def same_video(seed_imgs: list[Path], cand_imgs: list[Path]) -> int:
    """씨앗 장면마다 후보 장면 중 가장 많이 맞는 ORB 좋은 짝 수 → 그 중앙값(한 장만 우연히 맞는 걸 막는다)."""
    import cv2
    import numpy as np
    orb = cv2.ORB_create(1500)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)

    def feat(p):
        g = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_GRAYSCALE)   # cv2.imread 는 한글 경로를 못 읽어 None(10-21 실측: 전부 0점)
        if g is None:
            return None
        k, d = orb.detectAndCompute(g, None)
        return (k, d) if d is not None and len(d) > 10 else None
    C = [c for c in (feat(p) for p in cand_imgs) if c is not None]
    best = []
    for s in seed_imgs:
        ds = feat(s)
        if ds is None or not C:
            best.append(0); continue
        b = 0
        for kc, dc in C:
            good = [m[0] for m in bf.knnMatch(ds[1], dc, k=2) if len(m) == 2 and m[0].distance < 0.75 * m[1].distance]
            if len(good) < 8:
                continue
            # 위치까지 맞는 짝만(RANSAC 닮음변환 inlier) — 낱개 특징점만 세면 같은 결(땋은 머리·빨간 상자) 다른 영상도 60점(10-21 실측)
            a = np.float32([ds[0][m.queryIdx].pt for m in good]); c = np.float32([kc[m.trainIdx].pt for m in good])
            M, inl = cv2.estimateAffinePartial2D(a, c, method=cv2.RANSAC, ransacReprojThreshold=4.0)
            b = max(b, int(inl.sum()) if inl is not None else 0)
        best.append(b)
    best.sort()
    return best[len(best) // 2] if best else 0


# ── 한 씨앗 돌리기 ─────────────────────────────────────────────────────
def add_channel(L, v: dict, role: str):
    cid = v.get("channel_id") or v.get("channel")
    if not cid:
        return
    k = f"{v['platform']}:{cid}"
    c = L["channels"].setdefault(k, {"platform": v["platform"], "name": v.get("channel"), "id": cid, "url": v.get("channel_url"),
                                     "role": role, "videos": [], "first_seen": time.strftime("%Y-%m-%d")})
    c["subs"] = v.get("subs") or c.get("subs")
    if role == "origin":
        c["role"] = "origin"            # 한 번이라도 원본이면 원본 채널
    if v["key"] not in c["videos"]:
        c["videos"].append(v["key"])


def run_one(L: dict, pg, url: str, log=print) -> dict:
    from tools.calcopy import lens as LN
    p, i = vkey(url) or (None, None)
    if p != "yt":
        return {"why": "씨앗은 유튜브만"}
    seed = {"key": f"yt:{i}", "platform": "yt", "id": i, "url": url_of("yt", i), **meta(url)}
    seed_dir = WORK / i
    imgs = frames(seed["url"], seed_dir)
    if not imgs:
        return {"why": "씨앗 받기 실패"}
    seed["korean"] = is_korean(seed.get("title", ""), seed.get("channel", ""))
    found = {}
    for im in imgs:
        try:
            rows = LN.lens_rows(pg, str(im), skip=LN.SKIP_VIDEO)
        except Exception as e:  # noqa: BLE001 — 한 장 실패가 나머지를 막지 않는다(실패는 로그에)
            log(f"  렌즈 실패 {im.name}: {type(e).__name__} {str(e)[:80]}"); rows = []
        for r in rows:
            k = vkey(r["href"])
            if k and k != ("yt", i):
                a = found.setdefault(k, {"href": r["href"], "text": r["text"], "hits": 0})
                a["hits"] += 1
    log(f"  렌즈 장면 {len(imgs)}장 → 영상 링크 {len(found)}개")
    # 메타(병렬)
    keys = list(found)
    with ThreadPoolExecutor(6) as ex:
        metas = list(ex.map(lambda k: meta(url_of(k[0], k[1], found[k]["href"])), keys))
    cands = []
    for (pf, vid), m in zip(keys, metas):
        v = {"key": f"{pf}:{vid}", "platform": pf, "id": vid, "url": url_of(pf, vid, found[(pf, vid)]["href"]), "lens_text": found[(pf, vid)]["text"],
             "lens_hits": found[(pf, vid)]["hits"], **m}
        v["korean"] = is_korean(f'{v.get("title") or ""} {v["lens_text"]}', v.get("channel") or "")   # 인스타 제목은 'Video by …' 뿐 — 렌즈 글(본문 첫 줄)까지 본다(10-21 daillypick 등 한국 계정이 해외로 잡힘)
        cands.append(v)
    # 같은 영상 대조 — 유튜브·틱톡은 받아서 장면 대조, 인스타는 받기 막힘 → 미대조로 남김
    def check(v):
        if not VERIFY or v["platform"] == "ig":
            v["match"] = None; return v
        ci = frames(v["url"], WORK / "_cand" / f"{v['platform']}_{v['id']}", step=1.0)
        v["match"] = same_video(imgs, ci) if ci else None
        return v
    with ThreadPoolExecutor(3) as ex:
        cands = list(ex.map(check, cands))
    if not VERIFY:
        judged = judge_same(imgs, cands, seed_dir, log)
        for v in cands:
            v["match"] = None if v["key"] not in judged else (MATCH_MIN if judged[v["key"]] else 0)
            v["judge"] = "eye" if v["key"] in judged else None
    same = [v for v in cands if (v.get("match") or 0) >= MATCH_MIN]
    seed_brand = cat_brand(i) or brand_of(seed.get("title", ""))   # 브랜드 = 씨앗 한 편 기준(편 안 후보마다 갈리지 않게)
    origins = pick_origins([seed] + same)
    okeys = {o["key"] for o in origins}
    for v in cands:
        old = L["videos"].get(v["key"], {})
        v["role"] = ("origin" if v["key"] in okeys else
                     "korean_reup" if v["korean"] and (v.get("match") or 0) >= MATCH_MIN else
                     "overseas_copy" if (v.get("match") or 0) >= MATCH_MIN else
                     ("korean_found" if v["korean"] else "overseas_found") if v.get("match") is None else "other")   # *_found = 렌즈가 같이 보여 줌, 같은 영상 미판정
        v["brand"] = seed_brand
        v["seen_from"] = sorted(set(old.get("seen_from", []) + [seed["key"]]))
        if v["role"] in ("origin", "korean_reup", "overseas_copy", "korean_found", "overseas_found"):
            L["videos"][v["key"]] = {**old, **v}
            add_channel(L, v, "origin" if v["role"] == "origin" else "korean" if v["korean"] else "overseas")
    seed["role"] = "origin" if seed["key"] in okeys else ("korean_reup" if seed["korean"] else "overseas_copy")
    seed["brand"] = seed_brand
    L["videos"][seed["key"]] = {**L["videos"].get(seed["key"], {}), **seed}
    add_channel(L, seed, "origin" if seed["role"] == "origin" else "korean" if seed["korean"] else "overseas")
    for v in same + [seed]:
        for o in origins:
            if v["key"] == o["key"] or not v.get("korean"):
                continue
            pr = {"copy": v["key"], "origin": o["key"], "seed": seed["key"], "brand": seed["brand"], "at": time.strftime("%Y-%m-%d")}
            if not any(x["copy"] == pr["copy"] and x["origin"] == pr["origin"] for x in L["pairs"]):
                L["pairs"].append(pr)
    # 새 한국 재편집 영상은 다음 씨앗으로(그 영상의 렌즈가 또 다른 채널을 부른다)
    o_first = min((o["date"] for o in origins), default=None)
    for v in same:   # 같은 영상을 쓴 한국 채널만 = 다음에 상위 영상 분류할 채널
        # 원본보다 먼저 올린 한국 채널은 재편집이 아니다(같은 출연자의 국내 방송·공연 — 10-21 SBS 예능 2,958편·NICKY·원더매직이 들어와 대기열을 덮음)
        if not o_first or not v.get("date") or v["date"] < o_first:
            continue
        if v["korean"] and v["platform"] == "yt" and v.get("channel_id"):
            L.setdefault("channel_queue", [])
            if v["channel_id"] not in L["channel_queue"] and not L["channels"].get(f"yt:{v['channel_id']}", {}).get("classified"):
                L["channel_queue"].append(v["channel_id"])   # 새 한국 채널 = 상위 영상 분류부터(사장님 10-21)
    for v in same:
        if v["korean"] and v["platform"] == "yt" and v["key"] not in L["done"] and v["url"] not in L["queue"]:
            L["queue"].append(v["url"])
    L["done"].append(seed["key"])
    return {"seed": seed["key"], "links": len(found), "same": len(same), "origins": sorted(okeys),
            "unverified_ig": sum(1 for v in cands if v["platform"] == "ig")}


JUDGE_PROMPT = ("맨 위 줄(S1~S4)은 씨앗 쇼츠의 장면이다. 그 아래 번호 붙은 칸은 구글 렌즈가 찾아 준 다른 영상의 썸네일이다.\n"
                "씨앗과 **같은 원본 영상(같은 사람·같은 장소·같은 순간을 찍은 같은 촬영분)**을 쓴 칸 번호만 고른다. "
                "자막·제목 띠·잘림·확대·좌우반전·뉴스 화면 속 삽입이 달라도 같은 촬영분이면 같다. "
                "주제만 비슷한 다른 사람·다른 촬영(같은 제품을 다른 사람이 씀, 같은 출연자의 다른 무대·다른 방송 등)은 다르다. 썸네일이 비었거나 판단 불가면 넣지 않는다.\n"
                '답 = {"same":[번호,…], "why":"한 줄"}')


def judge_same(seed_imgs: list[Path], cands: list[dict], d: Path, log=print) -> dict:
    """같은 영상 판정 = Claude 눈(소넷) — 씨앗 장면 + 후보 썸네일 한 장(10-21: ORB 점수가 같은/다른 영상 겹쳐 버림).
    반환 {key: True|False} — 썸네일을 못 받은 후보는 빠진다(미판정)."""
    import io
    import urllib.request
    from PIL import Image, ImageDraw, ImageFont
    from tools.calcopy.engine import claude_cli as CC

    def get(v):
        try:
            u = v.get("thumb")
            if not u:
                return None
            b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
            return Image.open(io.BytesIO(b)).convert("RGB")
        except Exception:  # noqa: BLE001 — 썸네일 못 받음 = 미판정(판정에서 빠진다, 조용히 '다름'으로 두지 않는다)
            return None
    with ThreadPoolExecutor(8) as ex:
        th = list(ex.map(get, cands))
    pool = [(v, im) for v, im in zip(cands, th) if im is not None]
    if not pool:
        return {}
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 26)
    out = {}
    for s0 in range(0, len(pool), 24):
        part = pool[s0:s0 + 24]
        cw, chh, cols = 200, 300, 8
        rows_n = 1 + (len(part) + cols - 1) // cols
        sheet = Image.new("RGB", (cw * cols, (chh + 34) * rows_n), "white")
        dr = ImageDraw.Draw(sheet)
        for k, p in enumerate(seed_imgs[:4]):
            im = Image.open(p).convert("RGB"); im.thumbnail((cw, chh)); sheet.paste(im, (k * cw, 34)); dr.text((k * cw + 4, 2), f"S{k + 1}", fill="red", font=font)
        for j, (v, im) in enumerate(part):
            x, y = (j % cols) * cw, (1 + j // cols) * (chh + 34)
            im = im.copy(); im.thumbnail((cw, chh)); sheet.paste(im, (x, y + 34)); dr.text((x + 4, y + 2), str(j + 1), fill="blue", font=font)
        buf = io.BytesIO(); sheet.save(buf, "JPEG", quality=82)
        sheet.save(d / f"judge_{s0 // 24}.jpg", quality=82)
        res, err = CC.ask([buf.getvalue()], JUDGE_PROMPT, tag="ma_fit_origin", model="sonnet")
        if res is None:
            log(f"  눈 판정 실패: {err}"); continue
        same = {int(n) for n in res.get("same", []) if str(n).isdigit()}
        for j, (v, _) in enumerate(part):
            out[v["key"]] = (j + 1) in same
        log(f"  눈 판정 {len(part)}칸 → 같은 영상 {sorted(same)} · {str(res.get('why'))[:80]}")
    return out


def cat_brand(vid: str) -> str | None:
    """한국채널 분류 파일에 이 영상이 있으면 그 카테고리의 브랜드(classify 결과 = 주인)."""
    for f in (LEDGER.parent / "한국채널").glob("*.json"):
        for x in json.loads(f.read_text(encoding="utf-8"))["videos"]:
            if x["id"] == vid:
                return x.get("brand")
    return None


def pick_origins(vs: list[dict]) -> list[dict]:
    """같은 영상 판정 통과 중 해외 채널마다 가장 먼저 올라온 것 — 한국 쇼츠는 여러 외국인 영상을 이어 붙인 모음이 많다
    (10-21 떠튜브 ZQphwE2W1Aw = MissDarcei·곱슬머리 여성·golloria 셋). 짝은 모음 편의 원본 전부와 묶는다(편 단위, 장면 단위 아님)."""
    sd = vs[0].get("date") if vs and vs[0].get("korean") else None   # vs[0] = 씨앗(확실한 한국 재편집). 다른 한국 '같음'은 눈 판정이 넓게 잡아(같은 마술사 다른 무대) 기준으로 안 쓴다(10-21 BGT 원본이 빠짐)
    first_ko = sd or "99999999"
    best = {}
    for v in vs:
        if v.get("korean") or not v.get("date") or v["date"] > first_ko:   # 한국 재편집보다 늦게 올라온 해외 계정 = 퍼 간 쪽(원본 아님)
            continue
        k = v.get("channel_id") or v.get("channel") or v["key"]
        if k not in best or v["date"] < best[k]["date"]:
            best[k] = v
    return sorted(best.values(), key=lambda v: v["date"])


# ── 대기열 ─────────────────────────────────────────────────────────────
def cmd_run(n: int):
    from tools.calcopy import lens as LN
    with LN.lens_page() as pg:
        for _ in range(n):
            L = load()
            if L.get("channel_queue"):   # 새 한국 채널이 나오면 그 채널 상위 영상 분류부터(사장님 10-21) — 대기열은 조회수 순으로 다시 선다
                cq = list(L["channel_queue"])   # 끝난 뒤에 지운다 — 분류 중 죽으면 다음 바퀴가 이어 한다(10-21 620편 채널 유실)
                for cid in cq:
                    cmd_channel([cid], queue_top=100000)
                    L = load(); L["channel_queue"] = [c for c in L.get("channel_queue", []) if c != cid]; save(L)
                L = load()
            L["queue"] = [x for x in L["queue"] if f"yt:{(vkey(x) or ('', ''))[1]}" not in L["done"]]
            if not L["queue"]:
                print("대기열 비었음 — seed/search/expand 로 채운다"); break
            u = L["queue"][0]   # 늘 맨 앞(= 조회수 1위)부터
            print("씨앗", u, time.strftime("%H:%M"))
            try:
                r = run_one(L, pg, u)
            except Exception as e:  # noqa: BLE001 — 한 씨앗 실패가 루프를 멈추지 않게(이유는 장부 failed 에)
                r = {"why": f"{type(e).__name__}: {str(e)[:160]}"}
                L.setdefault("failed", {})[u] = r["why"]
            L["queue"] = [x for x in L["queue"] if x != u]
            save(L)
            print("  →", r)
    cmd_report()


def cmd_expand(per: int):
    """한국 채널의 쇼츠 목록(조회수 포함, 받지 않음)에서 터진 편 중 '외국인·한국' 결 제목만 대기열에."""
    L = load()
    pat = re.compile(r"외국인|한국|K-?|흑누나|미국|해외|일본인|영국", re.I)
    added = 0
    for k, c in L["channels"].items():
        if c["platform"] != "yt" or c["role"] != "korean" or c.get("expanded"):
            continue
        r = subprocess.run(["yt-dlp", "--flat-playlist", "--no-warnings", "--print", "%(id)s\t%(view_count)s\t%(title)s",
                            f"https://www.youtube.com/channel/{c['id']}/shorts"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        rows = []
        for ln in r.stdout.splitlines():
            f = ln.split("\t")
            if len(f) == 3 and f[1].isdigit():
                rows.append((int(f[1]), f[0], f[2]))
        rows.sort(reverse=True)
        pick = [x for x in rows if x[0] >= max(c.get("subs") or 0, 100_000) and pat.search(x[2])][:per]
        for views, vid, title in pick:
            u = url_of("yt", vid)
            if f"yt:{vid}" not in L["done"] and u not in L["queue"]:
                L["queue"].append(u); added += 1
        c["expanded"] = time.strftime("%Y-%m-%d")
        c["shorts_scanned"] = len(rows)
        print(f"  {c['name']}: 쇼츠 {len(rows)}개 중 터진·결 맞음 {len(pick)}")
    save(L)
    print(f"대기열 +{added} (지금 {len(L['queue'])})")


CATS = {"화장품": "잇템로그", "제품": "숏템로그", "음식": "맛템", "동물": "동물", "사람·유머": "썰", "기술·탈것": "숏템로그", "스포츠": "기타", "기타": "기타"}
CAT_PROMPT = ("아래는 한국 유튜브 쇼츠 제목 목록이다(대부분 해외 영상을 재편집한 것). 각 제목을 카테고리 하나로 나눈다.\n"
              "카테고리: 화장품(화장품·스킨케어·메이크업·헤어·뷰티 도구) / 제품(생활용품·아이디어 상품·가전·장난감·주방도구 등 살 수 있는 물건) / "
              "음식(먹는 것·요리·식당) / 동물 / 사람·유머(사람 이야기·반응·몰래카메라·감동, 물건이 중심이 아님) / 기술·탈것(기계·발명·자동차·로봇) / 스포츠 / 기타.\n"
              "korea=제목이 한국·K-·한국 제품/음식/문화와 관련 있으면 true. foreigner=외국인 반응·체험 꼴이면 true. item=제목에서 보이는 제품 이름(없으면 빈칸).\n"
              '답 = {"r":[{"i":번호,"cat":"…","korea":true|false,"foreigner":true|false,"item":"…"}, …]} — 목록의 모든 번호를 빠짐없이.\n\n')


def classify(titles: list[str], batch: int = 150, log=print) -> list[dict]:
    """제목 → [{cat, brand, korea, foreigner, item}] (하이쿠, 150개씩 병렬). 판단 주인 = 이 함수 + CATS(카테고리→우리 브랜드)."""
    from tools.calcopy.engine import claude_cli as CC
    chunks = [list(range(s, min(s + batch, len(titles)))) for s in range(0, len(titles), batch)]

    def one(ix):
        body = "\n".join(f"{i}. {titles[i]}" for i in ix)
        for k in range(5):
            out, err = CC.ask([], CAT_PROMPT + body, tag="of_cat", model="haiku")
            got = {r.get("i"): r for r in (out or {}).get("r", []) if isinstance(r, dict)}
            if all(i in got for i in ix):
                return got
            log(f"  분류 다시({len(got)}/{len(ix)}) {err or ''}")
            time.sleep(10 * (k + 1))   # 10-21 claude -p 가 동시에 뜰 때 1~2초 만에 rc=0xC0000409 로 죽음 — 쉬었다 다시
        return got
    res = {}
    with ThreadPoolExecutor(2) as ex:
        for g in ex.map(one, chunks):
            res.update(g)
    out = []
    for i in range(len(titles)):
        r = res.get(i) or {"cat": "미분류"}
        cat = r.get("cat") if r.get("cat") in CATS else ("미분류" if r.get("cat") is None else "기타")
        out.append({"cat": cat, "brand": CATS.get(cat, "미분류"), "korea": bool(r.get("korea")), "foreigner": bool(r.get("foreigner")),
                    "item": r.get("item") or ""})
    return out


def cmd_channel(ids: list[str], queue_top: int):
    """한국 채널 쇼츠 전부(조회수순) → 1차 카테고리 분류 → 채널 파일 + 조회수 1위부터 대기열(사장님 10-21 '버릴 게 하나 없다')."""
    L = load()
    for cid in ids:
        r = subprocess.run(["yt-dlp", "--flat-playlist", "--no-warnings", "--print", "%(id)s\t%(view_count)s\t%(title)s",
                            f"https://www.youtube.com/channel/{cid}/shorts"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        rows = []
        for ln in r.stdout.splitlines():
            f = ln.split("\t")
            if len(f) == 3:
                rows.append({"id": f[0], "views": int(f[1]) if f[1].isdigit() else None, "title": f[2]})
        rows.sort(key=lambda x: -(x["views"] or 0))
        print(f"{cid}: 쇼츠 {len(rows)}개 — 분류 중")
        cl = classify([x["title"] for x in rows])
        for k, (x, c) in enumerate(zip(rows, cl)):
            x.update(c, rank=k + 1)
        ch = L["channels"].setdefault(f"yt:{cid}", {"platform": "yt", "id": cid, "role": "korean", "videos": [], "first_seen": time.strftime("%Y-%m-%d")})
        name = ch.get("name") or (meta(f"https://www.youtube.com/shorts/{rows[0]['id']}").get("channel") if rows else cid)
        ch["name"] = name
        out = LEDGER.parent / "한국채널" / f"{re.sub(r'[^0-9A-Za-z가-힣_-]', '', name or cid)}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        cnt = {}
        for x in rows:
            cnt[x["cat"]] = cnt.get(x["cat"], 0) + 1
        out.write_text(json.dumps({"channel": name, "id": cid, "made": time.strftime("%Y-%m-%d"), "n": len(rows), "cats": cnt, "videos": rows},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        ch.update({"classified": time.strftime("%Y-%m-%d"), "shorts_n": len(rows), "cats": cnt, "file": str(out.relative_to(ROOT)).replace("\\", "/")})
        for x in rows[:queue_top]:
            u = url_of("yt", x["id"])
            if f"yt:{x['id']}" not in L["done"] and u not in L["queue"]:
                L["queue"].append(u)
        print(f"  {name}: {cnt} → {out.name}")
    # 대기열 = 조회수 큰 순(채널을 가로질러 1위부터)
    views = {}
    for f in (LEDGER.parent / "한국채널").glob("*.json"):
        for x in json.loads(f.read_text(encoding="utf-8"))["videos"]:
            views[x["id"]] = x["views"] or 0
    L["queue"].sort(key=lambda u: -views.get((vkey(u) or ("", ""))[1], 0))
    save(L)
    print(f"대기열 {len(L['queue'])}")


def cmd_seed(urls: list[str]):
    L = load()
    for u in urls:
        k = vkey(u)
        if k and k[0] == "yt" and f"yt:{k[1]}" not in L["done"]:
            u = url_of(*k)
            if u not in L["queue"]:
                L["queue"].append(u)
    save(L)
    print("대기열", len(L["queue"]))


def cmd_search(qs: list[str], n: int):
    from tools.calcopy.hybrid import server_ai
    res = server_ai.yt_search(qs, n=n, lang="ko", duration="short")
    urls = [it["url"] for q in res for it in q.get("items", [])]
    print(f"검색 {len(qs)}개 → 영상 {len(urls)}개")
    cmd_seed(urls)


def cmd_report():
    L = load()
    V = L["videos"].values()
    by = lambda r: [v for v in V if v.get("role") == r]  # noqa: E731
    C = L["channels"].values()
    print(f"영상: 원본 {len(by('origin'))} · 한국 재편집 {len(by('korean_reup'))} · 해외 사본 {len(by('overseas_copy'))} · 미대조(인스타) {len(by('unverified'))}")
    print(f"채널: 원본 {sum(1 for c in C if c['role'] == 'origin')} · 한국 {sum(1 for c in C if c['role'] == 'korean')} · 해외 {sum(1 for c in C if c['role'] == 'overseas')}")
    print(f"짝 {len(L['pairs'])} · 처리 {len(L['done'])} · 대기 {len(L['queue'])} · 실패 {len(L.get('failed', {}))}")
    for v in sorted(by("origin"), key=lambda v: -(v.get("views") or 0)):
        ko = [p for p in L["pairs"] if p["origin"] == v["key"]]
        kv = sum((L["videos"].get(p["copy"], {}).get("views") or 0) for p in ko)
        print(f"  [{v.get('brand')}] {v.get('channel')} · {v.get('views')}회 · {v.get('date')} · {v['url']} · 한국 재편집 {len(ko)}개 합 {kv}회 · {str(v.get('title'))[:50]}")


def main():
    ap = argparse.ArgumentParser()
    s = ap.add_subparsers(dest="cmd", required=True)
    s.add_parser("seed").add_argument("urls", nargs="+")
    a = s.add_parser("search"); a.add_argument("q", nargs="+"); a.add_argument("--n", type=int, default=15)
    a = s.add_parser("run"); a.add_argument("--n", type=int, default=5)
    a = s.add_parser("expand"); a.add_argument("--per", type=int, default=5)
    s.add_parser("report")
    a = s.add_parser("channel"); a.add_argument("ids", nargs="+"); a.add_argument("--queue-top", type=int, default=100000)
    a = ap.parse_args()
    {"seed": lambda: cmd_seed(a.urls), "search": lambda: cmd_search(a.q, a.n), "run": lambda: cmd_run(a.n),
     "channel": lambda: cmd_channel(a.ids, a.queue_top),
     "expand": lambda: cmd_expand(a.per), "report": cmd_report}[a.cmd]()


if __name__ == "__main__":
    main()
