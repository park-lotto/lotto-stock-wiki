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
      return `<div class="tl-cut" data-k="${k}" data-seg="${c.seg_id}"
        style="left:${left.toFixed(1)}px;width:${wd.toFixed(1)}px"
        title="${esc((DATA.segments[c.seg_id] || {}).label || c.seg_id)} · ${c.dur.toFixed(2)}초 — 누르면 필름식으로 펼쳐집니다"
        onclick="event.stopPropagation();tlToggleCut(${i},${k})">
        <img class="tl-thumb" src="${SL.thumb(c.seg_id)}" loading="lazy">
        <span class="tl-len">${c.dur.toFixed(1)}s</span>
        ${stretchPx > 4 ? `<span class="tl-stretch" style="width:${stretchPx.toFixed(1)}px"
           title="재료가 ${f.lack.toFixed(1)}초 모자라 이 컷이 그만큼 늘어납니다"></span>` : ''}
      </div>`;
    }).join('');
    const emptyHtml = clips.length ? '' :
      `<div class="tl-gap" style="left:0;width:${(dur * pps).toFixed(1)}px">장면 없음 — 아래 소스에서 담아주세요</div>`;
    const stretchBadge = (f.stretching && f.lack > 0.1)
      ? `<span class="tl-badge warn">늘려 채움 중 (+${f.lack.toFixed(1)}초)</span>` : '';

    // ── 자막 레인: captions 시간표 그대로. 누르면 F21(pickSeg)로 초가 필름에 들어간다.
    const capHtml = caps.map((c, k) => {
      const wd = Math.max(8, (c.end - c.start) * pps - 2);
      const sec = c.end - c.start;
      return `<div class="tl-cap" data-k="${k}"
        style="left:${(c.start * pps).toFixed(1)}px;width:${wd.toFixed(1)}px"
        title="${esc(c.text)} — ${sec.toFixed(2)}초. 누르면 필름 [+구간] 길이가 이 초로 맞춰집니다"
        onclick="event.stopPropagation();tlPickCap(${i},${k})">
        <span class="tl-cap-t">${esc(c.text)}</span><span class="tl-cap-s">${sec.toFixed(1)}s</span>
      </div>`;
    }).join('');

    // ── 음성 레인 + 재생선
    const ttsReal = ((DATA.tts_dur || {})[String(i)]);
    const audHtml = `<div class="tl-aud-bar" style="left:0;width:${(dur * pps).toFixed(1)}px">
        <span class="tl-aud-l">${ttsReal ? `beat_${i}.mp3 · ${(+ttsReal).toFixed(2)}s`
                                         : '🔇 음성 없음 — 추정 길이'}</span></div>`;

    return `<div class="tlwrap" data-i="${i}" data-pps="${pps.toFixed(3)}"
                 onclick="event.stopPropagation()">
      <div class="tl-lane tl-cuts"><span class="tl-name">컷</span>${cutHtml}${emptyHtml}${stretchBadge}</div>
      <div class="tl-lane tl-caps"><span class="tl-name">자막</span>${capHtml}</div>
      <div class="tl-lane tl-auds"><span class="tl-name">음성</span>${audHtml}</div>
      <div class="tl-head"></div>
    </div>`;
  }

  /* 자막 블록 클릭 → 기존 F21(pickSeg) 경로. 하이라이트만 타임라인에도 얹는다. */
  g.tlPickCap = function (i, k) {
    try { pickSeg(i, k); } catch (e) {}
    document.querySelectorAll('.tl-cap.sel').forEach(el => el.classList.remove('sel'));
    const el = document.querySelector(`.tlwrap .tl-cap[data-k="${k}"]`);
    if (el) el.classList.add('sel');
  };

  /* 컷 블록: 카드 ↔ 필름식 펼침(T2에서 filmframes로 채운다 — T1은 토글만) */
  g.tlToggleCut = function (i, k) {
    const el = document.querySelector(`.tlwrap .tl-cut[data-k="${k}"]`);
    if (!el) return;
    const open = el.classList.toggle('open');
    if (open && typeof g.tlFillFrames === 'function') g.tlFillFrames(i, k, el);
  };

  /* 마운트 — renderBand()가 innerHTML을 갈아끼운 직후 부른다. */
  g.tlMount = function () {
    cancelAnimationFrame(RAF);
    const host = document.querySelector('.tl-host');
    if (!host) return;
    const i = +host.dataset.i;
    if (!isFinite(i)) return;
    const w = host.clientWidth || 900;
    host.innerHTML = tlHtml(i, w);
    const wrap = host.querySelector('.tlwrap');
    const head = host.querySelector('.tl-head');
    const pps = parseFloat(wrap.dataset.pps);
    const capEls = [...host.querySelectorAll('.tl-cap')];
    const caps = capsOf(i);
    const tick = () => {
      if (!document.body.contains(host)) return;        // 다시 그려짐 — 다음 mount가 잇는다
      const playing = (typeof playKey !== 'undefined') && playKey === 'beat:' + i;
      if (playing) {
        const t = curT();
        head.style.left = (52 + t * pps) + 'px';
        head.classList.add('on');
        for (let k = 0; k < capEls.length; k++) {
          const c = caps[k];
          capEls[k].classList.toggle('on', !!c && t >= c.start - 1e-3 && t < c.end);
        }
      } else {
        head.classList.remove('on');
        capEls.forEach(el => el.classList.remove('on'));
      }
      RAF = requestAnimationFrame(tick);
    };
    RAF = requestAnimationFrame(tick);
  };
})(window);
