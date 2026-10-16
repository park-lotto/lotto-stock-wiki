# -*- coding: utf-8 -*-
"""소재창고 카테고리 워커 — PC 실행기 (관제 097, 2026-10-16).
서버 규격: docs/superpowers/specs/2026-10-16-소재창고-api.md (판단 주인 shopping_shorts/calcopy_topics.py)
설계: docs/superpowers/specs/2026-10-16-소재창고-보드-워커-design.md

    PYTHONUTF8=1 py tools/calcopy/engine/worker.py --category 식품 --track bench --channel yummyknow --once
    PYTHONUTF8=1 py tools/calcopy/engine/worker.py --category 식품 --track discover --channel yummyknow --loop
    (로컬 시험) --server http://127.0.0.1:8851 --cookie <dash_auth 값>

한 바퀴(tick) = claim_next(steps) → 받은 단계를 worker_steps 로 돌림 → 산출물 upload → advance(data·outputs·cost).
  · 실패는 release(error="이유") — 조용한 통과 없음. 사람 판정(review/reject)은 워커가 쓰지 않는다.
  · 할 일이 없으면 claim_next 가 준 reasons(비용 상한·잠김)를 로그에 남기고, --find-every 분마다 소재 찾기(find)를 돈다.
  · heartbeat = 잡은 소재에 별도 스레드(기본 60초, doing=단계). 서버는 11분 넘게 신호가 없으면 잠금을 푼다.
  · 검수 자리(plan_review·final_review)·남의 잠금은 서버가 409 로 거절한다 — 워커는 그 이유를 그대로 로그에 남긴다.
판단 주인: 다음 일·상태·잠금·비용 상한 = 서버 calcopy_topics · 단계→엔진 = worker_steps.STEPS · 돌기 = Worker.tick() (이 파일).
인증: 관리자 세션 쿠키 dash_auth. 라이브는 tools/live_admin.admin_cookie()(서버에서 2시간짜리 관리자 세션 발급, 비밀번호 없음)를
      재사용하고 403 이면 한 번 다시 발급한다. --cookie / CALCOPY_ADMIN_COOKIE 로 직접 줄 수도 있다(로컬 시험).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import worker_steps as WS  # noqa: E402

PREFIX = "/api/admin/calcopy/topics"
DEFAULT_SERVER = "https://shoppingshorts.duckdns.org"


class ApiError(Exception):
    def __init__(self, status: int, msg: str):
        self.status, self.msg = status, msg
        super().__init__(f"{status} {msg}")


class Api:
    """서버 API 창구 — 규격이 바뀌면 여기 한 곳만 고친다. session = requests.Session 또는 TestClient(같은 모양)."""

    def __init__(self, base: str, session=None, cookie: str | None = None, cookie_fn=None, timeout: float = 60):
        if session is None:
            import requests
            session = requests.Session()
        self.base, self.s, self.timeout, self.cookie_fn = base.rstrip("/"), session, timeout, cookie_fn
        if cookie is None and cookie_fn:
            cookie = cookie_fn()
        if cookie:
            self._set_cookie(cookie)

    def _set_cookie(self, cookie: str):
        host = urlparse(self.base).hostname or "testserver"
        self.s.cookies.set("dash_auth", cookie, domain=host if "." in host else "", path="/")

    def _req(self, method: str, path: str, retry: bool = True, **kw) -> dict:
        if self.base.startswith("http"):
            kw["timeout"] = self.timeout
        r = getattr(self.s, method)(self.base + PREFIX + path, **kw)
        if r.status_code == 403 and retry and self.cookie_fn:      # 관리자 세션 2시간 만료 → 한 번 다시 발급
            self._set_cookie(self.cookie_fn())
            return self._req(method, path, retry=False, **kw)
        try:
            j = r.json()
        except ValueError:
            j = {"error": f"HTTP {r.status_code}: {(r.text or '')[:200]}"}
        if r.status_code >= 400:
            raise ApiError(r.status_code, (j or {}).get("error") if isinstance(j, dict) else str(j)[:200])
        return j

    def claim_next(self, worker, steps):
        return self._req("post", "/claim_next", json={"worker": worker, "steps": list(steps)})

    def add(self, name, category, track, source=None, by=""):
        return self._req("post", "", json={"name": name, "category": category, "track": track, "source": source or {}, "by": by})

    def heartbeat(self, tid, worker, doing=None):
        return self._req("post", f"/{tid}/heartbeat", json={"worker": worker, "doing": doing})

    def advance(self, tid, worker, data=None, outputs=None, cost=None, note=""):
        return self._req("post", f"/{tid}/advance", json={"worker": worker, "data": data or {}, "outputs": outputs or {},
                                                         "cost": cost or {}, "note": note})

    def release(self, tid, worker, error):
        return self._req("post", f"/{tid}/release", json={"worker": worker, "error": error})

    def upload(self, tid, name, path: Path):
        # ★data= (requests·TestClient 둘 다 받는다). content= 는 httpx 전용이라 requests 에선 TypeError — 시험만 통과하고 실물에서 죽었다(10-16)
        return self._req("post", f"/{tid}/upload/{quote(name)}", data=Path(path).read_bytes())


def _cost(c: dict) -> dict:
    """서버가 받는 비용 종류만(gemini·typecast, 0 이상 정수). 0 은 빼서 보낸다."""
    return {k: int(c[k]) for k in ("gemini", "typecast") if int(c.get(k) or 0) > 0}


class Worker:
    def __init__(self, api: Api, category: str, track: str, channel: str, name: str | None = None, out_root: Path | None = None,
                 steps=WS, preset: str | None = None, hb_interval: float = 60, find_every: float = 60 * 60,
                 allowed_steps: list[str] | None = None, log=print, extra: dict | None = None):
        self.api, self.category, self.track, self.channel = api, category, track, channel
        self.name = name or f"{socket.gethostname()}-{category}-{track}"
        self.steps, self.hb_interval, self.find_every, self.log = steps, hb_interval, find_every, log
        self.allowed = [s for s in (allowed_steps or WS.STEPS) if s != "find"]
        self.ctx = WS.Ctx(out_root=Path(out_root or Path.home() / "숏템_칼카피" / "worker" / category), channel=channel,
                          category=category, track=track, preset=preset, log=log, extra=extra or {})
        self.state = {"step": None, "topic_id": None}
        self.done, self.last_find = 0, None
        self._stop = threading.Event()
        self._hb: threading.Thread | None = None
        self._lock = threading.Lock()

    # ── heartbeat(잡은 소재에만 — 서버 규격 §2) ──
    def beat(self):
        with self._lock:
            st = dict(self.state)
        if not st["topic_id"]:
            return
        try:
            self.api.heartbeat(st["topic_id"], self.name, f"{st['step']} 중")
        except Exception as e:  # noqa: BLE001 — 맥박 실패는 일을 멈출 이유가 아니다. 대신 로그에 남긴다(조용히 삼키지 않음)
            self.log(f"[heartbeat 실패] {type(e).__name__}: {e}")

    def start_heartbeat(self):
        if self._hb and self._hb.is_alive():
            return

        def loop():
            while not self._stop.wait(self.hb_interval):
                self.beat()
        self._stop.clear()
        self._hb = threading.Thread(target=loop, name="calcopy-heartbeat", daemon=True)
        self._hb.start()

    def stop_heartbeat(self):
        self._stop.set()
        if self._hb:
            self._hb.join(timeout=5)

    def _set(self, **kw):
        with self._lock:
            self.state.update(kw)

    # ── 소재 찾기(행이 없는 일 — claim 없이 add) ──
    def find(self) -> dict:
        self.last_find = time.time()
        self.log("[찾기] 새 소재 찾기")
        try:
            res = self.steps.run_step("find", None, self.ctx)
        except (WS.StepError, NotImplementedError, Exception) as e:  # noqa: BLE001 — 이유를 로그로(서버엔 행이 없어 둘 곳이 없다)
            why = e.reason if isinstance(e, WS.StepError) else f"{type(e).__name__}: {e}"
            self.log(f"[멈춤] find: {why}")
            return {"result": "error", "error": f"find: {why}"}
        ids, dup = [], []
        for r in res.get("rows") or []:
            try:
                ids.append(self.api.add(r["name"], self.category, self.track, r.get("source"), by=f"worker@{self.name}")["topic"]["id"])
            except ApiError as e:
                if e.status != 409:
                    raise
                dup.append(f"{r['name'][:30]}: {e.msg}")
        self.log(f"[찾음] 새 소재 {len(ids)}개 · 중복 {len(dup)}개")
        return {"result": "found", "ids": ids, "dup": dup}

    # ── 산출물 올리기 ──
    def _upload(self, tid, arts: dict) -> tuple[list[str], list[str]]:
        ok, bad = [], []
        for fname, p in (arts or {}).items():
            try:
                self.api.upload(tid, fname, Path(p))
                ok.append(fname)
            except Exception as e:  # noqa: BLE001 — 실패한 이름은 outputs 에서 빠지고 이유가 release/note 로 간다
                bad.append(f"{fname}: {type(e).__name__}: {str(e)[:150]}")
        return ok, bad

    # ── 한 바퀴 ──
    def tick(self) -> dict:
        """claim 1회 → 단계 1개. 결과: idle|advanced|error|found|refused"""
        c = self.api.claim_next(self.name, self.allowed)
        topic, step = c.get("topic"), c.get("step")
        if not step:
            self._set(step=None, topic_id=None)
            due = self.find_every and (self.last_find is None or time.time() - self.last_find >= self.find_every)
            if due:
                return self.find()
            self.log(f"[쉼] {'; '.join(c.get('reasons') or [])}")
            return {"result": "idle", "reasons": c.get("reasons") or []}
        tid = topic["id"]
        self._set(step=step, topic_id=tid)
        self.log(f"[받음] {step} · #{tid} {topic.get('name', '')[:40]}")
        self.beat()
        err, res = None, {}
        try:
            res = self.steps.run_step(step, topic, self.ctx)
        except WS.StepError as e:
            err, res = f"{e.reason}", {"artifacts": e.artifacts, "cost": e.cost}
        except NotImplementedError as e:
            err = f"NotImplementedError — {e}"
        except Exception as e:  # noqa: BLE001 — 어떤 예외든 이유(원문+마지막 줄)와 함께 서버에 올린다
            tb = traceback.format_exc().strip().splitlines()[-1]
            err = f"{type(e).__name__}: {str(e)[:250]} ({tb[:120]})"
        try:
            ok, bad = self._upload(tid, res.get("artifacts") or {})
            if bad:
                self.log(f"[올리기 실패] #{tid} {bad}")
            if err:
                if bad:
                    err += f" / 올리기 실패 {bad}"
                self.api.release(tid, self.name, err)
                self.log(f"[멈춤] #{tid} {step}: {err}")
                return {"result": "error", "error": err}
            outs = {k: v for k, v in (res.get("outputs") or {}).items() if v in ok}
            outs.update({Path(f).stem: f for f in ok if f not in outs.values()})
            r = self.api.advance(tid, self.name, res.get("data"), outs, _cost(res.get("cost") or {}),
                                 note=("올리기 실패: " + "; ".join(bad)) if bad else "")
        except ApiError as e:
            # 400(필수 자료 없음)·409(검수 자리·잠금) — 서버 이유 그대로. 잠금이 아직 내 것이면 release 로 이유를 남긴다
            self.log(f"[거절] #{tid} {step}: {e}")
            if e.status == 400:
                try:
                    self.api.release(tid, self.name, f"advance 거절: {e.msg}" + (f" / 올리기 실패 {bad}" if bad else ""))
                except ApiError as e2:
                    self.log(f"[release 거절] {e2}")
            return {"result": "refused", "status": e.status, "error": e.msg}
        finally:
            self._set(step=None, topic_id=None)
        self.done += 1
        self.log(f"[넘김] #{tid} {step} → {r['topic']['state']}")
        return {"result": "advanced", "topic": r["topic"]}

    def loop(self, idle_sleep: float = 60, max_ticks: int | None = None):
        self.start_heartbeat()
        n = 0
        try:
            while max_ticks is None or n < max_ticks:
                n += 1
                try:
                    r = self.tick()
                except ApiError as e:
                    self.log(f"[서버 오류] {e} — {idle_sleep}초 뒤 다시")
                    r = {"result": "server_error"}
                # ★실패(error·refused) 뒤에도 쉰다: 서버 claim_next 는 last_error 행을 다시 주므로(10-16 로컬 HTTP 실측 —
                #   같은 행 script 실패가 바로 다시 잡혔다) 쉬지 않으면 같은 실패를 매초 되풀이하며 무료 호출을 태운다
                if r["result"] in ("idle", "server_error", "error", "refused"):
                    time.sleep(idle_sleep)
        finally:
            self.stop_heartbeat()


def main(argv=None):
    ap = argparse.ArgumentParser(description="소재창고 카테고리 워커")
    ap.add_argument("--category", required=True)
    ap.add_argument("--track", required=True, choices=["bench", "discover"])
    ap.add_argument("--channel", required=True, help="배정할 채널 slug")
    ap.add_argument("--preset", help="프리셋 폴더(없으면 --channel)")
    ap.add_argument("--name")
    ap.add_argument("--server", default=os.environ.get("CALCOPY_SERVER", DEFAULT_SERVER))
    ap.add_argument("--cookie", default=os.environ.get("CALCOPY_ADMIN_COOKIE"), help="관리자 세션 dash_auth(없으면 live_admin 으로 발급)")
    ap.add_argument("--out", help="산출물 폴더(기본 ~/숏템_칼카피/worker/<카테고리>)")
    ap.add_argument("--steps", default="", help="할 일 쉼표 구분(기본 전부)")
    ap.add_argument("--find-every", type=float, default=60, help="할 일 없을 때 소재 찾기 간격(분, 0=안 함)")
    ap.add_argument("--source-kind", help="find 단계 소재 출처 유형(프리셋 manifest 에 없을 때)")
    ap.add_argument("--keywords", default="", help="find 검색어 쉼표 구분")
    ap.add_argument("--heartbeat", type=float, default=60)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    a = ap.parse_args(argv)
    cookie_fn = None
    if not a.cookie:
        from tools.live_admin import admin_cookie
        cookie_fn = admin_cookie
    extra = {k: v for k, v in {"source_kind": a.source_kind,
                               "keywords": [k.strip() for k in a.keywords.split(",") if k.strip()] or None}.items() if v}
    w = Worker(Api(a.server, cookie=a.cookie, cookie_fn=cookie_fn), a.category, a.track, a.channel, a.name,
               Path(a.out) if a.out else None, preset=a.preset, hb_interval=a.heartbeat, find_every=a.find_every * 60,
               allowed_steps=[s.strip() for s in a.steps.split(",") if s.strip()] or None, extra=extra)
    if a.once:
        w.start_heartbeat()
        try:
            r = w.tick()
        finally:
            w.stop_heartbeat()
        print(json.dumps({k: v for k, v in r.items() if k != "topic"}, ensure_ascii=False))
        return 0 if r["result"] in ("advanced", "found", "idle") else 1
    w.loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
