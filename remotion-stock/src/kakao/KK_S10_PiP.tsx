/**
 * KK_S10_PiP — 예약 자동화 (1308f · 튜토리얼 모드 v3 "액션 줌인")
 * S5/S7/S8/S9와 동일 아키텍처: 풀스크린 녹화 + 단계별 줌 + 단계 전환 카드
 * + 화면 밖 자막(S10_timestamps 1:1) + 오전 7시 예약완료 클라이맥스.
 *
 * 자막 = S10_timestamps.json 1:1 (긴 세그만 분할). ASR 교정: 모전→오전 / 전기세만이→전기세 많이 / 그니까→그러니까.
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, interpolate } from 'remotion';
import { cl, pop, flashAt, Sfx } from './fx';
import { Watermark, LifeSubBar, LIME } from './life';

export const KK_S10_PIP_FRAMES = 1308;

const NUM = "'Archivo',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

// S10_timestamps 6세그 1:1 — 긴 세그 자연 위치 분할(프레임 비례)
const SUBS = [
  { from: 0, to: 80, text: '이제 거의 다 왔습니다', accent: '' },
  { from: 80, to: 227, text: '예약 자동화 작업을 해볼 건데 채팅창에 이렇게 입력해볼게요', accent: '예약 자동화' },
  { from: 227, to: 360, text: '방금 만든 플러그인을 매일 아침 오전 7시에', accent: '오전 7시' },
  { from: 360, to: 476, text: '아침 브리핑으로 실행해줘, 이렇게 한번 넣어볼게요', accent: '실행해줘' },
  { from: 476, to: 600, text: '예약 작업 설정이 완료되었습니다', accent: '설정 완료' },
  { from: 600, to: 756, text: '클로드 앱이 켜져 있으면 매일 아침 7시부터 자동 실행됩니다', accent: '자동 실행' },
  { from: 756, to: 860, text: '출근할 때 켜놓으면 전기세 많이 나오지 않냐', accent: '전기세' },
  { from: 860, to: 936, text: '이렇게 물어보시는 분들도 가끔 계세요', accent: '' },
  { from: 936, to: 1030, text: '근데 윈도우 설정에서 절전 모드 끄고', accent: '절전 모드' },
  { from: 1030, to: 1128, text: '화면만 꺼지게 그렇게 해두면 되거든요', accent: '화면만' },
  { from: 1128, to: 1240, text: '그러니까 본체만 도니까 전기세는 거의 안 듭니다', accent: '거의 안 듭니다' },
  { from: 1240, to: 1308, text: '그렇게 설정 한번 해보세요', accent: '' },
];

const STEPS = [
  { at: 0, label: '예약 자동화 입력' },
  { at: 476, label: '오전 7시 예약 완료' },
  { at: 756, label: '전기세 걱정 해결' },
];

// 줌 키프레임 — STEP 안에서 완전히 고정, 컷(플래시)에서만 순간 변경 (S5~S9 동일 원칙)
const KF = [0, 475, 476, 755, 756, 1308];
const FX = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
const FY = [0.52, 0.52, 0.45, 0.45, 0.50, 0.50];
const SC = [1.12, 1.12, 1.14, 1.14, 1.10, 1.10];

export const KK_S10_PiP: React.FC = () => {
  const f = useCurrentFrame();

  const fx = interpolate(f, KF, FX, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const fy = interpolate(f, KF, FY, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sc = interpolate(f, KF, SC, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const step = STEPS.reduce((acc, s, i) => (f >= s.at ? i : acc), 0);

  // 단계 전환 카드 (각 STEP 시작 1.5초)
  const trans = STEPS.find((s) => f >= s.at && f < s.at + 45);

  // 오전 7시 예약 완료 클라이맥스 (476~756)
  const schedOp = cl(f, 490, 520) * cl(f, 710, 756, 1, 0);
  const schedPunch = pop(f, 490, { damping: 8, stiffness: 240 });

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: "'Noto Sans KR', sans-serif", overflow: 'hidden' }}>
      {/* 풀스크린 녹화 + 줌 */}
      <OffthreadVideo
        src={staticFile('kakao/ep1/s10_bg.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${sc})`, transformOrigin: `${fx * 100}% ${fy * 100}%` }}
      />

      {/* 상단/하단 미세 스크림 */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 90, background: 'linear-gradient(rgba(0,0,0,0.55), transparent)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 200, background: 'linear-gradient(transparent, rgba(0,0,0,0.85))', pointerEvents: 'none' }} />

      {/* 상단 얇은 진행바 (3단계) */}
      <div style={{ position: 'absolute', top: 22, left: 56, right: 56, display: 'flex', gap: 8 }}>
        {STEPS.map((_, i) => (
          <div key={i} style={{ flex: 1, height: 5, borderRadius: 3, background: i <= step ? LIME : 'rgba(255,255,255,0.18)', boxShadow: i <= step ? `0 0 8px ${LIME}` : 'none' }} />
        ))}
      </div>
      <div style={{ position: 'absolute', top: 38, left: 56, fontFamily: MONO, fontSize: 16, letterSpacing: 3, color: LIME }}>
        STEP {String(step + 1).padStart(2, '0')}/03 · 예약 자동화
      </div>

      {/* 단계 전환 컷 카드 */}
      {trans && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
          <div style={{ position: 'absolute', inset: 0, background: '#000', opacity: cl(f, trans.at, trans.at + 4) * cl(f, trans.at + 36, trans.at + 45, 1, 0) * 0.74 }} />
          <div style={{ opacity: cl(f, trans.at, trans.at + 5) * cl(f, trans.at + 38, trans.at + 45, 1, 0), transform: `scale(${0.8 + pop(f, trans.at, { damping: 8 }) * 0.2})`, textAlign: 'center' }}>
            <div style={{ fontFamily: NUM, fontSize: 130, fontWeight: 900, color: LIME, lineHeight: 0.9, textShadow: `0 0 40px ${LIME}` }}>
              STEP {step + 1}
            </div>
            <div style={{ fontSize: 56, fontWeight: 900, color: '#fff', marginTop: 10, letterSpacing: -1 }}>{STEPS[step].label}</div>
          </div>
        </div>
      )}

      {/* 컷 플래시 */}
      {STEPS.map((s) => (
        <div key={s.at} style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, s.at, 8, 0.4), pointerEvents: 'none' }} />
      ))}

      {/* 오전 7시 예약 완료 클라이맥스 */}
      {f >= 476 && f < 756 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 140, pointerEvents: 'none' }}>
          <div style={{ opacity: schedOp, transform: `scale(${0.85 + schedPunch * 0.15})`, width: 540, padding: '32px 40px', borderRadius: 22, background: 'rgba(20,16,14,0.92)', border: `2.5px solid ${LIME}`, textAlign: 'center', boxShadow: `0 0 44px rgba(170,255,0,0.32)` }}>
            <div style={{ fontSize: 54, marginBottom: 8 }}>⏰</div>
            <div style={{ fontFamily: MONO, fontSize: 14, letterSpacing: 4, color: LIME, marginBottom: 12 }}>SCHEDULED · 예약 완료</div>
            <div style={{ fontFamily: NUM, fontSize: 66, fontWeight: 900, color: LIME, letterSpacing: -1, textShadow: '0 0 28px rgba(170,255,0,0.5)' }}>매일 오전 7:00</div>
            <div style={{ fontSize: 20, color: 'rgba(255,255,255,0.7)', marginTop: 12 }}>앱이 켜져 있으면 자동 실행</div>
          </div>
        </div>
      )}

      <Sfx at={490} file="chime_up.mp3" vol={0.4} />
      {STEPS.map((s) => (
        <Sfx key={s.at} at={s.at} file="tick.mp3" vol={0.22} />
      ))}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: '#FF4455', boxShadow: '0 0 12px #FF4455' }} />
    </AbsoluteFill>
  );
};
