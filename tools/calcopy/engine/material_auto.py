# -*- coding: utf-8 -*-
"""재료 찾기 자동화 — 대본(토막) → 검색어 → 후보 영상(저해상도 미리보기) → 프레임 설명 → 글로 짝짓기 → 규칙 선택 → 쓸 구간만 1080p → 계획 시트
(관제 097, 2026-10-17 사장님 "재료찾기를 당연히 자동화해야지").

    PYTHONUTF8=1 py tools/calcopy/engine/material_auto.py <대본.json> --channel 잇썸홈|재미썸홈 --out <작업폴더> [--no-sections]

판단 주인(이 파일 밖에 같은 판단을 적지 않는다):
  plan_materials(script_json, channel_rules) -> 재료.json   전체 흐름
  allowed(cell, tok, rules)        후보 칸 하나를 이 토막에 써도 되나(채널 규칙·A5 남의 글자·어두움·CG·해상도)
  reuse_conflict(vid, t0, t1, used, prev)   같은 소스 겹침/±3초 재사용(사장님 10-17) · 되감김(B13)
  select(toks, ranked, cells, rules) 토막별 최종 선택(A12 같은 줄기 우선·B4 이웃 토막 한 컷·마지막 묶음 길게·짤 비율)
상한(사장님·공통규칙): 검색어 ≤10/작품 · 검색어당 ≤15편 · 요청 간격 ≥1초 · 무거운 일 동시 ≤4 · 제미나이 429 10회 넘으면 멈춤.
그림은 시트 한 장씩 '보이는 것'만 묻고(메모리: 큰 시트 한 번에 주면 순서대로 찍는다), 짝짓기는 글로 한다.
네트워크(net)·모델(llm)은 주입 — 시험은 가짜로 돈다.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

PROMPT_VER = "ma1"
MAX_QUERIES = 10          # 작품당 검색어 상한(사장님 10-17)
PER_QUERY = 15            # 검색어당 편 상한
META_PER_QUERY = 5        # 검색어당 메타(해상도) 조회 편수
PREVIEW_PER_QUERY = 3     # 검색어당 미리보기 편수 — 앞 검색어가 상한을 다 먹어 뒤 검색어(재검색 포함)가 0편 되는 것 방지(1판 실측)
MAX_PREVIEWS = 30         # 미리보기 받는 편 상한(작품당)
# 1080 구간은 HLS(m3u8) 포맷으로 — 10-17 실측: DASH 137 을 --download-sections 로 자르면 16~20KiB/s 로 막혀 7초 구간에 3분 반,
# HLS 270 은 같은 구간 6.5초 · 시작 시각 오차 0.1초 안(미리보기 프레임 대조).
SECTION_FMT = ("270/614/bv*[height>=1080][protocol^=m3u8]/bv*[width>=1080][protocol^=m3u8]/bv*[height>=720][protocol^=m3u8]"
               "/137/bv*[height>=1080]/bv*[height>=720]")
RATE = 1.0                # 유튜브 요청 간격(초)
WORKERS = 4               # 무거운 일 동시 상한
MAX_429 = 10              # 제미나이 429 이 횟수 넘으면 멈춤
REUSE_GAP = 3.0           # 같은 소스 ±3초 안 재사용 금지(사장님 10-17)
MIN_LUMA = 45             # 칸 평균 밝기(0~255) 이 미만은 어두움(B9 첫·끝 컷 기준 60보다 느슨)
VERIFY_ROUNDS = 2         # 1080 검사 → 재선택 바퀴 수(마지막 바퀴 뒤엔 검사만 하고 걸린 컷은 빈칸)
MIN_SCORE = 5             # 짝짓기 점수(0~10) 이 미만은 안 쓴다
PREVIEW_HEAD = 300        # 미리보기는 앞 300초까지
SHEET_N = 30              # 시트 한 장 칸 수(6×5)
MAX_FRAMES = 60           # 영상 하나 최대 칸 수
CELL = 200
MEME_DIR = Path("C:/숏템_칼카피/packs/meme/meme_pack")
MEME_INDEX = ROOT / "research/meme_pack/extra_memes.json"
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"

CHANNELS = {
    # 잇썸홈(두유노홈디노형) = 같은 제품 실영상만(비포 비교 토막만 같은 종류 다른 제품 허용), 짤 0
    "잇썸홈": {"channel": "잇썸홈", "same_product_only": True, "kinds": ["product", "before"], "meme_ratio": (0.0, 0.0),
              "min_res": 720, "pref_res": 1080, "allow_cg": False},
    # 재미썸홈(이븐쇼핑형) = 제품 + 유사·연상 + 짤 10~15%
    "재미썸홈": {"channel": "재미썸홈", "same_product_only": False, "kinds": ["product", "similar", "meme"], "meme_ratio": (0.10, 0.15),
               "min_res": 720, "pref_res": 1080, "allow_cg": False},
}


class Stop(Exception):
    """상한·429 로 멈춤 — 그때까지 결과를 남긴다."""


# ── 모델 창구 ──────────────────────────────────────────────────────────────
class LLM:
    """fn(parts, prompt, tag) -> (dict|None, err). 기본 = gemini_free.ask(무료 키 장부). 429 가 MAX_429 넘으면 Stop."""

    def __init__(self, fn=None):
        self.fn, self.calls, self.n429 = fn, [], 0

    def __call__(self, parts, prompt, tag):
        fn = self.fn
        if fn is None:
            from tools.calcopy.engine import gemini_free
            fn = lambda p, q, t: gemini_free.ask(p, q, tag=t)  # noqa: E731
        t0 = time.time()
        d, err = fn(parts, prompt, tag)
        if err in ("429", "quota"):
            self.n429 += 1
        self.calls.append({"tag": tag, "ok": bool(d), "err": err, "sec": round(time.time() - t0, 1)})
        if self.n429 > MAX_429:
            raise Stop(f"제미나이 429 {self.n429}회 — 멈춤")
        return d, err


# ── 대본 읽기 ──────────────────────────────────────────────────────────────
def _plain(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s or "")


def norm_script(sj: dict) -> tuple[str, list[dict]]:
    """두 꼴(잇썸홈 lines+tokens / 재미썸홈 spine55+pieces) → (주제, 토막[{i,text,t0,dur,line,line_text,shot_query}])."""
    topic = sj.get("topic") or (sj.get("title_slots") or {}).get("bodyTitle") or ""
    if sj.get("tokens"):
        lines = {l["i"]: l.get("text", "") for l in sj.get("lines") or []}
        toks = [{"i": t["i"], "text": t["text"], "t0": t.get("t0", 0.0), "dur": t.get("dur", 0.8), "line": t.get("line", 0),
                 "line_text": lines.get(t.get("line", 0), ""), "shot_query": t.get("shot_query")} for t in sj["tokens"]]
        return topic, toks
    lines = [l.get("line", "") for l in sj.get("spine55") or []]
    if not topic and lines:
        topic = lines[0]
    pieces = sj.get("pieces") or []
    # 토막 → 줄: 글자(공백·기호 뺀) 누적으로 배정
    bounds, acc = [], 0
    for l in lines:
        acc += len(_plain(l))
        bounds.append(acc)
    toks, acc = [], 0
    for p in pieces:
        mid = acc + len(_plain(p["caption"])) / 2
        acc += len(_plain(p["caption"]))
        li = next((k for k, b in enumerate(bounds) if mid <= b), max(0, len(lines) - 1))
        toks.append({"i": p["i"], "text": p["caption"], "t0": p.get("t0", 0.0), "dur": p.get("dur", 0.8), "line": li,
                     "line_text": lines[li] if lines else "", "shot_query": p.get("shot_query")})
    return topic, toks


# ── 1. 검색어·토막별 필요 장면 (모델 1회) ───────────────────────────────────
QUERY_PROMPT = """숏폼 재료 담당이다. 주제: {topic}
채널 규칙: {rule_text}
아래 토막(자막 조각)마다 화면에 보여야 할 장면을 정하고, 그 장면을 찾을 유튜브 검색어를 만들어라.
- need: 그 토막이 **문장 안에서** 말하는 순간을 보여줄 장면(영어 6~12낱말, 구체적으로 — 예 'hand puts plates into sink dishwasher basket').
  토막은 문장의 조각이다 — 문장 전체 뜻을 따른다(예: '설거지하다 허리 / 굽히는 게 귀찮았던' = 허리 굽혀 설거지하는 불편한 모습, 제품 자랑 장면 아님).
  같은 문장의 이웃 토막은 같은 장면이 이어져도 된다(인물·장소를 바꾸지 마라). 로고·글자 클로즈업은 장면으로 쓰지 않는다(회사·브랜드 얘기 = 매장·공장·진열·사용하는 사람).
