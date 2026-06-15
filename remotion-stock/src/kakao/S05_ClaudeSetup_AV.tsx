/**
 * S05_ClaudeSetup_AV — STEP1 Claude 설치 (PiP 버전)
 *
 * 레이아웃: KakaoLayout pip
 *   - 배경: screen_s05.mp4 (Claude 설치 화면녹화)
 *   - 아바타: avatar_s05.mp4 → pipEnterAt=60f 에서 우하단 PiP로 이동
 *   - 오버레이: STEP 카운터 / 하이라이트 박스 / TECHFEED 라벨
 *
 * 사용법: 화면녹화 타임라인에 맞춰 HL_* 프레임 값 조정
 */

import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';
import { C, GLOW } from '../constants';
import { KakaoLayout } from './KakaoLayout';

export const S05_AV_FRAMES = 1650;  // ← 화면녹화 길이에 맞춰 조정

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

// ── 자막 라인 ──────────────────────────────────────────────────────────────
const SUBTITLES = [
  { text: 'STEP 1 — Claude 데스크톱 앱 설치',                          from: 0,    to: 180  },
  { text: 'claude.ai 검색 → 다운로드 클릭',                             from: 180,  to: 390  },
  { text: 'Pro 플랜 필수 — 코워크 기능이 여기 있습니다',                from: 390,  to: 660  },
  { text: '설치 후 왼쪽 메뉴 → 코워크 탭',                              from: 660,  to: 900  },
  { text: '설치 완료! 다음 STEP으로 넘어갑니다',                         from: 900,  to: 1200 },
  { text: 'Pro ($20/월) — 이게 하루 1,000원입니다',                      from: 1200, to: 1500 },
  { text: '매일 아침 비서 한 명 고용하는 가격이에요',                    from: 1500, to: 1650 },
];

// ── 하이라이트 박스 (화면녹화 위 오버레이) ─────────────────────────────
// 화면녹화 실제 UI 위치에 맞춰 top/left/width/height 조정하세요
const HIGHLIGHTS: Array<{
  from: number; to: number;
  top: number; left: number; width: number; height: number;
  label?: string;
}> = [
  // 예시: 다운로드 버튼 영역
  { from: 180, to: 420, top: 440, left: 680, width: 240, height: 72,  label: '클릭!' },
  // 예시: Pro 요금제 카드
  { from: 420, to: 720, top: 580, left: 780, width: 360, height: 180, label: '이거' },
  // 예시: 코워크 탭
  { from: 860, to: 1100, top: 245, left: 18, width: 198, height: 48,  label: '바로 여기' },
];

const HL_PULSE = (f: number) => 0.55 + Math.sin(f * 0.14) * 0.45;

const HighlightBox: React.FC<{
  f: number;
  item: (typeof HIGHLIGHTS)[0];
}> = ({ f, item }) => {
  const op    = clamp(f, item.from, item.from + 24);
  const fadeO = f > item.to - 20 ? clamp(f, item.to - 20, item.to, 1, 0) : 1;
  const pulse = HL_PULSE(f);

  if (op === 0) return null;

  return (
    <div style={{
      position: 'absolute',
      top: item.top, left: item.left,
      width: item.width, height: item.height,
      opacity: op * fadeO,
      pointerEvents: 'none',
    }}>
      {/* 하이라이트 테두리 */}
      <div style={{
        position: 'absolute', inset: 0,
        border: `2.5px solid ${C.main}`,
        borderRadius: 10,
        boxShadow: `0 0 ${14 * pulse}px rgba(0,255,208,${0.7 * pulse}),
                    0 0 ${32 * pulse}px rgba(0,255,208,${0.3 * pulse})`,
      }} />

      {/* 라벨 태그 */}
      {item.label && (
        <div style={{
          position: 'absolute', top: -28, left: 0,
          background: C.main,
          color: '#000',
          fontSize: 13, fontWeight: 900,
          padding: '3px 10px', borderRadius: 6,
          whiteSpace: 'nowrap',
          boxShadow: `0 0 8px rgba(0,255,208,0.6)`,
        }}>
          {item.label}
        </div>
      )}

      {/* 코너 마커 */}
      {[
        { top: -3, left: -3, borderColor: `${C.main} transparent transparent ${C.main}` },
        { top: -3, right: -3, borderColor: `${C.main} ${C.main} transparent transparent` },
        { bottom: -3, left: -3, borderColor: `transparent transparent ${C.main} ${C.main}` },
        { bottom: -3, right: -3, borderColor: `transparent ${C.main} ${C.main} transparent` },
      ].map((corner, i) => (
        <div key={i} style={{
          position: 'absolute',
          width: 12, height: 12,
          ...corner,
          borderWidth: 2.5, borderStyle: 'solid',
        }} />
      ))}
    </div>
  );
};

