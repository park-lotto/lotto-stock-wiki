"""여행 숏폼 사진 모션 효과 시안 — 스카이베이 공식 사진·손님 사진에 효과 9가지를 3초씩 입혀 한 편으로(사장님 10-22 "여행쇼츠 사진들 모션효과 어울리는것").

    py tools/travel/work_skybay/fx_demo.py            → fx_demo/index.html
    npx -y hyperframes@0.8.105 render tools/travel/work_skybay/fx_demo -o tools/travel/work_skybay/fx_demo/fx.mp4

효과 출처 = 저장된 모션 프리셋·갤러리 문법(이름 옆 괄호). 색·글꼴은 1편 정본 템플릿(크림·주황·프리텐다드)을 따른다.
움직임: 등장 ease-out(power3.out) 0.2~0.4초 · scale(0)에서 시작 안 함 · 바운스 안 씀.
"""
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "fx_demo"
A = OUT / "assets"
SEG = 3.2
CREAM, ORANGE = "#F6F1EA", "#E8542A"


def img(src, name, w=1200):
    im = Image.open(src).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)))
    im.save(A / name, quality=86)
    return "assets/" + name


def main():
    A.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path.home() / "숏템자료/모션그래픽엔진/work/2026-10-20_라면레시피/ramen/brand/gsap.min.js", A / "gsap.min.js")
    shutil.copy(ROOT / "shopping_shorts/static/fonts/Pretendard-ExtraBold.otf", A / "P.otf")
    P = lambda no: img(HERE / "photos" / ("%02d.jpg" % (no - 1)), "o%02d.jpg" % no)  # noqa: E731
    cm = json.loads((HERE / "ep1/work/comments.json").read_text(encoding="utf-8"))
    picked = [ROOT / x["photo"] for v in cm.values() for x in v if x.get("photo")]
    pool = sorted((HERE / "ep1/work").glob("cm_[12]/rv_photos/*.jpg"))[:60]
    G = [img(p, "g%02d.jpg" % k, 700) for k, p in enumerate(picked)]
    W = [img(p, "w%02d.jpg" % k, 360) for k, p in enumerate(pool)]
    quotes = [x["quote"] for v in cm.values() for x in v][:4]

    body, js = [], []

    def scene(k, title, inner, setup):
        t0 = k * SEG
        sid = "s%d" % k
        body.append('<div id="%s" class="clip sc" data-start="%.2f" data-duration="%.2f" data-track-index="1">%s'
                    '<div class="lab"><b>%d</b>%s</div></div>' % (sid, t0, SEG, inner, k + 1, title))
        js.append('tl.fromTo("#%s .lab",{opacity:0,y:-20},{opacity:1,y:0,duration:0.25,ease:"power3.out"},%.2f);' % (sid, t0 + 0.05))
        setup(sid, t0)

    # 1 켄 번즈(지금 1편)
    scene(0, "켄 번즈 — 지금 1편", '<img class="full kb" src="%s">' % P(5),
          lambda s, t: js.append('tl.fromTo("#%s .kb",{scale:1},{scale:1.075,duration:%.2f,ease:"none"},%.2f);' % (s, SEG, t)))

    # 2 깊이 시차 — 사진 3장이 다른 속도로(달밤 2.5D 시차)
    def par(s, t):
        for j, (dx, sp) in enumerate([(-60, 40), (0, 90), (60, 160)]):
            js.append('tl.fromTo("#%s .d%d",{y:%d},{y:%d,duration:%.2f,ease:"none"},%.2f);' % (s, j, sp, -sp, SEG, t))
    scene(1, "깊이 시차 — 사진 3겹", '<img class="full dim" src="%s"><img class="d0 dp" src="%s"><img class="d1 dp" src="%s"><img class="d2 dp" src="%s">'
          % (P(11), P(12), G[0], P(6)), par)

    # 3 사진 벽 기울여 흐르기 → 한 장 확대(사진 앱 광고)
    tiles = "".join('<img src="%s">' % W[k % len(W)] for k in range(48))
    def wall(s, t):
        js.append('tl.fromTo("#%s .wall",{y:0},{y:-520,duration:%.2f,ease:"none"},%.2f);' % (s, SEG, t))
        js.append('tl.fromTo("#%s .hero",{opacity:0,scale:0.6},{opacity:1,scale:1,duration:0.4,ease:"power3.out"},%.2f);' % (s, t + 1.7))
    scene(2, "손님 사진 벽 → 한 장", '<div class="wall">%s</div><div class="hero"><img src="%s"><span>실제 손님 사진</span></div>' % (tiles, G[2]), wall)

    # 4 포털 줌 — 가운데 창이 다음 장면이 되어 화면을 채움(갤러리 portal)
    def portal(s, t):
        js.append('tl.fromTo("#%s .win",{clipPath:"inset(38%% 30%% 38%% 30%% round 40px)"},{clipPath:"inset(0%% 0%% 0%% 0%% round 0px)",duration:1.1,ease:"power3.inOut"},%.2f);' % (s, t + 1.0))
        js.append('tl.fromTo("#%s .base",{scale:1},{scale:1.25,duration:2.1,ease:"power2.in"},%.2f);' % (s, t))
    scene(3, "포털 줌 전환", '<img class="full base" src="%s"><img class="full win" src="%s">' % (P(1), P(5)), portal)

    # 5 낮 → 노을 크로스페이드(갤러리 day→night, 0.8초)
    def dusk(s, t):
        js.append('tl.fromTo("#%s .b",{opacity:0},{opacity:1,duration:0.8,ease:"power2.inOut"},%.2f);' % (s, t + 1.2))
        js.append('tl.fromTo("#%s .full",{scale:1},{scale:1.06,duration:%.2f,ease:"none"},%.2f);' % (s, SEG, t))
    scene(4, "낮 → 노을", '<img class="full" src="%s"><img class="full b" src="%s">' % (P(11), P(6)), dusk)

    # 6 폴라로이드 떨어져 쌓기
    pol = "".join('<div class="pol p%d"><img src="%s"></div>' % (j, G[j % len(G)]) for j in range(4))
    def drop(s, t):
        for j, r in enumerate([-8, 6, -3, 9]):
            js.append('tl.fromTo("#%s .p%d",{y:-900,rotate:%d,opacity:1},{y:0,rotate:%d,duration:0.45,ease:"power3.out"},%.2f);' % (s, j, r * 3, r, t + 0.3 + j * 0.55))
    scene(5, "손님 사진 폴라로이드", '<div class="desk"></div>' + pol, drop)

    # 7 격자 채우기 + 숫자(Jev 격자)
    cells = "".join('<img class="c" src="%s">' % W[k % len(W)] for k in range(48))
    def grid(s, t):
        js.append('tl.fromTo("#%s .c",{opacity:0.08},{opacity:1,duration:0.12,stagger:0.035,ease:"none"},%.2f);' % (s, t + 0.3))
        js.append('(function(){var o={v:0},el=document.querySelector("#%s .num");tl.to(o,{v:7908,duration:1.9,ease:"power2.out",onUpdate:function(){el.textContent=Math.round(o.v).toLocaleString("ko-KR")}},%.2f);})();' % (s, t + 0.3))
    scene(6, "격자 채우기 훅", '<div class="hook">후기 <span class="num">0</span>건 다 읽었어요</div><div class="grid">%s</div>' % cells, grid)

    # 8 빛 번짐 플래시 전환
    def flash(s, t):
        js.append('tl.set("#%s .b",{opacity:0},%.2f);' % (s, t))
        js.append('tl.fromTo("#%s .leak",{opacity:0,x:-400},{opacity:0.95,x:0,duration:0.35,ease:"power2.in"},%.2f);' % (s, t + 1.2))
        js.append('tl.set("#%s .b",{opacity:1},%.2f);' % (s, t + 1.55))
        js.append('tl.to("#%s .leak",{opacity:0,x:400,duration:0.45,ease:"power2.out"},%.2f);' % (s, t + 1.55))
    scene(7, "빛 번짐 전환", '<img class="full" src="%s"><img class="full b" src="%s"><div class="leak"></div>' % (P(12), P(7)), flash)

    # 9 사진 위 후기 말풍선 쌓기(말풍선 쌓기 LP)
    bub = "".join('<div class="bub u%d">%s</div>' % (j, q) for j, q in enumerate(quotes))
    def chat(s, t):
        js.append('tl.fromTo("#%s .full",{scale:1.05},{scale:1,duration:%.2f,ease:"none"},%.2f);' % (s, SEG, t))
        for j in range(len(quotes)):
            js.append('tl.fromTo("#%s .u%d",{opacity:0,y:30},{opacity:1,y:0,duration:0.3,ease:"power3.out"},%.2f);' % (s, j, t + 0.4 + j * 0.6))
    scene(8, "사진 위 후기 쌓기", '<img class="full" src="%s"><div class="shade"></div>%s' % (P(5), bub), chat)

    dur = SEG * 9
    css = """
@font-face{font-family:P;src:url(assets/P.otf)}
html,body{margin:0;background:%(cr)s}
#root{position:relative;width:1080px;height:1920px;overflow:hidden;background:%(cr)s}
.sc{position:absolute;inset:0;overflow:hidden;background:%(cr)s}
.full{position:absolute;left:0;top:0;width:100%%;height:100%%;object-fit:cover}
.lab{position:absolute;left:50px;top:70px;z-index:9;font-family:P;font-size:52px;color:#16130f;background:#fff;padding:14px 30px 14px 16px;border-radius:999px;box-shadow:0 10px 26px rgba(0,0,0,.18)}
.lab b{display:inline-block;width:64px;height:64px;line-height:64px;text-align:center;border-radius:50%%;background:%(or)s;color:#fff;margin-right:16px}
.dim{filter:brightness(.55) blur(2px)}
.dp{position:absolute;width:520px;height:680px;object-fit:cover;border-radius:28px;box-shadow:0 30px 60px rgba(0,0,0,.4)}
.d0{left:40px;top:420px}.d1{left:300px;top:760px;z-index:2}.d2{left:520px;top:1080px;z-index:3}
.wall{position:absolute;left:-260px;top:-200px;width:1600px;display:grid;grid-template-columns:repeat(6,250px);gap:18px;transform:rotate(-12deg)}
.wall img{width:250px;height:250px;object-fit:cover;border-radius:22px}
.hero{position:absolute;left:150px;top:560px;width:780px;height:900px;z-index:3;border-radius:36px;overflow:hidden;box-shadow:0 40px 80px rgba(0,0,0,.45);border:10px solid #fff}
.hero img{width:100%%;height:100%%;object-fit:cover}
.hero span{position:absolute;left:24px;bottom:24px;font-family:P;font-size:40px;color:#fff;background:%(or)s;padding:10px 24px;border-radius:999px}
.desk{position:absolute;inset:0;background:#e9e0d3}
.pol{position:absolute;width:560px;height:660px;background:#fff;padding:26px 26px 110px;box-sizing:border-box;box-shadow:0 24px 50px rgba(60,40,20,.3)}
.pol img{width:100%%;height:100%%;object-fit:cover}
.p0{left:90px;top:420px}.p1{left:430px;top:560px}.p2{left:140px;top:900px}.p3{left:400px;top:1080px}
.hook{position:absolute;left:0;right:0;top:250px;text-align:center;font-family:P;font-size:84px;color:#16130f;letter-spacing:-.03em}
.hook .num{color:%(or)s}
.grid{position:absolute;left:60px;top:450px;width:960px;display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.grid img{width:100%%;height:150px;object-fit:cover;border-radius:12px}
.leak{position:absolute;inset:-200px;z-index:4;background:radial-gradient(circle at 50%% 50%%,#fff 0%%,#ffd9a8 25%%,rgba(232,84,42,.7) 50%%,rgba(232,84,42,0) 75%%)}
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 30%%,rgba(0,0,0,.55))}
.bub{position:relative;z-index:3;margin:0 70px 22px;font-family:P;font-size:46px;color:#16130f;background:#fff;padding:22px 32px;border-radius:30px 30px 30px 8px;box-shadow:0 12px 28px rgba(0,0,0,.25);width:fit-content;max-width:820px}
.u0{margin-top:1000px}.u1,.u3{margin-left:auto;margin-right:70px;border-radius:30px 30px 8px 30px;background:%(or)s;color:#fff}
""" % {"cr": CREAM, "or": ORANGE}
    doc = ('<!doctype html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080, height=1920">'
           '<script src="assets/gsap.min.js"></script><style>%s</style></head><body>'
           '<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="%.2f" data-fps="30">%s</div>'
           '<script>const tl=gsap.timeline({paused:true});%s window.__timelines["main"]=tl;</script></body></html>'
           % (css, dur, "\n".join(body), "\n".join(js)))
    (OUT / "index.html").write_text(doc, encoding="utf-8")
    print("만듦", OUT / "index.html", "%.1f초" % dur, "손님 사진", len(G), "벽", len(W))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
