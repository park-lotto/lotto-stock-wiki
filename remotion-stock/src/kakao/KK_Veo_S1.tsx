/**
 * KK_Veo_S1 — S1 훅 (Veo AI 아바타)
 *
 * veo_s1.mp4 전체화면 + 카카오 브리핑 폰 모형 오버레이
 * 총 838프레임 (27.93s @ 30fps)
 *
 * Phase 1 f0~60   : 프레젠터 등장, 자막만
 * Phase 2 f60~210 : 폰 우측에서 슬라이드 인
 * Phase 3 f210~580: 메시지 하나씩 reveal
 * Phase 4 f580~838: hold
 */

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { FONT } from '../constants';

export const KK_VEO_S1_FRAMES = 838;

const KAKAO   = '#FAE100';
const KAKAO_D = '#3A2F00';
const CHAT_BG = '#B2C7D9';
const WHITE   = '#FFFFFF';

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

const SUBTITLES = [
  { text: '요즘 주식판 고수들은 클로드로 갈아탔습니다',             from: 0,   to: 120 },
  { text: '미국 앱스토어에서도 이미 난리가 났죠',                   from: 120, to: 210 },
  { text: '오늘 아침 이 카톡 — 어젯밤 클로드가 보낸 겁니다',        from: 210, to: 360 },
  { text: '딱 10분만 투자하면 됩니다',                              from: 360, to: 450 },
  { text: '매일 아침 브리핑이 자동으로 카톡에 옵니다',              from: 450, to: 580 },
  { text: '복잡한 코딩 없이 — 오늘 영상 끝까지 집중해주세요',       from: 580, to: 720 },
];

const MSGS = [
  { icon: '📋', text: '2026.06.15 오전 8:00 브리핑',    delay: 0,   bold: true  },
  { icon: '📊', text: '코스피 2,856 (+0.3%) — 외인 순매도', delay: 30  },
  { icon: '🔥', text: '주도 섹터: 반도체 / 조선',            delay: 60  },
  { icon: '⭐', text: '관심: 삼성전기 · HD현대중공업',        delay: 90  },
  { icon: '💰', text: '기관 순매수 집중 — 오늘 주목',         delay: 120 },
];

const PHONE_ENTER = 60;
const MSG_START   = 210;
const PHONE_W     = 360;
const PHONE_H     = 640;

