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
  const LADDER = [0.1, 0.2, 0.25, 0.5, 1, 2, 5];   // 확대 단계(오른쪽일수록 확대)
  const CH = 139;   // 칸 기본 높이(px). 훅 칸(78×16/9)과 같다 — CSS --fr-cell 기본값과 짝.
                    // ★끌어서 바꾸면 그 높이로 캔버스도 따라간다(안 그러면 그림이 눌린다).
  // ★기본 확대 = 한 칸 0.5초(2026-08-29 사장님 "처음 펼치기하면 기본 셋팅이 0.5로" —
  //   F21의 0.25 결정을 번복). 자동확대(_fitToRange)도 이보다 성기게는 못 간다 —
  //   기본값과 하한을 여기 한 곳에서만 정한다(0순위-B).
  const ZOOM_MAX_STEP = 0.5;

  // ★확대 슬라이더는 **한 칸 초(사다리 단계)**를 직접 고른다(2026-08-27 사장님
  //   "3단계가 0.25에서 조정이 안된다"). 종전엔 슬라이더가 칸 폭(px 26~240)이고
  //   초는 STEP=54/폭을 사다리에서 내림해 정했다 — 그러면 0.25초가 나오는 폭이
  //   109~216px, 즉 **트랙의 절반(108칸)**이라 손잡이를 한참 밀어도 숫자가 그대로였다.
  //   (아래 '영상 전체' 필름은 0.5초 구간이 54칸으로 좁아 잘 바뀌었다 — 같은 코드인데
  //    한쪽만 안 듣는 것처럼 보인 이유다.) 이제 한 칸 밀면 한 단계씩 확실히 바뀐다.
  //   칸 폭은 초에서 자동으로 나온다 — 폭과 초를 따로 두면 언젠가 어긋난다(0순위-B).
  const CW_MIN = 26, CW_MAX = 540;   // 칸 폭 한계 — 0.1초(540px)까지 실제로 벌어진다
  const SMAX = LADDER.length - 1;
  const stepFromSlider = v => LADDER[SMAX - Math.max(0, Math.min(SMAX, Math.round(+v)))];
  const sliderFromStep = s => {                 // 오른쪽으로 갈수록 확대(초가 작아진다)
    let bi = 0, bd = Infinity;
    LADDER.forEach((v, i) => { const d = Math.abs(v - s); if (d < bd) { bd = d; bi = i; } });
    return SMAX - bi;
  };
  const cwFor = s => Math.max(CW_MIN, Math.min(CW_MAX, Math.round(PPS_BASE / s)));

  const CACHE = {};                    // "vid|step|i" → dataURL (전 롤러 공용)


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
    let CW = cwFor(ZOOM_MAX_STEP), STEP = ZOOM_MAX_STEP, N = 0, off = 0;  // 기본 확대(위 상수)
    let _homed = false;      // 지금 쓰는 구간으로 한 번 옮겼나(처음 펼칠 때만)
    let MA = null;                     // 찍어둔 시작점
    let HEAD_T = 0;                    // 빨간선이 가리키는 시각(초) — moveHead가 갱신한다
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
    // ★길이 잠금 모드(2026-08-29 설계 ⑧ — "오렌지박스를 필름 위에 고정시켜놓고 마우스로만
    //   옮기면서 맞는 장면을 찾는다"). 바꿀 컷의 길이로 박스 하나가 처음부터 떠 있고,
    //   늘리고 줄이고 지우는 조작은 전부 잠긴다 — 옮기기와 🔁(교체)만 남는다.
    //   그래야 올리는 순간 초가 항상 딱 맞는다.
    const LOCK = +opt.lockLen > 0;
    if (LOCK) {
      const a = Math.max(0, +opt.lockFrom || 0);
      BOXES = [{ s: Math.round(a * 100) / 100,
                 e: Math.round((a + +opt.lockLen) * 100) / 100 }];
    }
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
          '<div class="frgrab" title="아래를 잡고 끌면 높이가 바뀝니다"></div>' +
          '<div class="frbar"></div>' +
          '<span class="frzoom">확대 ' +
            // ★버튼으로도 한 단계씩(2026-08-28 사장님 "마우스로 조절하는게 안된다").
            //   단계가 7개라 슬라이더를 넓혀도 끌기는 여전히 섬세한 조작이다 — 누르는 길을 같이 둔다.
            //   두 길 모두 아래 setStep() 하나를 부른다(0순위-B).
            '<button type="button" class="zb" data-z="-1" title="한 단계 축소">－</button>' +
            '<input type="range" class="frz" min="0" max="' + SMAX + '" step="1" value="' + sliderFromStep(ZOOM_MAX_STEP) + '">' +
            '<button type="button" class="zb" data-z="1" title="한 단계 확대">＋</button></span>' +
          '<span class="frstep"></span>' +
          '<button type="button" class="frclose" title="접기">◀ 접기</button>' +
        '</div>' +
        // ★위/아래 띠 = 다른 장면(칸)으로 넘어가기(2026-08-28 사장님 "빨간박스 위아래 2개는
        //   훅에서 다른 장면으로 넘어갈 수 있는 걸로"). 필름을 접고 다시 펴는 왕복 없이
        //   이 자리에서 앞뒤 칸을 훑는다. 부품은 어느 칸이 있는지 모른다 — 부모가 준
        //   onGoBeat(-1|+1)에 넘길 뿐이다(없으면 띠도 안 만든다).
        (typeof opt.onGoBeat === 'function'
          ? '<button type="button" class="frgo up" data-go="-1" title="앞 장면의 필름으로">▲ 앞 장면</button>' : '') +
        '<div class="frwin">' +
          '<div class="frload">🎞 필름 뽑는 중…</div>' +
          '<div class="frbelt"></div>' +
          '<div class="frcaps"></div>' +
          '<div class="fruse"></div>' +
          '<div class="frboxes"></div>' +
          '<div class="frmark"></div>' +
          // ★조작법을 손잡이에 적어둔다(2026-08-28) — 도움말 버튼이 따로 없어서
          //   우클릭 찍기가 있는 줄 모르고 쓰던 기능이다.
          '<div class="frhead"><span class="frgrip" title="끌어서 이동 · 우클릭 = 구간 찍기 · ' +
            'Q 시작 / W 끝 · 스페이스 재생"></span><span class="frdur"></span></div>' +
        '</div>' +
        (typeof opt.onGoBeat === 'function'
          ? '<button type="button" class="frgo down" data-go="1" title="다음 장면의 필름으로">▼ 다음 장면</button>' : '') +
        '<video class="frpv" muted playsinline preload="auto"></video>' +
        '<canvas class="frcv" style="display:none"></canvas>' +
      '</div>';

    // ★필름 안에서 난 클릭이 **바깥 칸으로 새지 않게** 한다(2026-08-28 사장님
    //   "확대조절을 하고 마우스를 놓으면 미리보기가 자동으로 재생됨").
    //   필름은 칸(.tbeat) 안에 들어가는데 그 칸에는 onclick="selBeat();playBeatHere()"가
    //   걸려 있다 — 확대 슬라이더를 놓는 click이 칸까지 올라가 재생이 시작됐다.
    //   ★막는 곳은 여기 하나다(0순위-B). 부품마다 stopPropagation을 붙이면 새 버튼을
    //     만들 때마다 빠뜨리고, 그때마다 같은 증상이 다시 난다.
    //   버블 단계에서 막으므로 필름 **안쪽** 동작(빨간선·박스·버튼)은 그대로 돈다.
    host.addEventListener('click', ev => ev.stopPropagation());
    host.addEventListener('dblclick', ev => ev.stopPropagation());

    const $ = s => host.querySelector(s);
    const win = $('.frwin'), belt = $('.frbelt'), pv = $('.frpv'), cv = $('.frcv');
    const headEl = $('.frhead'), gripEl = $('.frgrip'), durEl = $('.frdur');
    const markEl = $('.frmark'), boxesEl = $('.frboxes'), capsEl = $('.frcaps');
    const useEl = $('.fruse'), barEl = $('.frbar'), loadEl = $('.frload');

    host.querySelectorAll('.frgo').forEach(b => {
      b.addEventListener('click', e => {
        e.preventDefault(); e.stopPropagation();
        opt.onGoBeat(+b.dataset.go);
      });
    });

    $('.frname').textContent = opt.name || '';
    $('.frclose').onclick = () => { if (opt.onClose) opt.onClose(); };

    const winW = () => win.clientWidth || 600;
    const pps = () => CW / STEP;
    const maxOff = () => Math.max(0, DUR * pps() - winW());
    const clamp = v => Math.max(0, Math.min(maxOff(), v));
    const secToX = t => t * pps() - off;
    const xToSec = x => (x + off) / pps();

    /* 지금 칸 높이(px) — 높이가 바뀌면 그림도 다시 뽑아야 하므로 캐시키에 넣는다 */
    const cellNow = () => {
      const box = host.querySelector('.fr');
      const v = box && parseFloat(getComputedStyle(box).getPropertyValue('--fr-cell'));
      return (v && isFinite(v)) ? v : CH;
    };
    /* ★캐시키를 만드는 곳은 여기 하나뿐이다(뽑는 곳·읽는 곳이 어긋나면 통째로 불발된다) */
    const ckey = (st, i, ch) => vid + '|' + st + '|' + Math.round(ch != null ? ch : cellNow()) + '|' + i;

    /* 그 시각의 썸네일 — 저장 키를 아는 유일한 곳(캐시키 불일치 방지) */
    function thumbAt(sec) {
      const i = Math.floor(sec / STEP);
      const hit = CACHE[ckey(STEP, i)];
      if (hit) return hit;
      let best = '', bd = 1e9;
      for (const k in CACHE) {
        const p = k.split('|');
        if (p[0] !== vid) continue;
        const st = parseFloat(p[1]), idx = parseInt(p[3] !== undefined ? p[3] : p[2], 10);
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
      // ★손으로 옮긴 자리가 곧 다음 재생 지점이다(2026-08-28 사장님 제보: "한 번 재생
      //   후 다른 지점 클릭하고 재생하면 빨간선부터 안 되고 엉뚱한 곳에서 재생된다").
      //   RESUME(마지막 멈춘 자리)이 남아 있으면 아래 재생이 그걸 우선해, 방금 옮긴
      //   빨간선을 무시하고 옛 자리에서 이어 갔다. 사용자가 직접 옮겼으면 그게 이긴다.
      RESUME = scrubWant;
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
      // ★빨간선이 **지금 가리키는 시각**을 여기 한 곳에서 기록한다(2026-08-28 사장님
      //   "한 칸 1초에선 정확한데 확대가 바뀌면 Q/W가 다른 곳에 찍힌다").
      //   종전엔 Q/W가 pv.currentTime(영상 요소의 실제 시각)을 읽었는데, seek는
      //   **비동기**라 방금 옮긴 자리가 아직 반영되기 전이다. 확대를 바꾸면 필름을
      //   다시 뽑느라 그 지연이 커져 옛 시각이 찍혔다.
      //   막대를 옮기는 길은 전부 moveHead를 지나므로 여기가 유일한 기록 지점이다(0순위-B).
      HEAD_T = Math.round((+t || 0) * 100) / 100;
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
        // ★자막이 실제로 끝나는 시각을 쓴다(2026-08-29 사장님 "장면 자막이 안 맞음").
        //   종전엔 끝을 **다음 자막 시작**으로 지어냈다 — 말과 말 사이 공백이 앞 자막에
        //   통째로 먹혀 자막띠가 그림보다 길게 깔렸다(실측 2.3~3.0초씩 초과).
        //   c[2]=end가 오면 그걸 쓰고, 없으면(옛 2칸 caps) 종전대로 — 다음 시작을 넘진 않게.
        const st = c[0];
        const nxt = (i + 1 < caps.length) ? caps[i + 1][0] : DUR;
        const en = (c.length > 2 && isFinite(c[2]) && c[2] > st) ? Math.min(c[2], nxt) : nxt;
        const w = (en - st) * pps() - 1;
        if (w < 8) return '';
        return `<span class="cp" style="left:${st * pps()}px;width:${w}px">${esc(c[1])}</span>`;
      }).join('');
    }

    function drawBoxes() {
      // ★자식 좌표는 **절대(t×pps)**다 — frboxes 층 자체가 applyW에서 translateX(-off)로
      //   밀리므로, 여기서 secToX(off를 또 빼는 함수)를 쓰면 off가 **이중 차감**돼
      //   박스만 왼쪽으로 스크롤량만큼 밀린다(2026-08-29 사장님 "1초 빼고 다 안 찍힌다"
      //   — 실측: 어긋난 거리가 각 단계에서 정확히 off와 일치. 1·2·5초는 필름이 창보다
      //   좁아 off=0이라 안 드러났을 뿐). caps·use 층과 같은 규약: 층은 translate, 자식은 절대.
      boxesEl.style.width = (DUR * pps()) + 'px';
      boxesEl.innerHTML = BOXES.map((b, i) =>
        `<div class="bx${ACTBOX === i ? ' act' : ''}${LOCK ? ' lock' : ''}" data-i="${i}" ` +
        `style="left:${b.s * pps()}px;width:${Math.max(8, (b.e - b.s) * pps())}px">` +
        `<span class="t">${(b.e - b.s).toFixed(2)}초${LOCK ? ' 🔒' : ''}</span>` +
        // ★키 안내(2026-08-28 사장님 "시작Q 종료W 담기E 이렇게 써줘").
        //   기능은 이미 있었지만 화면에 없으니 아무도 몰랐다 — 없는 기능과 같다.
        //   잠금 모드에선 만들기·지우기 키가 다 잠기므로 안내도 옮기기 안내로 바뀐다.
        (LOCK
          ? `<span class="k">길이 고정 — 끌어서 맞는 장면 위에 놓고 <b>🔁 교체</b></span>`
          : `<span class="k">시작 <b>Q</b> · 종료 <b>W</b> · 담기 <b>E</b></span>` +
            `<span class="e l" data-edge="l"></span><span class="e r" data-edge="r"></span>` +
            `<span class="x" data-del="${i}">×</span>`) +
        // ★2026-08-26 사장님 "주황색 박스 만들면 위쪽 훅 있는 윗칸으로 더블클릭이나
        //   드래그로 옮기기". 박스 본체는 pointerdown에서 preventDefault를 하므로
        //   HTML5 dragstart가 안 뜬다(이동·양끝조절이 그 위에 서 있다) — 그래서
        //   **끌기 전용 손잡이**를 따로 둔다. 부품은 어디로 가는지 모른다: 부모가
        //   준 onBoxDrag에 넘길 뿐이다.
        (!LOCK && typeof opt.onBoxDrag === 'function'
          ? `<span class="g" draggable="true" data-g="${i}" title="누르면 바로 위 칸에 담깁니다 (끌어다 놓아도 됩니다)">⬆ 위로 담기</span>` : '') +
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
          mode = LOCK ? 'move' : (ev.target.dataset.edge || 'move');   // 잠금 = 옮기기만
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
          el.style.left = (b.s * pps()) + 'px';   // 절대좌표 — drawBoxes와 같은 규약
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
          // ★눌러도 담긴다(2026-08-28 사장님 "더블클릭이나 마우스로 잡고 훅쪽으로").
          //   박스 두 번 누르기는 **실제 마우스에서 안 잡힌다**(라이브 실측: 박스 위를
          //   정확히 두 번 눌러도 pointerdown이 오지 않아 담기지 않았다 — 위 LASTTAP
          //   주석의 함정이 아직 살아 있다). 끌기 하나만 남기면 손이 떨리는 날엔 아예 못 담는다.
          //   그래서 **누르기**를 정식 길로 둔다 — 담는 함수는 두 번 누르기와 같은
          //   onBoxCommit 하나다(0순위-B: 담는 규칙을 두 벌로 두지 않는다).
          g.addEventListener('click', ev => {
            ev.stopPropagation(); ev.preventDefault();
            const b = BOXES[+el.dataset.i]; if (!b) return;
            if (typeof opt.onBoxCommit === 'function') opt.onBoxCommit({ s: b.s, e: b.e });
          });
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

    /* Q = 시작 찍기 · W = 끝 찍기 (2026-08-28 사장님 "단축키는 시작=Q 끝=W").
       markHere(우클릭)는 한 번에 시작·끝을 번갈아 찍는 토글이라, 어느 쪽을 찍는
       중인지 헷갈릴 때가 있다. Q/W는 **무엇을 찍는지 손가락이 정한다**.
       ★박스를 만드는 규칙은 addBox 하나뿐이다 — 여기서 BOXES를 직접 건드리면
         정렬·중복·최소길이 규칙이 두 벌이 된다(0순위-B). */
    function headTime() {
      // ★**화면에 보이는 그 자리**가 곧 시각이다(2026-08-28 실측).
      //   HEAD_T만 믿었더니 0.2초 단계에서 W(종료)가 2.57초로 튀었다 —
      //   빨간선은 700px(=0.80초)에 멀쩡히 서 있고 영상도 0.80초에 멈춰 있는데,
      //   내부 값만 재생 tick 같은 다른 경로에 밀려 있었다.
      //   찍히는 자리는 사장님이 보는 자리여야 한다. 그래서 막대의 실제 위치에서
      //   되돌려 계산하고, 막대가 안 보일 때만 HEAD_T로 물러난다.
      if (headEl && headEl.classList.contains('on')) {
        const x = parseFloat(headEl.style.left);
        if (isFinite(x)) return Math.round(xToSec(x) * 100) / 100;
      }
      return HEAD_T;
    }
    function markStart() {
      MA = headTime();
      drawMark(); drawBar(); moveHead(MA);
    }
    function markEnd() {
      const t = headTime();
      if (MA === null) {            // 시작을 안 찍었으면 여기를 시작으로 삼는다
        MA = t; drawMark(); drawBar(); moveHead(t); return;
      }
      const a = Math.min(MA, t), b = Math.max(MA, t);
      if (b - a < 0.15) { MA = null; drawMark(); drawBar(); moveHead(t); return; }
      addBox(a, b); moveHead(t);
    }

    /* 손잡이 우클릭 = 여기 찍기(시작 → 끝) */
    function markHere() {
      const t = headTime();
      if (MA === null) { MA = t; drawMark(); drawBar(); moveHead(t); return; }
      const a = Math.min(MA, t), b = Math.max(MA, t);
      if (b - a < 0.15) { MA = null; drawMark(); drawBar(); moveHead(t); return; }
      addBox(a, b); moveHead(t);
    }

    function makeBox() {
      if (LOCK) return;                       // 길이 잠금 — 새 박스 금지
      const el = host.querySelector('.frlen');
      if (el) BOXLEN = Math.max(0.1, parseFloat(el.value) || BOXLEN);
      const n = BOXLEN;
      // ★빨간선이 화면 밖이면 **보이는 왼쪽 끝**에 만든다(2026-08-29). 조각 필름은
      //   펼치면 그 조각 자리로 스크롤돼 있는데 HEAD_T 초기값은 0이라, 그대로 만들면
      //   박스가 화면 밖(0초)에 생겨 "＋구간이 안 된다"로 보였다.
      //   화면에 생겨야 기능이 있는 것이다 — 박스 규칙 자체는 addBox 하나 그대로다.
      const base = (headEl && headEl.classList.contains('on')) ? headTime() : xToSec(8);
      const a = Math.max(0, Math.min(DUR - 0.1, base));
      addBox(a, Math.min(DUR, a + n));
    }

    /* ✂ 지금 쓰는 구간을 그대로 주황 박스로 올린다(2026-08-29 사장님 "훅쪽 짧은 카드를
       펼치고 끝에 다른 장면으로 이어지는 남는 부분을 잘라내려고").
       꼬리를 자르려면 쓰는 구간이 손에 잡혀야 한다 — 박스로 올린 뒤 끝을 당기고
       🔁(이 조각을 이 구간으로)로 확정하면 된다. 펼칠 때 미리 올리진 않는다
       (08-29 "노란박스 아예없이" 결정 유지) — **누를 때만** 만든다.
       박스를 만드는 규칙은 addBox 하나다(0순위-B). */
    function useToBox() {
      if (opt.from == null || opt.to == null) return;
      const s = Math.round(Math.max(0, +opt.from) * 100) / 100;
      const e = Math.round(Math.min(DUR || +opt.to, +opt.to) * 100) / 100;
      if (!(e - s >= 0.1)) return;
      const same = b => Math.abs(b.s - s) < 0.01 && Math.abs(b.e - e) < 0.01;
      if (!BOXES.some(same)) addBox(s, e);          // 이미 있으면 또 안 만든다
      ACTBOX = BOXES.findIndex(same);
      drawBoxes(); drawBar();
    }

    function drawBar() {
      const total = BOXES.reduce((a, b) => a + (b.e - b.s), 0);
      // ★길이 잠금(⑧) — 만들기·담기·비우기 없이 [▶듣기]와 [🔁 교체]만.
      //   영상을 갈아 끼워도 이 줄 모양이 그대로라 "박스가 고정돼 있다"가 화면에서 읽힌다.
      if (LOCK) {
        barEl.innerHTML =
          `<span class="frhint">🔒 ${(+opt.lockLen).toFixed(2)}초 고정 — 박스를 끌어 맞는 장면 위에 놓으세요</span>` +
          `<button type="button" class="frbtn" data-act="play">▶ 미리보기에서 듣기</button>` +
          (typeof opt.onReplace === 'function'
            ? `<button type="button" class="frbtn rep">🔁 이 장면으로 교체</button>` : '');
        const rep2 = barEl.querySelector('.rep');
        if (rep2) rep2.onclick = () => {
          if (BOXES.length === 1 && typeof opt.onReplace === 'function')
            opt.onReplace({ s: BOXES[0].s, e: BOXES[0].e });
        };
        const pl2 = barEl.querySelector('[data-act="play"]');
        if (pl2) pl2.onclick = () => {
          const b = BOXES[0];
          if (b && typeof opt.onPlay === 'function') opt.onPlay(b.s, b.e);
        };
        return;
      }
      barEl.innerHTML =
        (MA !== null
          ? `<span class="frhint">시작 <b>${MA.toFixed(2)}초</b> — 빨간선을 옮기고 <b>W</b>(또는 손잡이 클릭)</span>`
          // ★상시 안내문은 뺐다(2026-08-26 사장님 캡쳐 532) — 한 줄을 통째로 먹으면서
          //   그만큼 필름이 낮아졌다. 조작법은 오른쪽 위 [?] 도움말에 있다.
          //   '시작 N초' 같은 **작업 중 상태**는 그대로 남긴다(그건 지금 뭘 하는지다).
          : '') +
        `<span class="frmk"><button type="button" class="frbtn mk">＋ 구간</button>` +
        `<input type="number" class="frlen" step="0.1" min="0.1" value="${BOXLEN}"><span class="frhint">초</span></span>` +
        // ✂ 조각 하나를 펼친 필름에만 나온다(쓰는 구간 + 바꿀 대상이 있어야 하므로
        //   from/to·onReplace 둘 다 필요 — 영상 통째 필름엔 안 나온다).
        (opt.from != null && opt.to != null && typeof opt.onReplace === 'function'
          ? `<button type="button" class="frbtn use" title="지금 쓰는 구간을 주황 박스로 올립니다 — 끝을 당겨 자르고 🔁로 확정">✂ 쓰는 구간 다듬기</button>` : '') +
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
      const use = barEl.querySelector('.use'); if (use) use.onclick = useToBox;
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

    /* ★끌기 전용 경량 경로(2026-08-29 사장님 "앞으로 땡기면 이동이 안 되고 놓는 순간
       움직인다"). 원인은 applyW가 매 mousemove마다 자막·구간띠를 innerHTML로 통째
       재구성해 메인스레드가 막히는 것 — 브라우저가 그릴 틈이 없어 놓는 순간에야
       한꺼번에 그려졌다(합성 이벤트 실측으론 off가 매 이동 갱신됨 = 로직은 정상,
       페인트가 굶은 것). 끌 때 바뀌는 건 off 하나 — 층들의 transform만 밀면 된다.
       (모든 자식은 절대좌표 규약이라 transform만으로 정확히 따라온다) */
    function panW() {
      off = clamp(off);
      belt.style.transform = `translateX(${-off}px)`;
      boxesEl.style.transform = `translateX(${-off}px)`;
      capsEl.style.transform = `translateX(${-off}px)`;
      useEl.style.transform = `translateX(${-off}px)`;
      drawMark();                    // left 한 줄 — 재구성 아님
      moveHead(HEAD_T);
      clearTimeout(applyW._fill);
      applyW._fill = setTimeout(() => { fillVisible(); }, 60);
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
      // ★빨간선은 **자기 시각 그대로** 다시 그린다(2026-08-28 사장님 "0.5·0.2는 안 된다").
      //   종전엔 pv.currentTime을 넣었는데, applyW는 확대·스크롤마다 불리므로
      //   그때마다 HEAD_T가 **영상 요소의 실제 시각**으로 덮어써졌다.
      //   seek는 비동기고 키프레임으로 스냅되므로 내가 찍은 자리와 다르다 —
      //   실측(0.2초 단계): 0.30초 간격으로 Q/W를 찍었는데 1.75초짜리 박스가 생겼다.
      //   재생 중에는 tick이 moveHead(t)를 계속 불러 최신 위치가 들어온다.
      moveHead(HEAD_T);
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
      CW = cwFor(STEP);          // ★초가 주인, 칸 폭은 거기서 나온다(한 곳에서만 정한다)
      N = Math.max(1, Math.ceil(DUR / STEP));
      host.querySelector('.frstep').textContent = `한 칸 ${STEP}초`;
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
      // ★실제 칸 높이로 뽑는다 — 고정값을 쓰면 늘렸을 때 그림이 세로로 눌린다
      const cellH = cellNow();
      cv.width = Math.max(24, Math.round(w * 2)); cv.height = Math.max(40, Math.round(cellH * 2));
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
        const key = ckey(STEP, i, cellH);
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
      if (!_homed && LOCK) {
        // ★잠금 박스는 열리자마자 **화면 가운데**(2026-08-29 사장님 "옆으로 이동해서
        //   찾아야 한다") — 박스를 찾으러 스크롤하게 두지 않는다.
        _homed = true;
        const _c = (Math.max(0, +opt.lockFrom || 0) + (+opt.lockLen || 0) / 2);
        setTimeout(() => { off = clamp(_c * pps() - winW() / 2); applyW(); }, 0);
      }
      else if (!_homed && opt.from != null) {
        _homed = true;
        // ★배율은 **레이아웃이 잡힌 뒤** 정한다. 여기서 바로 재면 win.clientWidth가 아직
        //   0이라 winW()가 600 폴백을 쓰고, 그 폭 기준으로 엉뚱한 배율이 나온다
        //   (실측 2026-08-26: 2.4초 구간인데 창의 32%밖에 안 찼다).
        // ★async 함수의 예외는 try/catch로 안 잡힌다(Promise rejection이 된다).
        //   그래서 여기가 실패해도 화면만 이상하고 아무 흔적이 없었다 — 실제로
        //   2026-08-28에 '왜 안 도는지' 찾는 데 한참 걸렸다. 반드시 남긴다.
        // ★requestAnimationFrame에 맡기면 **안 돌 때가 있다**(2026-08-28 실측:
        //   iframe 문서가 visibilityState='hidden'이면 rAF 콜백이 아예 실행되지 않는다.
        //   탭이 뒤에 있거나 브라우저가 절전으로 판단하면 그 상태가 된다).
        //   그래서 자동확대가 통째로 안 걸렸다 — 예외도 없이 조용히.
        //   setTimeout은 숨은 문서에서도 돈다(느려질 뿐). 레이아웃이 잡혔는지는
        //   **창 폭이 잡혔는가**로 직접 확인한다(rAF의 원래 목적이 그것이었다).
        let _fitTry = 0;
        const _runFit = () => {
          if (destroyed) return;
          if ((win.clientWidth || 0) < 50 && _fitTry++ < 40) { setTimeout(_runFit, 50); return; }
          Promise.resolve().then(_fitToRange)
            .catch(e => console.error('[filmroll] 자동확대(_fitToRange) 실패', e));
        };
        setTimeout(_runFit, 0);
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
          // ★조각을 펼치면 **그 길이만큼만** 옆으로 늘어난다(2026-08-28 사장님
          //   "2.3초면 저 연두색 부분 정도만 늘어날 거잖아").
          //
          //   ⚠️앞서 두 번 실패했다. 되풀이하지 마라:
          //     ① win.style.width를 직접 잡았다 → 보이는 칸 계산(fillVisible)이 레이아웃보다
          //        먼저 돌아 **칸이 빈 검은색**으로 남았다.
          //     ② clamp를 조각 구간으로 묶었다 → 주황 박스는 원본 시각으로 그려지므로
          //        **볼 수 없는 자리**에 생겼다.
          //   그래서 여기서는 **슬롯의 최대 폭만** 정하고(레이아웃은 브라우저가 잡는다),
          //   폭이 반영된 **다음 프레임에** 다시 채운다. 스크롤 범위는 건드리지 않는다.
          // ★칸 폭은 **읽을 만한 크기로 고정**한다. 그래야 필름이 조각 길이에 비례해
          //   좁게/넓게 늘어난다(2026-08-28 사장님 "2.3초면 저 연두색 부분 정도만").
          //   종전처럼 '조각이 창을 채우도록' 칸 폭을 키우면 0.8초짜리도 화면을 가로지른다.
          // ★칸 폭은 **세로 영상 비율(9:16)**로 잡는다(2026-08-29 사장님 "저렇게 하려고
          //   한 거였어?" — 46px 고정이라 칸이 홀쭉한 띠가 돼 뭐가 뭔지 안 보였다).
          //   칸 높이는 그대로인데 폭만 줄이면 그림이 세로로 눌린다. 높이에서 폭을 낸다.
          const FIT_CELL = Math.max(40, Math.round(cellNow() * 9 / 16));
          const room = winW();
          let want = ZOOM_MAX_STEP;                       // 한 칸 초는 0.25 기본을 지킨다(F21)
          for (const st of LADDER) {
            if (st < ZOOM_MAX_STEP) continue;             // 기본보다 촘촘하게는 안 간다
            want = st;
            if ((span / st) * FIT_CELL <= room) break;    // 남는 폭 안에 들어오면 그만
          }
          const wantCW = FIT_CELL;
          const restrip = (want !== STEP);
          STEP = want; CW = wantCW;
          z.value = sliderFromStep(STEP);
          if (restrip) await strip();
          // 슬롯이 조각 길이만큼만 차지하게 한다 — 폭 자체를 박지 않고 **상한**만 준다.
          host.style.maxWidth = Math.ceil(span * pps() + 4) + 'px';
          requestAnimationFrame(() => { applyW(); fillVisible(); });   // 폭이 반영된 뒤 채운다
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
    let _shotVid = null, _filling = false, _fillWant = false;
    async function fillVisible() {
      // ★도는 중에 온 요청을 **기억한다**(2026-08-29 사장님 "칸이 검게 빈다").
      //   칸마다 영상을 seek해 캡처하므로 한 번 도는 데 오래 걸린다. 그 사이
      //   자동확대가 폭·스크롤을 바꿔 다시 채워달라고 불러도 여기서 그냥 return했고,
      //   앞의 것이 끝난 뒤엔 아무도 다시 부르지 않아 **보이는 칸이 영영 빈 채** 남았다
      //   (실측: 보이는 칸 6개 중 그림 0개, 채워진 11개는 전부 맨 앞 0~1초 자리).
      if (_filling) { _fillWant = true; return; }
      if (destroyed || !_shotVid) return;
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
          const key = ckey(STEP, i);
          let d = CACHE[key];
          if (!d) {
            await seekRaw(_shotVid, t);
            if (destroyed || my !== _stripSeq) break;
            try { x.drawImage(_shotVid, 0, 0, cv.width, cv.height); d = cv.toDataURL('image/jpeg', 0.6); CACHE[key] = d; }
            catch (_) { d = ''; }
          }
          if (d) c.insertAdjacentHTML('afterbegin', `<img src="${d}">`);
        }
      } finally {
        _filling = false;
        // 도는 동안 화면이 바뀌었으면 그 자리를 다시 채운다(놓친 요청을 갚는다).
        if (_fillWant && !destroyed) { _fillWant = false; setTimeout(fillVisible, 0); }
      }
    }

    host.addEventListener('pointerdown', () => { ACTIVE = SELF; }, true);
    host.addEventListener('mouseenter', () => { ACTIVE = SELF; });

    /* ★아래를 잡고 끌어 높이 조절(2026-08-27 사장님).
       높이는 CSS 변수 --fr-cell 한 곳만 바꾼다 — 창·벨트·칸·박스·자막띠가 따라온다. */
    const MIN_H = 60, MAX_H = 420;
    (function(){
      const g = host.querySelector('.frgrab'); if (!g) return;
      const box = host.querySelector('.fr');
      let dragging = false, sy = 0, h0 = 0;
      g.addEventListener('pointerdown', e => {
        dragging = true; sy = e.clientY; h0 = cellNow();
        g.classList.add('on');
        try { g.setPointerCapture(e.pointerId); } catch(_){}
        e.preventDefault(); e.stopPropagation();
      });
      g.addEventListener('pointermove', e => {
        if (!dragging) return;
        const h = Math.max(MIN_H, Math.min(MAX_H, h0 + (e.clientY - sy)));
        box.style.setProperty('--fr-cell', h + 'px');
        e.stopPropagation();
      });
      const end = e => {
        if (!dragging) return;
        dragging = false; g.classList.remove('on');
        try { localStorage.setItem('frCellH', cellNow()); } catch(_){}   // 다음에도 그 높이로
        strip().then(() => applyW());        // 높이가 바뀌었으니 그 비율로 다시 뽑는다
        e.stopPropagation();
      };
      g.addEventListener('pointerup', end);
      g.addEventListener('pointercancel', end);
      // 지난번 높이 복원
      try {
        const saved = parseFloat(localStorage.getItem('frCellH'));
        if (saved >= MIN_H && saved <= MAX_H) box.style.setProperty('--fr-cell', saved + 'px');
      } catch(_){}
    })();

    /* ── 마우스 배선 ───────────────────────────────────────── */
    // ★상태 선언을 배선보다 먼저 — 아래 핸들러들이 참조한다(TDZ 예방)
    let down = false, sx = 0, so = 0, dragged = false, dg = false;
    win.addEventListener('contextmenu', e => e.preventDefault());
    // ★가운데를 잡고 앞뒤로 밀기(2026-08-28 사장님 "가운데 부분은 마우스를 잡고
    //   필름을 뒤쪽 앞쪽으로 넘길수있게"). 2026-08-26에 뺐던 조작인데, 그때 문제는
    //   '밀기'와 '빨간선 찍기'가 **같은 왼쪽 버튼에서 구분 없이** 싸운 것이었다.
    //   이제 움직인 거리로 가른다: 4px 넘게 끌면 밀기, 그 자리에서 놓으면 찍기.
    //   (손잡이 gripEl이 이미 쓰는 판정과 같은 방식이다 — 판단 기준을 새로 만들지 않는다)
    win.addEventListener('pointerdown', e => {
      if (e.button !== 0 || e.target.closest('.bx')) return;
      down = true; sx = e.clientX; so = off; dragged = false;
      win.style.cursor = 'grabbing';
      try { win.setPointerCapture(e.pointerId); } catch (_) {}
    });
    win.addEventListener('pointermove', e => {
      if (!down) return;
      const dx = e.clientX - sx;
      if (!dragged && Math.abs(dx) > 4) dragged = true;   // 여기부터는 '밀기'다
      if (dragged) { off = clamp(so - dx); panW(); }   // 끌기 중엔 경량 경로(위 주석)
    });
    const _endPan = e => {
      if (!down) return;
      down = false; win.style.cursor = '';
      try { win.releasePointerCapture(e.pointerId); } catch (_) {}
      if (dragged) { setTimeout(() => { dragged = false; }, 0); return; }  // 끌었으면 찍지 않는다
      // 안 끌었다 = 그 자리를 찍는다(종전 동작 그대로)
      const r = win.getBoundingClientRect();
      const tt = Math.max(0, Math.min(DUR, xToSec(e.clientX - r.left)));
      pv.pause(); playing = false;
      scrubTo(tt);
    };
    win.addEventListener('pointerup', _endPan);
    win.addEventListener('pointercancel', e => { down = false; dragged = false; win.style.cursor = ''; });
    win.addEventListener('click', e => {
      // 위 pointerup이 이미 처리했다. click은 밖으로 새지 않게만 막는다.
      e.stopPropagation();
    });
    win.addEventListener('wheel', e => {
      e.preventDefault();
      // ★Ctrl+휠 = 확대/축소(2026-08-26 사장님). 슬라이더까지 손을 옮기지 않고 그 자리에서
      //   들여다본다. 확대는 **가리키는 지점을 축으로** 한다 — 안 그러면 보던 데를 놓친다.
      if (e.ctrlKey || e.metaKey) {
        const r = win.getBoundingClientRect();
        const anchorT = xToSec(e.clientX - r.left);          // 마우스가 가리키던 시각
        const z = host.querySelector('.frz');
        // 휠 한 번 = 사다리 한 단계(슬라이더 한 칸과 같은 길 — 두 벌로 두지 않는다).
        const nv = Math.max(0, Math.min(SMAX, (+z.value || 0) + (e.deltaY > 0 ? -1 : 1)));
        const ns = stepFromSlider(nv);
        if (ns === STEP) return;
        z.value = nv; STEP = ns; CW = cwFor(STEP);
        const keep = () => { off = clamp(anchorT * pps() - (e.clientX - r.left)); applyW(); };
        keep();                      // 다시 뽑기 **전에** 자리부터 잡는다(위 setStep과 같은 이유)
        strip().then(keep);
        return;
      }
      off = clamp(off + ((e.deltaY || e.deltaX) > 0 ? pps() * 2 : -pps() * 2)); panW();
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
    // ★한 손 제스처(2026-08-29 사장님): 빨간선을 왼쪽으로 잡고 끌다가 **오른쪽 버튼을
    //   겹쳐 누르면** 잡은 지점~지금 지점이 주황 박스가 된다(Q→W를 마우스 하나로).
    //   겹친 버튼은 pointerdown이 아니라 **buttons 비트가 바뀐 pointermove**로 온다
    //   (포인터 이벤트 규약 — chorded buttons). 우클릭 한 번 = 박스 하나(dgBoxed).
    let dgT0 = null, dgBoxed = false;
    gripEl.addEventListener('pointerdown', e => {
      dg = true; gripMoved = false; gripX = e.clientX;
      dgT0 = headTime(); dgBoxed = false;        // 잡은 순간의 시각 = 박스 시작점
      e.stopPropagation(); e.preventDefault();
      try { gripEl.setPointerCapture(e.pointerId); } catch (_) {}
    });
    gripEl.addEventListener('pointermove', e => {
      if (!dg) return;
      if (Math.abs(e.clientX - gripX) > 4) gripMoved = true;
      const r = win.getBoundingClientRect();
      scrubTo(xToSec(e.clientX - r.left));
      if ((e.buttons & 2) && !dgBoxed && dgT0 != null && !LOCK) {
        dgBoxed = true;                          // 우클릭이 눌려 있는 동안 한 번만
        gripEl._chordAt = performance.now();     // 곧 올 contextmenu(찍기)를 무시하기 위해
        const t1 = headTime();
        if (addBox(Math.min(dgT0, t1), Math.max(dgT0, t1)))
          dgT0 = t1;                             // 이어서 끌면 다음 박스는 여기부터
      }
      if (!(e.buttons & 2)) dgBoxed = false;     // 우클릭을 뗐다 — 다음 겹침을 받는다
      e.stopPropagation();
    });
    gripEl.addEventListener('pointerup', e => { dg = false; dgT0 = null; e.stopPropagation(); });
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
    gripEl.addEventListener('contextmenu', e => {
      e.preventDefault(); e.stopPropagation();
      // 끌기+우클릭(위 겹침 박스)의 우클릭 뗌이 여기로도 온다 — 그때 찍기까지 하면
      // 박스 만들자마자 새 시작점이 찍혀 헷갈린다. 겹침 직후엔 조용히 넘어간다.
      if (gripEl._chordAt && performance.now() - gripEl._chordAt < 600) return;
      markHere();
    });

    // ★확대를 바꾸는 곳은 여기 하나다(슬라이더·＋－버튼·Ctrl+휠이 모두 이걸 부른다).
    function setStep(sliderVal) {
      const z = host.querySelector('.frz');
      const v = Math.max(0, Math.min(SMAX, Math.round(+sliderVal)));
      const ns = stepFromSlider(v);
      if (ns === STEP) { z.value = v; return; }
      const centerT = xToSec(winW() / 2);                  // 보던 자리를 지킨다
      z.value = v; STEP = ns; CW = cwFor(STEP);
      // ★스크롤 위치를 **다시 뽑기 전에** 정한다(2026-08-28 실측).
      //   종전엔 strip().then 안에서 정했는데, 0.2초처럼 칸이 많은 단계는 다시 뽑는 데
      //   시간이 걸린다. 그 사이에 찍으면 off가 아직 옛 값이라 좌표가 통째로 어긋났다
      //   (실측: 길이는 0.30초로 정확한데 위치만 380px÷1350=0.28초 앞으로 밀렸다).
      //   off는 숫자일 뿐이라 칸이 아직 없어도 먼저 정할 수 있다.
      off = clamp(centerT * pps() - winW() / 2);
      strip().then(() => { off = clamp(centerT * pps() - winW() / 2); applyW(); });
    }
    host.querySelector('.frz').addEventListener('input', function () { setStep(this.value); });
    host.querySelectorAll('.zb').forEach(b => {
      b.addEventListener('click', e => {
        e.preventDefault(); e.stopPropagation();
        const z = host.querySelector('.frz');
        setStep((+z.value || 0) + (+b.dataset.z));
      });
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
        if (LOCK) return;                     // 길이 잠금 — 지우기 금지
        if (!BOXES.length) return;
        const i = (ACTBOX != null && BOXES[ACTBOX]) ? ACTBOX : BOXES.length - 1;
        BOXES.splice(i, 1);
        ACTBOX = null; MA = null;
        drawBoxes(); drawMark(); drawBar();
        e.preventDefault();
        return;
      }
      // ★Q/W = 주황 박스 만들기(2026-08-28 사장님). Space(재생)와 같은 자리에서 처리해
      //   '지금 만지는 필름만 받는다'(ACTIVE)와 입력칸 회피가 그대로 적용된다.
      if (!_typing && (e.code === 'KeyQ' || e.code === 'KeyW' || e.code === 'KeyE')) {
        if (LOCK) return;                     // 길이 잠금 — 만들기·담기 금지(옮기기·🔁만)
        if (e.ctrlKey || e.metaKey || e.altKey) return;   // Ctrl+W(창 닫기) 등은 건드리지 않는다
        e.preventDefault();
        if (e.code === 'KeyQ') { markStart(); return; }
        if (e.code === 'KeyW') { markEnd();   return; }
        // ★E = 담기(2026-08-28 사장님). 손을 마우스로 옮기지 않고 Q→W→E로 끝낸다.
        //   담는 함수는 ⬆ 손잡이·두 번 누르기와 같은 onBoxCommit 하나다(0순위-B).
        //   고른 박스가 있으면 그것, 없으면 마지막에 만든 것(Esc가 지우는 것과 같은 기준).
        if (!BOXES.length) return;
        const bi = (ACTBOX != null && BOXES[ACTBOX]) ? ACTBOX : BOXES.length - 1;
        const b = BOXES[bi];
        if (b && typeof opt.onBoxCommit === 'function') opt.onBoxCommit({ s: b.s, e: b.e });
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
        // ★빨간 막대가 **언제나 이긴다**(2026-08-28 사장님 제보: "빨간색을 스페이스로
        //   한 번 재생 후 다른 지점 클릭하고 재생하면 빨간선부터 재생이 안 되고 엉뚱한
        //   곳에서 재생된다"). 종전엔 박스가 있으면 s2=bx.s로 **박스 시작**부터 갔고,
        //   RESUME은 '박스 안'일 때만 인정했다 — 그래서 막대를 박스 밖으로 옮기면
        //   그 자리를 무시하고 박스 앞머리로 튀었다. 내가 놓은 자리가 곧 시작점이다.
        //   (RESUME은 스크럽으로 옮길 때와 멈출 때 둘 다 갱신된다 — scrubTo/stopHead)
        const a2 = (RESUME != null) ? RESUME : (bx ? bx.s : (pv.currentTime || 0));
        // 끝은 쓰는 구간 끝까지. 막대가 그 뒤에 있으면 잘 곳이 없으니 필름 끝까지 돈다.
        let b2 = bx ? bx.e : DUR;
        if (b2 <= a2 + 0.05) b2 = DUR;
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

  // ── 구간 프레임 추출(2026-08-29, 칸 타임라인 ④) ──────────────────────────
  // 타임라인 컷 블록을 '필름식'으로 펼칠 때 쓴다 — 구간 [a,b]를 n장으로.
  // 시크·캡처 원리는 위 fillVisible과 같다(같은 브라우저 검증을 통과한 방식).
  // 여기(부품 파일)에 두는 이유: 프레임을 뽑는 코드가 두 벌이 되면 반드시
  // 한쪽만 고쳐진다(0순위-B). 필름롤 자체와는 캐시가 다르다 — 필름롤은
  // 칸(step) 단위, 이건 임의 구간 단위라 키가 애초에 다르다.
  const FRAME_CACHE = {};                    // "vid|a|b|n" → [dataURL…]
  const _FVIDS = {};                         // vid → <video> 재사용(매번 열면 느리다)
  async function filmframes(vid, src, a, b, n) {
    n = Math.max(1, Math.min(24, Math.round(n) || 1));
    const key = `${vid}|${(+a).toFixed(2)}|${(+b).toFixed(2)}|${n}`;
    if (FRAME_CACHE[key]) return FRAME_CACHE[key];
    let v = _FVIDS[vid];
    if (!v) {
      v = document.createElement('video');
      v.muted = true; v.preload = 'auto'; v.src = src;
      _FVIDS[vid] = v;
    }
    await new Promise(r => {
      if (v.readyState >= 1) return r();
      v.addEventListener('loadedmetadata', r, { once: true });
      setTimeout(r, 5000);
    });
    const cv = document.createElement('canvas');
    cv.width = 96; cv.height = 170;                       // 9:16 소형 — 펼침용이라 충분
    const x = cv.getContext('2d');
    const out = [];
    for (let k = 0; k < n; k++) {
      const t = (+a) + ((+b) - (+a)) * (k + 0.5) / n;     // 칸 한가운데(위 strip과 같은 규칙)
      await new Promise(r => {
        let done = false;
        const fin = () => { if (done) return; done = true; v.removeEventListener('seeked', fin); r(); };
        v.addEventListener('seeked', fin);
        try { v.currentTime = Math.max(0, t); } catch (e) { fin(); }
        setTimeout(fin, 800);                              // 시크가 영영 안 오는 파일 대비
      });
      try { x.drawImage(v, 0, 0, cv.width, cv.height); out.push(cv.toDataURL('image/jpeg', 0.6)); }
      catch (e) { out.push(''); }                          // tainted 등 — 빈 칸으로 두고 계속
    }
    FRAME_CACHE[key] = out;
    return out;
  }

  global.filmroll = filmroll;
  global.filmframes = filmframes;
})(window);
