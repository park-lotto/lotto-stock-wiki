import React from 'react';
import {
  AbsoluteFill, Audio, OffthreadVideo, Img, Sequence, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, spring, random,
} from 'remotion';
import { BgFx, Glitch, Grain, EASE } from './fx';
import { C, F } from './theme2';

/* 숏템메이커 V2 광고 — CF 엔진 (2026-10-12 사장님 "광고처럼 화려하고 빠져들게")
   씬 = 문단 목록. 문단 길이는 TTS 문단 파일 실측(초). 문단 안의 hits(자막 덩어리)를 균등하게 나눠
   한 덩어리마다 컷을 바꾼다 — 컷마다 줌펀치·플래시·RGB 글리치·빛 줄기·흔들림이 자동으로 붙는다.
   한 씬의 연출 판단은 이 파일 하나에서만 한다(씬 파일은 데이터만 적는다). */

export type Hit = string | {
  t: string; style?: Style; accent?: string; sub?: string; img?: string; bg?: string;
  num?: number; unit?: string;              // style 'count' — 숫자 카운트업
  bars?: [string, number][];                // style 'bars' — 막대 그래프(마지막 막대가 주인공)
  vs?: [string, string];                    // style 'vs' — 왼쪽(나쁨) vs 오른쪽(숏템메이커)
  steps?: string[];                         // style 'flow' — 단계 흐름 화살표
};
export type Style = 'slam' | 'kinetic' | 'mega' | 'quote' | 'tag' | 'stack'
  | 'count' | 'bars' | 'vs' | 'neon' | 'flip' | 'flow';
export type Para = {
  dur: number;                    // 초
  bg?: string;                    // public 경로(영상)
  img?: string;                   // public 경로(이미지) — 화면 전체에 Ken Burns
  frame?: 'full' | 'phone' | 'screen';   // 영상을 어떻게 띄울지
  tint?: 'amber' | 'cyan' | 'red' | 'none' | 'mono' | 'monoWarm';
  hits: Hit[];
  hitAt?: number[];               // 덩어리 시작 비율(0~1) — 생략하면 균등
};

const FPS = 30;
export const sceneFrames = (P: Para[]) => Math.round(P.reduce((a, p) => a + p.dur, 0) * FPS) + 12;

const STROKE: React.CSSProperties = {
  WebkitTextStroke: '3px rgba(0,0,0,0.9)', paintOrder: 'stroke fill',
  textShadow: '0 10px 40px rgba(0,0,0,1), 0 0 20px rgba(0,0,0,0.9)',
};

/** 컷 들어올 때: 확 당겼다 놓기 + 흔들림 */
const Punch: React.FC<{ children: React.ReactNode; seed: number }> = ({ children, seed }) => {
  const f = useCurrentFrame();
  const s = interpolate(f, [0, 8], [1.18, 1], { extrapolateRight: 'clamp', easing: EASE.out });
  const sh = f < 10 ? (10 - f) * 2.2 : 0;
  const dx = sh * (random('x' + seed + f) - 0.5) * 2;
  const dy = sh * (random('y' + seed + f) - 0.5) * 2;
  const slow = interpolate(f, [8, 200], [1, 1.06], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ transform: 'translate(' + dx + 'px,' + dy + 'px) scale(' + s * slow + ')' }}>
      {children}
    </AbsoluteFill>
  );
};

/** 컷 경계 플래시 + 빛 줄기 */
const FlashSweep: React.FC<{ seed: number; color?: string }> = ({ seed, color = '#fff' }) => {
  const f = useCurrentFrame();
  const fl = interpolate(f, [0, 2, 7], [0.85, 0.5, 0], { extrapolateRight: 'clamp' });
  const x = interpolate(f, [0, 16], [-40, 140], { extrapolateRight: 'clamp', easing: EASE.out });
  const rot = random('r' + seed) > 0.5 ? 18 : -18;
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <AbsoluteFill style={{ background: color, opacity: fl, mixBlendMode: 'screen' }} />
      <div
        style={{
          position: 'absolute', top: '-30%', left: x + '%', width: '22%', height: '160%',
          transform: 'rotate(' + rot + 'deg)', opacity: f < 18 ? 0.55 : 0,
          background: 'linear-gradient(90deg, transparent, rgba(255,230,140,0.9), transparent)',
          mixBlendMode: 'screen', filter: 'blur(8px)',
        }}
      />
    </AbsoluteFill>
  );
};

