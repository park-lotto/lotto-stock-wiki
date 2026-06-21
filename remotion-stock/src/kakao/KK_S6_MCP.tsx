/**
 * KK_S6_MCP — MCP 설명 (1952f · 모드 C 리모션 단독)
 * 오디오(s06_audio) + 검정 무대. 자막 8줄 한 줄마다 중앙 그래픽이 호응(이탈 0).
 * Play MCP 소개 → MCP가 뭔지 → AI에 일 시키기 → 옛날의 고통(개발자·코딩)
 * → 회사마다 규격 제각각 → 충전기 5핀8핀 비유 → USB-C 대통합 = MCP → 멀티 허브
 *
 * 자막 = Whisper 1:1 타이밍 (ASR 오타만 교정: 주직정보→주식정보·먼지만→뭔지만·통영→통하는).
 * 골든 레퍼런스: KK_S3_L30.tsx
 */

import React from 'react';
import { Audio, staticFile, useCurrentFrame } from 'remotion';
import { cl, pop, riseFade, zoomPunch, shake, flashAt, pulse, Sfx } from './fx';
import { Stage, Kicker, Watermark, ClaudeIcon, LifeSubBar, LIME, LIME_GLOW, ORANGE, RED, SUB } from './life';

export const KK_S6_FRAMES = 1952;

const NUM = "'Archivo','Noto Sans KR',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

