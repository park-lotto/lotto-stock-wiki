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
  Loop, OffthreadVideo, staticFile, Sequence,
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

/* ══════════════════════════════════════════════════════════════
   배경 레이어 (2026-08-11 사장님 "S7·S8 배경이 밋밋하다")

   왜 영상 배경인가: 후반부는 말이 무거운 구간이라 화면이 비면 슬라이드처럼 보인다.
   그렇다고 새 소재를 찍을 필요는 없다 — **이미 만든 완성 쇼츠**를 어둡게 깔면
   "고생하신 분들 / 이걸 쓰셨으면" 하는 말 뒤로 결과물이 계속 흐른다.
   장식이 아니라 배경에 깔린 증거다.

   ★가독성이 우선이다. 밝기를 0.2 언저리까지 눌러 자막이 절대 안 묻히게 한다.
   ══════════════════════════════════════════════════════════════ */

const BED_CLIPS = [
  'vsl/s1/KakaoTalk_20260811_100239161.mp4',
  'vsl/s1/final_63d8494f99e3.mp4',
  'vsl/s1/KakaoTalk_20260811_103115345.mp4',
  'vsl/s1/final_31b394c4685d.mp4',
  'vsl/s1/KakaoTalk_20260811_105318092.mp4',
  'vsl/s1/final_8b7facca37a8.mp4',
];

/** 완성 쇼츠가 세로로 흐르는 배경. cols열이 서로 다른 속도로 움직여 패턴이 안 보인다. */
export const ReelBed: React.FC<{
  cols?: number; brightness?: number; blur?: number; speed?: number;
}> = ({ cols = 3, brightness = 0.22, blur = 1.5, speed = 1 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const colW = 1920 / cols;
  const cellH = Math.round(colW * 16 / 9);
  return (
    <AbsoluteFill style={{ background: '#040A08', overflow: 'hidden' }}>
      {Array.from({ length: cols }).map((_, c) => {
        // 열마다 속도·시작 위치를 어긋내 '같은 화면이 반복된다'는 느낌을 없앤다
        const sp = speed * (0.8 + (c % 3) * 0.22);
        const y = interpolate(frame, [0, durationInFrames], [0, -cellH * 0.9 * sp]);
        const a = BED_CLIPS[(c * 2) % BED_CLIPS.length];
        const b = BED_CLIPS[(c * 2 + 1) % BED_CLIPS.length];
        return (
          <div key={c} style={{
            position: 'absolute', left: c * colW, top: -cellH * 0.25 + (c % 2 ? -120 : 0),
            width: colW, transform: `translateY(${y}px)`,
          }}>
            {[a, b].map((src, i) => (
              <div key={i} style={{
                position: 'relative', width: colW, height: cellH, overflow: 'hidden',
              }}>
                <Loop durationInFrames={Math.max(1, Math.round(14 * fps))}>
                  <OffthreadVideo
                    src={staticFile(src)}
                    trimBefore={Math.round((3 + i * 4 + c * 2) * fps)}
                    volume={0}
                    style={{
                      width: '100%', height: '100%', objectFit: 'cover',
                      filter: `brightness(${brightness}) blur(${blur}px) saturate(0.7)`,
                    }}
                  />
                </Loop>
              </div>
            ))}
          </div>
        );
      })}
      {/* 가독성 보호막 — 이게 없으면 자막이 영상 무늬에 묻힌다 */}
      <AbsoluteFill style={{ background: 'rgba(4,10,8,0.52)' }} />
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 34%, rgba(0,0,0,0.72) 100%)',
      }} />
    </AbsoluteFill>
  );
};

