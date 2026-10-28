#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nukki.py — 사람 사진 누끼(배경 지우기)의 **한 자리** — 실행기 공용 모듈 (2026-10-17 · 신고 #121 3명).

■ 왜 여기 하나인가
    같은 누끼(본인 Cloudflare Worker · 아니면 Replicate)가 두 벌 있었다 — 너이봤 팩 `tools/nb_cfseg.py`·`tools/nb_matte.py` 와
    옛 롱폼 파이프라인 덧쓰기 `cfnukki.py`. 그리고 지금의 인물형 롱폼 엔진(geumbit)은 작성 안내가 «팩의 cfnukki.py connect» 를
    가리키는데 그 파일은 geumbit 작업이 받는 팩(runner·geumbit)에 없었고, 누끼를 실제로 만드는 실행기 일감도 없었다.
    → 연결·오리기·엔진 고르기를 여기 하나로 모은다. 실행기 팩(runner)에 실리므로 모든 작업 폴더에 있다
      (`<작업 폴더>/runner/nukki.py`). 너이봤 팩은 굽기(tools/build_neoibwa_pack.py)가 이 파일을 그대로 `tools/nukki.py` 로 싣는다.
      인물형 롱폼은 서버 일감 `prepare_cutouts`(실행기 longform_cutout.py)가 이 모듈로 오린다.

■ 쓰기
    python <작업 폴더>/runner/nukki.py connect   → 처음 한 번: 브라우저 «Allow» 한 번으로 본인 계정에 누끼 Worker 를 올리고 시험 한 장까지
                                                 오린다. 끝나면 ~/.volcano/keys/cf_nukki 에 {Worker 주소 · 비밀} 을 적는다(값은 찍지 않는다).
    python <작업 폴더>/runner/nukki.py status    → 연결돼 있는지만 말한다(요청을 보내지 않는다).

■ 엔진 순서(2026-10-13 사장님 결정 · 고르는 곳은 engine() 한 자리)
    ① 본인 Cloudflare 누끼 Worker 가 연결돼 있으면 → Cloudflare(Images segment=foreground = BiRefNet · 월 5,000장 무료)
    ② 연결 안 했으면 → 본인 Replicate 열쇠(유료 · 수강생이 직접 넣은 열쇠 = 그 사람이 고른 길 · 볼케이노 서비스 묶음 «nukki»)
    ③ 둘 다 없으면 오리지 않고 무엇을 하면 되는지 말한다.
    ★Cloudflare 가 거부·실패하면 남은 사진은 보내지 않고 멈춘다 — 유료 Replicate 로 몰래 넘기지 않는다(돈이 나가는 쪽).