/** 집중선 — 큰 글자 뒤에 */
const SpeedLines: React.FC<{ seed: number }> = ({ seed }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 4, 30], [0, 0.55, 0.25], { extrapolateRight: 'clamp' });
  const lines = Array.from({ length: 46 }, (_, i) => {
    const a = (i / 46) * 360 + random('a' + seed + i) * 6;
    const len = 300 + random('l' + seed + i + Math.floor(f / 2)) * 500;
    return (
      <div
        key={i}
        style={{
          position: 'absolute', left: 960, top: 540, width: len, height: 3 + random('w' + i) * 4,
          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.9))',
          transformOrigin: '0 50%', transform: 'rotate(' + a + 'deg) translateX(' + (520 - len * 0.1) + 'px)',
        }}
      />
    );
  });
  return <AbsoluteFill style={{ opacity: o, mixBlendMode: 'screen' }}>{lines}</AbsoluteFill>;
};

/** 불꽃 입자 — 터지는 순간 사방으로 */
const Burst: React.FC<{ seed: number; color?: string; at?: number }> = ({ seed, color = C.gold, at = 0 }) => {
  const f = useCurrentFrame() - at;
  if (f < 0 || f > 40) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {Array.from({ length: 36 }, (_, i) => {
        const a = random('ba' + seed + i) * Math.PI * 2;
        const v = 14 + random('bv' + seed + i) * 26;
        const d = v * f * (1 - f / 80);
        const o = interpolate(f, [0, 30, 40], [1, 0.6, 0]);
        const s = 6 + random('bs' + seed + i) * 10;
        return (
          <div key={i} style={{
            position: 'absolute', left: 960 + Math.cos(a) * d, top: 540 + Math.sin(a) * d + f * f * 0.15,
            width: s, height: s, borderRadius: s, background: color, opacity: o, boxShadow: '0 0 18px ' + color,
          }} />
        );
      })}
      {[0, 6].map((dl) => {
        const g = f - dl;
        const r = interpolate(g, [0, 24], [40, 900], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: EASE.out });
        return (
          <div key={dl} style={{
            position: 'absolute', left: 960 - r, top: 540 - r, width: r * 2, height: r * 2, borderRadius: r,
            border: '6px solid ' + color, opacity: interpolate(g, [0, 24], [0.9, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
          }} />
        );
      })}
    </AbsoluteFill>
  );
};