/** 느리게 떠오르는 민트 입자 — 화면이 '살아 있다'는 최소 신호 */
export const Particles: React.FC<{ count?: number; tone?: string }> = ({
  count = 34, tone = MINT,
}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {Array.from({ length: count }).map((_, i) => {
        const seed = (i * 9301 + 49297) % 233280 / 233280;
        const seed2 = (i * 4211 + 12345) % 65536 / 65536;
        const x = seed * 1920;
        const speed = 0.25 + seed2 * 0.55;
        const y = (1180 - ((frame * speed + seed2 * 1200) % 1300));
        const size = 2 + seed2 * 4;
        const op = 0.10 + seed * 0.30;
        return (
          <div key={i} style={{
            position: 'absolute', left: x, top: y, width: size, height: size,
            borderRadius: size, background: tone, opacity: op,
            boxShadow: `0 0 ${size * 4}px ${tone}`,
          }} />
        );
      })}
    </AbsoluteFill>
  );
};

/** 필름 그레인 + 비네트 — 순수 CSS라 렌더가 가볍고, 평평한 화면에 질감을 준다 */
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.06 }) => {
  const frame = useCurrentFrame();
  const shift = (frame % 6) * 37;
  return (
    <AbsoluteFill style={{
      pointerEvents: 'none', opacity,
      backgroundImage:
        'repeating-conic-gradient(#fff 0% 25%, #000 0% 50%)',
      backgroundSize: '3px 3px',
      backgroundPosition: `${shift}px ${shift * 0.7}px`,
      mixBlendMode: 'overlay',
    }} />
  );
};

/** 위에서 아래로 훑는 민트 광선 — 아주 느리게, 존재감만 */
export const ScanBeam: React.FC<{ tone?: string }> = ({ tone = MINT }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const y = interpolate(frame, [0, durationInFrames], [-30, 130]);
  return (
    <AbsoluteFill style={{ pointerEvents: 'none', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', left: '-20%', right: '-20%', top: `${y}%`, height: '46%',
        background: `linear-gradient(180deg, rgba(0,0,0,0) 0%, ${tone}14 50%, rgba(0,0,0,0) 100%)`,
        transform: 'rotate(-8deg)',
      }} />
    </AbsoluteFill>
  );
};

/* ══════════════════════════════════════════════════════════════
   ScreenBed — 배경의 주인공은 '우리 페이지'다 (2026-08-11)

   쇼츠만 3열로 흘리니 같은 무늬가 계속 도는 것처럼 보였다. S7·S8에서 하는 말은
   "프로그램이 확장된다 / 이 안에 다 담았다"인데, 그 말의 증거는 쇼츠 결과물이
   아니라 **제작소·레퍼런스·히트작 화면 그 자체**다. 그래서 배경을 화면녹화로 바꾸고,
   S1 완성본은 사이사이 숨 돌리는 자리에만 끼운다.

   반복 안 보이게 하는 장치 두 개:
   ① 소재 6개(총 205초)를 세그먼트마다 다른 지점(seek)에서 재생 → 같은 파일이 다시
      나와도 다른 장면이 나온다.
   ② 세그먼트 길이를 7·9·8초로 어긋내 '몇 초마다 바뀐다'는 박자가 안 잡힌다.
   ══════════════════════════════════════════════════════════════ */

/** ★우리 편 화면만. s2/rec*는 남의 유튜브, s4/rec1은 개발 터미널이라 고객 구간엔 안 쓴다. */
const SCREEN_CLIPS = [
  { src: 'vsl/s4/rec2.mp4', len: 27.6 },  // 레퍼런스 랭킹
  { src: 'vsl/s4/rec3.mp4', len: 33.8 },  // 히트작 그리드
];

/* 뷰포트 — 실사 소재가 61초뿐이라 '소재'가 아니라 '보는 방식'을 늘린다.
   같은 클립도 크게 잘라 다른 영역을 보여주면 다른 화면으로 읽힌다. */
const WINDOWS = [
  { z: 1.65, x: -14, y: -10 },
  { z: 2.10, x: 12, y: 8 },
  { z: 1.80, x: 8, y: -14 },
  { z: 2.20, x: -10, y: 12 },
  { z: 1.70, x: 0, y: 0 },
];

const SEG_LENS = [7, 9, 8]; // 초 — 균등하면 박자가 잡힌다

