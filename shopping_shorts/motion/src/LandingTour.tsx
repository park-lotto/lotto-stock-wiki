// 랜딩 "눌러보면 바로 이해됩니다" 탭 4개용 1280x800 영상 + Remotion 효과자막.
// ★원본 픽셀은 1배 이하(축소·크롭만) — 확대 금지.
// 재료: public/tour/ (gitignore) — rank_top.png(1646x863) · rank_grid.png(1685x896) · mix.png(1608x832)
//       search.mp4(1798x800, 15.07s) · script.mp4(1546x800, 11.93s) — render-tour.mjs prep 로 생성.
import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {useFont} from './LandingHeroWall';

const W = 1280;
const H = 800;
const FONT = 'HeroKR';
const YEL = '#FFD84D';
const RED = '#FF4D4D';
const MINT = '#6FF0D6';
const BG = '#070b0f';

// ── 효과자막 ─────────────────────────────────────────
type Tok = {t: string; k?: 'y' | 'r' | 'm'; suffix?: string}; // y=노랑마커 r=빨강글자 m=빨강마커(흰글자)
// 표기: [노랑마커] {빨강강조} — 공백으로 단어를 가르고, "[검색]만" 처럼 붙은 조사는 suffix 로 같이 팝
export const parse = (s: string): Tok[] => {
  const protectedS = s.replace(/(\[[^\]]+\]|\{[^}]+\}|<[^>]+>)/g, (m) => m.replace(/ /g, ' '));
  return protectedS
    .trim()
    .split(/ +/) // \s 는 NBSP도 갈라버리므로 ASCII 공백만
    .filter(Boolean)
    .map((w): Tok => {
      const m = w.match(/^(\[([^\]]+)\]|\{([^}]+)\}|<([^>]+)>)(.*)$/);
      if (!m) return {t: w.replace(/ /g, ' ')};
      const k = m[2] !== undefined ? 'y' : m[3] !== undefined ? 'r' : 'm';
      return {t: (m[2] ?? m[3] ?? m[4]).replace(/ /g, ' '), k, suffix: m[5] || undefined};
    });
};

