import React from 'react';
import {
  AbsoluteFill, OffthreadVideo, staticFile, interpolate, spring, random,
  useCurrentFrame, useVideoConfig, Easing,
} from 'remotion';
import { C, F } from './theme2';

const STROKE = {
  WebkitTextStroke: '3px rgba(0,0,0,0.55)',
  paintOrder: 'stroke fill',
} as React.CSSProperties;

/* ──────────────────────────────────────────────────────────
   CF 엔진 — 모든 화면은 (1)물든 배경 (2)움직이는 카메라
   (3)글자 자체의 운동 (4)컷을 때리는 전환 으로 구성한다.
   ────────────────────────────────────────────────────────── */

export const EASE = {
  out: Easing.bezier(0.16, 1, 0.3, 1),
  inOut: Easing.bezier(0.65, 0, 0.35, 1),
  slam: Easing.bezier(0.9, 0, 0.1, 1),
} as const;

/** 손떨림 — 항상 미세하게 흔들어 화면이 죽지 않게 */
export const useHandheld = (amp = 1, speed = 0.06) => {
  const f = useCurrentFrame();
  return {
    x: Math.sin(f * speed) * amp + Math.sin(f * speed * 2.3) * amp * 0.4,
    y: Math.cos(f * speed * 0.8) * amp * 0.8 + Math.cos(f * speed * 3.1) * amp * 0.3,
    r: Math.sin(f * speed * 0.5) * amp * 0.06,
  };
};

