# -*- coding: utf-8 -*-
"""노바 작가 방식 시험 — 사장님이 프로그램에서 누른 것과 **같은 재료**로, 한 번 호출에 스타일 틀 그대로 대본을 쓰게 한다.
  (서버, repo 폴더에서, env 적재 후) python3 tools/script_diff/nova_style_proto.py <work_id> <shortcode> <style_id,...>

2026-09-27 사장님: "제미니웹에서 영상을 주고 사람들이 좋아할 특징을 조사하고, 대본 스타일을 참고해 틀을 유지하고
기능·특징·장점을 쓰라고 하면 안 되나 — 노바 작가가 그렇게 한다. 웹에서 하면 되는데 API로 하면 왜 안 되나"
→ 같은 조건: 재료는 앱의 `_materials_for_generate`(=/api/wiki/generate가 쓰는 함수) 그대로, 모델은 대본생성과 같은 `_call_json`
  (vertex_enabled면 사장님 Vertex). DB에는 **아무것도 안 쓴다**. 결과는 화면에 나온 라이브 대본과 나란히 출력.
"""
import sys, json, re
sys.path.insert(0, ".")
wid, shortcode, style_ids = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
from shopping_shorts import app as A, story_writer as sw, script_generate as sg
from shopping_shorts.store import Store
from shopping_shorts.script_gate import SPEECH_CHARS_PER_SEC as CPS

store = Store(A.DB_PATH)
work = store.get_produce_work(wid, customer_id=None) if False else None
import sqlite3
c = sqlite3.connect("file:%s?mode=ro" % A.DB_PATH, uri=True)
cid, sj = c.execute("select customer_id, state_json from produce_works where work_id=?", (wid,)).fetchone()
s2 = json.loads(sj or "{}").get("s2") or {}
spines = {s.get("id"): s for s in store.list_spines()}
it = store.get_wiki_item(shortcode, customer_id=cid) or {}
seed = (s2.get("seed") or {}).get("text") or it.get("full_text") or ""
body = {"work_id": wid, "shortcode": shortcode, "selected_shortcode": shortcode, "target_seconds": 25}
src, facts, job, jid, scene = A._materials_for_generate(it, body, store, cid, [spines[i] for i in style_ids])
vis = [v for v in ((job or {}).get("extract") or {}).values() if isinstance(v, dict)]
product = (s2.get("materials") or {}).get("topic_product") or sg._sources_product(src) or ""
seg_ids = {x.get("seg_id") for v in vis for x in (v.get("segments") or []) if x.get("seg_id")}
print("재료: 영상 %d편 · 컷 %d개 · 제품 %r · 씨앗 %d자" % (len(vis), len(seg_ids), product, len(seed)))

BRIEF = """너는 한국 썰쇼핑 숏폼 나레이션 작가다. 이 제품으로 **팔릴 수밖에 없는 대본**을 써라.

[씨앗 대본]은 이 제품으로 이미 터진 영상의 말이다. [스타일 틀]은 고객이 고른 대본 스타일이다.

■ 틀을 지켜라 — [스타일 틀]의 **칸 순서 그대로**, 칸마다 예시 문장의 **꼴(말 뼈대)**을 빌려 이 제품에 맞게 새로 쓴다.
  칸 하나에 1~2줄. 칸을 빼거나 순서를 바꾸지 마라. {빈칸}은 이 제품 내용으로 채운다.
■ 차별점 = 기능·특징·장점 — 씨앗이 이미 말한 셀링포인트는 **제목·미끼 말고는** 쓰지 마라.
  본문은 [재료]를 보고 **사람들이 좋아할 만한** 기능·특징·장점(씨앗에 없는 것)으로 채운다.
  재료에 적힌 사실·장면에서 보이는 것만 쓴다. 수치·나라·사람·가격을 지어내지 마라.
■ 말투 — 남 얘기 전하는 썰. 보는 사람에게 말을 걸지 마라. 줄 끝: ~는데 · ~는 거 · ~다는데 · ~다고 · ~버림 · ~였음
■ 분량 — 전체 약 %d자(읽으면 약 %d초).
■ 줄마다 cuts에 그 말이 **화면에 보이는** 컷 번호를 [재료]에서 1~2개 골라 적어라(목록에 있는 번호만)."""

SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
    "role": {"type": "string"}, "text": {"type": "string"}, "cuts": {"type": "array", "items": {"type": "string"}}},
    "required": ["role", "text", "cuts"]}}, "seed_points": {"type": "array", "items": {"type": "string"}}},
    "required": ["lines", "seed_points"]}


def style_block(sp):
    t = sp.get("templates") or {}
    rows = []
    for r in sp.get("beat_roles") or []:
        ex = [x for x in (t.get(r) or []) if isinstance(x, str)][:2]
        rows.append("  %s: %s" % (r, " / ".join("「%s」" % x for x in ex) if ex else "(예시 없음)"))
    return "%s\n%s" % (sp.get("name") or "", "\n".join(rows))


mats = sw.source_block(vis) + ("\n\n[제품 사실]\n" + facts[:1500] if facts else "")
for sid in style_ids:
    sp = spines[sid]
    prompt = (BRIEF % (int(25 * CPS), 25)) + "\n\n[제품] %s\n\n[씨앗 대본]\n%s\n\n[스타일 틀]\n%s\n\n[재료]\n%s\n\n" % (
        product, seed.strip(), style_block(sp), mats) + "seed_points에는 씨앗이 자랑한 셀링포인트를 먼저 짧게 적어라."
    note = {}
    out = sg._call_json(prompt, SCHEMA, note=note) or {}
    lines = out.get("lines") or []
    bad_cuts = sum(1 for L in lines for x in (L.get("cuts") or []) if x not in seg_ids)
    roles = [L.get("role") for L in lines]
    order_ok = [r for r in roles if r in (sp.get("beat_roles") or [])]
    txt = " ".join(L.get("text", "") for L in lines)
    print("\n" + "=" * 70)
    print("[노바식 한 번 호출] 스타일 %s · %d자 · 인증 %s · 없는 컷번호 %d개" % (sp.get("name"), len(txt), note.get("auth"), bad_cuts))
    print("  스타일 칸 순서:", sp.get("beat_roles"))
    print("  나온 칸 순서  :", roles)
    print("  씨앗 셀링포인트:", out.get("seed_points"))
    for L in lines:
        print("   %-10s | %s   %s" % (L.get("role"), L.get("text"), L.get("cuts")))

print("\n" + "=" * 70 + "\n[비교] 사장님 화면에 나온 라이브 대본")
for d in s2.get("drafts") or []:
    print("  ── %s" % d.get("style_name"))
    for b in d.get("beats") or []:
        print("   %-6s | %s" % (b.get("role"), b.get("text")))
