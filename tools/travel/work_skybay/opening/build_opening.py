"""여행 숏폼 오프닝 '그림이 여행이 된다'(세로 1080×1920, 약 9초) — index.html + 펜 소리.

    py tools/travel/work_skybay/opening/prep.py           (재료 손질·획 따기, 먼저)
    py tools/travel/work_skybay/opening/build_opening.py
    npx -y hyperframes@0.8.105 render ~/숏템자료/모션그래픽엔진/work/2026-10-22_숙소_오프닝 -o …/out.mp4

원본(jasonzhu 2103135536634630632, 15 agents 2D 애니) 펜 그리기 실측 10가지를 옮겼다(사장님 10-22 "원본영상 다시보고 디테일하게"):
 ①회색 밑그림(머리 타원·중심선)이 먼저 ②펜 = 진짜 연필 모양(검정 몸통·나무 깎은 끝·주황 꼬리), 끝이 그리는 점에 붙음
 ③방금 그은 선 끝 26px 가 주황으로 빛나다 검게 식음 ④위→아래 부위 순서 ⑤채색은 펜 주변에 물감이 번지는 덩어리로
 ⑥끝나면 펜이 비켜서 떠 있음 ⑦배경 원근선은 펜이 한 번에 쏘듯 ⑧정면→옆→뒤로 돌아섬 ⑨잉크 번짐 전환 ⑩크림 종이·비네트·결
움직임 원칙(emil): 등장 ease-out, 바운스 없음, 0(scale)에서 시작 안 함.
"""
import json
import math
import shutil
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TRACK = HERE.parents[3]
D = Path.home() / "숏템자료/모션그래픽엔진/work/2026-10-22_숙소_오프닝"
SFX = TRACK / "shopping_shorts/assets/sfx_packs/팩21_사장님"
DUR = 9.0
SR = 48000

# ── 시간표(초) — 한 곳에서만 정한다. 화면(JS)과 소리(펜 긁는 소리)가 같은 표를 읽는다 ──
T = {
    "guide": (0.15, 0.55),          # ① 밑그림
    "fig": (0.45, 3.25),            # ④ 인물 선
    "figClean": (3.2, 3.45),        # 획 → 깨끗한 선화로 갈아끼움(뼈대 선의 거친 맛 정리)
    "wash": (3.35, 4.3),            # ⑤ 물감 번짐
    "shrink": (4.35, 5.25),         # 인물이 길 위 크기로
    "shots": (4.45, 5.6),           # ⑦ 원근선 쏘기
    "detail": (4.9, 5.75),          # 나머지 배경 잔선(펜 없이 여러 갈래)
    "bgClean": (5.7, 5.9),
    "write": (5.55, 6.25),          # 손글씨 '이번 주말, 강릉.'
    "turnSide": 5.95, "turnBack": 6.25,   # ⑧
    "bgWash": (6.2, 6.95),
    "walk": (6.4, 7.6),
    "dolly": (6.3, 8.4),
    "tap": 7.25,                    # 펜이 옥상 수영장을 톡
    "bloom": (7.3, 8.35),           # ⑨
    "fade": (7.5, 7.95),
    "card": (8.35, 8.95),           # 꽉 찬 사진 → 1편 가운데 카드 자리(90,500,900×940)로 내려앉음
}


def stroke_times(items, t0, t1, minimum=0.004, gap=0.0):
    """획 길이에 비례해 시간을 나눈다(긴 획 = 오래). 반환 [(시작, 길이)]."""
    tot = sum(it["L"] for it in items)
    avail = (t1 - t0) - gap * len(items) - minimum * len(items)
    out, t = [], t0
    for it in items:
        d = minimum + max(0.0, avail) * it["L"] / tot
        out.append((round(t, 4), round(d, 4)))
        t += d + gap
    return out


