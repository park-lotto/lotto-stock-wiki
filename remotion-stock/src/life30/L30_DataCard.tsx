/**
 * L30_DataCard — LIFE 3.0 스타일 데이터 카드 모음
 *
 * 컴포넌트 목록:
 *   L30_MetricCard     — "$420B" 대형 수치 카드 (MARKET CAP 스타일)
 *   L30_TimestampCard  — "2022.11.30" 날짜 카드
 *   L30_LogoCard       — 로고 + 이름 + 서브레이블 카드
 *   L30_ArrowBadge     — "→ 2024년 6월" 라임 배지
 *   L30_CountryRankCard— 국가 랭킹 카드 (RANK·01 + 국기 + EXCLUDED)
 *   L30_LargeLogoBlast — 화면 중앙 대형 로고 폭발 (NVIDIA 스타일)
 */

import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { cardBase, clamp, L30C, L30G } from './L30_constants';

const limeLabel: React.CSSProperties = {
  fontFamily:    L30C.fontMono,
  fontSize:      10,
  fontWeight:    400,
  letterSpacing: '3px',
  textTransform: 'uppercase',
  color:         L30C.lime,
};

// ── 유틸: 값 + 단위 분리 ("$420 B" → {num:"$420", unit:"B"}) ──────────────────
function splitValueUnit(val: string): { num: string; unit: string } {
  const trimmed = val.trim();
  const m = trimmed.match(/^(.*?)\s*([BTMK])$/i);
  if (m) return { num: m[1].trim(), unit: m[2].toUpperCase() };
  return { num: trimmed, unit: '' };
}

// ── L30_MetricCard ────────────────────────────────────────────────────────────
// 영상 레퍼런스 (frame ~355): "$420 B" — 숫자=흰색 대형, 단위=라임 소형
// value에 단위 포함 시 자동 분리: "$420 B" / "$420B" / "$5.5T" 모두 지원
export const L30_MetricCard: React.FC<{
  showAt?:    number;
  topLabel:   string;   // "MARKET CAP · 2022.11"
  value:      string;   // "$420 B" or "$420B" or "$5.5T"
  subLabel?:  string;   // "RANK · OUT OF TOP 10"
  width?:     number;
  slideFrom?: 'left' | 'right';
}> = ({
  showAt = 0, topLabel, value, subLabel, width = 290, slideFrom = 'left',
}) => {
  const f = useCurrentFrame();
  const op = clamp(f, showAt, showAt + 18);
  const tx = interpolate(op, [0, 1], [slideFrom === 'left' ? -28 : 28, 0]);

  const { num, unit } = splitValueUnit(value);

  return (
    <div style={{
      ...cardBase,
      width,
      padding: '18px 22px',
      opacity: op,
      transform: `translateX(${tx}px)`,
    }}>
      <div style={{ ...limeLabel, marginBottom: 8 }}>{topLabel}</div>

      {/* 수치: 숫자=흰색 대형, 단위=라임 소형 — 베이스라인 정렬 */}
      <div style={{
        display:    'flex',
        alignItems: 'baseline',
        gap:        4,
        lineHeight: 1.0,
      }}>
        <span style={{
          fontFamily:    L30C.fontMain,
          fontSize:      68,
          fontWeight:    900,
          color:         L30C.white,
          letterSpacing: '-2px',
          lineHeight:    1,
        }}>
          {num}
        </span>
        {unit && (
          <span style={{
            fontFamily:    L30C.fontMain,
            fontSize:      44,
            fontWeight:    900,
            color:         L30C.lime,
            textShadow:    L30G.lime.text,
            letterSpacing: '-1px',
            lineHeight:    1,
          }}>
            {unit}
          </span>
        )}
      </div>

      {subLabel && (
        <div style={{ ...limeLabel, marginTop: 10, opacity: 0.55 }}>{subLabel}</div>
      )}
    </div>
  );
};

// ── L30_TimestampCard ─────────────────────────────────────────────────────────
// 스크린샷2 "2022.11.30 / DAY ZERO" 스타일
export const L30_TimestampCard: React.FC<{
  showAt?:   number;
  date:      string;   // "2022.11.30"
  subLabel?: string;   // "DAY ZERO"
  width?:    number;
}> = ({
  showAt = 0, date, subLabel, width = 290,
}) => {
  const f = useCurrentFrame();
  const op = clamp(f, showAt, showAt + 18);
  const tx = interpolate(op, [0, 1], [-28, 0]);

  return (
    <div style={{
      ...cardBase,
      width,
      padding: '18px 22px',
      opacity: op,
      transform: `translateX(${tx}px)`,
    }}>
      <div style={{ ...limeLabel, marginBottom: 8 }}>TIMESTAMP</div>
      <div style={{
        fontFamily:    L30C.fontMono,
        fontSize:      38,
        fontWeight:    700,
        letterSpacing: '2px',
        color:         L30C.white,
        lineHeight:    1.1,
      }}>
        {date}
      </div>
      {subLabel && (
        <div style={{ ...limeLabel, marginTop: 8 }}>{subLabel}</div>
      )}
    </div>
  );
};

