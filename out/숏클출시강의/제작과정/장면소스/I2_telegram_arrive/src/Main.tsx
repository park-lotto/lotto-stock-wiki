import React from 'react';
import {AbsoluteFill, Easing, OffthreadVideo, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

const FPS = 30;
const s = (t: number) => Math.round(t * FPS);
const eo = Easing.out(Easing.cubic);
const eo5 = Easing.out(Easing.poly(5));
const ip = (f: number, a: number, b: number, from: number, to: number, e: (n: number) => number = eo) =>
  interpolate(f, [s(a), s(b)], [from, to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: e});

const SW = 550, SH = 990; // screen
const PW = 580, PH = 1020; // phone
const INK = '#2A2118';
const font = "'PretendardX', sans-serif";

const css = `
@font-face{font-family:'PretendardX';font-weight:600;src:url('${staticFile('fonts/Pretendard-SemiBold.otf')}');}
@font-face{font-family:'PretendardX';font-weight:800;src:url('${staticFile('fonts/Pretendard-ExtraBold.otf')}');}
`;

const tiles = [0, 1, 2].map((i) => ({x: 40 + i * 165, y: 335, w: 150, h: 270}));
const posters = ['t1.jpg', 't2.jpg', 't3.jpg'];
const durs = ['0:27', '0:24', '0:29'];

const PlayBadge = ({size = 56}: {size?: number}) => (
  <div style={{width: size, height: size, borderRadius: size, background: 'rgba(0,0,0,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
    <div style={{width: 0, height: 0, borderTop: `${size * 0.2}px solid transparent`, borderBottom: `${size * 0.2}px solid transparent`, borderLeft: `${size * 0.32}px solid #fff`, marginLeft: size * 0.08}} />
  </div>
);

const BotIcon = ({size}: {size: number}) => (
  <div style={{width: size, height: size, borderRadius: size * 0.26, background: 'linear-gradient(135deg,#3FB8A0,#1F7A8C)', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
    <div style={{width: 0, height: 0, borderTop: `${size * 0.2}px solid transparent`, borderBottom: `${size * 0.2}px solid transparent`, borderLeft: `${size * 0.32}px solid #fff`, marginLeft: size * 0.06}} />
  </div>
);

const Lock: React.FC<{f: number}> = ({f}) => {
  const bannerY = ip(f, 1.0, 1.6, -220, 205);
  const press = ip(f, 2.7, 2.8, 1, 0.965);
  const lockX = ip(f, 2.85, 3.4, 0, -140);
  const lockO = ip(f, 2.85, 3.3, 1, 0);
  return (
    <div style={{position: 'absolute', inset: 0, transform: `translateX(${lockX}px)`, opacity: lockO, background: 'linear-gradient(170deg,#1D3B4A 0%,#2C5F5B 55%,#C79A5B 120%)'}}>
      <div style={{position: 'absolute', top: 70, width: '100%', textAlign: 'center', color: 'rgba(255,255,255,.85)', fontSize: 36, fontWeight: 600}}>10월 29일 목요일</div>
      <div style={{position: 'absolute', top: 108, width: '100%', textAlign: 'center', color: '#fff', fontSize: 150, fontWeight: 800, letterSpacing: -4, lineHeight: 1.1}}>6:42</div>
      <div style={{position: 'absolute', left: 20, width: SW - 40, top: bannerY, transform: `scale(${press})`, borderRadius: 30, background: 'rgba(250,248,244,.95)', padding: '20px 22px', boxShadow: '0 14px 40px rgba(0,0,0,.35)', display: 'flex', gap: 18, alignItems: 'center', boxSizing: 'border-box'}}>
        <BotIcon size={72} />
        <div style={{flex: 1}}>
          <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 32, fontWeight: 600, color: '#6b6258'}}><span>숏클 봇</span><span>지금</span></div>
          <div style={{fontSize: 34, fontWeight: 800, color: INK, marginTop: 4, whiteSpace: 'nowrap'}}>완성본 3편이 도착했습니다</div>
        </div>
      </div>
      <div style={{position: 'absolute', bottom: 30, left: SW / 2 - 70, width: 140, height: 8, borderRadius: 8, background: 'rgba(255,255,255,.6)'}} />
    </div>
  );
};

const Chat: React.FC<{f: number}> = ({f}) => {
  const x = ip(f, 2.85, 3.4, SW, 0);
  const msgY = ip(f, 3.3, 3.8, 40, 0);
  const msgO = ip(f, 3.3, 3.7, 0, 1);
  return (
    <div style={{position: 'absolute', inset: 0, transform: `translateX(${x}px)`, background: '#DDE7EA'}}>
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 170, background: '#F7F5F0', borderBottom: '1px solid #d8d2c6', boxSizing: 'border-box'}}>
        <div style={{position: 'absolute', top: 76, left: 24, display: 'flex', alignItems: 'center', gap: 16}}>
          <div style={{fontSize: 44, color: '#1F7A8C', fontWeight: 600, lineHeight: 1}}>‹</div>
          <BotIcon size={64} />
          <div><div style={{fontSize: 36, fontWeight: 800, color: INK}}>숏클 봇</div><div style={{fontSize: 28, fontWeight: 600, color: '#8a8174'}}>봇</div></div>
        </div>
      </div>
      <div style={{position: 'absolute', left: 25, top: 205, width: 500, height: 430, opacity: msgO, transform: `translateY(${msgY}px)`, background: '#fff', borderRadius: 26, borderTopLeftRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,.08)'}}>
        <div style={{position: 'absolute', left: 18, top: 16, fontSize: 34, fontWeight: 800, color: INK, whiteSpace: 'nowrap'}}>완성본 3편이 도착했습니다</div>
        <div style={{position: 'absolute', right: 16, bottom: 6, fontSize: 28, fontWeight: 600, color: '#9a9184'}}>오전 6:42</div>
      </div>
      {tiles.map((t, i) => {
        const a = 3.5 + i * 0.15;
        const sc = ip(f, a, a + 0.45, 0.6, 1);
        const o = ip(f, a, a + 0.3, 0, 1);
        const hide = i === 0 && f >= s(5.5) ? 0 : 1;
        return (
          <div key={i} style={{position: 'absolute', left: t.x, top: t.y, width: t.w, height: t.h, opacity: o * hide, transform: `scale(${sc})`, borderRadius: 16, overflow: 'hidden', background: '#000'}}>
            <Img src={staticFile(posters[i])} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}><PlayBadge /></div>
            <div style={{position: 'absolute', left: 8, top: 8, background: 'rgba(0,0,0,.55)', color: '#fff', fontSize: 28, fontWeight: 600, padding: '0 10px', borderRadius: 10}}>{durs[i]}</div>
          </div>
        );
      })}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 130, background: '#F7F5F0', borderTop: '1px solid #d8d2c6'}}>
        <div style={{position: 'absolute', left: 24, right: 24, top: 22, height: 70, borderRadius: 35, background: '#fff', border: '1px solid #ddd5c6', color: '#a39a8c', fontSize: 32, fontWeight: 600, padding: '0 28px', lineHeight: '70px', boxSizing: 'border-box'}}>메시지</div>
      </div>
    </div>
  );
};

