/**
 * L30_TextReveal — 대형 선언문 텍스트 등장
 *
 * LIFE 3.0 스타일 (스크린샷6 "AI가 바꾼 것은 / 기술만이 아닙니다"):
 *   - 순수 블랙 배경
 *   - 좌측 정렬 대형 볼드 텍스트
 *   - 흰색 / 라임 교차 컬러링
 *   - 작은 서브텍스트 (모노스페이스)
 *   - 각 라인이 아래서 위로 스프링 등장
 *
 * 사용법:
 *   <L30_TextReveal
 *     topLabel="THE VERDICT"
 *     lines={[
 *       { text: 'AI가 바꾼 것은', color: 'white' },
 *       { text: '기술만이 아닙니다', color: 'lime' },
 *     ]}
 *     subLines={[
 *       { text: '숫자  —  시장  —  현실', color: 'white', size: 24 },
 *       { text: '데이터는 거짓말하지 않습니다.', color: 'dim', size: 18 },
 *     ]}
 *   />
 */

import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { clamp, L30C, L30G } from './L30_constants';

export interface TextLine {
  text:    string;
  color?:  'white' | 'lime' | 'dim';
  size?:   number;   // 폰트 크기 (default 72)
  weight?: number;   // 폰트 굵기 (default 900)
  mono?:   boolean;  // 모노스페이스 폰트
}

interface L30_TextRevealProps {
  topLabel?:  string;       // "THE VERDICT" (라임 소형 레이블)
  lines:      TextLine[];   // 메인 대형 텍스트 라인들
  subLines?:  TextLine[];   // 서브 텍스트 라인들
  startFrame?: number;
  leftPad?:   number;       // 좌측 여백 (default 80)
}

export const L30_TextReveal: React.FC<L30_TextRevealProps> = ({
  topLabel,
  lines,
  subLines,
  startFrame = 0,
  leftPad    = 80,
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const labelOp = clamp(f, startFrame, startFrame + 14);

  const getLineStyle = (line: TextLine): React.CSSProperties => ({
    fontFamily:  line.mono ? L30C.fontMono : L30C.fontMain,
    fontSize:    line.size   ?? 72,
    fontWeight:  line.weight ?? 900,
    lineHeight:  1.15,
    color:
      line.color === 'lime' ? L30C.lime :
      line.color === 'dim'  ? L30C.textDim :
      L30C.white,
    textShadow:  line.color === 'lime' ? L30G.lime.text : undefined,
  });

  return (
    <AbsoluteFill style={{ background: L30C.bg }}>
      <div style={{
        position:  'absolute',
        left:      leftPad,
        top:       '50%',
        transform: 'translateY(-50%)',
        maxWidth:  1400,
      }}>

        {/* 상단 소형 라임 레이블 */}
        {topLabel && (
          <div style={{
            fontFamily:    L30C.fontMono,
            fontSize:      12,
            fontWeight:    400,
            letterSpacing: '4px',
            textTransform: 'uppercase',
            color:         L30C.lime,
            opacity:       labelOp,
            marginBottom:  28,
          }}>
            {topLabel}
          </div>
        )}

        {/* 메인 텍스트 라인 */}
        {lines.map((line, i) => {
          const prog = spring({
            frame: Math.max(0, f - startFrame - i * 7),
            fps,
            config: { damping: 28, stiffness: 130, mass: 0.9 },
            durationInFrames: 26,
          });
          const op = clamp(f, startFrame + i * 7, startFrame + i * 7 + 18);
          const ty = interpolate(prog, [0, 1], [48, 0]);

          return (
            <div key={i} style={{
              ...getLineStyle(line),
              opacity:   op,
              transform: `translateY(${ty}px)`,
            }}>
              {line.text}
            </div>
          );
        })}

        {/* 서브 텍스트 라인 */}
        {subLines && subLines.length > 0 && (
          <div style={{ marginTop: 32 }}>
            {subLines.map((line, i) => {
              const baseDelay = startFrame + lines.length * 7;
              const op = clamp(f, baseDelay + i * 6, baseDelay + i * 6 + 16);
              const tx = interpolate(op, [0, 1], [-16, 0]);

              return (
                <div key={i} style={{
                  ...getLineStyle(line),
                  opacity:       op,
                  transform:     `translateX(${tx}px)`,
                  marginBottom:  i < subLines.length - 1 ? 10 : 0,
                  letterSpacing: line.mono ? '2px' : undefined,
                }}>
                  {line.text}
                </div>
              );
            })}
          </div>
        )}

      </div>
    </AbsoluteFill>
  );
};