/** 숫자 카운트업 — 숫자 굴러가며 커지고 마지막에 폭발 */
const CountBig: React.FC<{ h: any; seed: number }> = ({ h, seed }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const N = 28;
  const v = Math.round(interpolate(f, [0, N], [0, h.num], { extrapolateRight: 'clamp', easing: EASE.out }));
  const done = f >= N;
  const pop = spring({ frame: f - N, fps, config: { damping: 8, mass: 0.6 } });
  const sc = done ? 1 + (1 - pop) * 0.25 + 0.04 : interpolate(f, [0, N], [0.6, 1]);
  const jit = !done ? (random('j' + f) - 0.5) * 8 : 0;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'radial-gradient(circle, rgba(250,204,21,0.18), rgba(0,0,0,0.8) 70%)' }}>
      <SpeedLines seed={seed} />
      <Burst seed={seed} at={N} />
      <div style={{ textAlign: 'center', transform: 'translateX(' + jit + 'px) scale(' + sc + ')' }}>
        {h.sub ? <div style={{ font: '800 44px ' + F.sans, color: C.paper, letterSpacing: 8, marginBottom: 6 }}>{h.sub}</div> : null}
        <div style={{
          font: '900 260px/1 ' + F.sans, letterSpacing: -10,
          background: 'linear-gradient(180deg, #fff6c2 0%, #facc15 45%, #f59e0b 100%)', WebkitBackgroundClip: 'text', color: 'transparent',
          filter: 'drop-shadow(0 0 40px rgba(250,204,21,0.7)) drop-shadow(0 14px 30px rgba(0,0,0,0.9))',
        }}>
          {v.toLocaleString()}<span style={{ fontSize: 110 }}>{h.unit || ''}</span>
        </div>
        {h.t ? <div style={{ font: '900 64px ' + F.sans, color: C.paper, marginTop: 10, ...STROKE }}>{h.t}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

/** 막대 그래프 — 차례로 솟고 마지막 막대가 금색으로 터진다 */
const Bars: React.FC<{ h: any; seed: number }> = ({ h, seed }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const data: [string, number][] = h.bars;
  const max = Math.max(...data.map((d) => d[1]));
  const last = data.length - 1;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'rgba(0,0,0,0.6)' }}>
      {h.t ? <div style={{ font: '900 66px ' + F.sans, color: C.paper, marginBottom: 40, ...STROKE }}>{h.t}</div> : null}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 60, height: 560 }}>
        {data.map(([k, v], i) => {
          const p = spring({ frame: f - 6 - i * 8, fps, config: { damping: 12, mass: 0.7 } });
          const hero = i === last;
          return (
            <div key={k} style={{ textAlign: 'center', width: 210 }}>
              <div style={{ font: '900 54px ' + F.sans, color: hero ? C.gold : C.paper, opacity: p }}>{Math.round(v * Math.min(1, p)).toLocaleString()}{h.unit || ''}</div>
              <div style={{
                height: (v / max) * 430 * p, marginTop: 10, borderRadius: '16px 16px 0 0',
                background: hero ? 'linear-gradient(180deg,#fff2a8,#facc15 40%,#d97706)' : 'linear-gradient(180deg,rgba(255,255,255,0.45),rgba(255,255,255,0.12))',
                boxShadow: hero ? '0 0 80px rgba(250,204,21,0.8)' : 'none',
              }} />
              <div style={{ font: '900 50px ' + F.sans, color: hero ? C.gold : C.paper, marginTop: 14 }}>{k}</div>
            </div>
          );
        })}
      </div>
      <Burst seed={seed} at={6 + last * 8 + 14} />
    </AbsoluteFill>
  );
};

/** VS — 화면이 갈라지며 왼쪽은 회색·빨강 X, 오른쪽은 금색 */
const Versus: React.FC<{ h: any; seed: number }> = ({ h, seed }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const l = spring({ frame: f, fps, config: { damping: 14 } });
  const r = spring({ frame: f - 10, fps, config: { damping: 10 } });
  const x = spring({ frame: f - 22, fps, config: { damping: 8 } });
  const box = (txt: string, good: boolean, p: number, dir: number): React.ReactNode => (
    <div style={{
      flex: 1, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: good ? 'linear-gradient(135deg, rgba(250,204,21,0.35), rgba(0,0,0,0.6))' : 'rgba(30,30,36,0.85)',
      transform: 'translateX(' + (1 - p) * 900 * dir + 'px)',
    }}>
      <div style={{ font: '900 96px/1.2 ' + F.sans, color: good ? C.gold : '#9ca3af', textAlign: 'center', whiteSpace: 'pre-line', ...STROKE,
        filter: good ? 'drop-shadow(0 0 30px rgba(250,204,21,0.6))' : 'grayscale(1)' }}>{txt}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{ flexDirection: 'row' }}>
      {box(h.vs[0], false, l, -1)}
      {box(h.vs[1], true, r, 1)}
      <div style={{ position: 'absolute', left: 960 - 6, top: 0, width: 12, height: '100%', background: C.gold, boxShadow: '0 0 40px ' + C.gold }} />
      <div style={{ position: 'absolute', left: 860, top: 440, width: 200, height: 200, borderRadius: 100, background: '#111', border: '6px solid ' + C.gold,
        display: 'flex', alignItems: 'center', justifyContent: 'center', font: '900 90px ' + F.sans, color: C.gold, transform: 'scale(' + r + ') rotate(' + (1 - r) * 180 + 'deg)' }}>VS</div>
      <div style={{ position: 'absolute', left: 300, top: 300, font: '900 480px/1 ' + F.sans, color: 'rgba(248,113,113,0.85)', transform: 'scale(' + (2 - x) + ')', opacity: Math.min(1, x) }}>✕</div>
      <Burst seed={seed} at={10} />
    </AbsoluteFill>
  );
};

