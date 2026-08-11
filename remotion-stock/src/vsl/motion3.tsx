/**
 * S4 전용 모션 — "빌드 몽타주"와 "원리 도식".
 *
 * 핵심 판단: S4의 주장은 "이걸 내가 직접 만들었다"인데, **말로 하면 허풍이고 화면으로
 * 보여주면 증거**다. 그래서 재료를 지어내지 않고 repo에서 실제로 뽑았다
 * (buildStats.json — 커밋 2,067개 / 34일 / 파일 779개 / 새벽 커밋 22%).
 * 커밋 메시지도 진짜 문장이라 스치듯 읽혀도 거짓말이 아니다.
 */

import React from 'react';
import {
  AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, Easing, random,
} from 'remotion';
import { MINT, BG, FONT } from './motion';
import stats from './buildStats.json';

export const BUILD = stats as {
  total: number; first: string; last: string; days: number; files: number;
  byHour: number[]; nightPct: number; topDay: [string, number]; msgs: string[];
  recent?: { d: string; s: string }[];
};

/* ── CommitRain: 진짜 커밋 메시지가 폭포처럼 흐른다 ───────────────
   가짜 로그를 만들지 않는다 — 흐르는 문장이 실제 작업 기록이라 '많이 했다'가 사실이 된다. */
