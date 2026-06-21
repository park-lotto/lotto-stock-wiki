/**
 * KK_S11_Apply — 응용 4종 + 마무리 (744f · 모드 C 리모션 단독)
 * 오디오(s11_audio) + 검정 무대. 자막 4줄 한 줄마다 중앙 그래픽이 호응(이탈 0).
 * 세팅 끝→응용 무궁무진 → 4종 브리핑 → 고정댓글 프롬프트=여러분의 무기 → 따뜻한 엔딩
 *
 * 자막 = Whisper 1:1 타이밍 (ASR 오타만 교정: 프론포트→프롬프트).
 * 골든 레퍼런스: KK_S3_L30.tsx
 */

import React from 'react';
import { Audio, staticFile, useCurrentFrame } from 'remotion';
import { cl, pop, riseFade, zoomPunch, flashAt, pulse, Sfx } from './fx';
import { Stage, Kicker, Watermark, ClaudeIcon, LifeSubBar, LIME, LIME_GLOW, ORANGE, SUB } from './life';

export const KK_S11_APPLY_FRAMES = 744;

const MONO = "'Space Mono','Roboto Mono',monospace";

const SUBS = [
  { from: 0, to: 162, text: '세팅은 다 마쳤습니다. 이 구조만 익히면 응용은 무궁무진합니다.', accent: '무궁무진' },
  { from: 162, to: 397, text: '아침 브리핑, 종목 브리핑, 핵심 일정, 장중 매시간 브리핑까지.', accent: '장중 매시간 브리핑' },
  { from: 397, to: 628, text: '프롬프트 4개는 고정댓글에 올려둘게요. 문장 몇 개만 바꾸면 여러분의 무기.', accent: '여러분의 무기' },
  { from: 628, to: 744, text: '잘 활용해 보세요. 감사합니다.', accent: '감사합니다' },
];

const APPS = [
  { icon: '🌅', title: '아침 브리핑', sub: '장 시작 전 시황 요약', at: 180 },
  { icon: '🎯', title: '개별 종목 브리핑', sub: '내 종목 리포트·뉴스', at: 215 },
  { icon: '📅', title: '이번 주 핵심 일정', sub: '실적·이벤트 캘린더', at: 250 },
  { icon: '⏱️', title: '장중 매시간 브리핑', sub: '실시간 흐름 추적', at: 285 },
];

// ── ambient: 흐르는 흐름선 (S3 골든레퍼런스 동일) ──
const FlowField: React.FC<{ f: number; color?: string }> = ({ f, color = LIME }) => (
  <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
    <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
      {Array.from({ length: 7 }).map((_, i) => {
        const yBase = 120 + i * 140;
        const amp = 38 + (i % 3) * 14;
        const pts: string[] = [];
        for (let x = -40; x <= 1960; x += 36) {
          const y = yBase + Math.sin(x * 0.0055 + f * 0.024 + i * 0.9) * amp + Math.sin(x * 0.013 - f * 0.01) * (amp * 0.4);
          pts.push(`${x},${y.toFixed(1)}`);
        }
        return <polyline key={i} points={pts.join(' ')} fill="none" stroke={color} strokeWidth={1} opacity={0.05 + (i % 2) * 0.04} />;
      })}
    </svg>
    {Array.from({ length: 22 }).map((_, i) => {
      const x = (i * 97) % 1920;
      const y = (1080 - ((f * (0.5 + (i % 4) * 0.25) + i * 60) % 1140)) - 30;
      const op = 0.12 + (i % 3) * 0.06;
      return <div key={i} style={{ position: 'absolute', left: x, top: y, width: 3 + (i % 3), height: 3 + (i % 3), borderRadius: '50%', background: color, opacity: op, boxShadow: `0 0 8px ${color}` }} />;
    })}
  </div>
);

const Beat: React.FC<{ show: boolean; op: number; extra?: React.CSSProperties; children: React.ReactNode }> = ({ show, op, extra, children }) =>
  show ? (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingBottom: '11%', opacity: op, ...extra }}>
      {children}
    </div>
  ) : null;

const KICK: React.CSSProperties = { fontFamily: MONO, fontSize: 17, letterSpacing: 5, marginBottom: 18 };

