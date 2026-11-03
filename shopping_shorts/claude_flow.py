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
import inspect
import json
import os
import re
import sys
import time
import uuid
import zlib
from pathlib import Path

from shopping_shorts import claude_live as LIVE
from shopping_shorts import claude_portal as CP

_SCHEMA = """CREATE TABLE IF NOT EXISTS claude_flow_runs (
    sid TEXT PRIMARY KEY, cid INTEGER NOT NULL, preset TEXT, version TEXT, seq INTEGER NOT NULL DEFAULT 0,
    phase TEXT, status TEXT, created INTEGER, updated INTEGER, summary_json TEXT, engine TEXT)"""
# 직전 응답(편마다 하나) — 회원 PC 가 응답을 못 받고 같은 요청을 다시 보내면(네트워크·502 재시도) 그 응답을 그대로 돌려준다.
#   없으면 서버는 seq 를 올린 뒤라 'stale' 로 거절하고, 회원 PC 는 새 payload 를 영영 못 받아 편이 죽었다(11-03 김유선 retry 마다 stale)
_SCHEMA_LAST = """CREATE TABLE IF NOT EXISTS claude_flow_last (sid TEXT PRIMARY KEY, seq INTEGER NOT NULL, req TEXT NOT NULL, res TEXT NOT NULL)"""
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
        c.execute(_SCHEMA_LAST)
        # engine = 이 편을 만든 앱 판(단계 배포 실패율, 관제 304). version 칸은 프리셋 판이다. 라이브 표에는 칸이 없다
        if "engine" not in [r[1] for r in c.execute("PRAGMA table_info(claude_flow_runs)").fetchall()]:
            c.execute("ALTER TABLE claude_flow_runs ADD COLUMN engine TEXT")


def stop_counts(store, version: str, since_new: int, since_old: int) -> dict:
    """앱 판별 막힘 수 — 새 판 = version 으로 since_new 뒤 시작한 편, 옛 판 = 그 밖의 판(칸 없던 옛 행 포함) since_old 뒤.
    끝난 편(stop·done)만 센다. 진행 중이거나 버려진 편은 분모에 안 넣는다. 판정은 claude_portal.rollout_bad."""
    _ensure(store)
    with CP._tx(store) as c:
        rows = CP._rows(c, "SELECT COALESCE(engine,'') engine, status, created FROM claude_flow_runs "
                           "WHERE status IN ('stop','done') AND created>=?", (min(since_new, since_old),))
    out = {"new_stop": 0, "new_n": 0, "old_stop": 0, "old_n": 0}
    for r in rows:
        if r["engine"] == version:
            side = "new" if r["created"] >= since_new else None
        else:
            side = "old" if r["created"] >= since_old else None
        if side:
            out[side + "_n"] += 1
            out[side + "_stop"] += r["status"] == "stop"
    return out


