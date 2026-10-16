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
import importlib
import json
import os
import socket
import subprocess
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
LLM_STEPS = ("bench", "score", "script")          # 제미나이를 쓰는 단계 — 시간당 한도에 걸리면 이 단계만 쉰다
ENGINE_FILES = ("tools/calcopy/engine/topic_find.py", "tools/calcopy/engine/script_engine.py", "tools/calcopy/engine/worker_steps.py",
                "tools/calcopy/engine/worker_ledger.py")
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

    def _req(self, method: str, path: str, retry: bool = True, prefix: str = PREFIX, **kw) -> dict:
        if self.base.startswith("http"):
            kw["timeout"] = self.timeout
        r = getattr(self.s, method)(self.base + prefix + path, **kw)
        if r.status_code == 403 and retry and self.cookie_fn:      # 관리자 세션 2시간 만료 → 한 번 다시 발급
            self._set_cookie(self.cookie_fn())
            return self._req(method, path, retry=False, prefix=prefix, **kw)
        try:
            j = r.json()
        except ValueError:
            j = {"error": f"HTTP {r.status_code}: {(r.text or '')[:200]}"}
        if r.status_code >= 400:
            raise ApiError(r.status_code, (j or {}).get("error") if isinstance(j, dict) else str(j)[:200])
        return j

    def claim_next(self, worker, steps, category=None, track=None, channel=None):
        body = {"worker": worker, "steps": list(steps)}
        body.update({k: v for k, v in (("category", category), ("track", track), ("channel", channel)) if v})
        return self._req("post", "/claim_next", json=body)

    def worker_heartbeat(self, worker, category=None, track=None, channel=None, doing=None, idle_reason=None, last_error=None):
        """쉬는 중에도 보드에 보이게(규격 §6-3) — 잡은 소재와 무관한 워커 맥박."""
        return self._req("post", "/heartbeat", prefix="/api/admin/calcopy/workers",
                         json={"worker": worker, "category": category, "track": track, "channel": channel,
                               "doing": doing, "idle_reason": idle_reason, "last_error": last_error})

    def add(self, name, category, track, source=None, by=""):
        return self._req("post", "", json={"name": name, "category": category, "track": track, "source": source or {}, "by": by})

    def heartbeat(self, tid, worker, doing=None):
        return self._req("post", f"/{tid}/heartbeat", json={"worker": worker, "doing": doing})

    def advance(self, tid, worker, data=None, outputs=None, cost=None, note=""):
        return self._req("post", f"/{tid}/advance", json={"worker": worker, "data": data or {}, "outputs": outputs or {},
                                                         "cost": cost or {}, "note": note})

    def reject(self, tid, reason, back_to=None, by="worker"):
        return self._req("post", f"/{tid}/reject", json={"reason": reason, "back_to": back_to, "by": by})

    def release(self, tid, worker, error):
        return self._req("post", f"/{tid}/release", json={"worker": worker, "error": error})

    def upload(self, tid, name, path: Path):
        # ★data= (requests·TestClient 둘 다 받는다). content= 는 httpx 전용이라 requests 에선 TypeError — 시험만 통과하고 실물에서 죽었다(10-16)
        return self._req("post", f"/{tid}/upload/{quote(name)}", data=Path(path).read_bytes())


def _cost(c: dict) -> dict:
    """서버가 받는 비용 종류만(gemini·typecast·seconds, 0 이상 정수). 0 은 빼서 보낸다(seconds 는 규격 §6-4 — 단계 실제 소요 초)."""
    return {k: int(c[k]) for k in ("gemini", "typecast", "seconds") if int(c.get(k) or 0) > 0}

# claim_next 의 channel 거르기는 assign.channel 로 본다 — 배정 전 소재(found~scored)는 channel 을 주면 안 잡힌다(규격 §6-1).
# 그래서 배정 뒤 일은 내 채널로, 배정까지의 일은 카테고리·트랙으로만 거른다.
PRE_ASSIGN = ("bench", "score", "assign")


