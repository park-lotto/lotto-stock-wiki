import React from 'react';
import {
  AbsoluteFill, OffthreadVideo, Loop, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, random,
} from 'remotion';
import { C, F } from './theme2';

/* V2 광고 배경 6종 + 고급 아이콘 배지 (2026-10-12 사장님 "3D 벽만 쓰면 식상 / 이모티콘 유치")
   배경은 문단마다 돌려 쓴다 — 같은 배경이 연속으로 나오지 않게 씬 데이터에서 back 을 지정한다. */

export type BackKind = 'wall' | 'ring' | 'mosaic' | 'hero' | 'split' | 'aurora';
const WALL = (i: number) => 'shottem2/v2wall/w' + String(((i % 60) + 60) % 60).padStart(2, '0') + '.mp4';

const Tile: React.FC<{ i: number; w: number; r?: number; style?: React.CSSProperties }> = ({ i, w, r = 0.08, style }) => (
  <div style={{ width: w, height: (w * 16) / 9, borderRadius: w * r, overflow: 'hidden', flexShrink: 0, boxShadow: '0 20px 60px rgba(0,0,0,0.8)', ...style }}>
    <Loop durationInFrames={240}><OffthreadVideo src={staticFile(WALL(i))} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} /></Loop>
  </div>
);

const Vignette: React.FC<{ dim: number }> = ({ dim }) => (
  <>
    <AbsoluteFill style={{ background: 'rgba(0,0,0,' + dim + ')' }} />
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.9) 100%)' }} />
  </>
);

/** 1. 기울어진 3D 벽 — 기둥이 엇갈려 흐른다 */
const Wall: React.FC<{ seed: number; dim: number }> = ({ seed, dim }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: '#050507', overflow: 'hidden', perspective: 1600 }}>
      <div style={{ position: 'absolute', left: '50%', top: '50%', display: 'flex', gap: 24, transform: 'translate(-50%,-50%) rotateX(22deg) rotateZ(-10deg) scale(1.15)' }}>
        {Array.from({ length: 7 }, (_, c) => {
          const y = ((f * (1.4 + (c % 3) * 0.35) * (c % 2 ? 1 : -1)) % 900) - 450;
          return <div key={c} style={{ display: 'flex', flexDirection: 'column', gap: 24, transform: 'translateY(' + y + 'px)' }}>
            {Array.from({ length: 6 }, (_, r) => <Tile key={r} i={seed * 7 + c * 6 + r} w={250} />)}
          </div>;
        })}
      </div>
      <Vignette dim={dim} />
    </AbsoluteFill>
  );
};

/** 2. 회전 고리 — 폰들이 원통 위에서 천천히 돈다(정면 하나가 크게 빛남) */
const Ring: React.FC<{ seed: number; dim: number }> = ({ seed, dim }) => {
  const f = useCurrentFrame();
  const n = 12;
  const R = 1100;
  return (
    <AbsoluteFill style={{ background: 'radial-gradient(circle at 50% 60%, #1d1606, #030304 70%)', perspective: 2200, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: '50%', top: '50%', transformStyle: 'preserve-3d', transform: 'translate(-50%,-50%) translateZ(-' + R + 'px) rotateX(-6deg) rotateY(' + f * 0.35 + 'deg)' }}>
        {Array.from({ length: n }, (_, i) => (
          <div key={i} style={{ position: 'absolute', left: -150, top: -267, transform: 'rotateY(' + (i * 360) / n + 'deg) translateZ(' + R + 'px)' }}>
            <Tile i={seed * 5 + i} w={300} style={{ border: '3px solid rgba(250,204,21,0.35)' }} />
          </div>
        ))}
      </div>
      <Vignette dim={dim} />
    </AbsoluteFill>
  );
};

/** 3. 모자이크 줌아웃 — 한 칸에서 시작해 수십 칸으로 멀어진다 */
const Mosaic: React.FC<{ seed: number; dim: number }> = ({ seed, dim }) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const s = interpolate(f, [0, Math.min(durationInFrames, 150)], [3.2, 1], { extrapolateRight: 'clamp', easing: (x) => 1 - Math.pow(1 - x, 3) });
  const cols = 12;
  return (
    <AbsoluteFill style={{ background: '#030304', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: '50%', top: '50%', display: 'grid', gridTemplateColumns: 'repeat(' + cols + ', 150px)', gap: 12, transform: 'translate(-50%,-50%) scale(' + s + ')' }}>
        {Array.from({ length: cols * 3 }, (_, i) => <Tile key={i} i={seed * 3 + i} w={150} r={0.06} />)}
      </div>
      <Vignette dim={dim} />
    </AbsoluteFill>
  );
};

