/**
 * KK_S6 — STEP 2: MCP 개념 설명
 *
 * ⚠️ SUBS 타이밍은 추정값 — 녹화 후 Whisper 출력으로 교체
 *
 * 대본 요약:
 *   f0~90    MCP가 뭔지 딱 쉽게 짚고 갈게요.
 *   f90~240  AI한테 네이버 검색·카톡 보내려면 개발자+수백만원 코딩.
 *   f240~330 네이버랑 카카오 통신 언어가 아예 다르니까요.
 *   f330~480 충전기 5핀·8핀·24핀 따로 쓰던 시절 기억하시죠?
 *   f480~630 USB-C 대통합 규격 = 앤트로픽의 MCP
 *   f630~780 PlayMCP = 모든 국내 서비스 꽂을 수 있는 멀티 허브
 *   f780~900 Claude가 네이버도 카톡도 딸깍 하나로 처리합니다.
 */

import React from 'react';
import { SceneBase, ClaudeLogo } from './SceneBase';
import { ci, sp, panelOp, slideX, panelStyle, kickerStyle, LIME, LIME50, LIME20, RED, CARD, BORDER } from './theme';

export const KK_S6_FRAMES = 900;

// ── ⚠️ 녹화 후 Whisper 세그먼트로 교체 ──
const SUBS = [
  { from: 0,   to: 90,  text: "MCP가 뭔지만 딱 쉽게 짚고 갈게요.",                        accent: 'MCP' },
  { from: 90,  to: 240, text: "AI한테 시키려면 개발자 불러 수백만 원 코딩 짜야 했습니다.",  accent: '수백만 원' },
  { from: 240, to: 330, text: "네이버랑 카카오 통신 언어가 아예 다르니까요.",               accent: '아예 다르니까요' },
  { from: 330, to: 480, text: "충전기 5핀·8핀·24핀 따로 쓰던 시절 기억하시죠?",            accent: '따로 쓰던' },
  { from: 480, to: 630, text: "USB-C 대통합 규격이 바로 앤트로픽의 MCP입니다.",             accent: 'MCP' },
  { from: 630, to: 780, text: "PlayMCP는 모든 국내 서비스를 꽂을 수 있는 멀티 허브입니다.", accent: '멀티 허브' },
  { from: 780, to: 900, text: "Claude가 네이버도 카톡도 딸깍 하나로 처리합니다.",           accent: '딸깍 하나로' },
];

// ── 옛날 충전기 목록 (Before) ──
const OLD_CONNECTORS = [
  { icon: '🔌', label: '5핀',  sub: '삼성 구형',     delay: 345, color: 'rgba(255,100,100,0.9)' },
  { icon: '🔌', label: '8핀',  sub: 'Apple Lightning', delay: 365, color: 'rgba(255,130,80,0.9)' },
  { icon: '🔌', label: '24핀', sub: 'Micro USB',      delay: 385, color: 'rgba(255,160,60,0.9)' },
];

// ── PlayMCP 연결 서비스 목록 ──
const SERVICES = [
  { icon: '🟢', label: '네이버',    sub: '뉴스·쇼핑·증권',  delay: 645 },
  { icon: '🟡', label: '카카오톡', sub: '나채팅방 전송',    delay: 665 },
  { icon: '🔵', label: '유튜브',   sub: '트렌드·자막 분석', delay: 685 },
  { icon: '⚪', label: 'OpenDART', sub: '공시·재무데이터',  delay: 705 },
];

