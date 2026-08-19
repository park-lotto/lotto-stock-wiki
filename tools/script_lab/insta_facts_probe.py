# -*- coding: utf-8 -*-
"""실측: 다이소 영상 N편 전사로 insta_facts 재료 7종이 얼마나 채워지나(서버 실행).

라이브를 안 건드린다 — 읽기만 하고 결과를 화면에 뿌린다.

실행(서버):
    set -a && . /etc/shopping-shorts.env && set +a
    PYTHONPATH=/home/ubuntu/lotto-stock-wiki python3 tools/script_lab/insta_facts_probe.py
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
# ★`pipeline`(key_vault)은 **저장소 루트**에 있고 comment_gen이 그걸 import한다.
#   격리 폴더에서 돌릴 때 루트를 안 얹으면 import가 죽고, insta_facts의 except가
#   그걸 삼켜 "재료 0건"처럼 보인다(2026-08-19 실측으로 잡음).
_REPO = "/home/ubuntu/lotto-stock-wiki"
if Path(_REPO).exists() and _REPO not in sys.path:
    sys.path.append(_REPO)      # append — shopping_shorts는 BASE 것이 이겨야 한다

from shopping_shorts import insta_facts, spine_fill          # noqa: E402
from shopping_shorts.config import DB_PATH                   # noqa: E402

MAX_SOURCES = 5          # app._FACTS_MAX_SOURCES와 같은 값(사장님 지시 2026-08-19)
FIELDS = ("how_to", "targets", "effects", "numbers", "edge", "pain", "price")


def _text(sj):
    try:
        d = json.loads(sj)
    except Exception:
        return ""
    segs = d.get("segments") if isinstance(d, dict) else d
    t = (d.get("text") or d.get("full_text") or "") if isinstance(d, dict) else ""
    if not t and isinstance(segs, list):
        t = " ".join(x.get("text", "") for x in segs if isinstance(x, dict))
    return t


def main():
    c = sqlite3.connect(str(DB_PATH))
    # ★shortcode를 인자로 주면 그것만 본다.
    #   조회수 상위를 그냥 집으면 **서로 다른 제품**이 섞여 합친 결과가 말이 안 된다
    #   (실측 2026-08-19: 양말세제+바닥메꿈제+촉감놀이를 합쳐 "흰 양말부터 바닥 찍힘까지"가
    #    나왔다). 실무에서는 사장님이 같은 소재로 담으므로 자연히 지켜지는 조건이라,
    #    테스트도 같은 조건으로 맞춘다 — merge_sul 주석의 경고와 같은 얘기다.
    picked = [x for x in sys.argv[1:] if not x.startswith("-")]
    if picked:
        q = ("select r.username, r.views, s.script_json from script_extracts s "
             "join reel_history r on r.shortcode = s.shortcode where r.shortcode in (%s)"
             % ",".join("?" * len(picked)))
        rows = c.execute(q, picked).fetchall()
    else:
        rows = c.execute(
            "select r.username, r.views, s.script_json from script_extracts s "
            "join reel_history r on r.shortcode = s.shortcode "
            "where r.caption like '%다이소%' order by r.views desc").fetchall()
    caps = []
    for u, v, sj in rows:
        t = _text(sj)
        if len(re.sub(r"[^가-힣0-9]", "", t)) >= 60:
            caps.append((u, v, t))
        if len(caps) >= MAX_SOURCES:
            break
    if not caps:
        print("전사 재고가 없다 — 확인 필요")
        return 1

    print("== 소재 %d편 ==" % len(caps))
    for u, v, t in caps:
        print("  %-18s %7d회  %s…" % (u, v, t[:38]))

    per = []
    for i, (u, _v, t) in enumerate(caps, 1):
        f = insta_facts.analyze_insta({"captions": [t]}) or {}
        per.append(f)
        got = [k for k in FIELDS if f.get(k)]
        print("\n[%d/%d] %s — 채워진 항목 %d/7: %s"
              % (i, len(caps), u, len(got), ", ".join(got) or "(없음)"))
        for k in FIELDS:
            if f.get(k):
                print("     %-8s %s" % (k, " / ".join(f[k])[:110]))

    merged = spine_fill.merge_sul(per)          # 여러 편 합치기(같은 규약이라 재사용)
    print("\n" + "=" * 68)
    print("★ %d편 합친 결과" % len(caps))
    for k in FIELDS:
        v = merged.get(k) or []
        print("  %-8s %d개  %s" % (k, len(v), " / ".join(v)[:120]))
    filled = sum(1 for k in FIELDS if merged.get(k))
    print("\n  채워진 항목: %d/7" % filled)

    slots = spine_fill.slots_from_insta(merged)
    print("\n★ 슬롯 변환 결과 (%d개)" % len(slots))
    for k, v in slots.items():
        print("  {%s} = %s" % (k, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
