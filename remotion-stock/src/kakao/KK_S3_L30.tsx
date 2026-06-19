/**
 * KK_S3_L30 — 철학 (2404f · 발표자/녹음 배경 + 그래픽 오버레이)
 * Whisper 25세그 자막 + 3페이즈 그래픽.
 *
 * 에셋 도착 후: BG = 'kakao/ep1/s03_bg.mp4'
 */

import React from 'react';
import { SceneBase } from './SceneBase';
import { LIME, RED } from './theme';
import { cl, riseFade, zoomPunch, Sfx, type Sub } from './fx';

export const KK_S3_L30_FRAMES = 2404;

const BG: string | null = null; // 에셋 도착 시 'kakao/ep1/s03_bg.mp4'

const SUBS: Sub[] = [
  { from: 0, to: 107, text: '요즘 유튜브에 나오는 것 중에', accent: '유튜브' },
  { from: 107, to: 233, text: 'AI가 알아서 타점 잡아준다는 프로그램 본 적 있으신가요?', accent: '타점 잡아준다' },
  { from: 233, to: 397, text: '근데 단언컨대, 주식판에 절대 치트키는 없습니다.', accent: '절대 치트키는 없습니다' },
  { from: 397, to: 530, text: 'AI가 로직 짜고 코드는 정말 잘 만들고', accent: '코드' },
  { from: 530, to: 602, text: '백테스팅 수없이 돌릴 수 있어요.', accent: '백테스팅' },
  { from: 602, to: 774, text: '하지만 아직 1%가 부족한, 인간의 도움이 필요하더라고요.', accent: '인간의 도움' },
  { from: 774, to: 905, text: '아시다시피 주식은 살아있는 생물이잖아요.', accent: '살아있는 생물' },
  { from: 905, to: 1012, text: '기계가 숫자만으로는 절대 예측 못하는', accent: '예측 못하는' },
  { from: 1012, to: 1135, text: '시장의 심리, 인간의 광기가 핵심입니다.', accent: '인간의 광기' },
  { from: 1135, to: 1290, text: '제가 아침에 자동화 프로그램을 여러 개 돌리고 있는데', accent: '자동화' },
  { from: 1290, to: 1441, text: '그 중 하나가 오늘 설명할 카톡 정보수집 프로그램이에요.', accent: '카톡 정보수집' },
  { from: 1441, to: 1610, text: '이것도 AI한테 종목 추천받으려는 게 아닙니다.', accent: '종목 추천' },
  { from: 1610, to: 1826, text: '장 열리기 전 우리가 하는 건, 너무나 단순 반복 일이거든요.', accent: '단순 반복' },
  { from: 1826, to: 1948, text: '이런 건 AI가 인간보다 월등히 잘합니다.', accent: '월등히 잘합니다' },
  { from: 1948, to: 2032, text: '바로 정보수집과 요약이죠.', accent: '정보수집과 요약' },
  { from: 2032, to: 2167, text: '이런 일들은 AI한테 모두 자동화 시켜버리고', accent: '자동화' },
  { from: 2167, to: 2291, text: '우리는 장 열렸을 때, 오늘 주도 섹터가 어디지?', accent: '주도 섹터' },
  { from: 2291, to: 2404, text: '돈은 어디로 가지? 이 흐름만 집중해서 보자는 겁니다.', accent: '이 흐름만 집중' },
];

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  position: 'absolute',
  background: 'rgba(0,0,0,0.82)',
  border: `2px solid rgba(170,255,0,0.45)`,
  borderRadius: 14,
  ...extra,
});

export const KK_S3_L30: React.FC = () => (
  <SceneBase video={BG} audio="kakao/ep1/s03_audio.mp4" subs={SUBS} dim={0.2}>
    {(f) => {
      const p1Op = cl(f, 233, 260) * cl(f, 880, 905, 1, 0);
      const xPunch = zoomPunch(f, 240, 1.12, 14);
      const p2Op = cl(f, 1135, 1165) * cl(f, 1920, 1948, 1, 0);
      const p3Op = cl(f, 2032, 2062);

      return (
        <>
          <Sfx at={240} file="impact.mp3" vol={0.45} />
          <Sfx at={1948} file="pop_appear.mp3" vol={0.35} />
          <Sfx at={2060} file="chime_up.mp3" vol={0.4} />

          {/* Phase1: 빨간 X 환상파괴 카드 */}
          <div style={panel({ top: 110, left: '50%', transform: `translateX(-50%) scale(${xPunch})`, opacity: p1Op, width: 760, padding: '26px 34px', textAlign: 'center', borderColor: RED })}>
            <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 13, letterSpacing: 4, color: RED, marginBottom: 14 }}>MYTH · AI 만능설 파괴</div>
            <div style={{ fontSize: 38, fontWeight: 900, color: '#fff', lineHeight: 1.4 }}>
              ❌ 주식판에 <span style={{ color: RED }}>절대 치트키</span>는 없다
            </div>
            <div style={{ fontSize: 20, color: 'rgba(255,255,255,0.55)', marginTop: 14 }}>
              살아있는 생물 · 시장의 심리 · 인간의 광기
            </div>
          </div>

          {/* Phase2: AI가 잘하는 것 */}
          <div style={panel({ top: 120, left: 90, opacity: p2Op, width: 520, padding: '24px 30px' })}>
            <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 13, letterSpacing: 4, color: LIME, marginBottom: 16 }}>AI가 월등한 영역</div>
            {[
              { ic: '🔍', t: '정보 수집', at: 1200 },
              { ic: '📝', t: '요약·정리', at: 1240 },
              { ic: '🔁', t: '단순 반복 작업', at: 1280 },
            ].map((it, i) => {
              const { opacity, y } = riseFade(f, it.at, 12, 20);
              return (
                <div key={i} style={{ opacity, transform: `translateY(${y}px)`, display: 'flex', alignItems: 'center', gap: 16, padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  <span style={{ fontSize: 30 }}>{it.ic}</span>
                  <span style={{ fontSize: 28, fontWeight: 800, color: '#fff' }}>{it.t}</span>
                  <span style={{ marginLeft: 'auto', fontFamily: "'Roboto Mono', monospace", fontSize: 13, color: LIME }}>✓ 자동화</span>
                </div>
              );
            })}
          </div>

          {/* Phase3: 집중할 것 */}
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingBottom: '14%', opacity: p3Op }}>
            <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 15, letterSpacing: 5, color: LIME, marginBottom: 16 }}>FOCUS · 우리가 볼 것</div>
            <div style={{ fontSize: 64, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>오늘 주도 섹터는 어디?</div>
            <div style={{ fontSize: 64, fontWeight: 900, color: LIME, letterSpacing: -2, textShadow: '0 0 40px rgba(170,255,0,0.5)' }}>돈은 어디로 가는가</div>
          </div>
        </>
      );
    }}
  </SceneBase>
);
