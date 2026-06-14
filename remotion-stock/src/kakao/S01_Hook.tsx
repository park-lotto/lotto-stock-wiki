/**
 * S1 — 훅 (540프레임 = 18초 @ 30fps)
 *
 * 참조 영상 훅 스타일: 결과 먼저 → 포기 순간 → "어떻게?" 궁금증
 * 나레이션:
 *   아침 8시, 카톡 하나 옵니다.
 *   시장 요약, 수급 신호, 관심 종목까지.
 *   자는 동안 클로드가 한 겁니다.
 *   어떻게 세팅했는지, 지금 보여드릴게요.
 *
 * Phase 1 f0~180  : 카톡 알림 배너 elastic 도착 + 폰 mockup
 * Phase 2 f180~340: 메시지 내용 라인별 reveal
 * Phase 3 f340~500: "자동" IMPACT + 서브텍스트
 * Phase 4 f500~540: hold
 *
 * 스타일: 흰 배경 + 카카오 옐로우 포인트 + 민트(클로드) + 국민성장펀드 X슬라이드
 */

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
} from 'remotion';
import { FONT } from '../constants';

export const S01_FRAMES = 540;

const KAKAO   = '#FAE100';
const KAKAO_D = '#3A2F00';
const MINT    = '#00FFD0';
const BLACK   = '#111111';
const GRAY    = '#666666';
const WHITE   = '#FFFFFF';
const CHAT_BG = '#B2C7D9';

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

const sp = (
  frame: number,
  from: number,
  cfg = { damping: 10, stiffness: 200, mass: 0.75 },
) => spring({ frame: Math.max(0, frame - from), fps: 30, config: cfg });

const MSGS = [
  { icon: '📊', text: '코스피 2,856 (-0.3%)  외인 순매도',  delay: 22 },
  { icon: '🔥', text: '주도 섹터: 반도체 / 조선',            delay: 64 },
  { icon: '⭐', text: '관심: 삼성전기 · HD현대중공업',       delay: 106 },
];