export const CommitRain: React.FC<{ cols?: number; speed?: number; dim?: number }> = ({
  cols = 4, speed = 1, dim = 0.55,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const colW = 1920 / cols;
  return (
    <AbsoluteFill style={{ background: BG, overflow: 'hidden' }}>
      {Array.from({ length: cols }).map((_, c) => {
        const items = BUILD.msgs.filter((_, i) => i % cols === c).slice(0, 14);
        const drift = interpolate(frame, [0, durationInFrames], [0, -900 * speed * (0.8 + (c % 3) * 0.18)]);
        return (
          <div key={c} style={{
            position: 'absolute', left: c * colW, top: 0, width: colW - 18,
            transform: `translateY(${200 + drift}px)`,
            display: 'flex', flexDirection: 'column', gap: 12, padding: '0 12px',
          }}>
            {items.map((m, i) => (
              <div key={i} style={{
                fontFamily: "'Space Mono','Roboto Mono',monospace", fontSize: 19,
                color: i % 5 === 0 ? MINT : '#9fb7ad', lineHeight: 1.4,
                background: 'rgba(61,240,178,0.05)', border: '1px solid rgba(61,240,178,0.14)',
                borderRadius: 8, padding: '9px 12px', whiteSpace: 'nowrap',
                overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                <span style={{ color: MINT, opacity: 0.55 }}>✚ </span>{m}
              </div>
            ))}
          </div>
        );
      })}
      <AbsoluteFill style={{ background: `rgba(3,10,7,${dim})` }} />
    </AbsoluteFill>
  );
};

/* 큰 통계 숫자 — 카운트업 후 착지 */
export const StatBig: React.FC<{
  to: number; label: string; sub?: string; suffix?: string; hold?: number;
}> = ({ to, label, sub, suffix = '', hold = 24 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = interpolate(frame, [0, hold], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const land = frame - hold;
  const pop = spring({ frame: land, fps, config: { damping: 10, stiffness: 260, mass: 0.4 } });
  const sc = land >= 0 ? interpolate(pop, [0, 1], [1.16, 1]) : 1;
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
      <div style={{ textAlign: 'center', transform: `scale(${sc})` }}>
        <div style={{ fontFamily: FONT, fontSize: 34, color: '#ffffffaa', fontWeight: 800, marginBottom: -6 }}>{label}</div>
        <div style={{
          fontFamily: "'Space Mono',monospace", fontSize: 220, fontWeight: 700, color: MINT,
          textShadow: `0 0 80px ${MINT}55`, lineHeight: 1.02, letterSpacing: '-0.03em',
        }}>{Math.round(to * p).toLocaleString()}{suffix}</div>
        {sub ? <div style={{ fontFamily: FONT, fontSize: 38, color: '#fff', fontWeight: 800, marginTop: -4 }}>{sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

/* ── NightHeatmap: 24시간 커밋 분포 — 새벽에 불이 켜진다 ─────────
   "지금도 매일 진화하고 있습니다"의 증거. 막대가 시간순으로 차오르고
   0~6시 구간이 붉게 강조된다(잠 안 자고 만들었다는 사실을 굳이 말로 안 해도 된다). */
export const NightHeatmap: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const max = Math.max(...BUILD.byHour, 1);
  return (
    <AbsoluteFill style={{ background: BG, alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 1500 }}>
        <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 40, color: '#fff', marginBottom: 22 }}>
          시간대별 커밋 — <span style={{ color: MINT }}>{BUILD.first} ~ {BUILD.last}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, height: 460 }}>
          {BUILD.byHour.map((v, h) => {
            const p = spring({ frame: frame - h * 0.62, fps, config: { damping: 15, stiffness: 210 } });
            const night = h < 7;
            return (
              <div key={h} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <div style={{ fontFamily: "'Space Mono',monospace", fontSize: 17, color: night ? '#FF8A7D' : '#8aa39a', opacity: p }}>{v}</div>
                <div style={{
                  width: '100%', height: (v / max) * 400 * p, borderRadius: 6,
                  background: night ? "linear-gradient(180deg,#FF7A6B,#8A2E26)" : `linear-gradient(180deg,${MINT},#0E4A38)`,
                  boxShadow: night ? '0 0 26px #FF7A6B55' : `0 0 22px ${MINT}33`,
                }} />
                <div style={{ fontFamily: "'Space Mono',monospace", fontSize: 19, color: night ? '#FF8A7D' : '#7f948c', fontWeight: 700 }}>{h}</div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 18, fontFamily: FONT, fontSize: 32, color: '#ffffffcc', fontWeight: 700 }}>
          새벽 0~6시 커밋 <span style={{ color: '#FF8A7D', fontWeight: 900 }}>{BUILD.nightPct}%</span>
          <span style={{ opacity: 0.6 }}> · 최다 하루 {BUILD.topDay[1]}건</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ── FlowDiagram: 원리 4단계 — 촬영 없이 만드는 부분 ─────────────
   activeAt으로 단계가 하나씩 켜진다. 켜진 단계만 민트, 나머지는 눌러 둔다. */
export const FLOW = [
  { t: '지금 터지는 영상', s: '5개 플랫폼 실시간 랭킹' },
  { t: '동일 원본 수집', s: '같은 소스 자동으로 모음' },
  { t: '대본 새로 쓰기', s: '내 제품에 맞게 S급으로' },
  { t: '장면에 딱 배치', s: '문장↔컷 자동 매칭' },
];

export const FlowDiagram: React.FC<{ activeAt: number[]; allOn?: boolean }> = ({ activeAt, allOn }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: BG, alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {FLOW.map((f, i) => {
          const at = Math.round((activeAt[i] ?? i * 0.9) * fps);
          const on = allOn || frame >= at;
          const p = on ? spring({ frame: frame - at, fps, config: { damping: 14, stiffness: 190 } }) : 0;
          return (
            <React.Fragment key={i}>
              <div style={{
                width: 356, minHeight: 250, borderRadius: 20, padding: '26px 24px',
                background: on ? 'rgba(61,240,178,0.10)' : 'rgba(255,255,255,0.03)',
                border: `2px solid ${on ? MINT + '77' : '#ffffff14'}`,
                transform: `translateY(${interpolate(p, [0, 1], [40, 0])}px) scale(${interpolate(p, [0, 1], [0.9, 1])})`,
                opacity: on ? 0.35 + p * 0.65 : 0.28,
                boxShadow: on ? `0 0 46px ${MINT}22` : undefined,
              }}>
                <div style={{
                  width: 46, height: 46, borderRadius: 23, background: on ? MINT : '#ffffff22',
                  color: '#05130E', fontFamily: FONT, fontWeight: 900, fontSize: 24,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16,
                }}>{i + 1}</div>
                <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 40, color: '#fff', lineHeight: 1.24 }}>{f.t}</div>
                <div style={{ fontFamily: FONT, fontWeight: 700, fontSize: 25, color: on ? MINT : '#ffffff55', marginTop: 12 }}>{f.s}</div>
              </div>
              {i < FLOW.length - 1 ? (
                <div style={{
                  fontSize: 46, color: (allOn || frame >= Math.round((activeAt[i + 1] ?? 0) * fps)) ? MINT : '#ffffff22',
                  fontWeight: 900, padding: '0 2px',
                }}>›</div>
              ) : null}
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* 제품명 리빌 — "그렇게 나온 게 이겁니다… 숏템메이커" */
export const BrandReveal: React.FC<{ name?: string }> = ({ name = '숏템메이커' }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 16, stiffness: 130, mass: 0.9 } });
  const glow = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ background: BG, alignItems: 'center', justifyContent: 'center' }}>
      <AbsoluteFill style={{
        background: `radial-gradient(circle at 50% 50%, ${MINT}${Math.round(glow * 40).toString(16).padStart(2, '0')} 0%, rgba(0,0,0,0) 62%)`,
      }} />
      <div style={{
        fontFamily: FONT, fontWeight: 900, fontSize: 168, color: '#fff',
        letterSpacing: '-0.02em',
        transform: `scale(${interpolate(p, [0, 1], [0.82, 1])})`, opacity: p,
        textShadow: `0 0 70px ${MINT}66`,
      }}>
        {name}<span style={{ color: MINT }}>.</span>
      </div>
      <div style={{
        marginTop: 18, fontFamily: FONT, fontWeight: 800, fontSize: 34, color: MINT,
        opacity: interpolate(frame, [14, 30], [0, 1], { extrapolateRight: 'clamp' }),
      }}>
        {BUILD.days}일 · 커밋 {BUILD.total.toLocaleString()}개 · 파일 {BUILD.files}개
      </div>
    </AbsoluteFill>
  );
};

/* 화면녹화 재생(배속) — S4는 S2와 달리 탈색하지 않는다(우리 편 화면이다) */
export const Screen4: React.FC<{ src: string; at?: number; speed?: number; dim?: number }> = ({
  src, at = 0, speed = 1.4, dim = 0.28,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const s = interpolate(frame, [0, durationInFrames], [1.04, 1.1]);
  const { OffthreadVideo, staticFile } = require('remotion');
  return (
    <AbsoluteFill style={{ background: BG, overflow: 'hidden' }}>
      <OffthreadVideo
        src={staticFile(src)} trimBefore={Math.round(at * fps)} playbackRate={speed} volume={0}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${s})` }}
      />
      <AbsoluteFill style={{ background: `rgba(4,12,9,${dim})` }} />
    </AbsoluteFill>
  );
};
