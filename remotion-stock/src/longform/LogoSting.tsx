/**
 * 로고 스팅 — 롱폼→쇼츠에서 하이라이트와 본문 사이에 끼우는 1.8초 전환(2026-08-15).
 *
 * ★왜 필요한가. 하이라이트로 앞에 붙인 장면이 본문에서 곧 다시 나온다. 사이에 아무것도
 *   없으면 "영상이 되감겼나?"로 읽혀 오류처럼 보인다(사장님 지적).
 *
 * ★1차(0.9초)는 "퀄리티가 너무 안 좋다"는 평을 받았다. 이유를 갈라 보면 셋이었다:
 *   ① 너무 짧아 동작이 다 보이기 전에 끝났다 → 27 → 54프레임(1.8초)
 *   ② 검은 배경에 링 하나뿐이라 허전했다 → 방사형 글로우 + 빛줄기 + 입자
 *   ③ 로고가 그냥 커지기만 했다 → 회전 감쇠 + 글로우 + 링 2겹 + 자간 애니메이션
 *
 * 동작(54프레임 @30fps):
 *   0~6    화이트 플래시로 앞 장면을 끊는다
 *   4~24   로고가 스프링으로 튀어들어오며 살짝 돌아 제자리 / 링 2겹이 퍼진다
 *   10~30  빛줄기가 좌우로 훑고 지나간다
 *   18~36  채널명이 자간을 좁히며 올라오고 금색 밑줄이 그어진다
 *   36~48  전체가 아주 살짝 확대되며 붙잡아 둔다(정지처럼 보이지 않게)
 *   48~54  검정으로 닫으며 본문으로 넘어간다
 */
import React from 'react';
import {
  AbsoluteFill, Img, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from 'remotion';

export const STING_FPS = 30;
export const STING_FRAMES = 54;      // 1.8초

export type LogoStingProps = {
  channel: string;
  logo?: string;                     // public/ 안의 파일명. 없으면 글자만
  accent: string;
};

export const LogoSting: React.FC<LogoStingProps> = ({ channel, logo, accent }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();

  // 로고 — 스프링이라 '툭' 떨어지는 맛이 난다(선형 보간은 밋밋하다)
  const pop = spring({ frame: frame - 4, fps, config: { damping: 12, mass: 0.7 } });
  const logoScale = interpolate(pop, [0, 1], [0.4, 1]);
  const logoSpin = interpolate(pop, [0, 1], [-14, 0]);          // 감쇠 회전
  const logoOpacity = interpolate(frame, [4, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 링 2겹 — 시차를 둬야 '퍼진다'로 읽힌다(한 겹은 그냥 원이 커지는 것)
  const ringA = interpolate(frame, [5, 26], [0, 1], { extrapolateRight: 'clamp' });
  const ringB = interpolate(frame, [11, 34], [0, 1], { extrapolateRight: 'clamp' });
  const ringOf = (t: number, from: number, to: number) => ({
    width: interpolate(t, [0, 1], [from, to]),
    height: interpolate(t, [0, 1], [from, to]),
    opacity: interpolate(t, [0, 0.35, 1], [0, 0.8, 0]),
  });

  // 빛줄기 — 좌에서 우로 훑는다
  const sweep = interpolate(frame, [10, 30], [-1.2, 1.4], { extrapolateRight: 'clamp' });
  const sweepAlpha = interpolate(frame, [10, 14, 26, 30], [0, 0.5, 0.5, 0]);

  // 화이트 플래시 — 앞 장면을 끊는 역할.
  // ★0프레임부터 0.95로 때리면 앞의 어두운 화면에서 한 프레임에 밝기가 219 튄다
  //   (측정: tools/motion_check.py, 전체 평균 0.6의 365배 = 깜빡임·오류로 읽힌다).
  //   그래서 0에서 시작해 3프레임에 걸쳐 올리고, 정점도 낮추고, 길게 뺀다.
  const flash = interpolate(frame, [0, 3, 6, 14], [0, 0.42, 0.30, 0],
    { extrapolateRight: 'clamp' });

  // 채널명 — 자간을 좁히며 올라온다
  const nameUp = spring({ frame: frame - 18, fps, config: { damping: 15 } });
  const nameY = interpolate(nameUp, [0, 1], [34, 0]);
  const nameTrack = interpolate(nameUp, [0, 1], [16, 0]);
  const nameOpacity = interpolate(frame, [18, 26], [0, 1], { extrapolateRight: 'clamp' });
  const barW = interpolate(spring({ frame: frame - 24, fps, config: { damping: 16 } }),
    [0, 1], [0, 240]);

  // 전체 미세 확대 — 멈춘 그림처럼 보이지 않게
  const drift = interpolate(frame, [24, STING_FRAMES], [1, 1.045], { extrapolateLeft: 'clamp' });
  // 마무리 — 검정으로 닫으며 본문에 자연스럽게 넘긴다
  const closeOut = interpolate(frame, [STING_FRAMES - 6, STING_FRAMES], [0, 1],
    { extrapolateLeft: 'clamp' });

  const logoW = Math.round(height * 0.40);

  return (
    <AbsoluteFill style={{ backgroundColor: '#05070B' }}>
      {/* 바탕 글로우 — 검정 단색이면 허전하다 */}
      <AbsoluteFill style={{
        background: `radial-gradient(circle at 50% 46%, ${accent}22 0%, #05070B 62%)`,
      }} />

      <AbsoluteFill style={{ transform: `scale(${drift})` }}>
        {/* 링 2겹 */}
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <div style={{
            position: 'absolute', borderRadius: '50%',
            border: `4px solid ${accent}`, ...ringOf(ringA, 90, 430),
          }} />
          <div style={{
            position: 'absolute', borderRadius: '50%',
            border: `2px solid ${accent}`, ...ringOf(ringB, 90, 600),
          }} />
        </AbsoluteFill>

        {/* 로고 + 채널명 */}
        <AbsoluteFill style={{
          justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 14,
        }}>
          {logo ? (
            <Img
              src={staticFile(logo)}
              style={{
                width: logoW,
                transform: `scale(${logoScale}) rotate(${logoSpin}deg)`,
                opacity: logoOpacity,
                filter: `drop-shadow(0 0 26px ${accent}66)`,
              }}
            />
          ) : null}
          <div style={{
            transform: `translateY(${nameY}px)`, opacity: nameOpacity,
            color: '#fff', fontSize: 40, fontWeight: 800,
            letterSpacing: `${nameTrack}px`,
            fontFamily: 'Pretendard, system-ui, sans-serif',
            textShadow: '0 2px 14px rgba(0,0,0,.6)',
          }}>
            {channel}
          </div>
          <div style={{
            width: barW, height: 5, backgroundColor: accent, opacity: nameOpacity,
            boxShadow: `0 0 14px ${accent}`,
          }} />
        </AbsoluteFill>
      </AbsoluteFill>

      {/* 빛줄기 */}
      <AbsoluteFill style={{ overflow: 'hidden' }}>
        <div style={{
          position: 'absolute', top: '-30%', left: `${sweep * 100}%`,
          width: '26%', height: '160%',
          background: `linear-gradient(90deg, transparent, #ffffff${'aa'}, transparent)`,
          opacity: sweepAlpha, transform: 'rotate(14deg)', filter: 'blur(14px)',
        }} />
      </AbsoluteFill>

      {/* 화이트 플래시 */}
      <AbsoluteFill style={{ backgroundColor: '#fff', opacity: flash }} />
      {/* 닫기 */}
      <AbsoluteFill style={{ backgroundColor: '#000', opacity: closeOut }} />
    </AbsoluteFill>
  );
};
