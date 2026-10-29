import React from 'react';
import {registerRoot, Composition, AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame, interpolate, Easing} from 'remotion';

const FPS = 30;
const css = `
@font-face{font-family:PS;src:url(${staticFile('Pretendard-SemiBold.otf')});font-weight:600}
@font-face{font-family:PB;src:url(${staticFile('Pretendard-ExtraBold.otf')});font-weight:800}
`;
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const OR = '#e8823a', INK = '#1a1816', PAPER = '#f3eee6';
const vids = ['a.mp4', 'b.mp4', 'c.mp4'];
const starts = [5, 4, 6]; // 영상 속 재생 시작(초)
const titles = ['해외 화장품 · 코팩', '해외 화장품 · 크림', '해외 화장품 · 선크림'];
const chips = ['원본 찾기 ✓', '대본 ✓', '목소리 ✓'];
const TITLE_S = 2.0, SC = 3.8, CLOSE_S = 1.8;
const TOTAL = TITLE_S + SC * 3 + CLOSE_S; // 15.2s

const Polaroid: React.FC<{i: number; rot: number; x: number; y: number; w: number; delay: number}> = ({i, rot, x, y, w, delay}) => {
  const f = useCurrentFrame();
  const p = interpolate(f / FPS, [delay, delay + 0.8], [0, 1], {...clamp, easing: ease});
  const h = w * 1.25;
  return (
    <div style={{position: 'absolute', left: x, top: y + (1 - p) * 120, width: w, height: h, background: PAPER, padding: 14, boxSizing: 'border-box',
      transform: `rotate(${rot * p}deg) scale(${0.9 + 0.1 * p})`, opacity: p, boxShadow: '0 24px 60px rgba(0,0,0,.55)'}}>
      <div style={{width: '100%', height: w - 28 + 40, overflow: 'hidden', background: '#000'}}>
        <OffthreadVideo src={staticFile(vids[i])} muted startFrom={Math.round(starts[i] * FPS)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </div>
    </div>
  );
};

const Polaroids: React.FC<{base: number}> = ({base}) => (
  <>
    <Polaroid i={0} rot={-9} x={90} y={base + 60} w={400} delay={0.3} />
    <Polaroid i={1} rot={4} x={340} y={base} w={400} delay={0.5} />
    <Polaroid i={2} rot={11} x={590} y={base + 70} w={400} delay={0.7} />
  </>
);

const TitleCard: React.FC = () => {
  const f = useCurrentFrame(); const t = f / FPS;
  const a = interpolate(t, [0.1, 0.8], [0, 1], {...clamp, easing: ease});
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 0, right: 0, top: 200, textAlign: 'center', fontFamily: 'PB', fontWeight: 800, fontSize: 118, lineHeight: 1.2, color: PAPER,
        opacity: a, transform: `translateY(${(1 - a) * 50}px)`, letterSpacing: '-0.02em'}}>
        말 한 줄로 만든<br /><span style={{color: OR}}>쇼츠 3편</span>
      </div>
      <Polaroids base={720} />
    </AbsoluteFill>
  );
};

const PW = 680, PH = 1200, PTOP = 330; // 폰 카드 높이 62.5%
const Item: React.FC<{i: number}> = ({i}) => {
  const f = useCurrentFrame(); const t = f / FPS;
  const inP = interpolate(t, [0, 0.8], [0, 1], {...clamp, easing: ease});
  const outP = interpolate(t, [SC - 0.5, SC], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const x = (1 - inP) * 1100 - outP * 1200;
  const rot = (1 - inP) * 9 - outP * 10;
  const tOp = interpolate(t, [0.1, 0.6], [0, 1], {...clamp, easing: ease}) * (1 - outP);
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 70, top: 80, opacity: tOp, transform: `translateY(${(1 - tOp) * 30}px)`}}>
        <div style={{fontFamily: 'PB', fontWeight: 800, fontSize: 58, color: OR, letterSpacing: '0.12em'}}>0{i + 1}</div>
        <div style={{fontFamily: 'PB', fontWeight: 800, fontSize: 96, color: PAPER, letterSpacing: '-0.03em', whiteSpace: 'nowrap', marginTop: 2}}>{titles[i]}</div>
      </div>
      <div style={{position: 'absolute', left: (1080 - PW) / 2, top: PTOP, width: PW, height: PH, borderRadius: 54, background: '#0a0a0a', padding: 16, boxSizing: 'border-box',
        transform: `translateX(${x}px) rotate(${rot}deg)`, boxShadow: '0 0 0 2px #3a3633, 0 40px 90px rgba(0,0,0,.6)'}}>
        <div style={{width: '100%', height: '100%', borderRadius: 40, overflow: 'hidden', background: '#000'}}>
          <OffthreadVideo src={staticFile(vids[i])} volume={0.1} startFrom={Math.round(starts[i] * FPS)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </div>
      </div>
      {chips.map((c, k) => {
        const s = 1.0 + k * 0.7;
        const p = interpolate(t, [s, s + 0.45], [0, 1], {...clamp, easing: ease});
        const o = p * (1 - outP);
        return (
          <div key={k} style={{position: 'absolute', left: 0, right: 0, top: 1560 + k * 98, display: 'flex', justifyContent: 'center', opacity: o,
            transform: `translateY(${(1 - p) * 40}px) scale(${0.92 + 0.08 * p})`}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 18, background: OR, color: '#1a0f08', borderRadius: 999, padding: '10px 48px 10px 28px',
              fontFamily: 'PS', fontWeight: 600, fontSize: 50, lineHeight: 1.2}}>
              <span style={{width: 18, height: 18, borderRadius: 9, background: '#1a0f08', display: 'inline-block'}} />{c}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const Close: React.FC = () => {
  const f = useCurrentFrame(); const t = f / FPS;
  const a = interpolate(t, [0.1, 0.7], [0, 1], {...clamp, easing: ease});
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 0, right: 0, top: 640, textAlign: 'center', fontFamily: 'PB', fontWeight: 800, fontSize: 124, color: PAPER,
        opacity: a, transform: `translateY(${(1 - a) * 50}px)`, letterSpacing: '-0.02em', lineHeight: 1.25}}>
        말 <span style={{color: OR}}>한 줄</span>이면<br />됩니다
      </div>
    </AbsoluteFill>
  );
};

const Scene: React.FC = () => (
  <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 110%, #3a1c10 0%, ${INK} 62%)`}}>
    <style>{css}</style>
    <Sequence from={0} durationInFrames={Math.round(TITLE_S * FPS)}><TitleCard /></Sequence>
    {[0, 1, 2].map((i) => (
      <Sequence key={i} from={Math.round((TITLE_S + SC * i) * FPS)} durationInFrames={Math.round(SC * FPS)}><Item i={i} /></Sequence>
    ))}
    <Sequence from={Math.round((TITLE_S + SC * 3) * FPS)} durationInFrames={Math.round(CLOSE_S * FPS)}><Close /></Sequence>
  </AbsoluteFill>
);

const Root: React.FC = () => <Composition id="J2" component={Scene} durationInFrames={Math.round(TOTAL * FPS)} fps={FPS} width={1080} height={1920} />;
registerRoot(Root);