export const KK_S6_MCP: React.FC = () => (
  <SceneBase video="kakao/ep1/s06_bg.mp4" subs={SUBS}>
    {(f) => {
      const phase1Op = panelOp(f, 5, 320);
      const phase1Scale = 0.82 + sp(f, 5, 8, 280, 0.6) * 0.18;

      const beforeOp = panelOp(f, 325, 625);
      const afterOp  = panelOp(f, 475, 625);

      const playmcpOp    = panelOp(f, 630, 870);
      const playmcpROp   = panelOp(f, 660, 870);

      const impactOp    = panelOp(f, 875, 900);
      const impactScale = 0.78 + sp(f, 875, 7, 290, 0.5) * 0.22;

      return (
        <>
          {/* ══ Phase 1: 문제 제기 훅 카드 (f5~320) ══ */}
          <div style={{
            position: 'absolute', top: 80, left: '50%',
            transform: `translateX(-50%) scale(${phase1Scale})`,
            transformOrigin: 'center top',
            ...panelStyle({ position: 'relative', width: 720, padding: 0 }),
            opacity: phase1Op,
          }}>
            <div style={{ ...kickerStyle, display: 'flex', alignItems: 'center', gap: 10 }}>
              <ClaudeLogo size={28} />
              <span>STEP 2 · MCP 개념 설명</span>
            </div>
            <div style={{ padding: '16px 24px' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', lineHeight: 1.55 }}>
                AI한테 <span style={{ color: LIME }}>"네이버 검색해서 카톡으로 보내"</span>
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', lineHeight: 1.55, marginBottom: 14 }}>
                하려면?
              </div>
              <div style={{
                background: 'rgba(255,68,85,0.1)', border: '1px solid rgba(255,68,85,0.3)',
                borderRadius: 4, padding: '10px 16px',
                fontSize: 15, fontWeight: 700, color: 'rgba(255,120,120,0.9)',
                opacity: ci(f, 95, 115),
              }}>
                ❌ 개발자 + 수백만 원 코딩 → 네이버·카카오 통신 언어가 달라서
              </div>
            </div>
          </div>

          {/* ══ Phase 2 LEFT: Before — 파편화 (f325~625) ══ */}
          <div style={{
            ...panelStyle({ left: 36, top: 80, width: 380, height: 280 }),
            opacity: beforeOp,
            transform: `translateX(${slideX(f, 325, -1)}px)`,
          }}>
            <div style={kickerStyle}>BEFORE · 파편화 지옥</div>
            <div style={{ padding: '8px 18px 4px', fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.38)', opacity: ci(f, 330, 346) }}>
              서비스마다 다른 언어·규격
            </div>
            {OLD_CONNECTORS.map((c, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 18px',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                opacity: ci(f, c.delay, c.delay + 18),
              }}>
                <span style={{ fontSize: 20 }}>{c.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: c.color }}>{c.label}</div>
                  <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9, color: 'rgba(255,255,255,0.3)', letterSpacing: 1.5 }}>{c.sub}</div>
                </div>
                <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9, color: 'rgba(255,80,80,0.8)', opacity: ci(f, c.delay + 16, c.delay + 28) }}>별도 연동</span>
              </div>
            ))}
          </div>

          {/* ══ Phase 2 RIGHT: After — MCP 대통합 (f475~625) ══ */}
          <div style={{
            ...panelStyle({ right: 36, top: 80, width: 340, height: 220 }),
            opacity: afterOp,
            transform: `translateX(${slideX(f, 475, 1)}px)`,
            padding: '20px 22px',
            display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9, color: LIME50, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 12 }}>
              AFTER · 대통합
            </div>
            <div style={{ fontSize: 42, fontWeight: 900, letterSpacing: -1, color: LIME,
              textShadow: `0 0 24px rgba(170,255,0,0.6)`, marginBottom: 8 }}>
              USB-C
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.6)', lineHeight: 1.5 }}>
              하나로 전부 연결<br />
              <span style={{ color: LIME }}>MCP = 이 개념</span>
            </div>
            <div style={{
              height: 2, background: LIME, borderRadius: 1, marginTop: 14,
              width: `${ci(f, 510, 550, 0, 100)}%`,
              boxShadow: `0 0 10px ${LIME50}`,
            }} />
          </div>

          {/* ══ Phase 3 LEFT: PlayMCP 소개 (f630~870) ══ */}
          <div style={{
            ...panelStyle({ left: 36, top: 80, width: 460, height: 320 }),
            opacity: playmcpOp,
            transform: `translateX(${slideX(f, 630, -1)}px)`,
          }}>
            <div style={{ ...kickerStyle, display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 20 }}>🔌</span>
              <span>PlayMCP · 멀티 허브</span>
            </div>
            <div style={{ padding: '8px 18px 4px', fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.38)', opacity: ci(f, 635, 650) }}>
              국내 서비스 전부 꽂을 수 있는 허브
            </div>
            {SERVICES.map((s, i) => {
              const rowOp  = ci(f, s.delay, s.delay + 18);
              const doneOp = ci(f, s.delay + 16, s.delay + 28);
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '10px 18px',
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                  opacity: rowOp,
                }}>
                  <span style={{ fontSize: 18 }}>{s.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>{s.label}</div>
                    <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9, color: 'rgba(255,255,255,0.35)', letterSpacing: 1.5 }}>{s.sub}</div>
                  </div>
                  <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9, color: LIME, opacity: doneOp,
                    textShadow: `0 0 8px ${LIME50}` }}>✓ 연결</span>
                </div>
              );
            })}
          </div>

          {/* ══ Phase 3 RIGHT: Claude 처리 결과 (f660~870) ══ */}
          <div style={{
            ...panelStyle({ right: 36, top: 80, width: 340, height: 230 }),
            opacity: playmcpROp,
            transform: `translateX(${slideX(f, 660, 1)}px)`,
            padding: '22px 24px',
            display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9, color: LIME50, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 14 }}>
              RESULT · 처리 결과
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <ClaudeLogo size={38} />
              <div style={{ fontSize: 18, fontWeight: 800, color: '#fff', lineHeight: 1.4 }}>
                Claude가<br />전부 처리
              </div>
            </div>
            <div style={{
              background: LIME20, border: `1px solid ${LIME50}`,
              borderRadius: 4, padding: '8px 14px',
              fontFamily: "'Courier New',monospace", fontSize: 11,
              color: LIME, letterSpacing: 1.5, textAlign: 'center',
              opacity: ci(f, 720, 738),
            }}>
              딸깍 하나로 ✓
            </div>
          </div>

          {/* ══ Phase 4: 임팩트 (f875~900) ══ */}
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            paddingBottom: '12%',
            opacity: impactOp,
            transform: `scale(${impactScale})`,
          }}>
            <div style={{ fontFamily: "'Courier New',monospace", fontSize: 12, color: LIME50, letterSpacing: 4, textTransform: 'uppercase', marginBottom: 12 }}>
              MCP · 핵심 정리
            </div>
            <div style={{ fontSize: 72, fontWeight: 900, color: '#fff', letterSpacing: -3, textAlign: 'center',
              textShadow: '0 6px 28px rgba(0,0,0,0.95)' }}>
              딸깍 하나로
            </div>
            <div style={{ fontSize: 72, fontWeight: 900, color: LIME, letterSpacing: -3,
              textShadow: `0 0 40px rgba(170,255,0,0.6)` }}>
              전부 처리
            </div>
          </div>
        </>
      );
    }}
  </SceneBase>
);
