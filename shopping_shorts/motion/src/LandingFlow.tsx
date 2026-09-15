// 랜딩 flow 4칸(1080x1080, 9s 루프) — 빠른 컷·3D 틸트 등장·모션블러 전환·줌 펀치·빛 스윕·박스 드로잉·파티클 + 중상단 대형 자막.
// 확대 0(1:1 크롭·축소만). 글자에는 블러 없음(블러는 캡처 이미지 전환 순간에만).
// 재료(gitignore): public/cap/88~95.png(사장님 캡처 원본) · public/render/full1~4.mp4(608x1080)
import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {useFont} from './LandingHeroWall';
import {Word, parse} from './LandingTour';

const S = 1080;
const FONT = 'HeroKR';
const MINT = '#6FF0D6';
const YEL = '#FFD84D';
const BG = '#070b0f';
const NL = String.fromCharCode(10);

type Rect = {x: number; y: number; w: number; h: number};
export type Tile = {
  file: string;
  full: {w: number; h: number};
  crop: Rect; // 원본 좌표 1:1 크롭 (w ≤ 1080)
  pan?: [number, number];
  boxes?: Rect[]; // 크롭 기준 강조 박스(드로잉)
  wipe?: {file: string; full: {w: number; h: number}; crop: Rect}; // BEFORE(crop)→AFTER(wipe.crop) 스캔 와이프
};
// 컷 = 타일 1~3장을 세로로 쌓아 칸을 꽉 채운다(레터박스 없음)
export type Cut = {tiles: Tile[]; len?: number};
export type FlowProps = {cuts: Cut[]; cutFrames: number; lines: [string, string]; dur: number; lineSplit?: number; chip?: {label: string; n?: number; suffix?: string}};

// ── 파티클(결정적 난수) ──────────────────────────────
const rnd = (i: number, k: number) => {
  const x = Math.sin(i * 127.1 + k * 311.7) * 43758.5453;
  return x - Math.floor(x);
};
export const Sparkles: React.FC<{frame: number; n?: number; seed?: number}> = ({frame, n = 26, seed = 0}) => (
  <div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
    {Array.from({length: n}, (_, i) => {
      const x = rnd(i + seed, 1) * S;
      const y = rnd(i + seed, 2) * S;
      const sp = 0.5 + rnd(i + seed, 3) * 1.2;
      const ph = rnd(i + seed, 4) * Math.PI * 2;
      const tw = 0.5 + 0.5 * Math.sin(frame * 0.12 * sp + ph);
      const sz = 3 + rnd(i + seed, 5) * 5;
      const col = rnd(i + seed, 6) > 0.6 ? YEL : MINT;
      return (
        <div key={i} style={{position: 'absolute', left: x, top: ((y - frame * 0.25 * sp) % S + S) % S, width: sz, height: sz, borderRadius: '50%', background: col, opacity: tw * 0.85, boxShadow: `0 0 ${sz * 2}px ${col}`}} />
      );
    })}
  </div>
);

const LightSweep: React.FC<{local: number}> = ({local}) => {
  if (local > 26) return null;
  const x = interpolate(local, [3, 24], [-0.6, 1.4], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden'}}>
      <div style={{position: 'absolute', top: -300, bottom: -300, left: `${x * 100}%`, width: 300, background: 'linear-gradient(100deg, rgba(255,255,255,0), rgba(255,255,255,.32), rgba(255,255,255,0))', transform: 'skewX(-22deg)'}} />
    </div>
  );
};

