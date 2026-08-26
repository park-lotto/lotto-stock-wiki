# -*- coding: utf-8 -*-
"""북엔드 해외 원본을 담고 prewarm까지 태운다."""
import sys, io, hashlib, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from shopping_shorts.app import Store, DB_PATH, _grab_platform, _enrich_grab, _enqueue_prewarm

CID = 0
ITEMS = [
    ("https://www.instagram.com/reel/DYXHIpap2v8/", "Broom Holder Wall Mount"),
    ("https://www.instagram.com/reel/DXsxeozz23z/", "Door hanger | Heavy Duty Metal Over Door"),
    ("https://www.instagram.com/reel/DTVSEURgWcy/", "This genius spoon rest is my kitchen's new MVP"),
    ("https://www.youtube.com/shorts/ZjFlPhYTwRE", "Dish scrubbing brush online available on Amazon Flipkart"),
]

store = Store(DB_PATH)
for url, title in ITEMS:
    plat = _grab_platform(url)
    sc = "grab_" + plat + "_" + hashlib.sha1(url.encode("utf-8", "ignore")).hexdigest()[:12]
    added = store.mix_basket_add(sc, url=url, thumbnail="", name=title[:120],
                                 caption=title[:200], customer_id=CID, video_url="")
    store.autoload_reset(sc)
    print("%-7s %s" % ("담김" if added else "이미있음", url))
    print("        sc=%s  plat=%s" % (sc, plat))
    try:
        _enrich_grab(url, sc, CID)
        print("        메타 보강 완료")
    except Exception as e:
        print("        메타 보강 실패:", type(e).__name__, e)
    try:
        _enqueue_prewarm(Store(DB_PATH), sc, url, caption=title[:200], customer_id=CID)
        print("        prewarm 큐 등록")
    except Exception as e:
        print("        prewarm 실패:", type(e).__name__, e)
print()
print("현재 cid0 담김:", len(store.mix_basket_shortcodes(customer_id=CID)))
