import React, {useEffect, useState} from 'react';
import {
  AbsoluteFill,
  Img,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import data from './hero_data.json';

// ── 데이터 ─────────────────────────────────────────────
type Item = {id: string; name: string; title: string; views: number; seen: string; file: string};
const ITEMS = data.items as Item[];
const COUNT = data.count as number;
const MAX_VIEWS = data.maxViews as number;

export const fmtViews = (v: number): string => {
  if (v >= 100_000_000) return `${(v / 100_000_000).toFixed(1)}억회`;
  return `${Math.round(v / 10_000)}만회`;
};
const fmtSeen = (s: string): string => {
  const [, m, d] = s.split('-');
  return `${Number(m)}/${Number(d)} 랭킹`;
};

// ── 레이아웃 상수 ─────────────────────────────────────
const W = 1080;
const H = 1440;
const FPS = 30;
const DUR = 360; // 12s
const COLS = 3;
const GAP = 22;
const PAD = 24;
const CARD_W = Math.floor((W - PAD * 2 - GAP * (COLS - 1)) / COLS); // 330
const CARD_H = Math.round((CARD_W * 16) / 9); // 587
const PITCH = CARD_H + GAP;
const RADIUS = 28;
const LINE_FRAMES = DUR / 4; // 90
const CARD_ROWS = [5, 6, 5]; // 열마다 카드 수 → 속도 차이 (1주기/12s)
const COL_DIR = [1, -1, 1]; // 1 = 위로, -1 = 아래로 (offset을 빼므로 부호 반대)

const FONT = 'HeroKR';

// ── 폰트 로드(로컬 파일, 모든 한글/숫자 글리프 포함) ──
const useFont = () => {
  const [handle] = useState(() => delayRender('load font'));
  useEffect(() => {
    const f = new FontFace(FONT, `url(${staticFile('fonts/NotoSansKR-VF.otf')})`, {weight: '100 900'});
    f.load()
      .then((loaded) => {
        (document as any).fonts.add(loaded);
        continueRender(handle);
      })
      .catch(() => continueRender(handle));
  }, [handle]);
};

// ── ▶ 는 글리프 대신 SVG 삼각형 ─────────────────────────
const Play: React.FC<{size: number; color: string}> = ({size, color}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{display: 'inline-block', flex: 'none'}}>
    <path d="M6 3.5v17l14-8.5z" fill={color} />
  </svg>
);

// ── 카드 ──────────────────────────────────────────────
const Card: React.FC<{item: Item; hot: number; countT: number}> = ({item, hot, countT}) => {
  const scale = 1 + 0.06 * hot;
  const views = Math.round(interpolate(countT, [0, 1], [item.views * 0.88, item.views]));
  return (
    <div
      style={{
        position: 'relative',
        width: CARD_W,
        height: CARD_H,
        borderRadius: RADIUS,
        overflow: 'hidden',
        background: '#111820',
        transform: `scale(${scale})`,
        boxShadow: hot > 0 ? `0 0 ${40 * hot}px ${10 * hot}px rgba(255,216,77,${0.45 * hot})` : '0 8px 24px rgba(0,0,0,.45)',
        outline: hot > 0 ? `${3 * hot}px solid rgba(255,216,77,${0.9 * hot})` : 'none',
      }}
    >
      <Img src={staticFile(item.file)} style={{width: '100%', height: '100%', objectFit: 'cover', display: 'block'}} />
      {/* 하단 그라데이션 */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 180, background: 'linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,.75))'}} />
      {/* 좌상단 랭킹 칩 */}
      <div
        style={{
          position: 'absolute',
          top: 14,
          left: 14,
          padding: '6px 12px',
          borderRadius: 999,
          background: '#FF4D4D',
          color: '#fff',
          fontFamily: FONT,
          fontWeight: 800,
          fontSize: 22,
          lineHeight: 1.1,
          letterSpacing: -0.5,
        }}
      >
        {fmtSeen(item.seen)}
      </div>
      {/* 좌하단 조회수 필 */}
      <div
        style={{
          position: 'absolute',
          left: 14,
          bottom: 14,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '7px 14px 7px 10px',
          borderRadius: 999,
          background: hot > 0 ? '#FFD84D' : 'rgba(0,0,0,.62)',
          color: hot > 0 ? '#111' : '#fff',
          fontFamily: FONT,
          fontWeight: 900,
          fontSize: 27,
          lineHeight: 1.1,
          fontVariantNumeric: 'tabular-nums',
          letterSpacing: -0.5,
        }}
      >
        <Play size={22} color={hot > 0 ? '#111' : '#fff'} />
        <span>{fmtViews(views)}</span>
      </div>
    </div>
  );
};

