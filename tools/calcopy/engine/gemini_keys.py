# -*- coding: utf-8 -*-
"""칼카피 엔진의 무료 제미나이 키 목록 — **여기 한 곳**에서만 고른다(analyze·compare·다른 도구 공용).

이름 패턴으로 읽는다(값 하드코딩·출력 금지): GEMINI_API_KEY, GEMINI_API_KEY_<n>, GEMINI_BRIEFING_KEY*,
SHORTS_GEMINI_KEY, SHORTS_GEMINI_KEY_<n>(숏템 공용 14개, 2026-10-16 사장님). 환경변수가 .env 보다 먼저.
순서: GEMINI_API_KEY* → SHORTS_GEMINI_KEY* (번호순). 같은 값은 한 번만. 429면 부르는 쪽이 다음 키로 돈다.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATTERNS = (r"GEMINI_API_KEY(?:_\d+)?", r"GEMINI_BRIEFING_KEY(?:_\d+)?", r"SHORTS_GEMINI_KEY(?:_\d+)?")


def _num(name: str) -> int:
    m = re.search(r"_(\d+)$", name)
    return int(m.group(1)) if m else 1


def key_names(env_file: str | None = None) -> list[str]:
    """찾은 키 이름(값 말고) — 진단·보고용."""
    return [n for n, _ in _pairs(env_file)]


def _pairs(env_file: str | None = None) -> list[tuple[str, str]]:
    env_file = env_file or str(ROOT / ".env")
    found: dict[str, str] = {}
    if os.path.exists(env_file):
        for line in open(env_file, encoding="utf-8"):
            m = re.match(r"^([A-Z0-9_]+)=(\S+)", line.strip())
            if m:
                found[m.group(1)] = m.group(2).strip()
    for k, v in os.environ.items():
        if v.strip():
            found[k] = v.strip()
    out, seen = [], set()
    for pat in PATTERNS:
        names = sorted((n for n in found if re.fullmatch(pat, n)), key=_num)
        for n in names:
            if found[n] not in seen:
                seen.add(found[n])
                out.append((n, found[n]))
    return out


def keys(env_file: str | None = None) -> list[str]:
    return [v for _, v in _pairs(env_file)]


# ── 하루 예산·429 장부(2026-10-16 3판) ──────────────────────────────────────
# 무료 등급 한도는 태평양 자정(KST 16:00~17:00)에 풀린다. 오늘 429 난 (키, 모델)과 오늘 쓴 횟수를 파일 하나에 적어
# 모든 프로세스(분석기·워커·대조)가 같이 본다 — 바닥난 키로 재시도하며 시간을 버리지 않게(1판 편당 429 재시도 14회).
# 키 값은 적지 않는다(이름만).
import json as _json
import time as _time
from datetime import datetime as _dt, timezone as _tz, timedelta as _td

QUOTA_FILE = Path(os.environ.get("CALCOPY_QUOTA_FILE") or (Path.home() / ".calcopy_gemini_quota.json"))
DAILY_BUDGET = int(os.environ.get("CALCOPY_GEMINI_DAILY_BUDGET") or 250)   # 키·모델당 하루 성공 호출 상한(넘으면 그 키는 오늘 안 씀)


def quota_day() -> str:
    """무료 한도 날짜(태평양 시간 날짜)."""
    try:
        from zoneinfo import ZoneInfo
        return _dt.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001 — 시간대 자료가 없으면 UTC-7 로
        return (_dt.now(_tz.utc) - _td(hours=7)).strftime("%Y-%m-%d")


def _load() -> dict:
    try:
        d = _json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 없거나 깨졌으면 새로
        d = {}
    if d.get("day") != quota_day():
        d = {"day": quota_day(), "dead": {}, "used": {}}
    return d


def _save(d: dict) -> None:
    try:
        tmp = QUOTA_FILE.with_suffix(".tmp")
        tmp.write_text(_json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, QUOTA_FILE)
    except Exception:  # noqa: BLE001 — 장부를 못 써도 호출은 계속(다음 프로세스가 다시 429를 겪을 뿐)
        pass


MINUTE_COOLDOWN_S = 65             # 분당 한도 429 → 이만큼만 쉬고 다시 쓴다


def retry_after_s(err: str) -> float | None:
    """구글이 알려 주는 '다시 시도' 시간(초): 'Please retry in 6h2m47.8s' / retryDelay '41s'. 없으면 None."""
    m = re.search(r"retry in\s+((?:\d+h)?(?:\d+m)?(?:[\d.]+s)?)", err) or re.search(r"retryDelay['\"]?\s*:\s*['\"]([\d.]+s)", err)
    if not m or not m.group(1):
        return None
    t = 0.0
    for v, u in re.findall(r"([\d.]+)([hms])", m.group(1)):
        t += float(v) * {"h": 3600, "m": 60, "s": 1}[u]
    return t or None


def rate_scope(err: str) -> str:
    """429 글의 quotaId 로 한도 범위를 가른다: 'minute'(분당·잠깐 쉼) / 'day'(오늘 끝).
    10-18 실측: 429 를 전부 '오늘 끝'으로 적어 gemini-3.5-flash 가 성공 326회 만에 161키 전부 '죽음' — 분당 한도까지 하루를 버렸다."""
    if "PerMinute" in err or "per minute" in err.lower() or "PerSecond" in err:
        return "minute"
    return "day"


def is_dead(name: str, model: str, d: dict | None = None) -> bool:
    d = d or _load()
    k = f"{name}|{model}"
    v = d["dead"].get(k)
    if v is not None:
        if isinstance(v, (int, float)):        # 분당 한도 → 풀리는 시각(epoch)
            if _time.time() < v:
                return True
        else:                                  # 'HH:MM:SS' = 오늘 끝(예전 꼴 포함)
            return True
    return d["used"].get(k, 0) >= DAILY_BUDGET


def mark(name: str, model: str, status: str, err: str = "") -> None:
    """status: '429'(err 의 quotaId 가 분당이면 65초, 아니면 오늘 끝) / 'ok'(쓴 횟수 +1)."""
    d = _load()
    k = f"{name}|{model}"
    if status == "429":
        ra = retry_after_s(err)             # 구글이 준 시간이 있으면 그대로(가장 정확), 없으면 분당=65초 / 그 밖=오늘 끝
        d["dead"][k] = (_time.time() + ra + 2) if ra else             ((_time.time() + MINUTE_COOLDOWN_S) if rate_scope(err) == "minute" else _time.strftime("%H:%M:%S"))
    elif status == "ok":
        d["used"][k] = d["used"].get(k, 0) + 1
        d["dead"].pop(k, None)            # 성공했으면 '죽음' 표시는 틀린 것 — 바로 지운다
    _save(d)


# ── 죽은 키 바로 넘기기 (사장님 10-18 "키 죽은 건 바로 넘기는 걸로 체크해 실시간으로") ─────────────
# 뜯기 102편 실측: 호출 1,919회 중 키 무효 400 이 108회(7분)·404 19회 — 무효 키는 '오늘' 장부에만 적혀 날이 바뀌면 다시 불렀고,
# 404 는 프로세스 메모리(_DEAD)에만 있어 실행마다 다시 불렀다. → 날을 넘어 남는 '고장 장부'(BROKEN_FILE)를 둔다.
# 키는 값 지문(sha256 앞 12자)으로 적는다 — .env 에서 같은 이름에 새 키가 들어오면 지문이 달라져 자동으로 다시 쓴다. 키 값은 안 적는다.
import hashlib as _hl
import threading as _th

BROKEN_FILE = Path(os.environ.get("CALCOPY_BROKEN_FILE") or (Path.home() / ".calcopy_gemini_broken.json"))
NOMODEL_TTL_S = 7 * 86400          # 404(그 키에 그 모델 없음)는 7일 뒤 다시 확인
_BLOCK = _th.Lock()
_PROBED: set = set()                # 이번 프로세스에서 미리 확인한 (지문, 모델)


def fp(key: str) -> str:
    return _hl.sha256(key.encode("utf-8")).hexdigest()[:12]


def _bload() -> dict:
    try:
        d = _json.loads(BROKEN_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 없거나 깨졌으면 새로
        d = {}
    d.setdefault("key", {})
    d.setdefault("nomodel", {})
    return d


def _bsave(d: dict) -> None:
    try:
        tmp = BROKEN_FILE.with_suffix(".tmp")
        tmp.write_text(_json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, BROKEN_FILE)
    except Exception:  # noqa: BLE001 — 못 써도 호출은 계속(이 프로세스 메모리 _DEAD 가 막는다)
        pass


def broken_reason(err: str) -> str | None:
    """오류 글 → 키 고장 분류. 'key'=키 자체가 죽음(무효·권한·정지·결제) / 'nomodel'=그 모델만 없음 / None=일시(429·503 등)."""
    if "API key not valid" in err or "API_KEY_INVALID" in err or "API key expired" in err:
        return "key"
    if "PERMISSION_DENIED" in err or " 403" in err or err.startswith("403") or "SERVICE_DISABLED" in err \
            or "has been suspended" in err or "CONSUMER_SUSPENDED" in err:
        # ★'billing' 글자로 판정하지 마라 — 무료 하루 한도 429 도 "check your plan and billing details" 라고 쓴다(10-18 오판 11키)
        return "key"
    # 10-18 실측(161키 동시 1회): 402 'Your prepayment credits are depleted' 4키 · 429 인데 quota_limit_value '0'(그 프로젝트 한도 0 = 영영 못 씀) 1키
    if err.startswith("402") or "prepayment credits" in err or "credits are depleted" in err:
        return "key"
    if ("429" in err or "RESOURCE_EXHAUSTED" in err) and re.search(r"quota_limit_value['\"]?\s*:\s*['\"]0['\"]", err):
        return "key"
    if "404" in err or "NOT_FOUND" in err:
        return "nomodel"
    return None


def mark_broken(key: str, model: str | None, kind: str, why: str = "") -> None:
    """kind='key' → 그 키 모든 모델 영구 제외 / 'nomodel' → 그 키·모델 7일 제외."""
    with _BLOCK:
        d = _bload()
        f = fp(key)
        if kind == "key":
            d["key"][f] = {"at": _time.strftime("%Y-%m-%d %H:%M:%S"), "why": why[:80]}
        elif kind == "nomodel" and model:
            d["nomodel"][f"{f}|{model}"] = _time.time()
        _bsave(d)


def is_broken(key: str, model: str, d: dict | None = None) -> bool:
    d = d or _bload()
    f = fp(key)
    if f in d["key"]:
        return True
    t = d["nomodel"].get(f"{f}|{model}")
    return bool(t) and _time.time() - t < NOMODEL_TTL_S


def probe(model: str, ks: list[str] | None = None, workers: int = 32, timeout_s: float = 20.0) -> dict:
    """키를 **동시에** 1토큰 실제 호출로 확인 → 죽은 키(무효·402 선불 소진·한도 0·권한)는 고장 장부, 살아 있으면 오늘 '죽음' 표시를 지운다.
    models.get 은 402·한도 0 을 못 잡아서(10-18 실측) 실제 호출을 쓴다. **키·모델당 하루 한 번**(모든 세션이 같은 장부를 본다).
    반환 {'checked','ok','broken','nomodel','busy','sec'}."""
    from concurrent.futures import ThreadPoolExecutor
    ks = ks if ks is not None else keys()
    day = quota_day()
    d = _bload()
    pr = d.setdefault("probed", {})
    todo = [k for k in ks if pr.get(f"{fp(k)}|{model}") != day and not is_broken(k, model, d)]
    t0 = _time.time()
    out = {"checked": 0, "ok": 0, "broken": 0, "nomodel": 0, "busy": 0}
    if not todo:
        out["sec"] = 0.0
        return out

    def one(k):
        from google import genai
        from google.genai import types
        c = genai.Client(api_key=k, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
        try:
            c.models.generate_content(model=model, contents="ok",
                                      config=types.GenerateContentConfig(max_output_tokens=1, temperature=0))
            return k, None
        except Exception as e:  # noqa: BLE001 — 분류만 하고 넘긴다
            return k, str(e)

    name_of = dict(zip(keys(), key_names()))
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(todo)))) as ex:
        for k, err in ex.map(one, todo):
            out["checked"] += 1
            kind = broken_reason(err) if err else None
            if kind:
                mark_broken(k, model, kind, err or "")
                out["broken" if kind == "key" else "nomodel"] += 1
            elif err:
                out["busy"] += 1          # 429 분당·503 등 일시 — 장부는 손대지 않는다
            else:
                out["ok"] += 1
                if k in name_of:
                    clear_dead(name_of[k], model)
            with _BLOCK:
                dd = _bload()
                dd.setdefault("probed", {})[f"{fp(k)}|{model}"] = day
                _bsave(dd)
    out["sec"] = round(_time.time() - t0, 1)
    return out


def clear_dead(name: str, model: str) -> None:
    """살아 있는 게 확인된 키의 '오늘 죽음' 표시를 지운다(잘못 적힌 표시를 실시간으로 되살림)."""
    d = _load()
    if d["dead"].pop(f"{name}|{model}", None) is not None:
        _save(d)


_BG: dict = {}                      # 모델 → 뒤에서 도는 확인 스레드(프로세스당 하나)
PROBE_LOG: list = []                # 뒤 확인 결과(호출 장부에 붙일 수 있게)


def probe_bg(model: str, ks: list[str] | None = None) -> None:
    """probe 를 데몬 스레드로 — 본 호출은 안 기다린다. 확인이 끝나는 대로 고장 장부에 적혀 다음 호출부터 바로 넘긴다."""
    if os.environ.get("CALCOPY_GEMINI_PROBE", "1") == "0" or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    with _BLOCK:
        if model in _BG:
            return
        def run():
            try:
                PROBE_LOG.append({"model": model, **probe(model, ks, workers=32, timeout_s=20.0)})
            except Exception as e:  # noqa: BLE001 — 확인 실패는 장부에 남기고 본 호출엔 영향 없음
                PROBE_LOG.append({"model": model, "failed": str(e)[:80]})
        t = _th.Thread(target=run, name=f"gemini-probe-{model}", daemon=True)
        _BG[model] = t
        t.start()


def quota_report() -> dict:
    """오늘 장부 요약(이름만): 모델별 살아 있는 키 수·429 키·쓴 횟수."""
    d = _load()
    names = key_names()
    models = sorted({k.split("|", 1)[1] for k in list(d["dead"]) + list(d["used"])})
    return {"day": d["day"], "budget": DAILY_BUDGET,
            "models": {m: {"alive": sum(1 for n in names if not is_dead(n, m, d)), "keys": len(names),
                           "dead": sorted(k.split("|")[0] for k in d["dead"] if k.endswith("|" + m)),
                           "used": sum(v for k, v in d["used"].items() if k.endswith("|" + m))} for m in models}}
