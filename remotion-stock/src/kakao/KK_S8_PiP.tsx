/**
 * KK_S8_PiP — 프롬프트 작성 → 카톡 브리핑 (1585f · 튜토리얼 모드 v3 "액션 줌인")
 * S5/S7과 동일 아키텍처: 풀스크린 녹화 + 단계별 줌(STEP 안 고정, 컷에서만 순간 변경)
 * + 단계 전환 카드 + 화면 밖 자막(S08_timestamps 1:1) + 브리핑 도착 클라이맥스.
 *
 * 자막 = S08_timestamps.json 1:1 (긴 세그만 분할). ASR 교정: 프론포트→프롬프트 / 나체방 제거 / "제가 제가"→"제가".
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, interpolate } from 'remotion';
import { cl, pop, flashAt, shake, Sfx } from './fx';
import { Watermark, LifeSubBar, ClaudeIcon, LIME } from './life';

export const KK_S8_PIP_FRAMES = 1585;

const NUM = "'Archivo',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

// S08_timestamps 8세그 1:1 — 긴 세그(1·2·3·5·7·8)만 자연 위치 분할(프레임 비례)
const SUBS = [
  { from: 0, to: 70, text: '자 이제 핵심인데요', accent: '핵심' },
  { from: 70, to: 184, text: '업무 지시서를 잘 써야 AI 직원도 똑바로 일하거든요', accent: '업무 지시서' },
  { from: 184, to: 270, text: '주식용 프롬프트는 날카로워야 되는데', accent: '날카로워야' },
  { from: 270, to: 335, text: '제가 쓰는 프롬프트가 하나 있습니다', accent: '프롬프트' },
  { from: 335, to: 460, text: '템플릿은 고정댓글에 넣어둘 테니까 복사해서 그대로 쓰시면 되고', accent: '고정댓글' },
  { from: 460, to: 527, text: '검색 한번 해보겠습니다', accent: '검색' },
  { from: 527, to: 673, text: '네이버 검색 MCP를 사용하고 있네요. 허용 버튼을 눌러줍니다', accent: '허용 버튼' },
  { from: 673, to: 800, text: '검색이 잘 됐고 카카오톡 MCP를 사용하는 것 같습니다', accent: '카카오톡 MCP' },
  { from: 800, to: 879, text: '허용 버튼을 눌러줄게요', accent: '허용 버튼' },
  { from: 879, to: 1063, text: '간밤의 주요 섹터, 미국과 한국의 섹터 연결 브리핑이 잘 도착했네요', accent: '브리핑' },
  { from: 1063, to: 1190, text: '전 섹터 간밤 종합 내용들이 있고요', accent: '전 섹터' },
  { from: 1190, to: 1346, text: '그다음 코스피 코스닥 시초 방향 어떻게 예상하는지 나오고 있고', accent: '시초 방향' },
  { from: 1346, to: 1470, text: '이번 주에 리스크도 나오고 있고요', accent: '리스크' },
  { from: 1470, to: 1585, text: '핵심 일정, 이런 식으로 다섯 개로 정리를 해줬습니다', accent: '핵심 일정' },
];

const STEPS = [
  { at: 0, label: '업무 지시서 작성' },
  { at: 527, label: 'MCP 허용' },
  { at: 879, label: '브리핑 도착' },
  { at: 1063, label: '결과 정리 확인' },
];

// 줌 키프레임 — STEP 안에서 완전히 고정, 컷(플래시)에서만 순간 변경 (S5/S7 동일 원칙)
// FX는 전부 0.5(수평 중앙). FY/SC만 단계별 미세 조정 → Studio에서 포커스 미세조정.
const KF = [0, 526, 527, 878, 879, 1062, 1063, 1585];
const FX = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
const FY = [0.50, 0.50, 0.45, 0.45, 0.45, 0.45, 0.50, 0.50];
const SC = [1.12, 1.12, 1.16, 1.16, 1.14, 1.14, 1.10, 1.10];

export const KK_S8_PiP: React.FC = () => {
  const f = useCurrentFrame();

  const fx = interpolate(f, KF, FX, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const fy = interpolate(f, KF, FY, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sc = interpolate(f, KF, SC, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const step = STEPS.reduce((acc, s, i) => (f >= s.at ? i : acc), 0);

  // 단계 전환 카드 (각 STEP 시작 1.5초)
  const trans = STEPS.find((s) => f >= s.at && f < s.at + 45);

  // 브리핑 도착 클라이맥스 (879~1063)
  const briefOp = cl(f, 882, 910) * cl(f, 1020, 1063, 1, 0);
  const briefShake = shake(f, 882, 14, 4);

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: "'Noto Sans KR', sans-serif", overflow: 'hidden' }}>
      {/* 풀스크린 녹화 + 줌 */}
      <OffthreadVideo
        src={staticFile('kakao/ep1/s08_bg.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${sc})`, transformOrigin: `${fx * 100}% ${fy * 100}%` }}
      />

      {/* 상단/하단 미세 스크림 (텍스트 가독, 화면 본문은 밝게 유지) */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 90, background: 'linear-gradient(rgba(0,0,0,0.55), transparent)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 200, background: 'linear-gradient(transparent, rgba(0,0,0,0.85))', pointerEvents: 'none' }} />

      {/* 상단 얇은 진행바 (4단계) */}
      <div style={{ position: 'absolute', top: 22, left: 56, right: 56, display: 'flex', gap: 8 }}>
        {STEPS.map((_, i) => (
          <div key={i} style={{ flex: 1, height: 5, borderRadius: 3, background: i <= step ? LIME : 'rgba(255,255,255,0.18)', boxShadow: i <= step ? `0 0 8px ${LIME}` : 'none' }} />
        ))}
      </div>
      <div style={{ position: 'absolute', top: 38, left: 56, fontFamily: MONO, fontSize: 16, letterSpacing: 3, color: LIME }}>
        STEP {String(step + 1).padStart(2, '0')}/04 · 프롬프트 → 브리핑
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

      {/* 브리핑 도착 클라이맥스 */}
      {f >= 879 && f < 1063 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 150, pointerEvents: 'none' }}>
          <div style={{ opacity: briefOp, transform: `translate(${briefShake.x}px, ${briefShake.y}px) scale(${0.86 + pop(f, 882, { damping: 9 }) * 0.14})`, display: 'flex', alignItems: 'center', gap: 16, padding: '18px 36px', borderRadius: 999, background: 'rgba(20,16,14,0.92)', border: `2px solid ${LIME}`, boxShadow: `0 0 50px rgba(170,255,0,0.35)` }}>
            <ClaudeIcon size={40} />
            <span style={{ fontSize: 40, fontWeight: 900, color: '#fff' }}>카톡 <span style={{ color: LIME }}>브리핑 도착!</span></span>
          </div>
        </div>
      )}

      <Sfx at={882} file="kakao_ding.mp3" vol={0.5} />
      {STEPS.map((s) => (
        <Sfx key={s.at} at={s.at} file="tick.mp3" vol={0.22} />
      ))}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: '#FF4455', boxShadow: '0 0 12px #FF4455' }} />
    </AbsoluteFill>
  );
};
