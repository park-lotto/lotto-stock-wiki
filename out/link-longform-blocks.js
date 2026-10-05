// 구매링크 롱폼(가로 16:9) 안내 블록(관제 133, 2026-10-06 사장님 "촌스럽다 — 센스있게, 사람들이 눌러보게").
//   블록 = HTML·CSS 로 짠 움직이는 덩어리 하나(고정 댓글 카드·말풍선·누르는 버튼…). 낱개 배지를 흩어 놓는 대신 덩어리째 끌어 놓는다.
//   ★크기는 전부 em — 블록 폭의 1/20 이 1em 이라 폭만 바꾸면 통째로 커지고 작아진다.
//   ★움직임은 전부 2.4초 한 바퀴(CSS animation) — 렌더는 시간을 못 박아 72프레임(30fps)을 찍고 이어 붙인다. 길이를 바꾸면 LOOP_MS 도 같이.
//   W = '고정 댓글' | '설명란' (링크를 어디에 두는지), ch = 채널명.
(()=>{
const LOOP_MS=2400;
const CSS=`
.lfb{font-family:"SUIT","Pretendard","Malgun Gothic",sans-serif;font-weight:700;color:#fff;line-height:1.25;letter-spacing:-.02em;word-break:keep-all}
.lfb b,.lfb .x{font-family:"Pretendard","SUIT",sans-serif;font-weight:800}
.lfb *{box-sizing:border-box}
@keyframes lfb-tap{0%,100%{transform:translate(0,0) scale(1)}38%{transform:translate(-.5em,-.6em) scale(1)}50%{transform:translate(-.5em,-.6em) scale(.86)}62%{transform:translate(-.5em,-.6em) scale(1)}}
@keyframes lfb-ring{0%,40%{transform:scale(.6);opacity:0}50%{opacity:.9}100%{transform:scale(1.5);opacity:0}}
@keyframes lfb-glow{0%,100%{box-shadow:0 0 0 0 rgba(62,166,255,0)}50%{box-shadow:0 0 0 .5em rgba(62,166,255,.22)}}
@keyframes lfb-drop{0%,100%{transform:translateY(-.25em);opacity:.35}50%{transform:translateY(.25em);opacity:1}}
@keyframes lfb-mark{0%{transform:scaleX(0)}35%,100%{transform:scaleX(1)}}
@keyframes lfb-dot{0%,100%{transform:translateY(0);opacity:.35}50%{transform:translateY(-.28em);opacity:1}}
@keyframes lfb-pulse{0%{transform:scale(.72);opacity:.75}100%{transform:scale(1.45);opacity:0}}
@keyframes lfb-bob{0%,100%{transform:translateY(-.22em)}50%{transform:translateY(.22em)}}
@keyframes lfb-shine{0%{transform:translateX(-140%) skewX(-18deg)}55%,100%{transform:translateX(260%) skewX(-18deg)}}
.lfb [data-a]{animation-duration:${LOOP_MS}ms;animation-iteration-count:infinite;animation-timing-function:ease-in-out}

/* ① 고정 댓글 카드 — 유튜브 댓글창을 닮은 어두운 카드. 손가락이 링크를 누른다 */
.lfb-pin{background:rgba(18,18,18,.86);border:.06em solid rgba(255,255,255,.14);border-radius:1.2em;padding:1.15em 1.2em 1.05em;box-shadow:0 1.2em 3em rgba(0,0,0,.45);backdrop-filter:blur(.6em)}
.lfb-pin .pinned{font-size:.72em;color:#aaa;display:flex;align-items:center;gap:.4em;margin-bottom:.75em}
.lfb-pin .row{display:flex;gap:.75em}
.lfb-pin .av{flex:none;width:2.3em;height:2.3em;border-radius:50%;background:linear-gradient(135deg,#ff5a5f,#ffb400);display:flex;align-items:center;justify-content:center;font-size:1em}
.lfb-pin .name{font-size:.8em;color:#fff;background:#3f3f3f;border-radius:99em;padding:.12em .6em;display:inline-block;margin-bottom:.45em}
.lfb-pin .say{font-size:1em;margin-bottom:.6em}
.lfb-pin .link{position:relative;display:inline-flex;align-items:center;gap:.4em;font-size:1.05em;color:#3ea6ff;background:rgba(62,166,255,.14);border-radius:.6em;padding:.38em .7em;animation-name:lfb-glow}
.lfb-pin .tap{position:absolute;right:-1.55em;bottom:-1.35em;font-size:1.9em;animation-name:lfb-tap;filter:drop-shadow(0 .1em .2em rgba(0,0,0,.5))}
.lfb-pin .ring{position:absolute;right:-.55em;top:50%;width:1.6em;height:1.6em;margin-top:-.8em;border-radius:50%;border:.12em solid #3ea6ff;animation-name:lfb-ring}
.lfb-pin .foot{display:flex;gap:1.3em;margin-top:.95em;font-size:.78em;color:#aaa}

/* ① 짝 — 큰 글씨 한 덩어리. 둘째 줄에 형광펜이 그어진다 */
.lfb-head .tag{display:inline-block;font-size:.95em;color:#111;background:#fff;border-radius:99em;padding:.22em .8em;margin-bottom:.8em}
.lfb-head .big{font-size:3.05em;line-height:1.14;text-shadow:0 .06em .5em rgba(0,0,0,.45)}
.lfb-head .mk{position:relative;display:inline-block;z-index:0;padding:0 .08em}
.lfb-head .mk i{position:absolute;left:0;right:0;bottom:.06em;height:.42em;background:#ffd400;z-index:-1;transform-origin:left center;animation-name:lfb-mark;border-radius:.08em}
.lfb-head .dn{display:flex;flex-direction:column;align-items:flex-start;margin:.7em 0 0 .2em;font-size:2.6em;line-height:.5}
.lfb-head .dn span{animation-name:lfb-drop}.lfb-head .dn span:nth-child(2){animation-delay:.18s}.lfb-head .dn span:nth-child(3){animation-delay:.36s}

/* ② 말풍선 — 묻는 쪽(회색)과 답하는 쪽(파랑) */
.lfb-ask,.lfb-ans{display:flex;flex-direction:column;gap:.6em}
.lfb-ask{align-items:flex-start}.lfb-ans{align-items:flex-end}
.lfb-bub{font-size:1.35em;padding:.62em .95em;border-radius:1.15em;box-shadow:0 .5em 1.4em rgba(0,0,0,.35);max-width:100%}
.lfb-ask .lfb-bub{background:#f1f1f3;color:#111;border-bottom-left-radius:.3em}
.lfb-ans .lfb-bub{background:linear-gradient(135deg,#2f8bff,#1463ff);color:#fff;border-bottom-right-radius:.3em}
.lfb-who{font-size:.74em;color:rgba(255,255,255,.8);text-shadow:0 .05em .3em rgba(0,0,0,.6);padding:0 .5em}
.lfb-typing{display:inline-flex;gap:.32em;background:#f1f1f3;border-radius:1.1em;border-bottom-left-radius:.3em;padding:.75em .9em;box-shadow:0 .5em 1.4em rgba(0,0,0,.3)}
.lfb-typing i{width:.5em;height:.5em;border-radius:50%;background:#8a8a8f;animation-name:lfb-dot}.lfb-typing i:nth-child(2){animation-delay:.16s}.lfb-typing i:nth-child(3){animation-delay:.32s}
.lfb-card{display:flex;align-items:center;gap:.7em;background:#fff;color:#111;border-radius:1em;padding:.7em .9em;box-shadow:0 .5em 1.4em rgba(0,0,0,.35);width:100%;position:relative;overflow:hidden}
.lfb-card .ic{flex:none;width:2.6em;height:2.6em;border-radius:.7em;background:#111;display:flex;align-items:center;justify-content:center;font-size:1.1em}
.lfb-card .t1{font-size:1.05em}.lfb-card .t2{font-size:.76em;color:#1463ff}
.lfb-card .go{margin-left:auto;font-size:1.3em;color:#1463ff;animation-name:lfb-bob}
.lfb-card .sh{position:absolute;top:0;bottom:0;left:0;width:30%;background:linear-gradient(90deg,transparent,rgba(20,99,255,.16),transparent);animation-name:lfb-shine}

/* ③ 누르는 버튼 — 유리 원 안의 화살표에서 고리가 퍼져 나간다 */
.lfb-btn{display:flex;flex-direction:column;align-items:center;gap:1.1em;text-align:center}
.lfb-btn .orb{position:relative;width:10em;height:10em}
.lfb-btn .orb u{position:absolute;inset:0;border-radius:50%;border:.14em solid rgba(255,255,255,.85);animation-name:lfb-pulse;animation-timing-function:ease-out;text-decoration:none}
.lfb-btn .orb u:nth-child(2){animation-delay:1.2s}
.lfb-btn .orb .core{position:absolute;inset:1.9em;border-radius:50%;background:rgba(255,255,255,.16);border:.08em solid rgba(255,255,255,.6);backdrop-filter:blur(.5em);display:flex;align-items:center;justify-content:center;box-shadow:0 .6em 1.6em rgba(0,0,0,.3)}
.lfb-btn .orb svg{width:3.2em;height:3.2em;animation-name:lfb-bob}
.lfb-btn .cap{font-size:1.75em;text-shadow:0 .06em .4em rgba(0,0,0,.5)}
.lfb-word{text-align:left}
.lfb-word .sm{font-size:1.05em;letter-spacing:.32em;opacity:.85;margin-bottom:.5em;text-shadow:0 .06em .4em rgba(0,0,0,.5)}
.lfb-word .xl{display:inline-block;font-size:5.4em;line-height:1.02;text-shadow:0 .05em .4em rgba(0,0,0,.4)}
.lfb-word .ln{width:3.2em;height:.22em;background:#fff;border-radius:99em;margin-top:.9em;transform-origin:left center;animation-name:lfb-mark}
`;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ARROW='<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" data-a><path d="M12 4v15M5.5 12.5 12 19l6.5-6.5"/></svg>';
const BLOCKS={
  pin:{label:'고정 댓글 카드',html:(W,ch)=>`<div class="lfb lfb-pin"><div class="pinned">📌 ${esc(ch)} 님이 고정함</div><div class="row"><div class="av">🛒</div><div><span class="name">@${esc(ch)}</span><div class="say">영상 속 제품, 여기서 볼 수 있어요</div><span class="link" data-a>🔗 <b>구매링크 바로가기</b><i class="ring" data-a></i><span class="tap" data-a>👆</span></span></div></div><div class="foot"><span>👍</span><span>👎</span><span>답글</span></div></div>`},
  head:{label:'큰 글씨',html:W=>`<div class="lfb lfb-head"><span class="tag x">🛒 구매링크</span><div class="big x">${W==='설명란'?'영상 아래':'맨 위'}<br><span class="mk">${esc(W)}<i data-a></i></span>에 있어요</div><div class="dn"><span data-a>⌄</span><span data-a>⌄</span><span data-a>⌄</span></div></div>`},
  ask:{label:'묻는 말풍선',html:()=>`<div class="lfb lfb-ask"><span class="lfb-who">시청자</span><div class="lfb-bub x">이거 어디서 사요? 👀</div><div class="lfb-bub x">링크 좀 알려주세요!</div><div class="lfb-typing"><i data-a></i><i data-a></i><i data-a></i></div></div>`},
  ans:{label:'답하는 말풍선',html:(W,ch)=>`<div class="lfb lfb-ans"><span class="lfb-who">${esc(ch)}</span><div class="lfb-bub x">${esc(W)}에 올려뒀어요 🙌</div><div class="lfb-card"><i class="sh" data-a></i><div class="ic">🛒</div><div><div class="t1 x">구매링크</div><div class="t2">${W==='설명란'?'영상 아래 설명란에서 확인':'댓글 맨 위에서 확인'}</div></div><span class="go x" data-a>↓</span></div></div>`},
  word:{label:'큰 낱말',html:()=>`<div class="lfb lfb-word"><div class="sm x">이 영상 속 제품</div><div class="xl x">구매<br>링크</div><div class="ln" data-a></div></div>`},
  btn:{label:'누르는 버튼',html:W=>`<div class="lfb lfb-btn"><div class="orb"><u data-a></u><u data-a></u><div class="core">${ARROW}</div></div><div class="cap x">${esc(W)}에서 확인</div></div>`},
};
// 세트 = 블록을 어디에 얼마만 한 폭으로 놓나(가로 화면 기준 %). 가운데 쇼츠(34.2~65.8%)는 비운다. 높이는 내용이 정한다.
const SETS=[
  {id:'pin',label:'① 고정 댓글',items:[{block:'head',l:4.5,t:24,w:26},{block:'pin',l:68.5,t:29,w:28.5}]},
  {id:'chat',label:'② 묻고 답하기',items:[{block:'ask',l:4.5,t:26,w:26},{block:'ans',l:69,t:36,w:27}]},
  {id:'tap',label:'③ 누르는 버튼',items:[{block:'word',l:7,t:23,w:24},{block:'btn',l:70.5,t:24,w:25}]},
];
window.LINK_LONGFORM_BLOCKS={LOOP_MS,CSS,BLOCKS,SETS,
  word:where=>where==='desc'?'설명란':'고정 댓글',
  items:(id)=>structuredClone((SETS.find(s=>s.id===id)||SETS[0]).items).map(m=>({kind:'block',...m})),
};
})();
