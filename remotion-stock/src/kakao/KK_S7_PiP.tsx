/**
 * KK_S7_PiP — PlayMCP 연동 (4295f · 화면녹화 배경, 최장 씬)
 * Whisper 44세그 자막 + 상단 단계 진행바 + 액션 콜아웃 + 카톡 수신 임팩트.
 *
 * 에셋 도착 후: BG = 'kakao/ep1/s07_bg.mp4'
 */

import React from 'react';
import { SceneBase } from './SceneBase';
import { LIME } from './theme';
import { pop, cl, shake, StepProgress, Sfx, type Sub } from './fx';

export const KK_S7_PIP_FRAMES = 4295;

const BG = 'kakao/ep1/s07_bg.mp4'; // ✅ 활성화

const SUBS: Sub[] = [
  { from: 0, to: 118, text: '이제 Play MCP를 다운받을 건데요.', accent: 'Play MCP' },
  { from: 118, to: 322, text: '구글에 Play MCP 검색해서 접속하세요.', accent: '검색' },
  { from: 340, to: 497, text: '우측 상단 로그인 버튼을 눌러 로그인해주세요.', accent: '로그인' },
  { from: 512, to: 661, text: '아래에 네이버 MCP, 카카오톡 MCP 두 개가 보입니다.', accent: '두 개' },
  { from: 661, to: 763, text: '안 보이면 MCP 검색해서 찾으시면 됩니다.', accent: '검색' },
  { from: 763, to: 901, text: '네이버 MCP는 클로드가 직접 검색하게 하는 기능이고', accent: '네이버 MCP' },
  { from: 901, to: 1087, text: '카톡 MCP는 검색 결과를 카톡으로 보내주는 기능입니다.', accent: '카톡 MCP' },
  { from: 1087, to: 1337, text: '두 개 다 들어가서 도구함에 추가를 눌러주세요.', accent: '도구함에 추가' },
  { from: 1337, to: 1513, text: '추가했으면 코워크로 돌아와 세팅을 해줍니다.', accent: '코워크' },
  { from: 1513, to: 1705, text: '플러스 버튼 → 커넥터 → 커넥터 관리로 들어가면', accent: '커넥터 관리' },
  { from: 1705, to: 1898, text: '돋보기로 커넥터 검색, Play MCP를 누르면', accent: '커넥터 검색' },
  { from: 1898, to: 2110, text: '아래에 Play MCP가 뜨고, 연결되지 않았다고 나옵니다.', accent: '연결되지 않음' },
  { from: 2110, to: 2272, text: '연결이라는 문구를 누르면 연결이 시작됩니다.', accent: '연결' },
  { from: 2272, to: 2450, text: '클로드의 Play MCP 연결하기 화면이 나오는데', accent: 'Play MCP 연결하기' },
  { from: 2450, to: 2546, text: '필수 버튼 2개 누르고 모두 동의 후 계속하기.', accent: '모두 동의' },
  { from: 2546, to: 2761, text: '인증을 진행 중입니다. 잠시 기다려 주세요.', accent: '인증' },
  { from: 2761, to: 2968, text: 'Play MCP가 연결되었습니다! 메인화면으로 돌아옵니다.', accent: '연결되었습니다' },
  { from: 2968, to: 3145, text: '검색창에서 연결이 잘 됐는지 간단히 테스트해볼게요.', accent: '테스트' },
  { from: 3145, to: 3374, text: '"네이버에서 오늘 증시 검색하고 카톡으로 보내줘"', accent: '카톡으로 보내줘' },
  { from: 3415, to: 3636, text: '네이버 검색 MCP, 카카오톡 MCP가 잘 돌아가고 있네요.', accent: '잘 돌아가고' },
  { from: 3636, to: 3754, text: "중간에 '허용'이 나오면 꼭 눌러주셔야 합니다.", accent: '허용' },
  { from: 3754, to: 3979, text: '카톡으로 전송 완료! 한번 확인해 볼게요.', accent: '전송 완료' },
  { from: 3979, to: 4151, text: '카카오톡에 오늘 증시 마감 내용이 잘 와 있죠.', accent: '잘 와 있죠' },
  { from: 4151, to: 4295, text: '이렇게 테스트 끝. 여기까지 잘 따라오셨습니다!', accent: '잘 따라오셨습니다' },
];

