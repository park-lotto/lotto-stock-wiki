import React from 'react';
import {registerRoot, Composition, AbsoluteFill, OffthreadVideo, Sequence, Img, staticFile, useCurrentFrame, interpolate, Easing} from 'remotion';

const FPS = 30;
const css = `
@font-face{font-family:PS;src:url(${staticFile('Pretendard-SemiBold.otf')});font-weight:600}
@font-face{font-family:PB;src:url(${staticFile('Pretendard-ExtraBold.otf')});font-weight:800}
`;
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const cl = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const GREEN = '#1f9a7c', INK = '#16152e', NAVY = '#1d1b6b';
const sec = (t: number, a: number, b: number, e = true) => interpolate(t, [a, b], [0, 1], {...cl, easing: e ? ease : undefined});

// 격자 3x3: 카드 9:16, 재생 3칸(서로 다른 3편) + 같은 영상의 다른 장면 6칸
const CW = 290, CH = 516, GX = 24, GY = 24;
type Slot = {v?: string; from?: number; img?: string; vol?: number};
const slots: Slot[] = [
  {img: 's_a3.jpg'}, {img: 's_b9.jpg'}, {v: 'a.mp4', from: 2},
  {v: 'b.mp4', from: 6, vol: 0.1}, {img: 's_c17.jpg'}, {img: 's_a17.jpg'},
  {v: 'c.mp4', from: 4}, {img: 's_b3.jpg'}, {img: 's_c9.jpg'},
];
const cmp = [{v: 'a.mp4', from: 12}, {v: 'b.mp4', from: 2}, {v: 'c.mp4', from: 8}];