// ── 스크롤 열 ─────────────────────────────────────────
const Column: React.FC<{col: number; items: Item[]; frame: number}> = ({col, items, frame}) => {
  const n = items.length;
  const cycle = n * PITCH;
  const offset = ((frame / DUR) * cycle * COL_DIR[col] + cycle * 10) % cycle;
  // 시작 위치를 열마다 달리 해서 카드 줄이 안 맞게
  const phase = [0.15, 0.55, 0.35][col] * PITCH;
  const x = PAD + col * (CARD_W + GAP);

  // 이 열이 '포인트' 담당인 줄(line)
  const line = Math.floor(frame / LINE_FRAMES);
  const isHotCol = line % COLS === col;
  const lineStart = line * LINE_FRAMES;
  const local = frame - lineStart;
  const hotWin = local >= 12 && local < 78;
  // 포인트 카드: 효과 중간 시점(lineStart+45)에 y=800(자막 띠 아래 중앙)에 가장 가까운 카드로 고정
  let hotIdx = -1;
  if (isHotCol && hotWin) {
    const f0 = lineStart + 45;
    const off0 = (((f0 / DUR) * cycle * COL_DIR[col] + cycle * 10) % cycle);
    let best = 1e9;
    for (let i = 0; i < n; i++) {
      const base = ((i * PITCH - off0 + phase) % cycle + cycle) % cycle;
      const cy = base + CARD_H / 2;
      const d = Math.abs(cy - 800);
      if (d < best) {
        best = d;
        hotIdx = i;
      }
    }
  }
  const hotT = hotWin
    ? Math.min(
        interpolate(local, [12, 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
        interpolate(local, [66, 78], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
      )
    : 0;
  const countT = interpolate(local, [14, 60], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <>
      {items.map((it, i) => {
        // 카드 기본 y (cycle 안), 위아래로 한 장씩 더 그려서 끊김 없게
        const base = ((i * PITCH - offset + phase) % cycle + cycle) % cycle;
        const ys = [base, base - cycle, base + cycle].filter((y) => y > -CARD_H - 10 && y < H + 10);
        return ys.map((y) => (
          <div key={`${it.id}-${y > base ? 'b' : y < base ? 'a' : 'c'}`} style={{position: 'absolute', left: x, top: y}}>
            <Card item={it} hot={i === hotIdx ? hotT : 0} countT={i === hotIdx ? countT : 1} />
          </div>
        ));
      })}
    </>
  );
};

// ── 자막 ──────────────────────────────────────────────
type Tok = {t: string; k?: 'y' | 'r'; play?: boolean};
const LINES: Tok[][] = [
  [{t: '오늘도'}, {t: '랭킹에', k: 'y'}, {t: '올라온'}, {t: '대박', k: 'r'}, {t: '쇼츠'}],
  [{t: '최고'}, {t: fmtViews(MAX_VIEWS), k: 'y', play: true}, {t: '찍은'}, {t: '쇼핑쇼츠'}],
  [{t: '이런'}, {t: '영상이'}, {t: '매일', k: 'r'}, {t: '잡힙니다', k: 'y'}],
  [{t: '뭘'}, {t: '만들지'}, {t: '고민', k: 'r'}, {t: '끝', k: 'y'}],
];

const Word: React.FC<{tok: Tok; idx: number; local: number; exitT: number}> = ({tok, idx, local, exitT}) => {
  const {fps} = useVideoConfig();
  const delay = 4 + idx * 6;
  const s = spring({frame: local - delay, fps, config: {damping: 11, stiffness: 190, mass: 0.7}});
  const pop = interpolate(s, [0, 1], [0.6, 1]);
  const op = interpolate(local - delay, [0, 4], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const sweep = interpolate(local - delay, [5, 17], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const isY = tok.k === 'y';
  const isR = tok.k === 'r';
  const color = isY ? (sweep > 0.5 ? '#111' : '#fff') : isR ? '#FF4D4D' : '#fff';
  return (
    <span
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: isY ? '2px 16px' : '2px 4px',
        margin: '0 6px',
        transform: `scale(${pop}) translateY(${(1 - s) * 18}px)`,
        opacity: op * (1 - exitT),
        color,
        textShadow: isY && sweep > 0.5 ? 'none' : '0 4px 0 rgba(0,0,0,.55)',
        whiteSpace: 'nowrap',
      }}
    >
      {isY && (
        <span
          style={{
            position: 'absolute',
            left: 0,
            top: 6,
            bottom: 6,
            width: `${sweep * 100}%`,
            background: '#FFD84D',
            borderRadius: 12,
            transform: 'rotate(-1.2deg)',
            zIndex: 0,
          }}
        />
      )}
      {tok.play && (
        <span style={{position: 'relative', zIndex: 1, display: 'inline-flex'}}>
          <Play size={64} color={color} />
        </span>
      )}
      <span style={{position: 'relative', zIndex: 1}}>{tok.t}</span>
    </span>
  );
};

const Subtitle: React.FC<{frame: number}> = ({frame}) => {
  const line = Math.floor(frame / LINE_FRAMES) % LINES.length;
  const local = frame - line * LINE_FRAMES;
  const exitT = interpolate(local, [LINE_FRAMES - 10, LINE_FRAMES - 2], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        top: 0,
        height: 640,
        background: 'linear-gradient(180deg, rgba(7,11,15,.98) 0%, rgba(7,11,15,.96) 62%, rgba(7,11,15,.6) 82%, rgba(7,11,15,0) 100%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-start',
        paddingTop: 92,
      }}
    >
      <div
        style={{
          width: 980,
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          rowGap: 14,
          fontFamily: FONT,
          fontWeight: 900,
          fontSize: 88,
          lineHeight: 1.18,
          letterSpacing: -2,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {LINES[line].map((tok, i) => (
          <Word key={`${line}-${i}`} tok={tok} idx={i} local={local} exitT={exitT} />
        ))}
      </div>
      <div
        style={{
          marginTop: 26,
          fontFamily: FONT,
          fontWeight: 700,
          fontSize: 31,
          color: 'rgba(255,255,255,.82)',
          letterSpacing: -0.5,
          textShadow: '0 2px 0 rgba(0,0,0,.6)',
        }}
      >
        숏템메이커 랭킹에 잡힌 100만뷰+ 쇼핑쇼츠 <span style={{color: '#FFD84D', fontWeight: 900}}>{COUNT}편</span>
      </div>
    </div>
  );
};

// ── 메인 ──────────────────────────────────────────────
export const LandingHeroWall: React.FC = () => {
  useFont();
  const frame = useCurrentFrame();
  // 열 배분: 5 / 6 / 5 = 16장 (조회수 순으로 섞어 배치)
  let k = 0;
  const cols = CARD_ROWS.map((n) => ITEMS.slice(k, (k += n)));
  return (
    <AbsoluteFill style={{background: '#070b0f', overflow: 'hidden'}}>
      {cols.map((items, c) => (
        <Column key={c} col={c} items={items} frame={frame} />
      ))}
      <Subtitle frame={frame} />
      {/* 하단 페이드 */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 240, background: 'linear-gradient(0deg, rgba(7,11,15,1) 0%, rgba(7,11,15,0) 100%)'}} />
    </AbsoluteFill>
  );
};

export const HERO_WALL = {width: W, height: H, fps: FPS, durationInFrames: DUR};
