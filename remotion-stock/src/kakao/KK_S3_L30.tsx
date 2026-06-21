/**
 * KK_S3_L30 — 철학 (2404f · 모드 C 리모션 단독)
 * 오디오(s03_audio) + 검정 무대. 자막 18줄 한 줄마다 중앙 그래픽이 호응(이탈 0).
 * 미신 → 치트키 없다 → AI 인정 → 1% 반전 → 살아있는 생물 → 인간의 광기
 * → 카톡 정보수집 소개 → ❌종목추천 → AI가 월등한 영역 → FOCUS(주도섹터·돈의 흐름)
 *
 * 자막 = Whisper 1:1 (타이밍 변경 금지, DESIGN.md §7).
 */

import React from 'react';
import { Audio, staticFile, useCurrentFrame } from 'remotion';
import { cl, pop, riseFade, zoomPunch, shake, flashAt, pulse, Sfx } from './fx';
import { Stage, Kicker, Watermark, ClaudeIcon, LifeSubBar, LIME, LIME_GLOW, ORANGE, RED, SUB } from './life';

export const KK_S3_L30_FRAMES = 2404;

const NUM = "'Archivo','Noto Sans KR',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

const SUBS = [
  { from: 0, to: 107, text: '요즘 유튜브에 나오는 것 중에', accent: '유튜브' },
  { from: 107, to: 233, text: 'AI가 알아서 타점 잡아준다는 프로그램 본 적 있으신가요?', accent: '타점 잡아준다' },
  { from: 233, to: 397, text: '근데 단언컨대, 주식판에 절대 치트키는 없습니다.', accent: '절대 치트키는 없습니다' },
  { from: 397, to: 530, text: 'AI가 로직 짜고 코드는 정말 잘 만들고', accent: '코드' },
  { from: 530, to: 602, text: '백테스팅 수없이 돌릴 수 있어요.', accent: '백테스팅' },
  { from: 602, to: 774, text: '하지만 아직 1%가 부족한, 인간의 도움이 필요하더라고요.', accent: '인간의 도움' },
  { from: 774, to: 905, text: '아시다시피 주식은 살아있는 생물이잖아요.', accent: '살아있는 생물' },
  { from: 905, to: 1012, text: '기계가 숫자만으로는 절대 예측 못하는', accent: '예측 못하는' },
  { from: 1012, to: 1135, text: '시장의 심리, 인간의 광기가 핵심입니다.', accent: '인간의 광기' },
  { from: 1135, to: 1290, text: '제가 아침에 자동화 프로그램을 여러 개 돌리고 있는데', accent: '자동화' },
  { from: 1290, to: 1441, text: '그 중 하나가 오늘 설명할 카톡 정보수집 프로그램이에요.', accent: '카톡 정보수집' },
  { from: 1441, to: 1610, text: '이것도 AI한테 종목 추천받으려는 게 아닙니다.', accent: '종목 추천' },
  { from: 1610, to: 1826, text: '장 열리기 전 우리가 하는 건, 너무나 단순 반복 일이거든요.', accent: '단순 반복' },
  { from: 1826, to: 1948, text: '이런 건 AI가 인간보다 월등히 잘합니다.', accent: '월등히 잘합니다' },
  { from: 1948, to: 2032, text: '바로 정보수집과 요약이죠.', accent: '정보수집과 요약' },
  { from: 2032, to: 2167, text: '이런 일들은 AI한테 모두 자동화 시켜버리고', accent: '자동화' },
  { from: 2167, to: 2291, text: '우리는 장 열렸을 때, 오늘 주도 섹터가 어디지?', accent: '주도 섹터' },
  { from: 2291, to: 2404, text: '돈은 어디로 가지? 이 흐름만 집중해서 보자는 겁니다.', accent: '이 흐름만 집중' },
];