/** BG1 워크벤치 — 우리 페이지를 크게 잘라 아주 느리게 민다 */
const ScreenShot: React.FC<{
  src: string; at: number; brightness: number; win: number; deep?: boolean;
}> = ({ src, at, brightness, win, deep }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const w = WINDOWS[win % WINDOWS.length];
  const z = interpolate(frame, [0, durationInFrames], [w.z, w.z * 1.07]);
  const dx = interpolate(frame, [0, durationInFrames], [w.x, w.x * 0.4]);
  const dy = interpolate(frame, [0, durationInFrames], [w.y, w.y * 0.4]);
  const fade = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ overflow: 'hidden', opacity: fade }}>
      <OffthreadVideo
        src={staticFile(src)} trimBefore={Math.round(at * fps)} playbackRate={1.2} volume={0}
        style={{
          width: '100%', height: '100%', objectFit: 'cover',
          transform: `scale(${z}) translate(${dx}%, ${dy}%)`,
          // BG3 딥필드 = 같은 소재를 강하게 흐려 색만 남긴다(그래픽 컷의 바닥)
          filter: `brightness(${brightness}) blur(${deep ? 14 : 1.4}px) saturate(${deep ? 1.15 : 0.9})`,
        }}
      />
    </AbsoluteFill>
  );
};

