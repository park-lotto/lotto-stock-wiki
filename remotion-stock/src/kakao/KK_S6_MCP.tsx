/**
 * KK_S6_MCP — MCP 개념 (1952f · 순수 그래픽, 녹음 배경)
 * Whisper 8세그 자막 + 충전기→USB-C→PlayMCP 그래픽 4페이즈.
 *
 * 에셋 도착 후: BG = 'kakao/ep1/s06_bg.mp4'
 */

import React from 'react';
import { SceneBase, ClaudeLogo } from './SceneBase';
import { ci, sp, panelOp, slideX, panelStyle, kickerStyle, LIME, LIME50, LIME20 } from './theme';
import { Sfx, type Sub } from './fx';

export const KK_S6_FRAMES = 1952;

const BG: string | null = null; // 에셋 도착 시 'kakao/ep1/s06_bg.mp4'

const SUBS: Sub[] = [
  { from: 0, to: 173, text: '이제 Play MCP라는 기능을 하나 더 받을 거예요.', accent: 'Play MCP' },
  { from: 173, to: 316, text: '개발 용어 다 빼고, MCP가 뭔지만 짚을게요.', accent: 'MCP' },
  { from: 316, to: 564, text: "AI한테 '네이버 검색해서 카톡으로 보내' 시키면", accent: '네이버 검색' },
  { from: 564, to: 740, text: '원래는 개발자 불러 돈 주고 코딩을 새로 짜야 했어요.', accent: '개발자' },
  { from: 740, to: 976, text: '네이버·카카오가 AI를 호출하는 구조가 다 달랐거든요.', accent: '구조가 다 달랐' },
  { from: 976, to: 1202, text: '옛날에 충전기 5핀·8핀 따로 쓰던 거 기억나시죠?', accent: '5핀·8핀' },
  { from: 1202, to: 1576, text: '그걸 USB-C로 통합하듯, AI의 USB-C가 바로 MCP예요.', accent: 'MCP' },
  { from: 1576, to: 1952, text: 'PlayMCP는 국내 서비스 다 꽂는 멀티 허브입니다.', accent: '멀티 허브' },
];

const OLD_CONNECTORS = [
  { icon: '🔌', label: '5핀', sub: '삼성 구형', delay: 1010, color: 'rgba(255,100,100,0.9)' },
  { icon: '🔌', label: '8핀', sub: 'Lightning', delay: 1035, color: 'rgba(255,130,80,0.9)' },
  { icon: '🔌', label: '24핀', sub: 'Micro USB', delay: 1060, color: 'rgba(255,160,60,0.9)' },
];

const SERVICES = [
  { icon: '🟢', label: '네이버', sub: '뉴스·증권', delay: 1600 },
  { icon: '🟡', label: '카카오톡', sub: '나채팅방', delay: 1625 },
  { icon: '🔵', label: '유튜브', sub: '트렌드', delay: 1650 },
  { icon: '⚪', label: 'OpenDART', sub: '공시·재무', delay: 1675 },
];

