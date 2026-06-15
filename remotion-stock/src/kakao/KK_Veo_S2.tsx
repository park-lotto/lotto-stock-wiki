/**
 * KK_Veo_S2 — S2 페인포인트 (Veo AI 아바타, 웃음 반응)
 *
 * veo_s2.mp4 전체화면 + 앱 아이콘 혼돈 오버레이
 * 총 656프레임 (21.87s @ 30fps)
 *
 * Phase 1 f0~100  : 아침 루틴 나열 (앱 아이콘 팝업)
 * Phase 2 f100~300: 30분 증발 임팩트 텍스트
 * Phase 3 f300~480: "AI 외주" 메시지
 * Phase 4 f480~656: hold
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

export const KK_VEO_S2_FRAMES = 656;

const KAKAO   = '#FAE100';
const KAKAO_D = '#3A2F00';
const WHITE   = '#FFFFFF';
const MINT    = '#00FFD0';

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

const sp = (f: number, from: number, cfg = { damping: 12, stiffness: 220, mass: 0.7 }) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: cfg });

const SUBTITLES = [
  { text: '눈뜨자마자 인베스팅닷컴 켜고 야간 선물 확인',          from: 0,   to: 100 },
  { text: '네이버 뉴스, 텔레그램·카톡방 10개 돌면서 찌라시 체크',  from: 100, to: 220 },
  { text: '유튜브 쇼츠 몇 개 보다 보면 30분이 그냥 훅가죠!',       from: 220, to: 340 },
  { text: '정보 수집 노가다 — 이제 AI에게 전적으로 외주 주세요',   from: 340, to: 480 },
  { text: '매일 반복하는 아침 루틴을 자동화합니다',                from: 480, to: 600 },
];

// 아침 루틴 앱 목록
const APPS = [
  { icon: '📈', label: '인베스팅', x: 180, y: 220, delay: 8  },
  { icon: '📰', label: '네이버',   x: 340, y: 160, delay: 22 },
  { icon: '✈️', label: '텔레그램', x: 500, y: 250, delay: 38 },
  { icon: '💬', label: '카톡방',   x: 650, y: 180, delay: 52 },
  { icon: '▶️', label: '유튜브',   x: 280, y: 330, delay: 66 },
  { icon: '🔔', label: '알림 +9', x: 440, y: 310, delay: 80 },
];

const APP_ENTER = 8;
const APP_EXIT  = 220;
const IMPACT_AT = 240;
const SOLN_AT   = 320;

export const KK_Veo_S2: React.FC = () => {
  const f   = useCurrentFrame();
  useVideoConfig();

  const activeSub = SUBTITLES.find(s => f >= s.from && f < s.to);

  // 앱 아이콘 전체 opacity
  const appGroupOp = f < APP_EXIT
    ? clamp(f, APP_ENTER, APP_ENTER + 20)
    : clamp(f, APP_EXIT, APP_EXIT + 24, 1, 0);

  // 임팩트 텍스트 (f220~320)
  const impactOp = f < SOLN_AT
    ? clamp(f, IMPACT_AT, IMPACT_AT + 28)
    : clamp(f, SOLN_AT, SOLN_AT + 18, 1, 0);
  const impactScale = 0.72 + sp(f, IMPACT_AT, { damping: 8, stiffness: 280, mass: 0.5 }) * 0.28;

  // 솔루션 텍스트 (f320~480)
  const solnOp = f < 480
    ? clamp(f, SOLN_AT, SOLN_AT + 28)
    : clamp(f, 480, 498, 1, 0);
  const solnX  = interpolate(f, [SOLN_AT, SOLN_AT + 28], [-32, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
  });

  // "30분" 카운트다운 강조 (f=240~300)
  const timerOp = clamp(f, IMPACT_AT + 8, IMPACT_AT + 36);

  return (
    <AbsoluteFill style={{ fontFamily: FONT, overflow: 'hidden', background: '#000' }}>

      {/* 아바타 동영상 */}
      <OffthreadVideo
        src={staticFile('kakao/veo_s2.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* 상단 어두운 그라디언트 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.30) 0%, transparent 35%, transparent 60%, rgba(0,0,0,0.50) 100%)',
      }} />

      {/* ── 앱 아이콘 혼돈 레이어 ───────────────────────────────── */}
      <div style={{ position: 'absolute', inset: 0, opacity: appGroupOp, pointerEvents: 'none' }}>
        {APPS.map((app, i) => {
          const appProg = sp(f, APP_ENTER + app.delay);
          const appScale = 0.3 + appProg * 0.7;
          const appOp   = interpolate(appProg, [0, 1], [0, 0.88]);
          // 흔들림: 각 아이콘마다 다른 주파수
          const wobble = Math.sin(f * 0.12 + i * 1.4) * 3;
          return (
            <div key={i} style={{
              position: 'absolute',
              left: app.x,
              top: app.y + wobble,
              opacity: appOp,
              transform: `scale(${appScale})`,
              transformOrigin: 'center',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: 14,
                background: 'rgba(255,255,255,0.92)',
                backdropFilter: 'blur(8px)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 28,
                boxShadow: '0 4px 16px rgba(0,0,0,0.28)',
              }}>{app.icon}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: WHITE, textShadow: '0 1px 6px rgba(0,0,0,0.8)' }}>
                {app.label}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── 임팩트 "30분 증발" (f240~320) ──────────────────────── */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        opacity: impactOp, pointerEvents: 'none', gap: 16,
        paddingBottom: '16%',
      }}>
        <div style={{
          display: 'flex', alignItems: 'baseline', gap: 8,
          transform: `scale(${impactScale})`,
        }}>
          <span style={{
            fontSize: 180, fontWeight: 900, lineHeight: 0.9,
            color: WHITE,
            textShadow: '0 0 40px rgba(255,255,255,0.25)',
            letterSpacing: -8,
          }}>30</span>
          <span style={{
            fontSize: 80, fontWeight: 700,
            color: KAKAO,
            textShadow: `0 0 20px ${KAKAO}AA`,
          }}>분</span>
        </div>
        <div style={{
          opacity: timerOp,
          fontSize: 36, fontWeight: 600, color: 'rgba(255,255,255,0.75)',
          letterSpacing: 2,
        }}>
          그냥 &nbsp;<span style={{ color: KAKAO, fontWeight: 800 }}>훅</span>&nbsp; 가버립니다
        </div>
      </div>

      {/* ── 솔루션 텍스트 (f320~480) ────────────────────────────── */}
      <div style={{
        position: 'absolute',
        bottom: '20%', left: '50%',
        transform: `translateX(calc(-50% + ${solnX}px))`,
        opacity: solnOp, pointerEvents: 'none',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 42, fontWeight: 700, color: WHITE, lineHeight: 1.4 }}>
          정보 수집 노가다&nbsp;
          <span style={{ color: MINT, textShadow: `0 0 16px ${MINT}88` }}>AI</span>에게
        </div>
        <div style={{ fontSize: 42, fontWeight: 700, color: WHITE, lineHeight: 1.4 }}>
          전적으로 외주 주세요
        </div>
      </div>

      {/* ── 채널 배지 ───────────────────────────────────────────── */}
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

      {/* ── 자막 바 ─────────────────────────────────────────────── */}
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
