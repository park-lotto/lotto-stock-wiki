// Vertex 키 발급 안내 영상 — 장면(캡처+강조상자+자막)을 scenes.json 그대로 이어 붙인다.
// 장면 정의·가림 처리는 prep.py 한 곳에서만 한다(여기는 그리기만).
import React from 'react';
import {AbsoluteFill, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type Scene = {file: string; w: number; h: number; step: string; title: string; cap: string[]; hl: number[][]};
export type GuideProps = {scenes: Scene[]};

const FPS = 30;
const INTRO = 3.2 * FPS;
const PER = 6 * FPS;
const OUTRO = 3.5 * FPS;
export const guideDuration = (scenes: Scene[]) => INTRO + PER * scenes.length + OUTRO;

const FONT = '"Pretendard","Malgun Gothic","Apple SD Gothic Neo",sans-serif';
const BG = '#0b1418';
const MINT = '#34e0b5';
const HL = '#ff3d6e';

const HEAD_H = 120;
const CAP_H = 190;

const Intro: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 14}});
  const o = interpolate(f, [12, 28], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: BG, color: 'white', fontFamily: FONT, justifyContent: 'center', alignItems: 'center'}}>
      <div style={{fontSize: 44, color: MINT, fontWeight: 700, opacity: o}}>숏템메이커 · 설정 가이드</div>
      <div style={{fontSize: 96, fontWeight: 900, marginTop: 18, transform: `scale(${s})`}}>🚀 내 구글 Vertex 연결</div>
      <div style={{fontSize: 46, marginTop: 28, opacity: o}}>키(.json) 받는 법 — 5단계</div>
    </AbsoluteFill>
  );
};

const Outro: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 14}});
  return (
    <AbsoluteFill style={{background: BG, color: 'white', fontFamily: FONT, justifyContent: 'center', alignItems: 'center'}}>
      <div style={{fontSize: 92, fontWeight: 900, transform: `scale(${s})`}}>✅ 연결 끝!</div>
      <div style={{fontSize: 44, marginTop: 30, lineHeight: 1.5, textAlign: 'center'}}>
        대본 쓰기·장면 매칭이 내 구글 Vertex로 돌아가요<br />막히면 화면에 원인과 할 일이 나와요
      </div>
    </AbsoluteFill>
  );
};

const Shot: React.FC<{sc: Scene}> = ({sc}) => {
  const f = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const areaW = width - 120;
  const areaH = height - HEAD_H - CAP_H - 40;
  const k = Math.min(areaW / sc.w, areaH / sc.h, 2.2);
  const dw = sc.w * k, dh = sc.h * k;
  const left = (width - dw) / 2, top = HEAD_H + 20 + (areaH - dh) / 2;
  const enter = spring({frame: f, fps, config: {damping: 16}});
  const zoom = interpolate(f, [0, PER], [1, 1.035]);
  const capO = interpolate(f, [6, 18], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: BG, fontFamily: FONT, color: 'white'}}>
      <div style={{position: 'absolute', left: 0, top: 0, width, height: HEAD_H, display: 'flex', alignItems: 'center', padding: '0 60px', gap: 26}}>
        <div style={{background: MINT, color: '#062019', fontWeight: 900, fontSize: 44, borderRadius: 18, padding: '8px 26px'}}>{sc.step}</div>
        <div style={{fontSize: 52, fontWeight: 800}}>{sc.title}</div>
      </div>
      <div style={{position: 'absolute', left, top, width: dw, height: dh, opacity: enter,
        transform: `scale(${(0.96 + 0.04 * enter) * zoom})`, transformOrigin: 'center', borderRadius: 14, overflow: 'hidden',
        boxShadow: '0 20px 60px rgba(0,0,0,.55)', background: 'white'}}>
        <Img src={staticFile(sc.file)} style={{width: dw, height: dh, display: 'block'}} />
        {sc.hl.map(([x, y, w, h], i) => {
          const start = 16 + i * 38;
          const a = interpolate(f, [start, start + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          // 크기는 고정(상자가 줄면 대상 안쪽으로 들어간다) — 깜빡임은 빛 번짐으로만
          const glow = 10 + 10 * (0.5 + 0.5 * Math.sin(Math.max(0, f - start) / 5));
          const pad = 8;
          return (
            <div key={i} style={{position: 'absolute', left: x * k - pad, top: y * k - pad, width: w * k + pad * 2, height: h * k + pad * 2,
              boxSizing: 'border-box', border: `6px solid ${HL}`, borderRadius: 12, opacity: a,
              boxShadow: `0 0 ${glow}px ${HL}`}} />
          );
        })}
      </div>
      <div style={{position: 'absolute', left: 0, bottom: 0, width, height: CAP_H, background: 'rgba(0,0,0,.72)',
        display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 10, opacity: capO}}>
        {sc.cap.map((line, i) => (
          <div key={i} style={{fontSize: i === 0 ? 50 : 40, fontWeight: i === 0 ? 800 : 600, color: i === 0 ? 'white' : '#cfe9e2'}}>{line}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

export const Guide: React.FC<GuideProps> = ({scenes}) => (
  <AbsoluteFill style={{background: BG}}>
    <Sequence durationInFrames={INTRO}><Intro /></Sequence>
    {scenes.map((sc, i) => (
      <Sequence key={i} from={INTRO + i * PER} durationInFrames={PER}><Shot sc={sc} /></Sequence>
    ))}
    <Sequence from={INTRO + scenes.length * PER} durationInFrames={OUTRO}><Outro /></Sequence>
  </AbsoluteFill>
);
