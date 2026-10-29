# -*- coding: utf-8 -*-
"""버퍼 예약 전수 점검(읽기 전용) — 올린 영상마다 Buffer 실물 상태·제목 인포크 번호·설명란 쿠팡/인포크 링크·
인포크 공개 페이지 블록이 맞는지, 드라이브 폴더 위치(예약/완료)가 상태와 맞는지 본다. 아무것도 바꾸지 않는다.

    py tools/buffer_link_audit.py [--since 2026-10-20] [--web web_tree.json]

--web: 웹 드라이브 트리(JSON, {폴더: {files:{}, 예약:{}, 완료:{}}}) — G: 동기화가 늦을 때 웹 기준으로 위치를 본다.
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from shopping_shorts import buffer_api  # noqa: E402
from tools import buffer_post as bp  # noqa: E402 — 키 찾기 주인(_key_for)

KEYS = os.path.expanduser("~/.claude/buffer_keys.json")
LEDGER = os.path.expanduser("~/.claude/buffer_post_ledger.json")
DRIVE = r"G:\내 드라이브\버퍼예약"
INPOCK_BY_CHANNEL = bp.INPOCK_BY_CHANNEL
_Q = 'query($id: PostId!) { post(input: { id: $id }) { id status dueAt sentAt externalLink text } }'
_NUM = re.compile(r"^\s*(\[\d+\]|\d+\.)\s")


def _inpock_titles(acct):
    """공개 페이지 블록을 '제목 → 주소' 줄로 — 읽기는 bp._inpock_blocks 한 곳."""
    try:
        return [f"{t} → {u or '(링크없음)'}{'' if o else ' (비공개)'}" for t, u, o in bp._inpock_blocks(acct)]
    except Exception as e:  # noqa: BLE001 — 점검 도구: 못 받으면 표에 적는다
        return [f"(받기 실패 {e})"]


def _where(folder, name, web):
    stem = os.path.splitext(name)[0]
    if web is not None:
        node = web.get(folder) or {}
        spots = [k for k in ("files", "예약", "완료") if name in (node.get(k) or {})]
        return ",".join("꼭대기" if s == "files" else s for s in spots) or "없음"
    spots = []
    for sub, label in (("", "꼭대기"), ("예약", "예약"), ("완료", "완료")):
        if os.path.exists(os.path.join(DRIVE, folder, sub, name)):
            spots.append(label)
    return ",".join(spots) or ("없음(.txt만)" if os.path.exists(os.path.join(DRIVE, folder, "완료", stem + ".txt")) else "없음")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-10-20")
    ap.add_argument("--web")
    ap.add_argument("--inpock", action="store_true", help="채널별 인포크 공개 블록 목록도 같이 낸다")
    a = ap.parse_args()
    keys = json.load(open(KEYS, encoding="utf-8"))
    rows = json.load(open(LEDGER, encoding="utf-8"))
    web = json.load(open(a.web, encoding="utf-8")) if a.web else None
    out = []
    for r in rows:
        if (r.get("at") or "") < a.since:
            continue
        folder, svc = r["folder"], r.get("service", "youtube")
        ch = bp._acct_no(folder)
        key = bp._key_for(keys, folder)
        try:
            p = (buffer_api._call(key, _Q, {"id": r["post_id"]}).get("post") or {}) if key else {}
        except Exception as e:  # noqa: BLE001
            p = {"status": f"조회실패 {str(e)[:40]}"}
        text = p.get("text") or ""
        title = buffer_api._yt_title(text) if text else ""
        num = (_NUM.match(title) or [None, ""])[1] if title else ""
        acct = bp._inpock_acct(folder)
        # 짝 = 올릴 때 장부에 남긴 인포크 제목(r["inpock"], 관제 282). 옛 행은 유튜브 제목 앞 번호로만 찾는다
        block = ""
        if acct and r.get("inpock"):
            block = next((t for t in _inpock_titles(acct) if t.split(" → ")[0].strip() == r["inpock"]),
                         f"★없음: '{r['inpock']}' 블록이 공개 페이지에 없다")
        elif num and acct:
            block = next((t for t in _inpock_titles(acct) if t.startswith(num + " ") or t.startswith(num)), "")
        if not block:
            block = "(짝 기록 없음 — 옛 행)"
        out.append({
            "folder": folder, "svc": svc, "file": r["file"], "status": p.get("status") or "Buffer에없음",
            "due": (p.get("dueAt") or r.get("due") or "")[:16], "link": p.get("externalLink") or "",
            "title": title, "num": num, "inpock_acct": acct, "inpock_block": block,
            "desc_inpock": "inpock" in text, "desc_coupang": "link.coupang" in text,
            "where": _where(folder, r["file"], web) if svc == "youtube" else "",
        })
    # 중복·칸 겹침(사장님 10-26 "중복 업로드 절대 금지 / 한 번에 두 개는 없다") — 장부 전체에서
    live = [r for r in rows if r.get("final_status") != "deleted"]
    seen, problems = {}, []
    for r in live:
        k = (r["folder"], r.get("service", "youtube"), r.get("fp") or r["file"])
        if k in seen:
            problems.append(f"중복 업로드: {r['folder']} {k[1]} {r['file']} ({seen[k]} / {r.get('due')})")
        seen[k] = r.get("due")
    slot = {}
    for r in live:
        k = (r["folder"], r.get("service", "youtube"), (r.get("due") or "")[:16])
        if k in slot and slot[k] != r["file"]:
            problems.append(f"한 칸에 두 개: {r['folder']} {k[1]} {k[2]} {slot[k]} + {r['file']}")
        slot[k] = r["file"]
    print("중복·칸겹침:", problems or "없음", file=sys.stderr)
    if a.inpock:
        out = {"rows": out, "inpock": {acct: _inpock_titles(acct) for acct in sorted(set(INPOCK_BY_CHANNEL.values()) | set(bp.INPOCK_BY_FOLDER.values()))}}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
