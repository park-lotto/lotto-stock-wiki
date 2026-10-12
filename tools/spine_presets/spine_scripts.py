# -*- coding: utf-8 -*-
"""이븐쇼핑 백본 재료로 **유튜브형 스파인 8개의 대본만** 뽑는다 (2026-09-18 사장님 "렌더 말고 대본만 먼저").

같은 재료·같은 묶음, 스파인만 다르게. 모델 호출은 스파인당 1회(write_lines)뿐 — 렌더·TTS 없음.
★_spine_style이 있는 최신 backbone_assemble이어야 골격이 먹는다(구식이면 나열문이 나온다).
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/tmp/abtest")
sys.path.append("/home/ubuntu/lotto-stock-wiki")

from shopping_shorts import backbone_assemble as BA
from shopping_shorts.store import Store

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
SRC_JOB = "ba630a537511"
DEAD = "tjhKrXqsTGI"

st = Store(DB)
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
ex = json.loads(con.execute("select extract_json from mix_jobs where job_id=?", (SRC_JOB,)).fetchone()[0])
srcs = [v for v in ex.values() if isinstance(v, dict)] if isinstance(ex, dict) else ex

seg_index = {k: v for k, v in BA._seg_index(srcs).items() if DEAD not in k}
o = json.load(open("/tmp/bb_assemble_out.json"))
G = json.loads(json.dumps(o["meta"]["groups"]))
for g in G["groups"]:
    g["cuts"] = [c for c in (g.get("cuts") or []) if DEAD not in c]

CTA_MARK = ("댓글", "링크", "프로필", "구독", "팔로우", "남겨")
BAN = ("거든요", "예요", "에요", "습니다", "하세요", "네요", "드릴게요")   # 유튜브형 금지 어미(반말 규칙)

spines = [s for s in st.list_spines(status="approved") if s.get("no_cta")]
spines.sort(key=lambda s: -(s.get("source_count") or 0))
print("유튜브형 스파인 %d개 — 같은 재료로 대본만 뽑는다\n" % len(spines))

for sp in spines:
    sid, name = sp["id"], (sp.get("name") or "")
    try:
        lines = BA.write_lines(G, sp, seg_index, target_seconds=25) or []
    except Exception as exc:
        print("[%s] %s — 예외 %s\n" % (sid, name, repr(exc)[:90]))
        continue
    txt = [L.get("text", "") for L in lines]
    if not txt:
        print("[%s] %s — 줄 0개\n" % (sid, name))
        continue
    chars = len("".join(txt).replace(" ", ""))
    cta = [t for t in txt if any(m in t for m in CTA_MARK)]
    polite = [t for t in txt if any(t.rstrip(".").endswith(b) for b in BAN)]
    print("=" * 76)
    print("[%s] %s   근거 %s편 · 은폐=%s · %s자/30초" % (
        sid, name, sp.get("source_count"), sp.get("hook_conceal"), sp.get("chars_per_30s")))
    print("   줄 %d · %d자 · CTA %d줄 · 존댓말 %d줄" % (len(txt), chars, len(cta), len(polite)))
    for i, t in enumerate(txt):
        mark = ""
        if any(m in t for m in CTA_MARK):
            mark = "   ← CTA(유튜브형은 없어야 함)"
        elif any(t.rstrip(".").endswith(b) for b in BAN):
            mark = "   ← 존댓말"
        print("   %d %s%s" % (i, t, mark))
    print()
