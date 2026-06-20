/**
 * KK_S9_PiP — 플러그인 패키징 (1412f · 튜토리얼 모드 v3 "액션 줌인")
 * S5/S7/S8과 동일 아키텍처: 풀스크린 녹화 + 단계별 줌 + 단계 전환 카드
 * + 화면 밖 자막(S09_timestamps 1:1) + 패키징완료/카톡도착 클라이맥스.
 *
 * 자막 = S09_timestamps.json 1:1 (긴 세그만 분할). ASR 교정: 날벗→날것 / 이를→일을 / 간다는→간단한 / 카토로→카톡으로.
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, interpolate } from 'remotion';
import { cl, pop, flashAt, shake, Sfx } from './fx';
import { Watermark, LifeSubBar, ClaudeIcon, LIME } from './life';

export const KK_S9_PIP_FRAMES = 1412;

const NUM = "'Archivo',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

// S09_timestamps 7세그 1:1 — 긴 세그(1·2·3·5·6)만 자연 위치 분할(프레임 비례)
const SUBS = [
  { from: 0, to: 120, text: '자 지금까지 만든 걸 이제 매일 반복해서 해줄 건데', accent: '매일 반복' },
  { from: 120, to: 221, text: '이것도 처음부터 하려면 정말 큰일입니다', accent: '큰일' },
  { from: 221, to: 330, text: '첫 번째로는 이걸 하나의 패키징으로 묶어서', accent: '패키징' },
  { from: 330, to: 426, text: '언제든 간단한 명령으로 바로 일을 시키는 겁니다', accent: '간단한 명령' },
  { from: 426, to: 550, text: '클로드의 가장 큰 장점은 초보자인 여러분들도', accent: '초보자' },
  { from: 550, to: 678, text: '일상 자연어로만 대화해도 쉽게 코딩을 짜준다는 겁니다', accent: '자연어' },
  { from: 678, to: 820, text: '복잡한 것 없이 날것 그대로 한번 해보겠습니다', accent: '날것 그대로' },
  { from: 820, to: 940, text: '채팅창에 이렇게 한번 넣어 보겠습니다', accent: '채팅창' },
  { from: 940, to: 1066, text: '방금 만든 아침 브리핑을 플러그인으로 패키징 해줘', accent: '패키징 해줘' },
  { from: 1066, to: 1150, text: '작업이 완료되었습니다', accent: '완료' },
  { from: 1150, to: 1253, text: '카톡으로 보냈다고 하는데 한번 보겠습니다', accent: '카톡으로' },
  { from: 1253, to: 1412, text: '지금 브리핑이 잘 들어왔네요. 좋습니다', accent: '잘 들어왔네요' },
];

const STEPS = [
  { at: 0, label: '매일 반복 자동화' },
  { at: 678, label: '자연어로 패키징' },
  { at: 1066, label: '완료 → 카톡 도착' },
];

// 줌 키프레임 — STEP 안에서 완전히 고정, 컷(플래시)에서만 순간 변경 (S5/S7/S8 동일 원칙)
const KF = [0, 677, 678, 1065, 1066, 1412];
const FX = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
const FY = [0.48, 0.48, 0.55, 0.55, 0.45, 0.45];
const SC = [1.12, 1.12, 1.14, 1.14, 1.14, 1.14];

export const KK_S9_PiP: React.FC = () => {
  const f = useCurrentFrame();

  const fx = interpolate(f, KF, FX, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const fy = interpolate(f, KF, FY, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sc = interpolate(f, KF, SC, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const step = STEPS.reduce((acc, s, i) => (f >= s.at ? i : acc), 0);

  // 단계 전환 카드 (각 STEP 시작 1.5초)
  const trans = STEPS.find((s) => f >= s.at && f < s.at + 45);

  // 패키징 완료 배지 (1066~1250)
  const doneOp = cl(f, 1069, 1096) * cl(f, 1210, 1250, 1, 0);
  // 카톡 브리핑 도착 클라이맥스 (1253~1412)
  const kakaoOp = cl(f, 1256, 1284) * cl(f, 1380, 1412, 1, 0);
  const kakaoShake = shake(f, 1256, 14, 4);

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: "'Noto Sans KR', sans-serif", overflow: 'hidden' }}>
      {/* 풀스크린 녹화 + 줌 */}
      <OffthreadVideo
        src={staticFile('kakao/ep1/s09_bg.mp4')}
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
        STEP {String(step + 1).padStart(2, '0')}/03 · 플러그인 패키징
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

      {/* 패키징 완료 배지 */}
      {f >= 1066 && f < 1253 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 150, pointerEvents: 'none' }}>
          <div style={{ opacity: doneOp, transform: `scale(${0.86 + pop(f, 1069, { damping: 9 }) * 0.14})`, display: 'flex', alignItems: 'center', gap: 14, padding: '16px 34px', borderRadius: 999, background: 'rgba(20,16,14,0.92)', border: `2px solid ${LIME}`, boxShadow: `0 0 44px rgba(170,255,0,0.32)` }}>
            <span style={{ fontSize: 34 }}>📦</span>
            <span style={{ fontSize: 36, fontWeight: 900, color: '#fff' }}>플러그인 <span style={{ color: LIME }}>패키징 완료</span></span>
          </div>
        </div>
      )}

      {/* 카톡 브리핑 도착 클라이맥스 */}
      {f >= 1253 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 150, pointerEvents: 'none' }}>
          <div style={{ opacity: kakaoOp, transform: `translate(${kakaoShake.x}px, ${kakaoShake.y}px) scale(${0.86 + pop(f, 1256, { damping: 9 }) * 0.14})`, display: 'flex', alignItems: 'center', gap: 16, padding: '18px 36px', borderRadius: 999, background: 'rgba(20,16,14,0.92)', border: `2px solid ${LIME}`, boxShadow: `0 0 50px rgba(170,255,0,0.35)` }}>
            <ClaudeIcon size={40} />
            <span style={{ fontSize: 40, fontWeight: 900, color: '#fff' }}>카톡 <span style={{ color: LIME }}>브리핑 도착!</span></span>
          </div>
        </div>
      )}

      <Sfx at={1069} file="chime_up.mp3" vol={0.35} />
      <Sfx at={1256} file="kakao_ding.mp3" vol={0.5} />
      {STEPS.map((s) => (
        <Sfx key={s.at} at={s.at} file="tick.mp3" vol={0.22} />
      ))}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: '#FF4455', boxShadow: '0 0 12px #FF4455' }} />
    </AbsoluteFill>
  );
};
