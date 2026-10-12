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

export type Hit = string | { t: string; style?: Style; accent?: string; sub?: string; img?: string; bg?: string };
export type Style = 'slam' | 'kinetic' | 'mega' | 'quote' | 'tag' | 'stack';
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
  const lines = h.t.split('\n');
  if (style === 'mega') {
    const s = interpolate(f, [0, 6], [2.2, 1], { extrapolateRight: 'clamp', easing: EASE.slam });
    return (
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <SpeedLines seed={seed} />
        <AbsoluteFill style={{ background: 'radial-gradient(circle, rgba(0,0,0,0.15), rgba(0,0,0,0.75))' }} />
        <div style={{ textAlign: 'center', transform: 'scale(' + s + ') rotate(' + (1 - p) * -4 + 'deg)' }}>
          {h.sub ? <div style={{ font: '800 40px ' + F.sans, color: C.gold, letterSpacing: 10, marginBottom: 10 }}>{h.sub}</div> : null}
          {lines.map((l, i) => (
            <div key={i} style={{ font: '900 190px/1.05 ' + F.sans, color: i === lines.length - 1 ? C.gold : C.paper, ...STROKE, letterSpacing: -6 }}>
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
              const style: Style = h.style || (['slam', 'kinetic', 'mega', 'stack'] as Style[])[(i + k) % 4];
              const seed = i * 31 + k;
              return (
                <Sequence key={k} from={s0} durationInFrames={Math.max(1, s1 - s0)}>
                  {h.img || h.bg ? <Punch seed={seed + 7}><Back p={{ ...p, img: h.img, bg: h.bg || p.bg, frame: h.img ? undefined : p.frame }} /></Punch> : null}
                  {h.t ? (
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