const STEP_LABELS = ['로그인', 'MCP 추가', '커넥터 연결', '테스트', '카톡 수신'];
const STEP_BOUNDS = [0, 512, 1337, 2968, 3754]; // 각 단계 시작 프레임

// 액션 콜아웃 (우상단): 특정 구간 동작 안내
const ACTIONS = [
  { from: 340, to: 512, t: '🔑 우측 상단 로그인' },
  { from: 1087, to: 1337, t: '➕ 도구함에 추가' },
  { from: 1705, to: 1898, t: '🔍 커넥터 검색' },
  { from: 2110, to: 2272, t: '🔗 연결 클릭' },
  { from: 3636, to: 3754, t: '✅ 허용 클릭' },
];

export const KK_S7_PiP: React.FC = () => (
  <SceneBase video={BG} subs={SUBS} dim={0.1}>
    {(f) => {
      let current = 0;
      STEP_BOUNDS.forEach((b, i) => {
        if (f >= b) current = i;
      });

      const action = ACTIONS.find((a) => f >= a.from && f < a.to);

      // 연결완료 배지 (2761~2968)
      const connOp = cl(f, 2761, 2790) * cl(f, 2940, 2968, 1, 0);
      const connPunch = pop(f, 2761, { damping: 8, stiffness: 260 });

      // 카톡 왔어요 임팩트 (3979~4151)
      const kakaoOp = cl(f, 3979, 4005) * cl(f, 4120, 4151, 1, 0);
      const kakaoShake = shake(f, 3979, 16, 5);

      return (
        <>
          {STEP_BOUNDS.map((b, i) => (
            <Sfx key={i} at={b} file="tick.mp3" vol={0.3} />
          ))}
          <Sfx at={2761} file="chime_up.mp3" vol={0.4} />
          <Sfx at={3979} file="kakao_ding.mp3" vol={0.5} />
          <Sfx at={3979} file="impact.mp3" vol={0.4} />

          {/* 상단 진행바 */}
          <StepProgress steps={STEP_LABELS} current={current} f={f} />

          {/* 액션 콜아웃 */}
          {action && (
            <div
              style={{
                position: 'absolute',
                top: 110,
                right: 56,
                opacity: cl(f - action.from, 0, 10),
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '14px 24px',
                background: 'rgba(0,0,0,0.8)',
                border: `2px solid ${LIME}`,
                borderRadius: 12,
                boxShadow: '0 0 20px rgba(170,255,0,0.25)',
                fontSize: 24,
                fontWeight: 800,
                color: '#fff',
              }}
            >
              {action.t}
            </div>
          )}

          {/* 연결 완료 배지 */}
          {f >= 2761 && f < 2968 && (
            <div
              style={{
                position: 'absolute',
                top: '40%',
                left: '50%',
                transform: `translate(-50%,-50%) scale(${0.85 + connPunch * 0.15})`,
                opacity: connOp,
                padding: '22px 46px',
                background: 'rgba(0,0,0,0.85)',
                border: `2.5px solid ${LIME}`,
                borderRadius: 16,
                fontSize: 40,
                fontWeight: 900,
                color: LIME,
                boxShadow: '0 0 36px rgba(170,255,0,0.4)',
              }}
            >
              ✓ PlayMCP 연결 완료
            </div>
          )}

          {/* 카톡 왔어요 임팩트 */}
          {f >= 3979 && f < 4151 && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                paddingBottom: '12%',
                opacity: kakaoOp,
                transform: `translate(${kakaoShake.x}px, ${kakaoShake.y}px)`,
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 80, marginBottom: 10 }}>💬</div>
                <div style={{ fontSize: 72, fontWeight: 900, color: '#fff', letterSpacing: -2, textShadow: '0 6px 28px rgba(0,0,0,0.9)' }}>
                  카톡, <span style={{ color: LIME, textShadow: '0 0 40px rgba(170,255,0,0.6)' }}>바로 왔어요!</span>
                </div>
              </div>
            </div>
          )}
        </>
      );
    }}
  </SceneBase>
);
