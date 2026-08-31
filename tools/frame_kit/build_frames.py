"""기본 제공 '이미지 틀'을 굽는다 — HTML/CSS를 **진짜 크로미움으로 렌더**해서 PNG로.

★왜 PIL로 안 그리나(2026-08-31 사장님: "너가 코드로 다시그리면 느낌이 안나와"):
  PIL은 사각형과 글자만 놓는다. 질감을 만드는 것 — 여러 겹 그림자, 미세한 그라데이션,
  유리 흐림(backdrop-filter), 안쪽 하이라이트 — 은 전부 CSS가 이미 잘하는 일이다.
  브라우저로 구우면 그 결과가 **그대로 PNG**가 된다. 그게 '느낌'의 정체다.

★영상 자리는 **투명**으로 남긴다(omitBackground). 안 뚫으면 그 자리가 막혀 영상이 안 보인다.
  → 그래서 <body>에 배경을 깔지 않고, 그리는 요소만 둔다.

쓰는 법:  py tools/frame_kit/build_frames.py
결과   :  shopping_shorts/static/frames/<id>.png  +  frames.json(목록)
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

W, H = 1080, 1920
OUT = pathlib.Path(__file__).resolve().parents[2] / "shopping_shorts" / "static" / "frames"

BASE = """
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:%dpx;height:%dpx;background:transparent;overflow:hidden}
  body{font-family:'Pretendard','Malgun Gothic',sans-serif;-webkit-font-smoothing:antialiased}
  .bar{position:absolute;left:0;right:0;top:0;display:flex;align-items:center;
       justify-content:space-between;padding:0 46px}
  .ico{width:60px;height:60px;flex:0 0 auto}
  .ttl{position:absolute;left:0;right:0;padding:0 56px;text-align:center}