export const KK_S6_MCP: React.FC = () => (
  <SceneBase video={BG} audio="kakao/ep1/s06_audio.mp4" subs={SUBS} dim={0.15}>
    {(f) => {
      const hookOp = panelOp(f, 320, 970);
      const hookScale = 0.82 + sp(f, 320, 8, 280, 0.6) * 0.18;
      const beforeOp = panelOp(f, 978, 1200);
      const afterOp = panelOp(f, 1206, 1576);
      const playOp = panelOp(f, 1580, 1900);
      const playROp = panelOp(f, 1610, 1900);
      const impactOp = panelOp(f, 1830, 1952);
      const impactScale = 0.78 + sp(f, 1830, 7, 290, 0.5) * 0.22;

      return (
        <>
          <Sfx at={320} file="pop_appear.mp3" vol={0.35} />
          {OLD_CONNECTORS.map((c, i) => (
            <Sfx key={i} at={c.delay} file="tick.mp3" vol={0.28} />
          ))}
          <Sfx at={1230} file="impact.mp3" vol={0.4} />
          {SERVICES.map((s, i) => (
            <Sfx key={`s${i}`} at={s.delay} file="tick.mp3" vol={0.28} />
          ))}
          <Sfx at={1830} file="chime_up.mp3" vol={0.45} />

          {/* Phase1: 문제 제기 훅 */}
          <div style={{ position: 'absolute', top: 90, left: '50%', transform: `translateX(-50%) scale(${hookScale})`, transformOrigin: 'center top', ...panelStyle({ position: 'relative', width: 760, padding: 0 }), opacity: hookOp }}>
            <div style={{ ...kickerStyle, display: 'flex', alignItems: 'center', gap: 10 }}>
              <ClaudeLogo size={28} />
              <span>STEP 2 · MCP가 뭐죠?</span>
            </div>
            <div style={{ padding: '20px 28px' }}>
              <div style={{ fontSize: 26, fontWeight: 800, color: '#fff', lineHeight: 1.5 }}>
                AI한테 <span style={{ color: LIME }}>"네이버 검색해서 카톡으로 보내"</span> 하려면?
              </div>
              <div style={{ marginTop: 16, background: 'rgba(255,68,85,0.1)', border: '1px solid rgba(255,68,85,0.3)', borderRadius: 6, padding: '12px 18px', fontSize: 17, fontWeight: 700, color: 'rgba(255,120,120,0.95)', opacity: ci(f, 580, 600) }}>
                ❌ 개발자 + 수백만 원 코딩 → 회사마다 호출 구조가 달라서
              </div>
            </div>
          </div>

          {/* Phase2 LEFT: Before 파편화 */}
          <div style={{ ...panelStyle({ left: 64, top: 110, width: 420, height: 320 }), opacity: beforeOp, transform: `translateX(${slideX(f, 978, -1)}px)` }}>
            <div style={kickerStyle}>BEFORE · 파편화 지옥</div>
            {OLD_CONNECTORS.map((c, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '16px 22px', borderBottom: '1px solid rgba(255,255,255,0.04)', opacity: ci(f, c.delay, c.delay + 18) }}>
                <span style={{ fontSize: 26 }}>{c.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 19, fontWeight: 700, color: c.color }}>{c.label}</div>
                  <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>{c.sub}</div>
                </div>
                <span style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 11, color: 'rgba(255,80,80,0.8)', opacity: ci(f, c.delay + 16, c.delay + 28) }}>별도 연동</span>
              </div>
            ))}
          </div>

          {/* Phase2 RIGHT: After USB-C */}
          <div style={{ ...panelStyle({ right: 64, top: 110, width: 400, height: 260 }), opacity: afterOp, transform: `translateX(${slideX(f, 1206, 1)}px)`, padding: '26px 28px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 11, color: LIME50, letterSpacing: 3, marginBottom: 14 }}>AFTER · 대통합</div>
            <div style={{ fontSize: 56, fontWeight: 900, color: LIME, textShadow: `0 0 28px rgba(170,255,0,0.6)`, marginBottom: 10 }}>USB-C</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: 'rgba(255,255,255,0.65)', lineHeight: 1.5 }}>
              하나로 전부 연결<br /><span style={{ color: LIME }}>MCP = 이 개념</span>
            </div>
            <div style={{ height: 3, background: LIME, borderRadius: 2, marginTop: 18, width: `${ci(f, 1250, 1320, 0, 100)}%`, boxShadow: `0 0 12px ${LIME50}` }} />
          </div>

          {/* Phase3 LEFT: PlayMCP 멀티허브 */}
          <div style={{ ...panelStyle({ left: 64, top: 110, width: 500, height: 360 }), opacity: playOp, transform: `translateX(${slideX(f, 1580, -1)}px)` }}>
            <div style={{ ...kickerStyle, display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 22 }}>🔌</span><span>PlayMCP · 멀티 허브</span>
            </div>
            {SERVICES.map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 22px', borderBottom: '1px solid rgba(255,255,255,0.04)', opacity: ci(f, s.delay, s.delay + 18) }}>
                <span style={{ fontSize: 22 }}>{s.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>{s.label}</div>
                  <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>{s.sub}</div>
                </div>
                <span style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 11, color: LIME, opacity: ci(f, s.delay + 16, s.delay + 28), textShadow: `0 0 8px ${LIME50}` }}>✓ 연결</span>
              </div>
            ))}
          </div>

          {/* Phase3 RIGHT: Claude 처리 */}
          <div style={{ ...panelStyle({ right: 64, top: 110, width: 380, height: 260 }), opacity: playROp, transform: `translateX(${slideX(f, 1610, 1)}px)`, padding: '26px 28px' }}>
            <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 11, color: LIME50, letterSpacing: 3, marginBottom: 16 }}>RESULT · 처리 결과</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18 }}>
              <ClaudeLogo size={42} />
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', lineHeight: 1.4 }}>Claude가<br />전부 처리</div>
            </div>
            <div style={{ background: LIME20, border: `1px solid ${LIME50}`, borderRadius: 6, padding: '10px 16px', fontFamily: "'Roboto Mono',monospace", fontSize: 14, color: LIME, textAlign: 'center', opacity: ci(f, 1700, 1720) }}>딸깍 하나로 ✓</div>
          </div>

          {/* Phase4: 임팩트 */}
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingBottom: '14%', opacity: impactOp, transform: `scale(${impactScale})` }}>
            <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 14, color: LIME50, letterSpacing: 4, marginBottom: 14 }}>MCP · 핵심 정리</div>
            <div style={{ fontSize: 80, fontWeight: 900, color: '#fff', letterSpacing: -3 }}>딸깍 하나로</div>
            <div style={{ fontSize: 80, fontWeight: 900, color: LIME, letterSpacing: -3, textShadow: `0 0 40px rgba(170,255,0,0.6)` }}>전부 처리</div>
          </div>
        </>
      );
    }}
  </SceneBase>
);
