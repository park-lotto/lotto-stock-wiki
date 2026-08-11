/**
 * S6~S10 공용 모션 어휘 — 촬영본이 하나도 없는 구간이라 **화면을 전부 만들어야** 한다.
 *
 * 설계 원칙 3개
 *  1) 후반부는 '보여줄 게 없어서 텍스트만 띄우는' 함정에 빠지기 쉽다. 그래서 각 씬마다
 *     **주장을 그림으로 바꾼 장치**를 하나씩 둔다(로드맵/계산기/체크리스트/카드).
 *  2) 가격 구간은 형용사도 장식도 금지다(대본 지시). 숫자를 벌거벗겨 두고 **정적**으로만
 *     무게를 준다 — 화려하게 꾸미는 순간 "파는 사람" 냄새가 나고 신뢰가 깎인다.
 *  3) 색: 민트(우리)와 붉은(남·비용)을 계속 대비시킨다. S2에서 세운 규칙을 끝까지 지킨다.
 */

import React from 'react';
import {
  AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, Easing,
} from 'remotion';
import { MINT, BG, FONT } from './motion';
import { RED } from './motion2';

/* ── 공통 배경: 아주 느리게 도는 민트 오라 ─────────────────────
   후반부는 정지 화면이 많다. 배경이 미세하게 살아 있어야 '멈춘 슬라이드'로 안 보인다. */
export const Aura: React.FC<{ tone?: string; strength?: number }> = ({
  tone = MINT, strength = 0.10,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const x = 50 + Math.sin(frame / 90) * 12;
  const y = 52 + Math.cos(frame / 110) * 10;
  const s = interpolate(frame, [0, durationInFrames], [1, 1.12]);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <AbsoluteFill style={{
        background: `radial-gradient(circle at ${x}% ${y}%, ${tone}${Math.round(strength * 255).toString(16).padStart(2, '0')} 0%, rgba(0,0,0,0) 58%)`,
        transform: `scale(${s})`,
      }} />
    </AbsoluteFill>
  );
};

/* ── S6: 매일 갱신되는 제품 — 최근 커밋 날짜가 흘러간다 ─────────
   "어제 없던 기능이 오늘 생깁니다"를 말로만 두면 흔한 광고 문구다.
   실제 날짜가 지나가면 확인 가능한 사실이 된다. */