/** 단계 흐름 — 카드가 차례로 날아와 화살표로 이어진다 */
const Flow: React.FC<{ h: any }> = ({ h }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const st: string[] = h.steps;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'rgba(0,0,0,0.6)' }}>
      {h.t ? <div style={{ font: '900 64px ' + F.sans, color: C.gold, marginBottom: 50, ...STROKE }}>{h.t}</div> : null}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        {st.map((s, i) => {
          const p = spring({ frame: f - i * 9, fps, config: { damping: 11, mass: 0.6 } });
          const lastOne = i === st.length - 1;
          return (
            <React.Fragment key={i}>
              {i ? <div style={{ font: '900 70px ' + F.sans, color: C.gold, opacity: p }}>→</div> : null}
              <div style={{
                padding: '30px 34px', borderRadius: 22, font: '900 54px ' + F.sans, whiteSpace: 'pre-line', textAlign: 'center',
                background: lastOne ? C.gold : 'rgba(255,255,255,0.1)', color: lastOne ? '#111' : C.paper,
                border: '3px solid ' + (lastOne ? C.gold : 'rgba(255,255,255,0.3)'),
                boxShadow: lastOne ? '0 0 60px rgba(250,204,21,0.7)' : 'none',
                transform: 'translateY(' + (1 - p) * 160 + 'px) rotate(' + (1 - p) * 12 + 'deg)', opacity: p,
              }}>{s}</div>
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** 네온 — 깜빡이며 켜지는 네온 간판 글자 */
const Neon: React.FC<{ h: any }> = ({ h }) => {
  const f = useCurrentFrame();
  const flick = f < 14 ? (random('n' + f) > 0.45 ? 1 : 0.15) : 1 + Math.sin(f / 5) * 0.06;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'rgba(0,0,0,0.65)' }}>
      {h.t.split('\n').map((l: string, i: number) => (
        <div key={i} style={{
          font: '900 140px/1.15 ' + F.sans, color: '#fffbe6', opacity: flick,
          textShadow: '0 0 10px #fff, 0 0 30px ' + C.gold + ', 0 0 60px ' + C.gold + ', 0 0 120px #f59e0b',
        }}>{l}</div>
      ))}
    </AbsoluteFill>
  );
};

/** 플립 — 글자 하나하나 3D로 뒤집히며 등장 */
const Flip: React.FC<{ h: any }> = ({ h }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  let n = 0;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'rgba(0,0,0,0.45)', perspective: 1200 }}>
      {h.t.split('\n').map((l: string, i: number) => (
        <div key={i} style={{ font: '900 130px/1.2 ' + F.sans, ...STROKE }}>
          {Array.from(l).map((ch, j) => {
            const k = n++;
            const p = spring({ frame: f - k * 1.6, fps, config: { damping: 12, mass: 0.5 } });
            const hot = h.accent && l.indexOf(h.accent) >= 0 && j >= l.indexOf(h.accent) && j < l.indexOf(h.accent) + h.accent.length;
            return (
              <span key={j} style={{ display: 'inline-block', color: hot ? C.gold : C.paper, transform: 'rotateX(' + (1 - p) * 100 + 'deg)', opacity: Math.min(1, p * 1.3), minWidth: ch === ' ' ? 34 : undefined }}>
                {ch}
              </span>
            );
          })}
        </div>
      ))}
    </AbsoluteFill>
  );
};

