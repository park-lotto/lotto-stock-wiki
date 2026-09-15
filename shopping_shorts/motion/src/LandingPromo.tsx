// 랜딩 프로모 2편 — price_compare(1280x640) · free_banner(1600x360). 확대 0회, 블러 그림자 없음.
import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {useFont} from './LandingHeroWall';
import {Word, parse} from './LandingTour';
import hero from './hero_data.json';

const FONT = 'HeroKR';
const YEL = '#FFD84D';
const RED = '#FF4D4D';
const MINT = '#6FF0D6';
const BG = '#070b0f';
const SHADOW = '0 3px 0 rgba(0,0,0,.6)';

const Kinetic: React.FC<{text: string; from: number; to: number; size: number}> = ({text, from, to, size}) => {
  const frame = useCurrentFrame();
  if (frame < from || frame > to) return null;
  const out = interpolate(frame, [to - 8, to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', alignItems: 'center', fontFamily: FONT, fontWeight: 900, fontSize: size, lineHeight: 1.25, letterSpacing: -1.5, opacity: out}}>
      {parse(text).map((tok, i) => (
        <Word key={i} tok={tok} idx={i} local={frame - from} size={size} />
      ))}
    </div>
  );
};

// ── 1) 가격 비교 (1280x640, 9s) ─────────────────────
export const PRICE = {width: 1280, height: 640, fps: 30, durationInFrames: 270};
const Lock: React.FC<{size: number}> = ({size}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#8a93a0" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
    <rect x="4" y="10.5" width="16" height="10" rx="2.5" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
  </svg>
);

export const PriceCompare: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const D = PRICE.durationInFrames;
  const cardIn = (d: number) => spring({frame: frame - d, fps, config: {damping: 14, stiffness: 120}});
  const l = cardIn(2);
  const r = cardIn(8);
  const stamp = spring({frame: frame - 34, fps, config: {damping: 9, stiffness: 220, mass: 0.8}});
  const strike = interpolate(frame, [22, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const glow = 0.5 + 0.5 * Math.sin((frame / 30) * Math.PI); // 왼쪽 카드 숨쉬는 테두리
  const pulse = 1 + 0.035 * Math.sin((frame / 9) * Math.PI);
  const fade = Math.min(
    interpolate(frame, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [D - 8, D - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  const card: React.CSSProperties = {
    position: 'absolute',
    top: 44,
    width: 560,
    height: 360,
    borderRadius: 28,
    padding: '34px 40px',
    boxSizing: 'border-box',
    fontFamily: FONT,
  };
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden', opacity: fade}}>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(60% 80% at 25% 40%, rgba(111,240,214,.10), transparent 70%)'}} />
      {/* 왼쪽: 1기 */}
      <div
        style={{
          ...card,
          left: 60,
          background: 'linear-gradient(160deg, #10201c, #0b1512)',
          boxShadow: `0 0 0 3px rgba(111,240,214,${0.55 + 0.45 * glow}), 0 0 ${30 + 30 * glow}px rgba(111,240,214,.35), 0 30px 60px rgba(0,0,0,.6)`,
          transform: `translateY(${(1 - l) * 40}px)`,
          opacity: l,
        }}
      >
        <div style={{display: 'inline-block', padding: '8px 18px', borderRadius: 999, background: MINT, color: '#062018', fontWeight: 900, fontSize: 26, letterSpacing: -0.5}}>1기 · 9월 30일 마감</div>
        <div style={{marginTop: 28, fontSize: 30, fontWeight: 700, color: 'rgba(255,255,255,.55)', position: 'relative', display: 'inline-block'}}>
          정가 1,500,000원
          <div style={{position: 'absolute', left: -4, top: '52%', height: 5, width: `calc(${strike * 100}% + 8px)`, background: RED, borderRadius: 3, transform: 'rotate(-4deg)'}} />
        </div>
        <div style={{marginTop: 6, fontSize: 92, fontWeight: 900, color: '#fff', letterSpacing: -3, lineHeight: 1.1, textShadow: SHADOW}}>
          770,000<span style={{fontSize: 44, marginLeft: 6}}>원</span>
        </div>
        <div style={{marginTop: 10, fontSize: 26, fontWeight: 700, color: MINT}}>지금 신청하면 이 가격 그대로</div>
        {/* 49% 할인 도장 */}
        <div
          style={{
            position: 'absolute',
            right: 30,
            top: 22,
            width: 140,
            height: 140,
            borderRadius: '50%',
            border: `6px solid ${RED}`,
            boxShadow: `inset 0 0 0 4px #0b1512, inset 0 0 0 7px ${RED}`,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: RED,
            fontWeight: 900,
            transform: `rotate(-14deg) scale(${interpolate(stamp, [0, 1], [2.2, 1])})`,
            opacity: Math.min(1, stamp * 2),
            background: 'rgba(255,77,77,.08)',
          }}
        >
          <div style={{fontSize: 50, lineHeight: 1, letterSpacing: -2}}>49%</div>
          <div style={{fontSize: 28, lineHeight: 1.1}}>할인</div>
        </div>
      </div>
      {/* 오른쪽: 2기 */}
      <div
        style={{
          ...card,
          left: 660,
          background: 'linear-gradient(160deg, #161a20, #0f1216)',
          boxShadow: '0 0 0 2px rgba(255,255,255,.08), 0 30px 60px rgba(0,0,0,.5)',
          transform: `translateY(${(1 - r) * 40}px)`,
          opacity: r * 0.92,
        }}
      >
        <div style={{display: 'inline-block', padding: '8px 18px', borderRadius: 999, background: '#2a3038', color: '#aab2bd', fontWeight: 900, fontSize: 26, letterSpacing: -0.5}}>2기 · 10월 1일부터</div>
        <div style={{marginTop: 28, fontSize: 30, fontWeight: 700, color: 'rgba(255,255,255,.28)'}}>업데이트 반영 가격</div>
        <div style={{marginTop: 6, fontSize: 92, fontWeight: 900, color: '#6f7884', letterSpacing: -3, lineHeight: 1.1}}>
          880,000<span style={{fontSize: 44, marginLeft: 6}}>원</span>
        </div>
        <div style={{marginTop: 10, display: 'flex', alignItems: 'center', gap: 10, fontSize: 26, fontWeight: 700, color: '#8a93a0'}}>
          <Lock size={30} /> 2기 오픈 전까지 잠김
        </div>
      </div>
      {/* 하단 자막 */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 210, background: 'linear-gradient(0deg, rgba(4,7,10,.92) 0%, rgba(4,7,10,.75) 60%, rgba(4,7,10,0) 100%)'}} />
      <div style={{position: 'absolute', left: 40, right: 40, bottom: 44, display: 'flex', justifyContent: 'center'}}>
        <Kinetic text="1기 동안 프로그램 [대규모 업데이트] → 2기부터 {가격 인상}" from={56} to={168} size={46} />
        <div style={{transform: `scale(${frame >= 172 ? pulse : 1})`}}>
          <Kinetic text="<9월까지만> 이 가격" from={172} to={D - 2} size={64} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── 2) 무료 체험 배너 (1600x360, 8s) ────────────────
export const BANNER = {width: 1600, height: 360, fps: 30, durationInFrames: 240};
const THUMBS = (hero.items as {file: string}[]).slice(0, 9);
const TH = 360;
const TW = Math.round((TH * 9) / 16); // 203 — 원본 1080x1920 축소
const TGAP = 12;

export const FreeBanner: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const D = BANNER.durationInFrames;
  const cycle = THUMBS.length * (TW + TGAP);
  const off = (frame / D) * cycle; // 1주기/루프 → 이음매 없음
  const sweep = interpolate(frame % 120, [30, 75], [-0.5, 1.5], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const btnPulse = 1 + 0.02 * Math.sin((frame / 20) * Math.PI);
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      {THUMBS.map((t, i) =>
        [0, 1].map((k) => {
          const x = ((i * (TW + TGAP) - off) % cycle + cycle) % cycle + k * cycle - cycle + 0;
          if (x + TW < 0 || x > 1600) return null;
          return <Img key={`${i}-${k}`} src={staticFile(t.file)} style={{position: 'absolute', left: x, top: 0, width: TW, height: TH, objectFit: 'cover', opacity: 0.55}} />;
        }),
      )}
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(7,11,15,.97) 0%, rgba(7,11,15,.92) 48%, rgba(7,11,15,.55) 75%, rgba(7,11,15,.85) 100%)'}} />
      {/* 왼쪽 문구 */}
      <div style={{position: 'absolute', left: 64, top: 0, bottom: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14, fontFamily: FONT}}>
        <div style={{display: 'flex', alignItems: 'center', fontWeight: 900, fontSize: 64, letterSpacing: -2, lineHeight: 1.2}}>
          {parse('[무료로] 레퍼런스 랭킹 체험하기').map((tok, i) => (
            <Word key={i} tok={tok} idx={i} local={frame - 6} size={64} />
          ))}
        </div>
        <div style={{display: 'flex', gap: 14, alignItems: 'center', fontSize: 28, fontWeight: 700, color: 'rgba(255,255,255,.85)', textShadow: SHADOW, opacity: interpolate(frame, [40, 52], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), marginLeft: 8}}>
          {['설치 없음', '브라우저로 바로', '매일 100만뷰 쇼츠'].map((s, i) => (
            <React.Fragment key={s}>
              {i > 0 && <span style={{color: MINT}}>·</span>}
              <span>{s}</span>
            </React.Fragment>
          ))}
        </div>
      </div>
      {/* 오른쪽 버튼 */}
      <div
        style={{
          position: 'absolute',
          right: 64,
          top: 0,
          bottom: 0,
          display: 'flex',
          alignItems: 'center',
          transform: `scale(${btnPulse})`,
        }}
      >
        <div
          style={{
            position: 'relative',
            overflow: 'hidden',
            padding: '24px 44px',
            borderRadius: 999,
            background: MINT,
            color: '#062018',
            fontFamily: FONT,
            fontWeight: 900,
            fontSize: 38,
            letterSpacing: -1,
            boxShadow: '0 0 0 4px rgba(111,240,214,.25), 0 16px 40px rgba(111,240,214,.35), 0 20px 50px rgba(0,0,0,.6)',
            whiteSpace: 'nowrap',
          }}
        >
          <span style={{position: 'relative', zIndex: 1}}>지금 무료로 보기 →</span>
          <div style={{position: 'absolute', top: 0, bottom: 0, left: `${sweep * 100}%`, width: 120, background: 'linear-gradient(100deg, rgba(255,255,255,0), rgba(255,255,255,.75), rgba(255,255,255,0))', transform: 'skewX(-18deg)'}} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