export const DailyStream: React.FC<{ items: { d: string; s: string }[] }> = ({ items }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 1420, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map((it, i) => {
          const p = spring({ frame: frame - i * 3.4, fps, config: { damping: 15, stiffness: 200 } });
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 20,
              padding: '15px 24px', borderRadius: 14,
              background: 'rgba(61,240,178,0.07)', border: `1px solid ${MINT}33`,
              transform: `translateX(${interpolate(p, [0, 1], [-60, 0])}px)`, opacity: p,
            }}>
              <div style={{
                fontFamily: "'Space Mono',monospace", fontSize: 26, color: MINT, fontWeight: 700,
                minWidth: 148,
              }}>{it.d}</div>
              <div style={{
                fontFamily: FONT, fontSize: 30, color: '#fff', fontWeight: 700,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{it.s}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ── S7: 확장 로드맵 — 지금 → 곧 → 그다음 ────────────────────
   가로 타임라인 위에 플랫폼 칩이 순서대로 켜진다. 마지막 칩은 '준비 중'으로 점선. */
export type RoadItem = { label: string; when: string; soon?: boolean };

export const Roadmap: React.FC<{ items: RoadItem[]; appearAt: number[] }> = ({ items, appearAt }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lineP = interpolate(frame, [0, 60], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 1640, position: 'relative' }}>
        {/* 타임라인 */}
        <div style={{
          position: 'absolute', left: 0, right: 0, top: 112, height: 4,
          background: '#ffffff14', borderRadius: 2,
        }} />
        <div style={{
          position: 'absolute', left: 0, top: 112, height: 4, width: `${lineP * 100}%`,
          background: `linear-gradient(90deg, ${MINT}, ${MINT}55)`, borderRadius: 2,
          boxShadow: `0 0 20px ${MINT}66`,
        }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
          {items.map((it, i) => {
            const at = Math.round((appearAt[i] ?? i * 0.8) * fps);
            const on = frame >= at;
            const p = on ? spring({ frame: frame - at, fps, config: { damping: 14, stiffness: 200 } }) : 0;
            return (
              <div key={i} style={{
                flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
                transform: `translateY(${interpolate(p, [0, 1], [30, 0])}px)`, opacity: on ? p : 0.22,
              }}>
                <div style={{
                  fontFamily: FONT, fontWeight: 800, fontSize: 24,
                  color: it.soon ? '#ffffff88' : MINT, marginBottom: 16,
                }}>{it.when}</div>
                <div style={{
                  width: 26, height: 26, borderRadius: 13, marginBottom: 20,
                  background: it.soon ? 'transparent' : MINT,
                  border: `3px solid ${it.soon ? '#ffffff44' : MINT}`,
                  boxShadow: it.soon ? undefined : `0 0 24px ${MINT}88`,
                }} />
                <div style={{
                  padding: '18px 22px', borderRadius: 16, textAlign: 'center', minWidth: 200,
                  background: it.soon ? 'rgba(255,255,255,0.04)' : 'rgba(61,240,178,0.12)',
                  border: it.soon ? '2px dashed #ffffff2e' : `2px solid ${MINT}66`,
                  fontFamily: FONT, fontWeight: 900, fontSize: 38, color: '#fff',
                }}>{it.label}</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ── S8-A: 체크리스트 — "이런 분들이 쓰셨으면 합니다" ──────────
   한 줄씩 켜지고, 켜진 줄엔 민트 체크가 박힌다. */
export const WhoList: React.FC<{ lines: string[]; appearAt: number[] }> = ({ lines, appearAt }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 1380, display: 'flex', flexDirection: 'column', gap: 18 }}>
        {lines.map((t, i) => {
          const at = Math.round((appearAt[i] ?? i) * fps);
          const on = frame >= at;
          const p = on ? spring({ frame: frame - at, fps, config: { damping: 14, stiffness: 190 } }) : 0;
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 22,
              transform: `translateX(${interpolate(p, [0, 1], [-40, 0])}px)`, opacity: p,
            }}>
              <div style={{
                width: 52, height: 52, borderRadius: 26, background: MINT, color: '#05130E',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 30, fontWeight: 900, boxShadow: `0 0 30px ${MINT}55`,
              }}>✓</div>
              <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 46, color: '#fff' }}>{t}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ── S8-B: 외주 비용 계산기 ★S8의 승부처 ─────────────────────
   말로 하면 흘러가는 숫자를, 계산 과정으로 보여준다:
   3만원 × 하루 1개 × 30일 = 90만원 / 매달. 마지막에 '매달'이 붉게 반복 강조된다. */
export const CostCalc: React.FC<{ showAt: number[] }> = ({ showAt }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rows = [
    { k: '쇼츠 편집 외주', v: '한 편 3만 원', note: '(자막 포함 시 5~10만 원)' },
    { k: '하루 한 편만', v: '× 30일' },
    { k: '한 달', v: '90만 원' },
  ];
  const finalAt = Math.round((showAt[3] ?? 3.4) * fps);
  const fp = frame >= finalAt ? spring({ frame: frame - finalAt, fps, config: { damping: 10, stiffness: 240 } }) : 0;
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 1280 }}>
        {rows.map((r, i) => {
          const at = Math.round((showAt[i] ?? i * 1.1) * fps);
          const on = frame >= at;
          const p = on ? spring({ frame: frame - at, fps, config: { damping: 15, stiffness: 200 } }) : 0;
          const last = i === rows.length - 1;
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
              padding: last ? '22px 4px 10px' : '14px 4px',
              borderTop: last ? `2px solid ${RED}66` : undefined,
              marginTop: last ? 18 : 0,
              opacity: p, transform: `translateY(${interpolate(p, [0, 1], [22, 0])}px)`,
            }}>
              <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: last ? 52 : 40, color: last ? '#fff' : '#ffffffbb' }}>
                {r.k}
                {r.note ? <span style={{ fontSize: 26, color: '#ffffff66', marginLeft: 12 }}>{r.note}</span> : null}
              </div>
              <div style={{
                fontFamily: "'Space Mono',monospace", fontWeight: 700,
                fontSize: last ? 82 : 44, color: last ? RED : '#ffffffdd',
                textShadow: last ? `0 0 40px ${RED}44` : undefined,
              }}>{r.v}</div>
            </div>
          );
        })}
        {/* '매달 나가는 돈' — 여기가 이 그래픽의 핵심 한 방 */}
        <div style={{
          marginTop: 26, textAlign: 'right',
          opacity: fp, transform: `scale(${interpolate(fp, [0, 1], [1.25, 1])})`,
        }}>
          <span style={{
            fontFamily: FONT, fontWeight: 900, fontSize: 56, color: '#160404',
            background: RED, padding: '6px 22px', borderRadius: 12,
            boxShadow: `0 0 46px ${RED}55`,
          }}>그것도 매달</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ── S8-C: 가격 공개 ★장식 금지 ────────────────────────────
   숫자만 크게, 배경은 거의 검정. 등장은 느리게(스프링 damping 높게) — 튀어오르면 싸구려가 된다. */
