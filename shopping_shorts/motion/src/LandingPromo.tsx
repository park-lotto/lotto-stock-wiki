// 랜딩 프로모 2편 — price_compare(1280x640) · free_banner(1600x360). 확대 0회, 블러 그림자 없음.
import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {useFont, fmtViews} from './LandingHeroWall';
import {Word, parse} from './LandingTour';
import {BigCaption, CutView, SUBCLEAN_CUT, Sparkles} from './LandingFlow';
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
  // 왼쪽 카드: 오버슈트 스프링(0.6→1.08→1) + 2.5초마다 펄스(1→1.05→1) + 민트 링 확산
  const lIn = spring({frame: frame - 2, fps, config: {damping: 9, stiffness: 150, mass: 0.8}});
  const lScaleIn = interpolate(lIn, [0, 1], [0.6, 1]);
  const PULSE_T = 60;
  const pLocal = frame >= 60 ? (frame - 60) % PULSE_T : -1;
  const pulseL = pLocal >= 0 && pLocal < 16 ? 1 + 0.07 * Math.sin((pLocal / 16) * Math.PI) : 1;
  const bounceY = pLocal >= 0 && pLocal < 16 ? -14 * Math.sin((pLocal / 16) * Math.PI) : 0;
  const burst = pLocal >= 0 ? interpolate(pLocal, [0, 26], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
  const ringT = pLocal >= 0 ? interpolate(pLocal, [0, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
  const l = Math.min(1, lIn);
  const r = cardIn(8);
  // 770,000 카운트업(등장) + 펄스 때 살짝 흔들림
  const priceN = Math.round(interpolate(frame, [8, 34], [0, 770000], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const priceStr = priceN.toLocaleString('ko-KR');
  const shake = pLocal >= 0 && pLocal < 12 ? Math.sin((pLocal / 12) * Math.PI * 3) * 2.5 : 0;
  const stamp = spring({frame: frame - 34, fps, config: {damping: 9, stiffness: 220, mass: 0.8}});
  // 🔥 지금이 기회 도장: 쾅 찍힘(2.4→1) + 흔들림
  const stamp2 = spring({frame: frame - 48, fps, config: {damping: 7, stiffness: 260, mass: 0.9}});
  const stampShake = frame >= 48 && frame < 62 ? Math.sin((frame - 48) * 1.6) * (1 - (frame - 48) / 14) * 6 : 0;
  const landed = frame >= 34 && frame < 60; // 숫자 착지 파티클
  const strike = interpolate(frame, [22, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const glow = 0.5 + 0.5 * Math.sin((frame / 30) * Math.PI); // 왼쪽 카드 숨쉬는 테두리
  const pulse = 1 + 0.035 * Math.sin((frame / 9) * Math.PI);
  const fade = Math.min(
    interpolate(frame, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [D - 8, D - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  const card: React.CSSProperties = {
    position: 'absolute',
    top: 40,
    width: 560,
    height: 400,
    borderRadius: 28,
    padding: '30px 30px',
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
          left: 36,
          width: 616,
          background: 'linear-gradient(160deg, #10201c, #0b1512)',
          boxShadow: `0 0 0 3px rgba(111,240,214,${0.55 + 0.45 * glow}), 0 0 0 ${ringT * 34}px rgba(111,240,214,${0.45 * (1 - ringT)}), 0 0 ${30 + 90 * burst}px ${10 * burst}px rgba(111,240,214,${0.35 + 0.4 * burst}), 0 30px 60px rgba(0,0,0,.6)`,
          transform: `translateY(${(1 - l) * 40 + bounceY}px) scale(${lScaleIn * pulseL})`,
          transformOrigin: '50% 50%',
          opacity: l,
        }}
      >
        <div style={{display: 'inline-block', padding: '8px 18px', borderRadius: 999, background: MINT, color: '#062018', fontWeight: 900, fontSize: 26, letterSpacing: -0.5}}>1기 · 9월 30일 마감</div>
        <div style={{marginTop: 14, fontSize: 30, fontWeight: 700, color: 'rgba(255,255,255,.55)', position: 'relative', display: 'table'}}>
          정가 1,500,000원
          <div style={{position: 'absolute', left: -6, top: '46%', height: 9, width: `calc(${strike * 100}% + 12px)`, background: RED, borderRadius: 5, transform: 'rotate(-5deg)', boxShadow: '0 0 12px rgba(255,77,77,.7)'}} />
        </div>
        <div style={{position: 'relative', marginTop: 0, fontSize: 129, fontWeight: 900, color: YEL, letterSpacing: -7, lineHeight: 1.05, whiteSpace: 'nowrap', textShadow: '0 5px 0 rgba(0,0,0,.6)', fontVariantNumeric: 'tabular-nums', transform: `rotate(${shake}deg) scale(${1 + Math.abs(shake) * 0.02})`, transformOrigin: '20% 60%', display: 'inline-block'}}>
          {priceStr}<span style={{fontSize: 54, marginLeft: 6, color: '#fff'}}>원</span>
          {landed && [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((k) => {
            const a = (k / 12) * Math.PI * 2;
            const r = interpolate(frame, [34, 60], [10, 150], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            const op = interpolate(frame, [34, 60], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            return <div key={k} style={{position: 'absolute', left: 200 + Math.cos(a) * r, top: 60 + Math.sin(a) * r, width: k % 3 ? 10 : 16, height: k % 3 ? 10 : 16, borderRadius: '50%', background: k % 2 ? YEL : MINT, opacity: op, boxShadow: `0 0 14px ${k % 2 ? YEL : MINT}`}} />;
          })}
        </div>
        <div style={{marginTop: 4, fontSize: 26, fontWeight: 700, color: MINT}}>지금 신청하면 이 가격 그대로</div>
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
        {/* 🔥 지금이 기회 스탬프 */}
        <div
          style={{
            position: 'absolute',
            right: 22,
            bottom: 18,
            padding: '8px 18px',
            border: `5px solid ${RED}`,
            borderRadius: 14,
            color: RED,
            fontWeight: 900,
            fontSize: 38,
            letterSpacing: -1,
            whiteSpace: 'nowrap',
            background: 'rgba(255,77,77,.10)',
            boxShadow: 'inset 0 0 0 3px #0b1512, inset 0 0 0 5px rgba(255,77,77,.6)',
            transform: `rotate(${-8 + stampShake}deg) scale(${interpolate(stamp2, [0, 1], [2.4, 1])})`,
            opacity: Math.min(1, stamp2 * 2.5),
          }}
        >
          🔥 지금이 기회
        </div>
      </div>
      {/* 오른쪽: 2기 */}
      <div
        style={{
          ...card,
          left: 680,
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

// ── 3) ④ 렌더화면 칸 (1080x1080, 10.4s) — 사장님이 고른 완성 쇼츠 4편을 세로 크게 이어 재생 ─
// 재료 public/render/full1~4.mp4 (608x1080, 원본 1080x1920 축소, 2.7s씩, gitignore) — 원본은 바탕화면 KakaoTalk_*.mp4
//   full1=KakaoTalk_20260828_023955618(가스렌지 전동청소기 16.0s~) full2=KakaoTalk_20260824_015356161(헤어 롤빗 0.3s~)
//   full3=KakaoTalk_20260823_011355178(면도기 2.0s~) full4=KakaoTalk_20260823_015039780(이어폰 6.0s~)
export const SQ4 = {width: 1080, height: 1080, fps: 30, durationInFrames: 340};
const PRE_F = 60; // 앞 자막제거 컷(95.png BEFORE→AFTER 와이프)
const SEG_F = 93; // 완성본 3구간
const CARD_W = 608;
const CARD_H = 1080;
// 구간별 가운데(제품컷 위주: 가스렌지·면도기·이어폰) / 좌·우 카드. 빗(뷰티) 영상은 옆 카드로만.
const SEGS = [
  {center: 1, left: 2, right: 3, box: {x: 40, y: 280, w: 528, h: 96}},
  {center: 3, left: 4, right: 2, box: {x: 40, y: 360, w: 528, h: 96}},
  {center: 4, left: 1, right: 2, box: {x: 40, y: 230, w: 528, h: 96}},
];

const PhoneCard: React.FC<{clip: number; x: number; y: number; scale: number; rot: number; dim?: number; children?: React.ReactNode; style?: React.CSSProperties}> = ({clip, x, y, scale, rot, dim = 0, children, style}) => (
  <div style={{position: 'absolute', left: x, top: y, width: CARD_W, height: CARD_H, borderRadius: 34, overflow: 'hidden', transform: `perspective(1600px) rotateY(${rot}deg) scale(${scale})`, transformOrigin: '50% 50%', boxShadow: '0 40px 90px rgba(0,0,0,.7), 0 0 0 3px rgba(255,255,255,.08)', background: '#000', ...style}}>
    <OffthreadVideo src={staticFile(`render/full${clip}.mp4`)} muted style={{width: '100%', height: '100%', display: 'block'}} />
    {dim > 0 && <div style={{position: 'absolute', inset: 0, background: `rgba(4,7,10,${dim})`}} />}
    {children}
  </div>
);

export const SqRender: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const D = SQ4.durationInFrames;
  const fade = Math.min(
    interpolate(frame, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [D - 8, D - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  const preOut = interpolate(frame, [PRE_F - 8, PRE_F], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const segIdx = Math.max(0, Math.min(SEGS.length - 1, Math.floor((frame - PRE_F) / SEG_F)));
  const segLocal = frame - PRE_F - segIdx * SEG_F;
  const seg = SEGS[segIdx];
  // 등장: 가운데 카드 스프링, 옆 카드 패럴랙스 슬라이드
  const enter = spring({frame: segLocal, fps, config: {damping: 13, stiffness: 140}});
  // 흑백 → 자막 영역부터 컬러가 원형으로 살아남
  const colorR = interpolate(segLocal, [8, 40], [0, 130], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const cx = seg.box.x + seg.box.w / 2;
  const cy = seg.box.y + seg.box.h / 2;
  // 전환: 0→1 와이프, 1→2 글리치
  const wipeT = segIdx === 1 ? interpolate(segLocal, [0, 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
  const glitch = segIdx === 2 && segLocal < 8 ? 1 - segLocal / 8 : 0;
  const centerX = (1080 - CARD_W) / 2;
  const sideScale = 0.6;
  const sideY = (1080 - CARD_H) / 2;
  const par = (1 - enter) * 90;
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden', opacity: fade}}>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(60% 70% at 50% 50%, rgba(111,240,214,.10), transparent 70%)'}} />
      <Sparkles frame={frame} n={22} seed={5} />
      {frame < PRE_F && (
        <div style={{position: 'absolute', inset: 0, opacity: preOut, transform: `translateX(${(1 - preOut) * -120}px)`}}>
          <CutView cut={SUBCLEAN_CUT} local={frame} len={PRE_F} first />
        </div>
      )}
      {frame >= PRE_F && (
        <Sequence from={PRE_F + segIdx * SEG_F} durationInFrames={SEG_F} layout="none">
          {/* 옆 카드(어둡게·기울여·패럴랙스) */}
          <PhoneCard clip={seg.left} x={-120 - par} y={sideY} scale={sideScale} rot={22} dim={0.55} style={{filter: 'grayscale(.5)'}} />
          <PhoneCard clip={seg.right} x={1080 - CARD_W + 120 + par} y={sideY} scale={sideScale} rot={-22} dim={0.55} style={{filter: 'grayscale(.5)'}} />
          {/* 가운데 카드: 흑백 + 컬러 원형 리빌 */}
          <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${(1 - wipeT) * 100}% 0 0)`, transform: `translateX(${glitch * 18}px)`}}>
            <PhoneCard clip={seg.center} x={centerX} y={0} scale={interpolate(enter, [0, 1], [0.92, 1])} rot={(1 - enter) * -10} style={{filter: 'grayscale(1) brightness(.85)'}} />
            <div style={{position: 'absolute', left: centerX, top: 0, width: CARD_W, height: CARD_H, borderRadius: 34, overflow: 'hidden', clipPath: `circle(${colorR}% at ${(cx / CARD_W) * 100}% ${(cy / CARD_H) * 100}%)`, transform: `scale(${interpolate(enter, [0, 1], [0.92, 1])})`, transformOrigin: '50% 50%'}}>
              <OffthreadVideo src={staticFile(`render/full${seg.center}.mp4`)} muted style={{width: '100%', height: '100%', display: 'block'}} />
            </div>
            {/* 글리치 슬라이스 */}
            {glitch > 0 && [0, 1, 2, 3].map((k) => (
              <div key={k} style={{position: 'absolute', left: centerX + (k % 2 ? 1 : -1) * glitch * 26, top: 200 + k * 220, width: CARD_W, height: 60, overflow: 'hidden', opacity: 0.8}}>
                <div style={{position: 'absolute', left: 0, top: -(200 + k * 220), width: CARD_W, height: CARD_H, background: k % 2 ? 'rgba(255,77,77,.25)' : 'rgba(111,240,214,.25)'}} />
              </div>
            ))}
          </div>
          {segIdx === 1 && wipeT < 1 && <div style={{position: 'absolute', top: 0, bottom: 0, left: `calc(${wipeT * 100}% - 4px)`, width: 8, background: MINT, boxShadow: '0 0 30px 8px rgba(111,240,214,.8)'}} />}
        </Sequence>
      )}
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(7,11,15,.55) 0%, rgba(7,11,15,.12) 40%, rgba(7,11,15,0) 60%)', pointerEvents: 'none'}} />
      <BigCaption text="자막도 AI가 [싹] 지움" from={4} to={PRE_F - 2} size={76} />
      <BigCaption text="버튼 한 번에" from={PRE_F + 2} to={PRE_F + 96} />
      <BigCaption text={'자막·음성 입힌' + String.fromCharCode(10) + '<완성 쇼츠>'} from={PRE_F + 100} to={D - 2} />
    </AbsoluteFill>
  );
};

// ── 4) 첫 화면 후킹 hook_wall (1600x800, 12s) — 100만뷰 썸네일 3줄 벽 + 중앙 키네틱 자막 ─
export const HOOK = {width: 1600, height: 800, fps: 30, durationInFrames: 360};
const HK_ROWS = [
  [0, 1, 2, 6, 8],
  [11, 12, 14, 16, 0],
  [1, 6, 8, 11, 14],
]; // 뷰티 얼굴 클로즈업(3·4·5·7·9·10·13·15·17) 제외
const HK_H = 262; // 3줄 + 간격
const HK_W = Math.round((HK_H * 9) / 16); // 147 → 원본 1080 축소
const HK_GAP = 14;
// HTML 제목('오늘 뭘 만들지 고민 끝.')·부제와 겹치지 않는 문구로
const HK_LINES = ['어제도 [100만뷰] 터졌습니다', '터진 쇼츠는\n{매일 아침} 랭킹에 올라오고', '그 구조 그대로\n<내 제품>만 끼우면 끝'];
const HK_LINE_F = 120;

export const HookWall: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const D = HOOK.durationInFrames;
  const items = hero.items as {file: string; views: number}[];
  const line = Math.floor(frame / HK_LINE_F) % HK_LINES.length;
  const local = frame - line * HK_LINE_F;
  const out = interpolate(local, [HK_LINE_F - 10, HK_LINE_F - 2], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const rows = HK_LINES[line].split('\n');
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      {HK_ROWS.map((row, r) => {
        const cycle = row.length * (HK_W + HK_GAP);
        const dir = r === 1 ? -1 : 1;
        const off = (frame / D) * cycle * dir + r * 190; // 1주기/루프
        const y = 8 + r * (HK_H + HK_GAP - 8);
        return row.map((idx, i) =>
          [0, 1, 2].map((k) => {
            const x = ((i * (HK_W + HK_GAP) - off) % cycle + cycle) % cycle + (k - 1) * cycle;
            if (x + HK_W < 0 || x > 1600) return null;
            const it = items[idx];
            return (
              <div key={`${r}-${i}-${k}`} style={{position: 'absolute', left: x, top: y, width: HK_W, height: HK_H, borderRadius: 18, overflow: 'hidden', background: '#111'}}>
                <Img src={staticFile(it.file)} style={{width: '100%', height: '100%', objectFit: 'cover', display: 'block'}} />
                <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 90, background: 'linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,.8))'}} />
                <div style={{position: 'absolute', left: 8, bottom: 8, display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px 6px 8px', borderRadius: 999, background: 'rgba(0,0,0,.65)', color: '#fff', fontFamily: FONT, fontWeight: 900, fontSize: 26, lineHeight: 1.1, letterSpacing: -0.5}}>
                  <svg width="20" height="20" viewBox="0 0 24 24"><path d="M6 3.5v17l14-8.5z" fill="#fff" /></svg>
                  <span>{fmtViews(it.views)}</span>
                </div>
              </div>
            );
          }),
        );
      })}
      {/* 중앙 어두운 판 */}
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(70% 70% at 50% 50%, rgba(7,11,15,.9) 0%, rgba(7,11,15,.75) 42%, rgba(7,11,15,.22) 100%)'}} />
      <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, opacity: out, fontFamily: FONT, fontWeight: 900}}>
        {rows.map((row, ri) => {
          const offset = ri === 0 ? 0 : parse(rows[0]).length;
          return (
            <div key={`${line}-${ri}`} style={{display: 'flex', alignItems: 'center', fontSize: rows.length > 1 ? 80 : 92, lineHeight: 1.25, letterSpacing: -2}}>
              {parse(row).map((tok, i) => (
                <Word key={`${line}-${ri}-${i}`} tok={tok} idx={offset + i} local={local} size={rows.length > 1 ? 80 : 92} />
              ))}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ── 5) trend.mp4 (1600x700, 9s) — "쇼핑쇼츠가 대세" 키네틱 + 상승선 + 카운트업 ─
export const TREND = {width: 1600, height: 700, fps: 30, durationInFrames: 270};
const TR_LINES = ['지금 [쇼핑쇼츠]가 대세', '{100만뷰} 쇼츠가 매일 랭킹에', '지금 시작한 사람이 <가져갑니다>'];
const TR_ROW = [0, 1, 2, 6, 8, 11, 12, 14, 16];
export const TrendBanner: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const D = TREND.durationInFrames;
  const items = hero.items as {file: string; views: number}[];
  const seg = 90;
  const line = Math.min(2, Math.floor(frame / seg));
  const local = frame - line * seg;
  const out = interpolate(local, [seg - 10, seg - 2], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  // 배경 썸네일 띠(높이 230, 하단) — 1주기/루프
  const tw = 129;
  const th = 230;
  const gap = 12;
  const cycle = TR_ROW.length * (tw + gap);
  const off = (frame / D) * cycle;
  // 상승선
  const pts = [0, 0.12, 0.1, 0.25, 0.22, 0.4, 0.38, 0.6, 0.55, 0.8, 0.78, 1].map((v, i, arr) => [80 + (i / (arr.length - 1)) * 1440, 560 - v * 420]);
  const drawn = interpolate(frame, [0, 120], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const pathLen = 2200;
  const count = Math.round(interpolate(local, [6, 40], [0, 1000000], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      {TR_ROW.map((idx, i) =>
        [0, 1].map((k) => {
          const x = ((i * (tw + gap) - off) % cycle + cycle) % cycle + (k - 1) * cycle + 400;
          if (x + tw < 0 || x > 1600) return null;
          return <Img key={`${i}-${k}`} src={staticFile(items[idx].file)} style={{position: 'absolute', left: x, top: 700 - th + 20, width: tw, height: th, objectFit: 'cover', borderRadius: 14, opacity: 0.35}} />;
        }),
      )}
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(7,11,15,.2) 0%, rgba(7,11,15,.75) 55%, rgba(7,11,15,.95) 100%)'}} />
      <svg width={1600} height={700} style={{position: 'absolute', left: 0, top: 0}}>
        <defs>
          <linearGradient id="tg" x1="0" x2="1"><stop offset="0" stopColor={MINT} stopOpacity="0.15" /><stop offset="1" stopColor={MINT} stopOpacity="0.9" /></linearGradient>
        </defs>
        <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" stroke="url(#tg)" strokeWidth={10} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={pathLen} strokeDashoffset={pathLen * (1 - drawn)} />
        {drawn >= 1 && <circle cx={pts[11][0]} cy={pts[11][1]} r={14 + 6 * Math.abs(Math.sin(frame / 8))} fill={MINT} opacity={0.9} />}
      </svg>
      <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 22, opacity: out, fontFamily: FONT, fontWeight: 900}}>
        {line === 1 && (
          <div style={{padding: '10px 34px', borderRadius: 999, background: MINT, color: '#062018', fontSize: 54, letterSpacing: -1, fontVariantNumeric: 'tabular-nums', opacity: interpolate(local, [4, 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
            조회수 {count.toLocaleString('ko-KR')}+
          </div>
        )}
        <div style={{display: 'flex', alignItems: 'center', fontSize: 96, lineHeight: 1.2, letterSpacing: -2.5}}>
          {parse(TR_LINES[line]).map((tok, i) => (
            <Word key={`${line}-${i}`} tok={tok} idx={i} local={local} size={96} />
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── 6) easy60.mp4 (1600x500, 8s) — "60대도 만듭니다" + 제작소 단계바가 체크되며 흘러가 "완성본" ─
// 단계 이름은 제작소 produce.html STEP_LABELS 그대로(개수·숫자 언급 없음)
export const EASY = {width: 1600, height: 500, fps: 30, durationInFrames: 240};
const STEP_LABELS = ['영상추출/분석', '대본생성', '영상대본MIX', 'TTS음성', '고품질 자막제거', '장면꾸미기', '썸네일', '제목·태그', '완성본', 'SNS 예약'];
const FINAL_IDX = 8;
const PILL_GAP = 26;
const PILL_W = 236;
const ST0 = 24; // 첫 체크 프레임
const ST_GAP = 19; // 체크 간격
export const Easy60: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const D = EASY.durationInFrames;
  const fade = Math.min(
    interpolate(frame, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [D - 8, D - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  const at = (i: number) => ST0 + i * ST_GAP;
  // 현재 체크된 단계가 화면 x=1000 근처에 오도록 띠가 왼쪽으로 흐른다(부드럽게)
  const cur = Math.max(0, Math.min(FINAL_IDX, Math.floor((frame - ST0) / ST_GAP)));
  const target = 980 - cur * (PILL_W + PILL_GAP);
  const prevTarget = 980 - Math.max(0, cur - 1) * (PILL_W + PILL_GAP);
  const t = frame >= ST0 ? interpolate(frame - at(cur), [0, 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
  const ease = t * t * (3 - 2 * t);
  const offset = frame < ST0 ? 980 + 60 : prevTarget + (target - prevTarget) * ease;
  const finalDone = frame >= at(FINAL_IDX);
  const finalPop = spring({frame: frame - at(FINAL_IDX), fps, config: {damping: 10, stiffness: 200}});
  const nextPress = spring({frame: (frame - ST0) % ST_GAP, fps, config: {damping: 8, stiffness: 300}});
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden', opacity: fade}}>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(60% 80% at 30% 40%, rgba(111,240,214,.10), transparent 70%)'}} />
      {/* 문구 */}
      <div style={{position: 'absolute', left: 64, top: 54, display: 'flex', flexDirection: 'column', gap: 12, fontFamily: FONT}}>
        <div style={{display: 'flex', alignItems: 'center', fontWeight: 900, fontSize: 66, lineHeight: 1.2, letterSpacing: -2}}>
          {parse('단계만 따라가면 {60대도} 만듭니다').map((tok, i) => (
            <Word key={i} tok={tok} idx={i} local={frame - 4} size={66} />
          ))}
        </div>
        <div style={{display: 'flex', alignItems: 'center', fontWeight: 900, fontSize: 38, lineHeight: 1.25, letterSpacing: -1, marginLeft: 6}}>
          {parse('편집 몰라도 · [다음]만 누르면 완성본').map((tok, i) => (
            <Word key={i} tok={tok} idx={i + 4} local={frame - 4} size={38} />
          ))}
        </div>
      </div>
      {/* 다음 버튼 */}
      <div style={{position: 'absolute', right: 70, top: 92, padding: '16px 34px', borderRadius: 999, background: MINT, color: '#062018', fontFamily: FONT, fontWeight: 900, fontSize: 34, letterSpacing: -1, boxShadow: '0 12px 30px rgba(111,240,214,.3)', transform: `scale(${frame >= ST0 && !finalDone ? 1 - 0.1 * Math.sin(Math.min(1, ((frame - ST0) % ST_GAP) / 8) * Math.PI) : 1})`, opacity: nextPress > -1 ? 1 : 1}}>
        다음 →
      </div>
      {/* 단계 띠 */}
      <div style={{position: 'absolute', left: 0, right: 0, top: 300, height: 130}}>
        <div style={{position: 'absolute', left: 0, top: 44, width: 1600, height: 6, background: 'rgba(255,255,255,.08)', borderRadius: 3}} />
        {STEP_LABELS.map((label, i) => {
          const x = offset + i * (PILL_W + PILL_GAP);
          if (x + PILL_W < -50 || x > 1700) return null;
          const done = frame >= at(i);
          const pop = spring({frame: frame - at(i), fps, config: {damping: 11, stiffness: 220}});
          const isFinal = i === FINAL_IDX;
          const sc = done ? 1 + 0.08 * Math.sin(Math.min(1, pop) * Math.PI) + (isFinal ? 0.18 * finalPop : 0) : 1;
          return (
            <div
              key={label}
              style={{
                position: 'absolute',
                left: x,
                top: 10,
                width: PILL_W,
                height: 74,
                borderRadius: 999,
                background: done ? (isFinal ? YEL : MINT) : '#151c24',
                boxShadow: done ? (isFinal ? '0 0 0 6px rgba(255,216,77,.25), 0 16px 40px rgba(255,216,77,.35)' : '0 10px 26px rgba(111,240,214,.25)') : '0 0 0 2px rgba(255,255,255,.12)',
                color: done ? '#062018' : 'rgba(255,255,255,.55)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                fontFamily: FONT,
                fontWeight: 900,
                fontSize: isFinal && done ? 32 : 26,
                letterSpacing: -0.5,
                whiteSpace: 'nowrap',
                transform: `scale(${sc})`,
              }}
            >
              {done && <span style={{fontSize: 26}}>✓</span>}
              <span>{label}</span>
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: 64, bottom: 28, fontFamily: FONT, fontWeight: 700, fontSize: 24, color: 'rgba(255,255,255,.6)', opacity: finalDone ? 1 : 0}}>
        완성본 나옴 — 바로 올리면 끝
      </div>
    </AbsoluteFill>
  );
};
