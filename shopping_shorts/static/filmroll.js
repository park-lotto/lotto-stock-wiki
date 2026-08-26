/* filmroll.js — 필름 롤러(캡컷식 자르기) 부품 하나.
 *
 * ★같은 자르기 UI가 세 곳에서 필요하다(위 훅 컷 · 아래 소스 카드 · 필름형 토글).
 *   세 벌로 적으면 반드시 어긋난다(0순위-B) — 이 파일 하나만 쓴다.
 *
 * 쓰는 법:
 *   const roll = filmroll(hostEl, {
 *     videoId, src, dur,            // 원본 영상
 *     from, to,                     // 지금 쓰는 구간(하이라이트). 없으면 안 그린다
 *     caps,                         // [[초, "자막"], ...] (선택)
 *     onCommit(ranges)              // [{s,e}, ...] 담기 눌렀을 때
 *     onReplace({s,e})              // (선택) 열려 있는 조각을 이 구간으로 바꿀 때.
 *                                   //   주면 구간 1개일 때만 🔁 버튼이 나온다.
 *   });
 *   roll.destroy();                 // 접을 때 반드시 부른다(영상·타이머 정리)
 *
 * ★재생은 '미리보기 창'에서 한다(2026-08-26 사장님). opt.onPlay(a,b)를 주면
 *   스페이스·구간재생을 그쪽으로 넘긴다 — 필름 안의 <video>는 썸네일 추출과
 *   스크러빙(프레임 확인)에만 쓴다. onPlay가 없으면 종전대로 안에서 재생한다.
 *
 * ★데모(scratchpad/filmdemo)에서 실측으로 밟은 함정 — 여기 다 반영돼 있다:
 *   · 1칸 = 정확히 1초(STEP). t=i*(DUR/N)로 뽑으면 화면과 재생이 어긋난다
 *   · 썸네일은 칸 한가운데에서 뽑는다(정각은 그 칸 안의 전환을 놓쳐 22.6% 다른 그림)
 *   · 길이는 영상에서 읽는다(하드코딩 22.9 vs 실제 22.867 → 끝으로 갈수록 벌어짐)
 *   · 썸네일 캐시키와 조회키가 어긋나면 '있는데 안 쓰인다' → thumbAt(초) 하나로
 *   · 손잡이는 display:block + pointer-events:auto (span은 inline이라 0×0이 된다)
 */