def _req_key(kind: str, body: dict) -> str:
    """같은 요청인가 — 단계 종류·payload·measure·replies·revise 의 해시."""
    import hashlib
    j = json.dumps({"k": kind, "p": body.get("payload"), "m": body.get("measure"), "r": body.get("replies"), "v": body.get("revise")},
                   ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(j.encode("utf-8")).hexdigest()


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
    rh = getattr(_flow(), "ref_hash", None)      # 옛 지시서(지문 함수 없음)·시험 가짜 지시서면 비운다
    return {"seed_h": rh(st["ref"]) if rh and st.get("ref") else None, "origin": (st.get("origin") or {}).get("id"), "product": (st.get("product") or {}).get("product_id"),
            "mode": (st.get("product") or {}).get("mode"), "auto_ok": (st.get("auto") or {}).get("ok"),
            "look_ok": (st.get("look") or {}).get("ok"), "look_by": (st.get("look") or {}).get("by"), "look_scenes": (st.get("look") or {}).get("scenes"),
            "look_n": len((st.get("look") or {}).get("problems") or []), "look_skip": bool((st.get("look") or {}).get("skipped")), "look_left": len(st.get("look_left") or []),
            "tries": st.get("tries"), "stopped": st.get("stopped")}


def _made_refs(store, cid) -> list:
    """이 회원이 이미 만든(완성) 소재 지문(flow.ref_hash — 기록엔 주소를 안 남긴다) — 소재 창고에서 뺀다(같은 소재 두 번 금지)."""
    with CP._tx(store) as c:
        rows = c.execute("SELECT summary_json FROM claude_flow_runs WHERE cid=? AND status='done' ORDER BY updated DESC LIMIT 500", (cid,)).fetchall()
    out = []
    for r in rows:
        try:
            ref = (json.loads(r[0] or "{}") or {}).get("seed_h")
        except ValueError:
            ref = None
        if ref:
            out.append(ref)
    return out


def _used_refs(store, cid) -> dict:
    """다른 회원이 쓴 소재 지문 → 쓴 회원 수(claude_flow_runs 전체 · 진행 중 포함). 실패 편(stop·reject)은 안 친다. 순서 판단은 flow.bench_pool."""
    with CP._tx(store) as c:
        rows = c.execute("SELECT DISTINCT cid, json_extract(summary_json,'$.seed_h') FROM claude_flow_runs "
                         "WHERE cid<>? AND COALESCE(status,'') NOT IN ('stop','reject') AND json_valid(summary_json)", (cid,)).fetchall()
    out: dict = {}
    for r in rows:
        if r[1]:
            out[r[1]] = out.get(r[1], 0) + 1
    return out


def _pool_kw(fn, **kw) -> dict:
    """옛 지시서(새 인자를 모름)면 뺀다 — 호출 형식 호환."""
    names = inspect.signature(fn).parameters
    return {k: v for k, v in kw.items() if k in names}


def knowhow(ctx: dict, body: dict, store=None) -> dict:
    """막혔을 때 노하우 — 상황 글·단계에 맞는 막힘표·가이드·경험. 판단 주인 = flow.knowhow."""
    store = CP._store(store)
    _ensure(store)
    cid, _, _ = CP._front(store, ctx, "knowhow")
    body = body if isinstance(body, dict) else {}
    tier = CP.member_tier(store, cid)
    if str(body.get("topic") or "") == "benchmark":      # 채널 벤치마킹 노하우 = 고급 이상(사장님 11-02) — 나머지 노하우는 전 반 같다
        if tier == "basic":
            return {"ok": True, "locked": True, "say": "채널 벤치마킹은 고급반에서 제공돼요", "tier": tier}
        return {"ok": True, "tier": tier, "guide": _flow().benchmark_guide()}
    return {"ok": True, "tier": tier, **_flow().knowhow(str(body.get("stage") or "")[:40], str(body.get("query") or "")[:2000])}


def sign_memes(res: dict, cid, sid, store) -> None:
    """지시서 do 의 memes{stems} → 받을 주소·지문(claude_assets 'meme:<번호>', 짝 = hybrid/meme_catalog.json). 회원 PC 실행기 c_memes 가 받는다.
    목록에 없는 이름·서버에 없는 자산은 뺀다(실행기는 받은 것만 시트에 올린다). 주소 서명 주인 = claude_portal.asset_url."""
    dos = [d for d in (res.get("do") or []) if isinstance(d, dict) and d.get("cmd") == "memes"]
    if not dos:
        return
    try:
        cat = {m["stem"]: m for m in json.loads((engine_root() / "tools/calcopy/hybrid/meme_catalog.json").read_text(encoding="utf-8"))["memes"]}
    except (OSError, ValueError, KeyError):      # 목록이 없는 판 — 짤만 빠지고 단계는 간다(실행기는 받은 짤만 시트에 올린다)
        CP.log.warning("claude_flow: meme_catalog.json 없음 — 짤 후보 주소를 못 붙였다")
        cat = {}
    with CP._tx(store) as c:
        for d in dos:
            items = []
            for stem in list(d.pop("stems", None) or [])[:20]:
                m = cat.get(str(stem))
                a = CP._row(c, "SELECT * FROM claude_assets WHERE id=?", (m["asset"],)) if m else None
                if a:
                    url, _ = CP.asset_url(a, cid, sid)
                    items.append({"stem": m["stem"], "url": url, "sha256": a["sha256"], "tone": m["tone"], "title": m["title"]})
            d["items"] = items


def step(ctx: dict, body: dict, store=None) -> dict:
    store = CP._store(store)
    _ensure(store)
    cid, _, _ = CP._front(store, ctx, "step")
    flow = _flow()
    kind = str(body.get("step") or "go")
    blob = json.dumps({"m": body.get("measure"), "r": body.get("replies")}, ensure_ascii=False)
    if len(blob) > MEASURE_MAX:
        raise CP.PortalError("bad_request", "보낸 결과가 너무 큽니다")
    if kind in ("start", "sources"):
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
        made = _made_refs(store, cid)
        used = _used_refs(store, cid)
        if kind == "sources" and not hasattr(flow, "source_candidates"):
            raise CP.PortalError("bad_request", "이 서버는 아직 후보 뽑기를 못 합니다 — 영상 주소를 주세요")
        if kind == "sources":             # 회원 '후보 뽑아줘' — 그 판 소재 창고(벤치 채널 조회순)에서 안 만든 5개. 편은 만들지 않는다
            try:
                offset = max(0, int(body.get("offset") or 0))
            except (TypeError, ValueError):
                raise CP.PortalError("bad_request", "offset 은 숫자여야 합니다")
            found = flow.source_candidates(line["version"], made, **_pool_kw(flow.source_candidates, n=300, offset=offset, used=used, seed=cid))   # 창고 전체를 고객이 고른다(사장님 10-31)
            return {"ok": True, "status": "sources", "sources": found, "next_offset": offset + len(found)}
        auto = None
        if not url and hasattr(flow, "pick_source"):   # 주소 없이 '만들어줘' — 소재 창고 첫 편(순서 = flow.bench_pool)
            auto = flow.pick_source(line["version"], made, **_pool_kw(flow.pick_source, used=used, seed=cid))
            if not auto:
                raise CP.PortalError("bad_request", "이 프리셋의 소재 창고(벤치 채널)에 아직 안 만든 영상이 없어요 — 영상 주소를 주세요")
            url = auto["url"]
        why = flow.source_url_problem(url) if hasattr(flow, "source_url_problem") else (
            "" if re.match(r"^https://(www\.)?(youtube\.com/(shorts/|watch\?v=)|youtu\.be/)[0-9A-Za-z_-]{11}", url) else "유튜브 쇼츠 주소를 주세요")   # 판단 주인 = 지시서 flow.source_url_problem(옛 지시서면 옛 유튜브 규칙)
        if why:
            raise CP.PortalError("bad_request", why)
        sid = uuid.uuid4().hex[:12]
        # 고객이 정한 쿠팡 제품(이름·주소) — 원본에 제품이 말로만 나올 때 쓴다(사장님 10-23)
        product = str((body.get("source") or {}).get("product") or "")[:200]
        # 제품을 정했을 때만 넘긴다 — 엔진이 이 인자를 모르는 옛판이어도 정하지 않은 편은 그대로 돈다
        st, seq = (flow.start(url, line["version"], sid, product) if product else flow.start(url, line["version"], sid)), 0
        st["made_refs"] = made[:200]          # 둘째 소재(pick_alt_source)도 이 회원이 만든 것을 뺀다
        st["pool_used"], st["pool_seed"] = dict(sorted(used.items(), key=lambda x: -x[1])[:200]), cid   # 다음 소재·둘째 소재도 같은 순서
        if auto:
            st["auto_source"] = auto
            st["log"].append(f"소재 창고에서 시작: {auto['url']} (조회 {auto.get('views')})")
        with CP._tx(store, write=True) as c:
            c.execute("INSERT INTO claude_flow_runs(sid,cid,preset,version,seq,phase,status,created,updated,engine) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (sid, cid, pid, line["version"], 0, "setup", "start", CP._now(), CP._now(), str(ctx.get("engine") or "")[:32]))
    else:
        st, seq = _open(body.get("payload"))
        sid = str(st.get("sid") or "")
        with CP._tx(store) as c:
            row = CP._row(c, "SELECT * FROM claude_flow_runs WHERE sid=? AND cid=?", (sid, cid))
        if not row:
            raise CP.PortalError("bad_request", "그 작업을 찾을 수 없습니다")
        if seq != int(row["seq"]):
            with CP._tx(store) as c:
                last = CP._row(c, "SELECT * FROM claude_flow_last WHERE sid=?", (sid,))
            if last and int(last["seq"]) == seq and last["req"] == _req_key(kind, body):
                return json.loads(zlib.decompress(base64.b64decode(last["res"])).decode("utf-8"))      # 같은 요청 다시 = 같은 응답
            raise CP.PortalError("stale", "옛 진행 상태입니다 — 가장 최근 next_payload 로 이어 주세요")
    user = {"approve": kind == "approve", "retry": kind == "retry", "reclean": kind == "reclean", "revise": str(body.get("revise") or "")[:500] if kind == "revise" else ""}
    try:
        res = flow.step(st, body.get("measure") or {}, body.get("replies") or {}, user)
    except CP.PortalError:
        raise
    except Exception as e:      # noqa: BLE001 — 그대로 터뜨린다. 회원은 서버 오류만 보니 사건으로 남긴다(판단 = claude_live)
        LIVE.flow_crash(store, cid, sid, e)
        raise
    st2 = res.pop("state")
    sign_memes(res, cid, sid, store)      # 짤 후보 받을 주소(PC 제작 라인 짤 단계)
    seq2 = seq + 1
    with CP._tx(store, write=True) as c:
        c.execute("UPDATE claude_flow_runs SET seq=?, phase=?, status=?, updated=?, summary_json=? WHERE sid=?",
                  (seq2, st2.get("phase"), res.get("status"), CP._now(), json.dumps(_summary(st2), ensure_ascii=False), sid))
    LIVE.metrics(store, cid, sid, body.get("measure"), str((res.get("stage") or {}).get("text") or ""))
    LIVE.from_flow(store, cid, sid, res, st2)      # 멈춤·반려·과제·완성 — 옛 회원 프로그램도 서버에서 보인다(관제 304)
    res.update(sid=sid, next_payload=_seal(st2, seq2),
               then_call_with=["payload 는 next_payload 그대로", "do 를 실행해 measure{do id: 결과}", "review 마다 replies{review id: 답 JSON}"])
    if kind not in ("start", "sources"):
        with CP._tx(store, write=True) as c:
            c.execute("INSERT OR REPLACE INTO claude_flow_last(sid, seq, req, res) VALUES(?,?,?,?)",
                      (sid, seq, _req_key(kind, body), base64.b64encode(zlib.compress(json.dumps(res, ensure_ascii=False).encode("utf-8"), 6)).decode()))
    return res