/** 글자 — 스타일 다섯 가지를 돌려 쓴다 */
const Words: React.FC<{ h: Exclude<Hit, string>; style: Style; seed: number }> = ({ h, style, seed }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 11, mass: 0.6 } });
  const acc = h.accent;
  const paint = (s: string) => {
    if (!acc || !s.includes(acc)) return s;
    const [a, b] = s.split(acc);
    return (<>{a}<span style={{ color: C.gold }}>{acc}</span>{b}</>);
  };
  if (style === 'count') return <CountBig h={h} seed={seed} />;
  if (style === 'bars') return <Bars h={h} seed={seed} />;
  if (style === 'vs') return <Versus h={h} seed={seed} />;
  if (style === 'flow') return <Flow h={h} />;
  if (style === 'neon') return <Neon h={h} />;
  if (style === 'flip') return <Flip h={h} />;
  const lines = h.t.split('\n');
  if (style === 'mega') {
    const s = interpolate(f, [0, 6], [2.2, 1], { extrapolateRight: 'clamp', easing: EASE.slam });
    return (
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <SpeedLines seed={seed} />
        <AbsoluteFill style={{ background: 'radial-gradient(circle, rgba(0,0,0,0.15), rgba(0,0,0,0.75))' }} />
        <Burst seed={seed} at={4} />
        <div style={{ textAlign: 'center', transform: 'scale(' + s + ') rotate(' + (1 - p) * -4 + 'deg)' }}>
          {h.sub ? <div style={{ font: '800 40px ' + F.sans, color: C.gold, letterSpacing: 10, marginBottom: 10 }}>{h.sub}</div> : null}
          {lines.map((l, i) => (
            <div key={i} style={{ font: '900 190px/1.05 ' + F.sans, color: i === lines.length - 1 ? C.gold : C.paper, ...STROKE, letterSpacing: -6,
              ...(i === lines.length - 1 && lines.length > 1 ? { background: 'linear-gradient(180deg,#fff6c2,#facc15 50%,#f59e0b)', WebkitBackgroundClip: 'text', color: 'transparent', WebkitTextStroke: '0px', filter: 'drop-shadow(0 0 30px rgba(250,204,21,0.6)) drop-shadow(0 10px 20px #000)' } : {}) }}>
              {paint(l)}
            </div>
          ))}
        </div>
      </AbsoluteFill>
    );
  }
  if (style === 'quote') {
    return (
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'rgba(0,0,0,0.45)' }}>
        <div style={{ textAlign: 'center', transform: 'scale(' + (0.8 + p * 0.2) + ')', opacity: p }}>
          <div style={{ font: '900 220px/0.6 Georgia, serif', color: C.gold, opacity: 0.9 }}>“</div>
          {lines.map((l, i) => (
            <div key={i} style={{ font: 'italic 900 104px/1.25 ' + F.sans, color: C.paper, ...STROKE }}>{paint(l)}</div>
          ))}
        </div>
      </AbsoluteFill>
    );
  }
  if (style === 'tag') {
    // 아래 굵은 띠 자막(영상 위에 얹는 용)
    const w = interpolate(f, [0, 8], [0, 100], { extrapolateRight: 'clamp', easing: EASE.out });
    return (
      <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 90 }}>
        <div style={{ position: 'relative', padding: '18px 48px' }}>
          <div style={{ position: 'absolute', inset: 0, background: C.gold, transform: 'skewX(-8deg)', clipPath: 'inset(0 ' + (100 - w) + '% 0 0)' }} />
          <div style={{ position: 'relative', font: '900 72px ' + F.sans, color: '#111', opacity: f > 4 ? 1 : 0 }}>{h.t}</div>
        </div>
      </AbsoluteFill>
    );
  }
  if (style === 'stack') {
    return (
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'rgba(0,0,0,0.5)' }}>
        <div>
          {lines.map((l, i) => {
            const q = spring({ frame: f - i * 7, fps, config: { damping: 12, mass: 0.6 } });
            return (
              <div key={i} style={{ font: '900 110px/1.2 ' + F.sans, color: i === lines.length - 1 ? C.gold : C.paper, ...STROKE, transform: 'translateX(' + (1 - q) * -200 + 'px)', opacity: q }}>
                {l}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    );
  }
  if (style === 'kinetic') {
    let n = 0;
    return (
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'rgba(0,0,0,0.35)' }}>
        <div style={{ textAlign: 'center' }}>
          {lines.map((l, i) => (
            <div key={i} style={{ font: '900 116px/1.2 ' + F.sans, ...STROKE }}>
              {l.split(' ').map((w, j) => {
                const k = n++;
                const q = spring({ frame: f - k * 2.5, fps, config: { damping: 10, mass: 0.5 } });
                const hot = acc && w.includes(acc.split(' ')[0]);
                return (
                  <span key={j} style={{ display: 'inline-block', marginRight: 26, color: hot ? C.gold : C.paper, opacity: q, transform: 'translateY(' + (1 - q) * 90 + 'px) scale(' + (0.6 + q * 0.4) + ')' }}>
                    {w}
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </AbsoluteFill>
    );
  }
  // slam
  const s = interpolate(f, [0, 7], [1.6, 1], { extrapolateRight: 'clamp', easing: EASE.slam });
  const bl = interpolate(f, [0, 7], [20, 0], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', background: 'rgba(0,0,0,0.4)' }}>
      <div style={{ textAlign: 'center', transform: 'scale(' + s + ')', filter: 'blur(' + bl + 'px)' }}>
        {h.sub ? <div style={{ font: '800 38px ' + F.sans, color: C.gold, letterSpacing: 10, marginBottom: 14 }}>{h.sub}</div> : null}
        {lines.map((l, i) => (
          <div key={i} style={{ font: '900 132px/1.15 ' + F.sans, color: C.paper, ...STROKE }}>{paint(l)}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/** 배경 — 영상(전체/폰/모니터) 또는 이미지 */
const Back: React.FC<{ p: Para }> = ({ p }) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  if (p.img) {
    const s = interpolate(f, [0, durationInFrames], [1.05, 1.22]);
    return (
      <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
        <Img src={staticFile(p.img)} style={{ width: '100%', height: '100%', objectFit: 'contain', transform: 'scale(' + s + ')' }} />
      </AbsoluteFill>
    );
  }
  if (!p.bg) return <AbsoluteFill style={{ background: C.ink }} />;
  if (p.frame === 'screen' || p.frame === 'phone') {
    const phone = p.frame === 'phone';
    const rot = interpolate(f, [0, durationInFrames], [7, 2]);
    return (
      <AbsoluteFill>
        <BgFx src={p.bg} tint={p.tint || 'amber'} dim={0.5} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', perspective: 1800 }}>
          <div
            style={{
              width: phone ? 560 : 1500, height: phone ? 996 : 844, borderRadius: phone ? 36 : 18, overflow: 'hidden',
              boxShadow: '0 50px 140px rgba(0,0,0,0.9), 0 0 0 3px rgba(250,204,21,0.5)',
              transform: 'rotateY(' + -rot + 'deg) rotateX(' + rot * 0.4 + 'deg)',
            }}
          >
            <OffthreadVideo src={staticFile(p.bg)} muted style={{ width: '100%', height: '100%', objectFit: 'cover', filter: p.tint === 'mono' ? 'grayscale(1) contrast(1.2)' : 'none' }} />
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
    );
  }
  return <BgFx src={p.bg} tint={p.tint || 'amber'} dim={0.75} speed={1.8} />;
};

export const Scene: React.FC<{ voice?: string; paras: Para[] }> = ({ voice, paras }) => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: C.ink }}>
      {voice ? <Audio src={staticFile(voice)} /> : null}
      {paras.map((p, i) => {
        const from = Math.round(at * FPS);
        at += p.dur;
        const len = Math.round(at * FPS) - from;
        const marks = p.hitAt || p.hits.map((_, k) => k / p.hits.length);
        return (
          <Sequence key={i} from={from} durationInFrames={len}>
            <Back p={p} />
            {p.hits.map((raw, k) => {
              const h = typeof raw === 'string' ? { t: raw } : raw;
              const s0 = Math.round(marks[k] * len);
              const s1 = k + 1 < p.hits.length ? Math.round(marks[k + 1] * len) : len;
              const style: Style = h.style || (['slam', 'flip', 'mega', 'kinetic', 'neon', 'stack'] as Style[])[(i + k) % 6];
              const seed = i * 31 + k;
              return (
                <Sequence key={k} from={s0} durationInFrames={Math.max(1, s1 - s0)}>
                  {h.img || h.bg ? <Punch seed={seed + 7}><Back p={{ ...p, img: h.img, bg: h.bg || p.bg, frame: h.img ? undefined : p.frame }} /></Punch> : null}
                  {h.t || h.vs || h.bars || h.steps || h.num !== undefined ? (
                    <Glitch at={[0, 1]}>
                      <Punch seed={seed}><Words h={h} style={style} seed={seed} /></Punch>
                    </Glitch>
                  ) : null}
                  <FlashSweep seed={seed} />
                </Sequence>
              );
            })}
          </Sequence>
        );
      })}
      <Grain opacity={0.1} />
      <AbsoluteFill style={{ boxShadow: 'inset 0 0 260px rgba(0,0,0,0.85)', pointerEvents: 'none' }} />
    </AbsoluteFill>
  );
};
