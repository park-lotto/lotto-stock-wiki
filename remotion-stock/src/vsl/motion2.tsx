/**
 * S2 전용 모션 어휘 — 기획서 `영상제작/00_기획/S2_장면설계.md` §3의 N1~N4.
 *
 * S1(motion.tsx)과 분리한 이유: S2는 **색 자체가 장치**다(페인 구간은 탈색+붉은,
 * 마지막에만 민트 복귀). 같은 파일에 두면 S1 컴포넌트에 S2의 회색조가 새어 들어가
 * 두 씬의 톤이 섞인다 — 색은 씬의 주장이라 공유하면 안 된다.
 */

import React from 'react';
import {
  AbsoluteFill, Img, OffthreadVideo, interpolate, spring,
  staticFile, useCurrentFrame, useVideoConfig, Easing, Loop,
} from 'remotion';
import { KineticWord } from './motion';

export const RED = '#FF5A4D';
export const MINT2 = '#3DF0B2';
export const GREY_BG = '#0B0D0D';
export const FONT2 = "'Pretendard','Archivo',sans-serif";

/* ── 공통: 탈색 래퍼 ─────────────────────────────────────────
   남의 강의·어그로 썸네일은 **끝까지 색을 주지 않는다**. 컬러로 살려주는 순간
   "저것도 괜찮아 보이네"가 되어 씬의 주장이 무너진다. */
export const Desat: React.FC<{ children: React.ReactNode; amount?: number; tint?: number }> = ({
  children, amount = 1, tint = 0.14,
}) => (
  <AbsoluteFill>
    <AbsoluteFill style={{ filter: `grayscale(${amount}) contrast(1.08) brightness(0.82)` }}>
      {children}
    </AbsoluteFill>
    {/* 아주 옅은 붉은 틴트 — 회색만 쓰면 '오래된 영상'처럼 보이고, 붉은기가 있어야 '경고'가 된다 */}
    <AbsoluteFill style={{ background: RED, opacity: tint, mixBlendMode: 'overlay' }} />
  </AbsoluteFill>
);

/* ── N1 ScreenScroll: 화면녹화를 구간 배속으로 ────────────────
   speed>1이면 trimBefore를 프레임마다 앞으로 당겨 빨리감기처럼 보이게 한다. */
export const ScreenScroll: React.FC<{
  src: string; startSec?: number; speed?: number; scale?: number;
}> = ({ src, startSec = 0, speed = 1.6, scale = 1.06 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const drift = interpolate(frame, [0, durationInFrames], [scale, scale * 1.05]);
  return (
    <AbsoluteFill style={{ background: GREY_BG, overflow: 'hidden' }}>
      <OffthreadVideo
        src={staticFile(src)}
        trimBefore={Math.round(startSec * fps)}
        playbackRate={speed}
        volume={0}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${drift})` }}
      />
    </AbsoluteFill>
  );
};

/* ── N2 ThumbWall: 어그로 썸네일 벽 + 붉은 ✕ ──────────────────
   재료는 같은 녹화의 서로 다른 지점 6컷 — 실제로 저런 썸네일이 '널려 있다'는 게 논지다. */
export const ThumbWall: React.FC<{
  src: string; offsets?: number[]; xAt?: number[]; label?: string;
}> = ({ src, offsets = [4, 12, 20, 28, 36, 46], xAt = [], label }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cols = 3, gap = 14;
  const w = Math.floor((1920 - gap * 4) / cols);
  const h = Math.floor(w * 9 / 16);
  return (
    <AbsoluteFill style={{ background: GREY_BG, alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, ${w}px)`, gap }}>
        {offsets.map((off, i) => {
          const pop = spring({ frame: frame - i * 3, fps, config: { damping: 14, stiffness: 190 } });
          // ✕는 지정된 시각(초)에 쾅 박힌다 — 없으면 안 박힌다
          const xt = xAt[i];
          const xf = xt === undefined ? -1 : frame - Math.round(xt * fps);
          const xp = xf >= 0 ? spring({ frame: xf, fps, config: { damping: 8, stiffness: 300 } }) : 0;
          return (
            <div key={i} style={{
              position: 'relative', width: w, height: h, overflow: 'hidden',
              borderRadius: 10, background: '#000',
              transform: `scale(${interpolate(pop, [0, 1], [0.7, 1])})`, opacity: pop,
              boxShadow: '0 14px 40px rgba(0,0,0,0.6)',
            }}>
              <OffthreadVideo
                src={staticFile(src)} trimBefore={Math.round(off * fps)} volume={0}
                style={{
                  width: '100%', height: '100%', objectFit: 'cover',
                  filter: 'grayscale(1) brightness(0.7) contrast(1.1)',
                }}
              />
              {xp > 0 ? (
                <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{
                    fontSize: 150, fontWeight: 900, color: RED, lineHeight: 1,
                    fontFamily: FONT2, opacity: Math.min(1, xp),
                    transform: `scale(${interpolate(xp, [0, 1], [1.9, 1])}) rotate(-8deg)`,
                    textShadow: `0 0 40px ${RED}88`,
                  }}>✕</div>
                </AbsoluteFill>
              ) : null}
            </div>
          );
        })}
      </div>
      {label ? (
        <div style={{
          position: 'absolute', top: 54, fontFamily: FONT2, fontWeight: 900,
          fontSize: 52, color: RED, textShadow: '0 6px 26px rgba(0,0,0,0.9)',
        }}>{label}</div>
      ) : null}
    </AbsoluteFill>
  );
};

