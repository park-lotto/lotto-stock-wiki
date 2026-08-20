import React from 'react';
import {
  AbsoluteFill, OffthreadVideo, staticFile, interpolate, spring,
  useCurrentFrame, useVideoConfig, Sequence,
} from 'remotion';
import { C, F, BG } from './theme2';

/** 배경 루프 — 항상 뒤에서 돈다. 검정 단독 화면을 만들지 않기 위한 바닥. */
export const Bg: React.FC<{ src: string; dim?: number; startFrom?: number }> = ({
  src, dim = 1, startFrom = 0,
}) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scale = interpolate(f, [0, durationInFrames], [BG.zoomFrom, BG.zoomTo], {
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{ backgroundColor: C.ink, overflow: 'hidden' }}>
      <AbsoluteFill
        style={{
          transform: `scale(${scale})`,
          filter: `brightness(${BG.brightness * dim}) blur(${BG.blur}px) saturate(0.85)`,
        }}
      >
        <OffthreadVideo
          src={staticFile(src)}
          startFrom={startFrom}
          muted
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </AbsoluteFill>
      {/* 가장자리 비네트 — 중앙으로 시선을 모은다 */}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse at center, rgba(0,0,0,0) 35%, rgba(0,0,0,0.72) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};

/** 화면 녹화본을 "떠 있는 창"으로 얹는다. 풀스크린이 아니라 배경이 살아 보인다. */
export const ScreenCard: React.FC<{
  src: string;
  x?: number; y?: number; w?: number;
  rotate?: number;
  label?: string;
  startFrom?: number;
  delay?: number;
}> = ({ src, x = 0, y = 0, w = 1180, rotate = 0, label, startFrom = 0, delay = 0 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - delay, fps, config: { damping: 200, mass: 0.7 } });
  const op = interpolate(f - delay, [0, 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div
        style={{
          transform: `translate(${x}px, ${y + (1 - p) * 40}px) rotate(${rotate}deg) scale(${0.94 + p * 0.06})`,
          opacity: op,
          width: w,
          borderRadius: 14,
          overflow: 'hidden',
          border: `1px solid ${C.line}`,
          boxShadow: '0 40px 90px rgba(0,0,0,0.65)',
          background: C.ink,
        }}
      >
        {label ? (
          <div
            style={{
              height: 44, display: 'flex', alignItems: 'center', gap: 10,
              padding: '0 16px', background: 'rgba(255,255,255,0.06)',
              borderBottom: `1px solid ${C.line}`,
              font: `500 20px ${F.sans}`, color: C.dim, letterSpacing: 0.4,
            }}
          >
            <span style={{ display: 'flex', gap: 7 }}>
              {['#ff5f57', '#febc2e', '#28c840'].map((c) => (
                <i key={c} style={{ width: 12, height: 12, borderRadius: 99, background: c, opacity: 0.8 }} />
              ))}
            </span>
            {label}
          </div>
        ) : null}
        <OffthreadVideo
          src={staticFile(src)}
          startFrom={startFrom}
          muted
          style={{ width: '100%', display: 'block' }}
        />
      </div>
    </AbsoluteFill>
  );
};

/** 하단 자막 — 핵심 문구만. 노란 강조는 <b>로 감싼 부분. */
export const Caption: React.FC<{ text: string; accent?: string; sub?: string }> = ({
  text, accent, sub,
}) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.6 } });
  const out = interpolate(f, [durationInFrames - 8, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
  });
  const parts = accent ? text.split(accent) : [text];
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 92 }}>
      <div
        style={{
          transform: `translateY(${(1 - p) * 26}px)`,
          opacity: out,
          textAlign: 'center',
        }}
      >
        {sub ? (
          <div style={{ font: `700 26px ${F.sans}`, color: C.gold, letterSpacing: 3, marginBottom: 14 }}>
            {sub}
          </div>
        ) : null}
        <div
          style={{
            font: `900 62px/1.3 ${F.sans}`,
            color: C.paper,
            textShadow: '0 6px 30px rgba(0,0,0,0.9)',
            padding: '0 80px',
          }}
        >
          {parts.map((s, i) => (
            <React.Fragment key={i}>
              {s}
              {accent && i < parts.length - 1 ? (
                <span style={{ color: C.gold, background: C.goldSoft, padding: '0 10px', borderRadius: 8 }}>
                  {accent}
                </span>
              ) : null}
            </React.Fragment>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** 단어가 하나씩 툭툭 쌓이는 리스트 */
export const StackWords: React.FC<{ words: string[]; every?: number }> = ({ words, every = 14 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        {words.map((w, i) => {
          const d = i * every;
          const p = spring({ frame: f - d, fps, config: { damping: 200, mass: 0.5 } });
          return (
            <div
              key={w}
              style={{
                opacity: p,
                transform: `translateX(${(1 - p) * -50}px)`,
                font: `800 54px ${F.sans}`,
                color: C.paper,
                display: 'flex', alignItems: 'center', gap: 20,
              }}
            >
              <span style={{ font: `700 28px ${F.mono}`, color: C.gold, opacity: 0.9 }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              {w}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** 큰 질문 한 방 */
export const BigAsk: React.FC<{ text: string; color?: string }> = ({ text, color = C.paper }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 14, mass: 0.9 } });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div
        style={{
          transform: `scale(${0.9 + p * 0.1})`,
          opacity: interpolate(f, [0, 10], [0, 1], { extrapolateRight: 'clamp' }),
          font: `900 120px/1.2 ${F.sans}`,
          color,
          textAlign: 'center',
          whiteSpace: 'pre-line',
          textShadow: '0 10px 50px rgba(0,0,0,0.95)',
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

/** 씬 사이 크로스페이드용 래퍼 */
export const Fade: React.FC<{ children: React.ReactNode; inF?: number; outF?: number }> = ({
  children, inF = 10, outF = 10,
}) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fin = inF > 0
    ? interpolate(f, [0, inF], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    : 1;
  const fout = outF > 0
    ? interpolate(f, [durationInFrames - outF, durationInFrames], [1, 0], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      })
    : 1;
  const o = fin * fout;
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};

export { Sequence };