/** BG2 결과물 벽 — 완성 쇼츠 3편이 서로 다른 속도로 흐른다 */
const ReelRow: React.FC<{ pick: number; brightness: number }> = ({ pick, brightness }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const fade = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  const y = interpolate(frame, [0, durationInFrames], [0, -70]);
  const colW = 1920 / 3;
  return (
    <AbsoluteFill style={{ background: '#040A08', overflow: 'hidden', opacity: fade }}>
      {[0, 1, 2].map((c) => {
        const src = BED_CLIPS[(pick * 3 + c) % BED_CLIPS.length];
        return (
          <div key={c} style={{
            position: 'absolute', left: c * colW, top: -160 + (c % 2 ? -40 : 0),
            width: colW, height: 1420, overflow: 'hidden',
            transform: `translateY(${y * (0.7 + c * 0.25)}px)`,
          }}>
            <OffthreadVideo
              src={staticFile(src)}
              trimBefore={Math.round((2 + c * 3 + pick * 2) * fps)} volume={0}
              style={{
                width: '100%', height: '100%', objectFit: 'cover',
                filter: `brightness(${brightness}) blur(1.4px) saturate(0.75)`,
              }}
            />
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/** 우리 페이지(BG1) ↔ 결과물 벽(BG2) 교차 배경. deep=true면 전부 BG3 딥필드. */
export const ScreenBed: React.FC<{ brightness?: number; deep?: boolean }> = ({
  brightness = 0.32, deep,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  const segs: { from: number; dur: number; i: number }[] = [];
  let at = 0, i = 0;
  while (at < durationInFrames) {
    const dur = Math.round(SEG_LENS[i % SEG_LENS.length] * fps);
    segs.push({ from: at, dur: Math.min(dur, durationInFrames - at), i });
    at += dur; i += 1;
  }
  return (
    <AbsoluteFill style={{ background: '#040A08', overflow: 'hidden' }}>
      {segs.map((s) => {
        // 화면·화면·결과물 — 20초 룰(같은 그림이 20초 안에 두 번 안 온다)
        const isReel = !deep && s.i % 3 === 2;
        const k = Math.floor(s.i / 3);
        const clip = SCREEN_CLIPS[s.i % SCREEN_CLIPS.length];
        const at2 = (1 + s.i * 5.5) % Math.max(1, clip.len - 9);
        return (
          <Sequence key={s.i} from={s.from} durationInFrames={s.dur}>
            {isReel
              ? <ReelRow pick={k} brightness={brightness * 0.8} />
              : <ScreenShot src={clip.src} at={at2} win={s.i} deep={deep}
                  brightness={deep ? brightness * 1.5 : brightness} />}
          </Sequence>
        );
      })}
      {/* 가독성 보호막 — 배경은 어디까지나 배경이다 */}
      <AbsoluteFill style={{ background: `rgba(4,10,8,${deep ? 0.42 : 0.5})` }} />
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0.26) 0%, rgba(0,0,0,0.78) 100%)',
      }} />
    </AbsoluteFill>
  );
};

/* ══════════════════════════════════════════════════════════════
   BG6 릴스월 — 완성 쇼츠가 **인스타 릴스 플레이어 안에서** 도는 화면 (2026-08-11)

   사장님 요청: "쇼핑쇼츠 영상들 인스타에 있는 것들 재생화면으로."
   실제 인스타 녹화본이 없어서 플레이어 화면을 만들었다. 우리 결과물이
   '피드에 올라가 도는 상태'로 보이는 게 요지다.

   ★좋아요·댓글 수는 넣지 않는다. 없는 수치를 지어내면 그게 거짓말이다
     (같은 실수를 '남은 자리 14'로 이미 한 번 했다). 아이콘만 둔다.
   ★폰 3대는 서로 다른 시점에 다음 쇼츠로 '넘어간다' — 스와이프 재생처럼 읽힌다.
   ══════════════════════════════════════════════════════════════ */

const PhoneIcons: React.FC = () => (
  <div style={{
    position: 'absolute', right: 14, bottom: 96, display: 'flex',
    flexDirection: 'column', gap: 22, alignItems: 'center', opacity: 0.9,
  }}>
    {/* 하트 */}
    <div style={{ fontSize: 30, color: '#fff', lineHeight: 1 }}>♥</div>
    {/* 댓글 — 말풍선 외곽선 */}
    <div style={{
      width: 26, height: 24, border: '2.5px solid #fff', borderRadius: 8,
    }} />
    {/* 공유 — 종이비행기 대용 삼각형 */}
    <div style={{
      width: 0, height: 0, borderLeft: '15px solid #fff',
      borderTop: '9px solid transparent', borderBottom: '9px solid transparent',
      transform: 'rotate(-20deg)',
    }} />
  </div>
);

/** 폰 1대 — 안에서 쇼츠가 돌고, 일정 간격으로 다음 편으로 넘어간다 */
const Phone: React.FC<{ seed: number; w: number; every: number; brightness: number }> = ({
  seed, w, every, brightness,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const h = Math.round(w * 16 / 9);
  const step = Math.max(1, Math.round(every * fps));
  const idx = Math.floor((frame + seed * 37) / step);
  const src = BED_CLIPS[(idx + seed) % BED_CLIPS.length];
  // 넘어가는 순간 살짝 위로 밀린다 — 스와이프 느낌
  const local = (frame + seed * 37) % step;
  const slide = local < 8 ? interpolate(local, [0, 8], [40, 0]) : 0;
  return (
    <div style={{
      position: 'relative', width: w, height: h, borderRadius: 26, overflow: 'hidden',
      border: '2px solid rgba(255,255,255,0.16)',
      boxShadow: '0 30px 80px rgba(0,0,0,0.6)', background: '#000',
    }}>
      <div style={{ position: 'absolute', inset: 0, transform: `translateY(${slide}px)` }}>
        <OffthreadVideo
          key={src + idx}
          src={staticFile(src)} trimBefore={Math.round((2 + seed * 3) * fps)} volume={0}
          style={{
            width: '100%', height: '100%', objectFit: 'cover',
            filter: `brightness(${brightness}) saturate(0.9)`,
          }}
        />
      </div>
      {/* 상단 릴스 라벨 */}
      <div style={{
        position: 'absolute', top: 16, left: 18, right: 18,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontFamily: FONT, fontWeight: 800, fontSize: 20, color: '#fff', opacity: 0.85,
      }}>
        <span>릴스</span>
        <span style={{ fontSize: 22, letterSpacing: 2 }}>⋯</span>
      </div>
      {/* 하단 자리표시 — 캡션 내용을 지어내지 않고 막대로만 둔다 */}
      <div style={{
        position: 'absolute', left: 16, bottom: 26, display: 'flex',
        flexDirection: 'column', gap: 8,
      }}>
        <div style={{ width: w * 0.42, height: 9, borderRadius: 5, background: 'rgba(255,255,255,0.5)' }} />
        <div style={{ width: w * 0.3, height: 8, borderRadius: 5, background: 'rgba(255,255,255,0.28)' }} />
      </div>
      <PhoneIcons />
      {/* 화면 유리 반사 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(120deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 42%)',
      }} />
    </div>
  );
};

/** 릴스 플레이어 3대가 나란히 — 가운데가 앞, 양옆은 뒤로 물러난다 */
export const InstaBed: React.FC<{ brightness?: number }> = ({ brightness = 0.8 }) => {
  const frame = useCurrentFrame();
  const float = (k: number) => Math.sin((frame + k * 40) / 70) * 10;
  const phones = [
    { seed: 1, w: 340, every: 5.5, x: -600, s: 0.9, o: 0.72 },
    { seed: 0, w: 400, every: 6.5, x: 0, s: 1.0, o: 1.0 },
    { seed: 2, w: 340, every: 7.5, x: 600, s: 0.9, o: 0.72 },
  ];
  return (
    <AbsoluteFill style={{ background: '#060B09', overflow: 'hidden' }}>
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at 50% 40%, rgba(61,240,178,0.10) 0%, rgba(0,0,0,0) 60%)',
      }} />
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
        {phones.map((p) => (
          <div key={p.seed} style={{
            position: 'absolute',
            transform: `translate(${p.x}px, ${float(p.seed)}px) scale(${p.s})`,
            opacity: p.o,
          }}>
            <Phone seed={p.seed} w={p.w} every={p.every} brightness={brightness} />
          </div>
        ))}
      </AbsoluteFill>
      {/* 가독성 보호막 */}
      <AbsoluteFill style={{ background: 'rgba(4,10,8,0.18)' }} />
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0.10) 0%, rgba(0,0,0,0.62) 100%)',
      }} />
    </AbsoluteFill>
  );
};