/* ── N3 StepChain: 과정이 하나씩 쌓이며 시간이 누적된다 ────────
   여기서 중요한 건 '많다'는 느낌이다 — 그래서 지워지지 않고 계속 남아 화면을 채운다. */
export const STEP_LABELS = ['제품 찾기', '대본 쓰기', '자막 수정', '성우 입히기', '썸네일', '캡컷 수정'];

export const StepChain: React.FC<{
  steps?: string[]; appearAt: number[]; minutes?: number[];
}> = ({ steps = STEP_LABELS, appearAt, minutes = [20, 25, 45, 20, 30, 40] }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  let acc = 0;
  const rows = steps.map((s, i) => {
    const at = Math.round((appearAt[i] ?? i * 0.8) * fps);
    const on = frame >= at;
    if (on) acc = minutes.slice(0, i + 1).reduce((a, b) => a + b, 0);
    return { s, at, on, i };
  });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: 1180 }}>
        {rows.map(({ s, at, on, i }) => {
          const p = on ? spring({ frame: frame - at, fps, config: { damping: 13, stiffness: 210 } }) : 0;
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 18,
              padding: '14px 26px', borderRadius: 14,
              background: 'rgba(255,90,77,0.10)', border: `2px solid ${RED}55`,
              transform: `translateX(${interpolate(p, [0, 1], [-70, 0])}px)`, opacity: p,
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: 22, background: RED,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: FONT2, fontWeight: 900, fontSize: 24, color: '#150404',
              }}>{i + 1}</div>
              <div style={{ fontFamily: FONT2, fontWeight: 800, fontSize: 44, color: '#fff' }}>{s}</div>
              <div style={{
                marginLeft: 'auto', fontFamily: "'Space Mono',monospace", fontSize: 34,
                color: RED, fontWeight: 700,
              }}>+{minutes[i]}분</div>
            </div>
          );
        })}
      </div>
      {/* 누적 시간 — 오른쪽 위에서 계속 불어난다 */}
      <div style={{
        position: 'absolute', top: 60, right: 74, textAlign: 'right',
      }}>
        <div style={{ fontFamily: FONT2, fontSize: 28, color: '#ffffffaa', fontWeight: 700 }}>영상 1개 누적</div>
        <div style={{
          fontFamily: "'Space Mono',monospace", fontSize: 96, fontWeight: 700, color: RED,
          textShadow: `0 0 46px ${RED}55`, lineHeight: 1.05,
        }}>{Math.floor(acc / 60)}시간 {acc % 60}분</div>
      </div>
    </AbsoluteFill>
  );
};

/* ── N4 ColorReturn: 회색조가 민트로 되돌아온다 ────────────────
   S2 마지막 2컷에서만 쓴다. 중간에 새면 "문제 구간"의 색 규칙이 무너진다. */
export const ColorReturn: React.FC<{ children: React.ReactNode; overFrames?: number }> = ({
  children, overFrames = 40,
}) => {
  const frame = useCurrentFrame();
  const g = interpolate(frame, [0, overFrames], [1, 0], {
    extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic),
  });
  const glow = interpolate(frame, [0, overFrames], [0, 0.16], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ filter: `grayscale(${g}) brightness(${0.82 + (1 - g) * 0.18})` }}>
        {children}
      </AbsoluteFill>
      <AbsoluteFill style={{
        background: `radial-gradient(circle at 50% 55%, ${MINT2}${Math.round(glow * 255).toString(16).padStart(2, '0')} 0%, rgba(0,0,0,0) 60%)`,
        pointerEvents: 'none',
      }} />
    </AbsoluteFill>
  );
};

/* 정지 이미지(캡처)를 켄번즈로 — 캡처는 움직이지 않아 그냥 두면 화면이 죽는다 */
export const StillPan: React.FC<{ src: string; dir?: 1 | -1 }> = ({ src, dir = 1 }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const s = interpolate(frame, [0, durationInFrames], [1.06, 1.16]);
  const x = interpolate(frame, [0, durationInFrames], [0, dir * 60]);
  return (
    <AbsoluteFill style={{ background: GREY_BG, overflow: 'hidden' }}>
      <Img src={staticFile(src)} style={{
        width: '100%', height: '100%', objectFit: 'cover',
        transform: `scale(${s}) translateX(${x}px)`,
      }} />
    </AbsoluteFill>
  );
};

/* 붉은 경고 자막 — S1의 KineticWord와 같은 문법이지만 색만 다르다 */
/* ★S2 자막도 KineticWord 하나로 합쳤다 (2026-08-12).
   전엔 같은 로직이 KineticWord·PainWord 두 벌이었다. 그래서 KineticWord만 고친
   ①강조 덩어리 nowrap ②균형 줄바꿈 ③구두점 고아 방지가 S2엔 안 들어갔고,
   실제로 사장님 캡처에서 |"자세한 건 무료강의에서."|가 두 줄로 쪼개졌다.
   같은 판단은 한 곳에만 둔다 — 색·폰트만 넘긴다. */
export const PainWord: React.FC<{
  text: string; size?: number; center?: boolean; perWord?: number; accent?: string;
}> = ({ text, size = 76, center = false, perWord = 1.6, accent = RED }) => (
  <KineticWord
    text={text} size={size} center={center} perWord={perWord}
    accent={accent} hiText="#160404" font={FONT2} pad={94}
  />
);
