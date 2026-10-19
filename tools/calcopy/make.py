# -*- coding: utf-8 -*-
"""칼카피 만들기 입구 CLI (관제 097) — 판단은 shopping_shorts/calcopy_make 하나, 여기는 부르고 표로 찍기만.

    PYTHONUTF8=1 py tools/calcopy/make.py start  --preset channel/banggu/preset/게시글형 --pack 1            # 후보 표
    PYTHONUTF8=1 py tools/calcopy/make.py start  --preset … --pack 1 --topic "소재 글" [--facts facts.json] [--ref URL]
    PYTHONUTF8=1 py tools/calcopy/make.py start  --preset … --pack 1 --reuse-of <소재 id> [--voice 김건] [--channel-name 둘째]
    PYTHONUTF8=1 py tools/calcopy/make.py choose  <sid> <번호>        # 대본·재료·계획 시트까지(선검수 자리에서 멈춤)
    PYTHONUTF8=1 py tools/calcopy/make.py status  <sid>
    PYTHONUTF8=1 py tools/calcopy/make.py approve <sid> --by 페이블|사장님     # TTS 1회·렌더(관리자만)
    PYTHONUTF8=1 py tools/calcopy/make.py reject  <sid> "사유"
데이터 = CALCOPY_DATA_DIR(기본 C:/숏템_칼카피/창고 — 창고 보드와 같은 DB). 단계는 이 프로세스에서 끝까지 돈다(sync).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CALCOPY_DATA_DIR", "C:/숏템_칼카피/창고")

from shopping_shorts import calcopy_make as MK  # noqa: E402

DEPS = {"sync": True}


def _table(S: dict):
    print(f"세션 {S['sid']} · {S['state']} · 프리셋 {S['preset']} · 팩 {S['pack']} · 모드 {S.get('mode')}")
    for a in S.get("applied") or []:
        print(f"  팩 적용: {a}")
    for c in S.get("candidates") or []:
        sc = " ".join(f"{k}{v}" for k, v in (c.get("scores") or {}).items())
        print(f"  [{c.get('n')}] #{c['id']} {c['title'][:50]} | 총점 {c.get('total')} | {sc or '점수 전'} | 벤치 {c.get('bench_videos')}편"
              f" | 만든 수 {c.get('made', 0)} | 반전 {(c.get('twist') or '')[:30]} | 근거 {', '.join(c.get('sources') or [])[:60]}")
        if c.get("line"):
            print(f"       한 줄: {c['line'][:90]}")


def _status(S: dict):
    keep = {k: S.get(k) for k in ("sid", "state", "topic_id", "root_topic", "mode", "error", "topic_state", "variant", "variant_warn", "approved_by")}
    print(json.dumps(keep, ensure_ascii=False, indent=1))
    for f in S.get("files") or []:
        print(f"  산출물 {f['name']}")
    work = Path(S["merged_preset"]).parent / "work" / str(S.get("topic_id")) / "제작"
    for n in ("계획.md", "계획_시트.jpg", "재료.json"):
        if (work / n).exists():
            print(f"  {n}: {work / n}")
    for line in (S.get("log") or [])[-8:]:
        print(f"  로그 {line[:160]}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("start")
    a.add_argument("--preset", required=True)
    a.add_argument("--pack", default="1")
    a.add_argument("--topic")
    a.add_argument("--ref")
    a.add_argument("--facts", help="근거 JSON 파일({id:{text,url,date}} 또는 목록)")
    a.add_argument("--reuse-of", type=int)
    a.add_argument("--voice", help="이 세션만 목소리 바꾸기(팩 alternates 이름)")
    a.add_argument("--channel-name", help="이 세션만 채널명 바꾸기")
    c = sp.add_parser("choose")
    c.add_argument("sid")
    c.add_argument("n", type=int)
    s = sp.add_parser("status")
    s.add_argument("sid")
    p = sp.add_parser("approve")
    p.add_argument("sid")
    p.add_argument("--by", required=True)
    rs = sp.add_parser("restyle", help="완성본을 지금 설정(팩)으로 겉모습만 다시(관제 234)")
    rs.add_argument("sid")
    rs.add_argument("--by", required=True)
    r = sp.add_parser("reject")
    r.add_argument("sid")
    r.add_argument("reason")
    ap.add_argument("--json", action="store_true", help="표 대신 세션 JSON 한 줄(고객 PC MCP 가 읽는다, 관제 234)")
    x = ap.parse_args(argv)
    try:
        if x.cmd == "start":
            patch = {}
            if x.voice:
                pack = MK.load_packs()[str(x.pack)]
                v = next((v for v in [pack["tts"]] + pack["tts"].get("alternates", []) if v.get("name") == x.voice), None)
                if not v:
                    raise MK.MakeError(f"팩 {x.pack} 에 없는 목소리: {x.voice}")
                patch["tts"] = {"voice_id": v["voice_id"], "name": v["name"]}
            if x.channel_name:
                patch["brand"] = {"channel_name": x.channel_name}
            S = MK.start(x.preset, x.pack, topic=x.topic, ref_url=x.ref, facts=x.facts, reuse_of=x.reuse_of, pack_patch=patch or None, deps=DEPS)
            if x.json:
                print(json.dumps(MK.status(S["sid"]), ensure_ascii=False, default=str))
                return 0
            _table(S)
            if S["state"] != "candidates":
                _status(MK.status(S["sid"]))
        elif x.cmd == "choose":
            MK.choose(x.sid, x.n, deps=DEPS)
            if x.json:
                print(json.dumps(MK.status(x.sid), ensure_ascii=False, default=str))
                return 0
            _status(MK.status(x.sid))
        elif x.cmd == "status":
            if x.json:
                print(json.dumps(MK.status(x.sid), ensure_ascii=False, default=str))
                return 0
            _status(MK.status(x.sid))
        elif x.cmd == "approve":
            MK.approve(x.sid, by=x.by, deps=DEPS)
            if x.json:
                print(json.dumps(MK.status(x.sid), ensure_ascii=False, default=str))
                return 0
            _status(MK.status(x.sid))
        elif x.cmd == "restyle":
            MK.restyle(x.sid, by=x.by, deps=DEPS)
            if x.json:
                print(json.dumps(MK.status(x.sid), ensure_ascii=False, default=str))
                return 0
            _status(MK.status(x.sid))
        elif x.cmd == "reject":
            MK.reject(x.sid, x.reason, deps=DEPS)
            _status(MK.status(x.sid))
    except MK.MakeError as e:
        print(json.dumps({"error": e.msg, "code": e.code}, ensure_ascii=False) if x.json else f"거절({e.code}): {e.msg}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
