// 구매링크 롱폼(가로 16:9) 안내 블록(관제 133, 2026-10-06 사장님).
//   구성(사장님 확정): 가운데 쇼츠 위를 **가로지르는 문구 띠** + 양옆에서 **크게 움직이는 화살표**. 문구는 5가지 중에서 고른다.
//   블록 = HTML·CSS 로 짠 움직이는 덩어리 하나. 덩어리째 끌어 놓는다.
//   ★크기는 전부 em — 블록 폭의 1/20 이 1em 이라 폭만 바꾸면 통째로 커지고 작아진다.
//   ★움직임은 전부 1.2초(또는 그 배수 2.4초) 한 바퀴(CSS animation) — 렌더는 시간을 못 박아 72프레임(30fps)을 찍고 이어 붙인다. 길이를 바꾸면 LOOP_MS 도 같이.
(()=>{
const LOOP_MS=2400;
const CSS=`
.lfb{font-family:"GmarketSans","Pretendard","Malgun Gothic",sans-serif;font-weight:700;color:#fff;line-height:1.2;letter-spacing:-.03em;word-break:keep-all}
.lfb *{box-sizing:border-box}
.lfb [data-a]{animation-iteration-count:infinite;animation-timing-function:ease-in-out}
@keyframes lfb-beat{0%,100%{transform:scale(1)}50%{transform:scale(1.045)}}
@keyframes lfb-shine{0%{transform:translateX(-160%) skewX(-20deg)}60%,100%{transform:translateX(1100%) skewX(-20deg)}}
@keyframes lfb-pop{0%,100%{transform:rotate(-2deg) scale(1)}50%{transform:rotate(1.5deg) scale(1.09)}}
@keyframes lfb-dive{0%,100%{transform:translateY(-9%) scaleY(1)}45%{transform:translateY(11%) scaleY(1.04)}55%{transform:translateY(11%) scaleY(.94)}}
@keyframes lfb-trail{0%,100%{opacity:0;transform:translateY(-22%)}35%{opacity:.5}60%{opacity:0;transform:translateY(4%)}}
@keyframes lfb-halo{0%{transform:scale(.5);opacity:.7}100%{transform:scale(1.35);opacity:0}}

/* 문구 띠 — 화면을 가로지르는 살짝 기운 띠. 띠 안에서 글자가 두근거리고 빛이 한 번씩 지나간다 */
.lfb-band{position:relative;width:104%;margin-left:-2%;padding:.3em 0 .26em;text-align:center;transform:rotate(-1.6deg);overflow:hidden;box-shadow:0 .16em .7em rgba(0,0,0,.45),inset 0 .03em 0 rgba(255,255,255,.35),inset 0 -.04em 0 rgba(0,0,0,.25)}
.lfb-band .tx{display:inline-flex;align-items:center;gap:.28em;white-space:nowrap;animation-name:lfb-beat;animation-duration:1200ms}
.lfb-band .hot{display:inline-block;padding:.1em .26em .04em;border-radius:.12em;animation-name:lfb-pop;animation-duration:1200ms;box-shadow:0 .06em .2em rgba(0,0,0,.3)}
.lfb-band .sh{position:absolute;top:-20%;bottom:-20%;left:0;width:9%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.55),transparent);animation-name:lfb-shine;animation-duration:2400ms;animation-timing-function:ease-in}
.lfb-band.red{background:linear-gradient(180deg,#ff4032,#d9001f)}.lfb-band.red .hot{background:#ffe600;color:#111}
.lfb-band.yellow{background:linear-gradient(180deg,#fff04a,#ffd000);color:#111}.lfb-band.yellow .hot{background:#111;color:#ffe600}
.lfb-band.black{background:linear-gradient(180deg,#1c1c1c,#050505)}.lfb-band.black .hot{background:#ff2d2d;color:#fff}
.lfb-band.blue{background:linear-gradient(180deg,#3d93ff,#0f55f0)}.lfb-band.blue .hot{background:#fff;color:#0f55f0}
.lfb-band.purple{background:linear-gradient(180deg,#a743ff,#5a1fe0)}.lfb-band.purple .hot{background:#ffe600;color:#111}

/* 큰 화살표 — 아래로 내리꽂고 살짝 눌렸다 올라온다. 뒤에 잔상 둘, 끝에서 고리가 퍼진다 */
.lfb-arrow{position:relative;width:100%;aspect-ratio:1/1.3}
.lfb-arrow svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible;transform-origin:50% 100%}
.lfb-arrow .main{animation-name:lfb-dive;animation-duration:1200ms;filter:drop-shadow(0 .5em .7em rgba(0,0,0,.45))}
.lfb-arrow .ghost{animation-name:lfb-trail;animation-duration:1200ms}.lfb-arrow .ghost.g2{animation-delay:-150ms}
.lfb-arrow .halo{position:absolute;left:10%;right:10%;bottom:-6%;aspect-ratio:1/.32;border-radius:50%;border:.22em solid rgba(255,255,255,.9);animation-name:lfb-halo;animation-duration:1200ms;animation-timing-function:ease-out}
`;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const TONES={red:['#ff5a4d','#d9001f'],yellow:['#fff04a','#ffb800'],black:['#ff5a4d','#d9001f'],blue:['#59a6ff','#0f55f0'],purple:['#c06bff','#5a1fe0']};
// 굵은 아래 화살표(100x130 좌표): 몸통 + 넓은 촉. 흰 테두리로 어떤 배경에서도 또렷하다.
const PATH='M34 6h32a6 6 0 0 1 6 6v52h17a5 5 0 0 1 3.8 8.3L54 124a5.2 5.2 0 0 1-8 0L7.2 72.3A5 5 0 0 1 11 64h17V12a6 6 0 0 1 6-6z';
let uid=0;
const arrowSvg=(tone,cls)=>{const [a,b]=TONES[tone]||TONES.red,id='lfbg'+(++uid);
  return `<svg class="${cls}" viewBox="0 0 100 130" data-a><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs><path d="${PATH}" fill="url(#${id})" stroke="#fff" stroke-width="5" stroke-linejoin="round"/></svg>`};
const BLOCKS={
  // m.pre · m.hot(강조 칸) · m.post = 한 줄 문구. 글자 수가 늘면 크기를 줄여 한 줄에 넣는다(띠 폭 = 20em).
  band:{label:'문구 띠',html:m=>{const text=(m.pre||'')+(m.hot||'')+(m.post||''),n=[...text].reduce((k,c)=>k+(/[\u0000-\u007f]/.test(c)?.58:1),0)+1.6;
    return `<div class="lfb lfb-band ${esc(m.tone||'red')}"><i class="sh" data-a></i><span class="tx" data-a style="font-size:${Math.min(1.5,17.6/n).toFixed(3)}em">${m.pre?`<span>${esc(m.pre)}</span>`:''}<span class="hot" data-a>${esc(m.hot)}</span>${m.post?`<span>${esc(m.post)}</span>`:''}</span></div>`}},
  arrow:{label:'큰 화살표',html:m=>`<div class="lfb lfb-arrow"><i class="halo" data-a></i>${arrowSvg(m.tone,'ghost g2')}${arrowSvg(m.tone,'ghost')}${arrowSvg(m.tone,'main')}</div>`},
};
// 문구 5가지(사장님 2026-10-06 "30분간 할인중 하단 링크확인 / 구매특가 이벤트 링크확인 같은 걸로 5개 — 마케팅 심리 자극").
//   ①②는 사장님 문구 그대로. ③ 없어질까 봐(품절) ④ 남들도 산다 ⑤ 궁금하게(가격). 놓은 뒤 글자는 고칠 수 있다.
const COPY=[
  {id:'time',label:'① 30분 할인',tone:'red',pre:'⏰',hot:'30분간 할인중',post:'하단 링크 확인'},
  {id:'event',label:'② 특가 이벤트',tone:'yellow',pre:'🎁',hot:'구매특가 이벤트',post:'링크 확인'},
  {id:'stock',label:'③ 품절 전에',tone:'black',pre:'🔥',hot:'품절되기 전에',post:'링크 먼저 확인'},
  {id:'crowd',label:'④ 다들 여기서',tone:'blue',pre:'👀 다들',hot:'여기서 사요',post:'하단 링크 확인'},
  {id:'price',label:'⑤ 가격 궁금',tone:'purple',pre:'💸 가격 보면',hot:'놀라요',post:'링크에서 확인'},
];
// 자리(가로 화면 기준 %): 띠는 화면 폭 전체로 가운데를 가로지르고, 화살표는 양옆 여백 한가운데(17%·83%)에서 띠 아래로 내리꽂는다.
const SETS=COPY.map(c=>({id:c.id,label:c.label,items:[
  {block:'arrow',l:8.5,t:53,w:17,tone:c.tone},
  {block:'arrow',l:74.5,t:53,w:17,tone:c.tone},
  {block:'band',l:0,t:35,w:100,tone:c.tone,pre:c.pre,hot:c.hot,post:c.post},
]}));
window.LINK_LONGFORM_BLOCKS={LOOP_MS,CSS,BLOCKS,SETS,
  items:id=>structuredClone((SETS.find(s=>s.id===id)||SETS[0]).items).map(m=>({kind:'block',...m})),
};
})();
