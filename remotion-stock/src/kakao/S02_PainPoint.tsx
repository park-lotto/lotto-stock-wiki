/**
 * S2 — 페인포인트 (620프레임 = 약 20초 @ 30fps)
 * variant: 'dark' | 'light'
 *
 * Phase1 f0~220  : 2×2 카드 그리드 bounce 등장 (콘텐츠 영역 상단 82%)
 * Phase2 f220~270: 카드 페이드아웃
 * Phase3 f270~450: IMPACT "매  일 / 20  분"
 * Phase4 f430~580: "반복 노동" 민트 네온
 * Phase5 f580~620: hold
 *
 * 가이드 준수:
 *  - fadeIn f0-15, AbsoluteFill opacity
 *  - 배경 글로우 Math.sin 펄스
 *  - 콘텐츠 영역: bottom '18%'
 *  - 자막 바: height '16%', fontSize 40, fontWeight 700, paddingInline 80
 */

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
} from 'remotion';
import { C, FONT } from '../constants';

export const S02_FRAMES = 660;

interface Props { variant?: 'dark' | 'light' }

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (frame: number, from: number, cfg = { damping: 10, stiffness: 180, mass: 0.85 }) =>
  spring({ frame: Math.max(0, frame - from), fps: 30, config: cfg });

// 대본 S2 고증: 인베스팅 → 네이버 → 텔레그램/카톡방 → 쇼츠 → 뇌동매매
const CARDS = [
  { icon: '📈', label: '인베스팅닷컴 야간선물', startF: 8   },
  { icon: '🔍', label: '네이버 뉴스 검색',      startF: 50  },
  { icon: '💬', label: '텔레그램·카톡방 10개',  startF: 92  },
  { icon: '📱', label: '쇼츠... 30분 증발',      startF: 134 },
  { icon: '😵', label: '결국 뇌동매매',           startF: 176, boom: true },
];

