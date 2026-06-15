/**
 * L30_BarChart — 국가 막대차트
 *
 * 영상 레퍼런스: https://youtu.be/kI1soqlxwl8
 *   - 라벨 순서 (위→아래): 깃발 → 국가 → 값 → 바
 *   - 3D 바 효과: 다크 스틸 그라데이션 + 상단/우측 엣지
 *   - NVIDIA 수평 기준선: 차트 최상단 가로선 + 우측 레이블
 *   - PiP: 우하단 세로 모드 포트레이트
 */

import React from 'react';
import {
  AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig,
} from 'remotion';
import { clamp, L30C, L30G, L30V } from './L30_constants';

export interface BarItem {
  flag:    string;   // 이모지 국기 "🇰🇷"
  country: string;   // "한국"
  value:   string;   // "$4.5T"
  pct:     number;   // 0~100 (NVIDIA = 100 기준)
}

interface L30_BarChartProps {
  bars:            BarItem[];
  chartTitle?:     string;    // 좌상단 레이블
  referenceLabel?: string;    // "NVIDIA · $5.5T"
  refSubLabel?:    string;    // "REFERENCE CEILING"
  maxBarH?:        number;    // 최대 바 높이 px (default 520)
  startFrame?:     number;
}

const BAR_W    = 160;
const BAR_GAP  = 90;
const FLAG_SZ  = 64;
const CHART_BOTTOM = 80;   // 바 그룹 하단 오프셋

export const L30_BarChart: React.FC<L30_BarChartProps> = ({
  bars,
  chartTitle   = 'MARKET CAP · LISTED EQUITIES',
  referenceLabel,
  refSubLabel  = 'REFERENCE CEILING',
  maxBarH      = 520,
  startFrame   = 0,
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOp = clamp(f, startFrame, startFrame + 18);
  const refOp   = clamp(f, startFrame + 25, startFrame + 45);

  // 참조선 위치: 캔버스 하단에서 CHART_BOTTOM + maxBarH
  const refLineBottom = CHART_BOTTOM + maxBarH;

  return (
    <AbsoluteFill style={{ background: L30C.bg }}>

      {/* ① 좌상단 타이틀 */}
      <div style={{
        position:      'absolute',
        top:           52,
        left:          L30V.PAD,
        display:       'flex',
        alignItems:    'center',
        gap:           8,
        opacity:       titleOp,
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: L30C.lime,
          boxShadow: `0 0 6px ${L30C.lime}`,
        }} />
        <div style={{
          fontFamily:    L30C.fontMono,
          fontSize:      11,
          fontWeight:    400,
          letterSpacing: '3px',
          textTransform: 'uppercase',
          color:         L30C.lime,
        }}>
          {chartTitle}
        </div>
      </div>

      {/* ② NVIDIA 수평 기준선 */}
      {referenceLabel && (
        <div style={{
          position:  'absolute',
          left:      L30V.PAD,
          right:     L30V.PAD,
          bottom:    refLineBottom,
          height:    1,
          background: `linear-gradient(to right, transparent 0%, ${L30C.lime} 8%, ${L30C.lime} 80%, transparent 100%)`,
          boxShadow: `0 0 10px ${L30C.lime}66`,
          opacity:   refOp,
        }}>
          {/* 우측 레이블 */}
          <div style={{
            position:  'absolute',
            right:     0,
            bottom:    8,
            textAlign: 'right',
          }}>
            <div style={{
              fontFamily:    L30C.fontMono,
              fontSize:      18,
              fontWeight:    700,
              color:         L30C.lime,
              letterSpacing: '2px',
              textShadow:    L30G.lime.text,
            }}>
              {referenceLabel}
            </div>
            <div style={{
              fontFamily:    L30C.fontMono,
              fontSize:      9,
              fontWeight:    400,
              color:         L30C.lime,
              letterSpacing: '3px',
              textTransform: 'uppercase',
              opacity:       0.7,
            }}>
              {refSubLabel}
            </div>
          </div>
        </div>
      )}

      {/* ③ 바 그룹 */}
      <div style={{
        position:   'absolute',
        bottom:     CHART_BOTTOM,
        left:       '50%',
        transform:  'translateX(-50%)',
        display:    'flex',
        alignItems: 'flex-end',
        gap:        BAR_GAP,
      }}>
        {bars.map((bar, i) => {
          const barProg = spring({
            frame: Math.max(0, f - startFrame - i * 12),
            fps,
            config: { damping: 26, stiffness: 85, mass: 1.4 },
            durationInFrames: 48,
          });
          const barH    = bar.pct / 100 * maxBarH * barProg;
          const labelOp = interpolate(barProg, [0.6, 1], [0, 1], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          });
          const labelTy = interpolate(barProg, [0.6, 1], [10, 0], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          });

          return (
            <div key={i} style={{
              display:       'flex',
              flexDirection: 'column',
              alignItems:    'center',
              width:         BAR_W,
            }}>
              {/* ── 라벨 그룹 (순서: 깃발 → 국가 → 값) ── */}
              <div style={{
                display:       'flex',
                flexDirection: 'column',
                alignItems:    'center',
                gap:           8,
                opacity:       labelOp,
                transform:     `translateY(${labelTy}px)`,
                marginBottom:  16,
              }}>
                {/* 1. 깃발 */}
                <div style={{
                  width:          FLAG_SZ,
                  height:         FLAG_SZ,
                  borderRadius:   '50%',
                  background:     'rgba(255,255,255,0.06)',
                  border:         '1.5px solid rgba(255,255,255,0.20)',
                  display:        'flex',
                  alignItems:     'center',
                  justifyContent: 'center',
                  fontSize:       36,
                  lineHeight:     1,
                }}>
                  {bar.flag}
                </div>

                {/* 2. 국가명 */}
                <div style={{
                  fontFamily: L30C.fontMain,
                  fontSize:   15,
                  fontWeight: 500,
                  color:      L30C.white,
                  letterSpacing: '0.5px',
                }}>
                  {bar.country}
                </div>

                {/* 3. 값 */}
                <div style={{
                  fontFamily:    L30C.fontMain,
                  fontSize:      28,
                  fontWeight:    900,
                  color:         L30C.lime,
                  textShadow:    L30G.lime.text,
                  letterSpacing: '-0.5px',
                  lineHeight:    1,
                }}>
                  {bar.value}
                </div>
              </div>

              {/* ── 4. 3D 바 ── */}
              <div style={{ position: 'relative', width: BAR_W, flexShrink: 0 }}>
                {/* 상단 캡 (3D top face) */}
                <div style={{
                  position:   'absolute',
                  top:        -6,
                  left:       -8,
                  width:      BAR_W + 8,
                  height:     6,
                  background: 'linear-gradient(to bottom, #3A4760 0%, #28324A 100%)',
                }} />
                {/* 우측 면 (3D right face) */}
                <div style={{
                  position:   'absolute',
                  top:        -4,
                  right:      -8,
                  width:      8,
                  height:     barH + 4,
                  background: 'linear-gradient(to right, #141B2A, #0D1220)',
                }} />
                {/* 정면 (front face) */}
                <div style={{
                  width:        BAR_W,
                  height:       barH,
                  background:   'linear-gradient(160deg, #28354A 0%, #1C2840 45%, #141C30 100%)',
                  borderTop:    '1px solid rgba(255,255,255,0.10)',
                  borderLeft:   '1px solid rgba(255,255,255,0.04)',
                  flexShrink:   0,
                }} />
              </div>
            </div>
          );
        })}
      </div>

    </AbsoluteFill>
  );
};