export const S01_Hook: React.FC = () => {
  const f = useCurrentFrame();

  const fadeIn = clamp(f, 0, 15);
  const glint  = Math.sin(f * 0.05) * 0.018 + 0.022;

  // ── 자막 ──────────────────────────────────────────────────────────
  const cap1Op = f < 330 ? clamp(f, 18, 42) : clamp(f, 330, 350, 1, 0);
  const cap2Op = clamp(f, 355, 380);

  // ── Phase 1: 폰 + 알림 배너 ──────────────────────────────────────
  const phoneOp = clamp(f, 6, 28);
  const phoneY  = interpolate(f, [6, 38], [55, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  const notifScale = sp(f, 18, { damping: 8, stiffness: 240, mass: 0.6 });
  const notifOp    = f < 178 ? clamp(f, 18, 46) : clamp(f, 178, 198, 1, 0);
  const notifY     = interpolate(f, [18, 56], [-72, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.35)),
  });

  // ── Phase 2: 메시지 reveal (f180~340) ────────────────────────────
  const msgPhaseOp = f < 330 ? clamp(f, 178, 206) : clamp(f, 330, 350, 1, 0);

  // ── Phase 3: IMPACT (f340~500) ───────────────────────────────────
  const impactOp    = clamp(f, 340, 372);
  const impactScale = 0.68 + sp(f, 340, { damping: 7, stiffness: 300, mass: 0.5 }) * 0.32;
  const subOp       = clamp(f, 400, 428);
  const subX        = interpolate(f, [400, 428], [-30, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill style={{
      background: WHITE,
      opacity: fadeIn,
      overflow: 'hidden',
      fontFamily: FONT,
    }}>

      {/* 배경 앰비언트 — 카카오 옐로우 좌상 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 28% 18%, rgba(250,225,0,1) 0%, transparent 52%)',
        opacity: glint * 4,
      }} />

      {/* ══ Phase 1 + 2: 폰 mockup ══════════════════════════════════ */}
      <div style={{
        position: 'absolute',
        left: '50%', top: '50%',
        transform: `translate(-50%, calc(-50% + ${phoneY}px))`,
        opacity: phoneOp,
        width: 400, height: 680,
        background: WHITE,
        borderRadius: 50,
        border: '2px solid rgba(0,0,0,0.09)',
        boxShadow: '0 30px 80px rgba(0,0,0,0.13), 0 8px 18px rgba(0,0,0,0.07)',
        overflow: 'hidden',
        zIndex: 10,
      }}>

        {/* 노치 */}
        <div style={{
          position: 'absolute', top: 13, left: '50%',
          transform: 'translateX(-50%)',
          width: 110, height: 32, background: '#1A1A1A', borderRadius: 18,
        }} />

        {/* 카카오 채팅 헤더 */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 96,
          background: KAKAO,
          display: 'flex', alignItems: 'flex-end',
          paddingBottom: 13, paddingInline: 18, gap: 10,
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: KAKAO_D,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 17,
          }}>🤖</div>
          <div style={{ color: KAKAO_D, fontSize: 15, fontWeight: 700 }}>
            주식 AI 브리핑
          </div>
        </div>

        {/* 채팅 본문 (Phase 2) */}
        <div style={{
          position: 'absolute', top: 96, left: 0, right: 0, bottom: 56,
          background: CHAT_BG, opacity: msgPhaseOp,
          padding: '12px 10px', display: 'flex',
          flexDirection: 'column', gap: 5,
        }}>
          <div style={{
            textAlign: 'center',
            color: 'rgba(0,0,0,0.42)', fontSize: 11, fontWeight: 500,
            marginBottom: 5,
          }}>오전 8:00</div>

          {/* 메시지 버블 */}
          <div style={{
            background: WHITE,
            borderRadius: '4px 14px 14px 14px',
            padding: '10px 13px',
            boxShadow: '0 2px 5px rgba(0,0,0,0.11)',
            maxWidth: '90%',
          }}>
            <div style={{
              fontSize: 12, fontWeight: 700, color: KAKAO_D,
              marginBottom: 6,
              borderBottom: '1px solid rgba(0,0,0,0.07)',
              paddingBottom: 5,
            }}>📋 오늘의 주식 브리핑</div>

            {MSGS.map((msg, i) => {
              const mOp = clamp(f, 178 + msg.delay, 178 + msg.delay + 22);
              const mX  = interpolate(
                f,
                [178 + msg.delay, 178 + msg.delay + 18],
                [-18, 0],
                { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) },
              );
              return (
                <div key={i} style={{
                  opacity: mOp,
                  transform: `translateX(${mX}px)`,
                  fontSize: 11.5, color: '#333',
                  lineHeight: 1.85, display: 'flex', gap: 5,
                }}>
                  <span>{msg.icon}</span>
                  <span>{msg.text}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 홈바 */}
        <div style={{
          position: 'absolute', bottom: 8, left: '50%',
          transform: 'translateX(-50%)',
          width: 110, height: 5, background: 'rgba(0,0,0,0.16)', borderRadius: 3,
        }} />
      </div>

      {/* 카톡 알림 배너 (Phase 1) */}
      <div style={{
        position: 'absolute',
        top: 54, left: '50%',
        transform: `translateX(-50%) translateY(${notifY}px) scale(${0.52 + notifScale * 0.48})`,
        opacity: notifOp,
        width: 460,
        background: 'rgba(255,255,255,0.96)',
        backdropFilter: 'blur(20px)',
        borderRadius: 18, padding: '13px 18px',
        boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
        display: 'flex', gap: 13, alignItems: 'center',
        zIndex: 20,
      }}>
        <div style={{
          width: 42, height: 42, borderRadius: 11,
          background: KAKAO,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22, flexShrink: 0,
        }}>🤖</div>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: KAKAO_D }}>주식 AI 브리핑</div>
          <div style={{ fontSize: 12, color: '#555', marginTop: 1 }}>오늘 시장 브리핑 도착 📊</div>
        </div>
        <div style={{ marginLeft: 'auto', fontSize: 11.5, color: '#999', flexShrink: 0 }}>
          오전 8:00
        </div>
      </div>

      {/* ══ Phase 3: IMPACT (f340~500) ══════════════════════════════ */}
      <div style={{
        position: 'absolute', inset: 0, bottom: '16%',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        gap: 28, opacity: impactOp, pointerEvents: 'none',
      }}>
        {/* "자동" 임팩트 */}
        <div style={{
          fontSize: 210, fontWeight: 900, lineHeight: 0.88,
          fontFamily: '"Arial Black", Arial, sans-serif',
          letterSpacing: 16,
          transform: `scale(${impactScale})`,
          display: 'inline-block',
        }}>
          <span style={{ color: BLACK }}>자</span>
          <span style={{
            color: MINT,
            textShadow: '0 0 24px rgba(0,255,208,0.4)',
          }}>동</span>
        </div>

        {/* 서브텍스트 */}
        <div style={{
          opacity: subOp,
          transform: `translateX(${subX}px)`,
          fontSize: 34, fontWeight: 600, color: GRAY,
          letterSpacing: 1,
        }}>
          자는 동안&nbsp;
          <span style={{ color: MINT, fontWeight: 800 }}>클로드</span>
          가 했어요
        </div>
      </div>

      {/* ══ 자막 바 ══════════════════════════════════════════════════ */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        background: 'rgba(255,255,255,0.90)',
        borderTop: '1px solid rgba(0,0,0,0.07)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{
          position: 'absolute', opacity: cap1Op,
          color: BLACK, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80,
        }}>
          아침 8시, 이게&nbsp;
          <span style={{ color: '#9A7800', fontWeight: 800 }}>카카오톡</span>
          으로 옵니다
        </div>
        <div style={{
          position: 'absolute', opacity: cap2Op,
          color: BLACK, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80,
        }}>
          어떻게 세팅했는지 — 지금 보여드릴게요
        </div>
      </div>

    </AbsoluteFill>
  );
};
