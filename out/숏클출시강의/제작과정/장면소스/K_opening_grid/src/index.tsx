import React from 'react';
import {registerRoot, Composition, AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, interpolate, Easing} from 'remotion';

const FPS = 30;
const css = `@font-face{font-family:PB;src:url(${staticFile('Pretendard-ExtraBold.otf')});font-weight:800}`;
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const cl = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const sec = (t: number, a: number, b: number) => interpolate(t, [a, b], [0, 1], {...cl, easing: ease});
const GREEN = '#5fe3c0';
// [card, start, duration]
const SPW: [number, number, number][] = [[5, 5.6, 2.2], [4, 8.0, 2.8], [0, 10.9, 1.7], [3, 12.8, 2.3]];
const SPT: [number, number, number][] = [[5, 3.4, 2.2], [4, 5.8, 2.8], [0, 8.8, 1.7]];

// 0..1 강조 (0.25초 안에 올라가고 0.25초 안에 내려간다)
const spotAmt = (t: number, sp: [number, number, number][], i: number) => {
  const s = sp.find((x) => x[0] === i);
  if (!s) return 0;
  return sec(t, s[1], s[1] + 0.25) * (1 - sec(t, s[1] + s[2] - 0.25, s[1] + s[2]));
};

const Card: React.FC<{i: number; w: number; h: number; pre: string; amt: number}> = ({i, w, h, pre, amt}) => (
  <div style={{width: w, height: h, borderRadius: 22, overflow: 'hidden', background: '#000',
    boxShadow: `0 18px 44px rgba(0,0,0,0.55), 0 0 0 ${6 * amt}px rgba(255,255,255,${amt}), 0 0 ${60 * amt}px ${10 * amt}px rgba(95,227,192,${0.7 * amt})`}}>
    <OffthreadVideo src={staticFile(`${pre}${i + 1}.mp4`)} volume={0} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
  </div>
);

const Wide: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const W = 270, H = 480, G = 28;
  const pos = (i: number) => {
    const row = i < 5 ? 0 : 1, n = row === 0 ? 5 : 4, c = row === 0 ? i : i - 5;
    const rw = n * W + (n - 1) * G;
    return {x: (1920 - rw) / 2 + c * (W + G), y: 36 + row * (H + G)};
  };
  const back = sec(t, 15.4, 16.3);
  const t1 = sec(t, 0.2, 0.8) * (1 - sec(t, 1.6, 2.0));
  const t2 = sec(t, 15.7, 16.5);
  return (
    <AbsoluteFill style={{background: '#0d0d14'}}>
      <style>{css}</style>
      {t < 2.2 && <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'PB', fontWeight: 800,
        fontSize: 190, color: '#fff', letterSpacing: '-0.03em', opacity: t1, transform: `translateY(${(1 - t1) * 50}px)`}}>
        클로드로 <span style={{color: GREEN}}>'딸깍'</span></div>}
      <AbsoluteFill style={{transform: `translateY(${back * 300}px) scale(${1 - back * 0.28})`, transformOrigin: '50% 0%'}}>
        {Array.from({length: 9}, (_, i) => {
          const {x, y} = pos(i);
          const st = 2.0 + i * 0.3;
          const p = interpolate(t, [st, st + 0.9], [0, 1], {...cl, easing: ease});
          if (t < st) return null;
          const a = spotAmt(t, SPW, i);
          return <div key={i} style={{position: 'absolute', left: x, top: y, opacity: Math.min(1, p * 3), zIndex: a > 0 ? 10 : 1,
            transform: `translate(${(960 - W / 2 - x) * (1 - p)}px, ${(1080 - y) * (1 - p)}px) scale(${(0.3 + 0.7 * p) * (1 + 0.12 * a)})`}}><Card i={i} w={W} h={H} pre="vw" amt={a} /></div>;
        })}
      </AbsoluteFill>
      {t > 15.6 && <div style={{position: 'absolute', left: 0, right: 0, top: 18, textAlign: 'center', fontFamily: 'PB', fontWeight: 800, fontSize: 124, lineHeight: 1.12,
        color: '#fff', letterSpacing: '-0.03em', opacity: t2, transform: `translateY(${(1 - t2) * 40}px)`}}>
        진짜 <span style={{color: GREEN}}>클로드의 딸깍,</span><br />보여 드립니다</div>}
    </AbsoluteFill>
  );
};

const Tall: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const W = 275, H = 490, G = 18;
  const gx = (1080 - (3 * W + 2 * G)) / 2, gy = 390;
  const tp = sec(t, 0.1, 0.8);
  return (
    <AbsoluteFill style={{background: '#0d0d14'}}>
      <style>{css}</style>
      <div style={{position: 'absolute', left: 0, right: 0, top: 70, textAlign: 'center', fontFamily: 'PB', fontWeight: 800, fontSize: 124, lineHeight: 1.2,
        color: '#fff', letterSpacing: '-0.03em', opacity: tp, transform: `translateY(${(1 - tp) * 40}px)`}}>
        이 쇼츠들,<br /><span style={{color: GREEN}}>한 줄로 나왔습니다</span></div>
      {Array.from({length: 9}, (_, i) => {
        const c = i % 3, r = Math.floor(i / 3);
        const x = gx + c * (W + G), y = gy + r * (H + G);
        const st = 0.5 + i * 0.22;
        if (t < st) return null;
        const p = interpolate(t, [st, st + 0.8], [0, 1], {...cl, easing: ease});
        const a = spotAmt(t, SPT, i);
        return <div key={i} style={{position: 'absolute', left: x, top: y, opacity: Math.min(1, p * 3), zIndex: a > 0 ? 10 : 1,
          transform: `translate(${(540 - W / 2 - x) * (1 - p)}px, ${(1000 - y) * (1 - p)}px) scale(${(0.3 + 0.7 * p) * (1 + 0.12 * a)})`}}><Card i={i} w={W} h={H} pre="vt" amt={a} /></div>;
      })}
    </AbsoluteFill>
  );
};

const Root: React.FC = () => (<>
  <Composition id="Wide" component={Wide} durationInFrames={18 * FPS} fps={FPS} width={1920} height={1080} />
  <Composition id="Tall" component={Tall} durationInFrames={12 * FPS} fps={FPS} width={1080} height={1920} />
</>);
registerRoot(Root);
