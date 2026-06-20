/**
 * KK_S5_PiP — 클로드 설치 (2545f · 튜토리얼 모드 v3 "액션 줌인")
 * 풀스크린 녹화 + 단계별 줌인(시선 유도) + 단계 전환 컷 + 화면 밖 자막.
 * 화면 위 그래픽 최소화: 줌으로 강조, STEP은 전환 카드 + 상단 얇은 진행바.
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, interpolate } from 'remotion';
import { cl, pop, flashAt } from './fx';
import { Watermark, LifeSubBar, ClaudeIcon, LIME, ORANGE, ORANGE_GLOW, SUB } from './life';

export const KK_S5_PIP_FRAMES = 2545;

const NUM = "'Archivo',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

// Whisper 23세그 1:1 정렬 (음성 싱크 정확)
const SUBS = [
  { from: 0, to: 131, text: '먼저 PC에 클로드 데스크탑 앱을 설치할 겁니다.', accent: '클로드 데스크탑 앱' },
  { from: 131, to: 286, text: '구글에 먼저 접속해서 "클로드 데스크탑 앱"이라고 검색해 보세요.', accent: '클로드 데스크탑 앱' },
  { from: 286, to: 329, text: '메뉴에 나옵니다.', accent: '' },
  { from: 329, to: 488, text: '들어가시면 파란 글자로 "클로드 다운로드 페이지"라고 있을 거예요.', accent: '다운로드 페이지' },
  { from: 488, to: 523, text: '그걸 클릭하세요.', accent: '클릭' },
  { from: 523, to: 665, text: '다음엔 윈도우 버전, 네 클릭하시면 됩니다.', accent: '윈도우 버전' },
  { from: 665, to: 731, text: '내 PC에 다운로드가 될 겁니다.', accent: '다운로드' },
  { from: 731, to: 878, text: '이제 다운로드된 폴더에서 파일을 실행시켜 볼 거예요.', accent: '실행' },
  { from: 883, to: 941, text: '약 1분 정도 소요될 겁니다.', accent: '1분' },
  { from: 995, to: 1099, text: '자, 설치를 완료하고 앱을 실행시켜 보시면', accent: '' },
  { from: 1099, to: 1211, text: '좌측 상단에 코워크 탭 보입니다.', accent: '코워크 탭' },
  { from: 1211, to: 1273, text: '여기예요.', accent: '' },
  { from: 1273, to: 1382, text: '일단 설치는 성공적으로 되었으니, 잠시 후에', accent: '성공적으로' },
  { from: 1382, to: 1510, text: '프롬프트 넣어보고 질문을 해보도록 하죠.', accent: '프롬프트' },
  { from: 1510, to: 1632, text: '카톡 자동화를 하기 위해선 코워크라는 기능을 써야 되는데,', accent: '코워크' },
  { from: 1632, to: 1698, text: '이건 유료 플랜이 필요합니다.', accent: '유료 플랜' },
  { from: 1698, to: 1836, text: '근데 아쉽게도 무료 버전엔 이 자동화 기능 자체가 없거든요.', accent: '자동화 기능' },
  { from: 1836, to: 1982, text: '구글에 "클로드 AI"라고 들어가서 가입만 하면 되는데요.', accent: '가입' },
  { from: 1982, to: 2116, text: '무료 AI도 많은데 굳이 싶으시죠.', accent: '굳이' },
  { from: 2116, to: 2250, text: '근데 주식하다 보면 솔직히 3만원은 수수료 나가는 거나,', accent: '3만원' },
  { from: 2250, to: 2364, text: '손절 나가는 거에 비해서 사실 굉장히 작은 액수잖아요.', accent: '작은 액수' },
  { from: 2364, to: 2465, text: '매일 아침 자동으로 리포트 대령해주는 비서한테,', accent: '리포트 대령' },
  { from: 2465, to: 2545, text: '월 3만원, 기꺼이 투자해 보세요.', accent: '월 3만원' },
];

const STEPS = [
  { at: 0, label: '구글에서 검색' },
  { at: 329, label: '다운로드 페이지 클릭' },
  { at: 523, label: '윈도우 버전 클릭' },
  { at: 731, label: '설치 파일 실행' },
  { at: 995, label: '코워크 탭 확인' },
];

// 줌 키프레임 — STEP 안에서 완전히 고정, 컷(플래시)에서만 순간 변경
// [직전f, 컷f] 쌍으로 동일 값 유지 → 배경 떨림 완전 제거
const KF = [0, 328, 329, 522, 523, 730, 731, 994, 995, 1210, 1211, 1509, 1510, 2545];
const FX = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.16, 0.16, 0.16, 0.16, 0.5, 0.5];
const FY = [0.52, 0.52, 0.54, 0.54, 0.55, 0.55, 0.58, 0.58, 0.12, 0.12, 0.12, 0.12, 0.5, 0.5];
const SC = [1.22, 1.22, 1.26, 1.26, 1.30, 1.30, 1.22, 1.22, 1.48, 1.48, 1.35, 1.35, 1.06, 1.06];

export const KK_S5_PiP: React.FC = () => {
  const f = useCurrentFrame();

  const fx = interpolate(f, KF, FX, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const fy = interpolate(f, KF, FY, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sc = interpolate(f, KF, SC, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const step = STEPS.reduce((acc, s, i) => (f >= s.at ? i : acc), 0);

  // 단계 전환 카드 (각 STEP 시작 1.5초)
  const trans = STEPS.find((s) => f >= s.at && f < s.at + 45);

  // 가치 카드 ($19) — 마지막 "월 3만원" 라인(f2465)에서만
  const showVal = f >= 2455;
  const valOp = cl(f, 2455, 2480) * cl(f, 2532, 2545, 1, 0);

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: "'Noto Sans KR', sans-serif", overflow: 'hidden' }}>
      {/* 풀스크린 녹화 + 줌 */}
      <OffthreadVideo
        src={staticFile('kakao/ep1/s05_bg.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${sc})`, transformOrigin: `${fx * 100}% ${fy * 100}%` }}
      />

      {/* 상단/하단 미세 스크림 (텍스트 가독, 화면 본문은 밝게 유지) */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 90, background: 'linear-gradient(rgba(0,0,0,0.55), transparent)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 200, background: 'linear-gradient(transparent, rgba(0,0,0,0.85))', pointerEvents: 'none' }} />

      {/* 상단 얇은 진행바 (5단계) */}
      <div style={{ position: 'absolute', top: 22, left: 56, right: 56, display: 'flex', gap: 8 }}>
        {STEPS.map((_, i) => (
          <div key={i} style={{ flex: 1, height: 5, borderRadius: 3, background: i <= step ? LIME : 'rgba(255,255,255,0.18)', boxShadow: i <= step ? `0 0 8px ${LIME}` : 'none' }} />
        ))}
      </div>
      <div style={{ position: 'absolute', top: 38, left: 56, fontFamily: MONO, fontSize: 16, letterSpacing: 3, color: LIME }}>
        STEP {String(step + 1).padStart(2, '0')}/05 · CLAUDE SETUP
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

      {/* $19 가치 카드 (클라이맥스) */}
      {showVal && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: valOp }}>
          <div style={{ width: 820, padding: '54px 70px', borderRadius: 26, background: 'rgba(20,16,14,0.94)', border: `2px solid ${ORANGE}`, boxShadow: `0 0 70px ${ORANGE_GLOW}`, display: 'flex', flexDirection: 'column', alignItems: 'center', transform: `scale(${0.86 + pop(f, 2360, { damping: 9 }) * 0.14})` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 22 }}>
              <ClaudeIcon size={46} />
              <span style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 5, color: ORANGE }}>CLAUDE PRO</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline' }}>
              <span style={{ fontFamily: NUM, fontSize: 170, fontWeight: 900, color: ORANGE, letterSpacing: -6, lineHeight: 0.9, textShadow: `0 0 50px ${ORANGE_GLOW}` }}>$19</span>
              <span style={{ fontFamily: NUM, fontSize: 54, fontWeight: 800, color: SUB, marginLeft: 12 }}>/ month</span>
            </div>
            <div style={{ marginTop: 22, fontSize: 36, fontWeight: 800, color: '#fff' }}>
              월 <span style={{ color: LIME }}>3만원</span> — 기꺼이 투자해 보세요
            </div>
          </div>
        </div>
      )}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: '#FF4455', boxShadow: '0 0 12px #FF4455' }} />
    </AbsoluteFill>
  );
};