export const Word: React.FC<{tok: Tok; idx: number; local: number; size: number}> = ({tok, idx, local, size}) => {
  const {fps} = useVideoConfig();
  const delay = idx * 5;
  const s = spring({frame: local - delay, fps, config: {damping: 11, stiffness: 190, mass: 0.7}});
  const op = interpolate(local - delay, [0, 4], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const sweep = interpolate(local - delay, [5, 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const isM = tok.k === 'm';
  const isY = tok.k === 'y' || isM;
  const isR = tok.k === 'r';
  const onMarker = isY && sweep > 0.5;
  const shadow = `0 ${Math.max(2, size * 0.05)}px 0 rgba(0,0,0,.6)`;
  return (
    <span
      style={{
        position: 'relative',
        display: 'inline-block',
        margin: `0 ${size * 0.08}px`,
        transform: `scale(${interpolate(s, [0, 1], [0.6, 1])}) translateY(${(1 - s) * size * 0.25}px)`,
        opacity: op,
        whiteSpace: 'nowrap',
      }}
    >
      {/* 마커는 본문 글자 뒤에만 — 조사(suffix)는 밖 */}
      <span
        style={{
          position: 'relative',
          display: 'inline-block',
          padding: isY ? `0 ${size * 0.18}px` : '0 2px',
          color: onMarker ? (isM ? '#fff' : '#111') : isR ? RED : '#fff',
          textShadow: onMarker ? 'none' : shadow,
        }}
      >
        {isY && (
          <span
            style={{
              position: 'absolute',
              left: 0,
              top: size * 0.06,
              bottom: size * 0.06,
              width: `${sweep * 100}%`,
              background: isM ? RED : YEL,
              borderRadius: size * 0.14,
              transform: 'rotate(-1.2deg)',
              zIndex: 0,
            }}
          />
        )}
        <span style={{position: 'relative', zIndex: 1}}>{tok.t}</span>
      </span>
      {tok.suffix && <span style={{color: '#fff', textShadow: shadow, marginLeft: isY ? size * 0.06 : 0}}>{tok.suffix}</span>}
    </span>
  );
};

type CapProps = {main: string; sub?: string; from: number; to: number; size?: number; pos?: 'bottom' | 'top'};
export const Caption: React.FC<CapProps> = ({main, sub, from, to, size = 58, pos = 'bottom'}) => {
  const frame = useCurrentFrame();
  if (frame < from || frame > to) return null;
  const local = frame - from;
  const out = interpolate(frame, [to - 8, to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const inn = interpolate(local, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const toks = parse(main);
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        [pos]: 0,
        padding: pos === 'bottom' ? '54px 48px 30px' : '30px 48px 54px',
        background:
          pos === 'bottom'
            ? 'linear-gradient(0deg, rgba(4,7,10,.9) 0%, rgba(4,7,10,.8) 60%, rgba(4,7,10,0) 100%)'
            : 'linear-gradient(180deg, rgba(4,7,10,.9) 0%, rgba(4,7,10,.8) 60%, rgba(4,7,10,0) 100%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: 10,
        opacity: inn * out,
        fontFamily: FONT,
        fontWeight: 900,
      }}
    >
      <div style={{display: 'flex', flexWrap: 'wrap', alignItems: 'center', fontSize: size, lineHeight: 1.25, letterSpacing: -1.5}}>
        {toks.map((tok, i) => (
          <Word key={i} tok={tok} idx={i} local={local} size={size} />
        ))}
      </div>
      {sub && (
        <div
          style={{
            fontSize: 30,
            fontWeight: 700,
            lineHeight: 1.3,
            color: 'rgba(255,255,255,.88)',
            letterSpacing: -0.5,
            textShadow: '0 2px 0 rgba(0,0,0,.6)',
            opacity: interpolate(local, [toks.length * 5 + 8, toks.length * 5 + 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
            display: 'flex',
            flexWrap: 'wrap',
          }}
        >
          {parse(sub).map((tok, i) => (
            <span key={i} style={{marginRight: 8, whiteSpace: 'nowrap'}}>
              <span style={{color: tok.k === 'r' ? RED : tok.k === 'y' ? YEL : undefined}}>{tok.t}</span>
              {tok.suffix}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

// 우상단 사이트 칩
const Chip: React.FC<{label: string; color: string; from: number; to: number}> = ({label, color, from, to}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < from || frame > to) return null;
  const s = spring({frame: frame - from, fps, config: {damping: 12, stiffness: 180}});
  const out = interpolate(frame, [to - 6, to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div
      style={{
        position: 'absolute',
        top: 28,
        right: 28,
        padding: '12px 26px',
        borderRadius: 999,
        background: color,
        color: '#fff',
        fontFamily: FONT,
        fontWeight: 900,
        fontSize: 34,
        lineHeight: 1.1,
        letterSpacing: -0.5,
        boxShadow: '0 10px 30px rgba(0,0,0,.5)',
        transform: `scale(${interpolate(s, [0, 1], [0.5, 1])})`,
        opacity: Math.min(1, s * 1.5) * out,
        textShadow: '0 2px 0 rgba(0,0,0,.35)',
      }}
    >
      {label}
    </div>
  );
};

// 가장자리 페이드(루프 이음매)
const EdgeFade: React.FC<{dur: number; n?: number}> = ({dur, n = 9}) => {
  const frame = useCurrentFrame();
  const o = Math.max(
    interpolate(frame, [0, n], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [dur - n, dur - 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  return <div style={{position: 'absolute', inset: 0, background: BG, opacity: o, pointerEvents: 'none'}} />;
};

// ── 1) 레퍼런스 랭킹 — 캡처 2장 패닝 (8s) ───────────
const S1 = 240;
export const TourStep1: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  // 둘 다 높이 800에 맞춤(축소) → 가로 패닝
  const topS = 800 / 863; // 0.927
  const gridS = 800 / 896; // 0.893
  const topW = 1646 * topS; // 1526
  const gridW = 1685 * gridS; // 1505
  const aOut = interpolate(frame, [96, 112], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const aIn = interpolate(frame, [S1 - 14, S1 - 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const aOp = Math.max(aOut, aIn);
  const aX = interpolate(frame, [0, 112], [0, -(topW - W)], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const bX = interpolate(frame, [96, S1], [0, -(gridW - W)], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      <Img src={staticFile('tour/rank_grid.png')} style={{position: 'absolute', left: bX, top: 0, width: gridW, height: 800}} />
      <Img src={staticFile('tour/rank_top.png')} style={{position: 'absolute', left: aIn > 0 ? 0 : aX, top: 0, width: topW, height: 800, opacity: aOp}} />
      <Caption main="매일 [수백 개] 터지는 레퍼런스" sub="조회수·구독자 대비로 줄 세워 매일 갱신" from={10} to={S1 - 4} />
    </AbsoluteFill>
  );
};

// ── 2) 숏템파워검색 — 녹화본 + 사이트 칩 (15.07s) ──
const S2 = 452;
export const TourStep2: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const vw = 1798;
  // 검색 구간은 가운데 모달 → 살짝 오른쪽에서 왼쪽으로, 이후 사이트 화면은 왼쪽 정렬로 천천히
  const x = interpolate(frame, [0, 165, 166, S2], [-(vw - W) / 2 - 60, -(vw - W) / 2 + 60, 0, -(vw - W)], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const segs = [
    {label: '핀터레스트', color: '#E60023', from: 165, to: 225},
    {label: '인스타그램', color: '#D6249F', from: 225, to: 285},
    {label: '틱톡', color: '#161823', from: 285, to: 333},
    {label: '도우인', color: '#1C0B1A', from: 333, to: 387},
    {label: '샤오홍슈', color: '#FF2442', from: 387, to: S2 - 8},
  ];
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      <OffthreadVideo src={staticFile('tour/search.mp4')} muted style={{position: 'absolute', left: x, top: 0, width: vw, height: 800}} />
      {segs.map((s) => (
        <Chip key={s.label} {...s} />
      ))}
      <Caption main="[숏템파워검색]만 누르면" from={10} to={162} />
      <Caption main="{5대 플랫폼} 자동 검색" sub="핀터레스트·인스타그램·틱톡·도우인·샤오홍슈" from={166} to={S2 - 4} />
      <EdgeFade dur={S2} />
    </AbsoluteFill>
  );
};

// ── 3) 대본 — 녹화본 (11.93s) ───────────────────────
const S3 = 358;
export const TourStep3: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const vw = 1546;
  const x = interpolate(frame, [0, S3], [0, -(vw - W)], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      <OffthreadVideo src={staticFile('tour/script.mp4')} muted style={{position: 'absolute', left: x, top: 0, width: vw, height: 800}} />
      <Caption main="[최상급] 대본 스타일 템플릿을 선택" from={10} to={206} size={54} />
      <Caption main="{내 제품 대본} 완성" sub="A안·B안 두 가지로 바로 나옵니다" from={210} to={S3 - 4} />
      <EdgeFade dur={S3} />
    </AbsoluteFill>
  );
};

// ── 4) 장면매칭 — 캡처 켄번스(≤1배) + 민트 박스 (8s) ─
const S4 = 240;
export const TourStep4: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const iw = 1608;
  const ih = 832;
  // 배율 0.962(높이맞춤) ↔ 1.0 사이 — 절대 1 초과 안 함. sin 곡선이라 0/끝 프레임 동일
  const s = 800 / ih + (1 - 800 / ih) * Math.sin((Math.PI * frame) / S4);
  // hook 블록(원본 x385~1255, y275~605) 중심이 화면 중앙 조금 위로 오게
  const cx = 820;
  const cy = 430;
  const left = W / 2 - cx * s;
  const top = Math.min(0, Math.max(H - ih * s, 300 - cy * s));
  const boxes = [
    {r: {x: 393, y: 300, w: 850, h: 110}, t0: 40, t1: 100}, // 타임라인(컷+자막 줄)
    {r: {x: 393, y: 411, w: 372, h: 168}, t0: 104, t1: 160}, // 컷 카드 4개
    {r: {x: 393, y: 578, w: 305, h: 28}, t0: 164, t1: 220}, // 문장 선택
  ];
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      <div style={{position: 'absolute', left, top, width: iw * s, height: ih * s}}>
        <Img src={staticFile('tour/mix.png')} style={{width: '100%', height: '100%', display: 'block'}} />
        {boxes.map((b, i) => {
          if (frame < b.t0 || frame > b.t1) return null;
          const pulse = 0.55 + 0.45 * Math.sin(((frame - b.t0) / 9) * Math.PI);
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: b.r.x * s,
                top: b.r.y * s,
                width: b.r.w * s,
                height: b.r.h * s,
                border: `3px solid ${MINT}`,
                borderRadius: 10,
                boxShadow: '0 0 22px rgba(111,240,214,.6), inset 0 0 0 999px rgba(111,240,214,.08)',
                opacity: Math.abs(pulse),
              }}
            />
          );
        })}
      </div>
      <Caption main="[AI가 자동 매칭]" sub="마음에 안 들면 {직접 수동 매칭}도 아주 쉽게" from={10} to={S4 - 4} />
    </AbsoluteFill>
  );
};

export const TOURS = {
  tour_step1b: {component: TourStep1, durationInFrames: S1},
  tour_step2: {component: TourStep2, durationInFrames: S2},
  tour_step3b: {component: TourStep3, durationInFrames: S3},
  tour_step4b: {component: TourStep4, durationInFrames: S4},
} as const;
export const TOUR_BASE = {width: W, height: H, fps: 30};
