/* 스탁브레인 동적 로딩 컴포넌트 (2026-07-19)
 * 밋밋한 "불러오는 중…" 대신 살아있는 로딩을 어느 페이지든 한 줄로.
 * 색은 스탁브레인 민트(자체 --sbl-* 토큰이라 앱의 --accent(퍼플)에 물들지 않음).
 *
 * 쓰는 법:
 *   SBLoader.pipeline(el, [{label:'다운로드'},{label:'분석'},...])  → 다단계 작업
 *      .set(i, '분석 중…')  // i번째를 현재로, 앞은 완료(✓)
 *      .done('완료!')       // 전부 완료
 *   SBLoader.spinner(el, {messages:['생성 중…','다듬는 중…'], bar:true})  → 단일 대기
 *      .stop()
 *   SBLoader.skeleton(el, {count:8})   → 카드 목록 로드
 *   SBLoader.clear(el)                 → 결과로 교체할 때 비우기
 */
(function(){
  if (window.SBLoader) return;
  var CSS = `
  :root{ --sbl-accent:#3ee0bf; --sbl-accent2:#6ef0d4; --sbl-accent3:#14b8a6;
    --sbl-ok:#facc6b; --sbl-line:#243244; --sbl-panel:#0d1420; --sbl-sub:#8b97b0; --sbl-faint:#5a6580;
    --sbl-grad:linear-gradient(135deg,#6ef0d4 0%,#14b8a6 100%); --sbl-pulse:62,224,191; }
  .sbl-wrap{display:flex;flex-direction:column;align-items:center;gap:18px;padding:26px 8px;color:#e7ecf7;font-family:inherit}
  @keyframes sbl-spin{to{transform:rotate(360deg)}}
  /* 파이프라인 */
  .sbl-pipe{display:flex;align-items:flex-start;justify-content:space-between;position:relative;width:100%;max-width:600px;padding:8px 4px 0}
  .sbl-st{display:flex;flex-direction:column;align-items:center;gap:8px;position:relative;z-index:2;flex:1}
  .sbl-dot{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:700;
    background:var(--sbl-panel);border:2px solid var(--sbl-line);color:var(--sbl-faint);transition:.45s cubic-bezier(.4,0,.2,1)}
  .sbl-st.done .sbl-dot{background:var(--sbl-ok);border-color:var(--sbl-ok);color:#231a00}
  .sbl-st.cur .sbl-dot{background:var(--sbl-grad);border-color:transparent;color:#04201b;animation:sbl-pulse 1.5s ease-out infinite}
  .sbl-lb{font-size:11px;color:var(--sbl-faint);text-align:center;white-space:nowrap;transition:.4s}
  .sbl-st.done .sbl-lb{color:var(--sbl-sub)} .sbl-st.cur .sbl-lb{color:#e7ecf7;font-weight:700}
  .sbl-line{position:absolute;top:25px;left:0;right:0;height:3px;background:var(--sbl-line);z-index:1;border-radius:3px}
  .sbl-fill{position:absolute;left:0;top:0;bottom:0;width:0;border-radius:3px;background:var(--sbl-grad);transition:width .6s cubic-bezier(.4,0,.2,1)}
  @keyframes sbl-pulse{0%{box-shadow:0 0 0 0 rgba(var(--sbl-pulse),.5)}70%{box-shadow:0 0 0 11px rgba(var(--sbl-pulse),0)}100%{box-shadow:0 0 0 0 rgba(var(--sbl-pulse),0)}}
  .sbl-status{display:flex;align-items:center;justify-content:center;gap:11px;margin-top:6px}
  .sbl-ring{width:24px;height:24px;border-radius:50%;flex-shrink:0;
    background:conic-gradient(from 0deg,transparent 0 28%,var(--sbl-accent3) 88%,var(--sbl-accent2));
    -webkit-mask:radial-gradient(circle 7px at center,transparent 98%,#000);mask:radial-gradient(circle 7px at center,transparent 98%,#000);
    animation:sbl-spin .9s linear infinite}
  .sbl-txt{font-size:14px;font-weight:600} .sbl-txt b{color:var(--sbl-accent);font-variant-numeric:tabular-nums}
  /* 스피너 */
  .sbl-orb{position:relative;width:66px;height:66px}
  .sbl-orb .sbl-r{position:absolute;inset:0;border-radius:50%;border:3px solid transparent}
  .sbl-orb .sbl-r1{border-top-color:var(--sbl-accent2);border-right-color:var(--sbl-accent2);animation:sbl-spin 1.1s linear infinite}
  .sbl-orb .sbl-r2{inset:10px;border-bottom-color:var(--sbl-accent3);border-left-color:var(--sbl-accent3);animation:sbl-spin 1.6s linear infinite reverse}
  .sbl-orb .sbl-core{position:absolute;inset:23px;border-radius:50%;background:var(--sbl-grad);animation:sbl-core 1.6s ease-in-out infinite}
  @keyframes sbl-core{0%,100%{transform:scale(.8);opacity:.85}50%{transform:scale(1);opacity:1}}
  .sbl-rot{height:22px;position:relative;min-width:180px;text-align:center}
  .sbl-rot span{position:absolute;inset:0;font-size:14px;font-weight:600;opacity:0;transform:translateY(7px);transition:opacity .5s,transform .5s}
  .sbl-rot span.on{opacity:1;transform:none}
  .sbl-bar{width:min(340px,80%);height:6px;border-radius:99px;background:var(--sbl-panel);border:1px solid var(--sbl-line);overflow:hidden;position:relative}
  .sbl-bar i{position:absolute;top:0;bottom:0;left:-40%;width:40%;border-radius:99px;background:var(--sbl-grad);animation:sbl-slide 1.4s ease-in-out infinite}
  @keyframes sbl-slide{0%{left:-42%}100%{left:104%}}
  /* 스켈레톤 */
  .sbl-skg{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:11px;width:100%}
  .sbl-skc{background:var(--sbl-panel);border:1px solid var(--sbl-line);border-radius:11px;padding:9px;display:flex;flex-direction:column;gap:7px}
  .sbl-sk{background:var(--sbl-line);border-radius:6px;position:relative;overflow:hidden}
  .sbl-sk::after{content:"";position:absolute;inset:0;transform:translateX(-100%);
    background:linear-gradient(90deg,transparent,rgba(var(--sbl-pulse),.28),transparent);animation:sbl-shim 1.5s infinite}
  @keyframes sbl-shim{100%{transform:translateX(100%)}}
  .sbl-sk.t{aspect-ratio:3/4}.sbl-sk.a{height:10px;width:88%}.sbl-sk.b{height:9px;width:58%}
  @media (prefers-reduced-motion:reduce){.sbl-wrap *{animation:none!important;transition:none!important}}
  `;
  function injectCSS(){
    if (document.getElementById('sbl-css')) return;
    var s = document.createElement('style'); s.id = 'sbl-css'; s.textContent = CSS;
    document.head.appendChild(s);
  }
  function esc(x){ return String(x==null?'':x).replace(/[&<>"]/g,function(m){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m];}); }

  function pipeline(el, steps){
    injectCSS();
    steps = steps || [];
    el.innerHTML =
      '<div class="sbl-wrap"><div class="sbl-pipe"><div class="sbl-line"><div class="sbl-fill"></div></div>' +
      steps.map(function(s,i){ return '<div class="sbl-st"><div class="sbl-dot">'+(i+1)+'</div><div class="sbl-lb">'+esc(s.label)+'</div></div>'; }).join('') +
      '</div><div class="sbl-status"><span class="sbl-ring"></span><span class="sbl-txt">준비 중…</span></div></div>';
    var dots = [].slice.call(el.querySelectorAll('.sbl-st'));
    var fill = el.querySelector('.sbl-fill'), txt = el.querySelector('.sbl-txt'), ring = el.querySelector('.sbl-ring');
    function set(i, statusHtml){
      dots.forEach(function(d,j){
        d.classList.toggle('done', j < i);
        d.classList.toggle('cur', j === i);
        d.querySelector('.sbl-dot').textContent = j < i ? '✓' : (j+1);
      });
      if (steps.length > 1) fill.style.width = (Math.max(0,Math.min(i,steps.length-1))/(steps.length-1))*100 + '%';
      if (statusHtml != null) txt.innerHTML = statusHtml;
    }
    function done(msg){
      dots.forEach(function(d){ d.classList.remove('cur'); d.classList.add('done'); d.querySelector('.sbl-dot').textContent='✓'; });
      fill.style.width = '100%';
      if (ring) ring.style.display = 'none';
      txt.innerHTML = esc(msg || '완료!');
    }
    return { set: set, done: done, el: el };
  }

  function spinner(el, opts){
    injectCSS();
    opts = opts || {};
    var msgs = opts.messages && opts.messages.length ? opts.messages : ['불러오는 중…'];
    el.innerHTML =
      '<div class="sbl-wrap"><div class="sbl-orb"><span class="sbl-r sbl-r1"></span><span class="sbl-r sbl-r2"></span><span class="sbl-core"></span></div>' +
      '<div class="sbl-rot">' + msgs.map(function(m,i){ return '<span'+(i===0?' class="on"':'')+'>'+esc(m)+'</span>'; }).join('') + '</div>' +
      (opts.bar ? '<div class="sbl-bar"><i></i></div>' : '') + '</div>';
    var sp = [].slice.call(el.querySelectorAll('.sbl-rot span')), i = 0, timer = null;
    if (sp.length > 1){
      timer = setInterval(function(){
        // 컨테이너가 화면에서 빠졌으면(결과로 교체됨) 스스로 멈춘다 — 인터벌 누수 방지.
        if (!document.body || !document.body.contains(sp[0])) { clearInterval(timer); return; }
        sp[i].classList.remove('on'); i=(i+1)%sp.length; sp[i].classList.add('on');
      }, opts.interval || 1600);
    }
    return { stop: function(){ if (timer) clearInterval(timer); }, el: el };
  }

  function skeleton(el, opts){
    injectCSS();
    opts = opts || {};
    var n = opts.count || 8;
    var cards = '';
    for (var k=0;k<n;k++) cards += '<div class="sbl-skc"><div class="sbl-sk t"></div><div class="sbl-sk a"></div><div class="sbl-sk b"></div></div>';
    el.innerHTML = '<div class="sbl-skg">' + cards + '</div>';
    return { el: el };
  }

  function clear(el){ if (el) el.innerHTML = ''; }

  window.SBLoader = { pipeline: pipeline, spinner: spinner, skeleton: skeleton, clear: clear };
})();