/** 필름 그레인 */
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.16 }) => {
  const f = useCurrentFrame();
  const dots = new Array(90).fill(0).map((_, i) => {
    const seed = String(Math.floor(f / 2)) + '-' + String(i);
    return {
      x: random(seed + 'x') * 100,
      y: random(seed + 'y') * 100,
      s: 1 + random(seed + 's') * 2.5,
      o: 0.25 + random(seed + 'o') * 0.75,
    };
  });
  return (
    <AbsoluteFill style={{ opacity, pointerEvents: 'none' }}>
      {dots.map((d, i) => (
        <div
          key={i}
          style={{
            position: 'absolute', left: d.x + '%', top: d.y + '%',
            width: d.s, height: d.s, borderRadius: 99,
            background: '#fff', opacity: d.o,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

/** 듀오톤으로 물든 배경 + 그레인 + 스캔라인 + 패럴랙스 드리프트 */
export const BgFx: React.FC<{
  src: string;
  tint?: 'amber' | 'cyan' | 'red' | 'none' | 'mono' | 'monoWarm';
  dim?: number;
  speed?: number;
  startFrom?: number;
  zoom?: [number, number];
  drift?: number;
  blur?: number;
}> = ({
  src, tint = 'amber', dim = 1, speed = 1.6, startFrom = 0,
  zoom = [1.15, 1.32], drift = 60, blur = 5,
}) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const hh = useHandheld(2.2);
  const scale = interpolate(f, [0, durationInFrames], zoom, { extrapolateRight: 'clamp' });
  const dx = interpolate(f, [0, durationInFrames], [-drift / 2, drift / 2], { extrapolateRight: 'clamp' });

  const grad =
    tint === 'amber'
      ? 'linear-gradient(118deg, rgba(255,176,32,0.62) 0%, rgba(120,42,190,0.46) 58%, rgba(10,8,30,0.5) 100%)'
      : tint === 'cyan'
      ? 'linear-gradient(118deg, rgba(34,211,238,0.58) 0%, rgba(78,20,140,0.50) 60%, rgba(6,10,30,0.5) 100%)'
      : tint === 'red'
      ? 'linear-gradient(118deg, rgba(255,74,74,0.60) 0%, rgba(90,14,120,0.50) 60%, rgba(12,6,24,0.55) 100%)'
      : tint === 'mono'
      ? 'linear-gradient(118deg, rgba(210,220,235,0.16) 0%, rgba(10,12,20,0.55) 100%)'
      : tint === 'monoWarm'
      ? 'linear-gradient(118deg, rgba(255,236,200,0.20) 0%, rgba(18,12,8,0.55) 100%)'
      : 'linear-gradient(118deg, rgba(120,140,200,0.30) 0%, rgba(20,20,50,0.45) 100%)';

  const tf =
    'translate(' + (dx + hh.x) + 'px, ' + hh.y + 'px) scale(' + scale + ') rotate(' + hh.r + 'deg)';
  const isMono = tint === 'mono' || tint === 'monoWarm';
  const fil = isMono
    ? 'grayscale(1) brightness(' + 0.72 * dim + ') contrast(1.95) blur(' + blur + 'px)'
    : 'brightness(' + 0.95 * dim + ') contrast(1.32) saturate(0.35) blur(' + blur + 'px)';

  return (
    <AbsoluteFill style={{ backgroundColor: '#05060a', overflow: 'hidden' }}>
      <AbsoluteFill style={{ transform: tf, filter: fil }}>
        <OffthreadVideo
          src={staticFile(src)}
          startFrom={startFrom}
          playbackRate={speed}
          muted
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </AbsoluteFill>

      {/* 듀오톤 1겹 — 어두운 곳을 색으로 들어올린다 */}
      <AbsoluteFill style={{ background: grad, mixBlendMode: 'screen', opacity: isMono ? 0.28 : 0.5 }} />
      {/* 듀오톤 2겹 — 전체를 그 색으로 통일 */}
      <AbsoluteFill style={{ background: grad, mixBlendMode: 'overlay', opacity: isMono ? 0.35 : 0.75 }} />
      {/* 바닥 어둠 (약하게) */}
      <AbsoluteFill
        style={{ background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 42%, rgba(0,0,0,0.72) 100%)' }}
      />
      <AbsoluteFill
        style={{
          backgroundImage:
            'repeating-linear-gradient(0deg, rgba(255,255,255,0.045) 0px, rgba(255,255,255,0.045) 1px, transparent 1px, transparent 3px)',
          opacity: 0.5,
        }}
      />
      {isMono ? <FilmScratch /> : null}
      <Grain opacity={isMono ? 0.3 : 0.16} />
      {/* 노출 플리커 — 옛 필름처럼 밝기가 미세하게 떨린다 */}
      {isMono ? (
        <AbsoluteFill
          style={{
            background: '#fff',
            mixBlendMode: 'overlay',
            opacity: 0.05 + Math.abs(Math.sin(f * 0.9)) * 0.07,
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};

/** 옛 필름 세로 스크래치 */
export const FilmScratch: React.FC = () => {
  const f = useCurrentFrame();
  const bucket = Math.floor(f / 3);
  const lines = new Array(5).fill(0).map((_, i) => ({
    x: random('sc' + bucket + i) * 100,
    w: 1 + random('sw' + bucket + i) * 2,
    o: 0.05 + random('so' + bucket + i) * 0.16,
  }));
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {lines.map((l, i) => (
        <div
          key={i}
          style={{
            position: 'absolute', top: 0, bottom: 0, left: l.x + '%',
            width: l.w, background: '#fff', opacity: l.o,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};


/** 글자 뒤 스크림 — 배경이 밝아도 글자가 반드시 읽히게 만든다 */
export const Scrim: React.FC<{ y?: number; h?: number; strength?: number }> = ({
  y = 50, h = 46, strength = 0.82,
}) => (
  <AbsoluteFill
    style={{
      background:
        'radial-gradient(ellipse ' + (h * 1.9) + '% ' + h + '% at 50% ' + y + '%, rgba(0,0,0,' +
        strength + ') 0%, rgba(0,0,0,' + strength * 0.72 + ') 45%, rgba(0,0,0,0) 78%)',
    }}
  />
);

/** 순간 글리치 — RGB 분리 + 슬라이스 어긋남 */
export const Glitch: React.FC<{ at?: number[]; children: React.ReactNode }> = ({
  at = [], children,
}) => {
  const f = useCurrentFrame();
  const on = at.some((a) => f >= a && f < a + 3);
  if (!on) return <>{children}</>;
  const off = 8 + (f % 3) * 5;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: 'translateX(' + -off + 'px)', filter: 'url(#none)', opacity: 0.6, mixBlendMode: 'screen' }}>
        <AbsoluteFill style={{ background: 'rgba(255,0,60,0.9)', mixBlendMode: 'multiply' }} />
        {children}
      </AbsoluteFill>
      <AbsoluteFill style={{ transform: 'translateX(' + off + 'px)', opacity: 0.6, mixBlendMode: 'screen' }}>
        <AbsoluteFill style={{ background: 'rgba(0,220,255,0.9)', mixBlendMode: 'multiply' }} />
        {children}
      </AbsoluteFill>
      <AbsoluteFill>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

/** 컷 시작에 화면을 한 번 확 당긴다 */
export const ZoomPunch: React.FC<{ children: React.ReactNode; amount?: number; frames?: number }> = ({
  children, amount = 0.09, frames = 10,
}) => {
  const f = useCurrentFrame();
  const s = interpolate(f, [0, frames], [1 + amount, 1], { extrapolateRight: 'clamp', easing: EASE.slam });
  return <AbsoluteFill style={{ transform: 'scale(' + s + ')' }}>{children}</AbsoluteFill>;
};

/** 컷을 때리는 플래시 */
export const Flash: React.FC<{ color?: string; frames?: number }> = ({
  color = '#fff', frames = 4,
}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 1, frames], [0.9, 0.55, 0], { extrapolateRight: 'clamp' });
  return <AbsoluteFill style={{ background: color, opacity: o, mixBlendMode: 'screen' }} />;
};

/** 글자가 한 자씩 아래에서 솟으며 블러가 걷힌다 */
export const Kinetic: React.FC<{
  text: string;
  size?: number;
  color?: string;
  accent?: string;
  weight?: number;
  stagger?: number;
  delay?: number;
  align?: 'center' | 'left';
}> = ({
  text, size = 92, color = C.paper, accent, weight = 900, stagger = 1.6, delay = 0, align = 'center',
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lines = text.split('\n');
  let idx = 0;
  return (
    <div style={{ textAlign: align, width: '100%' }}>
      {lines.map((line, li) => {
        const accStart = accent ? line.indexOf(accent) : -1;
        return (
          <div key={li} style={{ overflow: 'hidden', padding: '0.08em 0' }}>
            {Array.from(line).map((ch, ci) => {
              const d = delay + idx * stagger;
              idx += 1;
              const p = spring({ frame: f - d, fps, config: { damping: 200, mass: 0.42 } });
              const isAcc =
                accStart >= 0 && ci >= accStart && ci < accStart + (accent ? accent.length : 0);
              const tr =
                'translateY(' + (1 - p) * 78 + 'px) scale(' + (0.86 + p * 0.14) + ')';
              return (
                <span
                  key={ci}
                  style={{
                    display: 'inline-block',
                    transform: tr,
                    opacity: p,
                    filter: 'blur(' + (1 - p) * 14 + 'px)',
                    font: weight + ' ' + size + 'px/1.16 ' + F.sans,
                    color: isAcc ? C.gold : color,
                    ...STROKE,
                    textShadow: isAcc
                      ? '0 0 46px rgba(250,204,21,0.9), 0 6px 26px rgba(0,0,0,1), 0 0 12px rgba(0,0,0,1)'
                      : '0 6px 26px rgba(0,0,0,1), 0 0 14px rgba(0,0,0,0.95)',
                    whiteSpace: ch === ' ' ? 'pre' : 'normal',
                  }}
                >
                  {ch}
                </span>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};

/** 때리는 문장 — 크게 들어와 꽝 멈추고 미세하게 계속 밀린다 */
export const Slam: React.FC<{ text: string; size?: number; color?: string; sub?: string }> = ({
  text, size = 128, color = C.paper, sub,
}) => {
  const f = useCurrentFrame();
  const s = interpolate(f, [0, 7], [1.55, 1], { extrapolateRight: 'clamp', easing: EASE.slam });
  const o = interpolate(f, [0, 5], [0, 1], { extrapolateRight: 'clamp' });
  const bl = interpolate(f, [0, 8], [26, 0], { extrapolateRight: 'clamp' });
  const shake = f < 12 ? Math.sin(f * 2.4) * (12 - f) * 1.4 : 0;
  const rot = interpolate(f, [0, 9], [-2.6, 0], { extrapolateRight: 'clamp', easing: EASE.slam });
  const drift = interpolate(f, [0, 120], [0, -22], { extrapolateRight: 'clamp' });
  const tr =
    'translate(' + shake + 'px, ' + drift + 'px) scale(' + s + ') rotate(' + rot + 'deg)';
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={48} h={48} strength={0.88} />
      <div style={{ textAlign: 'center', transform: tr, opacity: o, filter: 'blur(' + bl + 'px)' }}>
        {sub ? (
          <div style={{ font: '800 30px ' + F.sans, color: C.gold, letterSpacing: 10, marginBottom: 18 }}>
            {sub}
          </div>
        ) : null}
        <div
          style={{
            font: '900 ' + size + 'px/1.12 ' + F.sans,
            color,
            whiteSpace: 'pre-line',
            ...STROKE,
            textShadow: '0 10px 34px rgba(0,0,0,1), 0 0 18px rgba(0,0,0,1)',
          }}
        >
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** 하단 바 자막 — 골드 바가 열리고 글자가 따라 뜬다 */
export const BarCaption: React.FC<{ text: string; accent?: string; kicker?: string }> = ({
  text, accent, kicker,
}) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.5 } });
  const out = interpolate(f, [durationInFrames - 7, durationInFrames], [1, 0], { extrapolateLeft: 'clamp' });
  const parts = accent ? text.split(accent) : [text];
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 88 }}>
      <AbsoluteFill
        style={{
          background: 'linear-gradient(0deg, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.72) 14%, rgba(0,0,0,0) 30%)',
          opacity: out,
        }}
      />
      <div style={{ opacity: out, display: 'flex', alignItems: 'center', gap: 22, position: 'relative' }}>
        <div
          style={{
            width: 8, height: 74 * p, background: C.gold, borderRadius: 4,
            boxShadow: '0 0 30px rgba(250,204,21,0.9)',
          }}
        />
        <div style={{ textAlign: 'left' }}>
          {kicker ? (
            <div
              style={{
                font: '800 24px ' + F.sans, color: C.gold, letterSpacing: 6,
                opacity: interpolate(f, [2, 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
                marginBottom: 8,
              }}
            >
              {kicker}
            </div>
          ) : null}
          <div
            style={{
              font: '900 58px ' + F.sans, color: C.paper,
              transform: 'translateX(' + (1 - p) * -30 + 'px)',
              opacity: p, ...STROKE,
              textShadow: '0 6px 24px rgba(0,0,0,1), 0 0 12px rgba(0,0,0,1)',
            }}
          >
            {parts.map((s, i) => (
              <React.Fragment key={i}>
                {s}
                {accent && i < parts.length - 1 ? (
                  <span style={{ color: C.gold, textShadow: '0 0 34px rgba(250,204,21,0.8)' }}>{accent}</span>
                ) : null}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** 화면 녹화본 — 3D 틸트 + 골드 림라이트 + 지속 패럴랙스 */
export const Screen3D: React.FC<{
  src: string;
  w?: number; x?: number; y?: number;
  tilt?: number;
  label?: string;
  startFrom?: number;
  speed?: number;
  delay?: number;
  cropTop?: number;    // 위에서 잘라낼 비율 (0~0.4)
  cropBottom?: number;
}> = ({
  src, w = 1660, x = 0, y = 0, tilt = 6, label, startFrom = 0, speed = 1.4, delay = 0,
  cropTop = 0, cropBottom = 0,
}) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const p = spring({ frame: f - delay, fps, config: { damping: 200, mass: 0.55 } });
  const ty = interpolate(f, [0, durationInFrames], [26, -26], { extrapolateRight: 'clamp' });
  const rot = interpolate(f, [0, durationInFrames], [tilt, tilt * 0.25], { extrapolateRight: 'clamp' });
  const hh = useHandheld(1.6);
  const tr =
    'translate(' + (x + hh.x) + 'px, ' + (y + ty + (1 - p) * 70) + 'px) rotateY(' + rot +
    'deg) rotateX(' + -rot * 0.22 + 'deg) scale(' + (0.9 + p * 0.1) + ')';
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', perspective: 1800 }}>
      <div
        style={{
          width: w,
          transform: tr,
          opacity: p,
          borderRadius: 6,
          overflow: 'hidden',
          boxShadow:
            '0 70px 150px rgba(0,0,0,0.85), 0 0 0 1px rgba(255,255,255,0.10), 0 0 140px rgba(0,0,0,0.6)',
          background: '#05060a',
          position: 'relative',
        }}
      >
        {/* 코너 마커 — 카메라 뷰파인더 느낌 */}
        {[[0, 0], [1, 0], [0, 1], [1, 1]].map(([cx, cy], i) => (
          <div
            key={i}
            style={{
              position: 'absolute', zIndex: 3,
              [cx ? 'right' : 'left']: 14, [cy ? 'bottom' : 'top']: 14,
              width: 26, height: 26,
              borderTop: cy ? 'none' : '2px solid ' + C.gold,
              borderBottom: cy ? '2px solid ' + C.gold : 'none',
              borderLeft: cx ? 'none' : '2px solid ' + C.gold,
              borderRight: cx ? '2px solid ' + C.gold : 'none',
              opacity: 0.85,
            } as React.CSSProperties}
          />
        ))}
        {/* 라벨 — 화면 안 좌하단, 모노 소문자 */}
        {label ? (
          <div
            style={{
              position: 'absolute', zIndex: 3, left: 16, bottom: 14,
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '7px 14px', borderRadius: 4,
              background: 'rgba(0,0,0,0.62)',
              backdropFilter: 'blur(6px)',
              font: '700 19px ' + F.mono, color: '#fff', letterSpacing: 1.2,
            }}
          >
            <i
              style={{
                width: 9, height: 9, borderRadius: 99, background: C.red,
                boxShadow: '0 0 12px ' + C.red,
                opacity: 0.6 + Math.abs(Math.sin(f * 0.22)) * 0.4,
              }}
            />
            {label}
          </div>
        ) : null}

        <div
          style={{
            width: '100%',
            aspectRatio: String(16 / (9 * (1 - cropTop - cropBottom))),
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <OffthreadVideo
            src={staticFile(src)}
            startFrom={startFrom}
            playbackRate={speed}
            muted
            style={{
              width: '100%',
              display: 'block',
              position: 'absolute',
              top: '-' + cropTop * 100 / (1 - cropTop - cropBottom) + '%',
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** 세로 스트라이프가 훑고 지나가는 전환 */
export const Wipe: React.FC<{ frames?: number; color?: string }> = ({ frames = 12, color = C.gold }) => {
  const f = useCurrentFrame();
  const x = interpolate(f, [0, frames], [-30, 130], { extrapolateRight: 'clamp', easing: EASE.slam });
  if (f > frames) return null;
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute', top: '-20%', left: x + '%', width: '26%', height: '140%',
          background: 'linear-gradient(90deg, transparent, ' + color + ', transparent)',
          opacity: 0.5, transform: 'skewX(-14deg)', filter: 'blur(14px)',
        }}
      />
    </AbsoluteFill>
  );
};

/** 숫자가 굴러 올라가는 카운터 */
export const CountUp: React.FC<{ to: number; suffix?: string; label?: string; frames?: number }> = ({
  to, suffix = '', label, frames = 40,
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const v = Math.round(interpolate(f, [0, frames], [0, to], { extrapolateRight: 'clamp', easing: EASE.out }));
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.5 } });
  return (
    <div style={{ textAlign: 'center', transform: 'scale(' + (0.9 + p * 0.1) + ')', opacity: p }}>
      <div
        style={{
          font: '900 150px ' + F.sans, color: C.gold,
          textShadow: '0 0 60px rgba(250,204,21,0.55)', letterSpacing: -4,
        }}
      >
        {v.toLocaleString()}{suffix}
      </div>
      {label ? <div style={{ font: '700 30px ' + F.sans, color: C.dim, letterSpacing: 4 }}>{label}</div> : null}
    </div>
  );
};