export const KK_Veo_S1: React.FC = () => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 폰 슬라이드 인
  const phoneProg = spring({
    frame: Math.max(0, f - PHONE_ENTER),
    fps,
    config: { damping: 18, stiffness: 130, mass: 1.0 },
    durationInFrames: 40,
  });
  const phoneX = interpolate(phoneProg, [0, 1], [PHONE_W + 60, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // 알림 배너 (f60~210)
  const bannerProg = spring({
    frame: Math.max(0, f - 48),
    fps,
    config: { damping: 10, stiffness: 260, mass: 0.6 },
    durationInFrames: 22,
  });
  const bannerOp = f < MSG_START
    ? clamp(f, 48, 78)
    : clamp(f, MSG_START, MSG_START + 20, 1, 0);

  // 채팅 본문 (f210~)
  const msgPhaseOp = clamp(f, MSG_START, MSG_START + 22);

  // 자막 활성 라인
  const activeSub = SUBTITLES.find(s => f >= s.from && f < s.to);

  return (
    <AbsoluteFill style={{ fontFamily: FONT, overflow: 'hidden', background: '#000' }}>

      {/* 아바타 동영상 */}
      <OffthreadVideo
        src={staticFile('kakao/veo_s1.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* 우측 그라디언트 — 폰 가독성 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(to left, rgba(0,0,0,0.55) 0%, transparent 55%)',
      }} />

      {/* ── 카카오 알림 배너 (Phase 1→2) ────────────────────────── */}
      <div style={{
        position: 'absolute', top: 48, right: 52,
        opacity: bannerOp,
        transform: `translateY(${interpolate(bannerProg, [0, 1], [-60, 0], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.out(Easing.back(1.2)),
        })}px)`,
        width: 400,
        background: 'rgba(255,255,255,0.96)',
        backdropFilter: 'blur(18px)',
        borderRadius: 18,
        padding: '14px 18px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.22)',
        display: 'flex', gap: 13, alignItems: 'center',
      }}>
        <div style={{
          width: 44, height: 44, borderRadius: 11,
          background: KAKAO,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 23, flexShrink: 0,
        }}>🤖</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: KAKAO_D }}>주식 AI 브리핑</div>
          <div style={{ fontSize: 12, color: '#555', marginTop: 2 }}>오늘 시장 브리핑 도착 📊</div>
        </div>
        <div style={{ fontSize: 11, color: '#999', flexShrink: 0 }}>오전 8:00</div>
      </div>

      {/* ── 폰 모형 (Phase 2~4) ──────────────────────────────────── */}
      <div style={{
        position: 'absolute',
        right: 60,
        top: '50%',
        transform: `translateY(-50%) translateX(${phoneX}px)`,
        width: PHONE_W,
        height: PHONE_H,
        background: WHITE,
        borderRadius: 48,
        border: '2px solid rgba(0,0,0,0.08)',
        boxShadow: '0 24px 72px rgba(0,0,0,0.35), 0 6px 18px rgba(0,0,0,0.18)',
        overflow: 'hidden',
        zIndex: 10,
      }}>
        {/* 다이나믹 아일랜드 */}
        <div style={{
          position: 'absolute', top: 12, left: '50%',
          transform: 'translateX(-50%)',
          width: 100, height: 30, background: '#111', borderRadius: 16,
          zIndex: 2,
        }} />

        {/* 카카오 헤더 */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 88,
          background: KAKAO,
          display: 'flex', alignItems: 'flex-end',
          paddingBottom: 12, paddingInline: 16, gap: 9,
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: '50%',
            background: KAKAO_D,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16,
          }}>🤖</div>
          <div style={{ color: KAKAO_D, fontSize: 14, fontWeight: 700 }}>주식 AI 브리핑</div>
        </div>

        {/* 채팅 본문 */}
        <div style={{
          position: 'absolute', top: 88, left: 0, right: 0, bottom: 50,
          background: CHAT_BG,
          opacity: msgPhaseOp,
          padding: '10px 9px',
          display: 'flex', flexDirection: 'column', gap: 5,
          overflow: 'hidden',
        }}>
          <div style={{
            textAlign: 'center', color: 'rgba(0,0,0,0.40)',
            fontSize: 10.5, fontWeight: 500, marginBottom: 4,
          }}>오전 8:00</div>

          {/* 단일 메시지 버블 */}
          <div style={{
            background: WHITE,
            borderRadius: '4px 14px 14px 14px',
            padding: '10px 12px',
            boxShadow: '0 2px 6px rgba(0,0,0,0.10)',
            maxWidth: '92%',
          }}>
            {MSGS.map((msg, i) => {
              const mOp = clamp(f, MSG_START + msg.delay + 8, MSG_START + msg.delay + 26);
              const mY  = interpolate(
                f,
                [MSG_START + msg.delay + 8, MSG_START + msg.delay + 22],
                [8, 0],
                { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) },
              );
              return (
                <div key={i} style={{
                  opacity: mOp,
                  transform: `translateY(${mY}px)`,
                  fontSize: 11,
                  color: msg.bold ? KAKAO_D : '#333',
                  fontWeight: msg.bold ? 700 : 400,
                  lineHeight: 1.8,
                  display: 'flex', gap: 5,
                  borderBottom: msg.bold ? '1px solid rgba(0,0,0,0.06)' : 'none',
                  paddingBottom: msg.bold ? 5 : 0,
                  marginBottom: msg.bold ? 4 : 0,
                }}>
                  <span>{msg.icon}</span>
                  <span>{msg.text}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 홈바 */}
        <div style={{
          position: 'absolute', bottom: 8, left: '50%',
          transform: 'translateX(-50%)',
          width: 100, height: 5, background: 'rgba(0,0,0,0.14)', borderRadius: 3,
        }} />
      </div>

      {/* ── 채널 배지 ───────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 36, left: 52,
        opacity: clamp(f, 20, 45),
        display: 'flex', flexDirection: 'column', gap: 4,
      }}>
        <div style={{
          background: KAKAO, color: KAKAO_D,
          fontSize: 12, fontWeight: 900, letterSpacing: 0.5,
          padding: '3px 11px', borderRadius: 6,
        }}>카카오 × 클로드</div>
        <div style={{ color: 'rgba(255,255,255,0.55)', fontSize: 11, fontWeight: 500 }}>
          로또의 주식인사이트
        </div>
      </div>

      {/* ── 자막 바 ─────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, transparent 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {activeSub && (
          <div style={{
            fontSize: 40, fontWeight: 700, color: WHITE,
            textAlign: 'center', paddingInline: 80,
            textShadow: '0 2px 12px rgba(0,0,0,0.90)',
            lineHeight: 1.35,
          }}>
            {activeSub.text}
          </div>
        )}
      </div>

    </AbsoluteFill>
  );
};
