# -*- coding: utf-8 -*-
"""담은 해외 원본 4편 → 오용형 스파인(56)으로 대본 조립."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from shopping_shorts.app import Store, DB_PATH, _slots_for_spine, _FACTS_MAX_SOURCES
from shopping_shorts import spine_fill

SC = ['grab_instagram_68a075a9277d', 'grab_instagram_8a3372c3f8e6',
      'grab_instagram_96c0756bc4df', 'grab_youtube_4bf770895785']

s = Store(DB_PATH)
print("SOURCE_MAX(재료 상한):", _FACTS_MAX_SOURCES)

sources = []
for sc in SC:
    e = s.get_extract(sc) or {}
    if not e:
        print("  !! 추출 없음:", sc); continue
    e = dict(e); e['shortcode'] = sc
    sources.append(e)
print("재료로 넘길 영상:", len(sources), "편")
for x in sources:
    print("   - %s | 자막%d자 장면%d개" % (x['shortcode'], len(x.get('full_text') or ''), len(x.get('segments') or [])))

# 오용형 스파인 조회
sp = None
allsp = s.list_spines()
for cand in allsp:
    if str(cand.get('id')) == '56':
        sp = cand; break
print("전체 스파인:", len(allsp))
if sp is None:
    print("id=56 없음. 후보:")
    for c in allsp[:40]:
        print("   id=%s %s" % (c.get('id'), (c.get('name') or '')[:44]))
    raise SystemExit(1)
print("스파인: id=%s name=%s" % (sp.get('id'), sp.get('name')))
print("beat_roles:", str(sp.get('beat_roles'))[:200])

slots, prob = _slots_for_spine(sp, sources, s)
print()
print("=" * 70)
print("못 한 이유:", prob or "(없음)")
print("채워진 슬롯:", len(slots or {}))
for k, v in (slots or {}).items():
    print("   %-16s %s" % (k, str(v)[:100]))

if slots:
    filled = spine_fill.fill(sp, slots)
    print()
    print("=" * 70)
    print("조립된 대본:")
    print(json.dumps(filled, ensure_ascii=False, indent=1)[:2500])