■ 외부 요청 규칙(전역 규칙 6-2 · 숫자는 공식 문서·실측·사장님 결정 그대로 — 옛 두 벌에 적혀 있던 값을 옮겼다)
    Cloudflare — 공식(https://developers.cloudflare.com/workers/platform/limits/ · 2026-10-13 확인): Workers 무료 하루 요청 100,000건 ·
      «There is no general limit on requests per second». Images 변환(segment) 월 5,000장 무료 뒤 1,000장당 $0.50.
      Images 의 동시 처리 한도는 공식 숫자가 없다. 동시 20 = 2026-10-13 사장님 결정(실측 같은 20장: 동시 20 → 6.7초 · 동시 10 → 9.2초 ·
      거부 0). 200·PNG 가 아닌 응답이 **한 번이라도** 오면 아직 안 보낸 사진은 보내지 않는다(이미 보낸 것만 받는다). 자동 재시도 없음.
    Replicate — 공식(https://replicate.com/docs/topics/predictions/rate-limits «Rate limits», 2026-10-12 확인): 예측 만들기 분당 600건 ·
      그 밖의 API 분당 3000건. 단 «잔액이 바닥에 가까우면 더 센 한도», «크레딧을 받았고 결제 수단이 없으면 초당 1건 · 분당 최대 6건».
      수강생 잔액을 알 수 없으므로 **가장 좁은 숫자(분당 6건)** 에 맞춘다 — API 요청(만들기·상태 묻기·판 확인)은 전부 한 줄로 세어
      10초 간격(60 ÷ 6)으로, 동시에 하나만. 만들기는 `Prefer: wait=60`(공식 동기 모드 상한 60). 끝나지 않았으면 상태를 10초 간격으로
      최대 12번(2분 상한). 200·201 이 아닌 응답(429·402·401·403)이 한 번이라도 오면 남은 사진은 보내지 않고 멈춘다. 자동 재시도 없음.

■ 6-00: 하위 명령·요청에는 전부 상한(timeout)이 있다 · 끝나는 조건이 없는 반복이 없다 · 받은 그림은 한 번만 풀어(디코드) RGBA 로
    맞추고 투명 여부·크기를 같이 잰다 · 지문(sha256)은 이 모듈이 재지 않는다(부르는 쪽이 받은 바이트로 한 번).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

# ── Cloudflare(본인 계정 누끼 Worker) — 볼케이노 서비스 표 API_SERVICES["cf_nukki"] 와 같은 자리·이름 ──────────────
CONF = "~/.volcano/keys/cf_nukki"          # 서비스 표 file
ENV = "VOLCANO_CF_NUKKI"                    # 서비스 표 env_var — 값은 CONF 와 같은 JSON
HEADER = "x-volcano-nukki"                  # 서비스 표 header
WORKER = "volcano-nukki"
WRANGLER = "wrangler@4.142.0"               # 고정 판(2026-09-27 공개 · 2주 넘은 판)
PARALLEL = 20                               # 사장님 결정 2026-10-13(머리말)
TIMEOUT_S = 120                             # 한 장 응답 상한(실측 장당 3~4초)
LOGIN_TIMEOUT_S = 600                       # 브라우저에서 Allow 를 누를 때까지
CHECK_TRIES = 6                             # 연결 직후 시험 한 장: 비밀이 퍼지기 전 401 만 다시 묻는다(5초 × 6 = 30초 상한)
CHECK_GAP_S = 5
UA = "volcano-runner-nukki/1.0"

WORKER_JS = r"""export default {
  async fetch(req, env) {
    if (req.method !== "POST") return new Response("POST only", {status: 405});
    if (!env.K || req.headers.get("%s") !== env.K) return new Response("no", {status: 401});
    const r = (await env.IMAGES.input(req.body).transform({segment: "foreground"}).output({format: "image/png"})).response();
    return new Response(r.body, {status: r.status, headers: {"content-type": "image/png"}});
  }
};
""" % HEADER

WRANGLER_TOML = """name = "%s"
main = "index.js"
compatibility_date = "2026-09-01"
workers_dev = true
[images]
binding = "IMAGES"
""" % WORKER

# ── Replicate(본인 열쇠 · 유료) — 서비스 표 API_SERVICES["replicate"] 와 같은 자리 ──────────────────────────────
REP_API = "https://api.replicate.com/v1"
REP_MODEL = "men1scus/birefnet"
REP_ENV = ("REPLICATE_API_TOKEN",)          # 서비스 표 env_var(+ env_aliases)
REP_KEY_FILE = "~/.volcano/keys/replicate"  # 서비스 표 file
REP_GAP_S = 10.0                            # 공식 «분당 최대 6건»(머리말) — 60 ÷ 6
REP_POLL_MAX = 12                           # 상태 묻기 상한(10초 × 12 = 2분)
REP_SYNC_WAIT = 60                          # Prefer: wait 초(공식 동기 모드 상한 60)
REP_TIMEOUT_S = 90                          # 만들기 밖의 API 요청 한 건 상한
_rep = {"last": None, "version": None}       # last = 마지막 API 요청 시각(time.monotonic) · None = 아직 안 보냄
_rep_lock = threading.Lock()                 # 간격 줄은 이 프로세스 하나 — 동시에 하나만 보낸다


class NukkiError(RuntimeError):
    """누끼 한 장·한 요청의 실패 — code(기계가 가르는 이름)와 사람이 읽을 말. 부르는 쪽이 멈춤으로 바꾼다(여기서 삼키지 않는다)."""

    def __init__(self, code, message, refused=False):
        super().__init__(message)
        self.code = code
        self.refused = refused              # True = 서비스가 거부했다(열쇠·한도·잔액) — 이 실행의 남은 요청을 보내지 않는다


def this_file() -> str:
    return os.path.abspath(__file__)


def connect_command() -> str:
    """연결 명령 한 줄 — 이 PC 의 이 파일 경로 그대로(윈도우·맥 같은 꼴 · 빈칸이 있어도 따옴표로)."""
    return f'python "{this_file()}" connect'


# ── 연결 정보·열쇠 ───────────────────────────────────────────────────────────

def conf() -> dict | None:
    """Cloudflare 연결 정보 {url, key} 또는 None(없거나 모양이 틀림 — 연결을 다시 하라고 말한다)."""
    raw = os.environ.get(ENV, "").strip()
    p = os.path.expanduser(CONF)
    if not raw and os.path.isfile(p):
        with open(p, encoding="utf-8-sig") as fh:
            raw = fh.read().strip()
    if not raw:
        return None
    try:
        c = json.loads(raw)
    except ValueError:
        return None
    if not (isinstance(c, dict) and str(c.get("url", "")).startswith("https://") and len(str(c.get("key", ""))) >= 20):
        return None
    return {"url": c["url"], "key": c["key"]}


def rep_key() -> str | None:
    """Replicate 열쇠(환경변수 → ~/.volcano/keys/replicate) 또는 None. 값은 어디에도 찍지 않는다."""
    k = next((v for v in (os.environ.get(e, "").strip() for e in REP_ENV) if v), "")
    p = os.path.expanduser(REP_KEY_FILE)
    if not k and os.path.isfile(p):
        with open(p, encoding="utf-8-sig") as fh:
            k = fh.read().strip()
    return k or None


def engine() -> str | None:
    """누끼 엔진 — «cloudflare»(연결됨) · «replicate»(연결 안 했고 열쇠 있음) · None(둘 다 없음). 고르는 곳은 여기 한 자리."""
    if conf() is not None:
        return "cloudflare"
    return "replicate" if rep_key() else None


def not_connected_text() -> str:
    return ("누끼 엔진이 없습니다 — 본인 Cloudflare 를 한 번 연결하거나(월 5,000장 무료 · `" + connect_command() + "` · 브라우저에서 Allow "
            "한 번) Replicate 열쇠(유료 · 환경변수 " + " · ".join(REP_ENV) + " 또는 " + REP_KEY_FILE
            + " · https://replicate.com → Account → API tokens)를 넣으세요.")


# ── 받은 그림 ─────────────────────────────────────────────────────────────────

def is_png(b: bytes) -> bool:
    return b[:8] == b"\x89PNG\r\n\x1a\n"


def finish(png: bytes) -> tuple[bytes, bool, tuple[int, int]]:
    """받은 PNG 를 **한 번** 풀어 (RGBA PNG 바이트, 투명한 곳이 있나, (가로, 세로)).
    흑백 사진은 Cloudflare 가 LA(흑백+투명) PNG 로 돌려준다(실측 20장 중 3장) — Replicate 결과와 같은 RGBA 로 맞춘다.
    이미 RGBA 면 바이트를 다시 굽지 않는다."""
    from PIL import Image
    with Image.open(io.BytesIO(png)) as im:
        size = im.size
        out = im if im.mode == "RGBA" else im.convert("RGBA")
        transparent = out.getchannel("A").getextrema()[0] < 255
        if im.mode == "RGBA":
            return png, transparent, size
        buf = io.BytesIO()
        out.save(buf, "PNG")
        return buf.getvalue(), transparent, size


def rgba(png: bytes) -> bytes:
    return finish(png)[0]


# ── Cloudflare 한 장 ──────────────────────────────────────────────────────────

def cut(c: dict, data: bytes) -> bytes:
    """Cloudflare 로 한 장(받은 PNG 바이트 그대로 — RGBA 맞추기는 부르는 쪽). 200·PNG 가 아니면 그대로 올려 보낸다(재시도 없음)."""
    req = urllib.request.Request(c["url"], data=data, method="POST",
                                 headers={HEADER: c["key"], "Content-Type": "application/octet-stream", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        body = r.read()
    if not is_png(body):
        raise NukkiError("cloudflare_not_png", "Cloudflare 누끼 응답이 PNG 가 아닙니다", refused=True)
    return body


def _cf_error(name: str, error: Exception) -> NukkiError:
    """Cloudflare 실패 → 사람 말(무엇·어떻게). 어느 실패든 이 실행의 남은 사진은 보내지 않는다(refused)."""
    if isinstance(error, NukkiError):
        return NukkiError(error.code, f"{name}: {error}", refused=True)
    if isinstance(error, urllib.error.HTTPError):
        try:
            body = error.read().decode("utf-8", "replace")[:300]
        except OSError:
            body = ""
        hint = (f" — `{connect_command()}` 로 다시 연결하세요" if error.code == 401 else
                " — 대시보드 Images «Manage plan»(한도·요금)을 확인하세요")
        return NukkiError(f"cloudflare_http_{error.code}", f"{name}: 응답 {error.code} {body}{hint}", refused=True)
    return NukkiError("cloudflare_connection", f"{name}: 연결 오류 {type(error).__name__} {str(error)[:200]}", refused=True)


# ── Replicate 한 장 ───────────────────────────────────────────────────────────

def _rep_call(method: str, url: str, k: str, body: dict | None = None, headers: dict | None = None,
              timeout: int = REP_TIMEOUT_S) -> dict:
    """API 요청 한 건 — 간격 줄(10초)을 지난 뒤 보낸다. 200·201 이 아니면 거부(NukkiError refused)."""
    with _rep_lock:
        if _rep["last"] is not None:
            wait = REP_GAP_S - (time.monotonic() - _rep["last"])
            if wait > 0:
                time.sleep(wait)
        h = dict(headers or {}, Authorization=f"Bearer {k}", **{"User-Agent": UA})
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, text = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            try:
                text = error.read().decode("utf-8", "replace")
            except OSError:
                text = ""
            status = error.code
        finally:
            _rep["last"] = time.monotonic()
    if status not in (200, 201):
        where = url.rsplit("/v1", 1)[-1]
        raise NukkiError(f"replicate_http_{status}", f"Replicate {method} {where} 응답 {status}: {text[:400]}", refused=True)
    return json.loads(text)


def _rep_version(k: str) -> str:
    if not _rep["version"]:
        _rep["version"] = (_rep_call("GET", f"{REP_API}/models/{REP_MODEL}", k).get("latest_version") or {})["id"]
    return _rep["version"]


def _as_png(path: str) -> tuple[bytes, tuple[int, int]]:
    """보낼 PNG 바이트와 크기 — 파일을 한 번만 연다(PNG 가 아니면 PNG 로 바꿔 보낸다)."""
    from PIL import Image
    with Image.open(path) as im:
        size = im.size
        if im.format != "PNG":
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "PNG")
            return buf.getvalue(), size
    with open(path, "rb") as fh:
        return fh.read(), size


def rep_cut(path: str, k: str) -> bytes:
    """Replicate BiRefNet 로 한 장 → 받은 PNG 바이트. 실패하면 NukkiError(재시도 없음)."""
    name = os.path.basename(path)
    data, (w, h) = _as_png(path)
    body = {"version": _rep_version(k), "input": {"image": "data:image/png;base64," + base64.b64encode(data).decode(),
                                                   "resolution": f"{w}x{h}"}}
    pr = _rep_call("POST", f"{REP_API}/predictions", k, body=body, headers={"Prefer": f"wait={REP_SYNC_WAIT}"},
                   timeout=REP_SYNC_WAIT + 30)
    done = ("succeeded", "failed", "canceled")
    for _ in range(REP_POLL_MAX):
        if pr.get("status") in done:
            break
        pr = _rep_call("GET", pr["urls"]["get"], k)
    if pr.get("status") not in done:
        raise NukkiError("replicate_timeout", f"Replicate 누끼가 {int(REP_GAP_S * REP_POLL_MAX)}초 안에 끝나지 않았습니다({name})")
    if pr.get("status") != "succeeded":
        raise NukkiError("replicate_failed", f"Replicate 누끼 실패({name}): {pr.get('status')} {str(pr.get('error'))[:300]}")
    out = pr.get("output")
    out = out[0] if isinstance(out, list) else out
    try:
        with urllib.request.urlopen(urllib.request.Request(out, headers={"User-Agent": UA}), timeout=REP_TIMEOUT_S) as r:
            got = r.read()
    except (urllib.error.URLError, OSError) as error:
        raise NukkiError("replicate_download", f"누끼 결과를 받지 못했습니다({name}): {str(error)[:200]}") from error
    if not is_png(got):
        raise NukkiError("replicate_not_png", f"Replicate 누끼 결과가 PNG 가 아닙니다({name})")
    return got


# ── 여러 장 ──────────────────────────────────────────────────────────────────

NOT_STARTED = ("not_started_after_stop", "앞선 누끼가 거부·실패해 이 사진은 보내지 않았습니다(자동으로 다시 보내지 않음).")


def cut_files(jobs, write, log=None) -> dict:
    """jobs = [(열쇠, 원본 그림 경로), ...] 를 engine() 이 고른 엔진으로 오린다. 한 장 받을 때마다 write(열쇠, RGBA PNG 바이트, 투명한 곳이
    있나, (가로, 세로)) 를 부른다(Cloudflare 는 여러 스레드가 부른다 — write 는 스레드 안전해야 한다).

    돌려주는 것 {engine, done: [열쇠…], errors: {열쇠: {code, message}}, refused: None | {code, message}}.
    · 엔진이 없으면 아무것도 보내지 않고 refused={code: nukki_not_connected, message: 무엇을 하면 되는지}.
    · 거부·실패 한 번 → 남은 사진은 보내지 않는다(errors 의 not_started_after_stop). Cloudflare 실패를 Replicate 로 넘기지 않는다.
    · write 가 올린 예외(디스크 등)는 삼키지 않는다."""
    jobs = list(jobs)
    out = {"engine": engine(), "done": [], "errors": {}, "refused": None}
    if not jobs:
        return out
    if out["engine"] is None:
        out["refused"] = {"code": "nukki_not_connected", "message": not_connected_text()}
        for key, _ in jobs:
            out["errors"][key] = {"code": NOT_STARTED[0], "message": not_connected_text()}
        return out
    say = log or (lambda *_: None)
    lock = threading.Lock()
    stop = threading.Event()

    def failed(key, error):
        with lock:
            stop.set()
            out["errors"][key] = {"code": error.code, "message": str(error)[:400]}
            if error.refused and out["refused"] is None:
                out["refused"] = {"code": error.code, "message": str(error)[:400]}

    def got(key, png, how):
        data, transparent, size = finish(png)
        write(key, data, transparent, size)
        with lock:
            out["done"].append(key)
            say(f"  누끼 {len(out['done'])}/{len(jobs)} {key} ({how})")

    if out["engine"] == "cloudflare":
        from concurrent.futures import ThreadPoolExecutor
        c = conf()

        def one(job):
            key, path = job
            if stop.is_set():
                return
            with open(path, "rb") as fh:
                data = fh.read()
            try:
                png = cut(c, data)
            except (urllib.error.URLError, OSError, NukkiError) as error:   # HTTPError 는 URLError 의 아래 · 시간 초과는 OSError
                failed(key, _cf_error(os.path.basename(path), error))
                return
            got(key, png, "Cloudflare")

        with ThreadPoolExecutor(max_workers=min(PARALLEL, len(jobs))) as ex:
            for fut in [ex.submit(one, job) for job in jobs]:
                fut.result()                      # 거부 밖의 예외(write 의 디스크 오류 등)는 올린다
    else:
        k = rep_key()
        for key, path in jobs:
            if stop.is_set():
                break
            try:
                png = rep_cut(path, k)
            except NukkiError as error:
                failed(key, error)
                continue
            except (urllib.error.URLError, OSError) as error:
                failed(key, NukkiError("replicate_connection", f"Replicate 연결 오류({os.path.basename(path)}): {str(error)[:200]}",
                                       refused=True))
                continue
            got(key, png, "Replicate")
    for key, _ in jobs:
        if key not in out["errors"] and key not in out["done"]:
            out["errors"][key] = {"code": NOT_STARTED[0], "message": NOT_STARTED[1]}
    return out


# ── 연결(처음 한 번) ─────────────────────────────────────────────────────────

def _npx() -> str | None:
    for name in (("npx.cmd", "npx") if os.name == "nt" else ("npx",)):
        p = shutil.which(name)
        if p:
            return p
    return None


def _wr(npx: str, args: list, cwd: str, timeout: int, stdin: str | None = None):
    """wrangler 한 번(timeout 필수). cwd 는 이 도구가 만든 빈 임시 폴더 — 위 폴더의 다른 설정 파일을 집어 오지 않게."""
    return subprocess.run([npx, "--yes", WRANGLER, *args], cwd=cwd, input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _tiny_png() -> bytes:
    """연결 시험 한 장(256×256 회색 바탕 + 파란 타원) — 표준 라이브러리로 PNG 를 직접 쓴다(★10-23 setup 연결은 실행기 환경 밖
    회원 python 에서도 돈다 · 시험 그림 하나 때문에 PIL 에 기대지 않는다)."""
    import struct
    import zlib
    w = h = 256
    cx, cy = w // 2, h // 2                             # 타원 가운데 = 그림 가운데(크기에서 유도 · 상수를 따로 적지 않는다)
    rows = bytearray()
    for y in range(h):
        rows.append(0)                                  # 필터 없음
        dy = (y - cy) / 88.0
        for x in range(w):
            dx = (x - cx) / 64.0
            rows += b"\x28\x5a\xc8" if dx * dx + dy * dy <= 1.0 else b"\xe6\xe6\xe6"

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


def connect() -> None:
    npx = _npx()
    if not npx:
        raise SystemExit("Node.js(npx)가 없어 Cloudflare 누끼를 연결할 수 없다 — https://nodejs.org 에서 LTS 를 설치한 뒤 다시. "
                         "(연결하지 않으면 Replicate 열쇠로 오린다)")
    with tempfile.TemporaryDirectory(prefix="volcano-nukki-") as d:
        with open(os.path.join(d, "index.js"), "w", encoding="utf-8") as fh:
            fh.write(WORKER_JS)
        with open(os.path.join(d, "wrangler.toml"), "w", encoding="utf-8") as fh:
            fh.write(WRANGLER_TOML)
        who = _wr(npx, ["whoami"], d, 180)
        if who.returncode != 0 or "not authenticated" in (who.stdout + who.stderr).lower():
            print("브라우저가 열리면 Cloudflare 에 로그인하고 «Allow» 를 한 번 누르세요.", flush=True)
            lg = _wr(npx, ["login"], d, LOGIN_TIMEOUT_S)
            if lg.returncode != 0:
                raise SystemExit("Cloudflare 로그인이 끝나지 않았다: " + (lg.stderr or lg.stdout)[-500:])
        dep = _wr(npx, ["deploy"], d, 300)
        out = dep.stdout + dep.stderr
        if dep.returncode != 0:
            hint = (" — workers.dev 하위 주소를 아직 안 만들었으면 대시보드 Workers & Pages 를 한 번 열어 주소를 정한 뒤 다시"
                    if "subdomain" in out.lower() else "")
            raise SystemExit("누끼 Worker 를 올리지 못했다: " + out[-600:] + hint)
        m = re.search(r"https://%s\.[A-Za-z0-9-]+\.workers\.dev" % WORKER, out)
        if not m:
            raise SystemExit("누끼 Worker 는 올렸는데 주소를 못 읽었다: " + out[-400:])
        key = secrets.token_urlsafe(32)
        sp = _wr(npx, ["secret", "put", "K", "--name", WORKER], d, 180, stdin=key)
        if sp.returncode != 0:
            raise SystemExit("누끼 Worker 비밀을 넣지 못했다: " + (sp.stderr or sp.stdout)[-500:])
    c = {"url": m.group(0), "key": key}
    png = _tiny_png()
    for i in range(CHECK_TRIES):                    # 상한 있음 — 비밀이 퍼지기 전의 401 만 다시 묻는다
        try:
            cut(c, png)
            break
        except urllib.error.HTTPError as e:
            if e.code != 401 or i == CHECK_TRIES - 1:
                hint = " — 대시보드 Images «Manage plan» 에서 $0 Continue 를 했는지 확인" if e.code != 401 else ""
                raise SystemExit(f"누끼 Worker 시험 한 장이 실패했다(응답 {e.code}){hint} — 연결 정보는 저장하지 않았다")
        time.sleep(CHECK_GAP_S)
    p = os.path.expanduser(CONF)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".part", "w", encoding="utf-8") as fh:
        json.dump(c, fh)
    os.replace(p + ".part", p)
    if os.name != "nt":
        os.chmod(p, 0o600)
    print(json.dumps({"ok": True, "connected": True, "worker": WORKER, "conf": CONF}, ensure_ascii=False))


def main(argv: list) -> None:
    cmd = argv[0] if argv else ""
    if cmd == "connect":
        connect()
    elif cmd == "status":
        print(json.dumps({"connected": conf() is not None, "engine": engine(), "conf": CONF}, ensure_ascii=False))
    else:
        raise SystemExit(f'사용: python "{this_file()}" connect | status')


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