/** 4. 히어로 — 영상 하나를 화면 가득, 금·흑 듀오톤 + 빛 번짐 */
const Hero: React.FC<{ seed: number; dim: number; src?: string }> = ({ seed, dim, src }) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const s = interpolate(f, [0, durationInFrames], [1.15, 1.35]);
  const leak = 0.35 + Math.sin(f / 18) * 0.15;
  return (
    <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
      <Loop durationInFrames={240}><OffthreadVideo src={staticFile(src || WALL(seed))} muted style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scale(' + s + ')', filter: 'grayscale(1) contrast(1.25) brightness(0.7) blur(2px)' }} /></Loop>
      <AbsoluteFill style={{ background: 'linear-gradient(120deg, rgba(250,204,21,0.55), rgba(120,60,0,0.35) 50%, rgba(0,0,0,0.6))', mixBlendMode: 'color' }} />
      <AbsoluteFill style={{ background: 'radial-gradient(circle at ' + (20 + Math.sin(f / 40) * 15) + '% 30%, rgba(255,200,90,' + leak + '), transparent 45%)', mixBlendMode: 'screen' }} />
      <Vignette dim={dim * 0.8} />
    </AbsoluteFill>
  );
};

/** 5. 분할 패널 — 세로 3칸이 차례로 열리며 서로 다른 영상 */
const Split: React.FC<{ seed: number; dim: number }> = ({ seed, dim }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: '#000', flexDirection: 'row', gap: 10 }}>
      {[0, 1, 2].map((k) => {
        const p = spring({ frame: f - k * 6, fps, config: { damping: 18 } });
        return (
          <div key={k} style={{ flex: 1, overflow: 'hidden', clipPath: 'inset(' + (1 - p) * 50 + '% 0 ' + (1 - p) * 50 + '% 0)' }}>
            <Loop durationInFrames={240}><OffthreadVideo src={staticFile(WALL(seed * 3 + k))} muted style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scale(' + (1.1 + k * 0.03) + ') translateY(' + (k % 2 ? -1 : 1) * f * 0.3 + 'px)' }} /></Loop>
          </div>
        );
      })}
      <Vignette dim={dim} />
    </AbsoluteFill>
  );
};

/** 6. 오로라 — 움직이는 금빛 그라데이션 + 떠다니는 빛 입자(추상) */
const Aurora: React.FC<{ seed: number; dim: number }> = ({ seed }) => {
  const f = useCurrentFrame();
  const a = f / 60;
  return (
    <AbsoluteFill style={{ background: '#05060a', overflow: 'hidden' }}>
      {[0, 1, 2].map((k) => (
        <div key={k} style={{
          position: 'absolute', width: 1400, height: 1400, borderRadius: 700, filter: 'blur(140px)', opacity: 0.55,
          left: 260 + Math.sin(a + k * 2.1) * 500 - 700 + k * 400, top: 300 + Math.cos(a * 0.8 + k) * 300 - 700,
          background: ['#f59e0b', '#7c3aed', '#facc15'][k],
        }} />
      ))}
      {Array.from({ length: 50 }, (_, i) => {
        const x = random('ax' + seed + i) * 1920;
        const y = (random('ay' + seed + i) * 1200 - f * (0.5 + random('as' + i))) % 1200;
        return <div key={i} style={{ position: 'absolute', left: x, top: (y + 1200) % 1200 - 60, width: 4 + random('ar' + i) * 6, height: 4 + random('ar' + i) * 6, borderRadius: 10, background: '#fff6c2', opacity: 0.5, boxShadow: '0 0 12px #facc15' }} />;
      })}
      <AbsoluteFill style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)', backgroundSize: '80px 80px', transform: 'perspective(800px) rotateX(55deg) translateY(' + ((f * 2) % 80) + 'px) scale(2)', transformOrigin: '50% 100%', top: 400 }} />
    </AbsoluteFill>
  );
};

export const Backdrop: React.FC<{ kind: BackKind; seed?: number; dim?: number; src?: string }> = ({ kind, seed = 0, dim = 0.45, src }) => {
  if (kind === 'ring') return <Ring seed={seed} dim={dim} />;
  if (kind === 'mosaic') return <Mosaic seed={seed} dim={dim} />;
  if (kind === 'hero') return <Hero seed={seed} dim={dim} src={src} />;
  if (kind === 'split') return <Split seed={seed} dim={dim} />;
  if (kind === 'aurora') return <Aurora seed={seed} dim={dim} />;
  return <Wall seed={seed} dim={dim} />;
};

