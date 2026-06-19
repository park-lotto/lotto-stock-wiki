/**
 * KK_S1_L30 — S1 훅 씬 (LIFE 3.0 × 역동적 오버레이)
 *
 * 838프레임 = 27.93s @ 30fps
 * Whisper 자막 타임스탬프 기반 정확한 싱크
 *
 * [0.0→4.8]   f0→f144   : AI를 GPT나 Gemini 안 씁니다
 * [5.0→6.5]   f150→f195 : 클로드로 갈아탔어요
 * [6.9→8.9]   f207→f267 : 미국 앱스토어 난리
 * [8.9→13.8]  f267→f414 : 자동화 기능까지 특화
 * [14.3→18.5] f429→f555 : 카톡 자동화 설정
 * [18.5→20.7] f555→f621 : 아침 브리핑 자동 수신
 * [21.1→22.4] f633→f672 : 복잡한 코딩 없음
 * [22.8→25.6] f684→f768 : 프롬프트 고정 댓글 공유
 * [25.6→27.5] f768→f825 : 영상 끝까지 집중
 *
 * Phase 1 f0~225   : AI 앱 순위 (#1 카운트다운)
 * Phase 2 f205~445 : 자동화 특화 바차트 + 체크리스트
 * Phase 3 f415~660 : 카카오 브리핑 라이브 데모
 * Phase 4 f640~838 : CTA (코딩없음 · 프롬프트 공유)
 */

import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import { L30C, L30G, L30V, cardBase, hudLabel } from '../life30/L30_constants';
import { L30_Leaderboard, LeaderboardRow } from '../life30/L30_Leaderboard';
import {
  L30_MetricCard,
  L30_TimestampCard,
  L30_CountryRankCard,
} from '../life30/L30_DataCard';

export const KK_S1_L30_FRAMES = 838;

// ── 유틸 ──────────────────────────────────────────────────────────
const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (f: number, from: number, damping = 9, stiffness = 270, mass = 0.7) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping, stiffness, mass } });

// sin 파동 글로우 (0~1)
const pulse = (f: number, speed = 0.10) => Math.sin(f * speed) * 0.5 + 0.5;

// ── 위상 전환: 라임 플래시 ────────────────────────────────────────
const FlashFrame: React.FC<{ f: number; at: number }> = ({ f, at }) => {
  const op = ci(f, at, at + 6) * ci(f, at + 5, at + 20, 1, 0);
  if (op <= 0.01) return null;
  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: 'rgba(170,255,0,0.10)',
      opacity: op, pointerEvents: 'none', zIndex: 55,
    }} />
  );
};

// ── 전체화면 스캔라인 sweeper ─────────────────────────────────────
const ScanSweep: React.FC<{ f: number; at: number; dur?: number }> = ({
  f, at, dur = 20,
}) => {
  const p = ci(f, at, at + dur);
  if (p <= 0 || p >= 1) return null;
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0,
      top: `${p * 100}%`, height: 2,
      background: `linear-gradient(to right, transparent 0%, ${L30C.lime} 20%, ${L30C.lime} 80%, transparent 100%)`,
      boxShadow: `0 0 12px ${L30C.lime}, 0 0 30px rgba(170,255,0,0.35)`,
      pointerEvents: 'none', zIndex: 60,
    }} />
  );
};

