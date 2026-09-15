// 랜딩 프로모 2편 — price_compare(1280x640) · free_banner(1600x360). 확대 0회, 블러 그림자 없음.
import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {useFont, fmtViews} from './LandingHeroWall';
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

// ── 3) ④ 렌더화면 칸 (1080x1080, 10s) — 완성 쇼츠 4편이 폰 프레임 안에서 이어 재생 ─
// 재료 public/render/clip1~4.mp4 (400x712, 서버 mix_jobs final.mp4에서 2.5s씩 축소 컷, gitignore)
//   clip1=e0fb23f90286(CHUZHAO 카메라) clip2=4d9f89b50ba1(쿼티폰) clip3=1c8130dc5cfc(옷감 얼룩) clip4=f0bf15850de4(벽패널)
// 컴포지션 프레임 startFrom 부터 클립 0초가 재생되게
const OffthreadVideoAt: React.FC<{src: string; startFrom: number}> = ({src, startFrom}) => (
  <Sequence from={startFrom} layout="none">
    <OffthreadVideo src={src} muted style={{width: '100%', height: '100%', display: 'block'}} />
  </Sequence>
);

export const SQ4 = {width: 1080, height: 1080, fps: 30, durationInFrames: 300};
const CLIP_F = 75; // 2.5s
const PH_W = 400;
const PH_H = 712;
const PH_X = 310;
const PH_Y = 96;

export const SqRender: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const D = SQ4.durationInFrames;
  const idx = Math.min(3, Math.floor(frame / CLIP_F));
  const local = frame - idx * CLIP_F;
  const slide = spring({frame: local, fps, config: {damping: 16, stiffness: 140}});
  // 버튼: 매 클립 시작에 "눌림" 펄스
  const press = spring({frame: local, fps, config: {damping: 8, stiffness: 260}});
  const btnScale = 1 - 0.08 * Math.sin(Math.min(1, local / 10) * Math.PI);
  const fade = Math.min(
    interpolate(frame, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [D - 8, D - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  const ring = interpolate(local, [0, 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden', opacity: fade}}>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(50% 60% at 50% 45%, rgba(111,240,214,.12), transparent 70%)'}} />
      {/* 왼쪽 버튼 */}
      <div style={{position: 'absolute', left: 20, top: 430, width: 280, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, fontFamily: FONT}}>
        <div
          style={{
            position: 'relative',
            padding: '18px 30px',
            borderRadius: 999,
            background: MINT,
            color: '#062018',
            fontWeight: 900,
            fontSize: 32,
            letterSpacing: -1,
            whiteSpace: 'nowrap',
            boxShadow: `0 0 0 ${ring * 14}px rgba(111,240,214,${0.35 * (1 - ring)}), 0 16px 40px rgba(111,240,214,.35)`,
            transform: `scale(${btnScale})`,
          }}
        >
          ▶ 완성본 만들기
        </div>
        <div style={{color: 'rgba(255,255,255,.7)', fontWeight: 700, fontSize: 24, opacity: press}}>버튼 한 번</div>
        <svg width="120" height="44" viewBox="0 0 120 44" style={{opacity: 0.9, transform: `translateX(${(1 - press) * -20}px)`}}>
          <path d="M4 22h96" stroke={MINT} strokeWidth="6" strokeLinecap="round" strokeDasharray="110" strokeDashoffset={110 * (1 - press)} />
          <path d="M84 8l18 14-18 14" fill="none" stroke={MINT} strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" opacity={press} />
        </svg>
      </div>
      {/* 폰 프레임 */}
      <div
        style={{
          position: 'absolute',
          left: PH_X - 12,
          top: PH_Y - 12,
          width: PH_W + 24,
          height: PH_H + 24,
          borderRadius: 44,
          background: '#0d1218',
          boxShadow: '0 0 0 3px #232a33, 0 30px 80px rgba(0,0,0,.65), 0 0 60px rgba(111,240,214,.18)',
        }}
      >
        <div style={{position: 'absolute', left: 12, top: 12, width: PH_W, height: PH_H, borderRadius: 34, overflow: 'hidden', background: '#000'}}>
          {[0, 1, 2, 3].map((i) => {
            if (i !== idx && i !== idx - 1) return null;
            const isCur = i === idx;
            const x = isCur ? (1 - slide) * PH_W : -slide * PH_W;
            const start = i * CLIP_F;
            return (
              <div key={i} style={{position: 'absolute', left: x, top: 0, width: PH_W, height: PH_H}}>
                <OffthreadVideoAt src={staticFile(`render/clip${i + 1}.mp4`)} startFrom={start} />
              </div>
            );
          })}
          {/* 노치 */}
          <div style={{position: 'absolute', left: PH_W / 2 - 60, top: 10, width: 120, height: 26, borderRadius: 13, background: '#000'}} />
        </div>
      </div>
      {/* 오른쪽 자막 */}
      <div style={{position: 'absolute', left: PH_X + PH_W + 30, top: 400, width: 330, fontFamily: FONT}}>
        <div style={{display: 'flex', flexWrap: 'wrap', fontWeight: 900, fontSize: 46, lineHeight: 1.25, letterSpacing: -1.5}}>
          {parse('자막·음성 입힌 [완성본] 바로 나옴').map((tok, i) => (
            <Word key={i} tok={tok} idx={i} local={frame - 8} size={46} />
          ))}
        </div>
        <div style={{marginTop: 16, display: 'flex', gap: 8, alignItems: 'center', opacity: interpolate(frame, [40, 52], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} style={{width: i === idx ? 34 : 12, height: 12, borderRadius: 6, background: i === idx ? MINT : 'rgba(255,255,255,.25)'}} />
          ))}
          <span style={{marginLeft: 8, color: 'rgba(255,255,255,.7)', fontWeight: 700, fontSize: 22}}>{idx + 1} / 4편</span>
        </div>
      </div>
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
const HK_LINES = ['오늘 [뭘 만들지] 고민 끝.', '매일 랭킹에\n{100만뷰 쇼츠}가 줄 서 있습니다', '그대로 <내 제품>으로\n10분이면 똑같이'];
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
