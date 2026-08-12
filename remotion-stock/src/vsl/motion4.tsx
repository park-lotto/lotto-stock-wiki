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
  const { fps, width } = useVideoConfig();
  // ★폭 고정(1420) 금지 — 세로 1080 캔버스에서 목록이 화면 밖으로 밀려 날짜가 잘렸다(실측)
  const w = Math.min(1420, Math.round(width * 0.88));
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: w, display: 'flex', flexDirection: 'column', gap: 12 }}>
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
  /* ★선을 절대좌표(top:112)로 띄워놨더니 칩 글자를 가로질렀다(사장님 캡처 2장).
     이제 선은 **점이 놓인 줄에만** 있고, 칩은 그 아래 별도 층에 있다.
     진행선도 시간이 아니라 **켜진 항목 수**까지만 자란다 — 안 켜진 칩까지
     선이 미리 그어져 있으면 "이미 다 됐다"로 읽혀 로드맵이 뜻을 잃는다. */
  const onCount = items.filter((_, i) => frame >= Math.round((appearAt[i] ?? i * 0.8) * fps)).length;
  const target = items.length <= 1 ? 1 : (onCount - 0.5) / (items.length - 1);
  const grow = interpolate(
    frame, [0, 20], [0, Math.max(0, Math.min(1, target))],
    { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) },
  );
  const DOT_ROW = 46;   // 점이 놓인 줄의 높이
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 1640, position: 'relative' }}>
        {/* 1층 — 라벨(지금·확장·곧) */}
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
          {items.map((it, i) => {
            const at = Math.round((appearAt[i] ?? i * 0.8) * fps);
            const on = frame >= at;
            return (
              <div key={i} style={{
                flex: 1, textAlign: 'center', fontFamily: FONT, fontWeight: 800, fontSize: 24,
                color: it.soon ? '#ffffff88' : MINT, opacity: on ? 1 : 0.3, marginBottom: 14,
              }}>{it.when}</div>
            );
          })}
        </div>

        {/* 2층 — 선 + 점. 이 줄에는 글자가 없다(그래서 안 겹친다) */}
        <div style={{ position: 'relative', height: DOT_ROW }}>
          <div style={{
            position: 'absolute', left: 60, right: 60, top: DOT_ROW / 2 - 2, height: 4,
            background: '#ffffff12', borderRadius: 2,
          }} />
          <div style={{
            position: 'absolute', left: 60, top: DOT_ROW / 2 - 2, height: 4,
            width: `calc((100% - 120px) * ${grow})`,
            background: `linear-gradient(90deg, ${MINT}, ${MINT}77)`, borderRadius: 2,
            boxShadow: `0 0 20px ${MINT}66`,
          }} />
          <div style={{
            position: 'absolute', inset: 0, display: 'flex',
            justifyContent: 'space-between', gap: 14, alignItems: 'center',
          }}>
            {items.map((it, i) => {
              const at = Math.round((appearAt[i] ?? i * 0.8) * fps);
              const on = frame >= at;
              const p = on ? spring({ frame: frame - at, fps, config: { damping: 13, stiffness: 220 } }) : 0;
              const done = on && !it.soon;
              return (
                <div key={i} style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
                  {/* ★켜진 항목엔 체크, 예정은 빈 동그라미 — 상태가 한눈에 갈린다 */}
                  <div style={{
                    width: 38, height: 38, borderRadius: 19,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: done ? MINT : '#0A1512',
                    border: `3px solid ${done ? MINT : (on ? '#ffffff66' : '#ffffff2a')}`,
                    boxShadow: done ? `0 0 26px ${MINT}99` : undefined,
                    color: '#05130E', fontSize: 22, fontWeight: 900, fontFamily: FONT,
                    transform: `scale(${0.7 + p * 0.3})`,
                  }}>{done ? '✓' : ''}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 3층 — 칩 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, marginTop: 18 }}>
          {items.map((it, i) => {
            const at = Math.round((appearAt[i] ?? i * 0.8) * fps);
            const on = frame >= at;
            const p = on ? spring({ frame: frame - at, fps, config: { damping: 14, stiffness: 200 } }) : 0;
            return (
              <div key={i} style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
                <div style={{
                  padding: '18px 22px', borderRadius: 16, textAlign: 'center', minWidth: 200,
                  background: it.soon ? 'rgba(255,255,255,0.04)' : 'rgba(61,240,178,0.12)',
                  border: it.soon ? '2px dashed #ffffff2e' : `2px solid ${MINT}66`,
                  fontFamily: FONT, fontWeight: 900, fontSize: 38, color: '#fff',
                  transform: `translateY(${interpolate(p, [0, 1], [26, 0])}px)`,
                  opacity: on ? 1 : 0.22,
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

/* ★삭제(2026-08-12): CostCalc(외주 3만×30일=90만) — 녹음에 없는 구간이라 안 쓰는데
   옛 숫자만 코드에 남아 있었다. 죽은 코드에 든 가격은 언젠가 화면에 나간다. */

/* ── S8-C: 가격 공개 ★장식 금지 ────────────────────────────
   숫자만 크게, 배경은 거의 검정. 등장은 느리게(스프링 damping 높게) — 튀어오르면 싸구려가 된다. */
export const PriceReveal: React.FC<{
  price: string; label: string; after?: string;   // ★선택 아님 — 안 넘기면 컴파일이 막는다
}> = ({ price, label, after }) => {   // ★기본값 없음 — 가격은 넘겨받은 것만 쓴다
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

/* ★삭제(2026-08-12): PriceVersus — "90만 원 매달 / 99만 원 평생"이 박혀 있었다.
   실제 녹음은 "1기에서만 1년 77만 원". 안 쓰는 컴포넌트였지만 CutView 스위치에
   'versus'가 살아 있어, 컷 하나만 잘못 쓰면 음성과 다른 가격이 나갈 뻔했다.
   가격은 PRICE_LABEL/PRICE_VALUE 상수 한 곳에서만 온다. */

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
  { src: 'vsl/s4/rec4.mp4', len: 43.1 },  // 레퍼런스 랭킹 (2026-08-11 추가분)
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
  const fade = interpolate(frame, [0, 22], [0, 1], { extrapolateRight: 'clamp' });
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
  const fade = interpolate(frame, [0, 22], [0, 1], { extrapolateRight: 'clamp' });
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
   BG6 릴스월 — 인스타 프로필 릴스 그리드 **실제 녹화** (2026-08-11)

   처음엔 릴스 플레이어를 직접 그려 완성 쇼츠를 넣었다. 사장님이 실제 인스타
   화면 3개(총 50초)를 주셔서 **진짜로 교체**했다. 만든 화면과 결정적으로 다른 점:
   **조회수가 실제로 찍혀 있다**(28.9만·1.1만·8025…). 지어낸 숫자가 아니라
   실측치라 그대로 써도 된다 — 이게 이 배경의 힘이다.

   녹화가 브라우저 창이라 위아래 검은 여백이 있다 → 1.32배로 잘라 없앤다.
   ══════════════════════════════════════════════════════════════ */

const IG_CLIPS = [
  { src: 'vsl/insta/ig1.mp4', len: 25.1 },
  { src: 'vsl/insta/ig3.mp4', len: 15.5 },
  { src: 'vsl/insta/ig2.mp4', len: 9.2 },
];

const IG_WINDOWS = [
  { z: 1.32, x: 0, y: 0 },
  { z: 1.55, x: -6, y: 4 },
  { z: 1.40, x: 5, y: -3 },
];

const IgShot: React.FC<{ src: string; at: number; win: number; brightness: number }> = ({
  src, at, win, brightness,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const w = IG_WINDOWS[win % IG_WINDOWS.length];
  const z = interpolate(frame, [0, durationInFrames], [w.z, w.z * 1.05]);
  const fade = interpolate(frame, [0, 22], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ overflow: 'hidden', opacity: fade, background: '#000' }}>
      <OffthreadVideo
        src={staticFile(src)} trimBefore={Math.round(at * fps)} volume={0}
        style={{
          width: '100%', height: '100%', objectFit: 'cover',
          transform: `scale(${z}) translate(${w.x}%, ${w.y}%)`,
          filter: `brightness(${brightness}) saturate(0.95)`,
        }}
      />
    </AbsoluteFill>
  );
};

/** 인스타 릴스 그리드가 흐르는 배경 */
export const InstaBed: React.FC<{ brightness?: number }> = ({ brightness = 0.62 }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const segs: { from: number; dur: number; i: number }[] = [];
  let at = 0, i = 0;
  while (at < durationInFrames) {
    const dur = Math.round([7, 6, 8][i % 3] * fps);
    segs.push({ from: at, dur: Math.min(dur, durationInFrames - at), i });
    at += dur; i += 1;
  }
  return (
    <AbsoluteFill style={{ background: '#060B09', overflow: 'hidden' }}>
      {segs.map((sg) => {
        const clip = IG_CLIPS[sg.i % IG_CLIPS.length];
        const at2 = (sg.i * 4.5) % Math.max(0.5, clip.len - 7);
        return (
          <Sequence key={sg.i} from={sg.from} durationInFrames={sg.dur}>
            <IgShot src={clip.src} at={at2} win={sg.i} brightness={brightness} />
          </Sequence>
        );
      })}
      {/* 가독성 보호막 — 실사가 밝아서 이게 없으면 자막이 묻힌다 */}
      <AbsoluteFill style={{ background: 'rgba(4,10,8,0.34)' }} />
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0.30) 0%, rgba(0,0,0,0.76) 100%)',
      }} />
    </AbsoluteFill>
  );
};

/* 남의 방식 배경 — 유튜브 강의·검색 화면. ★페인 구간에서만 쓴다.
   우리 오퍼 뒤에 깔면 경쟁자 얼굴이 우리 편처럼 보인다(2026-08-11 규칙). */
const PAIN_CLIPS = ['vsl/s2/rec3.mp4', 'vsl/s2/rec2.mp4', 'vsl/s2/rec1.mp4'];

const PainBed: React.FC<{ brightness?: number }> = ({ brightness = 0.34 }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const segs: { from: number; dur: number; i: number }[] = [];
  let at = 0, i = 0;
  while (at < durationInFrames) {
    const dur = Math.round(6 * fps);
    segs.push({ from: at, dur: Math.min(dur, durationInFrames - at), i });
    at += dur; i += 1;
  }
  return (
    <AbsoluteFill style={{ background: '#0B0D0D', overflow: 'hidden' }}>
      {segs.map((sg) => (
        <Sequence key={sg.i} from={sg.from} durationInFrames={sg.dur}>
          <IgShot src={PAIN_CLIPS[sg.i % PAIN_CLIPS.length]} at={4 + sg.i * 7}
            win={sg.i} brightness={brightness} />
        </Sequence>
      ))}
      {/* 탈색 — 남의 방식은 색이 빠져 보여야 한다(S2 색 규칙) */}
      <AbsoluteFill style={{ background: 'rgba(10,10,12,0.5)' }} />
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.8) 100%)',
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
  kind?: 'work' | 'deep' | 'night' | 'insta' | 'pain' | 'aura'; tone?: string; brightness?: number;
}> = ({ kind = 'work', tone = MINT, brightness = 0.32 }) => (
  <AbsoluteFill>
    {kind === 'aura' ? <Aura tone={tone} strength={0.12} />
      : kind === 'insta' ? <InstaBed />
      : kind === 'pain' ? <PainBed />
      : kind === 'night' ? <NightBed />
      : <ScreenBed brightness={brightness} deep={kind === 'deep'} />}
    <ScanBeam tone={tone} />
    <Particles tone={tone} count={22} />
    <Grain />
  </AbsoluteFill>
);