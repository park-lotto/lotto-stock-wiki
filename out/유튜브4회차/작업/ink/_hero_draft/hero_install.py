# 이미 빌드된 장면 template 에 새 주인공을 싣는다(장면마다 빌드 도구가 달라도 빌드 뒤 이 한 줄이면 된다).
# 쓰기: py hero_install.py <장면폴더>/template [...]
#   → brand/hero_strokes.js · brand/hero_put.js · brand/hero/c_*_flat.png 복사
#   → index.html 의 hq.js(또는 assets.js) <script> 바로 뒤에 두 스크립트 태그 삽입(이미 있으면 그대로)
import sys, os, shutil, glob, re
HD = os.path.dirname(os.path.abspath(__file__))
TAGS = '<script src="brand/hero_strokes.js"></script><script src="brand/hero_put.js"></script>'
for t in sys.argv[1:]:
    b = os.path.join(t, "brand"); hb = os.path.join(b, "hero"); os.makedirs(hb, exist_ok=True)
    for fn in ("hero_strokes.js", "hero_put.js"): shutil.copy(os.path.join(HD, fn), os.path.join(b, fn))
    for f in glob.glob(os.path.join(HD, "c_*_flat.png")) + glob.glob(os.path.join(HD, "l_*.png")): shutil.copy(f, os.path.join(hb, os.path.basename(f)))
    p = os.path.join(t, "index.html"); h = open(p, encoding="utf8").read()
    if "hero_put.js" not in h:
        m = list(re.finditer(r'<script src="brand/(assets|hq)\.js"></script>', h))
        if not m: sys.exit(f"{p}: hq.js/assets.js 스크립트 태그 없음")
        e = m[-1].end(); h = h[:e] + TAGS + h[e:]
        open(p, "w", encoding="utf8").write(h)
    print("hero installed", t)
