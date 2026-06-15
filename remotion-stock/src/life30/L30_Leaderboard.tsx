/**
 * L30_Leaderboard — GLOBAL TOP 10 랭킹 테이블
 *
 * 영상 레퍼런스: https://youtu.be/kI1soqlxwl8 (frame ~350)
 *   - 타이틀: "GLOBAL · TOP 10 (2022.11)"
 *   - 라임 테두리 박스
 *   - 행: RANK | 국기 | 국가 | 시가총액
 *   - 행별 stagger 등장
 *   - excluded: dim 처리 + EXCL 뱃지
 *   - highlight: 라임 강조 행
 */

import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { cardBase, clamp, L30C, L30G } from './L30_constants';

export interface LeaderboardRow {
  rank:       string;    // "01"~"10"
  flag:       string;    // "🇰🇷"
  country:    string;    // "KOREA"
  value:      string;    // "$4.5T"
  excluded?:  boolean;   // dim + EXCL 뱃지
  highlight?: boolean;   // 라임 강조
}

interface L30_LeaderboardProps {
  showAt?:   number;
  title?:    string;     // "GLOBAL · TOP 10"
  subtitle?: string;     // "(2022.11)"
  rows:      LeaderboardRow[];
  width?:    number;
}

export const L30_Leaderboard: React.FC<L30_LeaderboardProps> = ({
  showAt   = 0,
  title    = 'GLOBAL · TOP 10',
  subtitle = '(2022.11)',
  rows,
  width    = 460,
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const containerOp = clamp(f, showAt, showAt + 18);
  const containerTx = interpolate(containerOp, [0, 1], [32, 0]);

  return (
    <div style={{
      ...cardBase,
      width,
      opacity:   containerOp,
      transform: `translateX(${containerTx}px)`,
      overflow:  'hidden',
    }}>
      {/* 타이틀 바 */}
      <div style={{
        padding:      '14px 20px',
        borderBottom: `1px solid ${L30C.limeBorder}`,
        display:      'flex',
        alignItems:   'baseline',
        gap:          8,
      }}>
        <span style={{
          fontFamily:    L30C.fontMono,
          fontSize:      11,
          fontWeight:    400,
          letterSpacing: '3px',
          textTransform: 'uppercase',
          color:         L30C.lime,
          textShadow:    L30G.lime.text,
        }}>
          {title}
        </span>
        <span style={{
          fontFamily:    L30C.fontMono,
          fontSize:      10,
          color:         L30C.limeDim,
          letterSpacing: '2px',
        }}>
          {subtitle}
        </span>
      </div>

      {/* 랭킹 행 */}
      {rows.map((row, i) => {
        const prog = spring({
          frame: Math.max(0, f - showAt - 14 - i * 4),
          fps,
          config: { damping: 30, stiffness: 220, mass: 0.65 },
          durationInFrames: 16,
        });
        const op = prog;
        const tx = interpolate(prog, [0, 1], [18, 0]);

        return (
          <div key={i} style={{
            display:    'flex',
            alignItems: 'center',
            padding:    '9px 20px',
            gap:        14,
            opacity:    op * (row.excluded ? 0.30 : 1),
            transform:  `translateX(${tx}px)`,
            background: row.highlight ? 'rgba(170,255,0,0.06)' : 'transparent',
            borderBottom:
              i < rows.length - 1
                ? '1px solid rgba(170,255,0,0.07)'
                : 'none',
          }}>
            {/* 랭크 번호 */}
            <div style={{
              fontFamily:    L30C.fontMono,
              fontSize:      11,
              letterSpacing: '2px',
              color:         row.highlight ? L30C.lime : L30C.limeDim,
              width:         28,
              flexShrink:    0,
            }}>
              {row.rank}
            </div>

            {/* 국기 */}
            <div style={{ fontSize: 20, lineHeight: 1, flexShrink: 0 }}>
              {row.flag}
            </div>

            {/* 국가명 */}
            <div style={{
              fontFamily:    L30C.fontMono,
              fontSize:      12,
              letterSpacing: '2px',
              color:         row.highlight ? L30C.white : L30C.textDim,
              flex:          1,
              textTransform: 'uppercase',
            }}>
              {row.country}
            </div>

            {/* 시가총액 */}
            <div style={{
              fontFamily:    L30C.fontMain,
              fontSize:      15,
              fontWeight:    700,
              color:         row.highlight ? L30C.lime : L30C.white,
              textShadow:    row.highlight ? L30G.lime.text : undefined,
              flexShrink:    0,
              letterSpacing: '-0.3px',
            }}>
              {row.value}
            </div>

            {/* EXCL 뱃지 */}
            {row.excluded && (
              <div style={{
                fontFamily:    L30C.fontMono,
                fontSize:      8,
                letterSpacing: '2px',
                color:         L30C.limeDim,
                border:        `1px solid ${L30C.limeBorder}`,
                padding:       '2px 6px',
                flexShrink:    0,
              }}>
                EXCL
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