const Player: React.FC<{f: number}> = ({f}) => {
  if (f < s(5.5)) return null;
  const p = ip(f, 5.5, 6.25, 0, 1);
  const t = tiles[0];
  const L = interpolate(p, [0, 1], [t.x, 0]), T = interpolate(p, [0, 1], [t.y, 0]);
  const W = interpolate(p, [0, 1], [t.w, SW]), H = interpolate(p, [0, 1], [t.h, SH]);
  const R = interpolate(p, [0, 1], [16, 0]);
  return (
    <div style={{position: 'absolute', left: L, top: T, width: W, height: H, borderRadius: R, overflow: 'hidden', background: '#000'}}>
      <OffthreadVideo src={staticFile('shorts.mp4')} volume={0.1} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
    </div>
  );
};

const Cursor: React.FC<{f: number}> = ({f}) => {
  let x = 420, y = 760, o = 0, tap = 0;
  if (f < s(3.4)) {
    x = ip(f, 2.0, 2.65, 440, 290); y = ip(f, 2.0, 2.65, 780, 255);
    o = ip(f, 2.0, 2.25, 0, 1) * ip(f, 3.0, 3.3, 1, 0);
    tap = ip(f, 2.7, 3.0, 0, 1);
  } else {
    x = ip(f, 4.6, 5.3, 470, 115); y = ip(f, 4.6, 5.3, 800, 470);
    o = ip(f, 4.6, 4.85, 0, 1) * ip(f, 5.9, 6.2, 1, 0);
    tap = ip(f, 5.35, 5.9, 0, 1);
  }
  const press = tap > 0 && tap < 0.25 ? 0.85 : 1;
  return (
    <div style={{position: 'absolute', left: x - 36, top: y - 36, width: 72, height: 72, opacity: o, pointerEvents: 'none'}}>
      {tap > 0 && <div style={{position: 'absolute', inset: 0, borderRadius: 72, border: '5px solid rgba(255,255,255,.9)', transform: `scale(${1 + tap * 1.6})`, opacity: 1 - tap}} />}
      <div style={{position: 'absolute', inset: 8, borderRadius: 72, background: 'rgba(60,60,60,.45)', border: '4px solid rgba(255,255,255,.95)', transform: `scale(${press})`, boxShadow: '0 4px 14px rgba(0,0,0,.35)'}} />
    </div>
  );
};