export const PriceReveal: React.FC<{
  price?: string; label?: string; after?: string;
}> = ({ price = '99만 원', label = '평생 소장', after }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 26, stiffness: 70, mass: 1.2 } });
  const afterP = interpolate(frame, [42, 62], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ background: '#030706', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: FONT, fontWeight: 800, fontSize: 44, color: '#ffffff99',
          letterSpacing: '0.14em', opacity: p, marginBottom: 10,
        }}>{label}</div>
        <div style={{
          fontFamily: FONT, fontWeight: 900, fontSize: 230, color: '#fff',
          letterSpacing: '-0.03em', lineHeight: 1.05,
          opacity: p, transform: `translateY(${interpolate(p, [0, 1], [26, 0])}px)`,
        }}>{price}</div>
        {after ? (
          <div style={{
            marginTop: 26, fontFamily: FONT, fontWeight: 800, fontSize: 40,
            color: RED, opacity: afterP,
          }}>{after}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/* 가격 대조 — 왼쪽 붉은(외주, 매달) vs 오른쪽 민트(평생 1회) */
export const PriceVersus: React.FC<{ rightAt?: number }> = ({ rightAt = 1.2 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const l = spring({ frame, fps, config: { damping: 16, stiffness: 150 } });
  const rAt = Math.round(rightAt * fps);
  const r = frame >= rAt ? spring({ frame: frame - rAt, fps, config: { damping: 12, stiffness: 190 } }) : 0;
  const Card: React.FC<{ t: string; big: string; sub: string; tone: string; p: number; dim?: boolean }> = ({
    t, big, sub, tone, p, dim,
  }) => (
    <div style={{
      width: 700, padding: '46px 40px', borderRadius: 24, textAlign: 'center',
      background: dim ? 'rgba(255,90,77,0.07)' : 'rgba(61,240,178,0.10)',
      border: `2px solid ${tone}55`,
      transform: `translateY(${interpolate(p, [0, 1], [50, 0])}px) scale(${interpolate(p, [0, 1], [0.94, 1])})`,
      opacity: p, boxShadow: dim ? undefined : `0 0 60px ${tone}22`,
    }}>
      <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 34, color: '#ffffffaa' }}>{t}</div>
      <div style={{
        fontFamily: FONT, fontWeight: 900, fontSize: 108, color: tone, margin: '10px 0 6px',
        textShadow: `0 0 50px ${tone}44`,
      }}>{big}</div>
      <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 32, color: '#fff' }}>{sub}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', gap: 40, alignItems: 'center' }}>
        <Card t="편집 외주" big="90만 원" sub="매달 · 계속" tone={RED} p={l} dim />
        <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 60, color: '#ffffff33' }}>vs</div>
        <Card t="숏템메이커" big="99만 원" sub="평생 · 한 번" tone={MINT} p={r} />
      </div>
    </AbsoluteFill>
  );
};