// 강조 박스: SVG 선 드로잉 + 안쪽 은은한 채움
const DrawBox: React.FC<{r: Rect; local: number; t0: number}> = ({r, local, t0}) => {
  const p = interpolate(local, [t0, t0 + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  if (p <= 0) return null;
  const per = 2 * (r.w + r.h);
  return (
    <svg style={{position: 'absolute', left: r.x - 6, top: r.y - 6, overflow: 'visible'}} width={r.w + 12} height={r.h + 12}>
      <rect x={0} y={0} width={r.w + 12} height={r.h + 12} rx={12} fill="rgba(111,240,214,.10)" opacity={p} />
      <rect x={0} y={0} width={r.w + 12} height={r.h + 12} rx={12} fill="none" stroke={MINT} strokeWidth={5} strokeDasharray={per} strokeDashoffset={per * (1 - p)} style={{filter: 'drop-shadow(0 0 10px rgba(111,240,214,.8))'}} />
    </svg>
  );
};

const TILE_GAP = 14;
const TileView: React.FC<{tile: Tile; local: number; len: number}> = ({tile, local, len}) => {
  const {crop} = tile;
  const [dx, dy] = tile.pan ?? [0, 0];
  const t = Math.min(1, local / len);
  const px = -crop.x - dx * t;
  const py = -crop.y - dy * t;
  const wipeP = tile.wipe ? interpolate(local, [14, 44], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
  return (
    <div style={{position: 'relative', width: crop.w, height: crop.h, overflow: 'hidden', borderRadius: 18, boxShadow: '0 0 0 2px rgba(255,255,255,.07)'}}>
      <Img src={staticFile(tile.file)} style={{position: 'absolute', left: px, top: py, width: tile.full.w, height: tile.full.h}} />
      {tile.wipe && (
        <>
          <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${(1 - wipeP) * 100}% 0 0)`}}>
            <Img src={staticFile(tile.wipe.file)} style={{position: 'absolute', left: -tile.wipe.crop.x, top: -tile.wipe.crop.y, width: tile.wipe.full.w, height: tile.wipe.full.h}} />
          </div>
          {wipeP > 0 && wipeP < 1 && (
            <>
              <div style={{position: 'absolute', inset: 0, background: 'repeating-linear-gradient(0deg, rgba(111,240,214,.14) 0 2px, transparent 2px 8px)', clipPath: `inset(0 ${(1 - wipeP) * 100}% 0 ${Math.max(0, wipeP * 100 - 18)}%)`}} />
              <div style={{position: 'absolute', top: -20, bottom: -20, left: `calc(${wipeP * 100}% - 4px)`, width: 8, background: MINT, boxShadow: '0 0 30px 8px rgba(111,240,214,.8)'}} />
            </>
          )}
        </>
      )}
      {(tile.boxes ?? []).map((b, i) => (
        <DrawBox key={i} r={{...b, x: b.x - dx * t, y: b.y - dy * t}} local={local} t0={10 + i * 10} />
      ))}
    </div>
  );
};

export const CutView: React.FC<{cut: Cut; local: number; len: number; first: boolean}> = ({cut, local, len, first}) => {
  const {fps} = useVideoConfig();
  const sIn = spring({frame: local, fps, config: {damping: 14, stiffness: 150}});
  const punch = interpolate(sIn, [0, 1], [0.86, 1]);
  const rotY = first && local < 0 ? 0 : (1 - sIn) * 16; // 3D 틸트 등장
  const slide = (1 - sIn) * 260;
  const blur = interpolate(local, [0, 6], [10, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}); // 모션블러 느낌(이미지에만)
  const W = Math.max(...cut.tiles.map((t) => t.crop.w));
  const H = cut.tiles.reduce((a, t) => a + t.crop.h, 0) + TILE_GAP * (cut.tiles.length - 1);
  const left = (S - W) / 2;
  const top = Math.max(0, (S - H) / 2);
  return (
    <div style={{position: 'absolute', inset: 0, perspective: 1600, perspectiveOrigin: '50% 50%'}}>
      <div style={{position: 'absolute', left, top, width: W, height: H, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: TILE_GAP, transform: `translateX(${slide}px) rotateY(${rotY}deg) scale(${punch})`, transformOrigin: '50% 50%', filter: `blur(${blur}px)`}}>
        {cut.tiles.map((tile, i) => (
          <TileView key={i} tile={tile} local={local} len={len} />
        ))}
        <LightSweep local={local} />
      </div>
    </div>
  );
};

// trend.mp4 스타일 민트 칩(카운트업)
export const CountChip: React.FC<{label: string; n?: number; suffix?: string; from: number; top?: number}> = ({label, n, suffix = '', from, top = 400}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < from) return null;
  const local = frame - from;
  const s = spring({frame: local, fps, config: {damping: 11, stiffness: 180}});
  const v = n === undefined ? undefined : Math.round(interpolate(local, [4, 34], [0, n], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top, display: 'flex', justifyContent: 'center', pointerEvents: 'none'}}>
      <div style={{padding: '10px 30px', borderRadius: 999, background: MINT, color: '#062018', fontFamily: FONT, fontWeight: 900, fontSize: 44, letterSpacing: -1, fontVariantNumeric: 'tabular-nums', boxShadow: '0 12px 36px rgba(111,240,214,.4)', transform: `scale(${interpolate(s, [0, 1], [0.6, 1])})`, opacity: Math.min(1, s * 1.5), whiteSpace: 'nowrap'}}>
        {label}{v !== undefined ? ` ${v.toLocaleString('ko-KR')}${suffix}` : ''}
      </div>
    </div>
  );
};

export const BigCaption: React.FC<{text: string; from: number; to: number; size?: number}> = ({text, from, to, size = 84}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < from || frame > to) return null;
  const local = frame - from;
  const inn = spring({frame: local, fps, config: {damping: 12, stiffness: 150}});
  const out = interpolate(frame, [to - 8, to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const rows = text.split('\n');
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: 118, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, opacity: Math.min(1, inn * 1.4) * out, transform: `scale(${interpolate(inn, [0, 1], [0.8, 1])})`, fontFamily: FONT, fontWeight: 900}}>
      {rows.map((row, r) => (
        <div key={r} style={{display: 'flex', alignItems: 'center', padding: '8px 26px', borderRadius: 22, background: 'rgba(4,7,10,.9)', boxShadow: '0 14px 40px rgba(0,0,0,.5)', fontSize: size, lineHeight: 1.2, letterSpacing: -2.5}}>
          {parse(row).map((tok, i) => (
            <Word key={`${r}-${i}`} tok={tok} idx={(r === 0 ? 0 : parse(rows[0]).length) + i} local={local} size={size} />
          ))}
        </div>
      ))}
    </div>
  );
};

const starts = (cuts: Cut[], cf: number) => {
  const out: number[] = [];
  let acc = 0;
  for (const c of cuts) {
    out.push(acc);
    acc += c.len ?? cf;
  }
  return out;
};

export const FlowCell: React.FC<FlowProps> = ({cuts, cutFrames, lines, dur, lineSplit, chip}) => {
  useFont();
  const frame = useCurrentFrame();
  const st = starts(cuts, cutFrames);
  let idx = 0;
  for (let i = 0; i < cuts.length; i++) if (frame >= st[i]) idx = i;
  const local = frame - st[idx];
  const len = cuts[idx].len ?? cutFrames;
  const fade = Math.min(
    interpolate(frame, [0, 5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [dur - 7, dur - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  const split = lineSplit ?? Math.round(dur * 0.38);
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden', opacity: fade}}>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(60% 60% at 50% 60%, rgba(111,240,214,.10), transparent 70%)'}} />
      <Sparkles frame={frame} seed={idx * 7} />
      {idx > 0 && local < 12 && (
        <div style={{position: 'absolute', inset: 0, transform: `translateX(${-local * 40}px) scale(${1 - local * 0.01})`, opacity: 1 - local / 12, filter: `blur(${local * 1.2}px)`}}>
          <CutView cut={cuts[idx - 1]} local={(cuts[idx - 1].len ?? cutFrames) + local} len={cuts[idx - 1].len ?? cutFrames} first={false} />
        </div>
      )}
      <CutView cut={cuts[idx]} local={local} len={len} first={idx === 0} />
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(7,11,15,.5) 0%, rgba(7,11,15,.12) 38%, rgba(7,11,15,0) 55%)', pointerEvents: 'none'}} />
      <BigCaption text={lines[0]} from={6} to={split - 4} />
      <BigCaption text={lines[1]} from={split} to={dur - 2} />
      {chip && <CountChip label={chip.label} n={chip.n} suffix={chip.suffix} from={split + 30} top={lines[1].includes(NL) ? 392 : 280} />}
      {/* 하단 진행선(돌아가는 느낌) */}
      <div style={{position: 'absolute', left: 60, right: 60, bottom: 46, height: 8, borderRadius: 4, background: 'rgba(255,255,255,.08)'}}>
        <div style={{width: `${(frame / dur) * 100}%`, height: '100%', borderRadius: 4, background: `linear-gradient(90deg, rgba(111,240,214,.3), ${MINT})`, boxShadow: '0 0 18px rgba(111,240,214,.7)'}} />
      </div>
    </AbsoluteFill>
  );
};

export const FLOW_BASE = {width: S, height: S, fps: 30};
const C88 = {file: 'cap/88.png', full: {w: 1577, h: 865}};
const C89 = {file: 'cap/89.png', full: {w: 1546, h: 482}};
const C90 = {file: 'cap/90.png', full: {w: 1572, h: 808}};
const C91 = {file: 'cap/91.png', full: {w: 1571, h: 897}};
const C92 = {file: 'cap/92.png', full: {w: 1607, h: 731}};
const C93 = {file: 'cap/93.png', full: {w: 1577, h: 831}};
const C94 = {file: 'cap/94.png', full: {w: 1654, h: 894}};
export const C95 = {file: 'cap/95.png', full: {w: 1641, h: 779}};

// ④ 앞에 붙는 자막제거 컷(BEFORE→AFTER 스캔 와이프) — 위에 단계바 타일, 아래에 비포/애프터 패널 영역
export const SUBCLEAN_CUT: Cut = {
  tiles: [
    {...C95, crop: {x: 0, y: 0, w: 1080, h: 110}},
    {...C95, crop: {x: 430, y: 130, w: 1080, h: 649}, wipe: {...C95, crop: {x: 430, y: 130, w: 1080, h: 649}}},
  ],
  len: 60,
};

// 타일 조합: 세로 합계 ≈ 1000~1080 (레터박스 없이 칸을 채움)
export const FLOWS: Record<string, FlowProps> = {
  // 박스 좌표는 격자 크롭으로 실측한 요소만(썸네일 1장·분석 카드 1장·스타일 카드 1장·타임라인 컷 1장). 못 잰 곳은 박스 없음.
  sq_1: {
    dur: 270,
    cutFrames: 54,
    lines: ['영상을 담으면', '장면마다 [뭐가 나오는지]'+NL+'AI가 싹 적어줌'],
    chip: {label: '담은 영상', n: 7, suffix: '개 → 장면 분석 완료'},
    cuts: [
      {tiles: [{...C88, crop: {x: 0, y: 0, w: 1080, h: 110}}, {...C89, crop: {x: 0, y: 90, w: 1080, h: 392}, pan: [-160, 0], boxes: [{x: 225, y: 60, w: 175, h: 230}]}, {...C88, crop: {x: 0, y: 500, w: 1080, h: 365}, pan: [80, 0], boxes: [{x: 340, y: 45, w: 305, h: 320}]}]},
      {tiles: [{...C89, crop: {x: 466, y: 60, w: 1080, h: 422}, pan: [-200, 0], boxes: [{x: 131, y: 90, w: 173, h: 230}]}, {...C90, crop: {x: 0, y: 0, w: 1080, h: 560}, pan: [120, 0]}]},
      {tiles: [{...C90, crop: {x: 300, y: 0, w: 1080, h: 808}, pan: [-140, 0]}, {...C88, crop: {x: 0, y: 190, w: 1080, h: 240}, pan: [200, 0]}]},
      {tiles: [{...C88, crop: {x: 497, y: 500, w: 1080, h: 365}, pan: [0, 0], boxes: [{x: 163, y: 45, w: 305, h: 320}]}, {...C90, crop: {x: 492, y: 100, w: 1080, h: 708}, pan: [-100, 0]}]},
      {tiles: [{...C88, crop: {x: 0, y: 0, w: 1080, h: 110}}, {...C89, crop: {x: 0, y: 90, w: 1080, h: 392}, pan: [-120, 0]}, {...C90, crop: {x: 0, y: 0, w: 1080, h: 560}, pan: [0, -100]}]},
    ],
  },
  sq_2: {
    dur: 270,
    cutFrames: 54,
    lines: ['잘 된 영상 구성 그대로', '{내 제품 대본}이'+NL+'자동으로'],
    chip: {label: '스타일 고르면 A안·B안', n: 2, suffix: '개 대본'},
    cuts: [
      {tiles: [{...C92, crop: {x: 0, y: 0, w: 1080, h: 110}}, {...C92, crop: {x: 0, y: 180, w: 1080, h: 551}, pan: [-140, 0]}, {...C91, crop: {x: 0, y: 0, w: 1080, h: 140}, pan: [100, 0]}]},
      {tiles: [{...C91, crop: {x: 0, y: 0, w: 1080, h: 897}, pan: [-160, 0], boxes: [{x: 685, y: 175, w: 205, h: 190}]}, {...C92, crop: {x: 0, y: 500, w: 1080, h: 150}, pan: [140, 0]}]},
      {tiles: [{...C91, crop: {x: 491, y: 140, w: 1080, h: 757}, pan: [0, -40], boxes: [{x: 194, y: 35, w: 205, h: 190}]}, {...C92, crop: {x: 400, y: 180, w: 1080, h: 260}, pan: [-120, 0]}]},
      {tiles: [{...C91, crop: {x: 0, y: 300, w: 1080, h: 597}, pan: [160, 0], boxes: [{x: 15, y: 340, w: 207, h: 235}]}, {...C92, crop: {x: 100, y: 500, w: 1080, h: 231}, pan: [-100, 0]}, {...C91, crop: {x: 300, y: 0, w: 1080, h: 140}}]},
      {tiles: [{...C92, crop: {x: 0, y: 0, w: 1080, h: 110}}, {...C92, crop: {x: 527, y: 180, w: 1080, h: 551}, pan: [-120, 0]}, {...C91, crop: {x: 200, y: 0, w: 1080, h: 140}, pan: [80, 0]}]},
    ],
  },
  sq_3: {
    dur: 270,
    cutFrames: 54,
    lines: ['대본 한 줄마다', '[딱 맞는 장면]이'+NL+'자동으로 착'],
    chip: {label: '컷', n: 27, suffix: '개 자동 배치'},
    cuts: [
      {tiles: [{...C93, crop: {x: 0, y: 80, w: 1080, h: 751}, pan: [-120, 0], boxes: [{x: 20, y: 20, w: 385, h: 630}]}, {...C94, crop: {x: 0, y: 380, w: 1080, h: 250}, pan: [200, 0]}]},
      {tiles: [{...C93, crop: {x: 497, y: 80, w: 1080, h: 751}, pan: [0, 0], boxes: [{x: 440, y: 115, w: 460, h: 22}, {x: 152, y: 175, w: 103, h: 180}]}, {...C94, crop: {x: 300, y: 380, w: 1080, h: 250}, pan: [-200, 0]}]},
      {tiles: [{...C94, crop: {x: 0, y: 0, w: 1080, h: 894}, pan: [-140, 0]}, {...C93, crop: {x: 497, y: 400, w: 1080, h: 130}, pan: [100, 0]}]},
      {tiles: [{...C94, crop: {x: 574, y: 300, w: 1080, h: 594}, pan: [0, -60]}, {...C93, crop: {x: 0, y: 80, w: 1080, h: 430}, pan: [-160, 0], boxes: [{x: 20, y: 20, w: 385, h: 400}]}]},
      {tiles: [{...C94, crop: {x: 0, y: 380, w: 1080, h: 514}, pan: [220, 0]}, {...C93, crop: {x: 497, y: 80, w: 1080, h: 510}, pan: [0, 0], boxes: [{x: 152, y: 175, w: 103, h: 180}]}]},
    ],
  },
};