// ── STEP 카운터 (좌상단) ───────────────────────────────────────────────────
const StepCounter: React.FC<{ f: number; step: number; total?: number }> = ({
  f, step, total = 5,
}) => {
  const op = clamp(f, 20, 50);
  return (
    <div style={{
      position: 'absolute', top: 30, left: 44, zIndex: 50, opacity: op,
    }}>
      <div style={{
        background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(8px)',
        borderRadius: 14, padding: '10px 20px',
        border: `1.5px solid rgba(0,255,208,0.3)`,
      }}>
        <div style={{
          color: C.textSub, fontSize: 11, fontWeight: 600, letterSpacing: 4, marginBottom: 2,
        }}>STEP</div>
        <div style={{
          color: C.main, fontSize: 46, fontWeight: 900, lineHeight: 1,
          fontFamily: '"Consolas","Menlo",monospace',
          textShadow: GLOW.mid.text,
        }}>
          {step}<span style={{ color: C.textSub, fontSize: 22 }}>/{total}</span>
        </div>
      </div>
    </div>
  );
};

// ── TECHFEED 라벨 (하단 좌측) ─────────────────────────────────────────────
const TECHFEED_ITEMS = [
  { label: '데스크톱 앱', desc: 'claude.ai → 다운로드', showFrom: 60  },
  { label: 'Pro 플랜',   desc: '$20/월 · 코워크 포함', showFrom: 400 },
  { label: '코워크 탭',  desc: '설치 후 왼쪽 메뉴',   showFrom: 870 },
];

const TechFeedOverlay: React.FC<{ f: number }> = ({ f }) => (
  <div style={{
    position: 'absolute', bottom: '18%', left: 44,
    display: 'flex', flexDirection: 'column', gap: 10,
  }}>
    {TECHFEED_ITEMS.map((item, i) => {
      const op = clamp(f, item.showFrom, item.showFrom + 24);
      const tx = interpolate(op, [0, 1], [-28, 0]);
      return (
        <div key={i} style={{
          opacity: op,
          transform: `translateX(${tx}px)`,
          display: 'flex', alignItems: 'center', gap: 12,
          background: 'rgba(0,0,0,0.68)', backdropFilter: 'blur(6px)',
          borderRadius: 8, padding: '7px 16px',
          border: `1px solid rgba(0,255,208,0.2)`,
        }}>
          <div style={{
            color: C.main, fontSize: 15, fontWeight: 700,
            minWidth: 84, textAlign: 'right',
            textShadow: GLOW.weak.text,
          }}>{item.label}</div>
          <div style={{ width: 1, height: 20, background: 'rgba(0,255,208,0.3)' }} />
          <div style={{ color: '#E5E5E5', fontSize: 15, fontWeight: 400 }}>{item.desc}</div>
        </div>
      );
    })}
  </div>
);

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────
export const S05_ClaudeSetup_AV: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <KakaoLayout
      avatarFile="avatar_s05.mp4"
      screenFile="screen_s05.mp4"
      mode="pip"
      pipEnterAt={60}   // 60프레임(2초) 후 PiP 전환
      subtitles={SUBTITLES}
    >
      {/* STEP 카운터 */}
      <StepCounter f={f} step={1} />

      {/* 하이라이트 박스들 */}
      {HIGHLIGHTS.map((hl, i) => (
        <HighlightBox key={i} f={f} item={hl} />
      ))}

      {/* TECHFEED 라벨 */}
      <TechFeedOverlay f={f} />
    </KakaoLayout>
  );
};
