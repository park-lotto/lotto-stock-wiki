/**
 * S01_Hook_AV — 훅 씬 (아바타 전체화면 버전)
 *
 * 레이아웃: KakaoLayout fullscreen
 *   - avatar_s01.mp4  전체화면 재생
 *   - 자막 바 동기화
 *   - 우하단 로고 배지
 *
 * 총 프레임: v6 대본 S1 나레이션 분량에 맞춰 조정
 * (HeyGen 클립 길이 확인 후 S01_AV_FRAMES 수정)
 */

import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';
import { KakaoLayout } from './KakaoLayout';

export const S01_AV_FRAMES = 660;   // ← HeyGen 클립 길이에 맞춰 조정 (30fps 기준)

const KAKAO   = '#FAE100';
const KAKAO_D = '#3A2F00';

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

// ── 자막 라인 (v6 대본 S1 기준, 초 단위 → 프레임 × 30) ──────────────────
// 실제 녹음 타이밍에 맞춰 수정하세요
const SUBTITLES = [
  { text: '요즘 주식판 고수들은 클로드로 갈아탔습니다',   from: 0,   to: 120 },
  { text: '미국 앱스토어에서도 이미 난리가 났죠',          from: 120, to: 210 },
  { text: '오늘 아침 이 카톡 — 어젯밤 클로드가 보낸 겁니다', from: 210, to: 330 },
  { text: '지금부터 딱 10분 투자하면 됩니다',              from: 330, to: 450 },
  { text: '복잡한 코딩 없이, 매일 아침 브리핑 자동화',      from: 450, to: 570 },
  { text: '오늘 영상 끝까지 집중해주세요!',                from: 570, to: 660 },
];

// ── 우측 하단 채널 배지 ──────────────────────────────────────────────────
const ChannelBadge: React.FC<{ f: number }> = ({ f }) => {
  const op = clamp(f, 24, 54);
  return (
    <div style={{
      position: 'absolute', bottom: '18%', right: 48,
      opacity: op, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4,
    }}>
      <div style={{
        background: KAKAO,
        color: KAKAO_D,
        fontSize: 13, fontWeight: 900, letterSpacing: 1,
        padding: '4px 12px', borderRadius: 6,
      }}>카카오 × 클로드</div>
      <div style={{ color: 'rgba(255,255,255,0.55)', fontSize: 12, fontWeight: 500 }}>
        STOCKBRAIN
      </div>
    </div>
  );
};

// ── 좌상단 LIVE 배지 (인트로 1~2초 등장) ────────────────────────────────
const LiveBadge: React.FC<{ f: number }> = ({ f }) => {
  const pulse = 0.55 + Math.sin(f * 0.18) * 0.45;
  const op    = clamp(f, 30, 60);
  return (
    <div style={{
      position: 'absolute', top: 36, left: 52,
      display: 'flex', alignItems: 'center', gap: 8,
      opacity: op,
    }}>
      <div style={{
        width: 10, height: 10, borderRadius: '50%',
        background: '#FF3B30',
        boxShadow: `0 0 ${8 * pulse}px rgba(255,59,48,0.9)`,
      }} />
      <span style={{
        color: '#fff', fontSize: 14, fontWeight: 700, letterSpacing: 3,
        textShadow: '0 1px 8px rgba(0,0,0,0.7)',
      }}>LIVE</span>
    </div>
  );
};

export const S01_Hook_AV: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <KakaoLayout
      avatarFile="avatar_s01.mp4"
      mode="fullscreen"
      subtitles={SUBTITLES}
    >
      <LiveBadge f={f} />
      <ChannelBadge f={f} />
    </KakaoLayout>
  );
};
