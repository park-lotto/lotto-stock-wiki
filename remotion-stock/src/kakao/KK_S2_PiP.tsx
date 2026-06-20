/**
 * KK_S2_PiP — 페인포인트 (1752f · 화면녹화 + 액션 줌인)
 * S5~S10과 동일 톤: 풀스크린 녹화 + 부드러운 줌 + 화면 밖 자막(S02 Whisper 재전사 1:1)
 * 페인포인트 연출이라 STEP 진행바 대신 'PAIN POINT' 라벨 + 뇌동매매/외주 클라이맥스.
 *
 * 자막 = S02_SUBS_final.json (Whisper medium 재전사). ASR 교정: 스탑→스탁브레인 / 종배→종가배팅 / "계획도" 중복 정리.
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, interpolate } from 'remotion';
import { cl, pop, flashAt, shake, zoomPunch, Sfx } from './fx';
import { Watermark, LifeSubBar, LIME, RED } from './life';

export const KK_S2_PIP_FRAMES = 1752;

const NUM = "'Archivo',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

// S02 Whisper medium 재전사 1:1 (단일점·중복 정리, ASR 교정)
const SUBS = [
  { from: 0, to: 84, text: '반갑습니다. 스탁브레인입니다', accent: '스탁브레인' },
  { from: 106, to: 220, text: '자, 아침에 눈 뜨자마자 주식 하시는 분들', accent: '주식' },
  { from: 220, to: 327, text: '솔직히 다 똑같죠? 폰부터 잡고 하루를 시작합니다', accent: '폰부터' },
  { from: 349, to: 498, text: '어제 종가배팅 하신 분들, 야간 선물 어떻게 됐는지 긴장하면서 보실 거고요', accent: '야간 선물' },
  { from: 511, to: 587, text: '미국장 어떻게 됐는지 쓱 봐야 되고', accent: '미국장' },
  { from: 595, to: 700, text: '내가 가진 종목들, 뉴스 뜬 거 있나 막 뒤져봐야 되죠?', accent: '뉴스' },
  { from: 726, to: 866, text: '텔레그램이랑 유튜브 시황 보다 보면 정신없이 8시가 금세 됩니다', accent: '텔레그램' },
  { from: 866, to: 992, text: '정작 제일 중요한 장 열릴 때는 눈도 침침하고', accent: '침침하고' },
  { from: 992, to: 1050, text: '머리도 잘 안 돌아가잖아요', accent: '' },
  { from: 1065, to: 1170, text: '아침부터 준비가 안 된 상황이라서 다 그런 겁니다', accent: '준비가 안 된' },
  { from: 1184, to: 1385, text: '결국 장 초반부터 허둥지둥하다가 계획도 없던 뇌동매매로', accent: '뇌동매매' },
  { from: 1385, to: 1423, text: '하루를 꼬이면서 시작하게 되는 거죠', accent: '' },
  { from: 1423, to: 1526, text: '제 말이 맞나요? 매일 아침 반복되는 이 지독한', accent: '매일 아침' },
  { from: 1526, to: 1576, text: '정보수집 노가다들', accent: '정보수집 노가다' },
  { from: 1588, to: 1710, text: '이제 클로드한테 통째로 외주 맡기자고요. 진짜 쉽게', accent: '외주' },
  { from: 1710, to: 1752, text: '끝납니다. 한번 보세요', accent: '끝납니다' },
];

// 줌 키프레임 — 내용 흐름 경계에서만 미세 변경 (S5 원칙). 화면녹화라 보수적 → Studio 조정.
// 경계: f866(준비 안 됨), f1588(외주 해결책)
const KF = [0, 865, 866, 1587, 1588, 1752];
const FX = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
const FY = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
const SC = [1.10, 1.10, 1.12, 1.12, 1.08, 1.08];

export const KK_S2_PiP: React.FC = () => {
  const f = useCurrentFrame();

  const fx = interpolate(f, KF, FX, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const fy = interpolate(f, KF, FY, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sc = interpolate(f, KF, SC, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // PAIN POINT 라벨 (인트로 후 ~ 뇌동매매 전)
  const labelOp = cl(f, 130, 160) * cl(f, 1560, 1588, 1, 0);

  // 뇌동매매 임팩트 (1184~1423)
  const panicOp = cl(f, 1190, 1216) * cl(f, 1390, 1423, 1, 0);
  const panicShake = shake(f, 1190, 18, 4);

  // 클라이맥스: 클로드에게 외주 (1588~)
  const solveOp = cl(f, 1600, 1640);
  const solvePunch = zoomPunch(f, 1620, 1.12, 18);

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: "'Noto Sans KR', sans-serif", overflow: 'hidden' }}>
      {/* 풀스크린 녹화 + 줌 */}
      <OffthreadVideo
        src={staticFile('kakao/ep1/s02_bg.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${sc})`, transformOrigin: `${fx * 100}% ${fy * 100}%` }}
      />

      {/* 상단/하단 미세 스크림 */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 100, background: 'linear-gradient(rgba(0,0,0,0.6), transparent)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 200, background: 'linear-gradient(transparent, rgba(0,0,0,0.85))', pointerEvents: 'none' }} />

      {/* PAIN POINT 라벨 (STEP 진행바 대신) */}
      <div style={{ position: 'absolute', top: 30, left: 56, opacity: labelOp, fontFamily: MONO, fontSize: 16, letterSpacing: 5, color: RED, textShadow: '0 0 10px rgba(255,68,85,0.5)' }}>
        PAIN POINT · 매일 아침
      </div>

      {/* 뇌동매매 임팩트 */}
      {f >= 1184 && f < 1423 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 150, pointerEvents: 'none' }}>
          <div style={{ opacity: panicOp, transform: `translate(${panicShake.x}px, ${panicShake.y}px)`, fontSize: 64, fontWeight: 900, color: RED, textShadow: '0 0 32px rgba(255,68,85,0.6)' }}>
            결국, 뇌동매매로 시작
          </div>
        </div>
      )}

      {/* 클라이맥스: 클로드에게 외주 */}
      {f >= 1588 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: solveOp, transform: `scale(${solvePunch})`, pointerEvents: 'none' }}>
          <div style={{ fontSize: 30, color: 'rgba(255,255,255,0.75)', fontWeight: 600, marginBottom: 16, textShadow: '0 2px 12px rgba(0,0,0,0.8)' }}>
            이 노가다, 통째로
          </div>
          <div style={{ fontFamily: NUM, fontSize: 92, fontWeight: 900, color: LIME, letterSpacing: -3, textShadow: '0 0 50px rgba(170,255,0,0.55)' }}>
            클로드에게 외주
          </div>
        </div>
      )}

      <Sfx at={1190} file="impact.mp3" vol={0.4} />
      <Sfx at={1600} file="chime_up.mp3" vol={0.42} />

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: '#FF4455', boxShadow: '0 0 12px #FF4455' }} />
    </AbsoluteFill>
  );
};
