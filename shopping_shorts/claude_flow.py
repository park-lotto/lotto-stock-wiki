# -*- coding: utf-8 -*-
"""클로드형 제작 지시 창구 — POST /api/claude/step (볼케이노형, 관제 234 2026-10-21 사장님 "볼케이노처럼 단계별로 착착").

노하우(단계 진행표·판정 질문·반려 규칙)는 엔진 hybrid/flow.py 한 곳 — 이 파일은 관문·서명·기록만 한다(판단 없음).
    요청 {preset, step: start|go|approve|revise|retry, source{url}, payload, measure{}, replies{}, revise}
    응답 {sid, status, message, stage, do, review, traps, reject, wait, video, next_payload, then_call_with}
next_payload = 서버 서명(HMAC) 상태 — 회원 PC 는 그대로 되돌린다. 한 글자라도 다르면 400, 옛 payload 를 다시 보내면 stale 로 거절한다.
서버에 남기는 것 = 요약만(sid·판·단계·원본 id·쿠팡 번호·검사 결과). 영상·대본 본문·키는 받지도 남기지도 않는다(서버 부담 0 원칙).
"""
from __future__ import annotations

import base64
import hmac
import json
import os
import re
import sys
import time
import uuid
import zlib
from pathlib import Path

from shopping_shorts import claude_portal as CP

_SCHEMA = """CREATE TABLE IF NOT EXISTS claude_flow_runs (
    sid TEXT PRIMARY KEY, cid INTEGER NOT NULL, preset TEXT, version TEXT, seq INTEGER NOT NULL DEFAULT 0,
    phase TEXT, status TEXT, created INTEGER, updated INTEGER, summary_json TEXT)"""
SID_RE = re.compile(r"^[0-9a-f]{12}$")
MEASURE_MAX = 400_000      # 요청 하나 measure+replies 상한(대본·받아쓰기가 가장 크다)


def engine_root() -> Path:
    """지시서(엔진 hybrid/flow.py)가 있는 저장소 뿌리 — 라이브는 이 저장소, 로컬 시험은 엔진 트랙(CLAUDE_FLOW_ENGINE)."""
    return Path(os.environ.get("CLAUDE_FLOW_ENGINE") or CP.channel_root())