// ── 가로 바 차트 (성장 애니메이션) ───────────────────────────────
interface BarRow { label: string; pct: number; highlight?: boolean; delay: number }
const BarChart: React.FC<{
  f: number; showAt: number; title: string; rows: BarRow[]; width?: number;
}> = ({ f, showAt, title, rows, width = 340 }) => {
  const containerSp = sp(f, showAt, 10, 280, 0.8);
  const containerX = interpolate(containerSp, [0, 1], [-50, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const containerOp = ci(f, showAt, showAt + 18);

  return (
    <div style={{
      ...cardBase, width,
      opacity: containerOp,
      transform: `translateX(${containerX}px)`,
    }}>
      <div style={{ padding: '12px 18px 8px', borderBottom: `1px solid ${L30C.limeBorder}`, ...hudLabel }}>
        {title}
      </div>
      {rows.map((row, i) => {
        const rowStart = showAt + row.delay;
        const barPct = ci(f, rowStart + 8, rowStart + 36, 0, row.pct);
        const rowOp  = ci(f, rowStart, rowStart + 15);
        const glowSz = row.highlight ? 6 + pulse(f, 0.08) * 8 : 0;
        return (
          <div key={i} style={{ padding: '10px 18px', opacity: rowOp }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
              <span style={{
                fontFamily: L30C.fontMono, fontSize: 11, letterSpacing: '1.5px',
                color: row.highlight ? L30C.lime : L30C.textDim,
                textShadow: row.highlight ? L30G.lime.text : undefined,
              }}>
                {row.label}
              </span>
              <span style={{
                fontFamily: L30C.fontMono, fontSize: 11,
                color: row.highlight ? L30C.lime : L30C.textDim,
                textShadow: row.highlight ? L30G.lime.text : undefined,
              }}>
                {Math.round(barPct)}%
              </span>
            </div>
            <div style={{
              height: 6, background: 'rgba(255,255,255,0.07)',
              borderRadius: 3, overflow: 'hidden',
            }}>
              <div style={{
                width: `${barPct}%`, height: '100%', borderRadius: 3,
                background: row.highlight ? L30C.lime : 'rgba(255,255,255,0.28)',
                boxShadow: row.highlight ? `0 0 ${glowSz}px ${L30C.lime}` : undefined,
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ── CLAUDE #1 카운트다운 (9→5→3→1) ──────────────────────────────
const CountRoll: React.FC<{ f: number; showAt: number }> = ({ f, showAt }) => {
  const progress = ci(f, showAt, showAt + 22);
  const nums = [9, 7, 5, 3, 2, 1];
  const idx = Math.floor(progress * (nums.length - 1));
  const displayNum = progress >= 1 ? 1 : nums[Math.min(idx, nums.length - 1)];
  const locked = progress >= 1;
  const glowSize = locked ? 12 + pulse(f, 0.09) * 18 : 0;

  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
      <span style={{
        fontFamily: L30C.fontMono, fontSize: 14,
        color: L30C.limeDim, letterSpacing: '3px',
      }}>#</span>
      <span style={{
        fontFamily: L30C.fontMain, fontSize: 78, fontWeight: 900,
        color: L30C.lime, lineHeight: 1,
        textShadow: `0 0 ${glowSize}px ${L30C.lime}, 0 0 ${glowSize * 2}px rgba(170,255,0,0.25)`,
      }}>
        {displayNum}
      </span>
    </div>
  );
};

// ── 자막 (Whisper 타임스탬프 정확 싱크) ──────────────────────────
const SUBS = [
  { from: 0,   to: 144,  text: 'AI를 GPT나 Gemini 안 씁니다',           accent: 'GPT나 Gemini' },
  { from: 150, to: 195,  text: '대부분 클로드로 갈아탔어요',              accent: '클로드' },
  { from: 207, to: 267,  text: '미국 앱스토어에서 이미 난리가 났는데',    accent: '난리' },
  { from: 267, to: 414,  text: '자동화 기능까지 특화되어서 그렇더라고요', accent: '자동화' },
  { from: 429, to: 555,  text: '어젯밤 클로드 자동화 설정만 해뒀어서',   accent: '클로드 자동화' },
  { from: 555, to: 621,  text: '아침 브리핑으로 받을 수 있었습니다',      accent: '브리핑' },
  { from: 633, to: 672,  text: '복잡한 코딩 전혀 없고요',                 accent: '코딩 전혀' },
  { from: 684, to: 768,  text: '프롬프트도 고정 댓글로 다 퍼드릴 테니까', accent: '고정 댓글' },
  { from: 768, to: 825,  text: '오늘 영상 끝까지만 집중해 주세요 👇',    accent: '끝까지' },
];

const SubtitleBar: React.FC<{ f: number }> = ({ f }) => {
  const sub = SUBS.find(s => f >= s.from && f < s.to);
  if (!sub) return null;

  const fadeOp = ci(f, sub.from, sub.from + 8);
  const parts   = sub.accent ? sub.text.split(sub.accent) : [sub.text];

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0, height: '17%',
      background: 'linear-gradient(to top, rgba(0,0,0,0.94) 0%, rgba(0,0,0,0.58) 55%, transparent 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 40,
    }}>
      <div key={sub.from} style={{
        fontFamily: L30C.fontMain, fontSize: 44, fontWeight: 700,
        color: '#FFFFFF', textAlign: 'center',
        paddingInline: 80, lineHeight: 1.3,
        textShadow: '0 2px 18px rgba(0,0,0,1)',
        opacity: fadeOp,
      }}>
        {parts.map((part, i, arr) => (
          <React.Fragment key={i}>
            {part}
            {i < arr.length - 1 && (
              <span style={{ color: L30C.lime, textShadow: L30G.lime.text }}>
                {sub.accent}
              </span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};

// ── HUD 챕터 레이블 ───────────────────────────────────────────────
const ChapterHUD: React.FC<{
  f: number; showAt: number; hideAt: number; chapter: string; title: string;
}> = ({ f, showAt, hideAt, chapter, title }) => {
  if (f < showAt - 5 || f > hideAt + 5) return null;
  const op = Math.min(ci(f, showAt, showAt + 14), ci(f, hideAt - 14, hideAt, 1, 0));
  const dotGlow = 8 + pulse(f, 0.12) * 10;
  return (
    <div style={{
      position: 'absolute', top: L30V.PAD, left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex', alignItems: 'center', gap: 10,
      opacity: op, zIndex: 45,
    }}>
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        background: L30C.lime,
        boxShadow: `0 0 ${dotGlow}px ${L30C.lime}`,
        flexShrink: 0,
      }} />
      <span style={{ ...hudLabel, opacity: 0.65 }}>{chapter}</span>
      <span style={{ ...hudLabel, color: L30C.white, fontSize: 13, letterSpacing: '2px' }}>{title}</span>
    </div>
  );
};

// ── AI 랭킹 데이터 ────────────────────────────────────────────────
const AI_RANKS: LeaderboardRow[] = [
  { rank: '01', flag: '🤖', country: 'CLAUDE',     value: '#1', highlight: true },
  { rank: '02', flag: '💬', country: 'CHATGPT',    value: '#2' },
  { rank: '03', flag: '💎', country: 'GEMINI',     value: '#3' },
  { rank: '04', flag: '🔍', country: 'PERPLEXITY', value: '#4' },
];

const SHARE_BARS: BarRow[] = [
  { label: 'CLAUDE',  pct: 100, highlight: true, delay: 4  },
  { label: 'CHATGPT', pct: 42,                   delay: 18 },
  { label: 'GEMINI',  pct: 28,                   delay: 32 },
];

const FEATURE_ITEMS = [
  { label: '웹 리서치 자동화',  delay: 0  },
  { label: '카톡 자동 발송',     delay: 18 },
  { label: 'MCP 외부 연결',      delay: 36 },
  { label: '스케줄 자동 실행',   delay: 54 },
];

// ── 메인 컴포넌트 ─────────────────────────────────────────────────
export const KK_S1_L30: React.FC = () => {
  const f = useCurrentFrame();

  // 페이즈 가시성 (부드러운 크로스페이드)
  const p1 = Math.min(ci(f, 0, 12),   ci(f, 215, 228, 1, 0));
  const p2 = Math.min(ci(f, 205, 215), ci(f, 435, 448, 1, 0));
  const p3 = Math.min(ci(f, 415, 425), ci(f, 648, 660, 1, 0));
  const p4 = ci(f, 638, 650);

  const vigOp = Math.max(p1, p2, p3, p4);

  return (
    <AbsoluteFill style={{ background: '#000', overflow: 'hidden', fontFamily: L30C.fontMain }}>

      {/* ── 배경 영상 ────────────────────────────────────────── */}
      <OffthreadVideo
        src={staticFile('kakao/s1scene.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* ── 좌우 비네트 (카드 가독성) ───────────────────────── */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', opacity: vigOp,
        background: `
          linear-gradient(to right, rgba(0,0,0,0.86) 0%, rgba(0,0,0,0.52) 28%, transparent 44%),
          linear-gradient(to left,  rgba(0,0,0,0.86) 0%, rgba(0,0,0,0.52) 28%, transparent 44%)
        `,
      }} />

      {/* ── 상단 비네트 (HUD 영역) ──────────────────────────── */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.72) 0%, transparent 16%)',
      }} />

      {/* ── 위상 전환 플래시 ─────────────────────────────────── */}
      <FlashFrame f={f} at={144} />
      <FlashFrame f={f} at={205} />
      <FlashFrame f={f} at={415} />
      <FlashFrame f={f} at={638} />

      {/* ── 스캔라인 sweeper ─────────────────────────────────── */}
      <ScanSweep f={f} at={0}   dur={22} />
      <ScanSweep f={f} at={205} dur={20} />
      <ScanSweep f={f} at={415} dur={20} />
      <ScanSweep f={f} at={638} dur={20} />

      {/* ── HUD 챕터 ─────────────────────────────────────────── */}
      <ChapterHUD f={f} showAt={0}   hideAt={225} chapter="S1 · HOOK" title="CLAUDE 혁명" />
      <ChapterHUD f={f} showAt={205} hideAt={445} chapter="S1 · FEAT" title="자동화 특화" />
      <ChapterHUD f={f} showAt={415} hideAt={660} chapter="S1 · DEMO" title="아침 브리핑" />
      <ChapterHUD f={f} showAt={638} hideAt={838} chapter="S1 · CTA"  title="딱 10분" />

      {/* ══════════════════════════════════════════════════════
          PHASE 1  f0~225  : AI 앱 순위 + CLAUDE #1 카운트다운
      ══════════════════════════════════════════════════════ */}
      <div style={{ opacity: p1 }}>
        {/* LEFT: 리더보드 */}
        <div style={{ position: 'absolute', left: L30V.PAD, top: 108, zIndex: 30 }}>
          <L30_Leaderboard
            showAt={0}
            title="APP STORE · AI"
            subtitle="(US 2025.06)"
            rows={AI_RANKS}
            width={380}
          />
        </div>

        {/* RIGHT: #1 카운트다운 카드 */}
        <div style={{
          position: 'absolute', right: L30V.PAD, top: 130, zIndex: 30,
          opacity: ci(f, 8, 24),
          transform: `
            translateX(${interpolate(sp(f, 8, 8, 290, 0.7), [0, 1], [80, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })}px)
            scale(${interpolate(sp(f, 8, 6, 290, 0.7), [0, 1], [0.78, 1.0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })})
          `,
        }}>
          <div style={{ ...cardBase, width: 300, padding: '18px 22px' }}>
            <div style={{ ...hudLabel, marginBottom: 12 }}>PRODUCTIVITY · RANKING</div>
            <CountRoll f={f} showAt={12} />
            <div style={{
              fontFamily: L30C.fontMono, fontSize: 11, color: L30C.textDim,
              letterSpacing: '1.5px', marginTop: 8,
            }}>
              클로드 · 앱스토어 1위
            </div>
            {/* 슬라이딩 언더라인 */}
            <div style={{
              height: 2, marginTop: 16, borderRadius: 1,
              background: L30C.lime,
              width: `${ci(f, 20, 50) * 100}%`,
              boxShadow: `0 0 ${6 + pulse(f, 0.12) * 8}px ${L30C.lime}`,
            }} />
          </div>

          {/* → GPT·Gemini 추월 배지 */}
          <div style={{
            marginTop: 14,
            opacity: ci(f, 38, 54),
            transform: `translateX(${interpolate(ci(f, 38, 54), [0, 1], [28, 0])}px)`,
          }}>
            <div style={{
              ...cardBase,
              padding: '8px 16px',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span style={{
                fontFamily: L30C.fontMono, fontSize: 11,
                color: L30C.lime, textShadow: L30G.lime.text, letterSpacing: '1.5px',
              }}>→</span>
              <span style={{
                fontFamily: L30C.fontMono, fontSize: 11,
                color: L30C.white, letterSpacing: '1px',
              }}>GPT · GEMINI 추월</span>
            </div>
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          PHASE 2  f205~445  : 자동화 특화 체크리스트 + 바차트
      ══════════════════════════════════════════════════════ */}
      <div style={{ opacity: p2 }}>
        {/* LEFT: 자동화 기능 체크리스트 */}
        <div style={{
          position: 'absolute', left: L30V.PAD, top: 108, zIndex: 30,
          opacity: ci(f, 205, 222),
          transform: `translateX(${interpolate(
            sp(f, 205, 10, 270, 0.8), [0, 1], [-48, 0],
            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
          )}px)`,
        }}>
          <div style={{ ...cardBase, width: 360 }}>
            <div style={{ padding: '13px 20px', borderBottom: `1px solid ${L30C.limeBorder}`, ...hudLabel }}>
              자동화 · 특화 기능
            </div>
            {FEATURE_ITEMS.map((feat, i) => {
              const showAt = 215 + feat.delay;
              const itemOp = ci(f, showAt, showAt + 18);
              const itemX  = interpolate(
                sp(f, showAt, 10, 240, 0.8), [0, 1], [-20, 0],
                { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
              );
              const ready  = itemOp >= 0.95;
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '12px 20px',
                  borderBottom: i < FEATURE_ITEMS.length - 1
                    ? 'rgba(170,255,0,0.07) solid 1px' : 'none',
                  opacity: itemOp,
                  transform: `translateX(${itemX}px)`,
                }}>
                  <span style={{
                    fontFamily: L30C.fontMono, fontSize: 13,
                    color: L30C.lime,
                    textShadow: ready ? `0 0 ${4 + pulse(f, 0.10) * 8}px ${L30C.lime}` : undefined,
                    flexShrink: 0, width: 16,
                  }}>▶</span>
                  <span style={{
                    fontFamily: L30C.fontMain, fontSize: 14, fontWeight: 600,
                    color: L30C.white, letterSpacing: '0.3px', flex: 1,
                  }}>
                    {feat.label}
                  </span>
                  {ready && (
                    <span style={{
                      fontFamily: L30C.fontMono, fontSize: 10,
                      color: L30C.lime, letterSpacing: '1.5px',
                      opacity: ci(f, showAt + 20, showAt + 34),
                    }}>✓ ON</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT: 바차트 + 자동화율 */}
        <div style={{ position: 'absolute', right: L30V.PAD, top: 130, zIndex: 30 }}>
          <BarChart
            f={f} showAt={215}
            title="AI 도구 점유율 (주식투자자)"
            rows={SHARE_BARS}
            width={330}
          />
          <div style={{ marginTop: 14 }}>
            <L30_MetricCard
              showAt={285}
              topLabel="AUTOMATION · LEVEL"
              value="100 %"
              subLabel="채널 운영 자동화율"
              width={330}
              slideFrom="right"
            />
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          PHASE 3  f415~660  : 카카오 브리핑 라이브 데모
      ══════════════════════════════════════════════════════ */}
      <div style={{ opacity: p3 }}>
        {/* LEFT: 타임스탬프 카드 */}
        <div style={{ position: 'absolute', left: L30V.PAD, top: 108, zIndex: 30 }}>
          <L30_TimestampCard
            showAt={415}
            date="08 : 00"
            subLabel="DAILY · BRIEFING · LIVE"
            width={340}
          />
        </div>

        {/* LEFT: 카카오 메시지 미리보기 */}
        <div style={{
          position: 'absolute', left: L30V.PAD, top: 308, zIndex: 30,
          opacity: ci(f, 444, 460),
          transform: `translateX(${interpolate(
            sp(f, 444, 10, 255, 0.8), [0, 1], [-36, 0],
            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
          )}px)`,
        }}>
          <div style={{ ...cardBase, width: 340, padding: '14px 18px' }}>
            <div style={{ ...hudLabel, marginBottom: 12 }}>카카오 · 주식 AI 브리핑</div>
            {[
              { icon: '📊', text: '코스피 2,856 (+0.3%)' },
              { icon: '🔥', text: '주도섹터: 반도체 / 조선' },
              { icon: '⭐', text: '관심: 삼성전기 · HD현대' },
            ].map((msg, i) => {
              const mStart = 454 + i * 20;
              const mOp    = ci(f, mStart, mStart + 16);
              const mY     = interpolate(mOp, [0, 1], [8, 0]);
              return (
                <div key={i} style={{
                  display: 'flex', gap: 8, fontSize: 13,
                  color: L30C.white, lineHeight: 1.8,
                  opacity: mOp, transform: `translateY(${mY}px)`,
                }}>
                  <span>{msg.icon}</span><span>{msg.text}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT: 브리핑 메트릭 */}
        <div style={{ position: 'absolute', right: L30V.PAD, top: 140, zIndex: 30 }}>
          <L30_MetricCard
            showAt={425}
            topLabel="BRIEFING · TIME"
            value="30 초"
            subLabel="AI 리서치 완료 시간"
            width={320}
            slideFrom="right"
          />
          <div style={{ marginTop: 14 }}>
            <L30_CountryRankCard
              showAt={458}
              rank="01"
              flag="🤖"
              country="CLAUDE"
              tag="AI BRIEFING"
              market="카카오 자동 발송"
              width={320}
              delay={0}
            />
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          PHASE 4  f638~838  : CTA
      ══════════════════════════════════════════════════════ */}
      <div style={{ opacity: p4 }}>
        {/* LEFT: 설정 체크리스트 */}
        <div style={{ position: 'absolute', left: L30V.PAD, top: 108, zIndex: 30 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {[
              { label: 'Claude 설치',       delay: 0,  highlight: false },
              { label: 'PlayMCP 연결',       delay: 14, highlight: false },
              { label: '프롬프트 붙여넣기',  delay: 28, highlight: false },
              { label: '스케줄 자동화',      delay: 42, highlight: false },
              { label: '완료 ✓',            delay: 56, highlight: true  },
            ].map((item, i) => {
              const showAt = 648 + item.delay;
              const iOp    = ci(f, showAt, showAt + 16);
              const iX     = interpolate(
                sp(f, showAt, 10, 250, 0.8), [0, 1], [-24, 0],
                { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
              );
              const glowSz = item.highlight ? 4 + pulse(f, 0.10) * 14 : 0;
              return (
                <div key={i} style={{
                  ...cardBase,
                  padding: '10px 16px',
                  display: 'flex', alignItems: 'center', gap: 10,
                  opacity: iOp,
                  transform: `translateX(${iX}px)`,
                  background: item.highlight ? 'rgba(170,255,0,0.12)' : L30C.bgCard,
                  boxShadow: item.highlight ? `0 0 ${glowSz}px rgba(170,255,0,0.4)` : undefined,
                }}>
                  <span style={{
                    fontFamily: L30C.fontMono, fontSize: 10, letterSpacing: '2px',
                    color: item.highlight ? L30C.lime : L30C.limeDim,
                    minWidth: 24, textAlign: 'center',
                    textShadow: item.highlight ? L30G.lime.text : undefined,
                  }}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span style={{
                    fontFamily: L30C.fontMain, fontSize: 14, fontWeight: 600,
                    color: item.highlight ? L30C.lime : L30C.white,
                    textShadow: item.highlight ? L30G.lime.text : undefined,
                  }}>
                    {item.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* CENTER: "딱 10분" 임팩트 텍스트 */}
        <div style={{
          position: 'absolute',
          bottom: '22%', left: '50%',
          transform: `translateX(-50%) scale(${interpolate(
            sp(f, 638, 8, 260, 0.8), [0, 1], [0.80, 1.0],
            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
          )})`,
          opacity: ci(f, 638, 655),
          textAlign: 'center', zIndex: 30, width: 480,
        }}>
          <div style={{ ...hudLabel, letterSpacing: '5px', marginBottom: 10 }}>
            세팅 소요 시간
          </div>
          <div style={{
            fontFamily: L30C.fontMain,
            fontSize: 100, fontWeight: 900,
            color: L30C.lime, lineHeight: 1, letterSpacing: '-2px',
            textShadow: `0 0 ${10 + pulse(f, 0.09) * 24}px ${L30C.lime}, 0 0 60px rgba(170,255,0,0.22)`,
          }}>
            딱 10분
          </div>
          <div style={{
            fontFamily: L30C.fontMain, fontSize: 22, fontWeight: 500,
            color: L30C.textDim, marginTop: 14,
            opacity: ci(f, 662, 678),
          }}>
            코딩 없음 · 프롬프트 전부 공유
          </div>
        </div>

        {/* RIGHT: 프롬프트 공유 배지 */}
        <div style={{ position: 'absolute', right: L30V.PAD, top: 195, zIndex: 30 }}>
          <L30_MetricCard
            showAt={658}
            topLabel="고정 댓글 확인"
            value="FREE"
            subLabel="프롬프트 전체 공유"
            width={300}
            slideFrom="right"
          />
        </div>
      </div>

      {/* ── 자막 바 ─────────────────────────────────────────────── */}
      <SubtitleBar f={f} />

      {/* ── 워터마크 ─────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', bottom: 22, right: 30,
        fontFamily: L30C.fontMono, fontSize: 10,
        letterSpacing: '3px', color: L30C.lime,
        textTransform: 'uppercase', opacity: 0.36,
        zIndex: 50,
      }}>
        STOCKBRAIN
      </div>

    </AbsoluteFill>
  );
};