// ── L30_LogoCard ──────────────────────────────────────────────────────────────
// 스크린샷2 ChatGPT 로고 카드 스타일
export const L30_LogoCard: React.FC<{
  showAt?:      number;
  emoji?:       string;   // "🤖" 이모지 로고
  emojiSize?:   number;
  name:         string;   // "ChatGPT"
  subLabel?:    string;   // "PUBLIC RELEASE"
  width?:       number;
  height?:      number;
  slideFrom?:   'left' | 'right';
}> = ({
  showAt = 0, emoji, emojiSize = 52, name, subLabel, width = 290, height = 170, slideFrom = 'right',
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();

  const prog = spring({
    frame: Math.max(0, f - showAt),
    fps,
    config: { damping: 22, stiffness: 140, mass: 0.9 },
    durationInFrames: 24,
  });
  const op    = clamp(f, showAt, showAt + 18);
  const scale = interpolate(prog, [0, 1], [0.88, 1]);

  return (
    <div style={{
      ...cardBase,
      width, height,
      padding: '16px 20px',
      opacity: op,
      transform: `scale(${scale})`,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 10,
    }}>
      {emoji && (
        <div style={{ fontSize: emojiSize, lineHeight: 1 }}>{emoji}</div>
      )}
      <div style={{
        fontFamily: L30C.fontMain,
        fontSize:   22,
        fontWeight: 700,
        color:      L30C.white,
        textAlign:  'center',
      }}>
        {name}
      </div>
      {subLabel && (
        <div style={{ ...limeLabel, textAlign: 'center' }}>{subLabel}</div>
      )}
    </div>
  );
};

// ── L30_ArrowBadge ────────────────────────────────────────────────────────────
// 스크린샷4 "→ 2024년 6월" 라임 배지
export const L30_ArrowBadge: React.FC<{
  showAt?: number;
  text:    string;   // "→ 2024년 6월"
}> = ({ showAt = 0, text }) => {
  const f  = useCurrentFrame();
  const op = clamp(f, showAt, showAt + 16);
  const tx = interpolate(op, [0, 1], [-20, 0]);

  return (
    <div style={{
      display:     'inline-flex',
      alignItems:  'center',
      background:  L30C.lime,
      opacity:     op,
      transform:   `translateX(${tx}px)`,
      padding:     '8px 20px',
      borderRadius: 3,
    }}>
      <span style={{
        fontFamily:  L30C.fontMain,
        fontSize:    18,
        fontWeight:  700,
        color:       '#000000',
        letterSpacing: '0.3px',
      }}>
        {text}
      </span>
    </div>
  );
};

// ── L30_CountryRankCard ───────────────────────────────────────────────────────
// 스크린샷5 USA / CHINA / JAPAN EXCLUDED 카드
export const L30_CountryRankCard: React.FC<{
  showAt?:  number;
  rank:     string;   // "01"
  flag:     string;   // "🇺🇸"
  country:  string;   // "USA"
  tag?:     string;   // "EXCLUDED"
  market?:  string;   // "MARKET > 5.5T"
  width?:   number;
  delay?:   number;   // stagger 딜레이 (프레임)
}> = ({
  showAt = 0, rank, flag, country, tag, market, width = 300, delay = 0,
}) => {
  const f  = useCurrentFrame();
  const at = showAt + delay;
  const op = clamp(f, at, at + 20);
  const ty = interpolate(op, [0, 1], [24, 0]);

  return (
    <div style={{
      ...cardBase,
      width,
      padding: '16px 20px',
      opacity: op,
      transform: `translateY(${ty}px)`,
    }}>
      <div style={{ ...limeLabel, marginBottom: 12 }}>RANK · {rank}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{ fontSize: 36, lineHeight: 1 }}>{flag}</span>
        <div>
          <div style={{
            fontFamily: L30C.fontMain,
            fontSize:   22,
            fontWeight: 700,
            color:      L30C.white,
            lineHeight: 1.2,
          }}>
            {country}
          </div>
          {tag && <div style={{ ...limeLabel, marginTop: 2 }}>{tag}</div>}
        </div>
      </div>
      {market && (
        <div style={{
          ...limeLabel,
          marginTop:   10,
          paddingTop:  8,
          borderTop:   `1px solid ${L30C.limeBorder}`,
        }}>
          ▲ {market}
        </div>
      )}
    </div>
  );
};

// ── L30_LargeLogoBlast ────────────────────────────────────────────────────────
// 스크린샷3 NVIDIA 로고 폭발 — 화면 중앙 대형 반투명 이모지/텍스트
export const L30_LargeLogoBlast: React.FC<{
  showAt?:    number;
  hideAt?:    number;
  emoji?:     string;   // "🟩" 또는 텍스트
  color?:     string;   // 오버레이 배경색 (default L30C.lime)
  opacity?:   number;   // 최대 투명도 (default 0.25)
  size?:      number;   // 폰트 크기 (default 380)
}> = ({
  showAt = 0, hideAt, emoji = '●', color, opacity: maxOp = 0.25, size = 380,
}) => {
  const f = useCurrentFrame();
  const fadeIn  = clamp(f, showAt, showAt + 10);
  const fadeOut = hideAt ? clamp(f, hideAt - 10, hideAt, 1, 0) : 1;
  const op      = fadeIn * fadeOut * maxOp;

  const scale = interpolate(fadeIn, [0, 1], [0.7, 1.0]);

  return (
    <div style={{
      position: 'absolute', inset: 0,
      display:  'flex',
      alignItems: 'center', justifyContent: 'center',
      opacity: op,
      transform: `scale(${scale})`,
      pointerEvents: 'none',
      zIndex: 20,
    }}>
      <div style={{
        fontSize:   size,
        lineHeight: 1,
        color:      color ?? L30C.lime,
        filter:     `drop-shadow(0 0 40px ${color ?? L30C.lime})`,
      }}>
        {emoji}
      </div>
    </div>
  );
};
