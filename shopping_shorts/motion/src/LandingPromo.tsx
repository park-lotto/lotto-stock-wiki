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

// ── 3) ④ 렌더화면 칸 (1080x1080, 10s) — 완성 쇼츠 3편을 세로 크게 이어 재생(폰프레임·문구 없음) ─
// 재료 public/render/full1~3.mp4 (608x1080, 서버 mix_jobs final.mp4에서 3.4s씩 축소 컷, gitignore)
//   full1=291623f777ce(행주·RedCow) full2=a490cb5998fa(세탁기 청소) full3=434e0589793c(행주 2)
export const SQ4 = {width: 1080, height: 1080, fps: 30, durationInFrames: 300};
const FULL_F = 100; // 3.33s
const XF = 8; // 크로스페이드
const FULL_W = 608;

export const SqRender: React.FC = () => {
  const frame = useCurrentFrame();
  const D = SQ4.durationInFrames;
  const fade = Math.min(
    interpolate(frame, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [D - 8, D - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden', opacity: fade}}>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(60% 70% at 50% 50%, rgba(111,240,214,.07), transparent 70%)'}} />
      {[0, 1, 2].map((i) => {
        const from = i * FULL_F;
        const inT = i === 0 ? 1 : interpolate(frame, [from, from + XF], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return (
          <Sequence key={i} from={from} durationInFrames={FULL_F + XF} layout="none">
            <div style={{position: 'absolute', left: (1080 - FULL_W) / 2, top: 0, width: FULL_W, height: 1080, opacity: inT, boxShadow: '0 0 80px rgba(0,0,0,.7)'}}>
              <OffthreadVideo src={staticFile(`render/full${i + 1}.mp4`)} muted style={{width: '100%', height: '100%', display: 'block'}} />
            </div>
          </Sequence>
        );
      })}
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

// ── 6) easy60.mp4 (1600x500, 8s) — "60대도 만듭니다" + 단계 버튼 1→4 차례로 눌림 ─
export const EASY = {width: 1600, height: 500, fps: 30, durationInFrames: 240};
const STEPS = ['영상 담기', '대본 생성', '장면 매칭', '완성본'];
export const Easy60: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const D = EASY.durationInFrames;
  const fade = Math.min(
    interpolate(frame, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    interpolate(frame, [D - 8, D - 1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
  const stepAt = (i: number) => 60 + i * 40; // 버튼 i 눌리는 프레임
  const done = STEPS.filter((_, i) => frame >= stepAt(i)).length;
  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden', opacity: fade}}>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(50% 90% at 78% 50%, rgba(111,240,214,.12), transparent 70%)'}} />
      {/* 왼쪽 문구 */}
      <div style={{position: 'absolute', left: 64, top: 0, bottom: 0, width: 600, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 16, fontFamily: FONT}}>
        <div style={{display: 'flex', flexWrap: 'wrap', alignItems: 'center', fontWeight: 900, fontSize: 62, lineHeight: 1.2, letterSpacing: -2}}>
          {parse('단계만 따라가면 {60대도} 만듭니다').map((tok, i) => (
            <Word key={i} tok={tok} idx={i} local={frame - 4} size={62} />
          ))}
        </div>
        <div style={{display: 'flex', flexWrap: 'wrap', alignItems: 'center', fontWeight: 900, fontSize: 36, lineHeight: 1.25, letterSpacing: -1, marginLeft: 6}}>
          {parse('편집 몰라도 · [버튼 네 번]이면 완성본').map((tok, i) => (
            <Word key={i} tok={tok} idx={i + 4} local={frame - 4} size={36} />
          ))}
        </div>
      </div>
      {/* 오른쪽 단계 버튼 */}
      <div style={{position: 'absolute', right: 70, top: 0, bottom: 0, display: 'flex', alignItems: 'center', gap: 22, fontFamily: FONT}}>
        {STEPS.map((label, i) => {
          const t = frame - stepAt(i);
          const press = spring({frame: t, fps, config: {damping: 9, stiffness: 240}});
          const on = t >= 0;
          const scale = on ? 1 - 0.12 * Math.sin(Math.min(1, Math.max(0, t / 10)) * Math.PI) : 1;
          const ring = interpolate(t, [0, 24], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <React.Fragment key={label}>
              {i > 0 && <div style={{width: 34, height: 6, borderRadius: 3, background: frame >= stepAt(i) - 12 ? MINT : 'rgba(255,255,255,.18)'}} />}
              <div
                style={{
                  width: 150,
                  height: 150,
                  borderRadius: 30,
                  background: on ? MINT : '#151c24',
                  boxShadow: on ? `0 0 0 ${ring * 16}px rgba(111,240,214,${0.35 * (1 - ring)}), 0 16px 40px rgba(111,240,214,.3)` : '0 0 0 2px rgba(255,255,255,.12)',
                  transform: `scale(${scale})`,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  color: on ? '#062018' : 'rgba(255,255,255,.55)',
                }}
              >
                <div style={{fontWeight: 900, fontSize: 54, lineHeight: 1}}>{on && press > 0.5 ? '✓' : i + 1}</div>
                <div style={{fontWeight: 900, fontSize: 24, letterSpacing: -0.5}}>{label}</div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
      <div style={{position: 'absolute', right: 70, bottom: 30, fontFamily: FONT, fontWeight: 700, fontSize: 24, color: 'rgba(255,255,255,.6)', opacity: done > 0 ? 1 : 0}}>
        {done < 4 ? `${done} / 4 단계` : '완성본 나옴!'}
      </div>
    </AbsoluteFill>
  );
};