/** BG4 나이트빌드 — 개발 화면을 강하게 흐려 '만들어지는 중'의 질감만 남긴다.
    ★글자가 읽히면 안 된다(내부 화면이다). blur 16px로 코드는 색·흐름으로만 남는다. */
const NightBed: React.FC<{ brightness?: number }> = ({ brightness = 0.42 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const z = interpolate(frame, [0, durationInFrames], [1.25, 1.4]);
  return (
    <AbsoluteFill style={{ background: '#040A08', overflow: 'hidden' }}>
      <Loop durationInFrames={Math.max(1, Math.round(20 * fps))}>
        <OffthreadVideo
          src={staticFile('vsl/s4/rec1.mp4')} trimBefore={Math.round(2 * fps)}
          playbackRate={1.6} volume={0}
          style={{
            width: '100%', height: '100%', objectFit: 'cover',
            transform: `scale(${z})`,
            filter: `brightness(${brightness}) blur(16px) saturate(1.3)`,
          }}
        />
      </Loop>
      <AbsoluteFill style={{ background: 'rgba(4,10,8,0.46)' }} />
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0.22) 0%, rgba(0,0,0,0.8) 100%)',
      }} />
    </AbsoluteFill>
  );
};

/** 합성 배경 — 기획서 BG1~BG5. work=워크벤치/딥=그래픽 컷 바닥/오라=보이드 */
export const RichBed: React.FC<{
  kind?: 'work' | 'deep' | 'night' | 'insta' | 'aura'; tone?: string; brightness?: number;
}> = ({ kind = 'work', tone = MINT, brightness = 0.32 }) => (
  <AbsoluteFill>
    {kind === 'aura' ? <Aura tone={tone} strength={0.12} />
      : kind === 'insta' ? <InstaBed />
      : kind === 'night' ? <NightBed />
      : <ScreenBed brightness={brightness} deep={kind === 'deep'} />}
    <ScanBeam tone={tone} />
    <Particles tone={tone} count={22} />
    <Grain />
  </AbsoluteFill>
);