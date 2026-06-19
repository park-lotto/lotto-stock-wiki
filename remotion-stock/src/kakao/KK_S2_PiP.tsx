/**
 * KK_S2_PiP — 페인포인트 (1191f · 무음 화면/발표자 배경 + 텍스트 오버레이)
 * Whisper 무음 → 자막 없음. 스크립트 키프레이즈를 수동 타임라인으로 몽타주.
 *
 * 에셋 도착 후: BG = 'kakao/ep1/s02_bg.mp4'
 */

import React from 'react';
import { SceneBase } from './SceneBase';
import { LIME, RED } from './theme';
import { cl, riseFade, shake, zoomPunch, Sfx, type Sub } from './fx';

export const KK_S2_PIP_FRAMES = 1191;

const BG = 'kakao/ep1/s02_bg.mp4'; // ✅ 활성화

const SUBS: Sub[] = [];

// 페인포인트 칩 (수동 타임라인)
const PAINS = [
  { t: '📱 눈 뜨자마자 폰부터', at: 70 },
  { t: '🌙 야간선물 확인', at: 150 },
  { t: '🇺🇸 미국장 체크', at: 230 },
  { t: '📰 내 종목 뉴스 뒤지기', at: 310 },
  { t: '💬 텔레그램·유튜브 시황', at: 390 },
  { t: '⏰ 어느새 8시…', at: 470 },
];

export const KK_S2_PiP: React.FC = () => (
  <SceneBase video={BG} subs={SUBS} dim={0.25}>
    {(f) => {
      const headerOp = cl(f, 8, 28);
      const panicShake = shake(f, 690, 30, 5);
      const panicOp = cl(f, 690, 720);
      const solveOp = cl(f, 980, 1010);
      const solvePunch = zoomPunch(f, 1000, 1.1, 16);

      return (
        <>
          {/* SFX */}
          <Sfx at={690} file="impact.mp3" vol={0.45} />
          <Sfx at={1000} file="chime_up.mp3" vol={0.45} />

          {/* 헤더 */}
          <div style={{ position: 'absolute', top: 70, left: 0, right: 0, textAlign: 'center', opacity: headerOp }}>
            <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 16, letterSpacing: 6, color: RED, marginBottom: 12 }}>
              PAIN POINT · 매일 아침
            </div>
            <div style={{ fontSize: 50, fontWeight: 900, color: '#fff' }}>주식러의 지독한 정보수집 노가다</div>
          </div>

          {/* 페인 칩 쌓이기 */}
          <div style={{ position: 'absolute', top: 230, left: 110, display: 'flex', flexDirection: 'column', gap: 16 }}>
            {PAINS.map((p, i) => {
              const { opacity, y } = riseFade(f, p.at, 12, 24);
              const fadeLate = cl(f, 690, 740, 1, 0.25);
              return (
                <div
                  key={i}
                  style={{
                    opacity: opacity * fadeLate,
                    transform: `translateY(${y}px)`,
                    alignSelf: 'flex-start',
                    padding: '14px 24px',
                    background: 'rgba(0,0,0,0.72)',
                    border: '1px solid rgba(255,255,255,0.18)',
                    borderRadius: 12,
                    fontSize: 28,
                    fontWeight: 700,
                    color: '#fff',
                  }}
                >
                  {p.t}
                </div>
              );
            })}
          </div>

          {/* 클라이맥스: 뇌동매매 */}
          <div
            style={{
              position: 'absolute',
              top: 420,
              left: 0,
              right: 0,
              textAlign: 'center',
              opacity: panicOp * cl(f, 940, 980, 1, 0),
              transform: `translate(${panicShake.x}px, ${panicShake.y}px)`,
            }}
          >
            <div style={{ fontSize: 64, fontWeight: 900, color: RED, textShadow: '0 0 30px rgba(255,68,85,0.6)' }}>
              결국, 뇌동매매로 하루 시작
            </div>
          </div>

          {/* 해결책 */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: solveOp,
              transform: `scale(${solvePunch})`,
            }}
          >
            <div style={{ fontSize: 30, color: 'rgba(255,255,255,0.7)', fontWeight: 600, marginBottom: 18 }}>
              이 노가다, 통째로
            </div>
            <div style={{ fontSize: 92, fontWeight: 900, color: LIME, letterSpacing: -3, textShadow: '0 0 50px rgba(170,255,0,0.5)' }}>
              클로드에게 외주
            </div>
          </div>
        </>
      );
    }}
  </SceneBase>
);
