/**
 * VSL 모션 어휘 8종 — 기획서 `영상제작/00_기획/S1_장면설계.md` §2와 1:1로 대응한다.
 *
 * 왜 라이브러리로 뽑나: 씬마다 인라인으로 애니메이션을 짜면 S2·S4·S5에서 같은 걸
 * 또 짜게 되고, 그때마다 미묘하게 달라져 영상 전체의 '말투'가 흔들린다(0순위-B의 영상판).
 * 모션을 어휘로 고정해 두면 씬은 **어휘를 고르는 일**이 되고 리듬만 설계하면 된다.
 *
 * 공통 규약
 *  - 모든 컴포넌트는 자기 <Sequence> 안에서 프레임 0부터 시작한다고 가정한다.
 *  - 영상 팬(액자)은 반드시 position:relative + overflow:hidden — <Loop>가 내부에
 *    absolute-fill 시퀀스를 만들기 때문에 static이면 액자를 뚫고 전체화면이 된다
 *    (2026-08-11 v1 실사고, 프레임 실측으로 발견).
 */

import React from 'react';
import {
  AbsoluteFill, Loop, OffthreadVideo, interpolate, random,
  spring, staticFile, useCurrentFrame, useVideoConfig, Easing,
} from 'remotion';

export const MINT = '#3DF0B2';
export const BG = '#08110E';
export const FONT = "'Pretendard','Archivo',sans-serif";

export type Clip = { src: string; dur: number };

/* ── 릴 팬: 세로 9:16 클립 한 장 ─────────────────────────────────
   seed로 시작 지점을 흩어 같은 클립이 여러 번 나와도 다른 장면이 보이게 한다. */
export const Reel: React.FC<{
  clip: Clip; w: number; h: number; seed?: number; radius?: number;
  grayscale?: boolean; dim?: number;
}> = ({ clip, w, h, seed = 0, radius = 14, grayscale, dim = 0 }) => {
  const { fps } = useVideoConfig();
  const span = Math.max(2, clip.dur - 5);
  const offset = 1 + (random(`off-${clip.src}-${seed}`) * span);
  const usable = Math.max(1.5, clip.dur - offset);
  return (
    <div style={{
      position: 'relative', width: w, height: h, overflow: 'hidden',
      borderRadius: radius, background: '#000',
      boxShadow: '0 22px 60px rgba(0,0,0,0.6)',
    }}>
      <Loop durationInFrames={Math.max(1, Math.floor(usable * fps))}>
        <OffthreadVideo
          src={staticFile(clip.src)}
          trimBefore={Math.round(offset * fps)}
          volume={0}
          style={{
            width: '100%', height: '100%', objectFit: 'cover',
            filter: grayscale ? 'grayscale(1) contrast(1.1)' : undefined,
          }}
        />
      </Loop>
      {dim > 0 ? <AbsoluteFill style={{ background: `rgba(0,0,0,${dim})` }} /> : null}
    </div>
  );
};

/* 흐린 배경 — 같은 클립을 크게 깔고 블러. 세로 영상의 좌우 여백을 죽은 공간으로 두지 않는다. */
export const BlurBed: React.FC<{ clip: Clip; seed?: number }> = ({ clip, seed = 0 }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();
  const offset = 1 + random(`bed-${clip.src}-${seed}`) * Math.max(2, clip.dur - 6);
  const drift = interpolate(frame, [0, durationInFrames], [1.18, 1.26]);
  return (
    <AbsoluteFill style={{ overflow: 'hidden', background: BG }}>
      <Loop durationInFrames={Math.max(1, Math.floor((clip.dur - offset) * fps))}>
        <OffthreadVideo
          src={staticFile(clip.src)} trimBefore={Math.round(offset * fps)} volume={0}
          style={{
            width: '100%', height: '100%', objectFit: 'cover',
            filter: 'blur(48px) brightness(0.3) saturate(1.25)',
            transform: `scale(${drift})`,
          }}
        />
      </Loop>
    </AbsoluteFill>
  );
};