const Card: React.FC<{s: Slot; style?: React.CSSProperties; w?: number; h?: number; vol?: number}> = ({s, style, w = CW, h = CH, vol}) => (
  <div style={{width: w, height: h, borderRadius: 28, overflow: 'hidden', background: '#fff',
    boxShadow: '0 24px 60px rgba(22,21,46,0.18), 0 2px 6px rgba(22,21,46,0.10)', ...style}}>
    {s.v ? <OffthreadVideo src={staticFile(s.v)} startFrom={Math.round((s.from ?? 0) * FPS)} volume={vol ?? s.vol ?? 0} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      : <Img src={staticFile(s.img!)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />}
  </div>
);

const Title: React.FC<{children: React.ReactNode; t: number; a: number; b: number; top?: number; size?: number}> = ({children, t, a, b, top = 150, size = 110}) => {
  const p = sec(t, a, a + 0.5);
  const o = 1 - sec(t, b, b + 0.35, false);
  return <div style={{position: 'absolute', left: 0, right: 0, top, textAlign: 'center', fontFamily: 'PB', fontWeight: 800, fontSize: size,
    letterSpacing: '-0.03em', color: INK, opacity: p * o, transform: `translateY(${(1 - p) * 40}px)`, filter: `blur(${(1 - p) * 8}px)`}}>{children}</div>;
};

const Scene: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / FPS;
  const text = '해외 화장품 쇼츠 만들어줘';
  const typed = text.slice(0, Math.floor(interpolate(t, [0.5, 2.3], [0, text.length], cl)));
  const cardIn = sec(t, 0.1, 0.8);
  const scan = sec(t, 2.6, 3.4, false);
  const cardOut = sec(t, 3.4, 4.0);
  const slotXY = (i: number) => {
    const c = i % 3, r = Math.floor(i / 3);
    return {x: 540 - (3 * CW + 2 * GX) / 2 + c * (CW + GX), y: 280 + r * (CH + GY)};
  };
  const gridOut = sec(t, 9.3, 9.9);
  const drift = sec(t, 5.4, 9.6, false);
  const gridVis = t >= 3.3 && t < 10.0;
  const cmpIn = sec(t, 9.6, 10.2);
  const cmpOut = sec(t, 12.4, 12.9, false);
  const idx = Math.min(2, Math.floor(Math.max(0, t - 10.3) / 0.9));
  const wipe = interpolate(t, [12.6, 13.4], [0, 1900], {...cl, easing: ease});
  const endP = sec(t, 13.4, 13.9);
  const endP2 = sec(t, 13.8, 14.3);

  return (
    <AbsoluteFill style={{background: '#f7f6f2'}}>
      <style>{css}</style>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse 70% 40% at 90% 0%, #e6f3ea 0%, rgba(230,243,234,0) 70%)'}} />
      <div style={{position: 'absolute', top: 60, left: 0, right: 0, textAlign: 'center', fontFamily: 'PS', fontWeight: 600, fontSize: 48, color: INK, opacity: t < 12.6 ? 1 : 0}}>
        <span style={{color: GREEN}}>●</span> 숏클메이커
      </div>

      <Title t={t} a={0.1} b={3.2}>말 <span style={{color: GREEN}}>한 줄</span>만 쓰세요</Title>
      {t < 4.1 && (
        <div style={{position: 'absolute', left: 90, width: 900, top: 760, height: 220, borderRadius: 36, background: '#fff', overflow: 'hidden',
          boxShadow: '0 24px 60px rgba(22,21,46,0.16), 0 2px 6px rgba(22,21,46,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          opacity: cardIn * (1 - cardOut), transform: `translateY(${(1 - cardIn) * 50}px) scale(${1 - cardOut * 0.7})`}}>
          <div style={{fontFamily: 'PS', fontWeight: 600, fontSize: 56, color: INK, letterSpacing: '-0.02em'}}>
            {typed}<span style={{color: GREEN, opacity: Math.floor(t * 2.5) % 2 === 0 && t < 2.6 ? 1 : 0}}>|</span>
          </div>
          <div style={{position: 'absolute', left: 0, right: 0, top: scan * 220 - 3, height: 6, background: '#2bd1a8',
            boxShadow: '0 0 30px 8px rgba(43,209,168,0.6)', opacity: scan > 0 && scan < 1 ? 1 : 0}} />
        </div>
      )}

      {gridVis && (
        <>
          <Title t={t} a={3.7} b={9.3} top={150}>쇼츠가 <span style={{color: GREEN}}>쏟아집니다</span></Title>
          <AbsoluteFill style={{perspective: 2400, opacity: 1 - gridOut, transform: `scale(${1 - gridOut * 0.08})`}}>
            <div style={{position: 'absolute', inset: 0, transformOrigin: '50% 60%',
              transform: `rotateX(${14 * sec(t, 5.0, 5.9)}deg) rotateZ(${-6 * sec(t, 5.0, 5.9)}deg) translateY(${-60 * drift}px)`}}>
              {slots.map((s, i) => {
                const {x, y} = slotXY(i);
                const st = 3.4 + i * 0.09;
                const p = interpolate(t, [st, st + 0.8], [0, 1], {...cl, easing: ease});
                const fx = 540 - CW / 2, fy = 770;
                const dx = (fx - x) * (1 - p), dy = (fy - y) * (1 - p);
                return (
                  <div key={i} style={{position: 'absolute', left: x, top: y, opacity: Math.min(1, p * 3),
                    transform: `translate(${dx}px, ${dy}px) scale(${0.25 + 0.75 * p})`}}>
                    <Card s={s} />
                  </div>
                );
              })}
            </div>
          </AbsoluteFill>
        </>
      )}

      {t >= 9.5 && t < 13.0 && (
        <AbsoluteFill style={{opacity: cmpIn * (1 - cmpOut), transform: `translateY(${(1 - cmpIn) * 60}px)`}}>
          <div style={{position: 'absolute', top: 170, left: 0, right: 0, textAlign: 'center', fontFamily: 'PS', fontWeight: 600, fontSize: 56, color: '#6a6a78'}}>말 한 줄</div>
          <div style={{position: 'absolute', left: 90, width: 900, top: 260, height: 190, borderRadius: 32, background: '#fff',
            boxShadow: '0 20px 50px rgba(22,21,46,0.14)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'PS', fontWeight: 600, fontSize: 56, color: INK, letterSpacing: '-0.02em'}}>해외 화장품 쇼츠 만들어줘</div>
          <div style={{position: 'absolute', top: 470, left: 0, right: 0, textAlign: 'center', fontFamily: 'PB', fontWeight: 800, fontSize: 80, color: GREEN}}>↓</div>
          <div style={{position: 'absolute', top: 600, left: 0, right: 0, textAlign: 'center', fontFamily: 'PS', fontWeight: 600, fontSize: 56, color: '#6a6a78'}}>완성 쇼츠</div>
          <div style={{position: 'absolute', left: 540 - 270, top: 690}}>
            <Card s={{v: cmp[idx].v, from: cmp[idx].from + (idx === 0 ? 0 : 0)}} w={540} h={960} vol={t > 10 ? 0.1 : 0} key={idx} />
          </div>
        </AbsoluteFill>
      )}

      {t >= 12.6 && (
        <AbsoluteFill style={{background: NAVY, clipPath: `circle(${wipe}px at 50% 50%)`}}>
          <div style={{position: 'absolute', left: 0, right: 0, top: 740, textAlign: 'center', fontFamily: 'PB', fontWeight: 800, fontSize: 124,
            letterSpacing: '-0.03em', color: '#fff', opacity: endP, transform: `translateY(${(1 - endP) * 50}px)`, lineHeight: 1.2}}>
            말 한 줄이면<br /><span style={{color: '#5fe3c0'}}>됩니다</span>
          </div>
          <div style={{position: 'absolute', left: 0, right: 0, top: 1130, textAlign: 'center', fontFamily: 'PS', fontWeight: 600, fontSize: 72,
            color: '#fff', opacity: endP2, transform: `translateY(${(1 - endP2) * 30}px)`}}>숏클메이커</div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};

const Root: React.FC = () => <Composition id="J1" component={Scene} durationInFrames={15 * FPS} fps={FPS} width={1080} height={1920} />;
registerRoot(Root);