/* ── 고급 아이콘 배지 — 금속 금 그라데이션 원판 + 선 아이콘(직접 그린 SVG) ── */
const P: Record<string, React.ReactNode> = {
  coin: (<><circle cx="12" cy="12" r="8" /><path d="M9.5 9.5c.5-1 1.5-1.5 2.5-1.5 1.7 0 2.8 1 2.8 2.2 0 2.6-5.3 1.4-5.3 4 0 1.2 1.2 2 2.8 2 1.1 0 2-.5 2.6-1.4M12 6.5v1.5M12 16v1.5" /></>),
  clock: (<><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>),
  flame: (<path d="M12 21c-3.9 0-6.5-2.6-6.5-6.2 0-3.1 2.1-5 3.4-7 .4 1.6 1.3 2.6 2.4 3 0-3 1.3-5.6 3.7-7.8.2 3.3 3.5 5.6 3.5 10.5C18.5 18.6 15.9 21 12 21z" />),
  trend: (<><path d="M3.5 17l5.5-5.5 3.5 3.5 7-7" /><path d="M14.5 8h5v5" /></>),
  heart: (<path d="M12 20s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.4 4.3 4.3 0 0 1 19.5 10c0 5.4-7.5 10-7.5 10z" />),
  calendar: (<><rect x="4" y="5.5" width="16" height="14.5" rx="2.5" /><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4M9 14.5l2 2 4-4" /></>),
  spark: (<path d="M12 3.5l1.9 5.6 5.6 1.9-5.6 1.9L12 18.5l-1.9-5.6L4.5 11l5.6-1.9z" />),
  bolt: (<path d="M13 3L5.5 13.5h6L10.5 21 18.5 10h-6z" />),
  gift: (<><rect x="4" y="9" width="16" height="11" rx="1.5" /><path d="M3.5 9h17v-3h-17zM12 6v14M12 6C10 2.5 6.5 3.5 7.5 6M12 6c2-3.5 5.5-2.5 4.5 0" /></>),
  user: (<><circle cx="12" cy="8.5" r="3.8" /><path d="M4.5 20c.8-4 3.8-6 7.5-6s6.7 2 7.5 6" /></>),
  crown: (<path d="M4 17.5L3 7.5l5 4 4-6.5 4 6.5 5-4-1 10z M4.5 20.5h15" />),
  rocket: (<><path d="M12 15.5l-3.5-3.5C10.5 6.5 14 4 20 4c0 6-2.5 9.5-8 11.5z" /><path d="M8.5 12H5l2.5-3.5H11M12 15.5V19l3.5-2.5V13M5.5 18.5c1-2 2.2-2.6 3.5-2.5" /></>),
};
export type IconName = keyof typeof P;

export const IconBadge: React.FC<{ name: IconName; size?: number; delay?: number }> = ({ name, size = 150, delay = 0 }) => {
  const f = useCurrentFrame() - delay;
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 10, mass: 0.6 } });
  const shine = interpolate(f % 70, [0, 25], [-120, 220], { extrapolateRight: 'clamp' });
  if (f < 0) return null;
  return (
    <div style={{ width: size, height: size, position: 'relative', transform: 'scale(' + p + ') rotate(' + (1 - p) * -40 + 'deg)' }}>
      <div style={{
        position: 'absolute', inset: 0, borderRadius: size, overflow: 'hidden',
        background: 'conic-gradient(from 210deg, #fff3c4, #facc15, #b45309, #fde68a, #f59e0b, #fff3c4)',
        boxShadow: '0 0 0 ' + size * 0.03 + 'px rgba(255,255,255,0.35) inset, 0 ' + size * 0.08 + 'px ' + size * 0.25 + 'px rgba(0,0,0,0.7), 0 0 ' + size * 0.4 + 'px rgba(250,204,21,0.45)',
      }}>
        <div style={{ position: 'absolute', inset: size * 0.09, borderRadius: size, background: 'radial-gradient(circle at 35% 30%, #2b2112, #0b0906 70%)', boxShadow: 'inset 0 4px 12px rgba(0,0,0,0.9)' }} />
        <div style={{ position: 'absolute', top: 0, bottom: 0, width: size * 0.25, left: shine + '%', background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.55), transparent)', transform: 'skewX(-20deg)' }} />
      </div>
      <svg viewBox="0 0 24 24" style={{ position: 'absolute', inset: size * 0.24, width: size * 0.52, height: size * 0.52, filter: 'drop-shadow(0 0 8px rgba(250,204,21,0.8))' }}
        fill="none" stroke="url(#gg)" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
        <defs><linearGradient id="gg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff7d1" /><stop offset="1" stopColor="#f59e0b" /></linearGradient></defs>
        {P[name]}
      </svg>
    </div>
  );
};

/** 단어 → 아이콘(자막에서 씀) */
export const ICON_RULES: [RegExp, IconName][] = [
  [/수익|매출|돈|벌|원\b|만 원|치킨값|용돈/, 'coin'], [/시간|세 시간|90시간|오래/, 'clock'], [/조회수|터지|터진|떡상/, 'flame'],
  [/성장|늘어|올라|오르/, 'trend'], [/엄마|어머니|부모님|가족/, 'heart'], [/매일|한 달|59일|일/, 'calendar'],
  [/대박|미친|소름/, 'spark'], [/빠르|순식간|딸깍|바로/, 'bolt'], [/무료|선물|혜택/, 'gift'], [/회원|50대|60대|연령대/, 'user'],
  [/제일|최고|셉니다|1기/, 'crown'], [/V2|V3|진화|업데이트/, 'rocket'],
];