/* ── S10: CTA 카드 — 행동 두 개를 번호로 못 박는다 ──────────── */
export const CtaCards: React.FC<{ appearAt: number[] }> = ({ appearAt }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cards = [
    { n: '1', t: '고정 댓글 확인', s: '단톡방 주소가 거기 있습니다' },
    { n: '2', t: '단톡방 입장', s: '1기 모집은 그 방에서만' },
  ];
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', gap: 36 }}>
        {cards.map((c, i) => {
          const at = Math.round((appearAt[i] ?? i * 1.2) * fps);
          const on = frame >= at;
          const p = on ? spring({ frame: frame - at, fps, config: { damping: 14, stiffness: 180 } }) : 0;
          return (
            <div key={i} style={{
              width: 660, padding: '44px 38px', borderRadius: 24,
              background: 'rgba(61,240,178,0.10)', border: `2px solid ${MINT}66`,
              transform: `translateY(${interpolate(p, [0, 1], [46, 0])}px)`, opacity: p,
              boxShadow: `0 0 56px ${MINT}1e`,
            }}>
              <div style={{
                width: 68, height: 68, borderRadius: 34, background: MINT, color: '#05130E',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: FONT, fontWeight: 900, fontSize: 38, marginBottom: 22,
              }}>{c.n}</div>
              <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 54, color: '#fff' }}>{c.t}</div>
              <div style={{ fontFamily: FONT, fontWeight: 700, fontSize: 30, color: MINT, marginTop: 12 }}>{c.s}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* 화면 아래를 가리키는 화살표 — "고정 댓글" 위치 지시. 통통 튄다. */
export const PointDown: React.FC<{ label?: string }> = ({ label = '고정 댓글' }) => {
  const frame = useCurrentFrame();
  const bob = Math.sin(frame / 6) * 14;
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'flex-end', paddingBottom: 40 }}>
      <div style={{ textAlign: 'center', transform: `translateY(${bob}px)` }}>
        <div style={{
          fontFamily: FONT, fontWeight: 900, fontSize: 42, color: '#05130E',
          background: MINT, padding: '10px 26px', borderRadius: 14, marginBottom: 10,
          boxShadow: `0 0 40px ${MINT}66`,
        }}>{label}</div>
        <div style={{ fontSize: 78, color: MINT, lineHeight: 0.9, textShadow: `0 0 30px ${MINT}88` }}>▼</div>
      </div>
    </AbsoluteFill>
  );
};

/* 우측 하단 고정 뱃지 — 가격을 계속 눈에 남긴다(S10 전용).
   ★숫자는 **녹음된 가격**과 반드시 같아야 한다. 2026-08-11 프레임 검수에서
   여기에 옛 대본값(99만/200만)이 박혀 있는 걸 잡았다 — 음성은 "1년 77만 원"인데
   화면은 99만 원이면 그 영상은 못 쓴다. 가격을 바꿀 땐 이 상수부터 고친다. */
export const PRICE_LABEL = '1기 · 1년';
export const PRICE_VALUE = '77만 원';

export const PriceBadge: React.FC = () => (
  <div style={{
    position: 'absolute', right: 40, bottom: 34, textAlign: 'right',
    fontFamily: FONT, fontWeight: 800, opacity: 0.92,
  }}>
    <div style={{ fontSize: 26, color: MINT }}>{PRICE_LABEL} <b style={{ fontSize: 32 }}>{PRICE_VALUE}</b></div>
    <div style={{ fontSize: 22, color: '#ffffff77' }}>다음 기수부터는 이 가격 없음</div>
  </div>
);

/* 카운트다운 자리 — "자리는 계속 줄어듭니다" */
export const SeatsShrink: React.FC<{ from?: number; to?: number; showCount?: boolean }> = ({
  from = 30, to = 7, showCount = false,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const p = interpolate(frame, [0, durationInFrames * 0.8], [0, 1], { extrapolateRight: 'clamp' });
  const n = Math.round(from + (to - from) * p);
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, width: 1100, justifyContent: 'center' }}>
        {Array.from({ length: from }).map((_, i) => {
          const gone = i >= n;
          return (
            <div key={i} style={{
              width: 92, height: 92, borderRadius: 16,
              background: gone ? 'rgba(255,255,255,0.03)' : 'rgba(61,240,178,0.16)',
              border: `2px solid ${gone ? '#ffffff10' : MINT + '77'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 38, color: gone ? '#ffffff22' : MINT,
              transform: gone ? 'scale(0.9)' : 'scale(1)',
            }}>{gone ? '✕' : '●'}</div>
          );
        })}
      </div>
      {/* ★실제 모집 인원을 모른다 — 숫자를 지어내지 않는다(2026-08-11 검수).
          자리가 줄어드는 '움직임'만 남기고 수치는 안 쓴다. */}
      <div style={{
        marginTop: 30, fontFamily: FONT, fontWeight: 900, fontSize: 44, color: '#fff',
      }}>{showCount
        ? <>남은 자리 <span style={{ color: MINT, fontSize: 58 }}>{n}</span></>
        : <>1기 <span style={{ color: MINT }}>한정 인원</span></>}</div>
    </AbsoluteFill>
  );
};