def main():
    st = json.loads((D / "strokes.js").read_text(encoding="utf-8").split("=", 1)[1].rstrip(";"))
    fig = st["fig"]
    fig_t = stroke_times(fig, *T["fig"])
    shots = st["shots"]
    sh_t, t = [], T["shots"][0]
    for k in range(len(shots)):            # 앞 6개는 또박또박(0.12초), 뒤는 빠르게 — 원본도 처음 몇 줄은 천천히 보였다
        d = 0.12 if k < 6 else (T["shots"][1] - T["shots"][0] - 0.72) / max(1, len(shots) - 6)
        sh_t.append((round(t, 4), round(d, 4)))
        t += d
    bg = [s for s in st["bg"]]
    lanes = 6                               # 잔선은 6갈래로 동시에(펜 없이) — 800획을 0.85초에
    det_t = []
    per = [bg[k::lanes] for k in range(lanes)]
    lane_t = [stroke_times(p, *T["detail"], minimum=0.0) for p in per]
    for k in range(len(bg)):
        det_t.append(lane_t[k % lanes][k // lanes])

    # 재료
    (D / "assets").mkdir(exist_ok=True)
    shutil.copy(Path.home() / "숏템자료/모션그래픽엔진/work/2026-10-20_라면레시피/ramen/brand/gsap.min.js", D / "assets/gsap.min.js")
    shutil.copy(TRACK / "shopping_shorts/static/fonts/NanumPenScript.ttf", D / "assets/pen.ttf")
    # 실제 사진 = 공식 11번 조감도(호텔+해변) — 방금 그린 호텔이 진짜가 되는 순간, 그리고 1편 첫 카드와 같은 사진이라 이어진다
    shutil.copy(HERE.parent / "photos/10.jpg", D / "img/real.jpg")
    for f in ("whoosh.wav", "pop.wav"):
        shutil.copy(SFX / f, D / "assets" / f)
    pen_sound(fig_t, sh_t, D / "assets/pen.wav")

    data = {"T": T, "fig": [[s["d"], s["L"], a, b] for s, (a, b) in zip(fig, fig_t)],
            "shots": [[l, a, b] for l, (a, b) in zip(shots, sh_t)],
            "bg": [[s["d"], s["L"], a, b] for s, (a, b) in zip(bg, det_t)],
            "wash": st["wash"]}
    html = PAGE.replace("__DATA__", json.dumps(data)).replace("__DUR__", "%.2f" % DUR)
    (D / "index.html").write_text(html, encoding="utf-8")
    print("만듦", D / "index.html", "인물 획 %d · 원근선 %d · 잔선 %d" % (len(fig), len(shots), len(bg)))


def pen_sound(fig_t, sh_t, out):
    """펜 소리를 획 시간표로 만든다 — 획마다 '사각' 한 번(대역 잡음 + 짧은 엔벌로프), 원근선은 길게 '쓱'.
    효과음 폴더에 펜 소리가 없어(실측 10-22) 합성한다. 크기는 -24 dBFS 안팎(음악·목소리 아래)."""
    n = int(DUR * SR)
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n).astype(np.float32)

    def band(x, lo, hi):
        k = np.arange(-256, 257)
        h = (np.sinc(2 * hi / SR * k) * 2 * hi / SR - np.sinc(2 * lo / SR * k) * 2 * lo / SR) * np.hanning(513)
        return np.convolve(x, h, mode="same").astype(np.float32)
    scratch = band(noise, 1800, 6500)
    swish = band(noise, 600, 3000)
    env = np.zeros(n, np.float32)
    for a, d in fig_t:                         # 사각사각
        i0, i1 = int(a * SR), int((a + max(d, 0.03)) * SR)
        m = i1 - i0
        if m <= 0:
            continue
        e = np.minimum(1, np.arange(m) / (0.004 * SR)) * np.exp(-np.arange(m) / (0.05 * SR)) * 0.8
        env[i0:i1] = np.maximum(env[i0:i1], e[: len(env[i0:i1])])
    env2 = np.zeros(n, np.float32)
    for a, d in sh_t:                          # 쓱
        i0, i1 = int(a * SR), int((a + d + 0.05) * SR)
        m = i1 - i0
        e = np.sin(np.linspace(0, np.pi, m)) ** 0.7
        env2[i0:i1] = np.maximum(env2[i0:i1], e[: len(env2[i0:i1])])
    w0, w1 = int(T["write"][0] * SR), int(T["write"][1] * SR)    # 손글씨 = 짧은 사각 여러 번
    for k in range(10):
        a = w0 + int((w1 - w0) * k / 10)
        m = int(0.05 * SR)
        env[a:a + m] = np.maximum(env[a:a + m], np.exp(-np.arange(m) / (0.02 * SR)) * 0.7)
    y = scratch * env * 0.22 + swish * env2 * 0.16
    y = y / (np.max(np.abs(y)) + 1e-9) * 10 ** (-9 / 20)
    pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes(pcm.tobytes())


PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080, height=1920">
<script src="assets/gsap.min.js"></script>
<style>
@font-face{font-family:"PenK";src:url("assets/pen.ttf")}
#vig,.grain{z-index:2}#pay{z-index:3}
html,body{margin:0;background:#efebe3}
#stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:#efebe3}
#art{position:absolute;left:-8.57px;top:0;width:768px;height:1344px;transform-origin:0 0;transform:scale(1.428571)}
.lay{position:absolute;left:0;top:0;width:768px;height:1344px}
.img{position:absolute;left:0;top:0;width:768px;height:1344px;object-fit:cover}
.mul{mix-blend-mode:multiply}
#vig{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 75% 60% at 50% 45%,rgba(255,252,245,.0) 40%,rgba(120,100,70,.22) 100%)}
.grain{position:absolute;inset:0;opacity:.13;mix-blend-mode:multiply;pointer-events:none;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'><feTurbulence baseFrequency='.85' numOctaves='2' seed='3'/><feColorMatrix values='0 0 0 0 .5 0 0 0 0 .45 0 0 0 0 .4 0 0 0 .9 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")}
#hw{position:absolute;left:0;top:140px;width:768px;text-align:center;font-family:"PenK";font-size:74px;color:#2b2724;letter-spacing:1px}
</style></head><body>
<div id="stage" data-composition-id="main" data-start="0" data-duration="__DUR__" data-width="1080" data-height="1920" data-fps="30">
<div id="art">
 <div id="world" class="lay">
  <svg id="bgS" class="lay" viewBox="0 0 768 1344"><g id="bgShots" stroke="#2b2724" stroke-width="1.5" fill="none" stroke-linecap="round"></g><g id="bgDet" stroke="#2b2724" stroke-width="1.3" fill="none" stroke-linecap="round" stroke-linejoin="round"></g><g id="bgGlow" stroke="#ff8a2a" stroke-width="2.6" fill="none" stroke-linecap="round" style="filter:drop-shadow(0 0 3px rgba(255,130,40,.9))"></g></svg>
  <img id="bgLine" class="img mul" src="img/bg_line.png" style="opacity:0">
  <svg id="bgWash" class="lay" viewBox="0 0 768 1344" style="opacity:0"><defs>
   <filter id="ragB" x="-20%" y="-20%" width="140%" height="140%"><feTurbulence type="fractalNoise" baseFrequency=".022" numOctaves="3" seed="11"/><feDisplacementMap in="SourceGraphic" scale="70"/><feGaussianBlur stdDeviation="3"/></filter>
   <mask id="mBg"><g filter="url(#ragB)"><circle id="bgBlob" cx="384" cy="1270" r="0" fill="#fff"/></g></mask></defs>
   <image href="img/bg_color.png" width="768" height="1344" preserveAspectRatio="xMidYMid slice" mask="url(#mBg)"/></svg>
  <div id="hwWrap" class="lay" style="clip-path:inset(0 100% 0 0)"><div id="hw">이번 주말, 강릉.</div></div>
 </div>
 <div id="fig" class="lay">
  <svg id="guides" class="lay" viewBox="0 0 768 1344" fill="none" stroke="#b8b0a3" stroke-width="1.2" stroke-linecap="round"></svg>
  <svg id="figS" class="lay" viewBox="0 0 768 1344"><g id="figP" stroke="#26221f" stroke-width="1.7" fill="none" stroke-linecap="round" stroke-linejoin="round"></g><g id="figGlow" stroke="#ff8a2a" stroke-width="3" fill="none" stroke-linecap="round" style="filter:drop-shadow(0 0 3px rgba(255,130,40,.95))"></g></svg>
  <img id="figLine" class="img mul" src="img/couple_line_reg.png" style="opacity:0">
  <svg id="figWash" class="lay" viewBox="0 0 768 1344"><defs>
   <filter id="ragF" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency=".04" numOctaves="3" seed="5"/><feDisplacementMap in="SourceGraphic" scale="48"/><feGaussianBlur stdDeviation="1.6"/></filter>
   <mask id="mFig"><g id="blobs" filter="url(#ragF)"></g><rect id="fullF" width="768" height="1344" fill="#fff" opacity="0"/></mask></defs>
   <image href="img/couple_color_cut.png" width="768" height="1344" mask="url(#mFig)"/></svg>
  <img id="side" class="img" src="img/couple_side_cut.png" style="opacity:0">
  <img id="backA" class="img" src="img/couple_backA_cut.png" style="opacity:0">
  <img id="backB" class="img" src="img/couple_backB_cut.png" style="opacity:0">
 </div>
 <svg id="portal" class="lay" viewBox="0 0 768 1344"><defs>
  <filter id="ink" x="-50%" y="-50%" width="200%" height="200%"><feTurbulence type="fractalNoise" baseFrequency=".018" numOctaves="4" seed="21"/><feDisplacementMap in="SourceGraphic" scale="110"/><feGaussianBlur stdDeviation="2.5"/></filter>
  <filter id="smoke" x="-50%" y="-50%" width="200%" height="200%"><feTurbulence type="fractalNoise" baseFrequency=".012" numOctaves="4" seed="8"/><feDisplacementMap in="SourceGraphic" scale="140"/><feGaussianBlur stdDeviation="9"/></filter>
  <filter id="smoke2" x="-50%" y="-50%" width="200%" height="200%"><feTurbulence type="fractalNoise" baseFrequency=".02" numOctaves="3" seed="33"/><feDisplacementMap in="SourceGraphic" scale="90"/><feGaussianBlur stdDeviation="6"/></filter>
  <mask id="mP"><g filter="url(#ink)"><circle id="pBlob" cx="384" cy="500" r="0" fill="#fff"/></g></mask></defs>
  <g id="smokeG"><circle id="s1" r="0" fill="#24313b" opacity=".42" filter="url(#smoke)"/><circle id="s2" r="0" fill="#31404a" opacity=".35" filter="url(#smoke2)"/><circle id="s3" r="0" fill="#1b252d" opacity=".3" filter="url(#smoke)"/></g>
  <image id="real" href="img/real.jpg" width="768" height="1344" preserveAspectRatio="xMidYMid slice" mask="url(#mP)"/></svg>
 <svg id="penL" class="lay" viewBox="0 0 768 1344" style="overflow:visible"><defs>
  <radialGradient id="tipG"><stop offset="0" stop-color="#fff2c0" stop-opacity="1"/><stop offset=".35" stop-color="#ff9a3c" stop-opacity=".85"/><stop offset="1" stop-color="#ff6a1a" stop-opacity="0"/></radialGradient>
  <linearGradient id="body" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a3a3e"/><stop offset=".45" stop-color="#151517"/><stop offset="1" stop-color="#0b0b0c"/></linearGradient>
  <linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f0d2a4"/><stop offset="1" stop-color="#c99a62"/></linearGradient>
  <filter id="psh"><feGaussianBlur stdDeviation="4"/></filter></defs>
  <g id="pen" opacity="0">
   <g transform="translate(10,12) rotate(-58)" opacity=".18" filter="url(#psh)"><rect x="34" y="-8" width="190" height="16" rx="3" fill="#000"/></g>
   <circle id="tip" r="16" fill="url(#tipG)"/>
   <g transform="rotate(-58)">
    <path d="M0 0 L34 -8 L34 8 Z" fill="url(#wood)"/><path d="M0 0 L9 -2.2 L9 2.2 Z" fill="#2a2a2a"/>
    <rect x="34" y="-8" width="190" height="16" fill="url(#body)"/><rect x="34" y="-3" width="190" height="2.2" fill="#55555c" opacity=".7"/>
    <rect x="224" y="-8" width="12" height="16" fill="#c9c9cf"/><rect x="236" y="-8" width="16" height="16" rx="4" fill="#ff7a2a"/>
   </g>
  </g></svg>
</div>
<div id="pay" style="position:absolute;left:-8.57px;top:0;width:1097px;height:1920px;overflow:hidden;opacity:0;box-shadow:0 28px 60px rgba(40,25,10,.28)"><img src="img/real.jpg" style="width:100%;height:100%;object-fit:cover;display:block"></div>
<div id="vig"></div><div class="grain"></div>
<audio src="assets/pen.wav" data-start="0" data-duration="__DUR__" data-track-index="10" data-volume="1"></audio>
<audio src="assets/pop.wav" data-start="7.18" data-duration="0.4" data-track-index="11" data-volume="0.35"></audio>
<audio src="assets/whoosh.wav" data-start="7.28" data-duration="0.8" data-track-index="12" data-volume="0.45"></audio>
</div>
<script>
(function(){
const DATA=__DATA__, T=DATA.T, NS="http://www.w3.org/2000/svg";
const $=id=>document.getElementById(id), cl=(x,a=0,b=1)=>Math.max(a,Math.min(b,x)), seg=(t,a,b)=>cl((t-a)/(b-a));
const eo=p=>1-Math.pow(1-p,3), eio=p=>p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2, sio=p=>-(Math.cos(Math.PI*p)-1)/2;
function mk(parent,d,L){const p=document.createElementNS(NS,"path");p.setAttribute("d",d);p.setAttribute("stroke-dasharray",L+" "+(L+10));p.setAttribute("stroke-dashoffset",L);parent.appendChild(p);return p}
// 인물 획·원근선·잔선
const F=DATA.fig.map(([d,L,a,b])=>({el:mk($("figP"),d,L),L,a,b}));
const S=DATA.shots.map(([l,a,b])=>{const d=`M${l[0]} ${l[1]} L${l[2]} ${l[3]}`,L=Math.hypot(l[2]-l[0],l[3]-l[1]);return {el:mk($("bgShots"),d,L),L,a,b,l}});
const B=DATA.bg.map(([d,L,a,b])=>({el:mk($("bgDet"),d,L),L,a,b}));
// 주황 빛(방금 그은 끝) — 칸 4개를 돌려 쓴다
const GF=[0,1,2,3].map(()=>{const p=document.createElementNS(NS,"path");$("figGlow").appendChild(p);return p});
const GB=[0,1,2].map(()=>{const p=document.createElementNS(NS,"path");$("bgGlow").appendChild(p);return p});
// 밑그림 ①
const G=[["ellipse",{cx:300,cy:405,rx:50,ry:60}],["ellipse",{cx:466,cy:338,rx:47,ry:57}],["line",{x1:300,y1:345,x2:300,y2:1250}],["line",{x1:466,y1:281,x2:466,y2:1250}],["line",{x1:150,y1:1252,x2:640,y2:1252}]]
 .map(([tag,at])=>{const e=document.createElementNS(NS,tag);for(const k in at)e.setAttribute(k,at[k]);$("guides").appendChild(e);const L=e.getTotalLength?e.getTotalLength():600;e.setAttribute("stroke-dasharray",L+" "+(L+5));e.setAttribute("stroke-dashoffset",L);return {e,L}});
// 물감 덩어리 ⑤
const W=DATA.wash.map(([x,y],k)=>{const c=document.createElementNS(NS,"circle");c.setAttribute("cx",x);c.setAttribute("cy",y);c.setAttribute("r",0);c.setAttribute("fill","#fff");$("blobs").appendChild(c);return {c,x,y,a:T.wash[0]+k*0.065}});

function drawSet(arr,t){let cur=-1;for(let k=0;k<arr.length;k++){const s=arr[k],p=cl((t-s.a)/Math.max(1e-4,s.b));s.el.setAttribute("stroke-dashoffset",s.L*(1-p));if(t>=s.a&&t<s.a+s.b)cur=k;}return cur}
function glow(pool,arr,t,cur){ // 그리는 중 = 끝 26px 주황, 끝난 뒤 0.35초에 걸쳐 식음
 for(let s=0;s<pool.length;s++){let j=-1;for(let k=s;k<arr.length;k+=pool.length){if(arr[k].a<=t)j=k;else break}
  const g=pool[s];if(j<0){g.setAttribute("opacity",0);continue}const st=arr[j],p=cl((t-st.a)/Math.max(1e-4,st.b)),dr=st.L*p,gl=Math.min(26,dr);
  g.setAttribute("d",st.el.getAttribute("d"));g.setAttribute("stroke-dasharray",`0 ${Math.max(0,dr-gl)} ${gl} ${st.L+50}`);
  const age=t-(st.a+st.b);g.setAttribute("opacity",p<1?1:cl(1-age/0.35))}}
function ptOn(s,t){const p=cl((t-s.a)/Math.max(1e-4,s.b));return s.el.getPointAtLength(s.L*p)}
// 무리(인물)·세상(배경) 카메라 — 숫자로 정하고 펜 위치도 같은 숫자로 바꾼다
function figXf(t){let sc=1,tx=0,ty=0;const k=eio(seg(t,...T.shrink));sc=1-0.44*k;ty=35*k;tx=-16*k;
 const w=sio(seg(t,...T.walk));sc*=1-0.29*w;ty-=170*w;return {sc,tx,ty,ox:400,oy:1255}}
function worldXf(t){const k=sio(seg(t,...T.dolly));return {sc:1+0.16*k,ox:384,oy:520}}
function ap(x,y,f){return [f.ox+(x-f.ox)*f.sc+(f.tx||0),f.oy+(y-f.oy)*f.sc+(f.ty||0)]}
let PX=600,PY=300;
function render(t){
 // ① 밑그림
 for(const g of G){g.e.setAttribute("stroke-dashoffset",g.L*(1-eo(seg(t,...T.guide))))}
 $("guides").style.opacity=1-seg(t,2.6,3.3);
 // ④ 인물 선 + ③ 주황 빛
 const cf=drawSet(F,t);glow(GF,F,t,cf);
 $("figS").style.opacity=1-seg(t,...T.figClean);$("figLine").style.opacity=seg(t,...T.figClean)*(1-seg(t,4.2,4.4));
 // ⑤ 물감
 for(const w of W){w.c.setAttribute("r",150*eo(seg(t,w.a,w.a+0.34)))}
 $("fullF").setAttribute("opacity",seg(t,T.wash[1]-0.3,T.wash[1]));
 const front=t<T.turnSide+0.06?1:cl(1-seg(t,T.turnSide,T.turnSide+0.12));$("figWash").style.opacity=front;
 $("side").style.opacity=t<T.turnSide?0:(t<T.turnBack?seg(t,T.turnSide,T.turnSide+0.12):1-seg(t,T.turnBack,T.turnBack+0.12));
 const walking=t>=T.walk[0], step=Math.floor((t-T.walk[0])/0.18)%2;
 const back=seg(t,T.turnBack,T.turnBack+0.12);$("backA").style.opacity=walking?(step?0:back):back;$("backB").style.opacity=walking&&step?back:0;
 const ff=figXf(t), bob=walking?Math.abs(Math.sin((t-T.walk[0])/0.18*Math.PI))*-3:0;
 $("fig").style.transform=`translate(${ff.tx}px,${ff.ty+bob}px) scale(${ff.sc})`;$("fig").style.transformOrigin=`${ff.ox}px ${ff.oy}px`;
 $("fig").style.opacity=1-seg(t,...T.fade);
 // ⑦ 배경
 const cs=drawSet(S,t);drawSet(B,t);glow(GB,S,t,cs);
 $("bgS").style.opacity=1-seg(t,...T.bgClean);$("bgLine").style.opacity=seg(t,...T.bgClean);
 $("bgWash").style.opacity=t>=T.bgWash[0]?1:0;$("bgBlob").setAttribute("r",1500*Math.pow(seg(t,...T.bgWash),1.2));
 const wf=worldXf(t);$("world").style.transformOrigin=`${wf.ox}px ${wf.oy}px`;$("world").style.transform=`scale(${wf.sc})`;
 // 손글씨(왼→오 드러남, 펜이 따라감)
 const hw=seg(t,...T.write);$("hwWrap").style.clipPath=`inset(0 ${100-12-76*hw}% 0 0)`;$("hwWrap").style.opacity=t<T.write[0]?0:1-seg(t,7.2,7.5);
 // ⑨ 잉크 번짐 → 실제 사진
 const pb=seg(t,...T.bloom),[rx,ry]=ap(384,488,wf);
 for(const id of ["pBlob","s1","s2","s3"]){$(id).setAttribute("cx",rx);$(id).setAttribute("cy",ry)}
 // 연기 3겹이 사진보다 조금씩 앞서 퍼진다(속도가 달라 덩어리가 겹쳐 보임) → 사진이 따라와 덮는다
 const R=q=>1650*Math.pow(cl(q),1.6);$("pBlob").setAttribute("r",R(pb));
 $("s1").setAttribute("r",pb>0?R(pb*1.18)+30:0);$("s2").setAttribute("r",pb>0?R(pb*1.32)+10:0);$("s3").setAttribute("r",pb>0?R(pb*1.08)+50:0);
 $("smokeG").style.opacity=1-seg(t,T.bloom[1]-0.35,T.bloom[1]);
 $("real").setAttribute("transform",`translate(${rx*(1-pb)*0.08} ${ry*(1-pb)*0.08}) scale(${1-0.08*(1-pb)})`);
 // 사진 → 1편 카드 자리. 넘겨받는 순간 같은 크기·같은 자르기(가로 1097 = #art 와 같은 덮기)라 튀지 않는다
 const cd=eo(seg(t,...T.card)),L=(a,b)=>a+(b-a)*cd;$("pay").style.opacity=t>=T.card[0]?1:0;$("art").style.opacity=t>=T.card[0]+0.02?0:1;
 Object.assign($("pay").style,{left:L(-8.57,90)+"px",top:L(0,500)+"px",width:L(1097,900)+"px",height:L(1920,940)+"px",borderRadius:L(0,36)+"px"});
 // ② 펜 위치 — 그리는 점 / 물감 자리 / 쏘는 선 / 글씨 끝 / 옥상 수영장
 let on=0,x=PX,y=PY;
 if(t>=T.guide[0]&&t<T.fig[0]){on=1;const g=G[Math.min(4,Math.floor(seg(t,...T.guide)*5))].e,p=g.getPointAtLength(g.getTotalLength()*((seg(t,...T.guide)*5)%1));[x,y]=[p.x,p.y]}
 else if(t>=T.fig[0]&&t<T.fig[1]){on=1;const k=cf>=0?cf:F.findIndex(s=>s.a>t)-1;const s=F[Math.max(0,k)];const p=ptOn(s,t);[x,y]=ap(p.x,p.y,ff)}
 else if(t>=T.wash[0]&&t<T.wash[1]-0.15){on=1;const k=Math.min(W.length-1,Math.floor((t-T.wash[0])/0.065)),w=W[k],a=(t-w.a)*40;[x,y]=ap(w.x+18*Math.cos(a),w.y+12*Math.sin(a),ff)}
 else if(t>=T.wash[1]-0.15&&t<T.shots[0]){on=1;const k=eo(seg(t,T.wash[1]-0.15,T.shots[0]));x=W[W.length-1].x+(640-W[W.length-1].x)*k;y=W[W.length-1].y+(260-W[W.length-1].y)*k}
 else if(t>=T.shots[0]&&t<T.shots[1]){on=1;const k=cs>=0?cs:Math.max(0,S.findIndex(s=>s.a>t)-1);const p=ptOn(S[k],t);[x,y]=ap(p.x,p.y,wf)}
 else if(t>=T.shots[1]&&t<T.write[1]){on=1;const k=seg(t,...T.write);[x,y]=ap(384-292+584*k*0.9+(k>0?0:0),232+10*Math.sin(t*38),wf);if(t<T.write[0]){const q=eo(seg(t,T.shots[1],T.write[0]));x=PX+(x-PX)*q;y=PY+(y-PY)*q}}
 else if(t>=T.write[1]&&t<T.tap+0.05){on=1;const k=eio(seg(t,T.write[1],T.tap));const [ex,ey]=ap(384,488,wf);x=640+(ex-640)*k;y=250+(ey-250)*k-40*Math.sin(Math.PI*k)}
 else if(t>=T.tap+0.05&&t<T.bloom[0]+0.35){on=1-seg(t,T.tap+0.05,T.bloom[0]+0.35);const [ex,ey]=ap(384,488,wf);x=ex+120*seg(t,T.tap,T.bloom[0]+0.35);y=ey-160*seg(t,T.tap,T.bloom[0]+0.35)}
 if(t<T.guide[0])on=seg(t,0,T.guide[0]),x=520,y=330;
 if(on>0){PX=x;PY=y}
 const drawing=(t>=T.fig[0]&&t<T.fig[1])||(t>=T.shots[0]&&t<T.shots[1])||(t>=T.write[0]&&t<T.write[1]);
 $("pen").setAttribute("opacity",on);$("pen").setAttribute("transform",`translate(${x} ${y})`);
 $("tip").setAttribute("r",drawing?14+3*Math.sin(t*41):(Math.abs(t-T.tap)<0.08?30:9));$("tip").setAttribute("opacity",drawing||Math.abs(t-T.tap)<0.1?1:.55);
}
window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});const P={t:0};
tl.to(P,{t:__DUR__,duration:__DUR__,ease:"none",onUpdate:()=>render(P.t)});render(0);window.__timelines["main"]=tl;
})();
</script></body></html>
"""

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