- keywords: need 의 핵심 영어 낱말 3~6개(소문자)
- kind: {kinds}  (product=이 제품 실영상, before=비교 대상 일반 제품, similar=제품이 아닌 연상·상황 영상, meme=반응 짤)
{meme_rule}
- queries: 검색어 최대 {nq}개. 영어 위주 + 제품 원산지 언어(일본어·중국어 등) 1~2개. 제품명·브랜드·모델명·'review'·'unboxing'·'stock footage' 등을 섞어 서로 다르게.
  각 검색어에 purpose(product/before/similar)와 그 검색어가 채울 토막 번호 목록(toks).
- product: 이 제품을 화면에서 알아볼 영어 설명 1문장(모양·색·브랜드). product_terms: 제목에서 이 제품을 알아볼 낱말(브랜드·모델명·영어/현지어).
토막:
{toks}
출력 JSON만: {{"product":"...","product_terms":["..."],"needs":[{{"i":토막번호,"need":"...","keywords":["..."],"kind":"..."}}],"queries":[{{"q":"...","purpose":"...","toks":[번호]}}]}}"""

REQUERY_PROMPT = """숏폼 재료 담당이다. 주제: {topic}. 아래 토막은 장면을 못 찾았다. 이미 쓴 검색어와 **다른** 유튜브 검색어를 최대 {nq}개 만들어라
(동의어·다른 언어·공식/리뷰 채널·'stock footage'·더 일반적인 상황어). 채널 규칙: {rule_text}
못 찾은 토막: {toks}
이미 쓴 검색어: {tried}
출력 JSON만: {{"queries":[{{"q":"...","purpose":"product|before|similar","toks":[번호]}}]}}"""


def _rule_text(rules: dict) -> str:
    if rules.get("same_product_only"):
        return "같은 제품 실영상만(짤·연상 영상 금지). '보통 제품은~' 같은 비교 토막만 before(같은 종류 다른 제품)."
    lo, hi = rules.get("meme_ratio", (0, 0))
    return f"제품 실영상 + 유사·연상 영상 + 반응 짤 {int(lo * 100)}~{int(hi * 100)}%."


def plan_queries(topic, toks, rules, llm) -> dict:
    lo, hi = rules.get("meme_ratio", (0, 0))
    meme_rule = (f"- meme 은 반응·감탄 토막(놀람·의심·충격)에만, 전체 토막의 {int(lo * 100)}~{int(hi * 100)}%({math.ceil(lo * len(toks))}~{int(hi * len(toks))}개)."
                 if hi else "- meme 금지.")
    lines = "\n".join(f"{t['i']}. «{t['text']}» (문장: {t['line_text']})" + (f" [원하는 장면: {t['shot_query']}]" if t.get("shot_query") else "")
                      for t in toks)
    d, err = llm([], QUERY_PROMPT.format(topic=topic, rule_text=_rule_text(rules), kinds="/".join(rules["kinds"]), meme_rule=meme_rule,
                                         nq=MAX_QUERIES - 2, toks=lines), "ma_queries")
    if not d:
        raise Stop(f"검색어 만들기 실패: {err}")
    needs = {}
    for n in d.get("needs") or []:
        i = _as_int(n.get("i"))
        if i is None:
            continue
        kind = n.get("kind") if n.get("kind") in rules["kinds"] else rules["kinds"][0]
        needs[i] = {"need": str(n.get("need") or ""), "keywords": [str(k).lower() for k in n.get("keywords") or []], "kind": kind}
    for t in toks:   # 빠진 토막은 문장 자체를 need 로
        needs.setdefault(t["i"], {"need": t["text"], "keywords": [], "kind": rules["kinds"][0]})
    _cap_memes(toks, needs, rules)
    qs = [q for q in d.get("queries") or [] if isinstance(q, dict) and str(q.get("q") or "").strip()]
    return {"product": d.get("product") or topic, "product_terms": [str(x) for x in d.get("product_terms") or []],
            "needs": needs, "queries": qs[:MAX_QUERIES - 2]}


def _cap_memes(toks, needs, rules):
    """짤 비율 상한 — 넘는 짤 토막은 similar 로(앞에서부터 남긴다)."""
    hi = rules.get("meme_ratio", (0, 0))[1]
    cap = int(hi * len(toks))
    n = 0
    for t in toks:
        nd = needs[t["i"]]
        if nd["kind"] == "meme":
            n += 1
            if n > cap:
                nd["kind"] = "similar" if "similar" in rules["kinds"] else rules["kinds"][0]


def _as_int(v):
    try:
        return int(str(v).strip().lstrip("c#"))
    except (TypeError, ValueError):
        return None


# ── 2. 통로(네트워크) — 주입 가능 ──────────────────────────────────────────
def _run(argv, timeout=600):
    return subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=timeout)


class Net:
    """유튜브 통로. 요청 간격 RATE 를 지킨다. 받은 바이트를 센다."""

    def __init__(self, workdir: Path, log=print):
        self.wd, self.log, self._last, self.requests, self.bytes = workdir, log, 0.0, 0, 0

    def _gap(self):
        g = time.time() - self._last
        if self._last and g < RATE:
            time.sleep(RATE - g)
        self._last = time.time()
        self.requests += 1

    def search(self, q: str, n: int) -> list[dict]:
        self._gap()
        r = _run(["yt-dlp", "--no-update", "--sleep-requests", "1", "--flat-playlist", "-J", f"ytsearch{n}:{q}"], timeout=120)
        try:
            ents = json.loads(r.stdout or "{}").get("entries") or []
        except ValueError:
            ents = []
        return [{"id": e.get("id"), "title": e.get("title") or "", "duration": e.get("duration") or 0,
                 "channel": e.get("channel") or e.get("uploader") or ""} for e in ents if e.get("id")]

    def meta(self, vid: str) -> dict:
        """web 클라이언트 -J → 해상도(짧은 변)·길이·info 파일(미리보기·구간 받기에 재사용)."""
        info = self.wd / "info" / f"{vid}.info.json"
        info.parent.mkdir(parents=True, exist_ok=True)
        if not info.exists():
            self._gap()
            r = _run(["yt-dlp", "--no-update", "--sleep-requests", "1", "-J", "--skip-download", f"https://www.youtube.com/watch?v={vid}"], timeout=120)
            if r.returncode != 0 or not r.stdout.strip():
                return {"failed": (r.stderr or "")[-160:].strip()}
            info.write_text(r.stdout, encoding="utf-8")
        d = json.loads(info.read_text(encoding="utf-8"))
        res = 0
        for f in d.get("formats") or []:
            if f.get("vcodec") not in (None, "none") and f.get("width") and f.get("height"):
                res = max(res, min(f["width"], f["height"]))
        return {"res": res, "duration": d.get("duration") or 0, "title": d.get("title") or "", "channel": d.get("channel") or "",
                "w": d.get("width"), "h": d.get("height"), "info": str(info)}

    def preview(self, vid: str, info: str) -> str | None:
        out = self.wd / "preview" / f"{vid}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        if _valid_video(out):
            return str(out)
        out.unlink(missing_ok=True)
        # 주소로 새로 받는다 — info 파일 재사용은 2/24편이 403(1판 실측: wqJZ·UNB6, 사람 정답의 핵심 소스)
        for _try in range(2):   # 10-17 실측: 새 주소로도 1/20편 403 — 한 번 더(다른 서명 주소가 나온다)
            self._gap()
            r = _run(["yt-dlp", "--no-update", "-f", "bv*", "-S", "res:360,+size", "--download-sections",
                      f"*0-{PREVIEW_HEAD}", "-o", str(out), f"https://www.youtube.com/watch?v={vid}"], timeout=600)
            if _valid_video(out):
                break
            out.unlink(missing_ok=True)
        if _valid_video(out):
            self.bytes += out.stat().st_size
            return str(out)
        out.unlink(missing_ok=True)
        self.log(f"[미리보기 실패] {vid} {(r.stderr or '')[-120:]}")
        return None

    def section(self, vid: str, info: str, a: float, b: float) -> str | None:
        """쓸 구간만 1080p(없으면 ≥720p) 영상만 — 통째로 받지 않는다(SECTION_FMT 주석)."""
        out = self.wd / "sections" / f"{vid}_{int(a * 10):05d}_{int(b * 10):05d}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        if _valid_video(out, b - a):
            return str(out)
        out.unlink(missing_ok=True)
        for fmt in (SECTION_FMT, "137/bv*[height>=1080]/bv*[width>=1080]/bv*[height>=720]"):   # HLS 가 빈 파일이면(10-17 qTWg) DASH 로 한 번 더
            self._gap()
            r = _run(["yt-dlp", "--no-update", "-f", fmt, "--download-sections", f"*{a:.2f}-{b:.2f}", "-o", str(out),
                      f"https://www.youtube.com/watch?v={vid}"], timeout=900)
            if _valid_video(out, b - a):
                break
            out.unlink(missing_ok=True)
        if _valid_video(out, b - a):
            self.bytes += out.stat().st_size
            return str(out)
        out.unlink(missing_ok=True)
        self.log(f"[구간 받기 실패] {vid} {a}-{b} {(r.stderr or '')[-160:]}")
        return None


# ── 3. 프레임 → 시트 → 설명(시트 한 장씩) ─────────────────────────────────
def _valid_video(p, need: float = 0.0) -> bool:
    """받은 파일이 진짜 영상인가 — 1판 실측: 구간 받기 실패가 262바이트 껍데기를 남겨 '받음'으로 셌다(17개 중 7개).
    need = 요청한 길이(초) — 5판 실측: HLS 구간 79개 중 9개가 요청보다 짧게 끊겼다(2.9초 요청 → 1.04초). 0.3초 넘게 모자라면 무효."""
    p = Path(p)
    return p.exists() and p.stat().st_size > 10000 and _probe_dur(str(p)) >= max(0.01, need - 0.3)


def _probe_dur(p: str) -> float:
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def frame_cells(preview: str, vid: str, wd: Path) -> list[dict]:
    """미리보기에서 칸 프레임을 뽑는다 → [{vid, n, t, interval, img}]. 간격 = max(2초, 길이/MAX_FRAMES)."""
    dur = min(_probe_dur(preview), PREVIEW_HEAD)
    if dur <= 0:
        return []
    step = max(2.0, round(dur / MAX_FRAMES, 1))
    fdir = wd / "frames" / vid
    fdir.mkdir(parents=True, exist_ok=True)
    if not list(fdir.glob("*.jpg")):
        _run(["ffmpeg", "-v", "error", "-y", "-i", preview, "-vf", f"fps=1/{step},scale={CELL}:{CELL}:force_original_aspect_ratio=decrease",
              "-t", str(dur), str(fdir / "%04d.jpg")], timeout=600)
    out = []
    for k, f in enumerate(sorted(fdir.glob("*.jpg"))):
        t = round(k * step + step / 2, 2)   # fps 필터는 각 간격 가운데 프레임
        if t >= dur:
            break
        out.append({"vid": vid, "t": t, "interval": step, "img": str(f), "luma": _luma(f)})
    return out


def _luma(img) -> float:
    from PIL import Image, ImageStat
    try:
        return round(ImageStat.Stat(Image.open(img).convert("L")).mean[0], 1)
    except Exception:  # noqa: BLE001 — 못 재면 밝다고 보지 않는다(어두움 판정에서 빠지지 않게 0)
        return 0.0


def make_sheet(cells: list[dict], start_no: int, out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    cols = 6
    rows = math.ceil(len(cells) / cols)
    sh = Image.new("RGB", (cols * (CELL + 6), rows * (CELL + 6)), "white")
    d = ImageDraw.Draw(sh)
    font = ImageFont.truetype(FONT_B, 24)
    for j, c in enumerate(cells):
        x, y = (j % cols) * (CELL + 6), (j // cols) * (CELL + 6)
        im = Image.open(c["img"]).convert("RGB")
        sh.paste(im, (x + (CELL - im.width) // 2, y + (CELL - im.height) // 2))
        n = str(start_no + j)
        d.rectangle([x, y, x + 14 + 14 * len(n), y + 30], fill="black")
        d.text((x + 5, y + 1), n, font=font, fill="yellow")
    sh.save(out, quality=85)
    return out


TAG_PROMPT = """그림은 영상 프레임 칸들이다(노란 번호 {lo}~{hi}). 찾는 제품: {product}
각 번호마다 **보이는 것만** 적어라(추측 금지):
- what: 무엇이 보이나 영어 6~12낱말(사물·장소)  - action: 동작 영어 2~6낱말(없으면 "")
- people: none / hands / 사람 수·성별·나이(예 "1 woman", "boy", "2 adults")
- text: 화면에 글자(자막·캡션·로고·워터마크·손글씨·앱 화면 글자)가 보이면 true
- dark: 거의 검정·암전·전환 화면이면 true   - cg: 3D 그래픽·애니메이션이면 true
- product: 찾는 제품 그 자체가 보이면 "same", 같은 종류 다른 제품이면 "similar", 아니면 "no"
번호를 빠짐없이. 출력 JSON만: {{"cells":[{{"n":번호,"what":"...","action":"...","people":"...","text":false,"dark":false,"cg":false,"product":"no"}}]}}"""


def tag_video(cells: list[dict], product: str, llm, wd: Path, vid: str) -> list[dict]:
    """영상 하나의 칸들을 시트 한 장(30칸)씩 설명. 캐시 = tags/<vid>.json(프롬프트 판·제품 설명이 같을 때만)."""
    cache = wd / "tags" / f"{vid}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    key = f"{PROMPT_VER}|{len(cells)}"     # 같은 작업 폴더 = 같은 제품. 제품 설명 글은 실행마다 조금씩 달라 키에 넣지 않는다(재태깅 낭비)
    if cache.exists():
        c = json.loads(cache.read_text(encoding="utf-8"))
        ck = str(c.get("key") or "")
        if ck == key or (ck.startswith(PROMPT_VER + "|") and ck.endswith(f"|{len(cells)}")):   # 1판 키(제품 설명 포함)도 받는다
            for x in c["cells"]:
                if x.get("luma") is None and x.get("img"):
                    x["luma"] = _luma(x["img"])
            return c["cells"]
    got = {}
    for s0 in range(0, len(cells), SHEET_N):
        chunk = cells[s0:s0 + SHEET_N]
        sp = make_sheet(chunk, s0, wd / "tags" / f"{vid}_{s0 // SHEET_N}.jpg")
        d, err = llm([sp.read_bytes()], TAG_PROMPT.format(lo=s0, hi=s0 + len(chunk) - 1, product=product), f"ma_tag:{vid}")
        for r in (d or {}).get("cells") or (d or {}).get("items") or []:
            n = _as_int(r.get("n")) if isinstance(r, dict) else None
            if n is not None and s0 <= n < s0 + len(chunk):
                got[n] = r
    out = []
    for k, c in enumerate(cells):
        r = got.get(k)
        if not r:
            continue   # 설명 못 받은 칸은 후보에서 뺀다(빈 설명을 '맞음'으로 세지 않는다)
        out.append({**c, "what": str(r.get("what") or ""), "action": str(r.get("action") or ""), "people": str(r.get("people") or ""),
                    "text": bool(r.get("text")), "dark": bool(r.get("dark")), "cg": bool(r.get("cg")),
                    "product": r.get("product") if r.get("product") in ("same", "similar", "no") else "no"})
    cache.write_text(json.dumps({"key": key, "cells": out}, ensure_ascii=False), encoding="utf-8")
    return out


# ── 4. 판정 주인 ───────────────────────────────────────────────────────────
def allowed(cell: dict, kind: str, rules: dict, res: int) -> bool:
    """후보 칸 하나를 이 종류 토막에 써도 되나 — 유일한 판단 자리."""
    if cell.get("text") or cell.get("dark"):          # A5 남의 글자 · 어두운 칸
        return False
    if cell.get("luma") is not None and cell["luma"] < MIN_LUMA:   # 모델이 dark=false 라 해도 실제로 어두운 칸(1판 '중국 주방가전 회사가' 검정 컷)
        return False
    if cell.get("cg") and not rules.get("allow_cg"):
        return False
    if res < rules.get("min_res", 720):               # A4
        return False
    p = cell.get("product")
    if kind == "product":
        return p == "same"
    if kind == "before":
        return p in ("similar", "same")
    if rules.get("same_product_only"):
        return p == "same"
    return True                                       # similar(연상) — 재미썸홈만 여기까지 온다


def reuse_conflict(vid: str, t0: float, t1: float, used: list[tuple], prev: tuple | None = None) -> str | None:
    """같은 소스 재사용 판정 — 이유 문자열(막힘) 또는 None.
    ① 한 영상 안에서 같은 소스의 겹치거나 ±REUSE_GAP 초 안 구간을 두 번 쓰지 않는다(사장님 10-17, 재미썸홈 수정2 같은 컷 두 번).
       단 바로 앞 컷을 이어 가는 것(prev 끝 = 이번 시작, 앞으로만)은 한 컷의 연장이라 허용.
    ② 바로 앞 컷과 같은 소스면 원본 시각이 앞으로만(B13 되감김 0)."""
    if prev and prev[0] == vid:
        if t0 < prev[2] - 1e-6:
            return "되감김(B13)"
        if abs(t0 - prev[2]) < 1e-6:
            return None                                # 이어 가기
    for (v, a, b) in used:
        if v == vid and t0 < b + REUSE_GAP and t1 > a - REUSE_GAP:
            return f"같은 소스 재사용 {v} {a:.1f}~{b:.1f}"
    return None


def select(toks: list[dict], needs: dict, ranked: dict, cells: dict, meta: dict, rules: dict, memes: dict | None = None) -> list[dict]:
    """토막별 최종 선택. ranked[i] = [(cell_id, score)] 높은 순. cells[cell_id] = 칸. meta[vid] = {res,...}. memes[i] = 짤 id.
    규칙: allowed · reuse_conflict · A12(같은 줄 안에서 앞 토막과 같은 영상 +2점) · B4(앞 컷을 이어 갈 수 있으면 이어 간다: 이웃 토막 한 컷)
    · 마지막 묶음 컷 ≥1.2초·끝 컷 ≥1.5초(못 채우면 앞 컷 이어 가기) · 1080 우선(+1점)."""
    picks, used = [], []
    prev = None          # (vid, t0, t1, line, cell)
    memes = memes or {}
    for k, t in enumerate(toks):
        i, kind = t["i"], needs[t["i"]]["kind"]
        dur = float(t["dur"])
        if kind == "meme":
            mid = memes.get(i)
            cont = bool(mid and picks and picks[-1].get("src") == "meme:" + mid)   # 바로 앞 토막과 같은 짤 = 한 컷 이어 가기
            used_memes = {p["src"] for p in picks if str(p.get("src", "")).startswith("meme:")}
            if mid and (cont or "meme:" + mid not in used_memes):                  # B6 짤 되풀이 금지
                a = picks[-1]["src_t1"] if cont else 0.0
                picks.append({"i": i, "src": "meme:" + mid, "vid": None, "src_t0": round(a, 2), "src_t1": round(a + dur, 2),
                              "dur": dur, "kind": "meme", "cont": cont, "score": None, "seen": "짤 " + mid})
                prev = None
                continue
            picks.append({"i": i, "none": True, "kind": kind, "why": "짤 못 고름"})
            prev = None
            continue
        best, best_s = None, -1e9
        why = {"후보": len(ranked.get(i, [])), "점수미달": 0, "규칙탈락": 0, "재사용": 0}
        same_line = bool(prev and prev[3] == t["line"])
        # 이어 가기 후보(B4): 앞 컷과 같은 영상·같은 줄, 이어 간 구간이 그 칸의 설명 프레임 곁
        if same_line:
            pv, _, pe, _, _ = prev
            for cid, s in ranked.get(i, []):
                c = cells[cid]
                if c["vid"] == pv and c["t"] - 2.5 <= pe <= c["t"] + 1.0 and s >= MIN_SCORE - 1:
                    if allowed(c, kind, rules, meta[pv]["res"]):
                        best, best_s = ("cont", c, pe), s + 3
                        break
        for cid, s in ranked.get(i, []):
            if s < MIN_SCORE:
                why["점수미달"] += 1
                continue
            c = cells[cid]
            res = meta.get(c["vid"], {}).get("res", 0)
            if not allowed(c, kind, rules, res):
                why["규칙탈락"] += 1
                continue
            a = max(0.0, c["t"] - dur / 2)   # 설명한 프레임(칸 시각 t)을 컷 가운데에 — 칸 간격이 4.6초면 칸 시작부터 자르면 2초 어긋난다(10-17 실측)
            if reuse_conflict(c["vid"], a, a + dur, used, prev[:3] if prev else None):
                why["재사용"] += 1
                continue
            sc = s + (2 if same_line and prev[0] == c["vid"] else 0) + (1 if res >= rules.get("pref_res", 1080) else 0)
            if sc > best_s:
                best, best_s = ("new", c, a), sc
        if best is None and same_line and prev[2] + dur - prev[4]["t"] <= 2.5:
            # 같은 문장 이웃 토막인데 새 장면이 없으면 앞 컷을 이어 간다(B4 '자막 토막=컷 1:1 고집 금지', A12 같은 줄기) — 설명 프레임에서 2.5초 안까지만
            best, best_s = ("cont", prev[4], prev[2]), None
            why["앞컷이어감"] = 1
        if best is None:
            picks.append({"i": i, "none": True, "kind": kind, "why": "규칙 통과 후보 없음 " + json.dumps(why, ensure_ascii=False)})
            prev = None
            continue
        how, c, a = best
        p = {"i": i, "src": c["vid"], "vid": c["vid"], "src_t0": round(a, 2), "src_t1": round(a + dur, 2), "dur": dur, "kind": kind,
             "cont": how == "cont", "score": best_s, "seen": " / ".join(x for x in (c["what"], c["action"], c["people"]) if x),
             "cell_t": c["t"], "res": meta[c["vid"]]["res"]}
        if why.get("앞컷이어감"):
            p["fallback"] = "앞 컷 이어 감(새 장면 없음)"
        picks.append(p)
        if how == "cont" and used and used[-1][0] == c["vid"]:
            used[-1] = (c["vid"], used[-1][1], p["src_t1"])
        else:
            used.append((c["vid"], p["src_t0"], p["src_t1"]))
        prev = (c["vid"], p["src_t0"], p["src_t1"], t["line"], c)
    _slow_ending(picks, toks)
    return picks


def _slow_ending(picks: list[dict], toks: list[dict]):
    """B4 마지막 묶음: 컷 길이(이어 가기 묶음 합) — 끝 컷 <1.5초면 앞 토막과 같은 영상 이어 가기로 표시만(실제 구간은 이어진 그대로)."""
    if len(picks) < 2:
        return
    last, before = picks[-1], picks[-2]
    if last.get("none") or before.get("none") or last.get("cont"):
        return
    if last["dur"] < 1.5 and before.get("vid") and last.get("vid") == before["vid"] and abs(last["src_t0"] - before["src_t1"]) <= REUSE_GAP:
        last["src_t0"], last["src_t1"], last["cont"] = before["src_t1"], round(before["src_t1"] + last["dur"], 2), True


def cut_lengths(picks: list[dict]) -> list[float]:
    """이어 가기를 합친 실제 컷 길이 목록(B4 컷 중앙 잴 때)."""
    out = []
    for p in picks:
        if p.get("cont") and out:
            out[-1] += p.get("dur", 0)
        else:
            out.append(p.get("dur", 0))
    return [round(x, 2) for x in out]


# ── 짝짓기(글) ─────────────────────────────────────────────────────────────
MATCH_PROMPT = """숏폼 편집자다. [토막]마다 [장면 목록]에서 토막의 명사·동작이 **화면에 그대로 보이는** 장면을 점수(0~10)와 함께 최대 5개 골라라.
10 = 말한 사물·동작이 정확히 보임, 6 = 대체로 맞음, 3 이하 = 분위기만 비슷. 맞는 게 없으면 빈 목록. 번호를 순서대로 찍지 마라.
[토막]
{toks}
[장면 목록] (번호: 설명)
{cells}
출력 JSON만: {{"picks":[{{"tok":토막번호,"cands":[[장면번호,점수],...]}}]}}"""


def _words(s: str) -> set:
    return {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", (s or "").lower())} - {"the", "and", "with", "into", "from", "for", "that", "this"}


def shortlist(need: dict, kind: str, cells: dict, meta: dict, rules: dict, k: int = 40) -> list:
    kw = _words(need["need"] + " " + " ".join(need["keywords"]))
    scored = []
    for cid, c in cells.items():
        if not allowed(c, kind, rules, meta.get(c["vid"], {}).get("res", 0)):
            continue
        s = len(kw & _words(c["what"] + " " + c["action"] + " " + c["people"]))
        scored.append((s, cid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [cid for _, cid in scored[:k]]


def match_lines(toks, needs, cells, meta, rules, llm, log=print) -> dict:
    """줄(문장)마다 1회: 토막 need ↔ 후보 칸 설명(글) → ranked[i] = [(cell_id, score)]."""
    ranked = {}
    by_line = {}
    for t in toks:
        if needs[t["i"]]["kind"] != "meme":
            by_line.setdefault(t["line"], []).append(t)
    jobs = []
    for li, ts in by_line.items():
        ids = []
        for t in ts:
            for cid in shortlist(needs[t["i"]], needs[t["i"]]["kind"], cells, meta, rules, k=max(15, 45 // len(ts))):
                if cid not in ids:
                    ids.append(cid)
        if not ids:
            continue
        tl = "\n".join(f"{t['i']}. «{t['text']}» 원하는 장면: {needs[t['i']]['need']}" for t in ts)
        cl = "\n".join(f"{cid}: {cells[cid]['what']}; {cells[cid]['action']}; 사람 {cells[cid]['people']}" for cid in ids)
        jobs.append((li, ts, set(ids), MATCH_PROMPT.format(toks=tl, cells=cl)))

    def run(job):
        li, ts, ids, prompt = job
        d, err = llm([], prompt, f"ma_match:{li}")
        return li, ts, ids, d, err
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for li, ts, ids, d, err in ex.map(run, jobs):
            valid = {t["i"] for t in ts}
            for p in (d or {}).get("picks") or []:
                ti = _as_int(p.get("tok")) if isinstance(p, dict) else None
                if ti not in valid:
                    continue
                lst = []
                for c in p.get("cands") or []:
                    if isinstance(c, (list, tuple)) and len(c) >= 2:
                        cid, s = _as_int(c[0]), _as_int(c[1])
                        if cid in ids and s is not None:
                            lst.append((cid, s))
                ranked[ti] = sorted(lst, key=lambda x: -x[1])[:5]   # 3개면 1080 검사로 몇 개 빠지면 빈칸(4판 실측)
            seq = [r[0][0] for r in (ranked.get(t["i"]) for t in ts) if r]
            n_seq = sum(1 for a, b in zip(seq, seq[1:]) if b == a + 1)
            if len(seq) > 3 and n_seq >= len(seq) - 1:
                log(f"[경고] 줄 {li} 짝짓기가 번호를 순서대로 찍음({n_seq}/{len(seq) - 1}) — 대조 안 한 답 의심")
    return ranked


MEME_PROMPT = """숏폼 편집자다. 각 토막(반응·감탄 자리)에 어울리는 짤을 [짤 목록]에서 하나씩 골라라. 같은 짤 두 번 금지.
[토막]
{toks}
[짤 목록] id: 설명(감정)
{memes}
출력 JSON만: {{"picks":[{{"tok":번호,"id":"짤id"}}]}}"""


def pick_memes(toks, needs, llm) -> dict:
    mt = [t for t in toks if needs[t["i"]]["kind"] == "meme"]
    if not mt or not MEME_INDEX.exists():
        return {}
    idx = [m for m in json.loads(MEME_INDEX.read_text(encoding="utf-8")) if (MEME_DIR / f"{m['id']}.mp4").exists()]
    ok = {m["id"] for m in idx}
    d, _ = llm([], MEME_PROMPT.format(toks="\n".join(f"{t['i']}. «{t['text']}» (문장: {t['line_text']})" for t in mt),
                                      memes="\n".join(f"{m['id']}: {m.get('title', '')} ({m.get('emotion', '')})" for m in idx)), "ma_meme")
    out, seen = {}, set()
    for p in (d or {}).get("picks") or []:
        ti, mid = _as_int(p.get("tok")), str(p.get("id") or "")
        if ti is not None and mid in ok and mid not in seen:
            out[ti] = mid
            seen.add(mid)
    return out


# ── 5. 계획 시트 ───────────────────────────────────────────────────────────
def _grab(src: str, t: float, out: Path) -> Path | None:
    _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t):.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=-2:180", str(out)], timeout=60)
    return out if out.exists() else None


def plan_sheet(picks, toks, wd: Path, rows_per: int = 10) -> list[str]:
    from PIL import Image, ImageDraw, ImageFont
    font, small = ImageFont.truetype(FONT_B, 18), ImageFont.truetype(FONT, 14)
    tok = {t["i"]: t for t in toks}
    gdir = wd / "plan" / "_frames"
    gdir.mkdir(parents=True, exist_ok=True)
    pages = []
    for p0 in range(0, len(picks), rows_per):
        chunk = picks[p0:p0 + rows_per]
        W, RH = 1100, 196
        sh = Image.new("RGB", (W, RH * len(chunk)), "white")
        d = ImageDraw.Draw(sh)
        for r, p in enumerate(chunk):
            y = r * RH
            d.text((8, y + 8), f"{p['i']}. {tok[p['i']]['text']}", font=font, fill="black")
            lab = "없음 — " + p.get("why", "") if p.get("none") else f"{p['kind']}{' (이어감)' if p.get('cont') else ''} {p['src']} {p['src_t0']}~{p['src_t1']}s"
            d.text((8, y + 36), lab, font=small, fill="red" if p.get("none") else "blue")
            d.text((8, y + 56), (p.get("seen") or "")[:60], font=small, fill="gray")
            if not p.get("none"):
                if p["src"].startswith("meme:"):
                    src, a = str(MEME_DIR / f"{p['src'][5:]}.mp4"), p["src_t0"]
                elif p.get("section_file"):
                    src, a = p["section_file"], p["section_ss"]
                else:
                    src, a = str(wd / "preview" / f"{p['vid']}.mp4"), p["src_t0"]
                for k, tt in enumerate((a + p["dur"] * 0.25, a + p["dur"] * 0.75)):
                    g = _grab(src, tt, gdir / f"{p['i']}_{k}.jpg")
                    if g:
                        im = Image.open(g).convert("RGB")
                        im.thumbnail((330, 180))
                        sh.paste(im, (420 + k * 340, y + 8))
            d.line([(0, y + RH - 1), (W, y + RH - 1)], fill="#ccc")
        out = wd / "plan" / f"계획_시트_auto_{p0 // rows_per + 1}.jpg"
        sh.save(out, quality=85)
        pages.append(str(out))
    return pages


# ── 전체 흐름 ──────────────────────────────────────────────────────────────
def reupload_of(m: dict, accepted: list[dict]) -> str | None:
    """재업로드(같은 영상 다른 id) 판정 — 길이 30초 넘고 이미 받기로 한 영상과 길이 차 ≤1초면 같은 영상으로 본다.
    1판 실측: cFL4LQH_trE(Amazing Finds) = rBCNBy1xmjQ(DreadTech) 재업(275초, 사람 시트 동일) — 두 id 를 다른 소스로 세면
    같은 그림이 두 번 나와도 ±3초 재사용 규칙이 못 막는다."""
    d = m.get("duration") or 0
    if d <= 30:
        return None
    for a in accepted:
        if abs((a.get("duration") or 0) - d) <= 1.0:
            return a.get("id")
    return None


def _gather(queries, net, state, log):
    """검색 → 메타(해상도) → 미리보기 대상 고르기. state 에 누적."""
    for q in queries:
        if len(state["queries"]) >= MAX_QUERIES:
            log(f"[상한] 검색어 {MAX_QUERIES}개 — '{q['q']}' 안 씀")
            break
        state["queries"].append(q)
        rows = [r for r in net.search(q["q"], PER_QUERY) if 5 <= (r.get("duration") or 0) <= 1800]
        n_meta = n_prev = 0
        for r in rows:
            if n_meta >= META_PER_QUERY or n_prev >= PREVIEW_PER_QUERY or len(state["previews"]) >= MAX_PREVIEWS:
                break
            if r["id"] in state["meta"]:
                continue
            m = net.meta(r["id"])
            n_meta += 1
            m.update({"query": q["q"], "purpose": q.get("purpose"), "search_title": r.get("title")})
            state["meta"][r["id"]] = m
            dup = reupload_of(m, [state["meta"][v] | {"id": v} for v in state["previews"]])
            if dup:
                m["reupload_of"] = dup
                log(f"[재업 의심] {r['id']} = {dup}(길이 같음) — 안 씀")
            elif m.get("res", 0) >= 720:
                state["previews"].append(r["id"])
                n_prev += 1
        log(f"[검색] «{q['q']}» {len(rows)}편 → 미리보기 대상 누적 {len(state['previews'])}")


def _tag_all(vids, net, state, product, llm, wd, log):
    def one(vid):
        m = state["meta"][vid]
        pv = net.preview(vid, m["info"])
        if not pv:
            return vid, []
        return vid, frame_cells(pv, vid, wd)
    todo = [v for v in vids if v not in state["tagged"]]
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        framed = list(ex.map(one, todo))
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        tagged = list(ex.map(lambda vc: (vc[0], tag_video(vc[1], product, llm, wd, vc[0]) if vc[1] else []), framed))
    for vid, cs in tagged:
        state["tagged"].add(vid)
        for c in cs:
            state["cells"][len(state["cells"])] = c
    log(f"[태깅] 영상 {len(todo)}편 → 칸 누적 {len(state['cells'])}")


def plan_materials(script_json, channel_rules, workdir=None, net=None, llm=None, log=print, sections: bool = True,
                   max_rounds: int = 2) -> dict:
    """대본 → 재료.json(dict). script_json = 경로 또는 dict, channel_rules = '잇썸홈'|'재미썸홈'|dict."""
    T = {}
    t_all = time.time()
    sj = json.loads(Path(script_json).read_text(encoding="utf-8")) if isinstance(script_json, (str, Path)) else script_json
    rules = CHANNELS[channel_rules] if isinstance(channel_rules, str) else channel_rules
    wd = Path(workdir or ROOT / "_material_auto")
    wd.mkdir(parents=True, exist_ok=True)
    net = net or Net(wd, log)
    llm = llm if isinstance(llm, LLM) else LLM(llm)
    topic, toks = norm_script(sj)
    state = {"queries": [], "meta": {}, "previews": [], "tagged": set(), "cells": {}}
    stopped, picks, rounds, needs = None, [], 0, {}
    try:
        t = time.time()
        qp = plan_queries(topic, toks, rules, llm)
        needs = qp["needs"]
        T["1_검색어"] = round(time.time() - t, 1)
        t = time.time()
        _gather(qp["queries"], net, state, log)
        T["2_검색·메타"] = round(time.time() - t, 1)
        t = time.time()
        _tag_all(state["previews"], net, state, qp["product"], llm, wd, log)
        T["3_미리보기·태깅"] = round(time.time() - t, 1)
        t = time.time()
        memes = pick_memes(toks, needs, llm)
        ranked = match_lines(toks, needs, state["cells"], state["meta"], rules, llm, log)
        picks = select(toks, needs, ranked, state["cells"], state["meta"], rules, memes)
        T["4_짝짓기·선택"] = round(time.time() - t, 1)
        # 빈 토막 → 검색어 바꿔 재검색(최대 max_rounds)
        while rounds < max_rounds and any(p.get("none") and p["kind"] != "meme" for p in picks) and len(state["queries"]) < MAX_QUERIES:
            rounds += 1
            t = time.time()
            empty = [x for x in toks if any(p["i"] == x["i"] and p.get("none") and p["kind"] != "meme" for p in picks)]
            d, _ = llm([], REQUERY_PROMPT.format(topic=topic, nq=min(3, MAX_QUERIES - len(state["queries"])), rule_text=_rule_text(rules),
                                                 toks="; ".join(f"{x['i']}. «{x['text']}» ({needs[x['i']]['need']})" for x in empty),
                                                 tried=" / ".join(q["q"] for q in state["queries"])), f"ma_requery:{rounds}")
            newq = [q for q in (d or {}).get("queries") or [] if isinstance(q, dict) and q.get("q")
                    and q["q"] not in [x["q"] for x in state["queries"]]]
            if not newq:
                break
            before = set(state["previews"])
            _gather(newq, net, state, log)
            _tag_all([v for v in state["previews"] if v not in before], net, state, qp["product"], llm, wd, log)
            ranked = match_lines(toks, needs, state["cells"], state["meta"], rules, llm, log)
            picks = select(toks, needs, ranked, state["cells"], state["meta"], rules, memes)
            T[f"5_재검색{rounds}"] = round(time.time() - t, 1)
        save_state(wd, {"topic": topic, "toks": toks, "needs": needs, "ranked": ranked, "memes": memes, "cells": state["cells"],
                        "meta": state["meta"], "queries": state["queries"], "rounds": rounds, "previews": state["previews"]})
        picks, sheets = finish_plan(toks, needs, ranked, memes, state, rules, net, llm, wd, sections, T)
    except Stop as e:
        stopped, sheets = str(e), []
        log(f"[멈춤] {e}")
    T["전체"] = round(time.time() - t_all, 1)
    return _write_out(wd, rules, topic, toks, needs, picks, state, rounds, stopped, sheets, T, llm, net)


def finish_plan(toks, needs, ranked, memes, state, rules, net, llm, wd, sections, T):
    """선택 → 1080 구간 받기 → 1080 글자 검사·재선택 → 계획 시트. plan_materials·replan 공용."""
    picks = select(toks, needs, ranked, state["cells"], state["meta"], rules, memes)
    if sections:
        t = time.time()
        fetch_sections(picks, state["meta"], net)
        T["6_구간받기"] = round(time.time() - t, 1)
        # 1080 컷 프레임 검사(남의 글자·어두움) — 360p 미리보기 설명이 놓친 작은 글자를 잡는다(1판: 'Click' 설명 자막 컷 통과)
        t = time.time()
        seen = {}            # (vid, src_t0, src_t1) → 검사 결과 — 다시 고른 뒤 그대로인 컷은 다시 안 묻는다
        for vr in range(VERIFY_ROUNDS + 1):
            for p in picks:
                k = (p.get("vid"), p.get("src_t0"), p.get("src_t1"))
                if k in seen:
                    p["verify"] = seen[k]
            flagged = verify_cuts(picks, wd, llm, only_new=True)
            for p in picks:
                if "verify" in p:
                    seen[(p.get("vid"), p.get("src_t0"), p.get("src_t1"))] = p["verify"]
            if not flagged or vr == VERIFY_ROUNDS:
                break
            ban_cells(flagged, state["cells"])
            picks = select(toks, needs, ranked, state["cells"], state["meta"], rules, memes)
            fetch_sections(picks, state["meta"], net)
        # 마지막 검사에도 걸린 컷은 쓰지 않는다(A5 > 빈칸) — 1판 4: 두 바퀴 재선택 뒤 최종 컷이 검사 없이 나갔다
        for p in picks:
            if p.get("verify") in ("text", "dark"):
                p.update({"none": True, "why": f"1080 검사 {p['verify']}"})
            elif p.get("vid") and not p.get("section_file"):
                p["verify"] = "구간 못 받음"
        T["6b_1080검사"] = round(time.time() - t, 1)
    for p in picks:
        if p.get("none"):
            p["tried"] = [q["q"] for q in state["queries"]]
    t = time.time()
    sheets = plan_sheet(picks, toks, wd)
    T["7_계획시트"] = round(time.time() - t, 1)
    return picks, sheets


def save_state(wd: Path, st: dict):
    """짝짓기까지의 결과(검색·태깅·순위)를 남긴다 — replan 이 모델·검색 없이 선택부터 다시 돈다."""
    d = {**st, "cells": {str(k): v for k, v in st["cells"].items()}, "ranked": {str(k): v for k, v in st["ranked"].items()},
         "needs": {str(k): v for k, v in st["needs"].items()}, "memes": {str(k): v for k, v in (st.get("memes") or {}).items()}}
    (wd / "state.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def replan(workdir, channel_rules, net=None, llm=None, log=print, sections: bool = True, rematch: bool = False) -> dict:
    """state.json 으로 선택부터 다시(규칙만 바뀌었을 때) — 검색·태깅·짝짓기 모델 호출 없음(1080 검사만 호출)."""
    wd = Path(workdir)
    rules = CHANNELS[channel_rules] if isinstance(channel_rules, str) else channel_rules
    d = json.loads((wd / "state.json").read_text(encoding="utf-8"))
    cells = {int(k): v for k, v in d["cells"].items()}
    ranked = {int(k): [tuple(x) for x in v] for k, v in d["ranked"].items()}
    needs = {int(k): v for k, v in d["needs"].items()}
    memes = {int(k): v for k, v in (d.get("memes") or {}).items()}
    state = {"queries": d["queries"], "meta": d["meta"], "previews": d.get("previews", []), "tagged": set(), "cells": cells}
    net = net or Net(wd, log)
    llm = llm if isinstance(llm, LLM) else LLM(llm)
    T, t0, stopped = {}, time.time(), None
    try:
        if rematch:   # 짝짓기만 다시(검색·태깅 없음) — 짝짓기 프롬프트·후보 수가 바뀌었을 때
            ranked = match_lines(d["toks"], needs, cells, d["meta"], rules, llm, log)
            save_state(wd, {**d, "cells": cells, "needs": needs, "memes": memes, "ranked": ranked})
        picks, sheets = finish_plan(d["toks"], needs, ranked, memes, state, rules, net, llm, wd, sections, T)
    except Stop as e:
        picks, sheets, stopped = [], [], str(e)
    T["전체(replan)"] = round(time.time() - t0, 1)
    return _write_out(wd, rules, d["topic"], d["toks"], needs, picks, state, d.get("rounds", 0), stopped, sheets, T, llm, net)


def _write_out(wd, rules, topic, toks, needs, picks, state, rounds, stopped, sheets, T, llm, net):
    tokd = {x["i"]: x for x in toks}
    shots = []
    for p in picks:
        s = {**p, "caption": tokd[p["i"]]["text"], "need": (needs.get(p["i"]) or {}).get("need", "")}
        if p.get("vid"):
            m = state["meta"][p["vid"]]
            s.update({"url": f"https://www.youtube.com/watch?v={p['vid']}", "src_title": m.get("title"), "src_channel": m.get("channel"),
                      "query": m.get("query")})
        shots.append(s)
    out = {"_note": f"material_auto {PROMPT_VER} — 자동 재료 계획(사람 검수 전). 채널 {rules['channel']}", "channel": rules["channel"],
           "topic": topic, "queries": state["queries"], "rounds": rounds, "stopped": stopped, "shots": shots,
           "cut_lengths": cut_lengths([p for p in picks if not p.get("none")]),
           "stats": {"time_sec": T, "llm_calls": len(llm.calls), "llm_ok": sum(1 for c in llm.calls if c["ok"]), "llm_429": llm.n429,
                     "yt_requests": getattr(net, "requests", None), "bytes": getattr(net, "bytes", None),
                     "videos_meta": len(state["meta"]), "videos_preview": len(state["previews"]), "cells": len(state["cells"]),
                     "empty": sum(1 for p in picks if p.get("none")), "toks": len(toks)},
           "sheets": sheets if not stopped else []}
    (wd / "재료_auto.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


VERIFY_PROMPT = """그림은 영상 컷 후보 프레임들이다(노란 번호 {lo}~{hi}). 각 번호마다 보이는 것만 적어라.
- text: 화면에 글자(자막·캡션·설명 문구·로고·워터마크·손글씨·앱/UI 글자)가 조금이라도 보이면 true. 제품 본체에 새겨진 아주 작은 상표만 있으면 false.
- dark: 거의 검정·암전이면 true   - what: 보이는 것 영어 6~10낱말
번호를 빠짐없이. 출력 JSON만: {{"cells":[{{"n":번호,"text":false,"dark":false,"what":"..."}}]}}"""


def verify_cuts(picks, wd: Path, llm, only_new: bool = False) -> list[dict]:
    """고른 컷마다 1080 구간의 가운데 프레임을 시트(20칸)로 모아 남의 글자·어두움 검사 → 걸린 컷 목록(p['verify'] 표시)."""
    from PIL import Image, ImageDraw, ImageFont
    todo = [p for p in picks if p.get("section_file") and not p.get("none") and (not only_new or "verify" not in p)]
    vdir = wd / "verify"
    vdir.mkdir(parents=True, exist_ok=True)
    flagged, W, H, cols = [], 360, 360, 5
    font = ImageFont.truetype(FONT_B, 26)
    for c0 in range(0, len(todo), 20):
        chunk, ims = todo[c0:c0 + 20], []
        for p in chunk:
            g = _grab(p["section_file"], p["section_ss"] + p["dur"] / 2, vdir / f"{p['i']}.jpg")
            ims.append(g)
            if not g:
                p["verify"] = "프레임 없음"   # 빈 칸을 모델에 보여 'ok'를 받지 않는다(5판: 잘린 구간이 ok 로 통과)
        sh = Image.new("RGB", (cols * (W + 6), math.ceil(len(chunk) / cols) * (H + 6)), "white")
        d = ImageDraw.Draw(sh)
        for j, g in enumerate(ims):
            x, y = (j % cols) * (W + 6), (j // cols) * (H + 6)
            if g:
                im = Image.open(g).convert("RGB")
                im.thumbnail((W, H))
                sh.paste(im, (x + (W - im.width) // 2, y + (H - im.height) // 2))
            d.rectangle([x, y, x + 40, y + 32], fill="black")
            d.text((x + 5, y + 1), str(j), font=font, fill="yellow")
        sp = vdir / f"sheet_{c0 // 20}.jpg"
        sh.save(sp, quality=88)
        r, _ = llm([sp.read_bytes()], VERIFY_PROMPT.format(lo=0, hi=len(chunk) - 1), "ma_verify")
        got = {_as_int(x.get("n")): x for x in (r or {}).get("cells") or [] if isinstance(x, dict)}
        for j, p in enumerate(chunk):
            x = got.get(j)
            if not ims[j]:
                continue
            if x is None:
                p["verify"] = "unchecked"
            elif x.get("text") or x.get("dark"):
                p["verify"] = "text" if x.get("text") else "dark"
                flagged.append(p)
            else:
                p["verify"] = "ok"
    return flagged


def ban_cells(flagged, cells: dict):
    """1080 검사에 걸린 컷의 칸(같은 영상, 칸 시각 ±간격)을 글자 칸으로 표시 — 다음 select 가 안 고른다."""
    for p in flagged:
        for c in cells.values():
            if c["vid"] == p.get("vid") and abs(c["t"] - p.get("cell_t", -99)) <= c["interval"] + 0.01:
                c["text" if p["verify"] == "text" else "dark"] = True


def fetch_sections(picks, meta, net, pad: float = 1.0, join_gap: float = 8.0):
    """쓸 구간만 받는다 — 영상마다 가까운 구간(join_gap 안)은 한 덩어리로."""
    by = {}
    for p in picks:
        if p.get("vid"):
            by.setdefault(p["vid"], []).append(p)
    jobs = []
    for vid, ps in by.items():
        ps = sorted(ps, key=lambda p: p["src_t0"])
        groups = [[ps[0]]]
        for p in ps[1:]:
            if p["src_t0"] - groups[-1][-1]["src_t1"] <= join_gap:
                groups[-1].append(p)
            else:
                groups.append([p])
        for g in groups:
            a, b = max(0.0, g[0]["src_t0"] - pad), max(p["src_t1"] for p in g) + pad
            jobs.append((vid, a, b, g))

    def one(j):
        vid, a, b, g = j
        return j, net.section(vid, meta[vid].get("info"), a, b)
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for (vid, a, b, g), f in ex.map(one, jobs):
            for p in g:
                if f:
                    p["section_file"], p["section_ss"] = f, round(p["src_t0"] - a, 2)


# ── 사람 매핑과 대조(검증 도구) ────────────────────────────────────────────
def human_map(mat: dict) -> dict:
    """사람 재료.json(두 꼴) → {토막 i: {vid, t0, seen, kind}}."""
    out = {}
    for s in mat.get("shots") or []:
        vid = re.sub(r"^src_|\.mp4$", "", s.get("src") or "")
        out[s["i"]] = {"vid": vid, "t0": s.get("ss"), "seen": s.get("ours") or "", "kind": s.get("kind")}
    for c in mat.get("cuts") or []:
        out[c["i"]] = {"vid": c.get("source"), "t0": c.get("src_t0"), "seen": c.get("seen") or "", "kind": c.get("kind")}
    # '(이어감)' 설명은 앞 컷 설명으로
    last = ""
    for i in sorted(out):
        if out[i]["seen"].startswith("(이어감)"):
            out[i]["seen"] = last
        last = out[i]["seen"]
    return out


JUDGE_PROMPT = """두 편집자가 같은 자막 토막에 고른 장면 설명이다. 토막마다 판정하라.
same_meaning: 두 장면이 자막이 말하는 명사·동작을 **같은 뜻으로** 보여주나(true/false).
better: 자막과 더 맞는 쪽 "A"(사람) / "B"(도구) / "=" (동급).
{rows}
출력 JSON만: {{"items":[{{"i":번호,"same_meaning":true,"better":"A|B|="}}]}}"""


def compare_human(auto: dict, human: dict, llm=None) -> dict:
    """판정 기준(먼저 적음): ① 동일 구간 = 같은 영상 id 이고 시작 시각 차 ≤3초 ② 같은 영상 = 같은 id, 다른 시각
    ③ 같은 뜻 = 다른 영상이라도 모델 판정(두 장면 설명 + 자막)으로 같은 명사·동작. 일치 = ① 또는 ③(②는 ③ 판정을 따른다)."""
    hm = human_map(human)
    rows, res = [], {}
    for s in auto["shots"]:
        h = hm.get(s["i"])
        if not h:
            continue
        a_vid = s.get("vid") or (s["src"][5:] if str(s.get("src", "")).startswith("meme:") else None)
        h_vid = (h["vid"] or "").replace("meme:", "")
        same_src = bool(a_vid and a_vid == h_vid)
        same_seg = same_src and h["t0"] is not None and abs(float(s.get("src_t0") or 0) - float(h["t0"])) <= 3
        res[s["i"]] = {"caption": s["caption"], "auto": None if s.get("none") else f"{a_vid}@{s.get('src_t0')}", "human": f"{h_vid}@{h['t0']}",
                       "auto_seen": s.get("seen") or ("없음" if s.get("none") else ""), "human_seen": h["seen"],
                       "same_seg": same_seg, "same_src": same_src}
        if not s.get("none"):
            rows.append(f"{s['i']}. 자막 «{s['caption']}» | A(사람): {h['seen']} | B(도구): {s.get('seen')}")
    if llm is not None and rows:
        for r0 in range(0, len(rows), 20):
            d, _ = llm([], JUDGE_PROMPT.format(rows="\n".join(rows[r0:r0 + 20])), "ma_judge")
            for it in (d or {}).get("items") or []:
                i = _as_int(it.get("i"))
                if i in res:
                    res[i]["same_meaning"] = bool(it.get("same_meaning"))
                    res[i]["better"] = it.get("better")
    n = len(res)
    match = sum(1 for r in res.values() if r["same_seg"] or r.get("same_meaning"))
    return {"n": n, "same_seg": sum(r["same_seg"] for r in res.values()), "same_src": sum(r["same_src"] for r in res.values()),
            "same_meaning": sum(1 for r in res.values() if r.get("same_meaning")), "match": match,
            "rate": round(match / n, 3) if n else None, "rows": res}


def compare_sheet(cmp_: dict, auto: dict, human: dict, human_src_dir: str, out: Path, rows_per: int = 12) -> list[str]:
    """사람 매핑과 다른 토막(동일 구간 아님)만: 자막 | 사람 프레임 | 도구 프레임 — 눈 대조용 시트."""
    from PIL import Image, ImageDraw, ImageFont
    font, small = ImageFont.truetype(FONT_B, 16), ImageFont.truetype(FONT, 13)
    hm, shots = human_map(human), {s["i"]: s for s in auto["shots"]}
    diff = [i for i, r in sorted(cmp_["rows"].items(), key=lambda x: int(x[0])) if not r["same_seg"]]
    tmp = out.parent / "_cmp_frames"
    tmp.mkdir(parents=True, exist_ok=True)
    pages = []

    def src_of_h(vid):
        return str(MEME_DIR / f"{vid[5:]}.mp4") if str(vid).startswith("meme:") else str(Path(human_src_dir) / f"src_{vid}.mp4")
    for p0 in range(0, len(diff), rows_per):
        chunk = diff[p0:p0 + rows_per]
        RH, W = 200, 1060
        sh = Image.new("RGB", (W, RH * len(chunk)), "white")
        d = ImageDraw.Draw(sh)
        for r, i in enumerate(chunk):
            i = int(i)
            y, row, s, h = r * RH, cmp_["rows"][i] if i in cmp_["rows"] else cmp_["rows"][str(i)], shots.get(i), hm.get(i)
            d.text((6, y + 6), f"{i}. {row['caption']}", font=font, fill="black")
            d.text((6, y + 32), f"판정 {('같은 뜻' if row.get('same_meaning') else '다름')} · 더 나음 {row.get('better')}", font=small, fill="blue")
            d.text((6, y + 52), "H " + (row.get("human_seen") or "")[:30], font=small, fill="gray")
            d.text((6, y + 70), "A " + (row.get("auto_seen") or "")[:30], font=small, fill="gray")
            imgs = []
            if h and h.get("t0") is not None:
                imgs.append(_grab(src_of_h(h["vid"]), float(h["t0"]) + 0.3, tmp / f"{i}_h.jpg"))
            else:
                imgs.append(None)
            if s and not s.get("none"):
                if str(s["src"]).startswith("meme:"):
                    imgs.append(_grab(str(MEME_DIR / f"{s['src'][5:]}.mp4"), s["src_t0"] + 0.3, tmp / f"{i}_a.jpg"))
                elif s.get("section_file"):
                    imgs.append(_grab(s["section_file"], s["section_ss"] + 0.3, tmp / f"{i}_a.jpg"))
                else:
                    imgs.append(_grab(str(out.parent / "preview" / f"{s['vid']}.mp4"), s["src_t0"] + 0.3, tmp / f"{i}_a.jpg"))
            else:
                imgs.append(None)
            for k, g in enumerate(imgs):
                x = 300 + k * 380
                d.text((x, y + 4), "사람" if k == 0 else "도구", font=small, fill="red")
                if g:
                    im = Image.open(g).convert("RGB")
                    im.thumbnail((360, 175))
                    sh.paste(im, (x, y + 22))
                else:
                    d.text((x, y + 80), "없음", font=font, fill="red")
            d.line([(0, y + RH - 1), (W, y + RH - 1)], fill="#ccc")
        f = out.parent / f"{out.stem}_{p0 // rows_per + 1}.jpg"
        sh.save(f, quality=85)
        pages.append(str(f))
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--channel", required=True, choices=list(CHANNELS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-sections", action="store_true")
    ap.add_argument("--human", help="사람 재료.json — 대조표를 같이 만든다")
    ap.add_argument("--human-src", help="사람 재료 원본 폴더(src_<id>.mp4) — 다른 토막 대조 시트")
    ap.add_argument("--compare-only", action="store_true", help="이미 만든 재료_auto.json 으로 대조만")
    ap.add_argument("--replan", action="store_true", help="state.json 으로 선택부터 다시(검색·태깅 없음)")
    ap.add_argument("--rematch", action="store_true", help="--replan 때 짝짓기(글)도 다시")
    a = ap.parse_args(argv)
    llm = LLM()
    if a.compare_only:
        res = json.loads(Path(a.out, "재료_auto.json").read_text(encoding="utf-8"))
    elif a.replan:
        res = replan(a.out, a.channel, llm=llm, sections=not a.no_sections, rematch=a.rematch)
    else:
        res = plan_materials(a.script, a.channel, a.out, llm=llm, sections=not a.no_sections)
    print(json.dumps(res["stats"], ensure_ascii=False))
    if a.human:
        human = json.loads(Path(a.human).read_text(encoding="utf-8"))
        cmp_ = compare_human(res, human, llm)
        Path(a.out, "대조_사람.json").write_text(json.dumps(cmp_, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in cmp_.items() if k != "rows"}, ensure_ascii=False))
        if a.human_src:
            print(compare_sheet(cmp_, res, human, a.human_src, Path(a.out, "대조_시트.jpg")))


if __name__ == "__main__":
    main()
