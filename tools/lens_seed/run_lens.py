# -*- coding: utf-8 -*-
"""오용형 씨앗 6장 × 렌즈 = 6클릭. 결과 전량을 가공 없이 출력."""
import json, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from shopping_shorts import lens_discover as L

SEEDS = [
    ("실리콘뚜껑", "프레임", "/tmp/seed_silicone.jpg"),
    ("실리콘뚜껑", "썸네일", "/tmp/thumb_u52_9Xnt6Oo.jpg"),
    ("매직랩",     "프레임", "/tmp/seed_magicwrap.jpg"),
    ("매직랩",     "썸네일", "/tmp/thumb_azDE6caCwjU.jpg"),
    ("북엔드",     "프레임", "/tmp/seed_bookend.jpg"),
    ("북엔드",     "썸네일", "/tmp/thumb_U5ee0EsBfww.jpg"),
]

print("렌즈 잔량(시작):", L.account_searches_left(force=True))
print("로케일:", L._LENS_LOCALES, "| 클릭당 상한:", L._MAX_CALLS_PER_SEARCH)
print("=" * 78)

allout = []
for name, kind, path in SEEDS:
    with open(path, "rb") as f:
        b = f.read()
    up = L.upload_frame(b)
    print("\n### %s / %s  (%d KB)" % (name, kind, len(b) // 1024))
    print("업로드:", up)
    if not up:
        print("  !! 업로드 실패 — 렌즈 호출 안 함")
        continue
    st = {}
    t0 = time.time()
    try:
        res = L.search_similar_videos(up, timeout=60, stats=st)
    except Exception as e:
        print("  !! 렌즈 예외:", type(e).__name__, e)
        continue
    print("결과 %d건 / %.1f초 / stats=%s" % (len(res), time.time() - t0, st))
    for r in res:
        allout.append(dict(r, _seed=name, _kind=kind))
        print("   [%-9s] %s" % (r.get("platform"), (r.get("url") or "")[:82]))
        print("        %s" % (r.get("title") or "")[:96])
print("\n" + "=" * 78)
print("렌즈 잔량(끝):", L.account_searches_left(force=True))
with open("/tmp/lens_out.json", "w", encoding="utf-8") as f:
    json.dump(allout, f, ensure_ascii=False, indent=1)
print("총 결과:", len(allout), "건 → /tmp/lens_out.json")