export const Main: React.FC = () => {
  const f = useCurrentFrame();
  const phoneIn = ip(f, 0, 0.7, 1, 0, eo5);
  const cx = ip(f, 7.2, 8.15, 960, 560, Easing.inOut(Easing.cubic));
  let zoom = 1, oy = 330;
  if (f < s(4.0)) {
    zoom = ip(f, 1.0, 1.9, 1, 1.26) - ip(f, 2.75, 3.5, 0, 0.26, Easing.inOut(Easing.cubic));
  } else {
    zoom = ip(f, 4.0, 4.8, 1, 1.2) - ip(f, 5.3, 6.3, 0, 0.2, Easing.inOut(Easing.cubic));
    oy = 520;
  }
  const textO = (k: number) => ip(f, 7.7 + k * 0.22, 8.3 + k * 0.22, 0, 1);
  const textY = (k: number) => ip(f, 7.7 + k * 0.22, 8.4 + k * 0.22, 50, 0);
  return (
    <AbsoluteFill style={{background: '#F6EEDC', fontFamily: font, overflow: 'hidden'}}>
      <style>{css}</style>
      <div style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, transformOrigin: `${cx}px ${oy}px`, transform: `scale(${zoom})`}}>
        <div style={{position: 'absolute', left: cx - PW / 2, top: 30 + phoneIn * 140, opacity: 1 - phoneIn, width: PW, height: PH, borderRadius: 78, background: '#17171A', boxShadow: '0 40px 90px rgba(60,40,10,.35), inset 0 0 0 4px #3a3a40'}}>
          <div style={{position: 'absolute', left: 15, top: 15, width: SW, height: SH, borderRadius: 64, overflow: 'hidden', background: '#000'}}>
            <Lock f={f} />
            <Chat f={f} />
            <Player f={f} />
            <Cursor f={f} />
            <div style={{position: 'absolute', top: 14, left: SW / 2 - 70, width: 140, height: 36, borderRadius: 20, background: '#000'}} />
          </div>
        </div>
      </div>
      <div style={{position: 'absolute', left: 1010, top: 0, height: 1080, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6}}>
        {['자는 동안', '도착했습니다'].map((w, k) => (
          <div key={k} style={{fontSize: 130, fontWeight: 800, color: k === 1 ? '#1F7A8C' : INK, lineHeight: 1.12, letterSpacing: -3, opacity: textO(k), transform: `translateY(${textY(k)}px)`, whiteSpace: 'nowrap'}}>{w}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
