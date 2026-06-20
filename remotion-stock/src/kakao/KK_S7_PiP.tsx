/**
 * KK_S7_PiP — PlayMCP 연동 (4295f · 튜토리얼 모드 v3 "액션 줌인", 최장 씬)
 * S5와 동일 아키텍처: 풀스크린 녹화 + 단계별 줌(STEP 안 고정, 컷에서만 순간 변경)
 * + 단계 전환 카드 + 화면 밖 자막(Whisper 44세그 1:1) + 연결완료/카톡수신 클라이맥스.
 *
 * 자막 = S07_timestamps.json 1:1 (의역·병합 금지). ASR 오류만 교정: 코어커→코워크 / 나체방 제거.
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, interpolate } from 'remotion';
import { cl, pop, flashAt, shake, Sfx } from './fx';
import { Watermark, LifeSubBar, ClaudeIcon, LIME } from './life';

export const KK_S7_PIP_FRAMES = 4295;

const NUM = "'Archivo',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

// Whisper medium + word_timestamps 재전사 (단어 단위 정확 싱크) — S07_SUBS_final.json
// 104초 반복("간단하게 한번 해볼게요"×2)은 녹화 원본 그대로 2줄로 싱크.
const SUBS = [
  { from: 0, to: 120, text: '자 이제 방금 말씀드렸던 Play MCP를 다운받을 건데요', accent: 'Play MCP' },
  { from: 120, to: 314, text: '구글에 접속하셔서 Play MCP 들어가시면 되고', accent: 'Play MCP' },
  { from: 337, to: 492, text: '우측 상단에 있는 로그인 버튼을 눌러서 로그인 해주시면 됩니다', accent: '로그인 버튼' },
  { from: 509, to: 658, text: '아래쪽에 보시면 네이버 MCP, 카카오톡 MCP가 두 개가 보이는데', accent: '두 개' },
  { from: 658, to: 761, text: '안 보이시는 분들은 MCP 검색해서 찾으시면 됩니다', accent: 'MCP 검색' },
  { from: 761, to: 902, text: '네이버 MCP는 클로드가 네이버에 직접 검색하게 할 수 있는 기능이고', accent: '네이버 MCP' },
  { from: 902, to: 998, text: '카카오톡 MCP는 검색된 정보를 카카오톡으로', accent: '카카오톡 MCP' },
  { from: 998, to: 1084, text: '보낼 수 있게 연결해주는 기능이라고 보시면 됩니다', accent: '연결' },
  { from: 1084, to: 1150, text: '두 개 다 다운받아야 되니 하나씩', accent: '두 개 다' },
  { from: 1150, to: 1256, text: '들어가셔서 도구함에 추가 누르시면 되고', accent: '도구함에 추가' },
  { from: 1256, to: 1336, text: '카카오톡도 추가해주시면 됩니다', accent: '추가' },
  { from: 1336, to: 1448, text: '그 다음 추가 있으면 코워크로 돌아와서 세팅을 해주셔야 되는데', accent: '코워크' },
  { from: 1448, to: 1512, text: '들어와 보시면 플러스 버튼이 나오는데', accent: '플러스 버튼' },
  { from: 1512, to: 1619, text: '커넥터 들어가시고 커넥터 관리 눌러 보시면', accent: '커넥터 관리' },
  { from: 1619, to: 1705, text: '여기 커넥터 옆에 돋보기 모양이 보입니다', accent: '돋보기' },
  { from: 1705, to: 1823, text: '돋보기에 커넥터 검색을 누르시고 플레이 MCP를 누르시면', accent: '커넥터 검색' },
  { from: 1823, to: 1897, text: '아래쪽에 플레이 MCP라고 뜹니다', accent: '플레이 MCP' },
  { from: 1897, to: 2042, text: '플레이 MCP를 누르시면 오른쪽 보시면 연결되지 않았습니다라 나옵니다', accent: '연결되지 않았습니다' },
  { from: 2042, to: 2110, text: '그 아래 보시면 연결이라는 문구가 나오는데', accent: '연결' },
  { from: 2110, to: 2200, text: '이 연결이라는 걸 눌러 보시면 연결이 될 겁니다', accent: '연결' },
  { from: 2200, to: 2251, text: '잠시만 기다려 보세요', accent: '' },
  { from: 2270, to: 2360, text: '클로드의 플레이 MCP를 연결하기가 나옵니다', accent: '연결하기' },
  { from: 2360, to: 2450, text: '아래 보시면 필수 버튼 두 개를 눌러주시고', accent: '필수 버튼 두 개' },
  { from: 2450, to: 2495, text: '모두 동의 후 계속하기', accent: '모두 동의' },
  { from: 2495, to: 2546, text: '인증을 진행 중입니다', accent: '인증' },
  { from: 2546, to: 2630, text: '잠시 후에 연결이 될 건데 조금만 기다려 주세요', accent: '연결' },
  { from: 2661, to: 2696, text: '연결되면 나옵니다', accent: '연결' },
  { from: 2759, to: 2841, text: '플레이 MCP가 연결이 되었다고 나왔습니다', accent: '연결이 되었다' },
  { from: 2841, to: 2968, text: '연결이 되었으면 뒤로 가기를 누르셔서 메인화면으로 다시 오시고요', accent: '뒤로 가기' },
  { from: 2968, to: 3085, text: '보시면 여기 검색창에 플레이 MCP가 연결이 잘 되었는지', accent: '검색창' },
  { from: 3085, to: 3143, text: '간단하게 한번 해볼게요', accent: '' },
  { from: 3143, to: 3236, text: '연결이 잘 되었으니 테스트를 간단하게 한번 해볼게요', accent: '테스트' },
  { from: 3265, to: 3413, text: '연결된 플레이 MCP를 활용해서 네이버에서 오늘 증시가 어땠는지 검색하고', accent: '검색하고' },
  { from: 3413, to: 3464, text: '카톡으로 보내주라고 한번 해보겠습니다', accent: '카톡으로 보내' },
  { from: 3515, to: 3645, text: '네이버 검색 MCP가 잘 돌아가고 있네요', accent: '잘 돌아가고' },
  { from: 3645, to: 3749, text: '카카오톡 MCP도 잘 돌아가고 있습니다', accent: '잘 돌아가고' },
  { from: 3749, to: 3861, text: '중간에 이 작업에 허용이 나오시면 이걸 눌러 주셔야 됩니다', accent: '허용' },
  { from: 3861, to: 3980, text: '카톡으로 전송이 완료됐다고 하는데 한번 볼게요', accent: '전송이 완료' },
  { from: 3980, to: 4064, text: '카카오톡에 잘 왔는지 한번 보겠습니다', accent: '잘 왔는지' },
  { from: 4064, to: 4145, text: '네 오늘 증시 마감 내용들 잘 나와 있죠', accent: '잘 나와 있죠' },
  { from: 4145, to: 4231, text: '이렇게 해서 간단하게 테스트를 마쳤습니다', accent: '테스트를 마쳤' },
  { from: 4231, to: 4282, text: '자 여기까지 잘 따라오셨습니다', accent: '잘 따라오셨습니다' },
];

const STEPS = [
  { at: 0, label: 'Play MCP 로그인' },
  { at: 512, label: 'MCP 2개 추가' },
  { at: 1337, label: '커넥터 연결' },
  { at: 2968, label: '검색 → 카톡 전송' },
  { at: 3754, label: '카톡 수신 확인' },
];

// 줌 키프레임 — STEP1~4 + STEP5 허용구간(f3754~3979)
const KF = [0, 511, 512, 1336, 1337, 2967, 2968, 3753, 3754, 3979];
const FX = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
const FY = [0.40, 0.40, 0.50, 0.50, 0.44, 0.44, 0.48, 0.48, 0.46, 0.46];
const SC = [1.14, 1.14, 1.18, 1.18, 1.16, 1.16, 1.18, 1.18, 1.20, 1.20];

// f3980~: 카톡 팝업 등장 구간 → translate+scale로 화면 중앙 배치
// 카톡 팝업 중앙 원본 픽셀 위치 (Studio에서 조정)
const KAKAO_CX = 200; // 원본 1920px 기준 x (px)
const KAKAO_CY = 185; // 원본 1080px 기준 y (px)
const KAKAO_SC = 2.0; // 확대 배율

export const KK_S7_PiP: React.FC = () => {
  const f = useCurrentFrame();

  const fx = interpolate(f, KF, FX, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const fy = interpolate(f, KF, FY, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sc = interpolate(f, KF, SC, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // STEP5: 카톡창 중앙(KAKAO_CX, KAKAO_CY)을 화면 중앙(960,540)으로 translate+scale
  const isKakaoStep = f >= 3980;
  const kakaoTx = 960 - KAKAO_CX * KAKAO_SC;
  const kakaoTy = 540 - KAKAO_CY * KAKAO_SC;
  const videoTransform = isKakaoStep
    ? `translate(${kakaoTx}px, ${kakaoTy}px) scale(${KAKAO_SC})`
    : `scale(${sc})`;
  const videoOrigin = isKakaoStep ? '0 0' : `${fx * 100}% ${fy * 100}%`;

  const step = STEPS.reduce((acc, s, i) => (f >= s.at ? i : acc), 0);

  // 단계 전환 카드 (각 STEP 시작 1.5초)
  const trans = STEPS.find((s) => f >= s.at && f < s.at + 45);

  // 연결 완료 배지 (2761~2968)
  const connOp = cl(f, 2761, 2790) * cl(f, 2930, 2968, 1, 0);
  const connPunch = pop(f, 2761, { damping: 8, stiffness: 260 });

  // 카톡 수신 클라이맥스 (3979~4151)
  const kakaoOp = cl(f, 3979, 4005) * cl(f, 4120, 4151, 1, 0);
  const kakaoShake = shake(f, 3979, 16, 5);

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: "'Noto Sans KR', sans-serif", overflow: 'hidden' }}>
      {/* 풀스크린 녹화 + 줌 */}
      <OffthreadVideo
        src={staticFile('kakao/ep1/s07_bg.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: videoTransform, transformOrigin: videoOrigin }}
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
        STEP {String(step + 1).padStart(2, '0')}/05 · PLAY MCP
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

      {/* 연결 완료 배지 (클라이맥스 1) */}
      {f >= 2761 && f < 2968 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18, padding: '24px 48px', borderRadius: 18, background: 'rgba(8,12,6,0.9)', border: `2.5px solid ${LIME}`, boxShadow: `0 0 44px rgba(170,255,0,0.4)`, opacity: connOp, transform: `scale(${0.85 + connPunch * 0.15})` }}>
            <ClaudeIcon size={48} />
            <span style={{ fontSize: 46, fontWeight: 900, color: LIME, letterSpacing: -1, textShadow: `0 0 24px rgba(170,255,0,0.55)` }}>✓ PlayMCP 연결 완료</span>
          </div>
        </div>
      )}

      {/* 카톡 수신 임팩트 (클라이맥스 2) */}
      {f >= 3979 && f < 4151 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', paddingBottom: '11%', opacity: kakaoOp, transform: `translate(${kakaoShake.x}px, ${kakaoShake.y}px)`, pointerEvents: 'none' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 86, marginBottom: 8 }}>💬</div>
            <div style={{ fontSize: 76, fontWeight: 900, color: '#fff', letterSpacing: -2, textShadow: '0 6px 28px rgba(0,0,0,0.95)' }}>
              카톡, <span style={{ color: LIME, textShadow: `0 0 40px rgba(170,255,0,0.6)` }}>바로 왔어요!</span>
            </div>
          </div>
        </div>
      )}

      {/* SFX (녹화 본 음성 위 소량) */}
      {STEPS.map((s) => (
        <Sfx key={s.at} at={s.at} file="tick.mp3" vol={0.22} />
      ))}
      <Sfx at={2761} file="chime_up.mp3" vol={0.35} />
      <Sfx at={3979} file="kakao_ding.mp3" vol={0.5} />
      <Sfx at={3979} file="impact.mp3" vol={0.32} />

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: '#FF4455', boxShadow: '0 0 12px #FF4455' }} />
    </AbsoluteFill>
  );
};
