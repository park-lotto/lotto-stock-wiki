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
@keyframes lfb-tick{0%{transform:scale(1.13)}22%,100%{transform:scale(1)}}
@keyframes lfb-blink{0%,49%{opacity:1}50%,100%{opacity:.25}}
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
.lfb-band.green{background:linear-gradient(180deg,#22c064,#0a8f43)}.lfb-band.green .hot{background:#fff;color:#0a8f43}
/* 줄어드는 시계 — 숫자 칸 폭을 못 박아 초가 바뀌어도 글자가 흔들리지 않는다. 초마다 툭 튄다(1초 한 바퀴) */
.lfb-band .hot.clk{animation-name:lfb-tick;animation-duration:1000ms;animation-timing-function:ease-out;display:inline-flex;align-items:center;padding:.1em .22em .04em}
.lfb-band .clk b{display:inline-block;width:.66em;text-align:center;font-weight:700}.lfb-band .clk u{text-decoration:none;display:inline-block;width:.3em;text-align:center;animation-name:lfb-blink;animation-duration:1000ms;animation-timing-function:step-end}
.lfb-band.purple{background:linear-gradient(180deg,#a743ff,#5a1fe0)}.lfb-band.purple .hot{background:#ffe600;color:#111}

/* 큰 화살표 — 아래로 내리꽂고 살짝 눌렸다 올라온다. 뒤에 잔상 둘, 끝에서 고리가 퍼진다 */
.lfb-arrow{position:relative;width:100%;aspect-ratio:1/1.3}
.lfb-arrow svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible;transform-origin:50% 100%}
.lfb-arrow .main{animation-name:lfb-dive;animation-duration:1200ms;filter:drop-shadow(0 .5em .7em rgba(0,0,0,.45))}
.lfb-arrow .ghost{animation-name:lfb-trail;animation-duration:1200ms}.lfb-arrow .ghost.g2{animation-delay:-150ms}
.lfb-arrow .halo{position:absolute;left:10%;right:10%;bottom:-6%;aspect-ratio:1/.32;border-radius:50%;border:.22em solid rgba(255,255,255,.9);animation-name:lfb-halo;animation-duration:1200ms;animation-timing-function:ease-out}
`;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=sec=>{const t=Math.max(0,Math.floor(sec)),d=String(Math.floor(t/60)).padStart(2,'0')+String(t%60).padStart(2,'0');return `<b>${d[0]}</b><b>${d[1]}</b><u data-a>:</u><b>${d[2]}</b><b>${d[3]}</b>`};
const TONES={green:['#4fe08c','#0a8f43'],red:['#ff5a4d','#d9001f'],yellow:['#fff04a','#ffb800'],black:['#ff5a4d','#d9001f'],blue:['#59a6ff','#0f55f0'],purple:['#c06bff','#5a1fe0']};
// 굵은 아래 화살표(100x130 좌표): 몸통 + 넓은 촉. 흰 테두리로 어떤 배경에서도 또렷하다.
const PATH='M34 6h32a6 6 0 0 1 6 6v52h17a5 5 0 0 1 3.8 8.3L54 124a5.2 5.2 0 0 1-8 0L7.2 72.3A5 5 0 0 1 11 64h17V12a6 6 0 0 1 6-6z';
let uid=0;
const arrowSvg=(tone,cls)=>{const [a,b]=TONES[tone]||TONES.red,id='lfbg'+(++uid);
  return `<svg class="${cls}" viewBox="0 0 100 130" data-a><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs><path d="${PATH}" fill="url(#${id})" stroke="#fff" stroke-width="5" stroke-linejoin="round"/></svg>`};
const BLOCKS={
  // m.clock(초) 가 있으면 강조 칸이 '줄어드는 시계'가 된다(영상 시작 = m.clock, 1초에 1씩 준다 — clockAt 이 영상 시각으로 맞춘다).
  // m.pre · m.hot(강조 칸) · m.post = 한 줄 문구. 글자 수가 늘면 크기를 줄여 한 줄에 넣는다(띠 폭 = 20em).
  band:{label:'문구 띠',html:m=>{const text=(m.pre||'')+(m.clock?'00:00':m.hot||'')+(m.post||''),n=[...text].reduce((k,c)=>k+(/[\u0000-\u007f]/.test(c)?.58:1),0)+1.6;
    return `<div class="lfb lfb-band ${esc(m.tone||'red')}"><i class="sh" data-a></i><span class="tx" data-a style="font-size:${Math.min(1.5,17.6/n).toFixed(3)}em">${m.pre?`<span>${esc(m.pre)}</span>`:''}${m.clock?`<span class="hot clk" data-a data-clock="${Number(m.clock)||0}">${fmt(m.clock)}</span>`:`<span class="hot" data-a>${esc(m.hot)}</span>`}${m.post?`<span>${esc(m.post)}</span>`:''}</span></div>`}},
  arrow:{label:'큰 화살표',html:m=>`<div class="lfb lfb-arrow"><i class="halo" data-a></i>${arrowSvg(m.tone,'ghost g2')}${arrowSvg(m.tone,'ghost')}${arrowSvg(m.tone,'main')}</div>`},
};
// 문구 5가지(사장님 2026-10-06 "30분간 할인중 하단 링크확인 / 구매특가 이벤트 링크확인 같은 걸로 5개 — 마케팅 심리 자극").
//   ①②는 사장님 문구 그대로. ③ 없어질까 봐(품절) ④ 남들도 산다 ⑤ 궁금하게(가격). 놓은 뒤 글자는 고칠 수 있다.
//   tts = 읽어 줄 말(사장님 2026-10-07 "tts 문구로 하나씩 — 고정댓글에 링크를 눌러주세요! 행복한 하루 되세요~") — 렌더 때 작업의 성우로 한 번 읽는다.
const COPY=[
  {id:'time',label:'① 30분 카운트',tone:'red',pre:'⏰ 할인 종료까지',clock:1800,post:'하단 링크 확인',tts:'할인이 곧 끝나요! 고정 댓글에 링크를 눌러주세요. 행복한 하루 되세요!'},   // 30:00 에서 초가 줄어든다(사장님 "30분에서 초 내려가는 걸로")
  {id:'event',label:'② 특가 이벤트',tone:'yellow',pre:'🎁',hot:'구매특가 이벤트',post:'링크 확인',tts:'지금 구매 특가 이벤트 중이에요! 고정 댓글에 링크를 눌러주세요. 행복한 하루 되세요!'},
  {id:'stock',label:'③ 품절 전에',tone:'black',pre:'🔥',hot:'품절되기 전에',post:'링크 먼저 확인',tts:'품절되기 전에 서두르세요! 고정 댓글 링크에서 확인해 주세요. 좋은 하루 되세요!'},
  {id:'crowd',label:'④ 다들 여기서',tone:'blue',pre:'👀 다들',hot:'여기서 사요',post:'하단 링크 확인',tts:'다들 여기서 사고 있어요! 고정 댓글에 링크를 눌러주세요. 행복한 하루 되세요!'},
  {id:'price',label:'⑤ 가격 궁금',tone:'purple',pre:'💸 가격 보면',hot:'놀라요',post:'링크에서 확인',tts:'가격 보시면 놀라실 거예요! 고정 댓글 링크에서 확인해 주세요. 좋은 하루 되세요!'},
  {id:'spot',label:'⑥ 구매 좌표',tone:'green',pre:'📌 구매 좌표는',hot:'고정 댓글에',post:'있어요',tts:'구매 좌표는 고정 댓글에 있어요! 링크를 눌러주세요. 행복한 하루 되세요!'},
];
// 자리(가로 화면 기준 %): 띠는 화면 폭 전체로 가운데를 가로지르고, 화살표는 양옆 여백 한가운데(17%·83%)에서 띠 아래로 내리꽂는다.
const SETS=COPY.map(c=>({id:c.id,label:c.label,items:[
  {block:'arrow',l:8.5,t:53,w:17,tone:c.tone},
  {block:'arrow',l:74.5,t:53,w:17,tone:c.tone},
  {block:'band',l:0,t:35,w:100,tone:c.tone,pre:c.pre,hot:c.hot,post:c.post,tts:c.tts,...(c.clock?{clock:c.clock}:{})},
]}));
// 🔊 읽어 줄 말 프리셋(2026-10-07 사장님 "재밌게 5개 — 편안한 쇼핑 되라든지, 영상 봐 주셔서 감사하다든지 위트 있게").
//   누르면 「읽어 줄 말」 칸이 이 글로 바뀐다(그 뒤 고쳐도 된다). 80자 안. 링크 자리(고정 댓글)는 꼭 넣는다.
const TTS_PRESETS=[
  {id:'thanks',label:'🙏 끝까지 봐주셔서',tts:'여기까지 봐주신 당신, 안목이 남다르시네요! 고정 댓글 링크에서 편안한 쇼핑 되세요!'},
  {id:'wallet',label:'👛 지갑 단속',tts:'지갑 꽉 잡으세요! 고정 댓글 링크 누르는 순간 장바구니가 바빠집니다. 영상 봐주셔서 감사해요!'},
  {id:'cart',label:'🛒 장바구니 직행',tts:'고민은 배송만 늦출 뿐! 고정 댓글 링크로 장바구니 직행하세요. 오늘도 기분 좋은 쇼핑 되세요!'},
  {id:'secret',label:'🤫 우리끼리 비밀',tts:'이건 우리끼리 비밀인데요, 링크는 고정 댓글에 숨겨놨어요. 시청 감사드리고 편안한 쇼핑 되세요!'},
  {id:'friend',label:'💌 친구한테 자랑',tts:'좋은 건 나눠야 제맛! 고정 댓글 링크 확인하시고 친구한테도 살짝 알려주세요. 봐주셔서 고마워요!'},
];
window.LINK_LONGFORM_BLOCKS={LOOP_MS,CSS,BLOCKS,SETS,TTS_PRESETS,
  // 시계를 영상 시각(ms)에 맞춘다 — 편집 화면은 흐르는 시간으로, 렌더는 프레임 시각으로 부른다. 숫자가 바뀔 때만 다시 쓴다.
  clockAt(root,ms){root.querySelectorAll('[data-clock]').forEach(el=>{const sec=Math.max(0,Number(el.dataset.clock)-Math.floor(ms/1000));if(el.dataset.now!==String(sec)){el.dataset.now=String(sec);const u=el.querySelector('u');el.querySelectorAll('b').forEach(b=>b.remove());const d=String(Math.floor(sec/60)).padStart(2,'0')+String(sec%60).padStart(2,'0');u.insertAdjacentHTML('beforebegin',`<b>${d[0]}</b><b>${d[1]}</b>`);u.insertAdjacentHTML('afterend',`<b>${d[2]}</b><b>${d[3]}</b>`);}})},
  items:id=>structuredClone((SETS.find(s=>s.id===id)||SETS[0]).items).map(m=>({kind:'block',...m})),
};
})();
