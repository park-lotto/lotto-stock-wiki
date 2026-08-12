/**
 * 자막 강조 3안 비교판 — "투박하다"는 지적(2026-08-12)에 대한 선택지.
 * 같은 문장·같은 배경에서 표현만 바꿔 한 화면에 쌓아 비교한다.
 */
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { KineticWord, MINT, FONT } from './motion';
import { RichBed } from './motion4';

const SAMPLE = '1기에서만 |1년 77만 원|에 시작합니다.';

const Row: React.FC<{
  hi: 'stamp' | 'underline' | 'plate'; name: string; desc: string; top: number;
}> = ({ hi, name, desc, top }) => (
  <div style={{ position: 'absolute', left: 0, right: 0, top }}>
    <div style={{
      position: 'absolute', left: 60, top: -6,
      fontFamily: FONT, fontWeight: 900, fontSize: 30, color: MINT,
    }}>
      {name}
      <span style={{ color: '#ffffff88', fontSize: 22, marginLeft: 12 }}>{desc}</span>
    </div>
    <div style={{ position: 'relative', height: 150 }}>
      <KineticWord text={SAMPLE} size={54} center hi={hi} perWord={1.2} />
    </div>
  </div>
);

export const StyleCompare: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: '#08110E' }}>
      <RichBed kind="work" />
      <AbsoluteFill style={{ background: 'rgba(4,10,8,0.55)' }} />
      <div style={{
        position: 'absolute', left: 60, top: 40,
        fontFamily: FONT, fontWeight: 900, fontSize: 40, color: '#fff',
      }}>자막 강조 3안 — 같은 문장, 표현만 다름</div>
      <Row hi="stamp" name="A · 스탬프" desc="현재 방식. 통짜 형광 박스" top={220} />
      <Row hi="underline" name="B · 형광펜" desc="흰 글자 + 두꺼운 형광 밑줄" top={560} />
      <Row hi="plate" name="C · 플레이트" desc="짙은 판 + 형광 테두리·글자" top={900} />
      <div style={{
        position: 'absolute', left: 60, bottom: 40,
        fontFamily: FONT, fontWeight: 700, fontSize: 26, color: '#ffffffaa',
      }}>frame {frame}</div>
    </AbsoluteFill>
  );
};
