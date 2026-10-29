import React from 'react';
import {registerRoot, Composition, AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, interpolate, Easing} from 'remotion';

const FPS = 30;
const css = `
@font-face{font-family:PB;src:url(${staticFile('Pretendard-ExtraBold.otf')});font-weight:800}
@font-face{font-family:NGC;src:url(${staticFile('NanumGothicCoding-Bold.ttf')})}
`;
const ease = Easing.bezier(0.16, 1, 0.3, 1); // ease-out expo
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const CH = 800, CW = Math.round(CH * 9 / 16), GAP = 56, TOP = 24;
const vids = ['a.mp4', 'b.mp4', 'c.mp4'];
const vol = [0, 0.1, 0]; // 가운데 카드만 -20dB

const Scene: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / FPS;
  // 터미널 글자
  const tIn = interpolate(t, [0.2, 0.5], [0, 1], clamp);
  const tOut = interpolate(t, [2.0, 2.7], [0, 1], {...clamp, easing: ease});
  const termY = 540 - 0 - tOut * 700;
  const termOp = tIn * (1 - interpolate(t, [2.0, 2.6], [0, 1], clamp));
  const cursor = Math.floor(t * 2) % 2 === 0 && t < 2.2;
  // 최종 글자
  const endIn = interpolate(t, [11.0, 11.5], [0, 1], {...clamp, easing: ease});
  return (
    <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 120%, #3a1a10 0%, #0e0d0d 60%)'}}>
      <style>{css}</style>
      <div style={{position: 'absolute', left: 0, right: 0, top: termY - 30, textAlign: 'center', opacity: termOp,
        fontFamily: 'NGC, monospace', fontWeight: 700, fontSize: 44, color: '#f3f1ef', letterSpacing: '0.02em'}}>
        <span style={{color: '#f0613a', fontFamily: '"Segoe UI Symbol", sans-serif'}}>✓</span> 완성 3편
        <span style={{opacity: cursor ? 1 : 0, color: '#f0613a'}}>▌</span>
      </div>
      {vids.map((v, i) => {
        const start = 2.0 + i * 0.5; // 박자(120BPM 1박=0.5s)
        const p = interpolate(t, [start, start + 0.9], [0, 1], {...clamp, easing: ease});
        const x = 960 - CW / 2 + (i - 1) * (CW + GAP);
        const y = TOP + (1 - p) * 1100;
        const sc = i === 1 ? 1.0 : 1.0;
        return (
          <div key={v} style={{position: 'absolute', left: x, top: y, width: CW, height: CH, opacity: p > 0 ? 1 : 0,
            borderRadius: 28, overflow: 'hidden', boxShadow: '0 30px 80px rgba(240,97,58,0.25), 0 0 0 2px rgba(243,241,239,0.12)', transform: `scale(${sc})`}}>
            <OffthreadVideo src={staticFile(v)} volume={vol[i]} startFrom={Math.round(0.0 * FPS)}
              style={{width: '100%', height: '100%', objectFit: 'cover'}} />
          </div>
        );
      })}
      <div style={{position: 'absolute', left: 0, right: 0, top: 862, textAlign: 'center', opacity: endIn,
        transform: `translateY(${(1 - endIn) * 40}px)`, fontFamily: 'PB, sans-serif', fontWeight: 800, fontSize: 120,
        color: '#f3f1ef', letterSpacing: '-0.02em'}}>
        말 한 줄로 나온 <span style={{color: '#f0613a'}}>3편</span>
      </div>
    </AbsoluteFill>
  );
};

const Root: React.FC = () => <Composition id="I1" component={Scene} durationInFrames={12 * FPS} fps={FPS} width={1920} height={1080} />;
registerRoot(Root);