// ── ambient: 흐르는 흐름선 (시장 = 유동성). 지구본 대체, 추상적. ──
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
    {/* 부유 광점 (위로 천천히 흐름) */}
    {Array.from({ length: 22 }).map((_, i) => {
      const x = (i * 97) % 1920;
      const y = (1080 - ((f * (0.5 + (i % 4) * 0.25) + i * 60) % 1140)) - 30;
      const op = 0.12 + (i % 3) * 0.06;
      return <div key={i} style={{ position: 'absolute', left: x, top: y, width: 3 + (i % 3), height: 3 + (i % 3), borderRadius: '50%', background: color, opacity: op, boxShadow: `0 0 8px ${color}` }} />;
    })}
  </div>
);

// 중앙 비트 래퍼
const Beat: React.FC<{ show: boolean; op: number; extra?: React.CSSProperties; children: React.ReactNode }> = ({ show, op, extra, children }) =>
  show ? (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingBottom: '13%', opacity: op, ...extra }}>
      {children}
    </div>
  ) : null;

const KICK: React.CSSProperties = { fontFamily: MONO, fontSize: 17, letterSpacing: 5, marginBottom: 18 };

export const KK_S3_L30: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <Stage>
      <Audio src={staticFile('kakao/ep1/s03_audio.mp4')} />
      <FlowField f={f} color={LIME} />
      <Kicker ch="CH 03" title="PHILOSOPHY" f={f} />

      <Sfx at={240} file="impact.mp3" vol={0.45} />
      <Sfx at={616} file="pop_appear.mp3" vol={0.32} />
      <Sfx at={1830} file="pop_appear.mp3" vol={0.32} />
      <Sfx at={1955} file="pop_appear.mp3" vol={0.32} />
      <Sfx at={2180} file="chime_up.mp3" vol={0.42} />

      {/* 컷 플래시 (환상파괴) */}
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, 236, 8, 0.35), pointerEvents: 'none' }} />

      {/* B1 미신 (0~233) */}
      <Beat show={f < 240} op={cl(f, 20, 50) * cl(f, 210, 233, 1, 0)}>
        <div style={{ ...KICK, color: RED }}>MYTH · 흔한 착각</div>
        <div style={{ fontSize: 52, fontWeight: 800, color: SUB, letterSpacing: -1 }}>AI가 알아서</div>
        <div style={{ fontSize: 104, fontWeight: 900, color: '#fff', letterSpacing: -3, lineHeight: 1.05 }}>
          타점을 <span style={{ color: RED, textShadow: `0 0 40px rgba(255,68,85,0.5)` }}>잡아준다?</span>
        </div>
      </Beat>

      {/* B2 치트키는 없다 (233~397) */}
      {f >= 233 && f < 397 && (() => {
        const sh = shake(f, 240, 20, 11);
        const punch = zoomPunch(f, 240, 1.14, 16);
        return (
          <Beat show op={cl(f, 236, 260) * cl(f, 372, 397, 1, 0)} extra={{ transform: `translate(${sh.x}px, ${sh.y}px) scale(${punch})` }}>
            <div style={{ ...KICK, color: RED }}>REALITY · 단언컨대</div>
            <div style={{ fontSize: 46, fontWeight: 700, color: SUB, letterSpacing: -1 }}>주식판에 절대</div>
            <div style={{ fontSize: 130, fontWeight: 900, color: RED, letterSpacing: -5, lineHeight: 1, textShadow: `0 0 60px rgba(255,68,85,0.6)` }}>치트키는 없다</div>
          </Beat>
        );
      })()}

      {/* B3 AI 인정 — 코드·백테는 잘한다 (397~602) */}
      <Beat show={f >= 397 && f < 602} op={cl(f, 400, 424) * cl(f, 577, 602, 1, 0)}>
        <div style={{ ...KICK, color: LIME }}>FACT · AI가 잘하는 것</div>
        <div style={{ fontSize: 62, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>
          <span style={{ color: LIME, textShadow: `0 0 30px ${LIME_GLOW}` }}>코드</span>는 진짜 잘 짠다
        </div>
        <div style={{ display: 'flex', gap: 18, marginTop: 28 }}>
          {[{ t: '✓ 로직 설계', at: 410 }, { t: '✓ 백테스팅 무한 반복', at: 530 }].map((c, i) => {
            const { opacity, y } = riseFade(f, c.at, 12, 36);
            return (
              <div key={i} style={{ opacity, transform: `translateY(${y}px)`, padding: '16px 30px', background: 'rgba(0,0,0,0.5)', border: `1.5px solid ${LIME}`, borderRadius: 14, fontSize: 32, fontWeight: 800, color: '#fff' }}>{c.t}</div>
            );
          })}
        </div>
      </Beat>

      {/* B4 1% 반전 (602~774) */}
      {f >= 602 && f < 774 && (() => {
        const punch = zoomPunch(f, 616, 1.16, 16);
        return (
          <Beat show op={cl(f, 606, 632) * cl(f, 749, 774, 1, 0)}>
            <div style={{ fontSize: 44, fontWeight: 700, color: SUB }}>하지만 아직</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, transform: `scale(${punch})` }}>
              <span style={{ fontFamily: NUM, fontSize: 170, fontWeight: 900, color: ORANGE, letterSpacing: -6, lineHeight: 1, textShadow: `0 0 50px rgba(217,119,87,0.6)` }}>1%</span>
              <span style={{ fontSize: 56, fontWeight: 900, color: '#fff' }}>가 부족하다</span>
            </div>
            <div style={{ fontSize: 34, fontWeight: 700, color: SUB, marginTop: 12 }}>그 1%, <span style={{ color: ORANGE }}>인간의 도움</span>이 필요</div>
          </Beat>
        );
      })()}

      {/* B5 살아있는 생물 (774~1012) */}
      <Beat show={f >= 774 && f < 1012} op={cl(f, 778, 805) * cl(f, 987, 1012, 1, 0)}>
        <div style={{ ...KICK, color: LIME }}>WHY · 숫자로 못 푸는 것</div>
        <div style={{ fontSize: 76, fontWeight: 900, color: '#fff', letterSpacing: -2, lineHeight: 1.1 }}>
          주식은 <span style={{ color: LIME, textShadow: `0 0 40px ${LIME_GLOW}` }}>살아있는 생물</span>
        </div>
      </Beat>

      {/* B6 인간의 광기 (1012~1135) */}
      {f >= 1012 && f < 1135 && (
        <Beat show op={cl(f, 1015, 1042) * cl(f, 1110, 1135, 1, 0)} extra={{ transform: `scale(${pulse(f, 0.13, 0.98, 0.04)})` }}>
          <div style={{ fontSize: 50, fontWeight: 800, color: SUB }}>기계가 숫자로 못 푸는</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 20, marginTop: 8 }}>
            <span style={{ fontSize: 64, fontWeight: 900, color: '#fff' }}>시장의 심리</span>
            <span style={{ fontSize: 88, fontWeight: 900, color: ORANGE, letterSpacing: -2, textShadow: `0 0 44px rgba(217,119,87,0.6)` }}>인간의 광기</span>
          </div>
        </Beat>
      )}

      {/* B7 카톡 정보수집 소개 + ❌종목추천 (1135~1610) */}
      <Beat show={f >= 1135 && f < 1610} op={cl(f, 1139, 1166) * cl(f, 1585, 1610, 1, 0)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 22 }}>
          <ClaudeIcon size={52} />
          <div style={{ fontSize: 52, fontWeight: 900, color: '#fff', letterSpacing: -1 }}>그래서 AI에겐, 이 일을</div>
        </div>
        {/* 1290~ 카톡 정보수집 칩 */}
        {(() => { const { opacity, y } = riseFade(f, 1300, 14, 36); return (
          <div style={{ opacity, transform: `translateY(${y}px)`, padding: '18px 36px', background: 'rgba(0,0,0,0.5)', border: `2px solid ${LIME}`, borderRadius: 16, fontSize: 40, fontWeight: 900, color: '#fff', boxShadow: `0 0 30px ${LIME}22` }}>
            💬 <span style={{ color: LIME }}>카톡 정보수집</span> 자동화
          </div>
        ); })()}
        {/* 1441~ ❌ 종목추천 아님 */}
        {(() => { const { opacity, y } = riseFade(f, 1450, 14, 30); return (
          <div style={{ opacity, transform: `translateY(${y}px)`, marginTop: 22, fontSize: 36, fontWeight: 800, color: SUB }}>
            <span style={{ color: RED, textDecoration: 'line-through', textDecorationColor: RED }}>종목 추천</span> 받으려는 게 아니다
          </div>
        ); })()}
      </Beat>

      {/* B8 AI가 월등한 영역 (1610~2032) — 단순반복→헤드→정보수집·요약 카드 */}
      <Beat show={f >= 1610 && f < 2032} op={cl(f, 1614, 1640) * cl(f, 2007, 2032, 1, 0)}>
        {/* 1610~1845: 단순 반복 강조 (헤드 등장 전) */}
        {f < 1845 ? (
          <div style={{ opacity: cl(f, 1614, 1640) * cl(f, 1820, 1845, 1, 0), fontSize: 70, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>
            장 열기 전 = <span style={{ color: LIME, textShadow: `0 0 36px ${LIME_GLOW}` }}>단순 반복</span>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 26, opacity: cl(f, 1845, 1872) }}>
              <ClaudeIcon size={50} />
              <div style={{ fontSize: 56, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>
                AI는 이걸 <span style={{ color: LIME, textShadow: `0 0 32px ${LIME_GLOW}` }}>월등히</span> 잘한다
              </div>
            </div>
            <div style={{ display: 'flex', gap: 24 }}>
              {[{ ic: '🔁', t: '단순 반복', at: 1850 }, { ic: '🔍', t: '정보 수집', at: 1955 }, { ic: '📝', t: '요약·정리', at: 1990 }].map((it, i) => {
                const { opacity, y } = riseFade(f, it.at, 12, 40);
                const p = pop(f, it.at, { damping: 8 });
                return (
                  <div key={i} style={{ opacity, transform: `translateY(${y}px) scale(${0.85 + p * 0.15})`, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '26px 38px', background: 'rgba(0,0,0,0.5)', border: `2px solid ${LIME}`, borderRadius: 18, boxShadow: `0 0 30px ${LIME}22` }}>
                    <span style={{ fontSize: 52 }}>{it.ic}</span>
                    <span style={{ fontSize: 34, fontWeight: 900, color: '#fff', whiteSpace: 'nowrap' }}>{it.t}</span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </Beat>

      {/* B9 자동화 위임 → FOCUS (2032~2404) */}
      {f >= 2032 && (
        <>
          {/* 2032~2167 위임 */}
          <Beat show={f < 2185} op={cl(f, 2036, 2062) * cl(f, 2160, 2185, 1, 0)}>
            <div style={{ fontSize: 64, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>
              이건 전부 <span style={{ color: LIME, textShadow: `0 0 32px ${LIME_GLOW}` }}>AI에게 자동화</span>
            </div>
            <div style={{ fontSize: 36, fontWeight: 700, color: SUB, marginTop: 12 }}>맡겨버리고</div>
          </Beat>
          {/* 2167~ FOCUS 클라이맥스 */}
          {f >= 2167 && (() => {
            const punch = zoomPunch(f, 2185, 1.1, 18);
            return (
              <Beat show op={cl(f, 2171, 2197)} extra={{ transform: `scale(${punch})` }}>
                <div style={{ ...KICK, color: LIME, fontSize: 18, letterSpacing: 6 }}>FOCUS · 우리가 볼 것</div>
                <div style={{ fontSize: 74, fontWeight: 900, color: '#fff', letterSpacing: -2, lineHeight: 1.12 }}>오늘 주도 섹터는 어디?</div>
                <div style={{ fontSize: 94, fontWeight: 900, color: LIME, letterSpacing: -3, lineHeight: 1.12, marginTop: 8, textShadow: `0 0 50px ${LIME_GLOW}` }}>돈은 어디로 가는가</div>
              </Beat>
            );
          })()}
        </>
      )}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
    </Stage>
  );
};