class Worker:
    def __init__(self, api: Api, category: str, track: str, channel: str, name: str | None = None, out_root: Path | None = None,
                 steps=WS, preset: str | None = None, hb_interval: float = 60, find_every: float = 60 * 60,
                 allowed_steps: list[str] | None = None, log=print, extra: dict | None = None, ledger: bool = False):
        self.api, self.category, self.track, self.channel = api, category, track, channel
        self.name = name or f"{socket.gethostname()}-{category}-{track}"
        self.steps, self.hb_interval, self.find_every, self.log = steps, hb_interval, find_every, log
        self.allowed = [s for s in (allowed_steps or WS.STEPS) if s != "find"]
        self.ctx = WS.Ctx(out_root=Path(out_root or Path.home() / "숏템_칼카피" / "worker" / category), channel=channel,
                          category=category, track=track, preset=preset, log=log, extra=extra or {})
        self.state = {"step": None, "topic_id": None, "idle_reason": None, "last_error": None}
        self.ledger = ledger
        if ledger:
            self.ctx.worker = self.name                 # worker_steps 가 유튜브·제미나이를 장부 한도 뒤에서 쓴다
        self._engine_rev = self._rev() if ledger else None
        self.done, self.last_find = 0, None
        self._stop = threading.Event()
        self._hb: threading.Thread | None = None
        self._lock = threading.Lock()

    # ── heartbeat(잡은 소재에만 — 서버 규격 §2) ──
    def beat(self):
        with self._lock:
            st = dict(self.state)
        try:
            if st["topic_id"]:
                self.api.heartbeat(st["topic_id"], self.name, f"{st['step']} 중")
            else:                     # 쉬는 중·find 중 — 소재가 없어도 보드 워커 패널에 보이게(규격 §6-3)
                self.api.worker_heartbeat(self.name, self.category, self.track, self.channel, doing=st["step"],
                                          idle_reason=st["idle_reason"], last_error=st["last_error"])
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

    # ── 장부·엔진 재로드 ──
    def _note(self, kind, n=1, note=""):
        if self.ledger:
            from tools.calcopy.engine import worker_ledger as L
            L.add(self.name, kind, n, note)

    @staticmethod
    def _rev(ref: str = "HEAD") -> str | None:
        """ref 에서 엔진 파일들의 마지막 커밋. 워커는 창고 전용 체크아웃(warehouse.ps1 — 트랙 폴더와 분리)에서 돌아
        다른 담당의 **커밋 안 된 편집**을 읽지 않는다(10-16 실측: 편집 중인 topic_find 에서 concrete_nouns 가 사라져 find 전멸)."""
        try:
            r = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%H", ref, "--", *ENGINE_FILES],
                               capture_output=True, text=True, timeout=20)
            return r.stdout.strip() or None
        except (OSError, subprocess.SubprocessError) as e:
            return f"err:{e}"

    def _follow_branch(self):
        """CALCOPY_FOLLOW_REF(예 track/칼카피숏템엔진)의 엔진 커밋이 이 체크아웃보다 새로우면 그 커밋으로 옮긴다(커밋된 것만 따라감)."""
        ref = os.environ.get("CALCOPY_FOLLOW_REF")
        if not ref:
            return
        tip, here = self._rev(ref), self._rev("HEAD")
        if tip and here and tip != here and not tip.startswith("err:"):
            r = subprocess.run(["git", "-C", str(ROOT), "checkout", "--detach", "-q", ref], capture_output=True, text=True, timeout=60)
            self.log(f"[따라감] {ref} {here[:9]} → {tip[:9]} rc={r.returncode} {r.stderr.strip()[:150]}")

    def _maybe_reload(self):
        self._follow_branch()
        rev = self._rev()
        if not self.ledger or rev == self._engine_rev or not rev or rev.startswith("err:"):
            return
        names = ["tools.calcopy.engine.worker_ledger", "tools.calcopy.engine.topic_find", "tools.calcopy.engine.script_engine",
                 "tools.calcopy.engine.worker_steps"]
        done = []
        for n in names:
            m = sys.modules.get(n)
            if m:
                try:
                    importlib.reload(m)
                    done.append(n.rsplit(".", 1)[1])
                except Exception as e:  # noqa: BLE001 — 새 코드가 깨졌으면 옛 코드로 계속 돌고 이유를 남긴다
                    self.log(f"[재로드 실패] {n}: {type(e).__name__}: {e}")
                    self._note("error", 1, f"재로드 실패 {n}: {e}")
        self.log(f"[재로드] 엔진 커밋 {str(self._engine_rev)[:9]} → {rev[:9]} · {done}")
        self._engine_rev = rev
        self.requeue_old()

    def requeue_old(self) -> list:
        """엔진이 바뀌면 옛 엔진으로 점수 낸 scored 소재를 재점수 큐로(back_to=benched — 다음 score 단계가 새 엔진으로 다시 잰다).
        scored 를 넘은 소재(배정·대본…)는 건드리지 않는다(사장님 10-16 'scored 이전 상태만')."""
        if not self.ledger or not self._engine_rev:
            return []
        try:
            have = self.api._req("get", "?category=" + quote(self.category) + "&state=scored&limit=2000").get("topics") or []
        except Exception as e:  # noqa: BLE001
            self.log(f"[재점수 큐 못 봄] {type(e).__name__}: {e}")
            return []
        moved = []
        for t in have:
            old = (t.get("score") or {}).get("engine_ver")
            if old == self._engine_rev:
                continue
            try:
                self.api.reject(t["id"], f"재점수: 엔진 {str(old)[:9]} → {self._engine_rev[:9]}", back_to="benched", by=f"worker@{self.name}")
                moved.append(t["id"])
            except ApiError as e:
                self.log(f"[재점수 큐 거절] #{t['id']}: {e}")
        if moved:
            self.log(f"[재점수 큐] {len(moved)}건 {moved}")
            self._note("rescore", len(moved), f"엔진 {self._engine_rev[:9]}: {moved}")
        return moved

    def _dedupe(self, rows: list[dict]) -> tuple[list[dict], list[str]]:
        """같은 소재(제목 2-gram 포함률 ≥0.6 또는 같은 출처 URL)는 다시 안 쌓는다 — 판정은 topic_find.overlap(겹침 주인)."""
        try:
            TF = WS._engine("topic_find")
            have = self.api._req("get", "?category=" + quote(self.category) + "&limit=2000").get("topics") or []
        except Exception as e:  # noqa: BLE001
            self.log(f"[중복 검사 못 함] {type(e).__name__}: {e} — 서버 이름 중복(409)만 믿는다")
            return rows, []
        corpus = [{"what": "창고", "text": t.get("name") or ""} for t in have]
        urls = {(t.get("source") or {}).get("url") for t in have} - {None, ""}
        keep, skip = [], []
        for r in rows:
            url = (r.get("source") or {}).get("url")
            ov = TF.overlap(r["name"], corpus + [{"what": "이번 찾기", "text": k["name"]} for k in keep])
            if url and url in urls:
                skip.append(f"{r['name'][:30]}: 같은 출처 URL")
            elif ov.get("score", 0) >= 0.6:
                skip.append(f"{r['name'][:30]}: 제목 겹침 {ov.get('score')} ({str(ov.get('with'))[:30]})")
            else:
                keep.append(r)
        return keep, skip

    # ── 소재 찾기(행이 없는 일 — claim 없이 add) ──
    def find(self) -> dict:
        self.last_find = time.time()
        self.log("[찾기] 새 소재 찾기")
        self._set(step="find")
        self.beat()
        try:
            res = self.steps.run_step("find", None, self.ctx)
        except (WS.StepError, NotImplementedError, Exception) as e:  # noqa: BLE001 — 행이 없으니 워커 맥박 last_error 로 보드에
            why = e.reason if isinstance(e, WS.StepError) else f"{type(e).__name__}: {e}"
            self.log(f"[멈춤] find: {why}")
            self._note("error", 1, f"find: {why}")
            self._set(step=None, idle_reason=f"find 실패: {why}"[:200], last_error=f"find: {why}"[:300])
            self.beat()
            return {"result": "error", "error": f"find: {why}"}
        self._set(step=None)
        ids, dup = [], []
        rows, skipped = self._dedupe(res.get("rows") or [])
        dup += skipped
        for r in rows:
            try:
                src = {**(r.get("source") or {}), "engine_ver": self._engine_rev}
                ids.append(self.api.add(r["name"], self.category, self.track, src, by=f"worker@{self.name}")["topic"]["id"])
            except ApiError as e:
                if e.status != 409:
                    raise
                dup.append(f"{r['name'][:30]}: {e.msg}")
        self.log(f"[찾음] 새 소재 {len(ids)}개 · 중복 {len(dup)}개" + (f" — {dup[:3]}" if dup else ""))
        self._note("topic", len(ids), f"찾기 {len(ids)} · 중복 {len(dup)}")
        self._set(idle_reason=None, last_error=None)
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
    def _claim(self) -> dict:
        """배정 뒤 일(script~check)은 내 채널에 배정된 소재만, 배정까지(bench·score·assign)는 카테고리·트랙으로만 거른다."""
        allowed = list(self.allowed)
        if self.ledger:
            from tools.calcopy.engine import worker_ledger as L
            if L.count("gemini", worker=self.name) >= L.GEMINI_PER_HOUR:      # 시간당 제미나이 한도 — 제미나이 단계만 쉰다
                allowed = [s for s in allowed if s not in LLM_STEPS]
        post = [s for s in allowed if s not in PRE_ASSIGN]
        pre = [s for s in allowed if s in PRE_ASSIGN]
        reasons = []
        for steps, ch in ((post, self.channel), (pre, None)):
            if not steps:
                continue
            c = self.api.claim_next(self.name, steps, self.category, self.track, ch)
            if c.get("step"):
                return c
            reasons += c.get("reasons") or []
        return {"topic": None, "step": None, "reasons": reasons}

    def tick(self) -> dict:
        """claim 1회 → 단계 1개. 결과: idle|advanced|error|found|refused"""
        if self.ledger:
            self._maybe_reload()
            if not getattr(self, "_requeued_once", False):     # 켤 때 한 번 — 꺼져 있던 사이 엔진이 바뀌었을 수 있다
                self._requeued_once = True
                self.requeue_old()
            from tools.calcopy.engine import worker_ledger as L
            until = L.pause_until(self.name)
            if until > time.time():
                why = f"제미나이 429 — {time.strftime('%H:%M', time.localtime(until))} 까지 쉼"
                self._set(step=None, topic_id=None, idle_reason=why)
                self.beat()
                return {"result": "idle", "reasons": [why]}
        c = self._claim()
        topic, step = c.get("topic"), c.get("step")
        if not step:
            self._set(step=None, topic_id=None)
            due = self.find_every and (self.last_find is None or time.time() - self.last_find >= self.find_every)
            if due:
                return self.find()
            self._set(idle_reason="; ".join(c.get("reasons") or [])[:200])
            self.log(f"[쉼] {'; '.join(c.get('reasons') or [])}")
            self.beat()
            return {"result": "idle", "reasons": c.get("reasons") or []}
        tid = topic["id"]
        self._set(step=step, topic_id=tid)
        self.log(f"[받음] {step} · #{tid} {topic.get('name', '')[:40]}")
        self._set(idle_reason=None)
        self.beat()
        err, res = None, {}
        t0 = time.time()
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
                self._set(last_error=f"#{tid} {step}: {err}"[:300])
                self._note("error", 1, f"#{tid} {step}: {err}")
                self.api.release(tid, self.name, err)
                self.log(f"[멈춤] #{tid} {step}: {err}")
                return {"result": "error", "error": err}
            outs = {k: v for k, v in (res.get("outputs") or {}).items() if v in ok}
            outs.update({Path(f).stem: f for f in ok if f not in outs.values()})
            cost = {**(res.get("cost") or {}), "seconds": round(time.time() - t0)}
            data = {k: ({**v, "engine_ver": self._engine_rev} if self._engine_rev and isinstance(v, dict) else v)
                    for k, v in (res.get("data") or {}).items()}
            rescore = step == "score" and (topic.get("rework_n") or 0) > 0 and "재점수" in str(topic.get("last_error") or "")
            notes = ([f"engine_ver={self._engine_rev[:9]}"] if self._engine_rev else []) + (["재점수"] if rescore else []) + \
                    (["올리기 실패: " + "; ".join(bad)] if bad else [])
            r = self.api.advance(tid, self.name, data, outs, _cost(cost), note=" · ".join(notes))
            if rescore:
                self._note("rescore_done", 1, f"#{tid} gemini {cost.get('gemini', 0)} · {cost['seconds']}초")
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
        if step == "script":
            self._note("script", 1, f"#{tid}")
        self._set(last_error=None)
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
    ap.add_argument("--llm-budget", type=int, default=6, help="한 단계 무료 제미나이 호출 상한(topic_find.LLM)")
    ap.add_argument("--no-ledger", action="store_true", help="장부 한도 끄기(시험용). 상시 가동은 장부 필수")
    ap.add_argument("--idle-sleep", type=float, default=60)
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
               allowed_steps=[s.strip() for s in a.steps.split(",") if s.strip()] or None, extra=extra, ledger=not a.no_ledger)
    w.ctx.llm_budget = a.llm_budget
    if a.once:
        w.start_heartbeat()
        try:
            r = w.tick()
        finally:
            w.stop_heartbeat()
        print(json.dumps({k: v for k, v in r.items() if k != "topic"}, ensure_ascii=False))
        return 0 if r["result"] in ("advanced", "found", "idle") else 1
    w.loop(idle_sleep=a.idle_sleep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