(function (global) {
  'use strict';

  const PPS_BASE = 54;                 // 칸 폭 54px일 때 1초
  const LADDER = [0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10];
  const CH = 72;                       // 칸 높이(9:16 → 폭 약 40)

  const CACHE = {};                    // "vid|step|i" → dataURL (전 롤러 공용)

  function calcStep(cw) {
    const raw = PPS_BASE / cw;
    let best = LADDER[0];
    for (const v of LADDER) if (v <= raw) best = v;
    return best;
  }

  // ★필름이 두 개(가운데·칸 안) 열려 있을 수 있다. 키(스페이스·Esc)를 document에서
  //   받으므로 **둘 다** 반응해 함께 재생되고 막대가 같이 움직였다(2026-08-26 사장님
  //   "아래 빨간막대기를 움직이는데 훅 빨간막대기도 같이 움직이고"). 마지막으로 만진
  //   필름 하나만 키를 받는다.
  let ACTIVE = null;

  function filmroll(host, opt) {
    opt = opt || {};
    const SELF = {};                    // 이 인스턴스의 표식
    ACTIVE = SELF;                      // 새로 편 필름이 활성이 된다
    const vid = opt.videoId || '';
    const caps = opt.caps || [];
    let DUR = +opt.dur || 0;
    let CW = 150, STEP = 0.25, N = 0, off = 0;   // 기본 확대 = 한 칸 0.25초(F21, 사장님)
    let _homed = false;      // 지금 쓰는 구간으로 한 번 옮겼나(처음 펼칠 때만)
    let MA = null;                     // 찍어둔 시작점
    // ★열 때 **이미 쓰는 구간**을 주황 박스로 올린다(2026-08-26 사장님 "상단에 카드형으로
    //   들어간걸 펼치면 … 해당 2.4초만 필름형으로 나오게"). 조각을 펼치면 그 조각이,
    //   영상을 펼치면 그 영상에서 담긴 구간들이 바로 손에 잡힌다(늘리고 줄이고 지운다).
    let LASTTAP = { i: null, t: 0 };   // 두 번 누르기 판정용
    // ★멈춘 지점(2026-08-26 사장님 "다시누르면 처음 재생한곳으로간다 => 마지막 멈춘
    //   지점에서 이어서 재생으로"). 구간을 끝까지 보면 비워서 다음엔 처음부터 간다.
    let RESUME = null;
    let BOXES = (opt.initBoxes || [])
      .map(b => ({ s: Math.round(+b.s * 100) / 100, e: Math.round(+b.e * 100) / 100 }))
      .filter(b => isFinite(b.s) && isFinite(b.e) && b.e - b.s >= 0.1)
      .sort((x, y) => x.s - y.s);
    let ACTBOX = null;
    let destroyed = false;
    let raf = 0, scrubWant = null, scrubBusy = false, playing = false;
    // ★구간 길이는 **상태로 들고 있는다**(2026-08-26 사장님 "이거 안된다" 캡쳐 534).
    //   종전엔 drawBar()가 innerHTML을 새로 그리며 value="2.4"를 다시 박아, 숫자를
    //   고쳐도 구간을 하나 만드는 순간 2.4로 되돌아갔다.
    let BOXLEN = 2.4;

    host.innerHTML =
      '<div class="fr">' +
        '<div class="frtop">' +
          '<span class="frname"></span>' +
          // ★도구줄을 **머리줄 안**으로(2026-08-26 사장님 "왼쪽클릭 손잡이끌기등 글자를
          //   영상1전체 옆으로 이동하게해서 넓게 / 구간박스 이것도 위쪽으로 이동
          //   아래쪽까지 필름높이는 높여"). 별도 줄로 두면 그 한 줄만큼 필름이 낮아진다.
          '<div class="frbar"></div>' +
          '<span class="frzoom">확대 <input type="range" class="frz" min="26" max="240" value="150"></span>' +
          '<span class="frstep"></span>' +
          '<button type="button" class="frclose" title="접기">◀ 접기</button>' +
        '</div>' +
        '<div class="frwin">' +
          '<div class="frload">🎞 필름 뽑는 중…</div>' +
          '<div class="frbelt"></div>' +
          '<div class="frcaps"></div>' +
          '<div class="fruse"></div>' +
          '<div class="frboxes"></div>' +
          '<div class="frmark"></div>' +
          '<div class="frhead"><span class="frgrip"></span><span class="frdur"></span></div>' +
        '</div>' +
        '<video class="frpv" muted playsinline preload="auto"></video>' +
        '<canvas class="frcv" style="display:none"></canvas>' +
      '</div>';

    const $ = s => host.querySelector(s);
    const win = $('.frwin'), belt = $('.frbelt'), pv = $('.frpv'), cv = $('.frcv');
    const headEl = $('.frhead'), gripEl = $('.frgrip'), durEl = $('.frdur');
    const markEl = $('.frmark'), boxesEl = $('.frboxes'), capsEl = $('.frcaps');
    const useEl = $('.fruse'), barEl = $('.frbar'), loadEl = $('.frload');

    $('.frname').textContent = opt.name || '';
    $('.frclose').onclick = () => { if (opt.onClose) opt.onClose(); };

    const winW = () => win.clientWidth || 600;
    const pps = () => CW / STEP;
    const maxOff = () => Math.max(0, DUR * pps() - winW());
    const clamp = v => Math.max(0, Math.min(maxOff(), v));
    const secToX = t => t * pps() - off;
    const xToSec = x => (x + off) / pps();

    /* 그 시각의 썸네일 — 저장 키를 아는 유일한 곳(캐시키 불일치 방지) */
    function thumbAt(sec) {
      const i = Math.floor(sec / STEP);
      const hit = CACHE[vid + '|' + STEP + '|' + i];
      if (hit) return hit;
      let best = '', bd = 1e9;
      for (const k in CACHE) {
        const p = k.split('|');
        if (p[0] !== vid) continue;
        const st = parseFloat(p[1]), idx = parseInt(p[2], 10);
        if (!isFinite(st) || !isFinite(idx)) continue;
        const d = Math.abs(idx * st + st / 2 - sec);
        if (d < bd) { bd = d; best = CACHE[k]; }
      }
      return best;
    }

    function seekRaw(v, t) {
      return new Promise(r => {
        let done = false;
        const k = () => { if (done) return; done = true; v.removeEventListener('seeked', k); r(); };
        v.addEventListener('seeked', k);
        try { v.currentTime = Math.min(Math.max(0, t), Math.max(0, (v.duration || DUR) - 0.04)); }
        catch (_) { done = true; r(); return; }
        setTimeout(k, 800);
      });
    }

    /* 스크러빙 — 끄는 동안 미리보기가 따라온다. 마지막 요청만 처리한다. */
    function scrubTo(t) {
      // ★큰 미리보기도 같은 시각으로 세운다 — 필름 안 작은 화면만 움직이면 어디를
      //   보고 있는지 알기 어렵다(2026-08-26 사장님). 부품은 부모를 모른다: 콜백만 부른다.
      if (typeof opt.onScrub === 'function') { try { opt.onScrub(t); } catch (_) {} }
      scrubWant = Math.max(0, Math.min(DUR - 0.03, t));
      moveHead(scrubWant);
      if (scrubBusy) return;
      scrubBusy = true;
      const pump = () => {
        if (destroyed || scrubWant === null) { scrubBusy = false; return; }
        const t2 = scrubWant; scrubWant = null;
        pv.pause(); playing = false;
        let done = false;
        const fin = () => { if (done) return; done = true; pv.removeEventListener('seeked', fin); pump(); };
        pv.addEventListener('seeked', fin);
        try { pv.currentTime = t2; } catch (_) { done = true; scrubBusy = false; return; }
        setTimeout(fin, 240);
      };
      pump();
    }

    function moveHead(t) {
      if (!headEl) return;
      if (MA !== null && durEl) {
        durEl.textContent = Math.abs(t - MA).toFixed(2) + '초';
        durEl.classList.add('on');
      } else if (durEl) durEl.classList.remove('on');
      const x = secToX(t);
      if (x < -6 || x > winW() + 6) { headEl.classList.remove('on'); return; }
      headEl.classList.add('on');
      headEl.style.left = Math.round(x) + 'px';
    }

    function drawMark() {
      if (MA === null) { markEl.classList.remove('on'); return; }
      const x = secToX(MA);
      if (x < -4 || x > winW() + 4) { markEl.classList.remove('on'); return; }
      markEl.classList.add('on'); markEl.style.left = Math.round(x) + 'px';
    }

    function drawUse() {
      if (opt.from == null || opt.to == null) { useEl.style.display = 'none'; return; }
      useEl.style.display = 'block';
      useEl.style.transform = `translateX(${-off}px)`;
      useEl.style.width = (DUR * pps()) + 'px';
      useEl.innerHTML = `<span class="u" style="left:${opt.from * pps()}px;` +
        `width:${Math.max(4, (opt.to - opt.from) * pps())}px"><b>지금 쓰는 구간</b></span>`;
    }

    function drawCaps() {
      capsEl.style.transform = `translateX(${-off}px)`;
      capsEl.style.width = (DUR * pps()) + 'px';
      if (!caps.length) { capsEl.innerHTML = ''; return; }
      capsEl.innerHTML = caps.map((c, i) => {
        const st = c[0], en = (i + 1 < caps.length) ? caps[i + 1][0] : DUR;
        const w = (en - st) * pps() - 1;
        if (w < 8) return '';
        return `<span class="cp" style="left:${st * pps()}px;width:${w}px">${esc(c[1])}</span>`;
      }).join('');
    }

    function drawBoxes() {
      boxesEl.style.width = (DUR * pps()) + 'px';
      boxesEl.innerHTML = BOXES.map((b, i) =>
        `<div class="bx${ACTBOX === i ? ' act' : ''}" data-i="${i}" ` +
        `style="left:${secToX(b.s)}px;width:${Math.max(8, (b.e - b.s) * pps())}px">` +
        `<span class="t">${(b.e - b.s).toFixed(2)}초</span>` +
        `<span class="e l" data-edge="l"></span><span class="e r" data-edge="r"></span>` +
        `<span class="x" data-del="${i}">×</span>` +
        // ★2026-08-26 사장님 "주황색 박스 만들면 위쪽 훅 있는 윗칸으로 더블클릭이나
        //   드래그로 옮기기". 박스 본체는 pointerdown에서 preventDefault를 하므로
        //   HTML5 dragstart가 안 뜬다(이동·양끝조절이 그 위에 서 있다) — 그래서
        //   **끌기 전용 손잡이**를 따로 둔다. 부품은 어디로 가는지 모른다: 부모가
        //   준 onBoxDrag에 넘길 뿐이다.
        (typeof opt.onBoxDrag === 'function'
          ? `<span class="g" draggable="true" data-g="${i}" title="위 칸으로 끌어다 놓으면 담깁니다">⬆</span>` : '') +
        `</div>`).join('');
      wireBoxes();
    }

    function wireBoxes() {
      boxesEl.querySelectorAll('.bx').forEach(el => {
        let mode = null, sx = 0, s0 = 0, e0 = 0, moved = false;
        el.addEventListener('pointerdown', ev => {
          const i = +el.dataset.i, b = BOXES[i]; if (!b) return;
          // ★두 번 누르기 = 담기. dblclick 이벤트는 **실제 마우스에서 안 온다**
          //   (pointerdown에서 preventDefault+setPointerCapture를 하기 때문 — 실측
          //    2026-08-26: dispatchEvent로는 되는데 진짜 클릭은 안 됐다).
          //   그래서 pointerdown에서 직접 간격을 재 판정한다.
          if (ev.target.dataset.del === undefined && !ev.target.dataset.edge
              && !ev.target.dataset.g) {
            const now = (ev.timeStamp || 0);
            if (LASTTAP.i === i && now - LASTTAP.t < 450) {
              LASTTAP = { i: null, t: 0 };
              ev.stopPropagation(); ev.preventDefault();
              if (typeof opt.onBoxCommit === 'function') opt.onBoxCommit({ s: b.s, e: b.e });
              return;
            }
            LASTTAP = { i, t: now };
          }
          if (ev.target.dataset.del !== undefined) {      // × = 즉시 삭제
            ev.stopPropagation(); ev.preventDefault();
            BOXES.splice(+ev.target.dataset.del, 1);
            ACTBOX = null; drawBoxes(); drawBar(); return;
          }
          ev.stopPropagation(); ev.preventDefault();
          mode = ev.target.dataset.edge || 'move';
          sx = ev.clientX; s0 = b.s; e0 = b.e; moved = false;
          ACTBOX = i; el.classList.add('dragging');
          try { el.setPointerCapture(ev.pointerId); } catch (_) {}
        });
        el.addEventListener('pointermove', ev => {
          if (!mode) return;
          const i = +el.dataset.i, b = BOXES[i]; if (!b) return;
          const d = (ev.clientX - sx) / pps();
          if (Math.abs(ev.clientX - sx) > 3) moved = true;
          if (mode === 'l') b.s = Math.max(0, Math.min(e0 - 0.1, s0 + d));
          else if (mode === 'r') b.e = Math.min(DUR, Math.max(s0 + 0.1, e0 + d));
          else { const len = e0 - s0, ns = Math.max(0, Math.min(DUR - len, s0 + d)); b.s = ns; b.e = ns + len; }
          b.s = Math.round(b.s * 100) / 100; b.e = Math.round(b.e * 100) / 100;
          el.style.left = secToX(b.s) + 'px';
          el.style.width = Math.max(8, (b.e - b.s) * pps()) + 'px';
          const lab = el.querySelector('.t'); if (lab) lab.textContent = (b.e - b.s).toFixed(2) + '초';
          ev.stopPropagation();
        });
        const end = ev => {
          if (!mode) return;
          mode = null; el.classList.remove('dragging');
          const b = BOXES[+el.dataset.i];
          BOXES.sort((x, y) => x.s - y.s);
          ACTBOX = b ? BOXES.indexOf(b) : null;
          drawBoxes(); drawBar();
          ev.stopPropagation();
        };
        el.addEventListener('pointerup', end);
        el.addEventListener('pointercancel', end);
        el.addEventListener('click', ev => ev.stopPropagation());
        el.addEventListener('contextmenu', ev => { ev.preventDefault(); ev.stopPropagation(); });
        // ⬆ 손잡이 = 위 칸으로 끌어 담기. preventDefault를 하면 드래그가 시작을
        // 안 하므로 여기서는 **막지 않는다**(박스 이동 로직만 끊는다).
        const g = el.querySelector('.g');
        if (g) {
          g.addEventListener('pointerdown', ev => ev.stopPropagation());
          g.addEventListener('click', ev => ev.stopPropagation());
          g.addEventListener('dragstart', ev => {
            ev.stopPropagation();
            const b = BOXES[+el.dataset.i]; if (!b) return;
            if (ev.dataTransfer) ev.dataTransfer.effectAllowed = 'copy';
            opt.onBoxDrag({ s: b.s, e: b.e }, ev);
          });
          g.addEventListener('dragend', ev => {
            ev.stopPropagation();
            if (typeof opt.onBoxDragEnd === 'function') opt.onBoxDragEnd();
          });
        }
      });
    }

    function addBox(a, b) {
      if (b - a < 0.1) return false;
      BOXES.push({ s: Math.round(a * 100) / 100, e: Math.round(b * 100) / 100 });
      BOXES.sort((x, y) => x.s - y.s);
      ACTBOX = null; MA = null;
      drawBoxes(); drawMark(); drawBar();
      return true;
    }

    /* 손잡이 우클릭 = 여기 찍기(시작 → 끝) */
    function markHere() {
      const t = Math.round(pv.currentTime * 100) / 100;
      if (MA === null) { MA = t; drawMark(); drawBar(); moveHead(t); return; }
      const a = Math.min(MA, t), b = Math.max(MA, t);
      if (b - a < 0.15) { MA = null; drawMark(); drawBar(); moveHead(t); return; }
      addBox(a, b); moveHead(t);
    }

    function makeBox() {
      const el = host.querySelector('.frlen');
      if (el) BOXLEN = Math.max(0.1, parseFloat(el.value) || BOXLEN);
      const n = BOXLEN;
      const a = Math.max(0, Math.min(DUR - 0.1, pv.currentTime));
      addBox(a, Math.min(DUR, a + n));
    }

    function drawBar() {
      const total = BOXES.reduce((a, b) => a + (b.e - b.s), 0);
      barEl.innerHTML =
        (MA !== null
          ? `<span class="frhint">시작 <b>${MA.toFixed(2)}초</b> — 빨간선을 옮기고 <b>손잡이 클릭</b> 한 번 더</span>`
          // ★상시 안내문은 뺐다(2026-08-26 사장님 캡쳐 532) — 한 줄을 통째로 먹으면서
          //   그만큼 필름이 낮아졌다. 조작법은 오른쪽 위 [?] 도움말에 있다.
          //   '시작 N초' 같은 **작업 중 상태**는 그대로 남긴다(그건 지금 뭘 하는지다).
          : '') +
        `<span class="frmk"><button type="button" class="frbtn mk">＋ 구간</button>` +
        `<input type="number" class="frlen" step="0.1" min="0.1" value="${BOXLEN}"><span class="frhint">초</span></span>` +
        (BOXES.length
          ? `<button type="button" class="frbtn" data-act="play">▶ 미리보기에서 듣기</button>` +
            `<button type="button" class="frbtn ok">⬆ 담기 (${BOXES.length}개 · ${total.toFixed(2)}초)</button>` +
            // 🔁 이 조각을 이 구간으로 — 부모가 onReplace를 줬을 때만 나온다(부품은 부모를 모른다).
            //   구간 하나일 때만 의미가 있다(무엇으로 바꿀지가 하나여야 한다).
            (typeof opt.onReplace === 'function' && BOXES.length === 1
              ? `<button type="button" class="frbtn rep">🔁 이 조각을 이 구간으로</button>` : '') +
            `<button type="button" class="frbtn" data-act="clr">비우기</button>`
          : '');
      const mk = barEl.querySelector('.mk'); if (mk) mk.onclick = makeBox;
      const len = barEl.querySelector('.frlen');
      if (len) len.oninput = () => { const v = parseFloat(len.value); if (v > 0) BOXLEN = v; };
      const ok = barEl.querySelector('.ok');
      if (ok) ok.onclick = () => { if (opt.onCommit) opt.onCommit(BOXES.map(b => ({ s: b.s, e: b.e }))); };
      const rep = barEl.querySelector('.rep');
      if (rep) rep.onclick = () => {
        if (BOXES.length === 1 && typeof opt.onReplace === 'function')
          opt.onReplace({ s: BOXES[0].s, e: BOXES[0].e });
      };
      const clr = barEl.querySelector('[data-act="clr"]');
      if (clr) clr.onclick = () => { BOXES = []; ACTBOX = null; drawBoxes(); drawBar(); };
      const pl = barEl.querySelector('[data-act="play"]');
      if (pl) pl.onclick = () => {
        const b = (ACTBOX != null && BOXES[ACTBOX]) ? BOXES[ACTBOX] : BOXES[0];
        if (!b) return;
        if (typeof opt.onPlay === 'function') opt.onPlay(b.s, b.e);
      };
    }

    function applyW() {
      off = clamp(off);
      belt.style.transform = `translateX(${-off}px)`;
      belt.querySelectorAll('.fc').forEach(c => {
        const f = parseFloat(c.dataset.frac || '1');
        c.style.width = (CW * f) + 'px';
      });
      boxesEl.style.transform = `translateX(${-off}px)`;
      markEl.style.transform = 'none';
      drawCaps(); drawUse(); drawBoxes(); drawMark();
      moveHead(pv.currentTime || 0);
      // 이번에 화면에 든 칸 중 아직 그림이 없는 것만 뽑는다(있는 건 건너뛴다).
      clearTimeout(applyW._fill);
      applyW._fill = setTimeout(() => { fillVisible(); }, 60);
    }

    // ★같은 필름을 두 번 겹쳐 뽑으면 belt에 옛 칸이 남아 **눈금이 섞인다**
    //   (2026-08-26 사장님 스샷: 9.3s 다음에 0.0s). 확대·재빌드가 겹칠 수 있으므로
    //   한 번에 하나만 돌게 줄을 세운다.
    let _stripSeq = 0;
    async function strip() {
      const my = ++_stripSeq;
      loadEl.style.display = 'block';
      // ★belt를 미리 비우고 한 칸씩 붙이면, 뽑는 데 시간이 걸리는 사이 다른 배율의
      //   칸이 섞여 들어간다(2026-08-26 사장님 스샷: 9.3s 다음에 0.0s).
      //   **다 만들어 한 번에 갈아 끼운다** — 중간 상태가 화면에 존재하지 않는다.
      const frag = document.createDocumentFragment();
      STEP = calcStep(CW);
      N = Math.max(1, Math.ceil(DUR / STEP));
      host.querySelector('.frstep').textContent = `한 칸 ${STEP < 1 ? STEP.toFixed(2) : STEP.toFixed(0)}초`;
      const tmp = document.createElement('video');
      tmp.muted = true; tmp.preload = 'auto'; tmp.src = opt.src;
      await new Promise(r => {
        if (tmp.readyState >= 1) return r();
        tmp.addEventListener('loadedmetadata', r, { once: true });
        setTimeout(r, 5000);
      });
      if (destroyed) return;
      if (isFinite(tmp.duration) && tmp.duration > 0) DUR = tmp.duration;
      N = Math.max(1, Math.ceil(DUR / STEP));
      const w = Math.max(24, Math.round(CW)), x = cv.getContext('2d');
      cv.width = w * 2; cv.height = CH * 2;
      // ★칸 **틀만** 먼저 만든다(그림 없이). 종전엔 여기서 칸마다 영상을 seek해
      //   캡처하느라 확대하면 250칸 × seek가 돌아 브라우저가 통째로 버벅였다
      //   (2026-08-26 사장님 "렉이 엄청 심한데"). 그림은 아래 fillVisible이
      //   **보이는 칸만** 채운다 — 30초 영상이라도 실제로 뽑는 건 20~30칸이다.
      for (let i = 0; i < N; i++) {
        if (destroyed) return;
        const t0 = i * STEP;
        const t = Math.min(DUR - 0.05, t0 + Math.min(STEP / 2, (DUR - t0) / 2));
        const c = document.createElement('div');
        c.className = 'fc' + (((i + 1) % 5 === 0) ? ' tick' : '');
        const frac = Math.min(1, (DUR - t0) / STEP);
        c.style.width = (CW * frac) + 'px';
        c.dataset.frac = frac; c.dataset.t = t.toFixed(3); c.dataset.i = i;
        const lab = (t0 % (STEP < 1 ? 1 : 5 * STEP) < STEP * 0.9)
          ? `<span class="s">${t0.toFixed(STEP < 1 ? 1 : 0)}s</span>` : '';
        const key = vid + '|' + STEP + '|' + i;
        const cached = CACHE[key];             // 전에 뽑아둔 게 있으면 바로 쓴다
        c.innerHTML = (cached ? `<img src="${cached}">` : '') + lab;
        if (my !== _stripSeq) return;        // 그 사이 새로 뽑기 시작했다 — 이 결과는 버린다
        frag.appendChild(c);
      }
      _shotVid = tmp;                          // 그림 뽑을 때 다시 쓴다(매번 새로 열지 않는다)
      if (my !== _stripSeq) return;          // 그 사이 새로 뽑기 시작했다 — 이 결과는 버린다
      belt.replaceChildren(frag);            // ← 여기서 한 번에 갈아 끼운다
      loadEl.style.display = 'none';
      applyW();                              // 폭·위치를 잡고
      fillVisible();                         // 보이는 칸부터 그림을 채운다
      // ★2026-08-26 3차 사장님 "펼치면 전체 영상이 나오네". 원본 전체를 펴는 건 맞다
      //   (조각 밖 구간을 잡으려면 원본이 다 보여야 한다) — 문제는 **0초에서 열려서**
      //   지금 쓰는 구간이 화면 밖에 있었다는 것이다. 처음 한 번만 그 구간으로 옮긴다
      //   (확대·축소로 다시 그릴 때는 그 자리를 지킨다 — 아래 frz 핸들러가 정한다).
      if (!_homed && opt.from != null) {
        _homed = true;
        // ★배율은 **레이아웃이 잡힌 뒤** 정한다. 여기서 바로 재면 win.clientWidth가 아직
        //   0이라 winW()가 600 폴백을 쓰고, 그 폭 기준으로 엉뚱한 배율이 나온다
        //   (실측 2026-08-26: 2.4초 구간인데 창의 32%밖에 안 찼다).
        requestAnimationFrame(() => { try{ _fitToRange(); }catch(_){} });
      }
      applyW(); drawBar();
    }

    async function _fitToRange() {
      {
        const span = Math.max(0.2, (opt.to != null ? opt.to : opt.from) - opt.from);
        // ★조각을 펼쳤으면 **그 구간이 창을 채우도록** 확대한다(2026-08-26 사장님
        //   "필름은 전체 영상이 아니라 카드 한장 2.6초까지를 펼치는거다").
        //   원본을 잘라 그리지 않고 배율만 맞춘다 — 밖으로 넓히려면 옆으로 끌면 된다
        //   (구간 밖을 못 보게 잘라버리면 '조각 범위 넓히기'가 통째로 막힌다).
        if (opt.fit) {
          const z = host.querySelector('.frz');
          const min = +z.min || 26, max = +z.max || 240;
          // ★한 칸 초(STEP)가 칸 폭(CW)에 딸려 바뀌므로 식으로 풀면 값이 진동한다(실측:
          //   목표가 240↔100을 오가며 엉뚱한 48로 끝났다). 후보를 훑어 **보이는 초가
          //   구간에 가장 가까운** 칸 폭을 고른다 — 215개뿐이라 훑는 게 싸고 확실하다.
          const W = winW() * 0.9;
          let want = CW, best = Infinity;
          for (let c = min; c <= max; c++) {
            const seen = W * calcStep(c) / c;            // 그 배율에서 창에 보이는 초
            const d = Math.abs(seen - span);
            if (d < best) { best = d; want = c; }
          }
          if (want !== CW) {
            z.value = want; CW = want;
            const ns = calcStep(CW);
            if (ns !== STEP) { await strip(); }           // 칸 간격이 바뀌면 다시 뽑는다
          }
        }
        const mid = opt.from + span / 2;
        off = clamp(mid * pps() - winW() / 2);
        try { pv.currentTime = opt.from; } catch (_) {}
      }
      applyW(); drawBar();
    }

    /* ── 보이는 칸만 그림 채우기 ─────────────────────────────
       필름은 원본 전체를 그리지만 **화면에 든 칸만** 실제로 캡처한다.
       스크롤·확대 때마다 다시 부르면 그때 필요한 것만 뽑힌다(캐시는 그대로 쓴다). */
    let _shotVid = null, _filling = false;
    async function fillVisible() {
      if (_filling || destroyed || !_shotVid) return;
      _filling = true;
      try {
        const x = cv.getContext('2d');
        const my = _stripSeq;
        const cells = belt.children;
        const left = off - CW, right = off + winW() + CW;      // 화면 ±한 칸 여유
        for (let k = 0; k < cells.length; k++) {
          if (destroyed || my !== _stripSeq) break;
          const c = cells[k];
          if (c.querySelector('img')) continue;                // 이미 그림이 있다
          const cl = c.offsetLeft, cw2 = c.offsetWidth;
          if (cl + cw2 < left || cl > right) continue;          // 화면 밖 — 나중에
          const i = +c.dataset.i, t = +c.dataset.t;
          const key = vid + '|' + STEP + '|' + i;
          let d = CACHE[key];
          if (!d) {
            await seekRaw(_shotVid, t);
            if (destroyed || my !== _stripSeq) break;
            try { x.drawImage(_shotVid, 0, 0, cv.width, cv.height); d = cv.toDataURL('image/jpeg', 0.6); CACHE[key] = d; }
            catch (_) { d = ''; }
          }
          if (d) c.insertAdjacentHTML('afterbegin', `<img src="${d}">`);
        }
      } finally { _filling = false; }
    }

    host.addEventListener('pointerdown', () => { ACTIVE = SELF; }, true);
    host.addEventListener('mouseenter', () => { ACTIVE = SELF; });

    /* ── 마우스 배선 ───────────────────────────────────────── */
    // ★상태 선언을 배선보다 먼저 — 아래 핸들러들이 참조한다(TDZ 예방)
    let down = false, sx = 0, so = 0, dragged = false, dg = false;
    win.addEventListener('contextmenu', e => e.preventDefault());
    win.addEventListener('click', e => {
      if (dragged || e.target.closest('.bx')) return;
      const r = win.getBoundingClientRect();
      const t = Math.max(0, Math.min(DUR, xToSec(e.clientX - r.left)));
      pv.pause(); playing = false;
      scrubTo(t);
    });
    win.addEventListener('wheel', e => {
      e.preventDefault();
      // ★Ctrl+휠 = 확대/축소(2026-08-26 사장님). 슬라이더까지 손을 옮기지 않고 그 자리에서
      //   들여다본다. 확대는 **가리키는 지점을 축으로** 한다 — 안 그러면 보던 데를 놓친다.
      if (e.ctrlKey || e.metaKey) {
        const r = win.getBoundingClientRect();
        const anchorT = xToSec(e.clientX - r.left);          // 마우스가 가리키던 시각
        const z = host.querySelector('.frz');
        const min = +z.min || 26, max = +z.max || 240;
        const next = Math.max(min, Math.min(max, Math.round(CW * (e.deltaY > 0 ? 0.85 : 1.18))));
        if (next === CW) return;
        z.value = next;
        const ns = calcStep(next);
        CW = next;
        const keep = () => { off = clamp(anchorT * pps() - (e.clientX - r.left)); applyW(); };
        if (ns !== STEP) strip().then(keep); else keep();
        return;
      }
      off = clamp(off + ((e.deltaY || e.deltaX) > 0 ? pps() * 2 : -pps() * 2)); applyW();
    }, { passive: false });

    // ★왼쪽 버튼으로 필름을 끌어 좌우로 미는 조작은 **없앴다**(2026-08-26 사장님 캡쳐 536
    //   "마우스 왼쪽잡고 화면이동하는거 없애줘 빨간선 옮기는거랑 겹친다").
    //   같은 왼쪽 버튼이 '빨간선 찍기'와 '밀기' 둘 다를 맡아, 조금만 손이 흔들려도
    //   찍으려던 게 밀기로 새고 빨간선이 안 옮겨졌다. 한 버튼에 두 일을 주지 않는다.
    //   좌우 이동은 **휠**, 확대는 **Ctrl+휠**로 그대로 된다(위 wheel 핸들러).
    //   dragged는 이제 늘 false — win click이 조건 없이 '여기 찍기'로 간다.

    // ★손잡이를 끌었는지(=훑어보기) 눌렀다 뗐는지(=여기 찍기) 가른다.
    //   끌고 난 뒤의 click까지 '찍기'로 받으면 훑을 때마다 구간이 생긴다.
    let gripMoved = false, gripX = 0;
    gripEl.addEventListener('pointerdown', e => {
      dg = true; gripMoved = false; gripX = e.clientX;
      e.stopPropagation(); e.preventDefault();
      try { gripEl.setPointerCapture(e.pointerId); } catch (_) {}
    });
    gripEl.addEventListener('pointermove', e => {
      if (!dg) return;
      if (Math.abs(e.clientX - gripX) > 4) gripMoved = true;
      const r = win.getBoundingClientRect();
      scrubTo(xToSec(e.clientX - r.left));
      e.stopPropagation();
    });
    gripEl.addEventListener('pointerup', e => { dg = false; e.stopPropagation(); });
    // ★2026-08-26 사장님 "빨간 막대 두번 누르면 시작점되고 주황박스 만들어지는 거
    //   그거 왜 구현 안 되어 있나". 되어 있었는데 **오른쪽 클릭에만** 걸려 있었다
    //   (왼쪽 클릭은 stopPropagation만 하고 아무 일도 안 했다) — 아무도 안 쓰는
    //   조작이면 없는 기능이다. 왼쪽 클릭도 같은 markHere로 보낸다.
    //   끌어서 훑은 직후의 click은 뺀다(안 그러면 훑을 때마다 구간이 찍힌다).
    gripEl.addEventListener('click', e => {
      e.stopPropagation();
      if (gripMoved) { gripMoved = false; return; }
      markHere();
    });
    gripEl.addEventListener('contextmenu', e => { e.preventDefault(); e.stopPropagation(); markHere(); });

    host.querySelector('.frz').addEventListener('input', function () {
      const centerT = xToSec(winW() / 2);
      CW = +this.value;
      const ns = calcStep(CW);
      if (ns !== STEP) { strip().then(() => { off = clamp(centerT * pps() - winW() / 2); applyW(); }); }
      else { off = clamp(centerT * pps() - winW() / 2); applyW(); }
    });

    /* ▶ 빨간 막대를 [a,b] 구간 동안 움직인다(소리는 미리보기 창이 낸다).
       pv는 muted라 자동재생이 막히지 않는다. 브라우저가 그래도 거부하면
       **시계로** 막대를 움직인다 — 막대가 멈춰 보이는 것보다 낫다. */
    function stopHead(quiet) {
      const was = playing;
      if (was) {                                  // 어디서 멈췄는지 기억한다
        let t = null;
        try { t = (typeof opt.getTime === 'function') ? opt.getTime() : pv.currentTime; }
        catch (_) { t = null; }
        if (typeof t === 'number' && isFinite(t)) RESUME = t;
      }
      playing = false;
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      try { pv.pause(); } catch (_) {}
      // ★2026-08-26 사장님 "멈춤하면 미리보기도 멈춰야지 싱크 맞게".
      //   막대와 소리가 **한 번에** 서고 앉아야 한다 — 멈춤 신호도 재생과 같은 길로
      //   부모에게 넘긴다(부품은 부모를 모른다: 배선은 준 쪽이 한다).
      //   quiet=true는 다시 틀기 전 자기 정리라 부모에게 안 알린다(껐다 켜지 않게).
      if (was && !quiet && typeof opt.onStop === 'function') {
        try { opt.onStop(); } catch (_) {}
      }
    }
    function runHead(a, b) {
      stopHead(true);          // 다시 틀기 전 자기 정리 — 부모는 곧 새 구간을 받는다
      playing = true;
      const tick = (getT) => {
        const loop = () => {
          if (!playing || destroyed) return;
          const t = getT();
          if (t >= b - 0.02) { stopHead(); RESUME = null; moveHead(b); return; }
          moveHead(t);
          raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);
      };
      // ★막대가 미리보기보다 먼저 갔다(2026-08-26 사장님 "빨간막대기 재생보다 미리보기가
      //   약간 더 늦게 재생됨"). 필름 안 pv는 바로 도는데 큰 미리보기는 시크·디코드에
      //   시간이 걸린다 — **부모의 실제 시각을 읽어** 그걸 따라가면 어긋날 수가 없다.
      //   부모가 아직 그 구간에 못 왔으면 막대는 시작점에 머문다(앞서가지 않는다).
      if (typeof opt.getTime === 'function') {
        try { pv.currentTime = a; } catch (_) {}
        tick(() => {
          const t = opt.getTime();
          return (typeof t === 'number' && isFinite(t) && t >= a - 0.5) ? t : a;
        });
        return;
      }
      try { pv.currentTime = a; } catch (_) {}
      pv.play().then(() => tick(() => pv.currentTime)).catch(() => {
        // 자동재생 거부 — 시계로 간다(구간 길이만큼 균일하게).
        const t0 = performance.now();
        tick(() => a + (performance.now() - t0) / 1000);
      });
    }

    /* 스페이스 = 재생/멈춤 (이 롤러가 열려 있을 때만) */
    function onKey(e) {
      if (destroyed) return;
      if (ACTIVE && ACTIVE !== SELF) return;      // 지금 만지는 필름만 받는다
      const _tag = (e.target && e.target.tagName || '').toLowerCase();
      const _typing = _tag === 'input' || _tag === 'textarea' || (e.target && e.target.isContentEditable);
      // ★Esc = 구간 지우기(2026-08-26 사장님 "esc로 삭제되게"). 고른 게 있으면 그것,
      //   없으면 마지막에 만든 것. ×를 정확히 누르지 않아도 손이 닿는다.
      if (e.code === 'Escape' && !_typing) {
        if (!BOXES.length) return;
        const i = (ACTBOX != null && BOXES[ACTBOX]) ? ACTBOX : BOXES.length - 1;
        BOXES.splice(i, 1);
        ACTBOX = null; MA = null;
        drawBoxes(); drawMark(); drawBar();
        e.preventDefault();
        return;
      }
      if (e.code !== 'Space') return;
      const tag = (e.target && e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || (e.target && e.target.isContentEditable)) return;
      e.preventDefault();
      const bx = (ACTBOX != null && BOXES[ACTBOX]) ? BOXES[ACTBOX] : null;
      // ★미리보기 창으로 넘긴다 — 구간이 있으면 그 구간, 없으면 지금 위치부터
      if (typeof opt.onPlay === 'function'){
        // ★2026-08-26 3차 사장님 제보 "빨간막대가 안움직여 스페이스바".
        //   2차에서 재생을 큰 미리보기로 넘기며 여기서 그냥 return했다 — 필름 안 pv가
        //   안 도니 moveHead 루프가 **아예 시작을 안 했다**(그래서 막대가 멈춰 있었다).
        //   소리는 미리보기가, **위치 표시는 필름이** 맡는다: pv는 muted라 같이 돌려도
        //   소리가 겹치지 않는다. 같은 파일·같은 시작점이라 막대가 그림을 따라간다.
        if (playing) { stopHead(); return; }      // 두 번째 스페이스 = 멈춤
        // ★박스가 없으면 **빨간 막대가 있는 자리**에서 재생한다(2026-08-26 사장님
        //   "스페이스바를 누르면 저 위치로만 이동이 된다" — 쓰는 구간으로 점프하게
        //   고쳤더니 내가 놓은 자리를 무시했다. 그건 더 나빴다).
        //   길이는 3초 고정이 아니라 **쓰는 구간 길이만큼**(모르면 3초) — 그게 이 조각을
        //   판단하는 데 필요한 시간이다.
        // ★박스가 없으면 **그 자리부터 필름 끝까지** 돈다(2026-08-26 사장님 "이건 왜
        //   재생이 파란구간만 되나" 캡쳐 535). 종전엔 '쓰는 구간 길이'(없으면 3초)만큼만
        //   돌아서, 앞뒤를 이어 보려 해도 파란 구간 언저리에서 툭 끊겼다.
        //   멈추는 건 스페이스 한 번이면 된다 — 길이를 미리 재단할 이유가 없다.
        const s2 = bx ? bx.s : (pv.currentTime || 0);
        const b2 = bx ? bx.e : DUR;
        // 멈춘 자리가 이 구간 안이면 거기서 이어서(끝까지 봤으면 RESUME이 비어 처음부터).
        const a2 = (RESUME != null && RESUME > s2 + 0.05 && RESUME < b2 - 0.05) ? RESUME : s2;
        opt.onPlay(a2, b2);
        runHead(a2, b2);
        return;
      }
      if (playing) { pv.pause(); playing = false; if (raf) cancelAnimationFrame(raf); raf = 0; return; }
      const b = bx;
      if (b && (pv.currentTime < b.s - 0.05 || pv.currentTime >= b.e - 0.02)) pv.currentTime = b.s;
      pv.play().then(() => {
        playing = true;
        const loop = () => {
          if (!playing || destroyed) return;
          const t = pv.currentTime;
          if (b && t >= b.e - 0.02) { pv.pause(); playing = false; moveHead(b.e); return; }
          moveHead(t);
          raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);
      }).catch(() => {});
    }
    document.addEventListener('keydown', onKey);

    pv.src = opt.src;
    if (opt.from != null) { try { pv.currentTime = opt.from; } catch (_) {} }
    strip();

    return {
      destroy() {
        if (ACTIVE === SELF) ACTIVE = null;
        try { if (_shotVid) { _shotVid.src = ''; _shotVid = null; } } catch (_) {}
        // 접는데 소리만 계속 나는 일이 없게 — 재생 중이었으면 미리보기도 세운다.
        try { stopHead(); } catch (_) {}
        destroyed = true;
        document.removeEventListener('keydown', onKey);
        if (raf) cancelAnimationFrame(raf);
        try { pv.pause(); pv.removeAttribute('src'); pv.load(); } catch (_) {}
        host.innerHTML = '';
      },
      boxes: () => BOXES.map(b => ({ s: b.s, e: b.e })),
      // ★구절 길이를 밖에서 넣는다(F21) — 대사 구절을 누르면 그 초가 [+구간] 길이칸에
      //   들어간다. 길이를 정하는 곳은 여전히 BOXLEN 하나다(0순위-B: 새 경로를 만들지
      //   않고 사람이 손으로 치던 그 값을 대신 채운다).
      setBoxLen(sec) {
        const v = Math.max(0.1, +sec || 0);
        if (!v) return BOXLEN;
        BOXLEN = Math.round(v * 100) / 100;
        const el = host.querySelector('.frlen');
        if (el) el.value = BOXLEN;
        return BOXLEN;
      },
    };
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  global.filmroll = filmroll;
})(window);
