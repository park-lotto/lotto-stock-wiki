/**
 * KK_ColdOpen — 콜드오픈 훅 (160f · 5.3s · 실사진 + 키네틱 훅)
 * 실제 손+아이폰 사진(잠금화면) 위에 카카오 알림 배너가 '딩'(+플래시) →
 * 옆 공간에 훅 문구가 단어별로 쌓임: "매일 아침 7시, 내 카톡에 주식 브리핑이 …와 있다면?"
 * SFX: kakao_ding@18, tick(문구마다), impact(마지막 질문). 무음 훅.
 *
 * 화면/배너 위치는 ADJ 상수로 Studio 미세조정 (S7 방식).
 * 골든 레퍼런스: KK_S3_L30.tsx
 */

import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from 'remotion';
import { cl, pop, riseFade, zoomPunch, flashAt, shake, pulse, Sfx } from './fx';
import { LIME, LIME_GLOW, RED } from './life';

export const KK_COLDOPEN_FRAMES = 160;

const MONO = "'Space Mono','Roboto Mono',monospace";
const KFONT = "'Noto Sans KR',sans-serif";
const IMG = 'kakao/ep1/coldopen_hand.jpg';

// ── Studio 미세조정 상수 ──
const ADJ = {
  phoneH: 1010,      // 폰 사진 높이(px)
  phoneCX: 63,       // 폰 사진 중심 X (%)
  phoneCY: 52,       // 폰 사진 중심 Y (%)
  bannerTop: 30,     // 알림 배너 상단 (사진 높이 %)
  bannerSide: 32,    // 알림 배너 좌우 여백 (사진 폭 %)
  bannerRot: -1.5,   // 폰 기울기 보정 (deg)
};

export const KK_ColdOpen: React.FC = () => {
  const f = useCurrentFrame();

  const push = 1 + cl(f, 0, 160, 0, 0.06);                  // 켄번즈 푸시인
  const inP = pop(f, 0, { damping: 16, stiffness: 120 });
  const phoneScale = (0.94 + inP * 0.06) * push;
  const phoneOp = cl(f, 0, 14);
  const dsh = shake(f, 18, 12, 3);                          // 딩 순간 미세 흔들림

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: KFONT, overflow: 'hidden' }}>
      <Sfx at={18} file="kakao_ding.mp3" vol={0.55} />
      <Sfx at={30} file="tick.mp3" vol={0.28} />
      <Sfx at={50} file="tick.mp3" vol={0.28} />
      <Sfx at={75} file="tick.mp3" vol={0.3} />
      <Sfx at={106} file="impact.mp3" vol={0.42} />

      {/* 흐릿한 배경(사진 확대·블러) — 빈 프레임 채움 */}
      <Img src={staticFile(IMG)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(44px) brightness(0.42) saturate(1.1)', transform: `scale(${1.3 * push})` }} />

      {/* 텍스트 가독성 스크림 (좌측) */}
      <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0.42) 34%, transparent 58%)', pointerEvents: 'none' }} />

      {/* 딩 플래시 */}
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, 18, 8, 0.16), pointerEvents: 'none' }} />

      {/* ───── 손+폰 사진 (선명) + 잠금화면 알림 배너 ───── */}
      <div
        style={{
          position: 'absolute',
          left: `${ADJ.phoneCX}%`,
          top: `${ADJ.phoneCY}%`,
          width: ADJ.phoneH,
          height: ADJ.phoneH,
          transform: `translate(-50%,-50%) translate(${dsh.x}px, ${dsh.y}px) scale(${phoneScale})`,
          opacity: phoneOp,
        }}
      >
        <Img src={staticFile(IMG)} style={{ width: '100%', height: '100%', objectFit: 'contain', filter: 'drop-shadow(0 30px 60px rgba(0,0,0,0.6))' }} />
      </div>

      {/* ───── 키네틱 훅 문구 (폰 위쪽 가운데) ───── */}
      <div style={{ position: 'absolute', left: `${ADJ.phoneCX}%`, top: 40, transform: 'translateX(-50%)', width: 1040, textAlign: 'center' }}>
        {/* 키커 */}
        <div style={{ fontFamily: MONO, fontSize: 17, letterSpacing: 5, color: LIME, opacity: cl(f, 6, 22), marginBottom: 22, textShadow: `0 0 10px ${LIME}` }}>
          EP.01 · STOCK BRAIN
        </div>

        {/* 1) 매일 아침 7시 */}
        {f >= 30 && (() => { const { opacity, y } = riseFade(f, 30, 10, 24); return (
          <div style={{ opacity: opacity * (f >= 75 ? 0.72 : 1), transform: `translateY(${y}px)`, fontSize: 58, fontWeight: 800, color: '#fff', letterSpacing: -1, textShadow: '0 2px 16px rgba(0,0,0,0.9)' }}>
            매일 아침 <span style={{ color: LIME, textShadow: `0 0 28px ${LIME_GLOW}` }}>7시</span>,
          </div>
        ); })()}

        {/* 2) 내 카톡에 */}
        {f >= 50 && (() => { const { opacity, y } = riseFade(f, 50, 10, 24); return (
          <div style={{ opacity: opacity * (f >= 75 ? 0.72 : 1), transform: `translateY(${y}px)`, marginTop: 6, fontSize: 58, fontWeight: 800, color: '#fff', letterSpacing: -1, textShadow: '0 2px 16px rgba(0,0,0,0.9)' }}>
            내 <span style={{ background: '#FEE500', color: '#191600', padding: '2px 14px', borderRadius: 12, fontWeight: 900 }}>카톡</span>에
          </div>
        ); })()}

        {/* 3) 주식 브리핑이 */}
        {f >= 75 && (() => { const { opacity, y } = riseFade(f, 75, 10, 28); const p = pop(f, 75, { damping: 9 }); return (
          <div style={{ opacity, transform: `translateY(${y}px) scale(${0.94 + p * 0.06})`, transformOrigin: 'center', marginTop: 16, fontSize: 94, fontWeight: 900, color: '#fff', letterSpacing: -3, lineHeight: 1.02, textShadow: '0 2px 22px rgba(0,0,0,0.95)' }}>
            주식 브리핑이
          </div>
        ); })()}

        {/* 4) …와 있다면? */}
        {f >= 106 && (() => { const punch = zoomPunch(f, 106, 1.16, 18); return (
          <div style={{ opacity: cl(f, 106, 122), transform: `scale(${punch})`, transformOrigin: 'center', marginTop: 10, fontSize: 122, fontWeight: 900, letterSpacing: -4, lineHeight: 1.0, textShadow: `0 0 50px ${LIME_GLOW}, 0 2px 22px rgba(0,0,0,0.9)` }}>
            <span style={{ color: '#fff' }}>…와 있다면</span>
            <span style={{ color: LIME, display: 'inline-block', transform: `scale(${pulse(f, 0.14, 1, 0.06)})` }}>?</span>
          </div>
        ); })()}

        {/* 라임 밑줄 스윕 */}
        {f >= 118 && (
          <div style={{ margin: '18px auto 0', height: 5, width: cl(f, 118, 140, 0, 420), background: `linear-gradient(90deg, transparent, ${LIME}, transparent)`, borderRadius: 3, boxShadow: `0 0 14px ${LIME}` }} />
        )}
      </div>

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: RED, boxShadow: `0 0 12px ${RED}` }} />
    </AbsoluteFill>
  );
};