export const S02_PainPoint: React.FC<Props> = ({ variant = 'dark' }) => {
  const f = useCurrentFrame();
  const isDark = variant === 'dark';

  // ─── 가이드 공통: fadeIn ──────────────────────────────────────
  const fadeIn = clamp(f, 0, 15);

  // ─── 배경 글로우 (Math.sin 펄스, 리스트형 기준) ──────────────
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  // ─── 색상 팔레트 ──────────────────────────────────────────────
  const BG             = isDark ? '#000000' : '#FFFFFF';
  const TEXT_MAIN      = isDark ? '#FFFFFF' : '#111111';
  const CARD_BG        = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)';
  const CARD_BORDER    = isDark ? 'rgba(0,255,208,0.25)'   : 'rgba(0,180,140,0.3)';
  const IMPACT_TEXT    = isDark ? '#FFFFFF' : '#111111';
  const SUBTITLE_BG    = isDark ? 'rgba(0,0,0,0.82)'       : 'rgba(255,255,255,0.88)';
  const SUBTITLE_LINE  = isDark ? 'rgba(255,255,255,0.08)'  : 'rgba(0,0,0,0.08)';
  const SUBTITLE_COLOR = isDark ? C.textPrimary             : '#111111';
  const LABOR_SHADOW   = isDark
    ? '0 0 10px rgba(0,255,208,0.55), 0 0 30px rgba(0,255,208,0.25)'
    : '0 2px 12px rgba(0,0,0,0.15), 0 0 20px rgba(0,200,160,0.3)';

  // ─── 카드 그룹 페이드아웃 ────────────────────────────────────
  const cardsOp = f < 240 ? 1 : clamp(f, 240, 285, 1, 0);

  // 😵 boom 이모지 elastic (뇌동매매 카드)
  const boomScale = sp(f, 190, { damping: 5, stiffness: 320, mass: 0.45 });
  const boomOp    = clamp(f, 190, 210);

  // ─── IMPACT ────────────────────────────────────────────────
  const impactOp   = clamp(f, 295, 338);
  const impactFade = f < 435 ? 1 : clamp(f, 435, 470, 1, 0);
  const impactY    = interpolate(f, [295, 338], [50, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // ─── 정보 소비 ─────────────────────────────────────────────
  const laborOp    = clamp(f, 455, 495);
  const laborScale = sp(f, 455, { damping: 9, stiffness: 210, mass: 0.7 });
  const laborPulse = 0.78 + Math.sin(f * 0.1) * 0.22;

  // ─── 자막 (2단계) ────────────────────────────────────────
  const cap1Op = f < 200 ? 0 : f < 428 ? clamp(f, 200, 228) : clamp(f, 428, 455, 1, 0);
  const cap2Op = clamp(f, 460, 488);

  return (
    <AbsoluteFill style={{
      background: BG,
      opacity: fadeIn,
      overflow: 'hidden',
      fontFamily: FONT,
    }}>

      {/* 배경 중앙 글로우 (가이드 §4 필수) */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: isDark ? bgGlow : bgGlow * 0.25,
        pointerEvents: 'none',
      }} />

      {/* ══════════════════════════════════════════════════════
          콘텐츠 영역 — 상단 82% (bottom '18%')
          ══════════════════════════════════════════════════════ */}

      {/* 2×2 카드 그리드 */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0, bottom: '18%',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        gridTemplateRows: '1fr 1fr',
        padding: 40,
        gap: 20,
        opacity: cardsOp,
      }}>
        {CARDS.map((card, i) => {
          // 국민성장펀드 스타일: X슬라이드 (왼쪽 → 중앙), letterSpacing 압축
          const slideX = interpolate(f, [card.startF, card.startF + 28], [-220, 0], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });
          const cardOp    = clamp(f, card.startF, card.startF + 22);
          const cardScale = 0.88 + sp(f, card.startF, { damping: 12, stiffness: 200, mass: 0.7 }) * 0.12;

          return (
            <div key={i} style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 20,
              opacity: cardOp,
              transform: `translateX(${slideX}px) scale(${cardScale})`,
              background: CARD_BG,
              border: `1.5px solid ${CARD_BORDER}`,
              borderRadius: 28,
            }}>
              {/* 이모지 (레퍼런스 기준 100~140px) */}
              <div style={{ fontSize: 130, lineHeight: 1, position: 'relative' }}>
                {card.icon}
                {card.boom && (
                  <span style={{
                    position: 'absolute',
                    fontSize: 96,
                    top: -14,
                    right: -64,
                    opacity: boomOp,
                    transform: `scale(${boomScale})`,
                    display: 'inline-block',
                    transformOrigin: 'center',
                  }}>
                    😅
                  </span>
                )}
              </div>

              {/* 카드 라벨 (가이드 §3-2: 최소 22px / 카드 메인 라벨) */}
              <div style={{
                fontSize: 52,
                fontWeight: card.boom ? 700 : 500,
                color: card.boom ? C.main : TEXT_MAIN,
                letterSpacing: 1,
                textShadow: card.boom
                  ? '0 0 8px rgba(0,255,208,0.45)'
                  : 'none',
              }}>
                {card.label}
              </div>
            </div>
          );
        })}
      </div>

      {/* IMPACT "매  일 / 20  분" */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        opacity: impactOp * impactFade,
        transform: `translateY(${impactY}px)`,
        pointerEvents: 'none',
      }}>
        <div style={{
          fontFamily: '"Arial Black", Arial, sans-serif',
          fontSize: 200,
          fontWeight: 900,
          letterSpacing: 28,
          color: IMPACT_TEXT,
          lineHeight: 1,
          textShadow: isDark
            ? '0 0 12px rgba(255,255,255,0.18)'
            : '0 4px 20px rgba(0,0,0,0.12)',
        }}>
          매&nbsp;&nbsp;일
        </div>
        <div style={{
          fontFamily: '"Arial Black", Arial, sans-serif',
          fontSize: 200,
          fontWeight: 900,
          letterSpacing: 28,
          color: C.main,
          lineHeight: 1,
          textShadow: '0 0 10px rgba(0,255,208,0.45), 0 0 28px rgba(0,255,208,0.2)',
        }}>
          20&nbsp;&nbsp;분
        </div>
      </div>

      {/* 반복 노동 */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: laborOp,
        transform: `scale(${0.78 + laborScale * 0.22})`,
        pointerEvents: 'none',
      }}>
        <div style={{
          fontSize: 164,
          fontWeight: 900,
          letterSpacing: 20,
          color: C.main,
          textShadow: `${LABOR_SHADOW}, 0 0 60px rgba(0,255,208,${0.12 * laborPulse})`,
        }}>
          정보 소비
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          하단 자막 바 — 가이드 §3-2: height '16%', fontSize 40, fontWeight 700
          ══════════════════════════════════════════════════════ */}
      <div style={{
        position: 'absolute',
        bottom: 0, left: 0, right: 0,
        height: '16%',
        background: SUBTITLE_BG,
        borderTop: `1px solid ${SUBTITLE_LINE}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {/* 자막 1: 카드+IMPACT 페이즈 */}
        <div style={{
          position: 'absolute',
          opacity: cap1Op,
          color: SUBTITLE_COLOR,
          fontSize: 40,
          fontWeight: 700,
          textAlign: 'center',
          paddingInline: 80,
        }}>
          "관망해야겠다" — 그날 대부분 뭔가 나요.
        </div>

        {/* 자막 2: 반복노동 페이즈 */}
        <div style={{
          position: 'absolute',
          opacity: cap2Op,
          color: SUBTITLE_COLOR,
          fontSize: 40,
          fontWeight: 700,
          textAlign: 'center',
          paddingInline: 80,
        }}>
          수집은 AI한테. 나는 판단만 합니다.
        </div>
      </div>

    </AbsoluteFill>
  );
};
