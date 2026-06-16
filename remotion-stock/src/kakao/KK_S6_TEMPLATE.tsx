/**
 * KK_S6 — 씬 이름 (복붙 후 여기만 수정)
 *
 * Whisper 대본:
 *   f0~XXX  첫 번째 문장
 *   f???~?? 두 번째 문장
 */

import React from 'react';
import { SceneBase, ClaudeLogo } from './SceneBase';
import { ci, sp, panelOp, slideX, panelStyle, kickerStyle, LIME, LIME50 } from './theme';

export const KK_S6_FRAMES = 600; // ← Whisper 마지막 세그먼트 끝 프레임

// ── 1. 대본 (Whisper → 여기만 붙여넣기) ──
const SUBS = [
  { from: 0,   to: 180, text: '첫 번째 자막 텍스트입니다.', accent: '자막' },
  { from: 180, to: 360, text: '두 번째 자막 텍스트입니다.', accent: '두 번째' },
  { from: 360, to: 600, text: '세 번째 자막 텍스트입니다.', accent: '세 번째' },
];

// ── 2. 리스트 아이템 (있으면 작성, 없으면 삭제) ──
const ITEMS = [
  { icon: '📊', label: '항목 1', sub: '설명', delay: 50 },
  { icon: '🚀', label: '항목 2', sub: '설명', delay: 70 },
  { icon: '💡', label: '항목 3', sub: '설명', delay: 90 },
];

export const KK_S6: React.FC = () => (
  <SceneBase video="kakao/ep1/SCENE_VIDEO.mp4" subs={SUBS}>
    {(f) => {
      // ── Phase 타이밍 계산 ──
      const phase1Op = panelOp(f, 0, 180);
      const phase2Op = panelOp(f, 185, 360);
      const phase3Op = panelOp(f, 365, 590);

      return (
        <>
          {/* ══ Phase 1: 센터 카드 ══ */}
          <div style={{
            position: 'absolute', top: 80, left: '50%',
            transform: `translateX(-50%)`,
            ...panelStyle({ position: 'relative', width: 680, padding: '20px 30px', textAlign: 'center' }),
            opacity: phase1Op,
          }}>
            <div style={kickerStyle}>SECTION · 섹션명</div>
            <div style={{ fontSize: 26, fontWeight: 800, color: '#fff', lineHeight: 1.5, padding: '16px 0' }}>
              여기에 <span style={{ color: LIME }}>핵심 메시지</span>를 씁니다
            </div>
          </div>

          {/* ══ Phase 2: 리스트 패널 (LEFT) ══ */}
          <div style={{
            ...panelStyle({ left: 36, top: 80, width: 440, height: 280 }),
            opacity: phase2Op,
            transform: `translateX(${slideX(f, 185, -1)}px)`,
          }}>
            <div style={kickerStyle}>
              <ClaudeLogo size={28} />
              <span style={{ marginLeft: 10 }}>PANEL TITLE · 패널 제목</span>
            </div>
            {ITEMS.map((item, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 18px',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                opacity: ci(f, item.delay + 185, item.delay + 203),
              }}>
                <span style={{ fontSize: 18 }}>{item.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>{item.label}</div>
                  <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>{item.sub}</div>
                </div>
                <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9, color: LIME, opacity: ci(f, item.delay + 200, item.delay + 212) }}>✓ DONE</span>
              </div>
            ))}
          </div>

          {/* ══ Phase 3: 임팩트 텍스트 ══ */}
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            paddingBottom: '12%',
            opacity: phase3Op,
          }}>
            <div style={{ fontFamily: "'Courier New',monospace", fontSize: 12, color: LIME50, letterSpacing: 4, textTransform: 'uppercase', marginBottom: 12 }}>
              LABEL · 라벨
            </div>
            <div style={{ fontSize: 72, fontWeight: 900, color: '#fff', letterSpacing: -3, textAlign: 'center' }}>
              첫 번째 줄
            </div>
            <div style={{ fontSize: 72, fontWeight: 900, color: LIME, letterSpacing: -3 }}>
              두 번째 줄
            </div>
          </div>
        </>
      );
    }}
  </SceneBase>
);
