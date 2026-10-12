# 씨앗(원본)과 결과가 얼마나 다른가 — 원본 컷 비율 · 원본 문장 6글자 조각 겹침 (2026-09-18 사장님 "백본이랑 다르게 보여야")
import sys, re; sys.path.insert(0, "/tmp/ab")
from shopping_shorts.store import Store
from shopping_shorts import backbone_assemble as ba
st = Store("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
base = st.get_mix_job(sys.argv[1]); srcs = ba.sources_from_extract(base.get("extract") or {})
ko = lambda t: sum(1 for c in t if "가" <= c <= "힣") / max(1, sum(1 for c in t if c.isalpha()))
# 씨앗 지정: 3번째 인자(예 s0) — 없으면 한국어 소스 중 가장 긴 것
_want = sys.argv[2] if len(sys.argv) > 2 else None
kor = [s for s in srcs if ko(s.get("full_text") or "") > 0.7]
bb = next((s for s in srcs if s["video_id"] == _want), None) or max(kor or srcs, key=lambda s: len((s.get("full_text") or "").strip()))
IDX = ba._seg_index(srcs)
print("원본(백본)", bb["video_id"], "| 한국어", round(ko(bb.get("full_text") or ""), 2), "|", (bb.get("full_text") or "")[:80].replace("\n", " "))
def grams(t, n=6):
    t = re.sub(r"\s+", "", t); return {t[i:i + n] for i in range(len(t) - n + 1)}
G = grams(bb.get("full_text") or "")
for style in ("제품정체형", "발명품형", "오용형"):
    note = {}
    given, bs, meta = ba.assemble(srcs, bb["video_id"], st, style=style, seed="diffchk" + style, note=note)
    if not given:
        print(style, "실패", note); continue
    segs = [s for b in bs for s in (b.get("segs") or [])]
    from_bb = sum(1 for s in segs if IDX.get(s, {}).get("vid") == bb["video_id"])   # ★이름표는 _seg_index 한 곳(소스 번호)
    g = set().union(*[grams(l) for l in given.split("\n")])
    print("== %s(%s) 원본 컷 %d/%d | 원본과 겹치는 6글자 조각 %d/%d (%.0f%%)" % (style, meta["spine"]["name"], from_bb, len(segs), len(g & G), len(g), 100 * len(g & G) / max(1, len(g))))
    for l in given.split("\n"): print("   ", l)