const SUBS = [
  { from: 0, to: 173, text: '이제 프로그램을 하나 더 받을 건데 Play MCP라는 기능입니다.', accent: 'Play MCP' },
  { from: 173, to: 316, text: '개발용어 다 빼고 MCP라는 게 뭔지만 잠깐 들어볼게요.', accent: 'MCP라는 게 뭔지' },
  { from: 316, to: 564, text: 'AI한테 "주식 뉴스 네이버 검색해서 카톡으로 보내" 라고 시키면', accent: '카톡으로 보내' },
  { from: 564, to: 740, text: '예전엔 개발자 불러서, 돈 주고 코딩을 새로 짜야 했어요.', accent: '돈 주고 코딩' },
  { from: 740, to: 976, text: '네이버·카카오 모든 회사가 AI를 불러 쓰는 구조가 다 달랐거든요.', accent: '다 달랐거든요' },
  { from: 976, to: 1202, text: '옛날 충전기 5핀·8핀 다 따로 쓰던 거 기억나시죠?', accent: '5핀·8핀' },
  { from: 1202, to: 1576, text: 'USB-C 하나로 대통합한 것처럼, AI의 USB-C가 바로 MCP입니다. 쉽죠?', accent: 'AI의 USB-C가 바로 MCP' },
  { from: 1576, to: 1952, text: 'Play MCP는 국내 서비스에 다 통하는 멀티 허브. 꽂아두면 네이버도 카톡도 딸깍.', accent: '멀티 허브' },
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

// 칩 카드 (라벨)
const Chip: React.FC<{ f: number; at: number; color?: string; children: React.ReactNode; big?: boolean }> = ({ f, at, color = LIME, children, big }) => {
  const { opacity, y } = riseFade(f, at, 12, 34);
  const p = pop(f, at, { damping: 8, stiffness: 240 });
  return (
    <div style={{ opacity, transform: `translateY(${y}px) scale(${0.85 + p * 0.15})`, display: 'flex', alignItems: 'center', gap: 12, padding: big ? '20px 38px' : '14px 26px', background: 'rgba(0,0,0,0.55)', border: `2px solid ${color}`, borderRadius: 16, fontSize: big ? 44 : 32, fontWeight: 900, color: '#fff', whiteSpace: 'nowrap', boxShadow: `0 0 28px ${color}22` }}>
      {children}
    </div>
  );
};

export const KK_S6_MCP: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <Stage>
      <Audio src={staticFile('kakao/ep1/s06_audio.mp4')} />
      <FlowField f={f} color={LIME} />
      <Kicker ch="CH 06" title="MCP" f={f} />

      <Sfx at={60} file="pop_appear.mp3" vol={0.3} />
      <Sfx at={580} file="impact.mp3" vol={0.4} />
      <Sfx at={990} file="pop_appear.mp3" vol={0.3} />
      <Sfx at={1240} file="impact.mp3" vol={0.42} />
      <Sfx at={1300} file="chime_up.mp3" vol={0.45} />
      <Sfx at={1600} file="pop_appear.mp3" vol={0.34} />

      {/* 컷 플래시 (충전기→USB-C 통합 순간) */}
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, 1240, 9, 0.4), pointerEvents: 'none' }} />

      {/* B1 — Play MCP 소개 (0~173) */}
      <Beat show={f < 180} op={cl(f, 8, 34) * cl(f, 150, 173, 1, 0)}>
        <div style={{ ...KICK, color: LIME }}>STEP · 하나만 더 설치</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 30 }}>
          <ClaudeIcon size={56} />
          <div style={{ fontSize: 64, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>프로그램 하나만 더</div>
        </div>
        <Chip f={f} at={60} big>🔌 <span style={{ color: LIME, textShadow: `0 0 24px ${LIME_GLOW}` }}>Play MCP</span></Chip>
      </Beat>

      {/* B2 — MCP가 뭔지 (173~316) */}
      {f >= 173 && f < 316 && (
        <Beat show op={cl(f, 177, 203) * cl(f, 293, 316, 1, 0)} extra={{ transform: `scale(${pulse(f, 0.1, 0.99, 0.02)})` }}>
          <div style={{ ...KICK, color: ORANGE }}>WHAT IS · 개발용어 0</div>
          <div style={{ fontSize: 200, fontWeight: 900, color: '#fff', letterSpacing: -8, lineHeight: 1, textShadow: `0 0 50px rgba(255,255,255,0.15)` }}>
            MCP<span style={{ color: ORANGE, textShadow: `0 0 40px ${ORANGE}88` }}>?</span>
          </div>
          <div style={{ fontSize: 40, fontWeight: 700, color: SUB, marginTop: 14 }}>딱 1분만 들어보세요</div>
        </Beat>
      )}

      {/* B3 — AI에 일 시키기 (316~564) */}
      <Beat show={f >= 316 && f < 564} op={cl(f, 320, 346) * cl(f, 541, 564, 1, 0)}>
        <div style={{ ...KICK, color: LIME }}>WISH · 이렇게 시키고 싶다</div>
        {/* 명령 말풍선 */}
        {(() => { const { opacity, y } = riseFade(f, 330, 14, 36); return (
          <div style={{ opacity, transform: `translateY(${y}px)`, padding: '24px 40px', background: 'rgba(0,0,0,0.6)', border: `2px solid ${ORANGE}`, borderRadius: 22, fontSize: 46, fontWeight: 800, color: '#fff', marginBottom: 40, maxWidth: 1100, textAlign: 'center', boxShadow: `0 0 30px ${ORANGE}33` }}>
            💬 "주식 뉴스 <span style={{ color: LIME }}>네이버</span>에서 찾아서 <span style={{ color: LIME }}>카톡</span>으로 보내줘"
          </div>
        ); })()}
        {/* 흐름: 네이버 → 카톡 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 26 }}>
          <Chip f={f} at={430} color={LIME} big>🔍 네이버 검색</Chip>
          {(() => { const a = cl(f, 470, 488); return <span style={{ fontSize: 56, color: ORANGE, opacity: a, transform: `translateX(${(1 - a) * -20}px)`, display: 'inline-block' }}>→</span>; })()}
          <Chip f={f} at={490} color={LIME} big>💬 카톡 전송</Chip>
        </div>
      </Beat>

      {/* B4 — 옛날의 고통 (564~740) */}
      {f >= 564 && f < 740 && (() => {
        const sh = shake(f, 580, 18, 8);
        return (
          <Beat show op={cl(f, 568, 594) * cl(f, 717, 740, 1, 0)} extra={{ transform: `translate(${sh.x}px, ${sh.y}px)` }}>
            <div style={{ ...KICK, color: RED }}>OLD WAY · 예전엔</div>
            <div style={{ fontSize: 62, fontWeight: 900, color: '#fff', letterSpacing: -2, marginBottom: 30 }}>자동화 하나 하려면…</div>
            <div style={{ display: 'flex', gap: 28 }}>
              <Chip f={f} at={600} color={RED} big>👨‍💻 개발자 호출</Chip>
              <Chip f={f} at={650} color={RED} big>💸 돈 주고 코딩</Chip>
            </div>
          </Beat>
        );
      })()}

      {/* B5 — 회사마다 규격 제각각 (740~976) */}
      <Beat show={f >= 740 && f < 976} op={cl(f, 744, 770) * cl(f, 953, 976, 1, 0)}>
        <div style={{ ...KICK, color: RED }}>WHY · 호출 규격이</div>
        <div style={{ fontSize: 72, fontWeight: 900, color: '#fff', letterSpacing: -2, marginBottom: 36 }}>
          회사마다 <span style={{ color: RED, textShadow: `0 0 40px rgba(255,68,85,0.5)` }}>제각각</span>
        </div>
        <div style={{ display: 'flex', gap: 24 }}>
          {[{ t: '네이버', ic: '🟢', at: 800 }, { t: '카카오', ic: '🟡', at: 850 }, { t: '구글', ic: '🔵', at: 900 }].map((c, i) => {
            const { opacity, y } = riseFade(f, c.at, 12, 34);
            return (
              <div key={i} style={{ opacity, transform: `translateY(${y}px)`, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, padding: '24px 34px', background: 'rgba(0,0,0,0.5)', border: `2px solid ${RED}`, borderRadius: 16 }}>
                <span style={{ fontSize: 50 }}>{c.ic}</span>
                <span style={{ fontSize: 30, fontWeight: 900, color: '#fff' }}>{c.t}</span>
                <span style={{ fontFamily: MONO, fontSize: 18, color: RED }}>✕ 규격 다름</span>
              </div>
            );
          })}
        </div>
      </Beat>

      {/* B6 — 충전기 비유 (976~1202) */}
      <Beat show={f >= 976 && f < 1202} op={cl(f, 980, 1006) * cl(f, 1179, 1202, 1, 0)}>
        <div style={{ ...KICK, color: ORANGE }}>옛날 생각 · 기억나시죠?</div>
        <div style={{ fontSize: 64, fontWeight: 900, color: '#fff', letterSpacing: -2, marginBottom: 36 }}>📱 충전기 단자가 다 따로</div>
        <div style={{ display: 'flex', gap: 22 }}>
          {[{ t: '5핀', at: 1030 }, { t: '8핀', at: 1070 }, { t: '마이크로', at: 1110 }].map((c, i) => {
            const { opacity, y } = riseFade(f, c.at, 12, 32);
            const p = pop(f, c.at, { damping: 7 });
            return (
              <div key={i} style={{ opacity, transform: `translateY(${y}px) scale(${0.85 + p * 0.15}) rotate(${(i - 1) * 4}deg)`, padding: '22px 40px', background: 'rgba(0,0,0,0.5)', border: `2px solid ${ORANGE}`, borderRadius: 14, fontSize: 44, fontWeight: 900, color: '#fff' }}>
                🔌 {c.t}
              </div>
            );
          })}
        </div>
        <div style={{ opacity: cl(f, 1140, 1165), fontSize: 34, fontWeight: 700, color: SUB, marginTop: 28 }}>전부 따로따로… 너무 불편했죠</div>
      </Beat>

      {/* B7 — USB-C 대통합 = MCP (1202~1576) CLIMAX */}
      {f >= 1202 && f < 1576 && (() => {
        const punch = zoomPunch(f, 1240, 1.18, 20);
        return (
          <Beat show op={cl(f, 1206, 1232) * cl(f, 1553, 1576, 1, 0)}>
            <div style={{ ...KICK, color: LIME }}>BIG MERGE · 대통합</div>
            <div style={{ fontSize: 50, fontWeight: 700, color: SUB, marginBottom: 6 }}>이걸 하나로 합친 게</div>
            <div style={{ transform: `scale(${punch})`, fontFamily: NUM, fontSize: 180, fontWeight: 900, color: LIME, letterSpacing: -8, lineHeight: 1, textShadow: `0 0 60px ${LIME_GLOW}` }}>USB-C</div>
            {/* = MCP 리빌 */}
            {f >= 1300 && (() => { const p = pop(f, 1300, { damping: 8 }); return (
              <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginTop: 24, transform: `scale(${0.7 + p * 0.3})`, opacity: cl(f, 1300, 1316) }}>
                <span style={{ fontSize: 80, fontWeight: 900, color: SUB }}>= AI의</span>
                <span style={{ fontFamily: NUM, fontSize: 150, fontWeight: 900, color: '#fff', letterSpacing: -6, textShadow: `0 0 50px rgba(255,255,255,0.25)` }}>MCP</span>
              </div>
            ); })()}
            {/* 쉽죠? */}
            {f >= 1500 && (
              <div style={{ opacity: cl(f, 1500, 1520), fontSize: 48, fontWeight: 900, color: ORANGE, marginTop: 26, transform: `scale(${pulse(f, 0.16, 0.98, 0.04)})`, textShadow: `0 0 30px ${ORANGE}88` }}>쉽죠? 😎</div>
            )}
          </Beat>
        );
      })()}

      {/* B8 — Play MCP = 멀티 허브 (1576~1952) */}
      {f >= 1576 && (() => {
        const nodes = [
          { t: '네이버', ic: '🟢', at: 1660 },
          { t: '카톡', ic: '💬', at: 1700 },
          { t: '뉴스', ic: '📰', at: 1740 },
          { t: '검색', ic: '🔍', at: 1780 },
        ];
        return (
          <Beat show op={cl(f, 1580, 1606)}>
            <div style={{ ...KICK, color: LIME }}>PLAY MCP · 멀티 허브</div>
            <div style={{ fontSize: 64, fontWeight: 900, color: '#fff', letterSpacing: -2, marginBottom: 12 }}>
              꽂아두면 클로드가 <span style={{ color: LIME, textShadow: `0 0 32px ${LIME_GLOW}` }}>딸깍</span>
            </div>
            {/* 허브: 클로드 중앙 + 노드 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginTop: 30 }}>
              <div style={{ transform: `scale(${1 + pulse(f, 0.1, 0, 0.04)})`, padding: 8, borderRadius: 24, boxShadow: `0 0 40px ${ORANGE}66` }}>
                <ClaudeIcon size={92} />
              </div>
              <span style={{ fontSize: 52, color: LIME, opacity: cl(f, 1640, 1660) }}>⇄</span>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                {nodes.map((n, i) => {
                  const { opacity, y } = riseFade(f, n.at, 12, 28);
                  return (
                    <div key={i} style={{ opacity, transform: `translateY(${y}px)`, display: 'flex', alignItems: 'center', gap: 10, padding: '14px 24px', background: 'rgba(0,0,0,0.55)', border: `2px solid ${LIME}`, borderRadius: 14, fontSize: 30, fontWeight: 900, color: '#fff', whiteSpace: 'nowrap' }}>
                      <span style={{ fontSize: 34 }}>{n.ic}</span>{n.t}
                    </div>
                  );
                })}
              </div>
            </div>
            <div style={{ opacity: cl(f, 1840, 1865), fontSize: 38, fontWeight: 800, color: SUB, marginTop: 34 }}>
              국내 서비스 <span style={{ color: LIME }}>전부</span> 한 방에
            </div>
          </Beat>
        );
      })()}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
    </Stage>
  );
};
