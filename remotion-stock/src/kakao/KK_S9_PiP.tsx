/**
 * KK_S9_PiP — 플러그인 패키징 (1412f · 화면녹화 배경)
 * Whisper 7세그 자막 + Before(긴 프롬프트) → After(/브리핑) 대비.
 *
 * 에셋 도착 후: BG = 'kakao/ep1/s09_bg.mp4'
 */

import React from 'react';
import { SceneBase } from './SceneBase';
import { LIME, RED } from './theme';
import { pop, cl, Sfx, type Sub } from './fx';

export const KK_S9_PIP_FRAMES = 1412;

const BG = 'kakao/ep1/s09_bg.mp4'; // ✅ 활성화

const SUBS: Sub[] = [
  { from: 0, to: 221, text: '이걸 매일 반복하면 그것도 일이잖아요.', accent: '매일 반복' },
  { from: 221, to: 426, text: '하나로 패키징해서, 한 줄 명령으로 실행합니다.', accent: '한 줄 명령' },
  { from: 426, to: 678, text: '클로드는 자연어로 대화만 해도 코딩을 짜줍니다.', accent: '자연어' },
  { from: 678, to: 820, text: '복잡한 것 없이 날것 그대로 해볼게요.', accent: '날것 그대로' },
  { from: 820, to: 1066, text: '"방금 만든 아침 브리핑을 플러그인으로 패키징해줘"', accent: '패키징해줘' },
  { from: 1066, to: 1253, text: '작업 완료! 카톡으로 보냈다고 하네요.', accent: '작업 완료' },
  { from: 1253, to: 1412, text: '브리핑이 잘 들어왔습니다. 좋습니다.', accent: '잘 들어왔습니다' },
];

export const KK_S9_PiP: React.FC = () => (
  <SceneBase video={BG} subs={SUBS} dim={0.12}>
    {(f) => {
      const beforeOp = cl(f, 40, 70) * cl(f, 660, 700, 1, 0);
      const afterOp = cl(f, 700, 740);
      const afterPunch = pop(f, 700, { damping: 9, stiffness: 220 });
      const doneOp = cl(f, 1066, 1096) * cl(f, 1380, 1412, 1, 0.3);
      const donePunch = pop(f, 1066, { damping: 8, stiffness: 240 });

      return (
        <>
          <Sfx at={700} file="transition_swipe.mp3" vol={0.4} />
          <Sfx at={1066} file="chime_up.mp3" vol={0.4} />
          <Sfx at={1253} file="kakao_ding.mp3" vol={0.5} />

          {/* Before: 긴 반복 작업 */}
          {f < 700 && (
            <div style={{ position: 'absolute', top: 150, left: '50%', transform: 'translateX(-50%)', opacity: beforeOp, width: 760, padding: '26px 30px', background: 'rgba(0,0,0,0.84)', border: `2px solid ${RED}`, borderRadius: 16 }}>
              <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 13, letterSpacing: 4, color: RED, marginBottom: 16 }}>BEFORE · 매일 반복</div>
              {['MCP 연결 확인', '프롬프트 다시 입력', '종목·조건 재설정', '검색·허용 클릭', '결과 카톡 확인'].map((t, i) => (
                <div key={i} style={{ fontSize: 22, fontWeight: 600, color: 'rgba(255,255,255,0.75)', padding: '8px 0', display: 'flex', gap: 12 }}>
                  <span style={{ color: RED }}>↻</span> {t}
                </div>
              ))}
            </div>
          )}

          {/* After: /브리핑 한 줄 */}
          {f >= 700 && f < 1066 && (
            <div style={{ position: 'absolute', top: 220, left: '50%', transform: `translateX(-50%) scale(${0.9 + afterPunch * 0.1})`, opacity: afterOp, textAlign: 'center' }}>
              <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 15, letterSpacing: 5, color: LIME, marginBottom: 22 }}>AFTER · 패키징 한 방</div>
              <div style={{ display: 'inline-block', fontFamily: "'Roboto Mono', monospace", fontSize: 64, fontWeight: 900, color: '#fff', padding: '24px 56px', background: 'rgba(0,0,0,0.85)', border: `2.5px solid ${LIME}`, borderRadius: 16, boxShadow: '0 0 40px rgba(170,255,0,0.3)' }}>
                <span style={{ color: LIME }}>/브리핑</span>
              </div>
              <div style={{ fontSize: 24, color: 'rgba(255,255,255,0.6)', marginTop: 22 }}>새 창에서도 이 한 줄이면 끝</div>
            </div>
          )}

          {/* 완료 배지 */}
          {f >= 1066 && (
            <div style={{ position: 'absolute', top: '38%', left: '50%', transform: `translate(-50%,-50%) scale(${0.85 + donePunch * 0.15})`, opacity: doneOp, padding: '22px 44px', background: 'rgba(0,0,0,0.85)', border: `2.5px solid ${LIME}`, borderRadius: 16, fontSize: 38, fontWeight: 900, color: LIME, boxShadow: '0 0 34px rgba(170,255,0,0.4)' }}>
              📦 플러그인 패키징 완료 → 💬 카톡 도착
            </div>
          )}
        </>
      );
    }}
  </SceneBase>
);
