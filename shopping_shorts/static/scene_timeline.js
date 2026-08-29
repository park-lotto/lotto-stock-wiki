/* scene_timeline.js — 칸 타임라인: 자막·TTS·컷을 한 시간축에 (2026-08-29 설계 ①②③④).
 *
 * 계산은 하나도 새로 하지 않는다(0순위-B) — 전부 scene_lab.html·scene_play.js의
 * 기존 전역을 부른다:
 *   planClips(ids, dur, spread, i)  컷 배치(렌더와 같은 규칙)
 *   beatFill(i, clips)              need/have/lack/stretching
 *   beatDur(i) · capsOf(i) · capAt(i,t) · curT() · playKey · DATA · lists · STRETCH
 *   pickSeg(i,k)                    구절 초 → 필름 [+구간] (F21 기존 배선)
 *   SL.thumb(segId) · esc(s)
 *
 * 좌표 규약: 스크롤(off) 개념을 아예 두지 않는다 — 칸 길이가 폭을 채우는 고정 배율
 * (pps)이고 자식은 전부 절대 t×pps다. (2026-08-29 필름롤 off 이중차감 사고의 교훈:
 * 층·자식에 오프셋 규약이 두 벌이면 반드시 어긋난다. 여기선 한 벌도 안 만든다.)
 */
