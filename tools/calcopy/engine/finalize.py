# -*- coding: utf-8 -*-
"""완성본 봉인 — final.mp4 를 다 쓴 뒤 **맨 마지막에** 한 번 부른다. 광고 표시·기본 규격을 재고 md5 를 봉인 파일에 적는다(2026-10-25).

왜(10-25 전 편 감사): 완성본을 쓰는 렌더 길이 8개인데 검사·광고 표시가 길마다 있거나 없었다 — 광고 없음 7편(트롯파파 4·숏템리폿 12·13·
반동마우스 v2)이 전부 검사 없는 길에서 나왔고, `자동검사.json` 은 마지막 실행으로 덮여 '통과한 판'과 '납품한 판'이 짝이 아니었다(잇템로그 04).
그래서 렌더 길을 하나로 합치는 대신, 납품(engine/deliver.to_drive)이 **봉인 파일의 md5 와 같은 파일만** 받는다.
봉인 뒤 한 프레임이라도 바뀌면(썸네일 덮기·자막 한 번 더 등) md5 가 달라 납품이 거절된다 → 손 스크립트가 ffmpeg 로 따로 써도 못 나간다.

판단 주인: '이 완성본이 납품해도 되는 그 파일인가' = seal()·verify() 한 곳. 부르는 곳 = render_bench.render · master_guard.encode_final
(render_itssum·render_jaemi·preset_make) · narr_video.build. 새 렌더 길은 final 을 다 쓴 뒤 seal() 을 부르면 된다.
봉인 파일 = <final>.seal.json (final 옆).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

SEAL_VERSION = "seal:v1"
SIZE = (1080, 1920)


def md5(p) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def seal_path(final) -> Path:
    final = Path(final)
    return final.with_name(final.name + ".seal.json")


def _probe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration,r_frame_rate:format_tags=comment",
                        "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    j = json.loads(r.stdout or "{}")
    st = j.get("streams") or []
    v = next((s for s in st if s.get("codec_type") == "video"), {})
    a = next((s for s in st if s.get("codec_type") == "audio"), {})
    num, _, den = str(v.get("r_frame_rate") or "0/1").partition("/")
    return {"w": int(v.get("width") or 0), "h": int(v.get("height") or 0), "fps": round(float(num) / float(den or 1), 3) if num else 0.0,
            "vdur": float(v.get("duration") or 0), "adur": float(a.get("duration") or 0) if a else None,
            "comment": str(((j.get("format") or {}).get("tags") or {}).get("comment") or "")}


def checks(final: Path) -> list[dict]:
    """렌더 길과 상관없이 모든 완성본에 같은 자로 재는 것(판 설정이 필요 없는 것만). 각 {what, ok, value}."""
    from tools.calcopy.engine import ad_mark
    p = _probe(final)
    fr = 1 / p["fps"] if p["fps"] else 0.04
    return [
        {"what": "광고 표시", "ok": ad_mark.MARK in p["comment"], "value": p["comment"] or "표식 없음"},
        {"what": "화면 크기", "ok": (p["w"], p["h"]) == SIZE, "value": f"{p['w']}x{p['h']}"},
        {"what": "소리 있음", "ok": p["adur"] is not None, "value": "있음" if p["adur"] is not None else "없음"},
        {"what": "영상=소리 길이", "ok": p["adur"] is not None and abs(p["vdur"] - p["adur"]) <= fr + 0.05,
         "value": f"영상 {p['vdur']:.3f} · 소리 {p['adur']}"},
    ]


def seal(final, renderer: str, script=None, log=print) -> dict:
    """(판단 주인) final 에 광고 표시가 없으면 입히고, checks() 를 재고, md5 를 봉인 파일에 적는다. final 을 바꾸는 마지막 단계 뒤에 불러야 한다.
    script = 이 완성본을 만든 대본 파일(렌더 뒤 대본이 바뀌면 납품이 거절된다). 반환 = 봉인 내용(ok 포함)."""
    from tools.calcopy.engine import ad_mark
    final = Path(final)
    ad_mark.apply_inplace(final, log=log)      # 이미 있으면 그대로 — 광고 표시 주인 = engine/ad_mark
    rows = checks(final)
    ok = all(r["ok"] for r in rows)
    rec = {"seal": SEAL_VERSION, "file": final.name, "md5": md5(final), "size": final.stat().st_size, "renderer": renderer,
           "script": str(script) if script else None, "script_md5": md5(script) if script and Path(script).exists() else None,
           "sealed_at": time.strftime("%Y-%m-%d %H:%M:%S"), "ok": ok, "checks": rows}
    seal_path(final).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [f"{r['what']}({r['value']})" for r in rows if not r["ok"]]
    log(f"[봉인] {final.name} md5 {rec['md5'][:8]} · {renderer} · " + ("기본 검사 통과" if ok else "★기본 검사 실패 — 납품 안 됨: " + ", ".join(bad)))
    return rec


def verify(final) -> tuple[bool, str, dict | None]:
    """봉인이 이 파일 그대로인가 — (ok, 이유, 봉인 내용). 납품(deliver)이 부른다."""
    final = Path(final)
    sp = seal_path(final)
    if not final.exists():
        return False, f"파일 없음: {final}", None
    if not sp.exists():
        return False, "봉인 없음 — 이 파일은 봉인하는 렌더 길(finalize.seal)로 만들지 않았다", None
    rec = json.loads(sp.read_text(encoding="utf-8"))
    if rec.get("seal") != SEAL_VERSION:
        return False, f"봉인 형식이 다름({rec.get('seal')})", rec
    got = md5(final)
    if got != rec.get("md5"):
        return False, f"봉인 뒤 파일이 바뀜(봉인 md5 {rec.get('md5', '')[:8]} · 지금 {got[:8]}) — 마지막으로 final 을 고친 단계 뒤에 seal() 을 불러야 한다", rec
    if not rec.get("ok"):
        return False, "봉인 때 기본 검사 실패: " + ", ".join(f"{r['what']}({r['value']})" for r in rec.get("checks", []) if not r["ok"]), rec
    return True, "봉인 그대로", rec
