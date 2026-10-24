# -*- coding: utf-8 -*-
"""agy_google.py — 구글 이미지 후보를 **agy(Antigravity CLI · 구독 정액제)** 로 모은다.

■ 왜 (2026-09-28 사장님 결정 «네이버는 기존대로 유지하고, 구글만 agy로 가자»)
    구글 이미지는 serper(질의마다 유료) 대신 수강생 자기 agy 요금제로 찾는다.
    수강생은 전원 agy 요금제(울트라 20x)를 결제했다(사장님 확인 2026-09-28).
    실측(이 맥, 검색어 16개 동시, 2026-09-28 run7): 검색 36초 · 구글 중계 주소 265개 136초 ·
    끝까지 350초 · 쓸 만한 사진 264장 · 구글 거부 0. 원본: 작업일지 볼트
    `노트/울트라20x자동화조사_20260927/원문/agy이미지검색/3차/7차_확정설정/`.

■ 흐름 — 이 부품은 **사진 주소 후보**까지만 만든다. 받기·거르기·검수는 부르는 쪽의 기존 흐름이 한다.
    ① agy `search_web` — 검색어마다 변형 여러 개를 agy 한 번에 검색하게 하고, agy 는 «끝» 만 답하게 한다.
       검색 결과 원문은 agy 가 남기는 `~/.gemini/antigravity-cli/brain/<대화>/.system_generated/steps/*/output.txt`
       에서 **직접** 읽는다(모델이 링크를 베껴 쓰면 18~50초가 더 들고 빠뜨린다 — 실측).
       윈도우도 같은 자리다(`%USERPROFILE%\\.gemini\\antigravity-cli\\brain`, win-01 실물 확인 2026-09-28).
    ② 결과의 출처는 구글 중계 주소(vertexaisearch.cloud.google.com/grounding-api-redirect/…)다.
       따라가지 않고 **이동할 곳(Location)만** 본다 — 동시 2 · 요청 시작 사이 0.5초 = **초당 2건 이하**
       (사장님 확정 2026-09-28 · 공식 숫자 없음: ai.google.dev google-search 문서 · Vertex grounding 문서 ·
       Gemini API 약관 · vertexaisearch robots.txt 확인. 초당 2건 266회 거부 0 실측).
    ③ 목적지 페이지에서 대표 사진(og:image)과 본문 사진(최대 max_body 장) 주소를 뽑는다.
       사이트마다 동시 1 · 초당 1건 이하(보수값 · 공식 숫자 없음), 서로 다른 사이트는 동시에.

■ 거부
    구글 소유 주소가 429·403·/sorry/ 를 한 번이라도 주면 **그 실행의 구글 요청을 전부 멈춘다**(작업일지 규칙 6-2).
    다른 사이트의 401(봇 검사)·403·429 는 **그 사이트만** 멈춘다. agy 가 429·한도 소진을 알리면 agy 호출을 전부 멈춘다.

■ 로그인·키
    agy 를 부를 때 `GEMINI_API_KEY`·`GOOGLE_API_KEY` 를 **뺀다** — 공식 문서상 agy 는 그 키로도 로그인할 수 있어서
    (antigravity.google/docs/cli/install), 수강생 PC 에 키가 있으면 요금제 대신 유료 API 로 빠질 수 있다.
    로그인이 안 된 PC 의 agy 는 «Authentication required» 와 로그인 주소를 찍는다(win-01 실측) — probe() 가 그 말을 잡는다.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def model() -> str:
    """이 부품의 agy 모델 — 실행기 agy 모델 한 자리(agy_transport_pc_env.agy_model: env INFO3D_AGY_MODEL 이 먼저, 없으면 그 기본값)를
    부를 때마다 읽는다(2026-10-23 수강생 요청 «고정값이라 환경 변수로 못 바꾼다»). 기본값은 그대로 gemini-3.8-flash-high."""
    import agy_transport_pc_env as PC   # 같은 실행기 폴더 — 이 부품을 쓸 때만 읽는다
    return PC.agy_model()
REDIRECT_MARK = "grounding-api-redirect"
#: 검색 문구(변형)·건너뛸 곳은 **서버가 준다**(`volcano_person.PHOTO_SOURCES` 의 agy_google 칸) — 2026-09-28 실측으로
#  다듬은 노하우라 배급 실행기에 두지 않는다(CLAUDE.md §2 · 경계 검사 [97]). 여기에는 쓰는 방법만 있다.
_GOOGLE_HOST = re.compile(r"(^|\.)(google\.[a-z.]+|youtube\.com|ytimg\.com|gstatic\.com|googleusercontent\.com|googleapis\.com)$")
_KO = re.compile(r"[가-힣]")


def _host(u: str) -> str:
    return urllib.parse.urlparse(u).netloc.lower().split(":")[0]


def _skipped(host: str, skip) -> bool:
    host = host[4:] if host.startswith("www.") else host
    return any(host == d or host.endswith("." + d) for d in skip)


def variants_for(q: str, variants) -> tuple[str, ...]:
    """서버가 준 검색 문구 중 이 검색어에 쓸 것. {"hangul": [...], "other": [...]} 이면 한글이 든 검색어에 hangul 쪽."""
    if isinstance(variants, dict):
        chosen = variants.get("hangul") if _KO.search(q) else variants.get("other")
    else:
        chosen = variants
    chosen = tuple(str(v) for v in (chosen or ()) if "{q}" in str(v))
    if not chosen:
        raise ValueError("서버 선언에 검색 문구(variants)가 없습니다 — agy 구글 검색을 시작하지 않습니다")
    return chosen


# ── agy 찾기·점검 ────────────────────────────────────────────────────────────
def agy_candidates(osname: str, home: str, localappdata: str | None) -> list[str]:
    """공식 설치 자리(antigravity.google/docs/cli/install): 맥·리눅스 ~/.local/bin/agy ·
    윈도우 %LOCALAPPDATA%\\agy\\bin\\agy.exe (win-01 실물 확인). 글자 경로로 만들어 어느 OS 에서든 같게 잰다."""
    out = []
    if osname == "nt":
        la = localappdata or home.rstrip("\\/") + "\\AppData\\Local"
        out.append(la.rstrip("\\/") + "\\agy\\bin\\agy.exe")
    out.append(os.path.join(home, ".local", "bin", "agy"))
    return out


def find_agy() -> str | None:
    """PATH 에 있으면 그것, 없으면 공식 설치 자리."""
    hit = shutil.which("agy")
    if hit:
        return hit
    for p in agy_candidates(os.name, str(Path.home()), os.environ.get("LOCALAPPDATA")):
        if os.path.isfile(p):
            return p
    return None


def brain_dir() -> Path:
    return Path.home() / ".gemini" / "antigravity-cli" / "brain"


def _agy_env() -> dict:
    env = dict(os.environ)
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        env.pop(k, None)                      # 요금제 로그인만 쓴다(유료 API 키로 빠지지 않게)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run_agy(agy: str, args: list[str], cwd: str | None, timeout: float) -> tuple[int, str, str]:
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.run([agy, *args], cwd=cwd, env=_agy_env(), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, **kw)
    return p.returncode, p.stdout or "", p.stderr or ""


def probe(agy: str | None = None, timeout: float = 60.0) -> dict:
    """agy 가 있고 로그인돼 있는가 — `agy models`(모델 목록 조회 · 한도를 쓰지 않는다)로 판정한다.

    ■ 왜 `models` 인가 (2026-09-28 · 실측)
        전에는 `agy -p /usage` 로 판정했다. 로그인이 안 된 PC 에서 print 모드는 로그인 흐름(consumerOAuth)을
        시작하고 **60초를 기다린 뒤** 끝났다(win-01 cli.log 12건) — 수강생 화면엔 그동안 아무 안내가 없고,
        agy 공식 문서대로면 내 PC 에서는 브라우저 로그인 창도 뜬다. `agy models` 는 로그인이 없으면
        곧바로 «Please sign in…» · 종료 1 로 끝난다(win-01 ssh = 로그인 없는 조건, 1.2.12 · 1.0초).
        로그인된 맥은 종료 0 · 3.1초 · 목록에 gemini-3.8-flash-high. 같은 제품 3D쇼츠 엔진도 이 방식이다.
    ★제한 시간 60초는 공식 숫자가 아니다(agy 문서에 없음) — 3D쇼츠 엔진 pc_env 의 agy 제한과 같게 둔다.
    """
    agy = agy or find_agy()
    if not agy:
        return {"ok": False, "why": "no_agy", "path": None,
                "say": "agy(Antigravity CLI)가 없습니다 — 설치: 맥 `curl -fsSL https://antigravity.google/cli/install.sh | bash` · "
                       "윈도우 PowerShell `irm https://antigravity.google/cli/install.ps1 | iex` 뒤 터미널에서 `agy` 를 한 번 실행해 로그인하세요."}
    try:
        rc, out, err = _run_agy(agy, ["models"], None, timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "why": "timeout", "path": agy, "say": f"agy 가 {timeout:.0f}초 안에 답하지 않았습니다."}
    blob = out + "\n" + err
    if rc != 0 and re.search(r"sign in|log in|Authentication required", blob, re.I):
        return {"ok": False, "why": "login", "path": agy,
                "say": "agy 로그인이 필요합니다 — 터미널에서 `agy` 를 한 번 실행해 구글 계정으로 로그인한 뒤 다시 시도하세요."}
    if rc != 0:
        return {"ok": False, "why": "unreadable", "path": agy,
                "say": f"agy 모델 목록을 읽지 못했습니다(rc={rc}): {blob.strip()[:160]}"}
    name = model()
    if not re.search(r"^" + re.escape(name) + r"\b", out, re.M):
        return {"ok": False, "why": "model", "path": agy,
                "say": f"이 agy 계정에서 {name} 모델을 쓸 수 없습니다 — 요금제·로그인 계정을 확인하세요."}
    return {"ok": True, "why": "", "path": agy, "say": ""}


# ── ① 검색 ──────────────────────────────────────────────────────────────────
_SRC_LINE = re.compile(r"^\[\d+\]\s*\[([^\]]+)\]\((https?://[^)\s]+)\)", re.M)
_MD_LINK = re.compile(r"\]\((https?://[^)\s]+)\)")


def parse_search_output(text: str, variants: tuple[str, ...]) -> list[dict]:
    """agy search_web 원문 하나 → [{v, dom, url}] (Sources 는 사이트 이름 + 구글 중계 주소, 요약 속 직접 링크 포함)."""
    m = re.match(r'The search for "(.*?)" returned', text)
    if not m:
        return []
    vq = m.group(1)
    vi = variants.index(vq) if vq in variants else -1
    summary, _, sources = text.partition("\nSources:")
    out = [{"v": vi, "dom": dom.lower(), "url": url} for dom, url in _SRC_LINE.findall(sources)]
    out += [{"v": vi, "dom": _host(u), "url": u} for u in _MD_LINK.findall(summary) if REDIRECT_MARK not in u]
    return out


class Stop:
    """한 실행 안에서 공유하는 멈춤 표시(구글 거부 · agy 거부 · 사이트별 거부)."""
    def __init__(self):
        self.google = threading.Event()
        self.agy = threading.Event()
        self.hosts: set[str] = set()
        self.lock = threading.Lock()
        self.notes: list[str] = []

    def note(self, s: str, log=None):
        with self.lock:
            self.notes.append(s)
        if log:
            log(s)


def search_one(agy: str, q: str, variants: tuple[str, ...], workdir: str, stop: Stop,
               timeout: float = 240.0, log=None) -> dict:
    """검색어 하나 = agy 한 번(변형 여러 개). 반환 {q, links, sec, outputs, tokens, error}."""
    t0 = time.time()
    if stop.agy.is_set():
        return {"q": q, "links": [], "sec": 0.0, "outputs": 0, "tokens": 0, "error": "agy_stopped"}
    vs = tuple(v.format(q=q) for v in variants)
    prompt = ("search_web 도구로 다음 검색어를 각각 한 번씩 검색해라: " + " / ".join(f"'{v}'" for v in vs) +
              ". 다른 도구는 쓰지 마라. 검색이 다 끝나면 '끝' 한 글자만 답해라.")
    try:
        rc, out, err = _run_agy(agy, ["-p", prompt, "--output-format", "json", "--model", model()], workdir, timeout)
    except subprocess.TimeoutExpired:
        return {"q": q, "links": [], "sec": round(time.time() - t0, 1), "outputs": 0, "tokens": 0, "error": "timeout"}
    blob = (err or "") + " " + (out[-400:] if out else "")
    try:
        d = json.loads(out[out.index("{"):])
    except ValueError:
        d = {}
    # ★정상 답(status SUCCESS · 오류 칸 없음)의 JSON 숫자 칸(걸린 ms·토큰 수 «429» 등)을 한도 표시로 읽지 않는다(2026-10-17 신고 —
    #   «끝» 한 글자 정상 답을 AGY REFUSED 로 판정해 그 실행의 구글 사진 검색이 통째로 멈췄다 · 두 번). 정상 답이면 stderr 만 본다.
    success = isinstance(d, dict) and str(d.get("status") or "").upper() == "SUCCESS" and not d.get("error")
    signs = (err or "") if success else blob + " " + str(d.get("error") or "")
    if re.search(r"\b429\b|RESOURCE_EXHAUSTED|quota|rate limit", signs, re.I):
        if not stop.agy.is_set():
            stop.agy.set()
            stop.note(f"AGY REFUSED — agy 호출을 전부 멈춘다: {blob.strip()[:160]}", log)
        return {"q": q, "links": [], "sec": round(time.time() - t0, 1), "outputs": 0, "tokens": 0, "error": "agy_refused"}
    conv = d.get("conversation_id") or ""
    links, n = [], 0
    steps = brain_dir() / conv / ".system_generated" / "steps"
    if conv and steps.is_dir():
        for p in sorted(steps.glob("*/output.txt")):
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            got = parse_search_output(t, vs)
            if got or t.startswith("The search for"):
                n += 1
            links += got
    err_s = "" if n else (d.get("error") or d.get("status") or f"rc={rc}")
    return {"q": q, "links": links, "sec": round(time.time() - t0, 1), "outputs": n,
            "tokens": (d.get("usage") or {}).get("total_tokens") or 0, "error": err_s}


# ── 받기(사이트마다 동시 1 · 초당 1건 이하, 구글 중계 주소는 동시 2 · 초당 2건 이하) ─────────
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_NO_FOLLOW = urllib.request.build_opener(_NoRedirect)
_locks: dict[str, threading.Lock] = {}
_next: dict[str, float] = {}
_gl = threading.Lock()
_RD_SEM = threading.Semaphore(2)              # 사장님 확정: 초당 2건 = 동시 2 · 시작 간격 0.5초
_RD_INTERVAL = 0.5
_RD_LOCK = threading.Lock()
_RD_NEXT = [0.0]


def _paced(host: str, interval: float = 1.0):
    with _gl:
        lk = _locks.setdefault(host, threading.Lock())
    lk.acquire()
    w = _next.get(host, 0.0) - time.time()
    if w > 0:
        time.sleep(w)
    _next[host] = time.time() + interval
    return lk


def _refused(host: str, code, final: str, stop: Stop, log=None) -> bool:
    code = str(code)
    if code not in ("401", "403", "429") and "/sorry/" not in (final or ""):
        return False
    if _GOOGLE_HOST.search(host) or (final and _GOOGLE_HOST.search(_host(final))):
        if not stop.google.is_set():
            stop.google.set()
            stop.note(f"GOOGLE REFUSED {code} {host} → 구글 요청 전부 멈춤", log)
    else:
        with stop.lock:
            new = host not in stop.hosts
            stop.hosts.add(host)
        if new:
            stop.note(f"site refused {code} {host} → 이 사이트만 멈춤", log)
    return True


def resolve(url: str, stop: Stop, timeout: float = 20.0, log=None) -> str:
    """구글 중계 주소 → 목적지 주소. 따라가지 않는다. 실패는 ''."""
    if stop.google.is_set():
        return ""
    host = _host(url)
    with _RD_SEM:
        with _RD_LOCK:
            w = _RD_NEXT[0] - time.time()
            if w > 0:
                time.sleep(w)
            _RD_NEXT[0] = time.time() + _RD_INTERVAL
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with _NO_FOLLOW.open(req, timeout=timeout) as r:
                code, loc = r.status, r.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            code, loc = e.code, e.headers.get("Location", "") if e.headers else ""
        except (urllib.error.URLError, OSError, ValueError):
            return ""
    if _refused(host, code, loc, stop, log):
        return ""
    return loc if code in (301, 302, 303, 307, 308) and loc.startswith("http") else ""


def fetch_text(url: str, stop: Stop, timeout: float = 20.0, cap: int = 3_000_000, log=None) -> tuple[str, str]:
    """페이지 HTML(최대 cap 바이트)과 최종 주소. 실패는 ('', '')."""
    host = _host(url)
    if host in stop.hosts or (stop.google.is_set() and _GOOGLE_HOST.search(host)):
        return "", ""
    lk = _paced(host)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            final = r.geturl()
            if "html" not in ctype:
                return "", final
            raw = r.read(cap)
            cs = r.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        _refused(host, e.code, getattr(e, "url", "") or "", stop, log)
        return "", ""
    except (urllib.error.URLError, OSError, ValueError):
        return "", ""
    finally:
        lk.release()
    try:
        return raw.decode(cs, errors="replace"), final
    except LookupError:
        return raw.decode("utf-8", errors="replace"), final


_OG = (re.compile(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I),
       re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image', re.I))
_IMG = re.compile(r"<img\b[^>]*>", re.I)


_TITLE = (re.compile(r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)', re.I),
          re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:title', re.I),
          re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S))
_DESC = (re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:)?description["\'][^>]+content=["\']([^"\']+)', re.I),
         re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:)?description', re.I))


def _first(patterns, text: str, cap: int = 300) -> str:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))).strip()[:cap]
    return ""


def page_text(html_text: str) -> tuple[str, str]:
    """(페이지 제목, 페이지 설명) — 받기 전 «누구·무엇의 사진인가» 근거(검수가 요구한다)."""
    return _first(_TITLE, html_text), _first(_DESC, html_text)


def page_images(html_text: str, base: str, max_body: int = 10) -> tuple[str, list[str]]:
    """(대표 사진, 본문 사진들). 본문은 data-src·srcset 우선, 작다고 적힌 것·svg·gif·아이콘은 뺀다."""
    og, body = page_images_alt(html_text, base, max_body)
    return og, [u for u, _ in body]


def page_images_alt(html_text: str, base: str, max_body: int = 10) -> tuple[str, list[tuple[str, str]]]:
    """page_images 와 같고, 본문 사진마다 alt 글(사진 설명)을 함께 준다."""
    og = ""
    for pat in _OG:
        m = pat.search(html_text)
        if m:
            og = urllib.parse.urljoin(base, _html.unescape(m.group(1)).strip())
            break
    body: list[tuple[str, str]] = []
    for tag in _IMG.findall(html_text):
        cand = None
        for a in ("data-original", "data-src", "data-lazy-src", "data-url", "src"):
            # 속성 이름은 통째로 — «:src»·«v-bind:src»(화면 틀 묶기 식)·«ng-src» 의 끝 «src» 를 주소 칸으로 읽지 않는다
            m = re.search(r"(?<![\w:.-])" + a + r"\s*=\s*[\"']([^\"']+)[\"']", tag, re.I)
            if m and not m.group(1).startswith("data:"):
                cand = m.group(1)
                break
        m = re.search(r"(?<![\w:.-])srcset\s*=\s*[\"']([^\"']+)[\"']", tag, re.I)
        if m:
            parts = [p.strip().split(" ")[0] for p in m.group(1).split(",") if p.strip()]
            if parts and not parts[-1].startswith("data:"):
                cand = parts[-1]
        if not cand:
            continue
        u = urllib.parse.urljoin(base, _html.unescape(cand.strip()))
        low = u.lower()
        if (not low.startswith("http") or re.search(r"\.(svg|gif)(\?|$)", low)
                or re.search(r"(logo|icon|sprite|btn_|blank|spacer|pixel|emoji)", low)):
            continue
        w = re.search(r"\bwidth\s*=\s*[\"']?(\d+)", tag)
        h = re.search(r"\bheight\s*=\s*[\"']?(\d+)", tag)
        if (w and int(w.group(1)) < 200) or (h and int(h.group(1)) < 150):
            continue
        alt = re.search(r"\balt\s*=\s*[\"']([^\"']*)[\"']", tag, re.I)
        alt_s = re.sub(r"\s+", " ", _html.unescape(alt.group(1))).strip()[:200] if alt else ""
        if u != og and all(u != x for x, _ in body):
            body.append((u, alt_s))
    return og, body[:max_body]


# ── 한 번에: 검색어 여러 개 → 검색어별 사진 주소 후보 ─────────────────────────────
def candidates(queries: list[str], workdir: str, *, variants, skip_domains, agy: str | None = None,
               search_workers: int = 16, page_workers: int = 24, max_body: int = 10, log=None,
               stop: "Stop | None" = None) -> dict:
    """반환 {"by_query": {q: [{url, page, kind('og'|'body'|'direct'), q}]}, "stats": {...}, "notes": [...]}.

    ★받기·크기 재기·중복·검수는 하지 않는다 — 부르는 쪽이 자기 기존 흐름(받기 자·검수)을 그대로 쓴다.
    검색어 순서대로 풀어서 앞 검색어의 후보가 먼저 완성된다.
    """
    chosen = {q: variants_for(q, variants) for q in queries}      # 문구가 없으면 agy 를 부르기 전에 멈춘다
    skip_domains = tuple(skip_domains)
    agy = agy or find_agy()
    # ★멈춤 표시는 **부르는 쪽이 한 실행 동안 같은 것을** 넘긴다(2026-09-28 규칙 6-2 수리) — 부를 때마다 새로
    #   만들면 컷 A 에서 구글이 거부해도 컷 B 가 구글을 다시 불렀다.
    stop = stop if stop is not None else Stop()
    cut: set[str] = set()                     # 거부로 멈춰 끝까지 못 푼 검색어 — 부르는 쪽이 «완료»로 적지 않는다
    stats = {"queries": len(queries), "search_sec": 0.0, "links": 0, "resolved": 0, "skipped": 0,
             "pages": 0, "candidates": 0, "agy_tokens": 0, "search_errors": {}}
    by_query: dict[str, list[dict]] = {q: [] for q in queries}
    if not agy or not queries:
        stats["search_errors"] = {"*": "no_agy" if not agy else "no_query"}
        return {"by_query": by_query, "stats": stats, "notes": stop.notes}
    os.makedirs(workdir, exist_ok=True)
    t0 = time.time()
    with ThreadPoolExecutor(max(1, min(search_workers, len(queries)))) as ex:
        res = list(ex.map(lambda q: search_one(agy, q, chosen[q], workdir, stop, log=log), queries))
    stats["search_sec"] = round(time.time() - t0, 1)
    for r in res:
        stats["links"] += len(r["links"])
        stats["agy_tokens"] += r["tokens"] or 0
        if r["error"]:
            stats["search_errors"][r["q"]] = r["error"]
    page_ex = ThreadPoolExecutor(page_workers)
    rd_ex = ThreadPoolExecutor(2)
    lock = threading.Lock()
    seen_pages: dict[str, set] = {q: set() for q in queries}
    seen_imgs: dict[str, set] = {q: set() for q in queries}
    futs = []

    def add(q, url, page, kind, title="", caption=""):
        with lock:
            if not url or url in seen_imgs[q] or _skipped(_host(url), skip_domains):
                return
            seen_imgs[q].add(url)
            by_query[q].append({"url": url, "page": page, "kind": kind, "q": q,
                                "title": title, "caption": caption})

    def do_page(q, url):
        if re.search(r"\.(jpe?g|png|webp)(\?|$)", url, re.I):
            add(q, url, "", "direct")
            return
        text, final = fetch_text(url, stop, log=log)
        if not text:
            return
        og, body = page_images_alt(text, final or url, max_body)
        title, desc = page_text(text)
        add(q, og, final or url, "og", title, desc)
        for u, alt in body:
            add(q, u, final or url, "body", title, alt or desc)
        with lock:
            stats["pages"] += 1

    def do_link(q, L):
        if _skipped(L["dom"], skip_domains):
            with lock:
                stats["skipped"] += 1
            return
        u = L["url"]
        if REDIRECT_MARK in u:
            if stop.google.is_set():
                with lock:
                    cut.add(q)
                return
            u = resolve(u, stop, log=log)
            if not u:
                if stop.google.is_set():
                    with lock:
                        cut.add(q)
                return
            with lock:
                stats["resolved"] += 1
        if _skipped(_host(u), skip_domains):
            with lock:
                stats["skipped"] += 1
            return
        with lock:
            if u in seen_pages[q]:
                return
            seen_pages[q].add(u)
            futs.append(page_ex.submit(do_page, q, u))

    rfuts = [rd_ex.submit(do_link, r["q"], L) for r in res for L in r["links"]]
    wait(rfuts)
    rd_ex.shutdown(wait=True)
    while True:
        with lock:
            pending = list(futs)
        wait(pending)
        with lock:
            if len(futs) == len(pending):
                break
    page_ex.shutdown(wait=True)
    for f in rfuts + futs:
        e = f.exception()
        if e:
            stop.note(f"ERROR {type(e).__name__}: {e}", log)
    stats["candidates"] = sum(len(v) for v in by_query.values())
    stats["google_stopped"] = stop.google.is_set()
    stats["cut_queries"] = sorted(cut)
    stats["agy_stopped"] = stop.agy.is_set()
    stats["blocked_hosts"] = sorted(stop.hosts)
    stats["sec"] = round(time.time() - t0, 1)
    return {"by_query": by_query, "stats": stats, "notes": stop.notes}


def _selftest() -> int:
    """네트워크·agy 없이 도는 자체 시험: 원문 해석 · 대표/본문 사진 뽑기 · 거부 판정 · 건너뛸 곳."""
    sample = ('The search for "올드보이 영화 사진" returned the following summary:\n'
              "요약 [FILMGRAB](https://filmgrab.com/) 입니다.[1]\n\nSources:\n"
              "[1] [film-grab.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQ1)\n"
              "[2] [photos.example](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQ2)\n")
    got = parse_search_output(sample, ("올드보이 영화 사진",))
    assert [g["dom"] for g in got] == ["film-grab.com", "photos.example", "filmgrab.com"], got
    assert got[0]["v"] == 0 and REDIRECT_MARK in got[0]["url"] and got[2]["url"] == "https://filmgrab.com/"
    html_text = ('<meta property="og:image" content="/og.jpg">'
                 '<img src="data:x" data-src="https://cdn.x/a.jpg"><img src="/logo.png">'
                 '<img srcset="https://cdn.x/b-320.jpg 320w, https://cdn.x/b-1280.jpg 1280w">'
                 '<img src="https://cdn.x/t.jpg" width="120"><img src="https://cdn.x/i.svg">')
    og, body = page_images(html_text, "https://site.x/p/1")
    assert og == "https://site.x/og.jpg", og
    assert body == ["https://cdn.x/a.jpg", "https://cdn.x/b-1280.jpg"], body
    # 화면 틀 묶기 식(«:src»·«v-bind:src»)은 주소 칸이 아니다 — 진짜 src 만 읽는다(10-20 강석주 InvalidURL)
    _, body = page_images('<img :src="article.ar_image_optimized || article.ar_image" src="https://cdn.x/d.jpg">'
                          '<img v-bind:src="a.b">', "https://site.x/articles/")
    assert body == ["https://cdn.x/d.jpg"], body
    _, body_alt = page_images_alt('<img alt="손흥민 &amp; 동료" src="https://cdn.x/c.jpg">', "https://site.x/")
    assert body_alt == [("https://cdn.x/c.jpg", "손흥민 & 동료")], body_alt
    assert page_text('<title>손흥민 - 나무위키</title><meta name="description" content="축구 선수">') == ("손흥민 - 나무위키", "축구 선수")
    assert page_text('<meta property="og:title" content="경복궁 &middot; 사진"><title>x</title>')[0] == "경복궁 · 사진"
    st = Stop()
    assert _refused("bot-check.example", 401, "", st) and "bot-check.example" in st.hosts and not st.google.is_set()
    assert not _refused("example.com", 200, "", st)
    assert _refused("vertexaisearch.cloud.google.com", 429, "", st) and st.google.is_set()
    skip = ("stock.example", "hotels.example")                  # 실제 목록은 서버가 준다 — 여기는 판정 방법만 잰다
    assert _skipped("www.stock.example", skip) and _skipped("kr.hotels.example", skip) and not _skipped("namu.wiki", skip)
    declared = {"hangul": ["{q} 표본"], "other": ["{q} sample"]}
    assert variants_for("손흥민", declared) == ("{q} 표본",) and variants_for("Beirut 1960s", declared) == ("{q} sample",)
    assert variants_for("x", ["{q} a", "{q} b"]) == ("{q} a", "{q} b")
    for bad in (None, {}, {"hangul": []}, ["no placeholder"]):
        try:
            variants_for("손흥민", bad)
            raise AssertionError(f"검색 문구 없이 시작했다: {bad!r}")
        except ValueError:
            pass
    saved = {k: os.environ.get(k) for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
    try:
        os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"] = "selftest"
        e = _agy_env()
        assert "GEMINI_API_KEY" not in e and "GOOGLE_API_KEY" not in e, "유료 키가 agy 로 넘어간다"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print("✓ agy_google 자체시험 통과 — 원문 해석 · 대표/본문 사진 · 거부 판정(401 사이트·429 구글) · 건너뛸 곳 · 유료 키 제거")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    if "--probe" in sys.argv:
        print(json.dumps(probe(), ensure_ascii=False))
        sys.exit(0)
    # 검색 문구·건너뛸 곳은 서버가 준다 — 단독 실행으로 검색하지 않는다(실행기 흐름 `_source_urls` 로 부른다).
    print("사용법: agy_google.py --selftest | --probe   (검색은 서버 지시로 실행기가 부른다)", file=sys.stderr)
    sys.exit(2)