def _flow():
    root = str(engine_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools.calcopy.hybrid import flow
    return flow


def _ensure(store):
    CP.ensure_schema(store)
    with CP._tx(store, write=True) as c:
        c.execute(_SCHEMA)


def _seal(state: dict, seq: int) -> str:
    raw = base64.urlsafe_b64encode(zlib.compress(json.dumps(state, ensure_ascii=False).encode("utf-8"), 6)).decode()
    mac = CP._mac("flow", f"{state['sid']}|{seq}|{raw}")
    return f"v1.{seq}.{raw}.{mac}"


def _open(payload: str) -> tuple[dict, int]:
    try:
        v, seq, raw, mac = str(payload or "").split(".")
        seq = int(seq)
        st = json.loads(zlib.decompress(base64.urlsafe_b64decode(raw.encode())).decode("utf-8"))
    except Exception:  # noqa: BLE001 — 모양이 틀린 payload 는 위변조와 같게 거절
        raise CP.PortalError("bad_request", "payload 가 올바르지 않습니다 — 받은 next_payload 를 그대로 보내세요")
    if v != "v1" or not hmac.compare_digest(mac, CP._mac("flow", f"{st.get('sid')}|{seq}|{raw}")):
        raise CP.PortalError("bad_request", "payload 가 바뀌었습니다 — 받은 next_payload 를 그대로 보내세요")
    return st, seq


def _line(preset_dir: Path) -> dict | None:
    try:
        j = json.loads((preset_dir / "line.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return j if j.get("line") == "hybrid" and j.get("version") else None


def _summary(st: dict) -> dict:
    return {"origin": (st.get("origin") or {}).get("id"), "product": (st.get("product") or {}).get("product_id"),
            "mode": (st.get("product") or {}).get("mode"), "auto_ok": (st.get("auto") or {}).get("ok"),
            "look_ok": (st.get("look") or {}).get("ok"), "tries": st.get("tries"), "stopped": st.get("stopped")}


def step(ctx: dict, body: dict, store=None) -> dict:
    store = CP._store(store)
    _ensure(store)
    cid, _, _ = CP._front(store, ctx, "step")
    flow = _flow()
    kind = str(body.get("step") or "go")
    blob = json.dumps({"m": body.get("measure"), "r": body.get("replies")}, ensure_ascii=False)
    if len(blob) > MEASURE_MAX:
        raise CP.PortalError("bad_request", "보낸 결과가 너무 큽니다")
    if kind == "start":
        pid = str(body.get("preset") or "")
        with CP._tx(store) as c:
            lic = CP._row(c, "SELECT * FROM claude_licenses WHERE cid=?", (cid,))
        if pid not in CP._entitled(store, cid, lic):
            raise CP.PortalError("not_entitled", "이 프리셋은 지금 쓸 수 없습니다")
        p = CP._preset_by_id(store, pid)
        line = _line(p["dir"]) if p else None
        if not line:
            raise CP.PortalError("bad_request", "이 프리셋은 단계 진행 방식이 아닙니다")
        url = str((body.get("source") or {}).get("url") or "")
        if not re.match(r"^https://(www\.)?(youtube\.com/(shorts/|watch\?v=)|youtu\.be/)[0-9A-Za-z_-]{11}", url):
            raise CP.PortalError("bad_request", "연예인 쇼핑 쇼츠(유튜브) 주소를 주세요")
        sid = uuid.uuid4().hex[:12]
        # 고객이 정한 쿠팡 제품(이름·주소) — 원본에 제품이 말로만 나올 때 쓴다(사장님 10-23)
        product = str((body.get("source") or {}).get("product") or "")[:200]
        # 제품을 정했을 때만 넘긴다 — 엔진이 이 인자를 모르는 옛판이어도 정하지 않은 편은 그대로 돈다
        st, seq = (flow.start(url, line["version"], sid, product) if product else flow.start(url, line["version"], sid)), 0
        with CP._tx(store, write=True) as c:
            c.execute("INSERT INTO claude_flow_runs(sid,cid,preset,version,seq,phase,status,created,updated) VALUES(?,?,?,?,?,?,?,?,?)",
                      (sid, cid, pid, line["version"], 0, "setup", "start", CP._now(), CP._now()))
    else:
        st, seq = _open(body.get("payload"))
        sid = str(st.get("sid") or "")
        with CP._tx(store) as c:
            row = CP._row(c, "SELECT * FROM claude_flow_runs WHERE sid=? AND cid=?", (sid, cid))
        if not row:
            raise CP.PortalError("bad_request", "그 작업을 찾을 수 없습니다")
        if seq != int(row["seq"]):
            raise CP.PortalError("stale", "옛 진행 상태입니다 — 가장 최근 next_payload 로 이어 주세요")
    user = {"approve": kind == "approve", "retry": kind == "retry", "revise": str(body.get("revise") or "")[:500] if kind == "revise" else ""}
    res = flow.step(st, body.get("measure") or {}, body.get("replies") or {}, user)
    st2 = res.pop("state")
    seq2 = seq + 1
    with CP._tx(store, write=True) as c:
        c.execute("UPDATE claude_flow_runs SET seq=?, phase=?, status=?, updated=?, summary_json=? WHERE sid=?",
                  (seq2, st2.get("phase"), res.get("status"), CP._now(), json.dumps(_summary(st2), ensure_ascii=False), sid))
    res.update(sid=sid, next_payload=_seal(st2, seq2),
               then_call_with=["payload 는 next_payload 그대로", "do 를 실행해 measure{do id: 결과}", "review 마다 replies{review id: 답 JSON}"])
    return res
