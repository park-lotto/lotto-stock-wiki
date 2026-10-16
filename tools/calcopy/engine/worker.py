# -*- coding: utf-8 -*-
"""소재창고 카테고리 워커 — PC 실행기 (관제 097, 2026-10-16). 설계: docs/superpowers/specs/2026-10-16-소재창고-보드-워커-design.md

    PYTHONUTF8=1 py tools/calcopy/engine/worker.py --category 식품 --track bench --channel yummyknow --once
    PYTHONUTF8=1 py tools/calcopy/engine/worker.py --category 식품 --track discover --channel yummyknow --loop

한 바퀴(tick) = 서버에 claim → 받은 단계를 worker_steps 로 돌림 → 산출물 올림 → advance(산출물·비용).
  · 실패는 reject 가 아니라 advance(error="이유") — 사람 판정 자리를 워커가 쓰지 않는다. 조용한 통과 없음.
  · claim 이 429 budget(비용 상한)이면 그 단계를 exclude_steps 에 넣고 다른 행을 다시 받는다.
  · heartbeat 는 별도 스레드(기본 60초) — 단계가 오래 돌아도 잠금(11분)이 유지된다.
  · 검수 자리(plan_review·final_review)를 넘기는 건 서버가 409 review_gate 로 거절한다.
판단 주인: 다음 일감·상태·잠금·비용 = 서버 API · 단계→엔진 = worker_steps.STEPS · 돌기 = Worker.tick() (이 파일).
키: 환경변수 CALCOPY_RELAY_KEY (헤더 X-Calcopy-Key). 서버: --server 또는 CALCOPY_SERVER.
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
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import worker_steps as WS  # noqa: E402

PREFIX = "/api/calcopy_worker"
UPLOAD_MAX = 40 * 1024 * 1024        # 보드에서 볼 산출물 상한(설계 §3-1)
DEFAULT_SERVER = "https://shoppingshorts.duckdns.org"


class ApiError(Exception):
    def __init__(self, status: int, body: dict):
        self.status, self.body = status, body or {}
        self.code = self.body.get("error") or f"http_{status}"
        super().__init__(f"{status} {self.code}: {self.body.get('detail') or ''}")


class Api:
    """서버 API 창구 — 규격이 바뀌면 여기 한 곳만 고친다. session 은 requests.Session 또는 TestClient(같은 모양)."""

    def __init__(self, base: str, key: str, session=None, timeout: float = 30):
        if session is None:
            import requests
            session = requests.Session()
        self.base, self.key, self.s, self.timeout = base.rstrip("/"), key, session, timeout

    def _post(self, path: str, body: dict | None = None, files=None, data=None) -> dict:
        kw = {"headers": {"X-Calcopy-Key": self.key}}
        if files is not None:
            kw.update(files=files, data=data or {})
        else:
            kw["json"] = body or {}
        if self.base.startswith("http"):
            kw["timeout"] = self.timeout
        r = self.s.post(self.base + PREFIX + path, **kw)
        try:
            j = r.json()
        except ValueError:
            j = {"error": f"http_{r.status_code}", "detail": (r.text or "")[:200]}
        if r.status_code >= 400:
            raise ApiError(r.status_code, j if isinstance(j, dict) else {"detail": str(j)[:200]})
        return j

    def claim(self, worker, category, track, channel, exclude_steps=()):
        return self._post("/claim", {"worker": worker, "category": category, "track": track, "channel": channel,
                                     "exclude_steps": list(exclude_steps)})

    def create_rows(self, worker, category, track, rows):
        return self._post("/topics", {"worker": worker, "category": category, "track": track, "rows": rows})

    def advance(self, topic_id, worker, step, artifacts=None, cost=None, data=None, error=None):
        body = {"worker": worker, "step": step, "artifacts": artifacts or {}, "cost": cost or {}, "data": data or {}}
        if error:
            body["error"] = error
        return self._post(f"/topics/{topic_id}/advance", body)

    def upload(self, topic_id, name, path: Path):
        with open(path, "rb") as f:
            return self._post(f"/topics/{topic_id}/file", files={"file": (path.name, f)}, data={"name": name})

    def heartbeat(self, **body):
        return self._post("/heartbeat", body)


class Worker:
    def __init__(self, api: Api, category: str, track: str, channel: str, name: str | None = None, out_root: Path | None = None,
                 steps=WS, preset: str | None = None, hb_interval: float = 60, log=print, extra: dict | None = None):
        self.api, self.category, self.track, self.channel = api, category, track, channel
        self.name = name or f"{socket.gethostname()}-{category}-{track}"
        self.steps, self.hb_interval, self.log = steps, hb_interval, log
        self.ctx = WS.Ctx(out_root=Path(out_root or Path.home() / "숏템_칼카피" / "worker" / category), channel=channel,
                          category=category, track=track, preset=preset, log=log, extra=extra or {})
        self.state = {"step": None, "topic_id": None, "last_error": None}
        self.done_today, self._day = 0, date.today()
        self._stop = threading.Event()
        self._hb: threading.Thread | None = None
        self._lock = threading.Lock()

    # ── heartbeat ──
    def beat(self):
        with self._lock:
            st = dict(self.state)
        if date.today() != self._day:
            self._day, self.done_today = date.today(), 0
        try:
            self.api.heartbeat(worker=self.name, category=self.category, track=self.track, channel=self.channel,
                               step=st["step"], topic_id=st["topic_id"], host=socket.gethostname(), done_today=self.done_today,
                               last_error=st["last_error"])
        except Exception as e:  # noqa: BLE001 — heartbeat 실패는 일을 멈출 이유가 아니다. 대신 남긴다(조용히 삼키지 않음)
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

    # ── 산출물 올리기 ──
    def _upload(self, topic_id, arts: dict) -> dict:
        out = {}
        for name, p in (arts or {}).items():
            p = Path(p)
            ent = {"local": str(p)}
            try:
                if p.is_file() and p.stat().st_size <= UPLOAD_MAX:
                    ent["url"] = self.api.upload(topic_id, name, p).get("url")
                elif p.is_file():
                    ent["upload_error"] = f"{p.stat().st_size // 1048576}MB > 상한 {UPLOAD_MAX // 1048576}MB — PC 에만 있음"
                else:
                    ent["upload_error"] = "파일 없음"
            except Exception as e:  # noqa: BLE001 — 올리기 실패는 산출물 항목에 이유로 남긴다(보드에 보인다)
                ent["upload_error"] = f"{type(e).__name__}: {str(e)[:150]}"
            out[name] = ent
        return out

    # ── 한 바퀴 ──
    def _claim(self) -> dict:
        excluded: list[str] = []
        for _ in range(len(WS.STEPS) + 1):
            try:
                return self.api.claim(self.name, self.category, self.track, self.channel, excluded)
            except ApiError as e:
                if e.status == 429 and e.code == "budget" and e.body.get("step") and e.body["step"] not in excluded:
                    self.log(f"[비용 상한] {e.body.get('step')} ({e.body.get('which')}) — {e.body.get('detail') or ''} → 그 단계 건너뜀")
                    excluded.append(e.body["step"])
                    continue
                raise
        return {"topic": None, "step": None, "reason": f"비용 상한으로 건너뛴 단계 {excluded}"}

    def tick(self) -> dict:
        """claim 1회 → 단계 1개. 돌려주는 값: {"result": idle|advanced|error|found|lock_lost|review_gate, ...}"""
        c = self._claim()
        topic, step = c.get("topic"), c.get("step")
        if not step:
            self._set(step=None, topic_id=None)
            return {"result": "idle", "reason": c.get("reason")}
        tid = (topic or {}).get("id")
        self._set(step=step, topic_id=tid)
        self.log(f"[받음] {step} · {tid or '(새 소재 찾기)'} {(topic or {}).get('topic', '')[:40]}")
        self.beat()
        t0 = time.time()
        try:
            res = self.steps.run_step(step, topic, self.ctx)
            err, arts, cost, data = None, res.get("artifacts") or {}, res.get("cost") or {}, res.get("data") or {}
        except WS.StepError as e:
            res, err, arts, cost, data = {}, f"{step}: {e.reason}", e.artifacts, e.cost, {}
        except NotImplementedError as e:
            res, err, arts, cost, data = {}, f"{step}: NotImplementedError — {e}", {}, {}, {}
        except Exception as e:  # noqa: BLE001 — 어떤 예외든 이유(원문+마지막 줄)와 함께 서버에 올린다
            tb = traceback.format_exc().strip().splitlines()[-1]
            res, err, arts, cost, data = {}, f"{step}: {type(e).__name__}: {str(e)[:250]} ({tb[:120]})", {}, {}, {}
        cost = {**cost, "seconds": cost.get("seconds", round(time.time() - t0))}
        self._set(last_error=err)
        try:
            if step == "find" and not err:
                r = self.api.create_rows(self.name, self.category, self.track, res.get("rows") or [])
                self.log(f"[찾음] 새 소재 {len(r.get('ids') or [])}개")
                self.done_today += 1
                return {"result": "found", "ids": r.get("ids") or []}
            if step == "find":
                self.log(f"[멈춤] {err}")        # 행이 없으니 advance 대신 heartbeat.last_error 로 보드에 뜬다
                self.beat()
                return {"result": "error", "error": err}
            up = self._upload(tid, arts)
            r = self.api.advance(tid, self.name, step, up, cost, data, error=err)
        except ApiError as e:
            if e.status == 409 and e.code in ("lock", "review_gate"):
                self.log(f"[거절] {e.code}: {e.body.get('detail') or ''}")
                return {"result": "lock_lost" if e.code == "lock" else "review_gate", "error": str(e)}
            raise
        finally:
            self._set(step=None, topic_id=None)
        if err:
            self.log(f"[멈춤] {tid} {err}")
            return {"result": "error", "error": err, "topic": r.get("topic")}
        self.done_today += 1
        self.log(f"[넘김] {tid} {step} → {(r.get('topic') or {}).get('state')}")
        return {"result": "advanced", "topic": r.get("topic")}

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
                if r["result"] in ("idle", "server_error"):
                    time.sleep(idle_sleep)
        finally:
            self.stop_heartbeat()


def main(argv=None):
    ap = argparse.ArgumentParser(description="소재창고 카테고리 워커")
    ap.add_argument("--category", required=True)
    ap.add_argument("--track", required=True, choices=["bench", "discover"])
    ap.add_argument("--channel", required=True, help="배정할 채널 slug 또는 프리셋 폴더")
    ap.add_argument("--preset", help="프리셋 폴더(없으면 --channel)")
    ap.add_argument("--name")
    ap.add_argument("--server", default=os.environ.get("CALCOPY_SERVER", DEFAULT_SERVER))
    ap.add_argument("--out", help="산출물 폴더(기본 ~/숏템_칼카피/worker/<카테고리>)")
    ap.add_argument("--source-kind", help="find 단계 소재 출처 유형(프리셋 manifest 에 없을 때)")
    ap.add_argument("--keywords", default="", help="find 검색어 쉼표 구분")
    ap.add_argument("--heartbeat", type=float, default=60)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    a = ap.parse_args(argv)
    key = os.environ.get("CALCOPY_RELAY_KEY", "")
    if not key:
        print("CALCOPY_RELAY_KEY 가 없다 — 서버가 403 으로 닫는다(설계 §3-1)", file=sys.stderr)
        return 2
    extra = {k: v for k, v in {"source_kind": a.source_kind,
                               "keywords": [k.strip() for k in a.keywords.split(",") if k.strip()] or None}.items() if v}
    w = Worker(Api(a.server, key), a.category, a.track, a.channel, a.name, Path(a.out) if a.out else None,
               preset=a.preset, hb_interval=a.heartbeat, extra=extra)
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
