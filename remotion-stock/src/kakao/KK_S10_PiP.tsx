/**
 * KK_S10_PiP — 예약 자동화 (1308f · 화면녹화 배경)
 * Whisper 6세그 자막 + 예약완료 카드(오전 7시) + 전기세 안심 카드.
 *
 * 에셋 도착 후: BG = 'kakao/ep1/s10_bg.mp4'
 */

import React from 'react';
import { SceneBase } from './SceneBase';
import { LIME } from './theme';
import { pop, cl, riseFade, Sfx, type Sub } from './fx';

export const KK_S10_PIP_FRAMES = 1308;

const BG = 'kakao/ep1/s10_bg.mp4'; // ✅ 활성화

const SUBS: Sub[] = [
  { from: 0, to: 227, text: '이제 거의 다 왔습니다. 예약 자동화를 해볼게요.', accent: '예약 자동화' },
  { from: 227, to: 476, text: '"방금 만든 플러그인을 매일 오전 7시에 실행해줘"', accent: '오전 7시' },
  { from: 476, to: 756, text: '예약 완료! 앱이 켜져 있으면 매일 7시에 자동 실행됩니다.', accent: '자동 실행' },
  { from: 756, to: 936, text: '"출근할 때 켜두면 전기세 많이 나오지 않냐" 물으시는데', accent: '전기세' },
  { from: 936, to: 1128, text: '윈도우 설정에서 절전 모드 끄고 화면만 꺼지게 하면', accent: '절전 모드' },
  { from: 1128, to: 1308, text: '본체만 도니까 전기세는 거의 안 듭니다.', accent: '거의 안 듭니다' },
];

export const KK_S10_PiP: React.FC = () => (
  <SceneBase video={BG} subs={SUBS} dim={0.12}>
    {(f) => {
      const schedOp = cl(f, 490, 520) * cl(f, 730, 760, 1, 0);
      const schedPunch = pop(f, 490, { damping: 8, stiffness: 240 });
      const powerOp = cl(f, 950, 980);

      return (
        <>
          <Sfx at={490} file="chime_up.mp3" vol={0.42} />
          <Sfx at={950} file="pop_appear.mp3" vol={0.35} />

          {/* 예약 완료 카드 */}
          {f >= 490 && f < 760 && (
            <div
              style={{
                position: 'absolute',
                top: '34%',
                left: '50%',
                transform: `translate(-50%,-50%) scale(${0.85 + schedPunch * 0.15})`,
                opacity: schedOp,
                width: 540,
                padding: '34px 40px',
                background: 'rgba(0,0,0,0.86)',
                border: `2.5px solid ${LIME}`,
                borderRadius: 20,
                textAlign: 'center',
                boxShadow: '0 0 40px rgba(170,255,0,0.3)',
              }}
            >
              <div style={{ fontSize: 56, marginBottom: 10 }}>⏰</div>
              <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 14, letterSpacing: 4, color: LIME, marginBottom: 14 }}>SCHEDULED · 예약 완료</div>
              <div style={{ fontSize: 64, fontWeight: 900, color: LIME, letterSpacing: -1, textShadow: '0 0 28px rgba(170,255,0,0.5)' }}>매일 오전 7:00</div>
              <div style={{ fontSize: 20, color: 'rgba(255,255,255,0.7)', marginTop: 14 }}>앱이 켜져 있으면 자동 실행</div>
            </div>
          )}

          {/* 전기세 안심 카드 */}
          {f >= 950 && (
            <div style={{ position: 'absolute', top: 140, left: '50%', transform: 'translateX(-50%)', opacity: powerOp, width: 760, padding: '26px 32px', background: 'rgba(0,0,0,0.84)', border: '2px solid rgba(170,255,0,0.45)', borderRadius: 16 }}>
              <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 13, letterSpacing: 4, color: LIME, marginBottom: 16 }}>💡 전기세 걱정 NO</div>
              {[
                { ic: '🔌', t: '절전 모드 끄기', at: 980 },
                { ic: '🖥️', t: '화면만 꺼지게 설정', at: 1020 },
                { ic: '✅', t: '본체만 도니까 전기세 거의 0', at: 1060 },
              ].map((it, i) => {
                const { opacity, y } = riseFade(f, it.at, 12, 18);
                return (
                  <div key={i} style={{ opacity, transform: `translateY(${y}px)`, display: 'flex', alignItems: 'center', gap: 16, padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <span style={{ fontSize: 28 }}>{it.ic}</span>
                    <span style={{ fontSize: 26, fontWeight: 700, color: '#fff' }}>{it.t}</span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      );
    }}
  </SceneBase>
);
