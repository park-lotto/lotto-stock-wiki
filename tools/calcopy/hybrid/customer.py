# -*- coding: utf-8 -*-
"""회원 PC(숏템 MCP) — 집 PC 제작 순서(channel/칼카피_제작순서 01~12) 그대로 한 편 (관제 234·097, 2026-10-21 사장님
"집에서는 한마디면 영상이 만들어지는데 여기서도 똑같애야 된다" / "볼케이노처럼 어떤 단계인지만 간략하게").

    python tools/calcopy/make.py --json hybrid start --ref <벤치 쇼츠 URL> --version 키치잇판
    python tools/calcopy/make.py --json hybrid approve <sid>
    python tools/calcopy/make.py --json hybrid status <sid>

판단 주인은 집 PC 와 같다(새로 적지 않는다): 판 = styles · 렌더 = render_bench · 배치 = placement · 대본 검사 = script_audit ·
자동 검사 = bench_check · 받기·가려내기 = screen. 집 PC 에서 Claude 워커가 브리프를 보고 하던 판단은 여기서
회원 Claude 에게 AI 요청(engine/client_llm.ask)으로 묻는다 — 지시문 = 제작순서 단계 파일·hybrid/briefs 의 기준 그대로.
회원 PC 에 없는 것(사장님 10-21): 서버 유튜브 API·제미나이·스피치매틱스 → yt-dlp·위스퍼 / 미나 → 회원 일레븐랩스 키 / 쿠팡 → 회원 파트너스 키(없으면 크롬).
진행 안내 = 작업 폴더 progress.json {step, total, stage} 한 곳 — MCP 는 stage 한 줄만 회원에게 보인다(세부 금지).
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import ROOT, StageError, jload, jsave, run  # noqa: E402

STAGES = [   # (키, 회원에게 보이는 한 줄) — 제작순서 99_회원PC_MCP.md 표와 같은 순서
    ("bench", "영상 확인 중"), ("origin", "원본 영상 찾는 중"), ("product", "제품 확인 중"), ("research", "자료 조사 중"),
    ("material", "재료 영상 모으는 중"), ("asr", "원음 정리 중"), ("script", "대본 쓰는 중"), ("sign", "대본 확인을 기다립니다"),
    ("plan", "장면 맞추는 중"), ("render", "목소리·영상 만드는 중"), ("check", "완성본 검사 중"), ("done", "완성"),
]
STAGE_TEXT = dict(STAGES)


class Stop(Exception):
    """제작순서 '멈출 때' — 그 편은 만들지 않는다. why = 회원에게 보이는 이유, fix = 회원이 할 수 있는 일."""
    def __init__(self, why: str, fix: str = ""):
        super().__init__(why)
        self.why, self.fix = why, fix


def base() -> Path:
    return Path(os.environ.get("CALCOPY_DATA_DIR") or (ROOT / "_data")) / "hybrid"


class Piece:
    def __init__(self, sid: str):
        self.sid = sid
        self.W = base() / sid                    # 작업물(받은 영상·시트·렌더)
        self.D = self.W / "doc"                  # 문서(조사·대본·재료·근거) — 집 PC channel/yanshottem/하이브리드_<키>/ 자리
        self.W.mkdir(parents=True, exist_ok=True)
        self.p = self.W / "piece.json"
        self.s = jload(self.p) if self.p.exists() else {"sid": sid, "done": {}, "at": time.time()}

    def save(self):
        jsave(self.p, self.s)

    def stage(self, key: str):
        i = [k for k, _ in STAGES].index(key) + 1
        jsave(self.W / "progress.json", {"step": i, "total": len(STAGES), "stage": STAGE_TEXT[key], "key": key, "at": time.time()})

    def mark(self, key: str, **info):
        self.s["done"][key] = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), **info}
        self.save()

    def did(self, key: str) -> bool:
        return key in self.s["done"]


# ── AI 요청(회원 Claude) ────────────────────────────────────────────────
def ask(tag: str, prompt: str, parts: list | None = None, need: tuple = ()) -> dict:
    from tools.calcopy.engine import client_llm
    r, why = client_llm.ask(parts or [], prompt, tag)
    if r is None:
        raise StageError(f"AI 요청 실패({tag}): {why}")
    miss = [k for k in need if k not in r]
    if miss:
        raise StageError(f"AI 답에 칸이 없다({tag}): {miss}")
    return r


def img(p: Path) -> tuple:
    """그림 파트 = (바이트, mime) — client_llm._write_parts 꼴."""
    p = Path(p)
    return (p.read_bytes(), "image/png" if p.suffix.lower() == ".png" else "image/jpeg")


def brief_text(*rel: str) -> str:
    """지시문 = 집 PC 문서 그대로(빌린 기술 꾸러미 안) — 회원에게 설명하지 않는다(요청 글로만)."""
    out = []
    for r in rel:
        p = ROOT / r
        if p.is_file():
            out.append(f"### {p.name}\n" + p.read_text(encoding="utf-8"))
    return "\n\n".join(out)


# ── 도구(기계적) ────────────────────────────────────────────────────────
def ytdlp(args: list, timeout: int = 300) -> subprocess.CompletedProcess:
    # 제목은 한국어로 — 없으면 유튜브가 영어 번역 제목을 줘 '연예인 이름이 제목에 있나'가 빗나갔다(10-21 선우용여 원본 'What's in Yong-ryeo's Bag')
    return subprocess.run(["yt-dlp", "--encoding", "utf-8", "--no-warnings", "--extractor-args", "youtube:lang=ko", *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def sheet(video: Path, dst: Path, fps: float = 1.0, cols: int = 6, rows: int = 5, w: int = 300, ss: float | None = None, t: float | None = None) -> Path:
    pre = (["-ss", f"{ss:.2f}"] if ss is not None else []) + (["-t", f"{t:.2f}"] if t is not None else [])
    run(["ffmpeg", "-y", "-v", "error", *pre, "-i", str(video), "-vf", f"fps={fps},scale={w}:-1,tile={cols}x{rows}", "-frames:v", "1", str(dst)])
    return dst


def frame(video: Path, t: float, dst: Path, crop: list | None = None) -> Path:
    vf = ["-vf", f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}"] if crop else []
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", *vf, str(dst)])
    return dst


def whisper(path: Path) -> list[dict]:
    """위스퍼 받아쓰기(회원 PC 결정 10-21) → [{t0, t1, text}]."""
    from tools.calcopy.engine import asr_local
    r = asr_local.transcribe(str(path))
    return [{"t0": s.get("start", s.get("t0", 0)), "t1": s.get("end", s.get("t1", 0)), "text": s.get("text", "")} for s in (r.get("segments") or [])]


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def fingerprint(bench_lines: list[dict], vtt: list[tuple[float, str]]) -> list[dict]:
    """벤치 말(받아쓰기) ↔ 원본 자동자막 — 같은 말이 원본 몇 초에 있나(제작순서 02 §4 '두세 줄 이상 맞으면 확정'). 맞은 줄만."""
    words = [(t, _norm(w)) for t, w in vtt if _norm(w)]
    out = []
    # 위스퍼는 나레·원음을 한 덩어리로 묶는다(10-21 실측: 2줄, 둘째 줄 80자) → 문장·쉼표·10~16자 토막으로 갈라 토막마다 대조
    chunks = []
    for b in bench_lines:
        for s in re.split(r"[.?!,]\s*", b["text"]):
            n = _norm(s)
            while len(n) > 16:
                chunks.append(n[:14]); n = n[10:]
            if len(n) >= 6:
                chunks.append(n)
    for q in dict.fromkeys(chunks):
        if not words:
            break
        best = (0.0, None)
        for i in range(len(words)):
            acc, j = "", i
            while j < len(words) and len(acc) < len(q) + 4:
                acc += words[j][1]; j += 1
            r = difflib.SequenceMatcher(None, q, acc[:len(q) + 4]).ratio()
            if r > best[0]:
                best = (r, words[i][0])
        if best[0] >= 0.7:
            out.append({"bench": q, "origin_t": round(best[1], 2), "score": round(best[0], 2)})
    return out


# ── 단계 ───────────────────────────────────────────────────────────────
def st_bench(P: Piece, ref: str):
    bd = P.W / "bench"; bd.mkdir(exist_ok=True)
    r = ytdlp(["-f", "bv*[height>=720]+ba/b", "--merge-output-format", "mp4", "--write-info-json", "--write-auto-subs", "--sub-langs", "ko",
               "-o", str(bd / "bench.%(ext)s"), ref])
    mp4 = bd / "bench.mp4"
    if not mp4.exists():
        raise Stop("영상을 받지 못했습니다", "영상 주소가 맞는지, 또는 유튜브 로그인 연결을 확인해 주세요")
    info = jload(bd / "bench.info.json") if (bd / "bench.info.json").exists() else {}
    sheet(mp4, bd / "sheet.jpg")
    lines = whisper(mp4)
    jsave(bd / "asr.json", lines)
    P.s["bench"] = {"url": ref, "id": info.get("id"), "title": info.get("title"), "channel": info.get("channel"), "date": info.get("upload_date"),
                    "dur": info.get("duration"), "desc": (info.get("description") or "")[:1500]}
    P.mark("bench")


ORIGIN_READ = """너는 쇼츠 원본 추적 담당이다. 아래는 남의 채널이 만든 연예인 쇼핑 쇼츠(벤치)의 1초 간격 장면 시트와 제목·설명·받아쓰기다.
제작 순서 문서(02 원본 찾기) 기준으로, 이 쇼츠가 따온 **연예인 본인 원본 영상**(본인 유튜브·방송)을 찾기 위한 단서를 읽어라.
- 화면 위·아래의 '출처: ○○' 글자 = 원본 채널. 방송 로고·프로그램 이름도 본다. 이름표·자막으로 말하는 사람을 확인(얼굴로 짐작한 이름은 '불명').
- 설명란 '영상 속 제품'은 그 채널의 파트너스 상품일 뿐 근거가 아니다.
- 연예인이 쓰는 물건(쇼핑 소재)이 아니면 is_shopping=false.
JSON 하나: {"celeb": "이름 또는 불명", "source_label": "화면 출처 글자 그대로 또는 ''", "channel_hint": "원본 채널 이름·핸들 추정 또는 ''",
 "product_words": ["제품을 가리키는 낱말"], "queries": ["유튜브 검색어 3~5개 — '<연예인> <제품 낱말>' 꼴"], "is_shopping": true}"""

ORIGIN_PICK = """너는 원본 판정 담당이다. 벤치 쇼츠의 말과 같은 말이 들어 있는 후보 원본 영상들이다(자동자막 지문 대조 결과).
제작 순서 02 §4·§5 기준: 두세 줄 이상 같은 말이 맞고, 그 제품을 말한 사람이 연예인 **본인**이어야 확정. 후보 썸네일·제목·채널·날짜도 본다
(원본은 벤치보다 먼저 올라왔다). 확정 못 하면 origin_id 를 ''.
JSON 하나: {"origin_id": "유튜브 id 또는 ''", "matched": [{"bench": "벤치 말", "origin_t": 초}], "self_spoken": true, "why": "한 줄"}"""


ORIGIN_TITLES = """너는 원본 후보 고르기 담당이다(제작 순서 02 §3). 연예인 본인 채널의 영상 목록(제목)에서, 벤치 쇼츠가 따온 원본일 만한 영상을 최대 8개 골라라 —
제목에 그 제품·쓰임(주방·청소·살림템·추천템 등)·계절이 맞는 것. 벤치보다 먼저 올라온 것.
JSON 하나: {"ids": ["유튜브 id", …]}"""


LOOK_FIXES = 2         # 완성본 눈 검수 실패 시 재료 고쳐 다시 렌더 횟수
TITLE_CHUNK = 120     # 원본 후보 제목 한 묶음(질문 하나 약 6천 자)
ORIGIN_TRY = 16       # 자막 대조할 후보 수(자막만 받는다 — 편당 몇 초)


def _channels_of(found: list[dict], r: dict) -> list[str]:
    """원본을 뒤질 채널 id — ① 연예인 **본인 채널**(채널 이름에 연예인 이름, 사장님 10-21 "연예인 본인 채널이 1순위") ② 출처 글자·채널 단서와 맞는 채널."""
    hint = _norm((r.get("source_label") or "").replace("출처", "") + (r.get("channel_hint") or ""))
    celeb = _norm(r.get("celeb") or "")
    own, other = [], []
    for c in found:
        name, cid = _norm(c.get("channel") or ""), c.get("channel_id")
        if not cid or not name or cid in own or cid in other:
            continue
        if len(celeb) >= 2 and celeb in name:
            own.append(cid)
        elif name in hint or hint[:6] in name:
            other.append(cid)
    return own + other


def _search(qs: list[str], n: int = 12, shorts: bool = False) -> list[dict]:
    """유튜브 검색(한국어 제목). shorts=True 면 '4분 이하' 필터 검색 — 그냥 검색은 긴 영상만 줬다(10-21 선우용여 눈 세정 티슈 10편 모두 20분대)."""
    from urllib.parse import quote
    seen: dict[str, dict] = {}
    for q in qs[:10]:
        src = (f"https://www.youtube.com/results?search_query={quote(q)}&sp=EgIYAQ%253D%253D" if shorts else f"ytsearch{n}:{q}")
        r = ytdlp(["--flat-playlist", "-J", "--playlist-end", str(n), src], timeout=180)
        if r.returncode != 0 or not r.stdout.strip():
            continue
        for e in json.loads(r.stdout).get("entries") or []:
            if e.get("id") and e["id"] not in seen:
                seen[e["id"]] = {"id": e["id"], "title": e.get("title"), "channel": e.get("channel") or e.get("uploader"), "dur": e.get("duration"),
                                 "views": e.get("view_count"), "q": q, "channel_id": e.get("channel_id")}
    return list(seen.values())


PEER_READ = """너는 출처 글자 읽기 담당이다. 같은 연예인·제품을 다룬 **다른 채널 쇼츠**들의 장면 모음이다(쇼츠마다 한 줄, 왼쪽에 번호).
화면 위·아래의 '출처: ○○' 글자, 방송 로고·프로그램 이름을 그대로 읽어라. 안 보이면 빈 값. 지어내지 마라.
JSON 하나: {"labels": [{"n": 번호, "source": "출처 글자 그대로 또는 ''", "program": "방송·채널 이름 또는 ''"}]}"""
PEER_N = 5            # 출처를 읽을 남의 쇼츠 수(360p 로 앞 20초만 받는다)


def _peer_labels(P: Piece, r: dict) -> list[str]:
    """같은 연예인+제품을 다룬 다른 사람 쇼츠의 '출처:' 글자 → 원본 검색 단서(사장님 10-21 "이렇게 치면 다른 사람이 만든 영상에 원본 출처가 나온다 / 그걸 활용").
    그 쇼츠 영상은 재료로 쓰지 않는다(출처 읽기만 — 다른 채널 연예인 영상 금지)."""
    from PIL import Image, ImageDraw
    celeb = str(r.get("celeb") or "")
    if not celeb or celeb == "불명":
        return []
    words = [w for w in r.get("product_words") or [] if w][:2] or [""]
    found = _search([f"{celeb} {w}".strip() for w in words], n=10, shorts=True)
    bench = str((P.s.get("bench") or {}).get("id") or "")
    shorts = [c for c in found if c["id"] != bench and 0 < (c.get("dur") or 0) <= 75][:PEER_N]
    pd = P.W / "peer"; pd.mkdir(exist_ok=True)
    rows = []
    for i, c in enumerate(shorts, 1):
        mp4 = pd / f"{c['id']}.mp4"
        if not mp4.exists():
            ytdlp(["-f", "worst[height>=360][ext=mp4]/worst[ext=mp4]/worst", "--download-sections", "*0-20", "-o", str(mp4),
                   f"https://www.youtube.com/watch?v={c['id']}"], timeout=180)
        if not mp4.exists():
            continue
        tiles = []
        for t in (1.5, 6.0, 12.0):
            f = pd / f"{c['id']}_{t}.jpg"
            try:
                frame(mp4, t, f)
                im = Image.open(f).convert("RGB"); im.thumbnail((200, 360)); tiles.append(im)
            except Exception:  # noqa: BLE001 — 짧은 쇼츠는 뒤 장면이 없을 수 있다
                pass
        if tiles:
            row = Image.new("RGB", (40 + 200 * len(tiles), 360), (0, 0, 0))
            ImageDraw.Draw(row).text((8, 170), str(i), fill=(255, 255, 0))
            for k, im in enumerate(tiles):
                row.paste(im, (40 + 200 * k, 0))
            rows.append(row)
    if not rows:
        return []
    sh = Image.new("RGB", (max(x.width for x in rows), 360 * len(rows)), (0, 0, 0))
    for k, row in enumerate(rows):
        sh.paste(row, (0, 360 * k))
    sp = pd / "peer_sheet.jpg"; sh.save(sp, quality=85)
    a = ask("origin_peer", PEER_READ + f"\n\n연예인: {celeb}", [img(sp)], need=("labels",))
    out = []
    for x in a.get("labels") or []:
        for k in ("source", "program"):
            v = re.sub(r"^\s*출처\s*[:：]?\s*", "", str(x.get(k) or "")).strip()
            if v and v not in out:
                out.append(v)
    P.s["origin_peer"] = out; P.save()
    return out


def st_origin(P: Piece):
    bd = P.W / "bench"
    B = P.s["bench"]
    lines = jload(bd / "asr.json")
    r = ask("origin_read", ORIGIN_READ + "\n\n제목: " + str(B.get("title")) + "\n채널: " + str(B.get("channel")) + "\n설명: " + str(B.get("desc")) +
            "\n받아쓰기: " + " / ".join(l["text"] for l in lines)[:3000], [img(bd / "sheet.jpg")], need=("celeb", "queries", "is_shopping"))
    if not r.get("is_shopping"):
        raise Stop("연예인이 쓰는 물건이 나오는 영상이 아닙니다", "연예인 쇼핑 쇼츠 주소를 주세요")
    P.s["origin_read"] = r; P.save()
    label = re.sub(r"^\s*출처\s*[:：]?\s*", "", r.get("source_label") or "").strip()
    name = str(r["celeb"]) if r.get("celeb") and r["celeb"] != "불명" else ""
    # 고정 검색어를 늘 먼저 — AI 가 판마다 검색어를 새로 지어 같은 영상인데 원본이 걸렸다 안 걸렸다 했다(10-21 선우용여 2판 걸림·3판 빠짐)
    fixed = [name, f"{name} {label}".strip(), f"{name} 꿀템"] if name else []
    qs = [q for q in fixed + ([label] if label else []) + [q for q in r.get("queries") or [] if q] +
          ([r["channel_hint"]] if r.get("channel_hint") else []) if q]                               # 이름만 검색 = 본인 채널 찾기
    qs = list(dict.fromkeys(qs))
    peers = [p for p in _peer_labels(P, r) if _norm(p) not in _norm(label)]      # 남의 쇼츠가 적은 출처(우리 벤치와 다른 것만 더한다)
    if peers:
        r["channel_hint"] = " / ".join([r.get("channel_hint") or ""] + peers)
        qs = qs[:3] + [f"{name} {p}".strip() for p in peers[:2]] + qs[3:]
    found = _search(qs)
    celeb = _norm(r.get("celeb") or "")
    own = lambda c: len(celeb) >= 2 and celeb in _norm(c.get("channel") or "")
    cands = [c for c in found if c["id"] != B.get("id") and (c.get("dur") or 0) > (B.get("dur") or 0) + 20]
    # 연예인 이름이 제목에 있는 검색 결과가 앞(10-21 선우용여: 원본 'What's in 용여 가방'이 검색에 나왔는데 채널 목록 후보에 밀려 대조도 못 했다)
    hint = _norm((r.get("source_label") or "").replace("출처", "") + (r.get("channel_hint") or ""))
    cands.sort(key=lambda c: (not own(c), (celeb[-2:] not in _norm(c.get("title") or "")) if celeb else 0,
                              not (_norm(c.get("channel") or "") and _norm(c.get("channel") or "") in hint)))   # 출처 채널 영상도 앞
    # 제작순서 02 §3 — 본인 유튜브면 **채널 영상 목록**에서 찾는다(10-21 실측: 이미도 원본 '[미도주방] 찐 살림템'은 검색 15편 어디에도 없었다)
    ch_ids = _channels_of(found, r)
    titles = []
    for cid in ch_ids[:3]:
        lr = ytdlp(["--flat-playlist", "-J", "--playlist-end", "300", f"https://www.youtube.com/channel/{cid}/videos"], timeout=240)
        if lr.returncode == 0 and lr.stdout.strip():
            titles += [{"id": e["id"], "title": e.get("title"), "dur": e.get("duration")} for e in json.loads(lr.stdout).get("entries") or [] if e.get("id")]
    ids: list[str] = []
    for k in range(0, len(titles), TITLE_CHUNK):     # 한 묶음씩 '아이디<TAB>제목' 한 줄 — 10-21 300편 통째 JSON = 4.2만 자 질문
        part = titles[k:k + TITLE_CHUNK]
        pick = ask("origin_titles", ORIGIN_TITLES + f"\n\n벤치 제목: {B.get('title')}\n제품 낱말: {r.get('product_words')}\n채널 영상 목록(아이디\t제목):\n" +
                   "\n".join(f"{t['id']}\t{str(t.get('title') or '')[:80]}" for t in part), need=("ids",))
        ids += [i for i in pick.get("ids") or [] if any(t["id"] == i for t in part) and i not in ids][:8]
    picked = [t for t in titles if t["id"] in ids]
    # 검색 후보와 채널 목록 후보를 번갈아 — 어느 한쪽이 대조 자리를 다 차지하지 않게
    mixed, seen = [], set()
    for k in range(max(len(cands), len(picked))):
        for c in (cands[k] if k < len(cands) else None, picked[k] if k < len(picked) else None):
            if c and c["id"] not in seen:
                seen.add(c["id"]); mixed.append(c)
    cands = mixed
    od = P.W / "origin"; od.mkdir(exist_ok=True)
    from tools.calcopy.yanshot.common import vtt_words
    scored = []
    for c in cands[:ORIGIN_TRY]:
        ytdlp(["--skip-download", "--write-auto-subs", "--sub-langs", "ko-orig,ko", "-o", str(od / f"{c['id']}.%(ext)s"), f"https://www.youtube.com/watch?v={c['id']}"],
              timeout=180)
        vtt = next(iter(sorted(od.glob(f"{c['id']}*.ko-orig.vtt")) + sorted(od.glob(f"{c['id']}*.ko.vtt"))), None)   # 원래 말(ko-orig) 먼저
        if not vtt:
            continue
        m = fingerprint(lines, vtt_words(vtt))
        if m:
            scored.append({**c, "matched": m})
    scored.sort(key=lambda c: -len(c["matched"]))
    if not scored:
        raise Stop("원본 영상을 찾지 못했습니다", "연예인 본인 원본 영상(유튜브) 주소를 알려 주세요")
    pick = ask("origin_pick", ORIGIN_PICK + "\n\n후보:\n" + json.dumps(scored[:5], ensure_ascii=False, indent=1), [img(bd / "sheet.jpg")],
               need=("origin_id", "self_spoken"))
    if not pick.get("origin_id") or not pick.get("self_spoken"):
        raise Stop("연예인 본인이 말한 원본을 확정하지 못했습니다", "연예인 본인 원본 영상(유튜브) 주소를 알려 주세요")
    oid = pick["origin_id"]
    ts = [m["origin_t"] for m in pick.get("matched") or [] if isinstance(m.get("origin_t"), (int, float))]
    a, b = (max(0, min(ts) - 90), max(ts) + 90) if ts else (None, None)
    from tools.calcopy.hybrid import screen
    files = screen.download(P.W, [oid], [(a, b)] if ts else None, prefix="")
    P.s["origin"] = {"id": oid, "url": f"https://www.youtube.com/watch?v={oid}", "matched": pick.get("matched"), "files": [str(f) for f in files],
                     "info": next((c for c in scored if c["id"] == oid), {}), "window": [a, b]}
    if files and ts:
        P.s["origin"]["offset"] = origin_offset(P, Path(files[-1]), a or 0.0)
    P.mark("origin", offset=P.s["origin"].get("offset"))


def origin_offset(P: Piece, src: Path, guess: float) -> float:
    """받은 원본 파일 0초 = 원본 몇 초인가 — **잰다**(판단 주인). 구간 받기는 조각 단위로 잘려 요청보다 앞에서 시작한다
    (10-21 선우용여: 요청 360.5초 → 실제 약 340초, 파일 231초 vs 요청 191초) → 그 차이만큼 원음 줄이 엉뚱한 말을 틀었다.
    방법: 벤치 말이 맞은 자리 근처를 받아쓰고, 그 말이 원본 자동자막 몇 초에 있나 대조 → (원본 초 − 파일 초)의 가운데 값."""
    from statistics import median
    from tools.calcopy.yanshot.common import vtt_words
    O = P.s["origin"]
    vtt = next(iter(sorted((P.W / "origin").glob(f"{O['id']}*.ko-orig.vtt")) + sorted((P.W / "origin").glob(f"{O['id']}*.ko.vtt"))), None)
    ts = [float(m["origin_t"]) for m in O.get("matched") or [] if isinstance(m.get("origin_t"), (int, float))]
    if not vtt or not ts:
        return guess
    words = vtt_words(vtt)
    f0 = max(0.0, min(ts) - guess - 45)
    wav = P.W / "origin" / "offset.wav"
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{f0:.2f}", "-t", "90", "-i", str(src), "-ac", "1", "-ar", "16000", str(wav)])
    diffs = []
    for seg in whisper(wav):
        m = fingerprint([seg], words)
        if m:
            diffs.append(m[0]["origin_t"] - (f0 + float(seg["t0"])))
    if len(diffs) < 2:
        return guess
    off = round(median(diffs), 2)
    P.s.setdefault("origin_offset_log", {}).update(guess=guess, measured=off, n=len(diffs))
    return off


def origin_t0(P: Piece) -> float:
    """받은 원본 파일 0초의 원본 초 — 잰 offset, 없으면 요청 구간 시작."""
    O = P.s.get("origin") or {}
    off = O.get("offset")
    return float(off if off is not None else (O.get("window") or [0])[0] or 0)


def file_t(P: Piece, origin_t: float) -> float:
    """원본 초 → 받은 파일 초(잰 offset 기준, 없으면 요청 구간 시작)."""
    O = P.s.get("origin") or {}
    off = O.get("offset")
    return float(origin_t) - float(off if off is not None else (O.get("window") or [0])[0] or 0)


PRODUCT_PICK = """너는 제품 특정 담당이다(제작 순서 03). 원본 영상 장면 시트에서 연예인이 쓰는 그 제품의 **전체 모양**이 보이는 장면을 2~4개 골라라
(포장 라벨·로고가 보이는 장면이 최고, 너무 작게 부분만 자르지 않는다). 시트는 1초 간격, 왼쪽 위부터 0초(시트 시작 초는 아래 적힘).
JSON 하나: {"scenes": [{"t": 원본 초, "crop": [x, y, w, h]  (원본 영상 픽셀)}], "brand_words": ["원본 대사·화면에 나온 브랜드·제품 이름"], "coupang_queries": ["쿠팡 검색어 2~4개"]}"""

PRODUCT_SAME = """너는 같은 제품 판정 담당이다(제작 순서 03 §4 — 사장님 10-21 "쿠팡에서 정확한 거"). 원본 장면 사진과 쿠팡 후보(이름·대표 이미지)를 대조해
포장·로고·모양·색이 **같은 제품**인 후보 하나를 골라라. 비슷한 제품 대체 금지. 없으면 product_id ''.
JSON 하나: {"product_id": "쿠팡 상품번호 또는 ''", "name": "정식 제품명(브랜드·모델·색)", "why": "대조 근거 한 줄", "category": "화장품|식품|생활|의약품|의료기기|기타"}"""


def coupang_chrome(queries: list[str], out: Path) -> dict:
    """회원 파트너스 키가 없을 때(사장님 10-21) — 회원 PC 크롬 창(화면 뜸, 쿠팡은 헤드리스를 막는다)으로 검색 결과 카드만 읽는다."""
    # 동선·추출·파싱 = 서비스 크롤러(shopping_shorts/coupang_search) 그대로 — 홈 먼저 → 검색 → 상품 칸 기다림 → _EXTRACT_JS → parse_items
    #   (10-21 실측: 이것 없이 검색 주소로 바로 가니 0개)
    from playwright.sync_api import sync_playwright
    from shopping_shorts import coupang_partners as cp, coupang_search as cs
    res = {}
    prof = Path(os.environ.get("SHORTEM_HOME") or (base() / "_home")) / "browser" / "coupang"
    prof.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(prof), headless=False, channel="chrome", locale="ko-KR", viewport={"width": 1366, "height": 900},
                                                   args=["--disable-blink-features=AutomationControlled"])
        try:
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                pg.goto("https://www.coupang.com/", wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(900)
            except Exception:  # noqa: BLE001 — 홈이 늦어도 검색은 해 본다
                pass
            for q in queries[:4]:
                pg.goto(cp.search_url(q), wait_until="domcontentloaded", timeout=30000)
                try:
                    pg.wait_for_selector("li[class*=ProductUnit_productUnit]", timeout=15000)
                except Exception:  # noqa: BLE001
                    pass
                items = cs.parse_items(pg.evaluate(cs._EXTRACT_JS, 12), limit=12)
                res[q] = {"ok": bool(items), "items": items, **({} if items else {"notice": pg.inner_text("body")[:200]})}
                pg.wait_for_timeout(1500)                     # 몰아치면 쿠팡이 잠시 막는다(서비스 크롤러 실측)
        finally:
            ctx.close()
    jsave(out, res)
    return res


PRODUCT_NAMED = """너는 같은 제품 판정 담당이다(원본 화면에 상표가 안 보여 포털·유튜브 글로 제품 이름을 찾은 경우). 찾은 이름과 근거(블로그·기사·본인 채널 글)를 보고
쿠팡 후보 중 그 이름(브랜드·제품명)과 **같은 제품** 하나를 골라라. 근거가 '그 연예인이 쓴 그 제품'을 가리키지 않으면 고르지 마라. 없으면 product_id ''.
JSON 하나: {"product_id": "…", "name": "…", "why": "근거 한 줄(어느 글에 무엇이라고)", "category": "화장품|생활용품|식품|의류|의약품|의료기기|기타"}"""

PRODUCT_BEST = """너는 대체 제품 고르기 담당이다(사장님 10-21: 같은 제품이 없으면 쿠팡에서 후기 많고 제일 좋은 제품). 연예인이 쓴 것과 **같은 종류·같은 쓰임**인 쿠팡 후보 중
후기(rating 의 괄호 숫자) 많고 별점 높은 것 하나를 골라라. 광고(is_ad)·묶음 이상한 것은 뒤로. 같은 종류가 없으면 product_id ''.
JSON 하나: {"product_id": "…", "name": "…", "why": "고른 이유 한 줄(후기 수·별점)", "category": "화장품|생활용품|식품|의류|의약품|의료기기|기타"}"""

NAME_FIND = """너는 제품 이름 찾기 담당이다. 연예인이 방송·유튜브에서 쓴 제품의 이름을 포털(네이버)·유튜브 검색 글에서 찾아라.
그 연예인이 쓴 바로 그 제품을 가리키는 글만 근거다(다른 연예인·다른 제품 글 금지). 지어내지 마라. 못 찾으면 names 빈 목록.
JSON 하나: {"names": [{"name": "브랜드 제품명", "evidence": "글 그대로 한 줄", "where": "블로그|뉴스|유튜브 제목|본인 채널"}], "kind": "제품 종류 한 줄(예: 눈가 세정 티슈)"}"""


def _naver_text(q: str, limit: int = 2500) -> str:
    """네이버 통합검색 글(연예인 이름 앞뒤만) — 회원 PC 에서 바로 연다(키 없음)."""
    import html as H
    import urllib.parse
    import urllib.request
    try:
        req = urllib.request.Request("https://search.naver.com/search.naver?query=" + urllib.parse.quote(q),
                                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36", "Accept-Language": "ko"})
        t = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — 포털이 막혀도 유튜브 글로 이어 간다(이유는 남긴다)
        return f"(네이버 검색 실패: {type(e).__name__})"
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", t)
    t = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t)))
    key = q.split()[0]
    out, last = [], -1
    for m in re.finditer(re.escape(key), t):
        if m.start() < last:
            continue
        out.append(t[max(0, m.start() - 80):m.start() + 220]); last = m.start() + 220
    return " … ".join(out)[:limit]


def _name_hints(P: Piece, r: dict) -> dict:
    celeb = str(r.get("celeb") or "")
    words = [w for w in (r.get("product_words") or []) if w][:3]
    if not celeb or celeb == "불명" or not words:
        return {}
    qs = [f"{celeb} {w}" for w in words]
    texts = [f"[네이버 {q}] {_naver_text(q)}" for q in qs]
    yt = _search(qs, n=8)
    texts.append("[유튜브 제목] " + " / ".join(f"{c.get('channel')}: {c.get('title')}" for c in yt)[:3000])
    a = ask("product_name", NAME_FIND + f"\n\n연예인: {celeb}\n제품 낱말: {words}\n\n" + "\n\n".join(texts), need=("names",))
    P.s["product_name_find"] = a; P.save()
    return a


def st_product(P: Piece):
    O = P.s["origin"]
    src = Path(O["files"][-1]) if O.get("files") else None
    if not src or not src.exists():
        raise StageError("원본 영상 파일이 없다")
    ld = P.W / "look"; ld.mkdir(exist_ok=True)
    a = float(origin_t0(P))
    # 벤치 말이 맞은 원본 시각 근처만 본다(10-21 실측: 받은 구간 전체 시트를 주자 주방 도구 영상 앞머리의 식칼을 골랐다)
    ts = [float(m["origin_t"]) - a for m in O.get("matched") or [] if isinstance(m.get("origin_t"), (int, float))]
    s0 = max(0.0, (min(ts) if ts else 0) - 25)
    sh = sheet(src, ld / "origin_sheet.jpg", fps=1, cols=6, rows=6, w=320, ss=s0, t=36)
    R0 = P.s.get("origin_read") or {}
    r = ask("product_pick", PRODUCT_PICK + f"\n\n첫 그림 = 원본 파일 {s0:.0f}초부터 1초 간격(왼쪽 위부터) — 답의 t 는 **파일 초**({s0:.0f} + 칸 번호).\n"
            f"둘째 그림 = 벤치 쇼츠 1초 시트(그 제품이 무엇인지 보여 준다). 벤치·원본 대사의 제품 낱말: {R0.get('product_words')}\n"
            f"벤치 말과 원본이 맞은 원본 초: {[m.get('origin_t') for m in O.get('matched') or []]}",
            [img(sh), img(P.W / "bench" / "sheet.jpg")], need=("scenes", "coupang_queries"))
    shots = []
    for i, s in enumerate(r.get("scenes") or []):
        try:
            shots.append(frame(src, float(s["t"]), ld / f"p{i + 1}.jpg", s.get("crop")))
        except Exception:  # noqa: BLE001 — 자르기 실패한 장면은 빼고 나머지로
            continue
    if not shots:
        raise Stop("제품이 보이는 장면을 찾지 못했습니다", "")
    from tools.calcopy import coupang_customer as C
    qs = [q for q in r.get("coupang_queries") or [] if q][:4] + [w for w in r.get("brand_words") or [] if w][:2]
    found = C.search(qs)
    if any((v or {}).get("need") == "chrome" for v in found.values()):
        found = coupang_chrome(qs, ld / "coupang.json")
    jsave(ld / "coupang.json", found)
    cands = [it for v in found.values() for it in (v or {}).get("items", [])][:16]
    if not cands:
        raise Stop("쿠팡에서 같은 제품을 찾지 못했습니다", "")
    same = ask("product_same", PRODUCT_SAME + "\n\n쿠팡 후보:\n" + json.dumps(cands, ensure_ascii=False, indent=1), [img(x) for x in shots],
               need=("product_id", "name", "category"))
    mode, hint = "exact", {}
    if not same.get("product_id"):
        # 사장님 10-21: 정확한 상품이 없으면 '연예인 + 제품 낱말'로 포털·유튜브를 다시 검색해 제품 이름을 찾고,
        #   그래도 없으면 쿠팡에서 같은 종류 중 후기 많고 제일 좋은 제품 — 대본은 '같은 건 없어서 후기 많은 걸로 써 봤다'
        hint = _name_hints(P, R0)                      # 연예인·제품 낱말 = 원본 단서 읽기 답(R0)
        named = [n["name"] for n in hint.get("names") or [] if n.get("name")][:3]
        if named:
            f2 = C.search(named)
            if any((v or {}).get("need") == "chrome" for v in f2.values()):
                f2 = coupang_chrome(named, ld / "coupang_named.json")
            c2 = [it for v in f2.values() for it in (v or {}).get("items", [])][:16]
            if c2:
                same = ask("product_named", PRODUCT_NAMED + "\n\n찾은 제품 이름·근거:\n" + json.dumps(hint.get("names"), ensure_ascii=False, indent=1) +
                           "\n\n쿠팡 후보:\n" + json.dumps(c2, ensure_ascii=False, indent=1), [img(x) for x in shots], need=("product_id", "name", "category"))
                mode, cands = "named", c2
        if not same.get("product_id"):
            same = ask("product_best", PRODUCT_BEST + f"\n\n연예인이 쓴 것: {hint.get('kind') or r.get('brand_words')}\n\n쿠팡 후보:\n" +
                       json.dumps(cands, ensure_ascii=False, indent=1), [img(x) for x in shots], need=("product_id", "name", "category"))
            mode = "alt"
    if not same.get("product_id"):
        raise Stop("쿠팡에서 같은 종류 제품을 찾지 못했습니다", "")
    if same.get("category") in ("의약품", "의료기기"):
        raise Stop("의약품·의료기기는 만들 수 없는 소재입니다", "다른 소재 영상을 주세요")
    P.s["product"] = {**same, "mode": mode, "name_hints": hint.get("names") or [], "brand_words": r.get("brand_words"), "shots": [str(x) for x in shots]}
    P.mark("product", mode=mode)


RESEARCH = """너는 조사 담당이다. 아래 제작 순서 04(조사)·브리프(research)의 기준 그대로 `조사.md` 한 파일 내용을 써라. 필요하면 웹 검색으로 사실을 확인하고 출처 URL 을 적는다.
지어내기 금지·수치 어림 금지·원본에 없는 말을 본인 말로 적기 금지. 멈출 이유(전문의약품·의료기기 효능 등)가 있으면 stop 에 적는다.
원본 자동자막(원본 초·말)과 벤치 지문 대조, 제품 판정 결과가 아래에 있다.
JSON 하나: {"stop": "" , "조사_md": "마크다운 전문(0 결론 ~ 6 확인 못 한 것)", "keywords": ["제품명", "영문명", "모델"], "queries": ["재료 영상 유튜브 검색어 5~8개"],
 "exclude": ["모음", "TOP", "가성비"], "spans": [{"a": 원본 파일 초, "b": 초, "tag": "O1"}], "facts": [{"id": "f1", "fact": "…", "src": "URL 또는 '원본 n초'"}]}"""


def st_research(P: Piece):
    from tools.calcopy.yanshot.common import vtt_words
    O, PR = P.s["origin"], P.s["product"]
    vtt = next((P.W / "origin").glob(f"{O['id']}*.ko.vtt"), None)
    words = vtt_words(vtt) if vtt else []
    a = origin_t0(P)
    b = a + (_dur(Path(O["files"][-1])) or 0) if O.get("files") else None
    near = [(round(t, 1), w) for t, w in words if b is None or (a <= t <= b)]
    txt = " ".join(f"[{t}]{w}" for t, w in near)[:9000]
    r = ask("research", RESEARCH + "\n\n" + brief_text("channel/칼카피_제작순서/04_조사.md", "tools/calcopy/hybrid/briefs/research.md") +
            f"\n\n## 원본\n{O['url']} (받은 파일 0초 = 원본 {a:.2f}초 — 잰 값. spans 는 파일 초 = 원본 초 − {a:.2f})\n지문 대조: {json.dumps(O.get('matched'), ensure_ascii=False)}\n"
            f"자동자막(원본 초):\n{txt}\n\n## 제품\n{json.dumps(PR, ensure_ascii=False)}",
            [img(Path(x)) for x in PR.get("shots", [])[:3]], need=("조사_md", "keywords", "queries", "spans"))
    if r.get("stop"):
        raise Stop(str(r["stop"])[:200], "다른 소재 영상을 주세요")
    (P.D / "조사").mkdir(parents=True, exist_ok=True)
    (P.D / "조사" / "조사.md").write_text(r["조사_md"], encoding="utf-8")
    P.s["research"] = {k: r.get(k) for k in ("keywords", "queries", "exclude", "spans", "facts")}
    P.mark("research")


SCREEN_PICK = """너는 제품 영상 고르기 담당이다(브리프 screen_pick · 제작 순서 05). 같은 제품만, 1080 이상, 남의 글자가 가운데 상시면 뺀다, 제품 컷이 많은 것 앞으로, 2~4개.
★연예인이 나오는 영상은 찾은 원본(연예인 본인 채널·방송사 공식)에서만 쓴다 — 다른 채널(벤치 쇼츠·재편집·리뷰)에 나온 연예인 영상은 절대 금지(사장님 10-21). 후보에 그 연예인이 나오면 rejected.
각 후보의 360p 토막 시트(키워드 구간)와 메타가 있다.
JSON 하나: {"chosen": [{"id": "…", "why": "…", "sections": [[a, b]]}], "rejected": [{"id": "…", "why": "…"}]}"""


def st_material(P: Piece):
    from tools.calcopy.hybrid import screen
    R = P.s["research"]
    screen.search(P.W, R.get("queries") or [], n=10, exclude=R.get("exclude"), server=False)
    sj = screen.screen(P.W, R.get("keywords") or [], top=8)
    rows = sj.get("rows") or []
    sheets = [P.W / "screen" / f"{x['id']}_sheet.jpg" for x in rows if (P.W / "screen" / f"{x['id']}_sheet.jpg").exists()][:8]
    meta = [{k: x.get(k) for k in ("id", "title", "channel", "max_height", "dur", "hits", "score")} for x in rows][:8]
    r = ask("screen_pick", SCREEN_PICK + "\n\n후보(시트 순서와 같다):\n" + json.dumps(meta, ensure_ascii=False, indent=1) +
            f"\n\n제품: {P.s['product'].get('name')}", [img(s) for s in sheets], need=("chosen",))
    sp = P.W / "screen.json"
    d = jload(sp) if sp.exists() else {}
    d.update(chosen=r.get("chosen") or [], rejected=r.get("rejected") or [])
    jsave(sp, d)
    files = []
    for c in d["chosen"]:
        secs = [tuple(s) for s in c.get("sections") or []] or None
        files += screen.download(P.W, [c["id"]], secs, prefix="")
    P.s["material"] = {"files": [str(f) for f in files]}
    P.mark("material")


def st_asr(P: Piece):
    O = P.s["origin"]
    src = Path(O["files"][-1])
    out = []
    ad = P.W / "asr"; ad.mkdir(exist_ok=True)
    for s in P.s["research"].get("spans") or []:
        wav = ad / f"{s.get('tag', 'O')}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{float(s['a']):.2f}", "-to", f"{float(s['b']):.2f}", "-i", str(src), "-ac", "1", "-ar", "16000", str(wav)])
        out.append({**s, "src": src.name, "heard": " ".join(x["text"] for x in whisper(wav))})
    jsave(ad / "result.json", {"spans": out, "engine": "whisper"})
    P.mark("asr", n=len(out))


SCRIPT = """너는 대본 작가다(오푸스). 아래 판 규칙(styles brief)·브리프(script)·제작 순서 07 기준 그대로 이 편의 `대본.json`·`재료.json`·`근거.md` 를 써라.
꼴은 렌더러 설명(render_bench docstring)과 같다. 대본 검사(script_audit)를 통과해야 한다 — 통과 못 한 이유가 아래에 있으면 고쳐서 다시.
원음 줄(kind orig)의 src 는 원본 파일 이름, spans 는 그 파일 초. 원음 자막(caps_rel)은 받아쓰기 오류를 문맥으로 바로잡아 적는다(10-21 선우용여: 자동자막·위스퍼 둘 다 '눈곱'을 '눈꽃'으로). 재료.json 의 cand_dir 는 비워 둔다(엔진이 채운다), 컷 src 는 재료 파일 이름.
JSON 하나: {"대본": {…}, "재료": {"cuts": {…}}, "근거_md": "…"}"""


PRODUCT_TALK = {   # 제품을 어떻게 찾았나 → 대본이 제품을 말하는 법(사장님 10-21)
    "exact": "원본 화면의 포장과 같은 제품이다 — '○○가 쓰는 그 제품'으로 말해도 된다.",
    "named": "원본 화면엔 상표가 안 보여 포털·유튜브 글로 이름을 찾았다 — 근거 글이 가리키는 만큼만 말한다(지어 붙이지 않는다).",
    "alt": ("같은 제품을 못 찾아 쿠팡에서 같은 종류 중 후기 많고 좋은 제품을 골랐다. ★대본에 이 사실을 말한다 — 예: '영상 보고 쿠팡에서 찾아봤는데 똑같은 건 없어서 "
            "후기 제일 많은 걸로 써 봤는데 좋더라'. ★이 제품을 연예인이 쓴다고 말하지 마라(연예인이 쓴 건 '이런 ○○'까지만)."),
}


def st_script(P: Piece, version: str, fail: str = ""):
    from tools.calcopy.hybrid import render_bench, script_audit, styles as STY
    vd = P.D / version; vd.mkdir(parents=True, exist_ok=True)
    mats = [Path(f) for f in P.s["material"]["files"]] + [Path(f) for f in P.s["origin"]["files"]]
    mat_list = [{"file": m.name, "dur": _dur(m)} for m in mats if m.exists()]
    sheets = []
    for m in mats[:5]:
        if m.exists():
            sheets.append(sheet(m, P.W / f"_sheet_{m.stem[:40]}.jpg", fps=0.5, cols=6, rows=5, w=240))
    ctx = (STY.brief(version) + "\n\n" + brief_text("tools/calcopy/hybrid/briefs/script.md", "channel/칼카피_제작순서/07_대본.md") +
           "\n\n## 렌더러 꼴\n" + (render_bench.__doc__ or "") + "\n\n## 조사.md\n" + (P.D / "조사" / "조사.md").read_text(encoding="utf-8") +
           "\n\n## 제품 판정\n" + PRODUCT_TALK.get((P.s.get("product") or {}).get("mode") or "exact", "") +
           "\n" + json.dumps({k: (P.s.get("product") or {}).get(k) for k in ("name", "why", "mode", "name_hints")}, ensure_ascii=False) +
           "\n\n## 원음 받아쓰기\n" + json.dumps(jload(P.W / "asr" / "result.json"), ensure_ascii=False) +
           "\n\n## 재료 파일(시트 순서 = 앞 5개)\n" + json.dumps(mat_list, ensure_ascii=False) + _shots_ctx(P) +
           (f"\n\n## 지난 검사에서 걸린 것\n{fail}" if fail else ""))
    for attempt in range(3):
        r = ask(f"script_{version}", SCRIPT + "\n\n" + ctx, [img(s) for s in sheets], need=("대본", "재료"))
        S, M = r["대본"], r["재료"]
        M["cand_dir"] = str(P.W / "src")
        fill_shot_max(P, M, _ar(version), S)
        jsave(vd / "대본.json", S); jsave(vd / "재료.json", M)
        (vd / "근거.md").write_text(r.get("근거_md") or "", encoding="utf-8")
        a = script_audit.audit(vd / "대본.json", version)
        bad_title = _title_colors_bad(S, STY.load(version))
        if bad_title:
            a = {**a, "ok": False, "title": bad_title}
        bad_src = source_rule_bad(P, M)
        if bad_src:
            a = {**a, "ok": False, "source_rule": bad_src}
        bad_caps = _caps_vs_tts(S)
        if bad_caps:
            a = {**a, "ok": False, "caps_vs_tts": bad_caps}
        bad_heard = _orig_heard_bad(P, S)
        if bad_heard:
            a = {**a, "ok": False, "orig_heard": bad_heard}
        if a.get("ok"):
            P.mark("script", version=version, tries=attempt + 1)
            return S
        ctx += "\n\n## 대본 검사에서 걸린 것(고쳐라)\n" + json.dumps(a, ensure_ascii=False)[:4000]
    raise StageError("대본 검사를 세 번 통과하지 못했다")


HEARD_MIN = 0.6       # 원음 줄 자막 ↔ 그 구간 받아쓰기 닮음 최소(10-21 선우용여: 맞는 줄 0.8+, 어긋난 줄 0.3~0.5)


def _orig_heard_bad(P: Piece, S: dict) -> list[str]:
    """원음 줄마다 그 구간을 **실제로 받아써** 자막과 대조 — 집 PC 워커가 귀로 하던 확인(10-21 선우용여: 자막 '나이 드시면 눈곱까지 껴'
    구간에 '눈곱까지 껴줘'만 들림 / 다른 출연자 말이 섞임). 다르면 앞뒤 3초 받아쓰기(파일 초)를 붙여 대본이 구간을 다시 잡게 한다."""
    out = []
    src_of = {Path(f).name: Path(f) for f in (P.s.get("origin") or {}).get("files") or []}
    ad = P.W / "asr"; ad.mkdir(exist_ok=True)
    for l in S.get("lines") or []:
        if l.get("kind") != "orig" or not l.get("spans"):
            continue
        src = src_of.get(str(l.get("src") or ""))
        if not src:
            continue
        a, b = float(l["spans"][0][0]), float(l["spans"][-1][1])
        cap = _norm("".join(str(c[0]) for c in l.get("caps_rel") or []))
        w = ad / f"chk_{l['id']}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.2f}", "-to", f"{b:.2f}", "-i", str(src), "-ac", "1", "-ar", "16000", str(w)])
        heard = " ".join(s["text"] for s in whisper(w))
        r = difflib.SequenceMatcher(None, cap, _norm(heard)).ratio() if cap else 1.0
        if r < HEARD_MIN:
            wide = ad / f"chk_{l['id']}_wide.wav"
            w0 = max(0.0, a - 3)
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{w0:.2f}", "-to", f"{b + 3:.2f}", "-i", str(src), "-ac", "1", "-ar", "16000", str(wide)])
            near = " / ".join(f"{w0 + float(s['t0']):.2f}~{w0 + float(s['t1']):.2f} {s['text']}" for s in whisper(wide))
            out.append(f"{l['id']}: 자막 '{' '.join(str(c[0]) for c in l.get('caps_rel') or [])}' 인데 {a:.2f}~{b:.2f}초에 실제로 들리는 말은 '{heard}'(닮음 {r:.2f}). "
                       f"앞뒤 받아쓰기(파일 초): {near} — 구간을 그 말이 들리는 자리로 옮기고, 다른 출연자 말이 섞이면 빼라")
    return out


def _caps_vs_tts(S: dict) -> list[str]:
    """나레 줄마다 화면 자막(caps 이어 붙인 글)이 실제로 읽는 글(tts)과 같은가 — 부호·띄어쓰기만 다른 건 같다
    (10-21 선우용여 N3: 자막 '따라 사 봤는데요' ↔ 목소리 '하나 사서 따라 해 봤는데요' — 완성본 눈 검수가 짚었다)."""
    out = []
    for l in S.get("lines") or []:
        if l.get("kind") != "tts" or not l.get("caps"):
            continue
        cap = _norm("".join(str((c.get("text") if isinstance(c, dict) else c) or "") for c in l["caps"]))  # 집 PC 옛 대본은 caps 가 글 목록
        shown, say = _norm(str(l.get("text") or "")), _norm(str(l.get("tts") or ""))
        if shown and cap != shown:
            out.append(f"{l.get('id')}: 자막 조각을 이으면 '{cap}' — 화면 글(text) '{shown}' 과 다르다")
        # 읽는 글은 숫자·영문 읽기·이름 발음 때문에 달라도 된다(제작순서 07 §4) — 숫자·영문 없는 줄에서 말이 4자 넘게 늘거나 줄면 결함
        if shown and say and not re.search(r"[0-9A-Za-z%]", str(l.get("text") or "")) and abs(len(say) - len(shown)) >= 4:
            out.append(f"{l.get('id')}: 화면 '{l.get('text')}' ↔ 목소리 '{l.get('tts')}' — 말이 더해지거나 빠졌다(자막은 읽는 말 그대로, 발음 고침만 다르게)")
    return out


def _title_colors_bad(S: dict, st: dict) -> list[str]:
    """제목 줄마다 판 틀(frame.title[줄])에 있는 색만 썼나 — 'hi' 는 그 줄 틀에 hi 가 있을 때만(10-21 실측: 키치잇판 둘째 줄 상자에 hi → 렌더 KeyError)."""
    spec = (st.get("frame") or {}).get("title") or []
    out = []
    for i, line in enumerate(S.get("title_lines") or []):
        sp = spec[i] if i < len(spec) else {}
        for chunk in line if isinstance(line, list) else []:
            c = chunk[1] if isinstance(chunk, list) and len(chunk) > 1 else None
            if c == "hi" and "hi" not in sp:
                out.append(f"제목 {i + 1}줄 '{chunk[0]}' 에 'hi' — 이 판 제목 {i + 1}줄은 강조색이 없다(null 또는 '#hex')")
    if len(S.get("title_lines") or []) > len(spec):
        out.append(f"제목 줄 수 {len(S['title_lines'])} > 판 틀 {len(spec)}줄")
    return out


def _dur(p: Path) -> float | None:
    try:
        from tools.calcopy.hybrid.common import dur_of
        return round(dur_of(p), 2)
    except Exception:  # noqa: BLE001
        return None


PLAN_LOOK = """너는 장면 검수 담당이다(제작 순서 08). 계획 시트를 보고 컷마다: 대사와 화면이 맞나(A3) · 남의 신체 근접(A13) · 남의 글자·원본 자막 띠(A5) ·
0초·훅 = 연예인 얼굴(T1) · A-B-A 끼움.
★연예인이 나오는 영상은 찾은 원본(연예인 본인 채널·방송사 공식)에서만 쓴다 — 다른 채널(벤치 쇼츠·재편집·리뷰)에 나온 연예인 영상은 절대 금지(사장님 10-21). 사람 얼굴 컷(face)은 원본 파일만, 제품 컷도 원본 안 제품 장면이 먼저. 시트 칸 = 렌더러가 실제로 자를 화면 그대로다.
★crop 'face' 는 원본 **높이 전체**를 쓴다 — 원본에 편집 자막·제목 띠가 박혀 있으면 'face' 대신 숫자 crop [x, y, w, h](원본 픽셀, 창 비율 {ar})로
자막·띠 밖을 잘라라(집 PC 예: 1920×1080 원본, 자막 y≈930 → [455, 0, 870, 870]). 고칠 것이 있으면 재료.json 전체를 고쳐서 돌려준다(없으면 null).
JSON 하나: {"ok": true, "problems": ["…"], "재료": null}"""


def plan_sheet(P: Piece, version: str, T: dict) -> Path:
    """계획 시간표의 컷마다 가운데 한 장(크롭 그대로) → 모음 그림 — 렌더 전 눈 확인용(plan_only 는 시간표만 쓴다)."""
    from PIL import Image, ImageDraw
    from tools.calcopy.hybrid import render_bench, styles as STY
    M = jload(P.D / version / "재료.json")
    cand = Path(M.get("cand_dir") or (P.W / "src"))
    _, _, ww, wh = STY.load(version)["frame"]["window"]
    tiles = []
    for i, c in enumerate(T.get("cuts") or []):
        src = cand / str(c.get("src") or "")
        if not src.exists():
            continue
        f = P.W / "_plan" / f"c{i:02d}.jpg"
        f.parent.mkdir(exist_ok=True)
        # 렌더러와 똑같이 자른다(render_bench.render_window) — 'face' = face_crop(높이 전체 → 원본 아래 자막이 들어온다).
        #   10-21 실측: 'face' 컷을 자르지 않은 원본으로 보여 줘 검수가 세 번 다 '자막 띠'를 짚고도 무엇이 렌더될지 몰랐다
        crop = c.get("crop", "face")
        try:
            if crop == "face" and src.suffix.lower() not in render_bench.IMG_EXT:
                crop = render_bench.face_crop(src, float(c.get("ss") or 0) + min(0.5, float(c.get("dur") or 0) / 2), ww / wh)
            crop = crop if isinstance(crop, list) else None
            frame(src, float(c.get("ss") or 0) + min(0.5, float(c.get("dur") or 0) / 2), f, crop)
            im = Image.open(f).convert("RGB")
            im.thumbnail((220, 220))
            d = ImageDraw.Draw(im)
            d.rectangle((0, 0, im.width, 18), fill=(0, 0, 0))
            d.text((3, 2), f"{c.get('line')} {c.get('t0')}~{c.get('t1')}", fill=(255, 255, 0))
            tiles.append(im)
        except Exception:  # noqa: BLE001 — 못 뜬 컷은 시트에서 빠진다(검수가 본다)
            continue
    out = P.W / version / "plan_sheet.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = 6
    sh = Image.new("RGB", (220 * cols, 220 * max(1, -(-len(tiles) // cols))), (20, 20, 20))
    for k, im in enumerate(tiles):
        sh.paste(im, ((k % cols) * 220, (k // cols) * 220))
    sh.save(out, quality=85)
    return out


SHOT_READ = """너는 원본 샷 판독 담당이다. 방송·영상 원본을 카메라가 바뀌는 곳마다 나눈 샷들의 가운데 장면이다(칸마다 '#번호 시작~끝초').
샷마다: who = "main"(주인공 {celeb} 혼자 또는 크게) · "both"({celeb}와 다른 사람 함께) · "other"({celeb} 없이 다른 사람만) · "none"(사람 없음),
product = 그 제품({kind})이 또렷이 보이면 true, cx = 주인공 얼굴 가운데의 가로 위치(0=왼쪽 끝~1=오른쪽 끝, 주인공이 없으면 null), desc = 한국어 10자 안팎. 주인공은 옷·머리·얼굴로 알아본다(같은 영상 안 다른 칸과 비교).
JSON 하나: {{"shots": [{{"i": 번호, "who": "main", "product": false, "cx": 0.5, "desc": "…"}}]}}"""
SHOT_TILES = 40       # 샷 모음 한 장에 들어가는 칸(8×5)


def shot_table(P: Piece, src: Path) -> list[dict]:
    """원본 샷 표(판단 주인) — [{i, a, b, who, product, desc}]. 방송 원본은 카메라가 1~2초마다 바뀌는데 계획 시트는 컷마다 한 장이라
    컷 안에서 다른 출연자로 넘어가는 걸 못 봤다(10-21 선우용여: 계획 검수 4번 다 '다른 출연자'로 실패). 파일마다 한 번 만들어 둔다."""
    from PIL import Image, ImageDraw
    from tools.calcopy.yanshot.plan import shots_in
    cache = P.W / f"shots_{src.stem}.json"
    if cache.exists():
        return jload(cache)
    d = _dur(src) or 0
    shots = [{"i": i, "a": a, "b": b} for i, (a, b) in enumerate(shots_in(src, [(0.0, d)]))]
    R0 = P.s.get("origin_read") or {}
    kind = (P.s.get("product") or {}).get("name") or R0.get("product_words")
    sd = P.W / "_shots"; sd.mkdir(exist_ok=True)
    for k in range(0, len(shots), SHOT_TILES):
        part = shots[k:k + SHOT_TILES]
        sh = Image.new("RGB", (8 * 240, 5 * 160), (0, 0, 0))
        for j, s in enumerate(part):
            f = sd / f"{src.stem}_{s['i']:03d}.jpg"
            try:
                frame(src, (s["a"] + s["b"]) / 2, f)
                im = Image.open(f).convert("RGB"); im.thumbnail((240, 160))
            except Exception:  # noqa: BLE001 — 못 뜬 샷은 빈칸(판독이 none 으로 둔다)
                continue
            sh.paste(im, ((j % 8) * 240, (j // 8) * 160))
            dr = ImageDraw.Draw(sh)
            dr.rectangle(((j % 8) * 240, (j // 8) * 160, (j % 8) * 240 + 150, (j // 8) * 160 + 16), fill=(0, 0, 0))
            dr.text(((j % 8) * 240 + 3, (j // 8) * 160 + 2), f"#{s['i']} {s['a']:.1f}~{s['b']:.1f}", fill=(255, 255, 0))
        p = sd / f"{src.stem}_sheet{k // SHOT_TILES}.jpg"; sh.save(p, quality=85)
        r = ask(f"shot_read_{src.stem[:20]}", SHOT_READ.format(celeb=R0.get("celeb") or "주인공", kind=kind), [img(p)], need=("shots",))
        got = {int(x.get("i", -1)): x for x in r.get("shots") or [] if isinstance(x, dict)}
        for s in part:
            g = got.get(s["i"]) or {}
            cx = g.get("cx")
            s.update(who=g.get("who") or "?", product=bool(g.get("product")), desc=str(g.get("desc") or "")[:30],
                     cx=float(cx) if isinstance(cx, (int, float)) and 0 <= cx <= 1 else None)
    jsave(cache, shots)
    return shots


def shot_text(shots: list[dict]) -> str:
    return "\n".join(f"#{s['i']} {s['a']:.2f}~{s['b']:.2f} ({s['b'] - s['a']:.1f}초) {s.get('who')}{' 제품' if s.get('product') else ''} {s.get('desc', '')}" for s in shots)


def _shot_at(shots: list[dict], t: float) -> dict | None:
    return next((s for s in shots if s["a"] - 0.05 <= t < s["b"]), None)


def fill_shot_max(P: Piece, M: dict, ar: float | None = None, S: dict | None = None) -> dict:
    """원본 컷마다 샷 표로 두 칸을 채운다(판단 주인 — 손으로 적던 칸):
    ① max = 그 샷 끝 − ss — 렌더러의 '컷이 원본 샷보다 길다' 검사가 다른 출연자로 넘어가는 컷을 잡게 한다
    ② 주인공 컷(face)은 크롭을 **주인공 얼굴 가운데**로 좌우 이동(사장님 10-21 "등장인물 주인공이 가운데 정렬되게") — 위아래(자막 피하기)는 그대로.
       'face'(자동 얼굴 크롭 = 가장 큰 얼굴)는 다른 출연자에 맞춰질 수 있어 숫자 크롭(높이 전체, 창 비율 ar)으로 바꾼다."""
    from tools.calcopy.hybrid.common import probe
    origin = {Path(f).name: Path(f) for f in (P.s.get("origin") or {}).get("files") or []}
    orig_at = {l["id"]: (l.get("src"), float(l["spans"][0][0])) for l in (S or {}).get("lines") or [] if l.get("kind") == "orig" and l.get("spans")}
    for lid, cuts in (M.get("cuts") or {}).items():
        for c in cuts if isinstance(cuts, list) else [cuts]:
            ss = c.get("ss")
            if ss is None and lid in orig_at:            # 원음 컷 = 그 줄 원음 구간 시작 + at
                ss = orig_at[lid][1] + float(c.get("at") or 0)
                c.setdefault("src", orig_at[lid][0])
            src = origin.get(str(c.get("src") or ""))
            if not src or ss is None:
                continue
            ss = float(ss)
            s = _shot_at(shot_table(P, src), ss)
            if not s:
                continue
            c["max"] = round(s["b"] - ss, 3)
            if s.get("cx") is None or str(c.get("face") or "").strip() in NO_FACE:
                continue
            sw, sh, _ = probe(src)
            crop = c.get("crop")
            if not isinstance(crop, list) or len(crop) != 4:
                if not ar:
                    continue
                cw = min(sw, int(round(sh * ar)))
                crop = [0, 0, cw, sh]
            fx = s["cx"] * sw
            if isinstance(c.get("crop"), list) and crop[0] + crop[2] * 0.25 <= fx <= crop[0] + crop[2] * 0.75:
                continue      # 이미 주인공이 칸 가운데 절반 안 — 고친 칸(박힌 자막 피하기 등)을 덮지 않는다(10-21 선우용여: 가운데로 다시 밀어 자막이 돌아왔다)
            x = int(round(fx - crop[2] / 2))
            c["crop"] = [max(0, min(sw - int(crop[2]), x)), int(crop[1]), int(crop[2]), int(crop[3])]
            c["center"] = "주인공"
    return M


NO_FACE = {"", "없음", "none", "None"}


def _cut_jumps(src: Path, ss: float, dur: float, fps: int = 10, n: int = 64) -> list[float]:
    """컷 구간 안 프레임끼리 바뀐 정도(회색 64칸 평균 차) — 장면 전환·끊김을 잰다(1초 시트 사이로 지나가는 0.5초 전환은 눈 검수가 못 본다)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.2f}", "-t", f"{dur:.2f}", "-i", str(src), "-vf", f"fps={fps},scale={n}:{n}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, stdin=subprocess.DEVNULL, timeout=120).stdout
    a = np.frombuffer(raw, np.uint8)
    if a.size < 2 * n * n:
        return []
    a = a[: a.size // (n * n) * n * n].reshape(-1, n, n).astype(float)
    return [float(x) for x in np.abs(np.diff(a, axis=0)).mean((1, 2))]


def source_rule_bad(P: Piece, M: dict, T: dict | None = None) -> list[str]:
    """재료 출처 규칙(사장님 10-21 "반드시 원본을 찾아서 / 다른 채널의 연예인 영상을 그대로 가져다 쓰면 절대 안 된다") — 판단 주인은 이 함수 하나.
    ① 벤치(남의 쇼츠)는 재료가 아니다 ② 사람 얼굴 컷은 원본 파일만 ③ T(계획·렌더 시간표)가 있으면 원본 밖 재료 컷에 장면 전환이 섞였나
    (10-21 이미도 실측: 리뷰여왕 0.3~2.5초 = 별 전환, 프레임 차 최고 73 · 상위10% 53 / 다른 재료 컷 최고 28 이하)."""
    origin = {Path(f).name for f in (P.s.get("origin") or {}).get("files") or []}
    bench = str((P.s.get("bench") or {}).get("id") or "")
    out = []
    for line, cuts in (M.get("cuts") or {}).items():
        for c in cuts if isinstance(cuts, list) else [cuts]:
            src = str(c.get("src") or "")
            if src.startswith("bench") or (bench and src.startswith(bench)):
                out.append(f"{line}: 벤치(남의 쇼츠) {src} 를 재료로 썼다 — 원본·제품 영상만 쓴다")
            elif str(c.get("face") or "").strip() not in NO_FACE and src not in origin:
                out.append(f"{line}: 사람 얼굴 컷({c.get('face')})이 원본이 아닌 {src} 에서 왔다 — 연예인 장면은 원본 파일({', '.join(sorted(origin))})에서만")
            elif src in origin and c.get("ss") is not None and (P.W / f"shots_{Path(src).stem}.json").exists():
                s = _shot_at(jload(P.W / f"shots_{Path(src).stem}.json"), float(c["ss"]))
                if s and s.get("who") == "other" and str(c.get("face") or "").strip() not in NO_FACE:
                    out.append(f"{line}: ss {c['ss']} 는 원본 샷 #{s['i']}({s['a']}~{s['b']}, {s.get('desc')}) — 주인공이 없는 다른 출연자 샷이다")
    cand = Path(M.get("cand_dir") or (P.W / "src"))
    for c in (T or {}).get("cuts") or []:
        src = str(c.get("src") or "")
        if not src or src in origin or not (cand / src).exists() or not c.get("dur"):
            continue
        d = _cut_jumps(cand / src, float(c.get("ss") or 0), float(c["dur"]))
        if d and (max(d) > 40 or sum(x > 25 for x in d) >= 3):
            out.append(f"{c.get('line')}: {src} {float(c.get('ss') or 0):.1f}초부터 {float(c['dur']):.1f}초 안에 장면 전환·끊김이 있다(남의 영상 편집 효과) — 시작점을 옮기거나 다른 장면으로")
    return out


def _fix_materials(P: Piece, version: str, why: str, sheet_img: Path | None, tag: str) -> dict:
    """계획 시트를 보고 재료.json 을 고치게 한다(제작순서 08). 답 = {ok, problems, 재료|null}."""
    from tools.calcopy.hybrid import styles as STY
    vd = P.D / version
    _, _, ww, wh = STY.load(version)["frame"]["window"]
    r = ask(tag, PLAN_LOOK.replace("{ar}", f"{ww}:{wh}") + (f"\n\n멈춘 이유(재료를 고쳐라): {why}" if why else "") + "\n\n대본:\n" +
            (vd / "대본.json").read_text(encoding="utf-8")[:6000] + "\n\n재료:\n" + (vd / "재료.json").read_text(encoding="utf-8")[:8000] + _shots_ctx(P),
            [img(sheet_img)] if sheet_img else [], need=("ok",))
    if r.get("재료"):
        M = r["재료"]; M["cand_dir"] = str(P.W / "src")
        jsave(vd / "재료.json", fill_shot_max(P, M, _ar(version), jload(vd / "대본.json")))
    return r


def _ar(version: str) -> float:
    from tools.calcopy.hybrid import styles as STY
    _, _, ww, wh = STY.load(version)["frame"]["window"]
    return ww / wh


def _shots_ctx(P: Piece) -> str:
    """대본·재료 고치기에 주는 원본 샷 표 — 주인공 컷(face)은 who main/both 샷 안에서, 한 컷이 샷 끝을 넘지 않게(max 는 엔진이 채운다)."""
    out = []
    for f in (P.s.get("origin") or {}).get("files") or []:
        if Path(f).exists():
            out.append(f"### {Path(f).name}\n" + shot_text(shot_table(P, Path(f))))
    return ("\n\n## 원본 샷 표(카메라가 바뀌는 곳마다 — 주인공 컷은 who main·both 샷 안에서 ss 를 고르고, 컷 길이가 그 샷 끝을 넘지 않게. "
            "넘으면 렌더가 '컷이 원본 샷보다 길다'로 멈춘다)\n" + "\n".join(out)) if out else ""


def st_plan(P: Piece, version: str):
    """계획 시트 → 검수 → 고침을 검수가 ok 일 때까지(최대 4번). ok 없이 렌더로 넘기지 않는다(10-21 실측: 세 번째도 자막 띠가 남은 채 넘어갔다)."""
    from tools.calcopy.hybrid import render_bench
    vd = P.D / version
    jsave(vd / "재료.json", fill_shot_max(P, jload(vd / "재료.json"), _ar(version), jload(vd / "대본.json")))      # 샷 끝(max)을 채운 뒤 계획 — 샷을 넘는 컷은 계획이 바로 짚는다
    for attempt in range(4):
        try:
            res, over = render_bench.render(version, vd, P.W / version, plan_only=True), ""
        except StageError as e:          # 컷이 원본 샷보다 길다 → 재료를 고치게 한다(제작순서 08)
            res, over = {"timeline": {"cuts": []}}, str(e)
        if not over:
            over = "; ".join(source_rule_bad(P, jload(vd / "재료.json"), res.get("timeline") or {}))
        sh = plan_sheet(P, version, res.get("timeline") or {}) if (res.get("timeline") or {}).get("cuts") else None
        r = _fix_materials(P, version, over, sh, f"plan_{version}")
        if r.get("ok") and not over and not r.get("재료"):
            P.mark("plan", version=version, tries=attempt + 1)
            return
        if not r.get("재료"):
            raise StageError(f"계획 검수가 통과하지 않았는데 재료를 고치지 못했다: {over or r.get('problems')}")
    raise StageError("계획 검수를 네 번 통과하지 못했다")


FINAL_LOOK = """너는 완성본 검수 담당이다(제작 순서 11 ③). 1초 시트를 보고: 틀·제목·자막 자리·출처 줄, 줄마다 화면이 대사와 맞나(A3), 남의 얼굴·손·글자(원본 편집 자막·워터마크) 없나,
0초 = 연예인 얼굴 크게. 남의 채널 연예인 장면·장면 전환 효과(별·와이프)가 섞였나. 받아쓰기(위스퍼 — 혼자 틀린 건 결함이 아닐 수 있다)와 대본 글자도 대조한다.
JSON 하나: {"ok": true, "problems": ["…"]}"""


def st_render_check(P: Piece, version: str) -> Path:
    from tools.calcopy.hybrid import bench_check, render_bench
    vd, wd = P.D / version, P.W / version
    P.stage("render")
    for attempt in range(3):              # 실제 목소리 길이로 컷이 원본 샷보다 길어지면 멈춘다(어림 계획은 통과해도) → 재료를 고쳐 다시(제작순서 10 '로그에서 볼 것')
        try:
            render_bench.render(version, vd, wd)
            bad = source_rule_bad(P, jload(vd / "재료.json"), jload(wd / "render" / "timeline.json"))
            if not bad:
                break
            if attempt == 2:
                raise StageError("재료 출처 규칙을 세 번 못 지켰다: " + "; ".join(bad))
            why = "; ".join(bad)
        except StageError as e:
            if "원본 샷보다 길다" not in str(e) or attempt == 2:
                raise
            why = str(e)
        r = _fix_materials(P, version, why, None, f"render_fix_{version}")
        if not r.get("재료"):
            raise StageError(f"렌더 뒤 재료를 고치지 못했다: {why}")
    final = wd / "render" / "final.mp4"
    if not final.exists():
        raise StageError("완성본이 나오지 않았다")
    P.stage("check")
    for fix in range(LOOK_FIXES + 1):     # 마지막 눈 검수가 ok 가 아니면 재료를 고쳐 다시 렌더(10-21: look_ok false 인데 '완성'으로 넘어갔다)
        auto = bench_check.check(version, vd, wd)
        heard = " ".join(x["text"] for x in whisper(final))
        sh = vd / "final_sheet_1s.jpg"
        look = ask(f"final_{version}", FINAL_LOOK + f"\n\n자동 검사: {json.dumps(auto.get('report'), ensure_ascii=False)[:2500]}\n받아쓰기: {heard[:2500]}\n대본:\n" +
                   (vd / "대본.json").read_text(encoding="utf-8")[:5000], [img(sh)] if sh.exists() else [], need=("ok",))
        if look.get("ok") or fix == LOOK_FIXES:
            break
        r = _fix_materials(P, version, "완성본 눈 검수에서 걸린 것(화면·크롭·남의 글자만 재료로 고친다): " + json.dumps(look.get("problems"), ensure_ascii=False)[:3000],
                           sh if sh.exists() else None, f"final_fix_{version}")
        if not r.get("재료"):
            break
        P.stage("render")
        render_bench.render(version, vd, wd)
        P.stage("check")
    P.mark("check", auto_ok=bool(auto.get("ok")), look_ok=bool(look.get("ok")), problems=look.get("problems"), look_fixes=fix)
    return final


# ── 바깥 진입 ───────────────────────────────────────────────────────────
def _out(P: Piece, need: str, **kw) -> dict:
    pr = jload(P.W / "progress.json") if (P.W / "progress.json").exists() else {}
    return {"sid": P.sid, "need": need, "stage": pr.get("stage"), "step": pr.get("step"), "total": pr.get("total"), **kw}


def _script_view(P: Piece, version: str) -> dict:
    S = jload(P.D / version / "대본.json")
    title = " ".join("".join(c[0] for c in l) if isinstance(l, list) else str(l) for l in S.get("title_lines") or [])
    lines = [(l.get("tts") or l.get("text") or " ".join(c[0] for c in l.get("caps_rel") or []) or "").strip() for l in S.get("lines") or []]
    return {"title": title, "lines": [x for x in lines if x][:30]}


def start(ref: str, version: str) -> dict:
    P = Piece(uuid.uuid4().hex[:12])
    P.s.update(ref=ref, version=version); P.save()
    return advance(P)


def advance(P: Piece) -> dict:
    v = P.s["version"]
    try:
        for key, fn in (("bench", lambda: st_bench(P, P.s["ref"])), ("origin", lambda: st_origin(P)), ("product", lambda: st_product(P)),
                        ("research", lambda: st_research(P)), ("material", lambda: st_material(P)), ("asr", lambda: st_asr(P)),
                        ("script", lambda: st_script(P, v))):
            if not P.did(key):
                P.stage(key)
                fn()
        if not P.s.get("approved"):
            P.stage("sign")
            return _out(P, "approve", script=_script_view(P, v))
        if not P.did("plan"):
            P.stage("plan")
            st_plan(P, v)
        final = st_render_check(P, v) if not P.did("check") else P.W / v / "render" / "final.mp4"
        P.stage("done")
        c = P.s["done"].get("check", {})
        return _out(P, "done", video=str(final), title=_script_view(P, v)["title"], auto_ok=c.get("auto_ok"), look_ok=c.get("look_ok"))
    except Stop as e:
        P.s["stopped"] = {"why": e.why, "fix": e.fix}; P.save()
        return _out(P, "fail", why=e.why, fix=e.fix, retry_ok=False)


def approve(sid: str) -> dict:
    P = Piece(sid)
    P.s["approved"] = True; P.save()
    return advance(P)


def resume(sid: str) -> dict:
    """멈춘 단계(오류)부터 다시 — 끝난 단계는 건너뛴다(집 PC run.py 와 같은 이어 돌리기)."""
    if not (base() / sid / "piece.json").exists():
        return {"sid": sid, "need": "fail", "why": "그 작업이 없습니다", "fix": "", "retry_ok": False}
    return advance(Piece(sid))


def status(sid: str) -> dict:
    if not (base() / sid / "piece.json").exists():
        return {"sid": sid, "need": "fail", "why": "그 작업이 없습니다", "fix": "", "retry_ok": False}
    P = Piece(sid)
    if P.s.get("stopped"):
        return _out(P, "fail", **P.s["stopped"])
    if P.did("check"):
        return _out(P, "done", video=str(P.W / P.s["version"] / "render" / "final.mp4"))
    return _out(P, "wait")