(function (g) {
  'use strict';

  let RAF = 0;                    // 재생선 루프 — 마운트된 타임라인 하나만 돈다

  function _dur(i) {
    return Math.max(0.2, beatDur(i) || 0.2);
  }

  /* 칸 i의 타임라인 HTML. 폭(px)은 mount가 잰 값을 준다. */
  function tlHtml(i, w) {
    const dur = _dur(i);
    const pps = Math.max(12, (w - 58) / dur);   // 왼쪽 레인이름 52px + 여백
    const caps = capsOf(i);
    const clips = planClips(lists[i] || [], beatDur(i), STRETCH[i], i);
    const f = beatFill(i, clips);

    // ── 컷 레인: planClips = 실제 렌더와 같은 배치("다 채움" 그대로 보인다)
    let acc = 0;
    const cutHtml = clips.map((c, k) => {
      const left = acc * pps, wd = Math.max(10, c.dur * pps - 2);
      acc += c.dur;
      // 마지막 컷이 모자람을 흡수해 늘어난 경우 — 그 늘어난 꼬리를 빗금으로 표시
      //   (★보정 후 합계만 보여주면 정보가 0이 된다는 교훈: 보정분을 눈에 보이게)
      const isLast = k === clips.length - 1;
      const stretchPx = (isLast && f.lack > 0.1 && !f.stretching)
        ? Math.min(f.lack, c.dur) * pps : 0;
      const inRep = REPLACE && REPLACE.i === i && REPLACE.k === k;
      return `<div class="tl-cut" data-k="${k}" data-seg="${c.seg_id}"
        style="left:${left.toFixed(1)}px;width:${wd.toFixed(1)}px"
        title="${esc((DATA.segments[c.seg_id] || {}).label || c.seg_id)} · ${c.dur.toFixed(2)}초 — 누르면 필름식으로 펼쳐집니다"
        onclick="event.stopPropagation();tlToggleCut(${i},${k})">
        <img class="tl-thumb" src="${SL.thumb(c.seg_id)}" loading="lazy">
        <span class="tl-len${getFix(i, c.seg_id) ? ' fixed' : ''}"
          ${getFix(i, c.seg_id) ? `title="내가 정한 길이 — 누르면 자동 배분으로 되돌립니다"
            onclick="event.stopPropagation();tlFixReset(${i},${k})"` : ''}
          >${getFix(i, c.seg_id) ? '✋' : ''}${c.dur.toFixed(1)}s</span>
        <span class="tl-edge" data-k="${k}" title="끌어서 이 컷의 길이 조절 — 늘리면 나머지 컷이 비례로 줄어듭니다"></span>
        <button type="button" class="tl-repbtn${inRep ? ' on' : ''}"
          title="${inRep ? '교체 모드 끄기' : `이 컷을 바꿉니다 — ${c.dur.toFixed(2)}초 고정 박스가 아래 소스 필름에 뜹니다`}"
          onclick="event.stopPropagation();tlReplaceToggle(${i},${k})">🔁</button>
        ${stretchPx > 4 ? `<span class="tl-stretch" style="width:${stretchPx.toFixed(1)}px"
           title="재료가 ${f.lack.toFixed(1)}초 모자라 이 컷이 그만큼 늘어납니다"></span>` : ''}
      </div>`;
    }).join('');
    const emptyHtml = clips.length ? '' :
      `<div class="tl-gap" style="left:0;width:${(dur * pps).toFixed(1)}px">장면 없음 — 아래 소스에서 담아주세요</div>`;
    const stretchBadge = (f.stretching && f.lack > 0.1)
      ? `<span class="tl-badge warn">늘려 채움 중 (+${f.lack.toFixed(1)}초)</span>` : '';

    // ── 자막 레인: captions 시간표 그대로. 누르면 F21(pickSeg)로 초가 필름에 들어간다.
    //    앞뒤 무음(리드인·꼬리)은 회색으로 채운다(2026-08-29 사장님 "무음표시 넣고") —
    //    표시만 한다: 시간표(진실)는 서버가 준 그대로, 빈 자리를 이름 붙일 뿐이다.
    let silHtml = '';
    if (caps.length) {
      const lead = caps[0].start, tail = dur - caps[caps.length - 1].end;
      if (lead > 0.15)
        silHtml += `<div class="tl-sil" style="left:0;width:${(lead * pps - 2).toFixed(1)}px"
          title="첫말 전 무음 ${lead.toFixed(2)}초 — 화면은 나오지만 아직 말이 없습니다">무음 ${lead.toFixed(1)}s</div>`;
      if (tail > 0.15)
        silHtml += `<div class="tl-sil" style="left:${(caps[caps.length - 1].end * pps).toFixed(1)}px;` +
          `width:${(tail * pps - 2).toFixed(1)}px" title="끝 무음 ${tail.toFixed(2)}초">무음 ${tail.toFixed(1)}s</div>`;
    }
    const capHtml = silHtml + caps.map((c, k) => {
      const wd = Math.max(8, (c.end - c.start) * pps - 2);
      const sec = c.end - c.start;
      // ★좁은 블록엔 글자를 아예 안 넣는다(2026-08-29 사장님 "자막이 0000 이렇게 뽑혔어" —
      //   구절 31개짜리 비정상 칸에서 초 배지가 "0."으로 잘려 도배됐다). 정보는 title에 남는다.
      const inner = wd < 30 ? ''
        : `<span class="tl-cap-t">${esc(c.text)}</span>` +
          (wd < 60 ? '' : `<span class="tl-cap-s">${sec.toFixed(1)}s</span>`);
      return `<div class="tl-cap" data-k="${k}"
        style="left:${(c.start * pps).toFixed(1)}px;width:${wd.toFixed(1)}px"
        title="${esc(c.text)} — ${sec.toFixed(2)}초. 누르면 필름 [+구간] 길이가 이 초로 맞춰집니다"
        onclick="event.stopPropagation();tlPickCap(${i},${k})">${inner}</div>`;
    }).join('');

    // ── 음성 레인 + 재생선. cap_src(⑦a) = 이 칸 구절 초가 어느 단에서 나왔나.
    const ttsReal = ((DATA.tts_dur || {})[String(i)]);
    const _b = (DATA.beats || [])[i] || {};
    // cap_src 기록이 없는 옛 job이라도 cap_durs가 비어 있으면 **그 자체가 추정**이다
    // (렌더도 그때 글자수 비례로 그린다). 균일한 0.8s 블록·무음 없음의 정체가 이것 —
    // 기록이 없다고 아는 척은 안 하되, 데이터가 말해주는 것까지 숨기진 않는다(2026-08-29).
    const capSrc = _b.cap_src || (ttsReal && _b.cap_durs == null ? 'estimate' : null);
    const srcBadge = capSrc === 'precise'
        ? '<span class="tl-src ok" title="TTS가 준 정밀 타임스탬프로 계산된 초입니다">🎯 정밀싱크</span>'
      : capSrc === 'asr'
        ? '<span class="tl-src mid" title="받아쓰기(ASR)로 맞춘 초 — 대체로 정확하지만 오인식만큼 어긋날 수 있어요">👂 받아쓰기</span>'
      : capSrc === 'estimate'
        ? '<span class="tl-src bad" title="구절 초가 글자수 추정입니다 — 🔊 음성·자막 다시 뽑기 한 번이면 정밀로 올라갑니다">≈ 추정</span>'
      : '';    // 옛 작업은 기록이 없다 — 아무것도 안 단다(모르는 걸 아는 척하지 않는다)
    const audHtml = `<div class="tl-aud-bar" style="left:0;width:${(dur * pps).toFixed(1)}px">
        <span class="tl-aud-l">${srcBadge}${ttsReal ? ` beat_${i}.mp3 · ${(+ttsReal).toFixed(2)}s`
                                         : ' 🔇 음성 없음 — 추정 길이'}</span></div>`;

    // 자막 레인은 두 얼굴: 보기(시간축 블록) / ✂편집(어절 칩 + 경계 클릭 — ⑥).
    // 레인 자리는 하나고 내용물만 바뀐다 — 래퍼를 두 벌 만들지 않는다(0순위-B).
    const capLane = TL_EDIT[i]
      ? `<div class="tl-lane tl-capedit"><span class="tl-name">자막</span>${tlCapEditHtml(i)}</div>`
      : `<div class="tl-lane tl-caps"><span class="tl-name">자막</span>${capHtml}</div>`;
    const editBtn = `<button type="button" class="tl-editbtn${TL_EDIT[i] ? ' on' : ''}"
        title="${TL_EDIT[i] ? '경계 편집 끝내기' : '자막 구절 경계 고치기 — 어절 사이를 눌러 끊고 합칩니다 (초는 실제 발화 시각으로 자동 재계산)'}"
        onclick="event.stopPropagation();tlEditToggle(${i})">${TL_EDIT[i] ? '✔ 끝내기' : '✂ 경계'}</button>`;

    return `<div class="tlwrap" data-i="${i}" data-pps="${pps.toFixed(3)}"
                 onclick="event.stopPropagation()">
      <div class="tl-lane tl-cuts"><span class="tl-name">컷</span>${cutHtml}${emptyHtml}${stretchBadge}</div>
      ${capLane}
      <div class="tl-lane tl-auds"><span class="tl-name">음성</span>${audHtml}</div>
      ${editBtn}
      <div class="tl-head"><span class="tl-hgrip" title="잡고 끌어서 재생 위치 이동">≡</span></div>
    </div>`;
  }

  const TL_POS = {};               // beat_idx → 재생선이 마지막으로 선 시각(초)

  // ── 스페이스 = 선택 칸 재생/일시정지(2026-08-29 사장님 — 재생선을 옮겨놓고 스페이스로
  //    그 지점부터 듣고 멈추며 자막과 비교하는 흐름). 재생·정지·이어서는 전부 기존 경로
  //    (playBeat가 토글까지 겸한다 / 미리보기 류는 togglePause)라 새 재생 규칙이 없다.
  //    ★필름롤이 펼쳐져 있으면 스페이스는 필름롤 몫이다(filmroll onKey) — 건드리지 않는다.
  document.addEventListener('keydown', e => {
    if (e.code !== 'Space') return;
    const tag = (e.target && e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || (e.target && e.target.isContentEditable)) return;
    if (document.querySelector('.frwin')) return;      // 필름이 열려 있다 — 필름롤이 받는다
    if (typeof playBeat !== 'function') return;
    e.preventDefault();
    if (typeof playKey !== 'undefined' && playKey && String(playKey).indexOf('beat:') === 0) {
      playBeat(+String(playKey).split(':')[1]);        // 재생 중이면 일시정지/재개 토글
    } else if (typeof seq !== 'undefined' && seq.length && typeof togglePause === 'function'
               && typeof playKey !== 'undefined' && playKey) {
      togglePause();                                   // 전체·조각 미리보기 중이면 그것을
    } else if (typeof sel !== 'undefined') {
      playBeat(sel);                                   // 아무것도 안 돌면 선택 칸부터
    }
  });

  // ── ⑧ 고정길이 박스 교체 ─────────────────────────────────────────────
  // 컷의 🔁를 누르면 그 컷 길이로 잠긴 박스가 **아래 소스 필름 어디를 펼치든** 떠 있고,
  // 영상1→2→3 갈아 끼워도 유지된다. 박스를 옮겨 맞는 장면에 놓고 [🔁 교체]를 누르면
  // 그 자리 컷이 바뀐다 — 길이가 잠겨 있어 초가 항상 딱 맞는다.
  let REPLACE = null;              // {i, k, len, oldSeg} | null

  g.tlReplaceToggle = function (i, k) {
    if (REPLACE && REPLACE.i === i && REPLACE.k === k) { REPLACE = null; render(); return; }
    const clips = planClips(lists[i] || [], beatDur(i), STRETCH[i], i);
    const c = clips[k];
    if (!c) return;
    // ★박스 = 그 조각이 쓰인 자리(2026-08-29 사장님 "그 영상이 담긴 부분이 오렌지박스로
    //   되어서 해당 영상을 필름으로 펼치고") — 그 영상 필름을 바로 펼치고, 잠금 박스를
    //   조각의 원본 위치에 놓는다. 카드의 🎞펼치기는 이 버튼이 겸한다(폭도 확보).
    REPLACE = { i, k, len: Math.round(c.dur * 100) / 100, oldSeg: c.seg_id,
                vid: c.video_id, from: Math.round(c.start * 100) / 100 };
    render();
    try {
      const S = (typeof rollSlot === 'function') ? rollSlot('src') : null;
      if (S && S.key === 'src:' + c.video_id) toggleRoll('src', c.video_id);  // 이미 열림 → 닫고
      toggleRoll('src', c.video_id);                                          // 잠금 박스와 함께 연다
    } catch (e) {}
    nsay(`📦 ${REPLACE.len.toFixed(2)}초 고정 박스 — 옮겨 놓고 [🔁 이 장면으로 교체], Esc로 끄기`);
  };

  /* 필름롤을 여는 쪽(scene_lab openRoll)이 부른다 — 교체 모드면 잠금 옵션을 준다.
     영상 통째 필름(src)에서만 잠근다: 조각 필름은 원래의 🔁(replaceRoll)이 이미 있다. */
  g.tlLockOpts = function (kind, vid) {
    if (!REPLACE || kind !== 'src') return {};
    REPLACE.filmVid = vid;                 // Esc로 끌 때 이 필름을 잠금 없이 다시 연다
    return {
      lockLen: REPLACE.len,
      // 조각이 이 영상 것이면 박스를 그 조각 자리에 놓는다(다른 영상이면 0초부터).
      lockFrom: (REPLACE.vid === vid ? REPLACE.from : 0),
      onReplace: r => tlReplaceApply(vid, r),
    };
  };

  // Esc = 박스(교체 모드) 끄기(2026-08-29 사장님 "esc로 끄기"). 필름롤의 Esc(박스 삭제)는
  // 잠금 모드에선 아무것도 안 하므로(LOCK 가드) 여기가 받아서 모드를 접는다.
  document.addEventListener('keydown', e => {
    if (e.code !== 'Escape' || !REPLACE) return;
    const tag = (e.target && e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || (e.target && e.target.isContentEditable)) return;
    const v = REPLACE.filmVid;
    REPLACE = null;
    render();
    // 잠금 박스를 얹은 채 열린 소스 필름이 있으면 잠금 없이 다시 연다(닫았다 열기).
    if (v && document.querySelector('.frwin')) {
      try { toggleRoll('src', v); toggleRoll('src', v); } catch (err) {}
    }
    nsay('📦 박스 모드를 껐어요');
  });

  async function tlReplaceApply(vid, r) {
    if (!REPLACE) return;
    const rep = REPLACE;
    // 컷 교체는 **기존 replaceRoll 경로 하나**로 — 새 조각 만들기·칸 갈아끼우기 규칙을
    // 여기서 다시 적지 않는다(0순위-B).
    try { replaceRoll(rep.oldSeg, vid, { s: r.s, e: r.e }); }
    catch (e) { nsay('⚠ 교체 실패 — ' + e.message); return; }
    REPLACE = null;
    // 교체 로그(⑩ 축소판 — 기록만, 픽 로직 무변경). 실패해도 조용히 넘어간다(부가 기능).
    try {
      const cap = (capsOf(rep.i) || [])[rep.k] || {};
      fetch(`/api/mix/scene_lab/${SL.job}/swap_log`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ beat: rep.i, old_seg: rep.oldSeg,
          new_video: vid, new_start: r.s, new_end: r.e,
          cap_text: cap.text || '', cap_sec: rep.len }) });
    } catch (e) {}
    render();
    nsay(`🔁 교체 완료 — ${rep.len.toFixed(2)}초 그대로 새 장면이 들어갔습니다`);
  }

  // ── ⑥ 구절 경계 편집 ────────────────────────────────────────────────
  const TL_EDIT = {};              // beat_idx → 편집 모드 켜짐

  /* 어절 칩 + 사이 경계. 현재 경계는 capsOf(i)의 구절 나눔 그대로다(그게 진실). */
  function tlCapEditHtml(i) {
    const caps = capsOf(i);
    const items = [];               // {w, ci} — 어절과 그 어절이 속한 구절 번호
    caps.forEach((c, ci) => String(c.text).split(/\s+/).filter(Boolean)
      .forEach(w => items.push({ w, ci })));
    if (!items.length) return '<span class="tl-loading">자막 없음</span>';
    let h = '<div class="tl-chips">';
    items.forEach((it, j) => {
      h += `<span class="tl-word">${esc(it.w)}</span>`;
      if (j < items.length - 1) {
        const isB = items[j + 1].ci !== it.ci;
        h += `<button type="button" class="tl-gapbtn${isB ? ' b' : ''}"
          title="${isB ? '경계 지우기(앞 구절과 합치기)' : '여기서 끊기'}"
          onclick="event.stopPropagation();tlGapClick(${i},${j})">${isB ? '‖' : '·'}</button>`;
      }
    });
    return h + '</div>';
  }

  g.tlEditToggle = function (i) {
    TL_EDIT[i] = !TL_EDIT[i];
    g.tlMount();
  };

  // ── 컷 가장자리 드래그 = 길이 직접 조절(2026-08-29 사장님 "1초짜리를 마우스로 잡고
  //    조금 더 길게 늘릴 수 있나? 편하게"). 길이를 정하는 곳은 기존 FIXLEN/setFix
  //    하나다(0순위-B) — 카드 숫자 클릭(askCutLen)과 같은 저장소·같은 배분 규칙:
  //    "정한 컷은 그대로, 나머지 컷이 비례로 줄어든다"(칸 총초는 음성에 매여 불변).
  g.tlFixReset = function (i, k) {
    const clips = planClips(lists[i] || [], beatDur(i), STRETCH[i], i);
    const c = clips[k];
    if (c) setFix(i, c.seg_id, 0);         // setFix가 render()까지 부른다
  };
  function wireEdges(host, i, pps) {
    host.querySelectorAll('.tl-edge').forEach(ed => {
      ed.addEventListener('pointerdown', e => {
        e.stopPropagation(); e.preventDefault();
        const cut = ed.closest('.tl-cut');
        const k = +cut.dataset.k;
        const w0 = cut.offsetWidth, x0 = e.clientX;
        const badge = cut.querySelector('.tl-len');
        cut.classList.add('sizing');
        try { ed.setPointerCapture(e.pointerId); } catch (_) {}
        const move = me => {
          const w = Math.max(0.2 * pps, w0 + (me.clientX - x0));
          cut.style.width = w + 'px';                       // 미리보기 — 확정은 놓을 때
          if (badge) badge.textContent = '✋' + (w / pps).toFixed(2) + 's';
          me.stopPropagation();
        };
        const up = ue => {
          ed.removeEventListener('pointermove', move);
          ed.removeEventListener('pointerup', up);
          ed.removeEventListener('pointercancel', up);
          cut.classList.remove('sizing');
          const sec = Math.round((cut.offsetWidth / pps) * 100) / 100;
          const clips = planClips(lists[i] || [], beatDur(i), STRETCH[i], i);
          const c = clips[k];
          if (c && Math.abs(sec - c.dur) >= 0.05) setFix(i, c.seg_id, sec);
          else g.tlMount();                                 // 거의 안 움직임 — 원상 복구
          ue.stopPropagation();
        };
        ed.addEventListener('pointermove', move);
        ed.addEventListener('pointerup', up);
        ed.addEventListener('pointercancel', up);
      });
    });
  }

  /* 어절 j 뒤의 경계를 토글 → 새 구절 목록을 서버에 저장(초 재계산) → 화면 연쇄 갱신(⑨). */
  g.tlGapClick = async function (i, j) {
    const caps = capsOf(i);
    const words = [];               // 전체 어절(순서 보존)
    const bset = new Set();         // 경계 = "이 어절 뒤에서 끊김"인 어절 인덱스
    caps.forEach((c, ci) => {
      String(c.text).split(/\s+/).filter(Boolean).forEach(w => words.push(w));
      if (ci < caps.length - 1) bset.add(words.length - 1);
    });
    if (bset.has(j)) bset.delete(j); else bset.add(j);
    const lines = []; let cur = [];
    words.forEach((w, k) => { cur.push(w); if (bset.has(k)) { lines.push(cur.join(' ')); cur = []; } });
    if (cur.length) lines.push(cur.join(' '));
    try {
      // 저장은 **이미 있는** 자막 줄나눔 API 하나로(0순위-B — 2026-08-25 caplines).
      const r = await fetch(`/api/produce/mix/${SL.job}/caplines`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ beat_idx: i, lines }) });
      const d = await r.json();
      if (!r.ok || !d.ok) { nsay('⚠ ' + (d.error || '경계 저장 실패')); return; }
      // ⑨ 연쇄 갱신 — 진실(구절 시간표)만 바꾸고 나머지는 render()가 파생으로 다시 그린다.
      if (d.captions) DATA.captions[String(i)] = d.captions;
      const b = (DATA.beats || [])[i];
      if (b) { b.caption_lines = lines; b.cap_durs = d.cap_durs;
               b.cap_lead = d.cap_lead; b.cap_src = d.cap_src; }
      if (!d.timed) nsay('⚠ 이 칸은 정밀 타임스탬프가 없어 초가 추정입니다 — 🔊 음성·자막 다시 뽑기를 권장');
      render();
    } catch (e) { nsay('⚠ 경계 저장 실패 — 네트워크'); }
  };

  /* 자막 블록 클릭 → 기존 F21(pickSeg) 경로. 하이라이트만 타임라인에도 얹는다. */
  g.tlPickCap = function (i, k) {
    try { pickSeg(i, k); } catch (e) {}
    document.querySelectorAll('.tl-cap.sel').forEach(el => el.classList.remove('sel'));
    const el = document.querySelector(`.tlwrap .tl-cap[data-k="${k}"]`);
    if (el) el.classList.add('sel');
  };

  /* 컷 블록: 카드 ↔ 필름식 펼침(④). 프레임 추출은 filmroll.js의 filmframes 하나만 쓴다. */
  g.tlToggleCut = function (i, k) {
    const el = document.querySelector(`.tlwrap .tl-cut[data-k="${k}"]`);
    if (!el) return;
    const open = el.classList.toggle('open');
    if (!open) { const fr = el.querySelector('.tl-frames'); if (fr) fr.remove(); return; }
    g.tlFillFrames(i, k, el);
  };

  /* 펼친 컷을 실제 프레임들로 채운다 — clip 구간을 폭에 맞는 장수로. */
  g.tlFillFrames = async function (i, k, el) {
    const clips = planClips(lists[i] || [], beatDur(i), STRETCH[i], i);
    const c = clips[k];
    if (!c || typeof filmframes !== 'function') return;
    const n = Math.max(3, Math.round(el.offsetWidth / 34));
    let fr = el.querySelector('.tl-frames');
    if (!fr) {
      fr = document.createElement('div'); fr.className = 'tl-frames';
      fr.innerHTML = '<span class="tl-loading">🎞…</span>';
      el.appendChild(fr);
    }
    try {
      const urls = await filmframes(c.video_id, SL.src(c.video_id), c.start, c.start + c.dur, n);
      if (!el.classList.contains('open')) return;          // 그 사이 접혔다 — 버린다
      fr.innerHTML = urls.map(u => u ? `<img src="${u}">` : '<img>').join('');
    } catch (e) {
      fr.innerHTML = '<span class="tl-loading">프레임 실패</span>';
    }
  };

  /* 마운트 — renderBand()가 innerHTML을 갈아끼운 직후 부른다. */
  // 모든 칸에 타임라인(2026-08-29 사장님 "옆에도 다 타임스탬프 만들고 꽉 채워줘" —
  // 종전엔 선택 칸 하나만). 칸마다 자기 rAF·자기 재생선이라 서로 안 밟는다.
  const RAFS = [];
  g.tlMount = function () {
    cancelAnimationFrame(RAF);
    while (RAFS.length) cancelAnimationFrame(RAFS.pop());
    document.querySelectorAll('.tl-host').forEach(h => { try { _mountOne(h); } catch (e) { console.error('[tl]', e); } });
  };
  function _mountOne(host) {
    const i = +host.dataset.i;
    if (!isFinite(i)) return;
    const w = host.clientWidth || 900;
    host.innerHTML = tlHtml(i, w);
    const wrap = host.querySelector('.tlwrap');
    const head = host.querySelector('.tl-head');
    const pps = parseFloat(wrap.dataset.pps);
    const capEls = [...host.querySelectorAll('.tl-cap')];
    const caps = capsOf(i);
    wireEdges(host, i, pps);               // 컷 가장자리 드래그(길이 조절)
    // ── 재생선 손잡이(2026-08-29 사장님 "가운데 잡고 재생위치 옮길수있게") ─────────
    //    이동은 기존 seekTo 하나로(0순위-B — 진행바(#seek)와 같은 길: 컷·음성·타이머
    //    정렬을 그 함수가 다 한다). 끄는 동안은 진행바처럼 **일시정지**.
    let hdrag = false;
    const hgrip = head.querySelector('.tl-hgrip');
    if (hgrip) {
      const laneX = () => host.querySelector('.tl-lane').getBoundingClientRect().left;
      let lastSeek = 0;
      hgrip.addEventListener('pointerdown', e => {
        e.stopPropagation(); e.preventDefault();
        hdrag = true;
        try { hgrip.setPointerCapture(e.pointerId); } catch (_) {}
        // 이 칸 재생이 아직 안 올라와 있으면 올린다(그래야 seek할 대상이 있다).
        if (typeof playKey === 'undefined' || playKey !== 'beat:' + i) {
          try { playBeat(i); } catch (_) {}
        }
        // ★일시정지는 seq가 **뜬 뒤에** 걸어야 한다(2026-08-29 사장님 "놓으면 맨 앞으로
        //   튕김"). startSeq가 비동기라 잡는 순간엔 seq가 비어 togglePause가 조용히
        //   무시됐고, 재생이 0초부터 시작돼 놓을 때 오디오 시계 0초가 이겼다.
        //   뜰 때까지 되풀이해 멈춘다 — 멈추면 이후 seek이 '자리만 옮김'으로 안전하다.
        let _pt = 0;
        const ensurePause = () => {
          try {
            if (seq.length) { if (!seqPaused) togglePause(); return; }
          } catch (_) { return; }
          if (_pt++ < 30) setTimeout(ensurePause, 100);
        };
        ensurePause();
      });
      hgrip.addEventListener('pointermove', e => {
        if (!hdrag) return;
        const dur = _dur(i);
        const t = Math.max(0, Math.min(dur - 0.05, (e.clientX - laneX()) / pps));
        TL_POS[i] = t;
        head.style.left = (52 + t * pps) + 'px';
        head.classList.add('on');
        const now = performance.now();
        if (now - lastSeek > 150) {
          lastSeek = now;
          try { seekTo(t); } catch (_) {}
          // ★멈춘 채 옮길 땐 seekTo가 자막 갱신(tickSub)을 건너뛴다(재생 분기에만 있음) —
          //   미리보기 자막도 그 지점 것으로 한 번 칠한다(2026-08-29 사장님 "이동할 때는
          //   미리보기에서 자막이 안 바뀐다"). tickSub는 멈춤 상태면 한 번 그리고 스스로 꺼진다.
          try { if (typeof tickSub === 'function') tickSub(); } catch (_) {}
        }
        e.stopPropagation();
      });
      const hup = e => {
        if (!hdrag) return;
        hdrag = false;
        const t = TL_POS[i];
        // seq가 뜨고 + 멈춘 상태가 된 뒤에 시크하고, 안착까지 확인한다(오디오가 늦게
        // 준비되면 시계가 0초로 되감아 "맨 앞으로 튕김"이 됐다 — 안착 실패 시 재시도).
        let tries = 0;
        const settle = () => {
          try {
            if (typeof seq !== 'undefined' && seq.length) {
              if (!seqPaused) togglePause();
              seekTo(t);
              try { if (typeof tickSub === 'function') tickSub(); } catch (_) {}
              setTimeout(() => {
                try {
                  if (t > 0.4 && curT() < 0.2 && tries++ < 8) settle();  // 0으로 되감김 — 다시
                } catch (_) {}
              }, 250);
              return;
            }
          } catch (_) {}
          if (tries++ < 12) setTimeout(settle, 150);
        };
        settle();
        e.stopPropagation();
      };
      hgrip.addEventListener('pointerup', hup);
      hgrip.addEventListener('pointercancel', hup);
    }
    const tick = () => {
      if (!document.body.contains(host)) return;        // 다시 그려짐 — 다음 mount가 잇는다
      const playing = (typeof playKey !== 'undefined') && playKey === 'beat:' + i;
      if (playing && !hdrag) {
        const t = curT();
        TL_POS[i] = t;
        head.style.left = (52 + t * pps) + 'px';
        head.classList.add('on');
        for (let k = 0; k < capEls.length; k++) {
          const c = caps[k];
          capEls[k].classList.toggle('on', !!c && t >= c.start - 1e-3 && t < c.end);
        }
      } else if (!hdrag) {
        // 재생 전에도 손잡이는 보인다(잡을 수 있어야 하니까) — 마지막 자리 또는 첫말 앞.
        const t = TL_POS[i] != null ? TL_POS[i] : ((caps[0] && caps[0].start) || 0);
        head.style.left = (52 + t * pps) + 'px';
        head.classList.add('on');
        capEls.forEach(el => el.classList.remove('on'));
      }
      RAFS.push(requestAnimationFrame(tick));
    };
    RAFS.push(requestAnimationFrame(tick));
  }
})(window);