</style>
""" % (W, H)

# ── 아이콘은 SVG로 — 확대해도 안 뭉개진다(PIL 선 긋기와 결정적으로 다른 점) ──
HAMB = ('<svg class="ico" viewBox="0 0 60 60" fill="none" stroke="{c}" stroke-width="6" '
        'stroke-linecap="round"><path d="M10 18h40M10 30h40M10 42h40"/></svg>')
SEARCH = ('<svg class="ico" viewBox="0 0 60 60" fill="none" stroke="{c}" stroke-width="6" '
          'stroke-linecap="round"><circle cx="26" cy="26" r="15"/><path d="M37 37l13 13"/></svg>')
DOTS = ('<svg class="ico" viewBox="0 0 60 60" fill="{c}"><circle cx="30" cy="14" r="5"/>'
        '<circle cx="30" cy="30" r="5"/><circle cx="30" cy="46" r="5"/></svg>')


def frame(bar_h, bar_css, ico_color, sub_h, sub_css, left=HAMB, right=SEARCH, extra=""):
    """띠 + 그 아래 제목 블록. 글자는 안 넣는다 — 제작소가 얹는다(그게 자리 조절의 전제)."""
    return f"""{BASE}
    <div class="bar" style="height:{bar_h}px;{bar_css}">
      {left.format(c=ico_color)}{right.format(c=ico_color)}
    </div>
    <div class="ttl" style="top:{bar_h}px;height:{sub_h}px;{sub_css}"></div>
    {extra}"""


# ★틀과 **글자색은 한 세트**다(프리셋 20종에서 이미 배운 것).
#   색을 안 주면 흰 틀에 흰 채널명·검은 틀에 검은 제목이 나가 글자가 사라진다
#   (실측 2026-08-31: 크림판 채널명·먹지판 제목이 안 보였다).
#   on_bar=띠 위 글자 / title=제목 글자 / ol=제목 외곽선(없으면 빈값)
FRAMES = [
    # ── ① 유리 헤더: 반투명 + 뒤 흐림. PIL로는 아예 못 만드는 질감이다 ──
    ("glass_navy", "유리 · 네이비", frame(
        300,
        "background:linear-gradient(180deg,rgba(28,44,74,.94),rgba(18,30,54,.86));"
        "backdrop-filter:blur(18px);box-shadow:0 10px 30px rgba(0,0,0,.45),"
        "inset 0 -1px 0 rgba(255,255,255,.14)", "#EAF1FF", 210,
        "background:linear-gradient(180deg,#FFFFFF,#F2F5FA);"
        "box-shadow:0 6px 18px rgba(0,0,0,.18)"), {"on_bar":"#EAF1FF","title":"#12203A"}),
    # ── ② 종이 카드: 안쪽 하이라이트 + 부드러운 그림자 = '인쇄물' 느낌 ──
    ("paper_cream", "종이 · 크림", frame(
        268,
        "background:linear-gradient(180deg,#FDF6E7,#F5E9CF);"
        "box-shadow:inset 0 -2px 0 rgba(0,0,0,.07),0 8px 24px rgba(120,90,40,.22)",
        "#3A2E1B", 200,
        "background:#FFFDF7;box-shadow:0 5px 16px rgba(120,90,40,.16)"), {"on_bar":"#3A2E1B","title":"#2A2115"}),
    # ── ③ 새빨간 띠: 진한 채도 + 아래로 떨어지는 그림자(썰채널 정석) ──
    ("bold_red", "굵은 띠 · 레드", frame(
        286,
        "background:linear-gradient(180deg,#F0333B,#D6151E);"
        "box-shadow:0 12px 26px rgba(180,20,28,.42),inset 0 -2px 0 rgba(0,0,0,.18)",
        "#FFFFFF", 216, "background:#FFFFFF;box-shadow:0 6px 18px rgba(0,0,0,.2)"), {"on_bar":"#FFFFFF","title":"#1A1A1A"}),
    # ── ④ 먹지: 검정 + 얇은 금선. 고급스러운 대비 ──
    ("ink_gold", "먹지 · 골드라인", frame(
        276,
        "background:linear-gradient(180deg,#141414,#050505);"
        "box-shadow:0 2px 0 #C9A227,0 12px 28px rgba(0,0,0,.55)", "#E8D9A8", 204,
        "background:#0E0E0E;box-shadow:0 6px 18px rgba(0,0,0,.5);"
        "border-bottom:2px solid rgba(201,162,39,.5)", right=DOTS), {"on_bar":"#E8D9A8","title":"#F5EBC8"}),
    # ── ⑤ 하늘 그라데이션: 두 색이 섞이는 자리가 '손그림'과 갈린다 ──
    ("sky_fade", "그라데이션 · 하늘", frame(
        292,
        "background:linear-gradient(135deg,#4FA8E8,#2C6FD1 60%,#24519E);"
        "box-shadow:0 10px 26px rgba(30,80,160,.4)", "#FFFFFF", 208,
        "background:linear-gradient(180deg,#FFFFFF,#EDF4FF);"
        "box-shadow:0 6px 16px rgba(30,80,160,.18)"), {"on_bar":"#FFFFFF","title":"#123059"}),
    # ── ⑥ 민트 카드형: 띠가 화면에 안 붙고 '떠 있는' 모양(레이아웃 자체가 다르다) ──
    ("float_mint", "떠 있는 카드 · 민트", f"""{BASE}
      <div style="position:absolute;left:36px;right:36px;top:40px;height:238px;border-radius:28px;
           background:linear-gradient(180deg,#3FD6B0,#1FB894);
           box-shadow:0 16px 34px rgba(20,150,120,.42),inset 0 -2px 0 rgba(0,0,0,.12);
           display:flex;align-items:center;justify-content:space-between;padding:0 40px">
        {HAMB.format(c='#06302A')}{SEARCH.format(c='#06302A')}
      </div>
      <div style="position:absolute;left:36px;right:36px;top:300px;height:196px;border-radius:22px;
           background:#FFFFFF;box-shadow:0 12px 26px rgba(0,0,0,.2)"></div>""", {"on_bar":"#06302A","title":"#0A2A24"}),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for fid, name, html, colors in FRAMES:
            pg.set_content(html)
            pg.wait_for_timeout(120)          # 폰트·그림자 합성이 끝나길 기다린다
            path = OUT / f"{fid}.png"
            pg.screenshot(path=str(path), omit_background=True)   # ★영상 자리 = 투명
            made.append({"id": fid, "name": name, **colors})
            print(f"  구움: {fid}.png  {path.stat().st_size // 1024}KB")
        b.close()
    (OUT / "frames.json").write_text(json.dumps(made, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(f"완료: {len(made)}종 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