/* ── M1 GridBloom: 3×3 격자가 스태거로 팝인 ──────────────────── */
export const GridBloom: React.FC<{ clips: Clip[]; cols?: number; stagger?: number }> = ({
  clips, cols = 3, stagger = 2.5,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const rows = Math.ceil(clips.length / cols);
  const gap = 16;
  const cellH = Math.floor((1080 - gap * (rows + 1)) / rows);
  const cellW = Math.floor(cellH * 9 / 16);
  // 격자 전체가 아주 천천히 밀려 올라간다 — 정지 화면이 아니라 '흐르는 생산 라인'
  const rise = interpolate(frame, [0, durationInFrames], [12, -12]);
  return (
    <AbsoluteFill style={{ background: BG, alignItems: 'center', justifyContent: 'center' }}>
      <div style={{
        display: 'grid', gridTemplateColumns: `repeat(${cols}, ${cellW}px)`,
        gap, transform: `translateY(${rise}px)`,
      }}>
        {clips.map((c, i) => {
          const pop = spring({
            frame: frame - i * stagger, fps,
            config: { damping: 13, stiffness: 200, mass: 0.5 },
          });
          return (
            <div key={i} style={{
              transform: `scale(${interpolate(pop, [0, 1], [0.55, 1])})`,
              opacity: pop,
            }}>
              <Reel clip={c} w={cellW} h={cellH} seed={i} radius={10} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ── M2 PickZoom: 격자에서 하나가 확대되며 나머지는 밀려 흐려짐 ── */
export const PickZoom: React.FC<{ hero: Clip; others?: Clip[]; seed?: number }> = ({
  hero, others = [], seed = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const grow = spring({ frame, fps, config: { damping: 18, stiffness: 120, mass: 0.9 } });
  const scale = interpolate(grow, [0, 1], [0.72, 1]);
  const push = interpolate(grow, [0, 1], [0, 480]);
  const drift = interpolate(frame, [0, durationInFrames], [1, 1.05]);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <BlurBed clip={hero} seed={seed} />
      {/* 밀려나는 주변 카드 — 결과물이 '여럿 중 하나'임을 유지 */}
      {others.slice(0, 2).map((c, i) => (
        <AbsoluteFill key={i} style={{
          alignItems: 'center', justifyContent: 'center',
          transform: `translateX(${(i === 0 ? -1 : 1) * push}px) scale(0.74)`,
          opacity: interpolate(grow, [0, 1], [0.9, 0.34]),
        }}>
          <Reel clip={c} w={470} h={836} seed={seed + i + 7} dim={0.35} />
        </AbsoluteFill>
      ))}
      <AbsoluteFill style={{
        alignItems: 'center', justifyContent: 'center',
        transform: `scale(${scale * drift})`,
      }}>
        <Reel clip={hero} w={572} h={1016} seed={seed} radius={20} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ── M3 SliceWipe: 세로 5조각이 시차를 두고 쓸려 들어오며 화면 교체 ── */
export const SliceWipe: React.FC<{
  children: React.ReactNode; slices?: number; durFrames?: number; from?: 'top' | 'bottom';
}> = ({ children, slices = 5, durFrames = 12, from = 'top' }) => {
  const frame = useCurrentFrame();
  const w = 1920 / slices;
  return (
    <AbsoluteFill>
      {children}
      {/* 커버 슬라이스가 위로 빠지며 아래 화면을 드러낸다 */}
      {Array.from({ length: slices }).map((_, i) => {
        const p = interpolate(frame, [i * 1.6, i * 1.6 + durFrames], [0, 1], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.bezier(0.76, 0, 0.24, 1),
        });
        const y = (from === 'top' ? -1 : 1) * p * 1080;
        return (
          <div key={i} style={{
            position: 'absolute', left: i * w, top: 0, width: w + 1, height: 1080,
            background: i % 2 ? BG : '#0C1A15', transform: `translateY(${y}px)`,
          }} />
        );
      })}
    </AbsoluteFill>
  );
};

/* ── M4 WhipPan: 진입 순간 수평 이동 + 모션블러 ─────────────── */
export const WhipPan: React.FC<{ children: React.ReactNode; dir?: 1 | -1 }> = ({
  children, dir = 1,
}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, 9], [1, 0], {
    extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
  });
  return (
    <AbsoluteFill style={{
      transform: `translateX(${dir * p * 900}px)`,
      filter: `blur(${p * 26}px)`,
    }}>
      {children}
    </AbsoluteFill>
  );
};

/* ── M5 CardStack: 카드가 쌓였다가 부채꼴로 펼쳐진다 ─────────── */
export const CardStack: React.FC<{ clips: Clip[]; seed?: number }> = ({ clips, seed = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const open = spring({ frame, fps, config: { damping: 16, stiffness: 110, mass: 1 } });
  const n = clips.length;
  return (
    <AbsoluteFill style={{ background: BG, alignItems: 'center', justifyContent: 'center' }}>
      <BlurBed clip={clips[0]} seed={seed} />
      {clips.map((c, i) => {
        const mid = (n - 1) / 2;
        const off = i - mid;
        const x = interpolate(open, [0, 1], [off * 14, off * 400]);
        const rot = interpolate(open, [0, 1], [off * 1.5, off * 7]);
        const delay = spring({ frame: frame - i * 3, fps, config: { damping: 15, stiffness: 150 } });
        return (
          <AbsoluteFill key={i} style={{
            alignItems: 'center', justifyContent: 'center',
            transform: `translateX(${x}px) rotate(${rot}deg) scale(${interpolate(delay, [0, 1], [0.8, 1])})`,
            opacity: delay,
          }}>
            <Reel clip={c} w={430} h={764} seed={seed + i} radius={16} />
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
};

/* ── M6 KineticWord: 단어 단위 팝인 + 키워드 스탬프 ──────────
   text의 |구간|은 민트 스탬프(박스+글로우)로 강조된다. */
type WordTok = { t: string; hi: boolean };
/* |강조|는 **한 덩어리**로 묶는다.
   예전엔 강조 안의 단어를 하나씩 쪼개 각자 민트 박스를 줬다 → flex 줄바꿈이
   "안 하시는 / 걸 추천드립니다" 처럼 구 한가운데를 잘라 박스가 따로 놀았다
   (사장님 캡처 2장 실측). 덩어리로 묶으면 통째로 다음 줄로 넘어간다. */
type WordGroup = { words: string[]; hi: boolean; tail?: string };

const tokenize = (text: string): WordGroup[] => {
  const out: WordGroup[] = [];
  text.split('|').forEach((chunk, ci) => {
    const words = chunk.split(/\s+/).filter(Boolean);
    if (!words.length) return;
    const hi = ci % 2 === 1;
    if (hi) out.push({ words, hi });                       // 강조는 통째로
    else words.forEach((w) => out.push({ words: [w], hi })); // 일반은 낱말 단위(등장 스태거)
  });
  /* ★구두점이 줄 앞으로 떨어지는 것 방지 — 강조 뒤 쉼표가 다음 줄 첫 글자가 돼
     ", 음성과 대본만…"이 됐다(실측). 선행 구두점은 앞 덩어리에 붙여 같이 다닌다. */
  for (let i = 1; i < out.length; i += 1) {
    const g = out[i];
    const m = g.words[0]?.match(/^([,.!?…·]+)(.*)$/);
    if (!m) continue;
    out[i - 1].tail = (out[i - 1].tail ?? '') + m[1];
    if (m[2]) g.words[0] = m[2];
    else { g.words.shift(); if (!g.words.length) { out.splice(i, 1); i -= 1; } }
  }
  return out;
};

/* 균형 줄바꿈 — flex-wrap에 맡기면 첫 줄을 꽉 채우고 남은 한 낱말이 둘째 줄에
   혼자 떨어진다("… 댓글이 많은 / 순입니다." 사장님 캡처). 그래서 **줄을 직접 나눈다**:
   전체 폭을 줄 수로 나눈 목표치를 넘어가면 다음 줄로 넘긴다.
   한글은 글자폭이 거의 균일해서 글자수로 재도 눈에 맞는다(강조는 박스 여백 +2자). */
const MAX_W = 1560;

const layoutLines = (groups: WordGroup[], size: number): WordGroup[][] => {
  const cost = (g: WordGroup) => g.words.join(' ').length + (g.tail?.length ?? 0) + (g.hi ? 2 : 0) + 0.6;
  const total = groups.reduce((a, g) => a + cost(g), 0);
  const perLine = Math.max(6, Math.floor(MAX_W / (size * 0.98)));
  const lineCount = Math.max(1, Math.ceil(total / perLine));
  if (lineCount === 1) return [groups];
  const target = total / lineCount;
  const lines: WordGroup[][] = [];
  let cur: WordGroup[] = [];
  let acc = 0;
  groups.forEach((g, i) => {
    const c = cost(g);
    // 남은 그룹 수가 '앞으로 더 만들 줄 수' 이상이어야 줄을 나눈다.
    // ★rest >= linesLeft 로 뒀다가 마지막 강조 덩어리를 못 내려보내 한 줄에 다 붙고
    //   좌우가 잘렸다(사장님 캡처 'SNS로 … 추천드립니다'). -1이 맞다.
    const rest = groups.length - i;
    const linesLeft = lineCount - lines.length;
    const balance = acc + c / 2 > target && linesLeft > 1 && rest >= linesLeft - 1;
    const overflow = acc + c > perLine;        // 백스톱: 폭을 넘기면 무조건 넘긴다
    if (cur.length && (balance || overflow)) {
      lines.push(cur); cur = []; acc = 0;
    }
    cur.push(g); acc += c;
  });
  if (cur.length) lines.push(cur);
  return lines;
};

export const KineticWord: React.FC<{
  text: string; sub?: string; size?: number; center?: boolean; perWord?: number;
}> = ({ text, sub, size = 74, center = false, perWord = 1.6 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const groups = tokenize(text);
  const lines = layoutLines(groups, size);
  let wi = 0; // 등장 순서는 낱말 기준(강조 덩어리도 안에서 차례로 뜬다)
  return (
    <AbsoluteFill style={{
      alignItems: 'center', justifyContent: center ? 'center' : 'flex-end',
      paddingBottom: center ? 0 : 92, pointerEvents: 'none',
    }}>
      <div style={{ maxWidth: MAX_W, textAlign: 'center' }}>
        {lines.map((line, li) => (
          <div key={li} style={{
            display: 'flex', flexWrap: 'nowrap', gap: 16,
            justifyContent: 'center', alignItems: 'baseline',
            marginTop: li === 0 ? 0 : 10,
          }}>
            {line.map((g, gi) => {
              const start = wi; wi += g.words.length;
              const s = spring({
                frame: frame - start * perWord, fps,
                config: { damping: 12, stiffness: 220, mass: 0.4 },
              });
              const y = interpolate(s, [0, 1], [34, 0]);
              const sc = interpolate(s, [0, 1], [0.82, 1]);
              const box = (
                <span key={gi} style={{
                  display: 'inline-flex', gap: 14, whiteSpace: 'nowrap',
                  transform: `translateY(${y}px) scale(${sc})`, opacity: s,
                  fontFamily: FONT, fontWeight: 900, fontSize: size, lineHeight: 1.24,
                  color: g.hi ? '#05130E' : '#fff',
                  background: g.hi ? MINT : undefined,
                  padding: g.hi ? '2px 16px' : undefined,
                  borderRadius: g.hi ? 12 : undefined,
                  boxShadow: g.hi ? `0 0 38px ${MINT}66` : undefined,
                  textShadow: g.hi ? 'none' : '0 8px 32px rgba(0,0,0,0.8)',
                  wordBreak: 'keep-all',
                }}>{g.words.join(' ')}</span>
              );
              return g.tail ? (
                <span key={gi} style={{
                  display: 'inline-flex', alignItems: 'baseline', whiteSpace: 'nowrap',
                }}>
                  {box}
                  <span style={{
                    fontFamily: FONT, fontWeight: 900, fontSize: size, lineHeight: 1.24,
                    color: '#fff', textShadow: '0 8px 32px rgba(0,0,0,0.8)',
                    transform: `translateY(${y}px) scale(${sc})`, opacity: s,
                  }}>{g.tail}</span>
                </span>
              ) : box;
            })}
          </div>
        ))}
        {sub ? (
          <div style={{
            marginTop: 18, fontFamily: FONT, fontWeight: 700, fontSize: 38,
            color: 'rgba(255,255,255,0.86)', textShadow: '0 4px 20px rgba(0,0,0,0.85)',
            opacity: interpolate(frame, [wi * perWord, wi * perWord + 8], [0, 1],
              { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
          }}>{sub}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/* ── M7 CountPunch: 숫자 카운트 + 착지 셰이크 ────────────────── */
export const CountPunch: React.FC<{
  from: number; to: number; suffix?: string; label?: string; holdFrames?: number;
  /** 강조색 — S2 페인 구간은 붉은색을 넘긴다. 기본 민트로 두면 "여긴 문제 구간"이라는
   *  색 규칙이 카운터 하나 때문에 깨진다(2026-08-11 S2 v1 프레임 검수에서 적발). */
  color?: string;
}> = ({ from, to, suffix = '', label, holdFrames = 26, color = MINT }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = interpolate(frame, [0, holdFrames], [0, 1], {
    extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
  });
  const val = Math.round(from + (to - from) * p);
  // 착지 직후 짧은 셰이크 — 숫자가 '쾅' 박히는 느낌
  const land = frame - holdFrames;
  const shake = land >= 0 && land < 10
    ? Math.sin(land * 2.2) * (10 - land) * 0.9 : 0;
  const pop = spring({ frame: land, fps, config: { damping: 9, stiffness: 260, mass: 0.4 } });
  const sc = land >= 0 ? interpolate(pop, [0, 1], [1.22, 1]) : 1;
  return (
    <AbsoluteFill style={{
      alignItems: 'center', justifyContent: 'center', pointerEvents: 'none',
      transform: `translate(${shake}px, ${shake * 0.4}px)`,
    }}>
      <div style={{ textAlign: 'center', transform: `scale(${sc})` }}>
        <div style={{
          fontFamily: "'Space Mono','Roboto Mono',monospace", fontWeight: 700,
          fontSize: 210, color, textShadow: `0 0 70px ${color}55`,
          letterSpacing: '-0.02em',
        }}>{val}{suffix}</div>
        {label ? (
          <div style={{
            fontFamily: FONT, fontWeight: 800, fontSize: 44, color: '#fff',
            marginTop: -10, textShadow: '0 6px 24px rgba(0,0,0,0.8)',
          }}>{label}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/* ── M8 BlackCard: 암전 + 중앙 한 줄 ─────────────────────────── */
export const BlackCard: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const vig = interpolate(frame, [0, 10], [0.4, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ background: '#040907' }}>
      <AbsoluteFill style={{
        background: `radial-gradient(circle at 50% 50%, rgba(61,240,178,${0.07 * vig}) 0%, rgba(0,0,0,0) 62%)`,
      }} />
      {children}
    </AbsoluteFill>
  );
};

/* ── 진입 킥: 섹션이 바뀔 때마다 걸리는 공통 펀치 ─────────────── */
export const useKick = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 14, stiffness: 200, mass: 0.55 } });
  return {
    scale: interpolate(pop, [0, 1], [1.06, 1]),
    flash: interpolate(frame, [0, 6], [0.5, 0], { extrapolateRight: 'clamp' }),
  };
};

/* 화면 전체에 얹는 민트/화이트 플래시 */
export const Flash: React.FC<{ v: number }> = ({ v }) => (
  <>
    <AbsoluteFill style={{ background: MINT, opacity: v * 0.3, pointerEvents: 'none' }} />
    <AbsoluteFill style={{ background: '#fff', opacity: v * 0.22, pointerEvents: 'none' }} />
  </>
);

/* 상단 진행바 */
export const ProgressBar: React.FC<{ p: number; color?: string }> = ({ p, color = MINT }) => (
  <div style={{
    position: 'absolute', top: 0, left: 0, height: 5,
    width: `${p * 100}%`, background: color, opacity: 0.85,
    boxShadow: `0 0 18px ${color}88`,
  }} />
);