export const KK_S11_Apply: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <Stage>
      <Audio src={staticFile('kakao/ep1/s11_audio.mp4')} />
      <FlowField f={f} color={LIME} />
      <Kicker ch="CH 11" title="APPLY" f={f} />

      <Sfx at={20} file="chime_up.mp3" vol={0.4} />
      {APPS.map((a, i) => (
        <Sfx key={i} at={a.at} file="pop_appear.mp3" vol={0.3} />
      ))}
      <Sfx at={470} file="impact.mp3" vol={0.4} />
      <Sfx at={636} file="chime_up.mp3" vol={0.45} />

      {/* 컷 플래시 (무기 리빌) */}
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, 470, 8, 0.3), pointerEvents: 'none' }} />

      {/* B1 — 세팅 끝 → 응용 무궁무진 (0~162) */}
      <Beat show={f < 170} op={cl(f, 8, 30) * cl(f, 140, 162, 1, 0)}>
        <div style={{ ...KICK, color: LIME }}>SETUP DONE · 세팅 완료</div>
        {(() => { const p = pop(f, 16, { damping: 8 }); return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 26, transform: `scale(${0.8 + p * 0.2})` }}>
            <span style={{ fontSize: 64 }}>✅</span>
            <span style={{ fontSize: 56, fontWeight: 800, color: SUB }}>세팅은 전부 끝</span>
          </div>
        ); })()}
        <div style={{ fontSize: 64, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>이제 응용은</div>
        <div style={{ fontSize: 130, fontWeight: 900, color: LIME, letterSpacing: -5, lineHeight: 1.05, textShadow: `0 0 50px ${LIME_GLOW}`, transform: `scale(${zoomPunch(f, 60, 1.12, 16)})` }}>무궁무진</div>
      </Beat>

      {/* B2 — 응용 4종 (162~397) */}
      <Beat show={f >= 162 && f < 397} op={cl(f, 166, 192) * cl(f, 374, 397, 1, 0)}>
        <div style={{ ...KICK, color: LIME }}>USE CASES · 이런 것들</div>
        <div style={{ fontSize: 52, fontWeight: 900, color: '#fff', letterSpacing: -2, marginBottom: 30 }}>당장 이렇게 쓸 수 있어요</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22 }}>
          {APPS.map((a, i) => {
            const { opacity, y } = riseFade(f, a.at, 12, 34);
            const p = pop(f, a.at, { damping: 8, stiffness: 240 });
            return (
              <div key={i} style={{ opacity, transform: `translateY(${y}px) scale(${0.85 + p * 0.15})`, display: 'flex', alignItems: 'center', gap: 18, width: 480, padding: '22px 28px', background: 'rgba(0,0,0,0.55)', border: `2px solid ${LIME}`, borderRadius: 18, boxShadow: `0 0 26px ${LIME}22` }}>
                <span style={{ fontSize: 54 }}>{a.icon}</span>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontSize: 32, fontWeight: 900, color: '#fff', letterSpacing: -1 }}>{a.title}</div>
                  <div style={{ fontSize: 20, fontWeight: 600, color: SUB, marginTop: 4 }}>{a.sub}</div>
                </div>
              </div>
            );
          })}
        </div>
      </Beat>

      {/* B3 — 고정댓글 프롬프트 = 여러분의 무기 (397~628) */}
      <Beat show={f >= 397 && f < 628} op={cl(f, 401, 427) * cl(f, 605, 628, 1, 0)}>
        <div style={{ ...KICK, color: ORANGE }}>FREE GIFT · 고정댓글</div>
        {/* 프롬프트 4개 칩 */}
        {(() => { const { opacity, y } = riseFade(f, 410, 14, 34); return (
          <div style={{ opacity, transform: `translateY(${y}px)`, display: 'flex', alignItems: 'center', gap: 14, padding: '18px 34px', background: 'rgba(0,0,0,0.6)', border: `2px solid ${ORANGE}`, borderRadius: 16, fontSize: 40, fontWeight: 900, color: '#fff', marginBottom: 28, boxShadow: `0 0 28px ${ORANGE}33` }}>
            📌 프롬프트 <span style={{ color: ORANGE }}>4개</span> 고정댓글에 박제
          </div>
        ); })()}
        {/* 문장 몇 개만 바꾸면 */}
        <div style={{ opacity: cl(f, 440, 466), fontSize: 46, fontWeight: 800, color: SUB, marginBottom: 18 }}>
          문장 몇 개만 바꾸면 →
        </div>
        {/* 여러분의 무기 리빌 */}
        {f >= 470 && (() => { const p = pop(f, 470, { damping: 8 }); return (
          <div style={{ transform: `scale(${0.7 + p * 0.3})`, opacity: cl(f, 470, 488), fontSize: 110, fontWeight: 900, color: LIME, letterSpacing: -4, lineHeight: 1.05, textShadow: `0 0 50px ${LIME_GLOW}` }}>
            🗡️ 여러분의 무기
          </div>
        ); })()}
      </Beat>

      {/* B4 — 따뜻한 엔딩 (628~744) */}
      {f >= 628 && (
        <Beat show op={cl(f, 632, 658) * cl(f, 720, 744, 1, 0.2)}>
          <div style={{ transform: `scale(${1 + pulse(f, 0.08, 0, 0.03)})`, marginBottom: 26 }}>
            <ClaudeIcon size={88} />
          </div>
          <div style={{ fontSize: 70, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>
            잘 <span style={{ color: LIME, textShadow: `0 0 32px ${LIME_GLOW}` }}>활용</span>해 보세요
          </div>
          {(() => { const { opacity, y } = riseFade(f, 680, 14, 30); return (
            <div style={{ opacity, transform: `translateY(${y}px)`, fontSize: 56, fontWeight: 900, color: ORANGE, marginTop: 18, textShadow: `0 0 30px ${ORANGE}66` }}>
              감사합니다 🙏
            </div>
          ); })()}
          <div style={{ opacity: cl(f, 700, 720), fontFamily: MONO, fontSize: 22, letterSpacing: 4, color: SUB, marginTop: 26 }}>
            STOCK<span style={{ color: LIME }}>BRAIN</span>
          </div>
        </Beat>
      )}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
    </Stage>
  );
};
