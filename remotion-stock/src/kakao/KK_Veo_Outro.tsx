/**
 * KK_Veo_Outro — AI 호스트 아웃트로 (920f · outro.mp4 / 4클립 합본)
 * LIFE 3.0 스타일 + Whisper 14세그 자막 + 음성 정렬 카드.
 *
 * 음성 흐름: B1 결과요약(0~203) / B2 자동반복(223~454) / B3 다음편예고(454~684) / B4 구독CTA(684~914)
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame } from 'remotion';
import { cl, pop, flashAt } from './fx';
import { Kicker, Watermark, LifeSubBar, ClaudeIcon, LIME, ORANGE, RED, SUB } from './life';

export const KK_VEO_OUTRO_FRAMES = 920;

const MONO = "'Space Mono','Roboto Mono',monospace";

const win = (f: number, a: number, b: number) => cl(f, a, a + 14) * cl(f, b - 14, b, 1, 0);
const bob = (f: number, amp = 6, speed = 0.05, phase = 0) => Math.sin(f * speed + phase) * amp;

const SUBS = [
  { from: 0, to: 68, text: '방금 보신 이 카톡 브리핑,', accent: '카톡 브리핑' },
  { from: 68, to: 128, text: '어제 딱 10분 세팅한 게', accent: '10분' },
  { from: 128, to: 203, text: '오늘 아침 그대로 온 결과예요.', accent: '그대로' },
  { from: 203, to: 223, text: '아우…', accent: '' },
  { from: 223, to: 259, text: '한 번 만들어 두면', accent: '한 번' },
  { from: 259, to: 328, text: '내일도 모레도 알아서 옵니다.', accent: '알아서' },
  { from: 328, to: 407, text: '아침마다 하던 그 번거로운 정보 수집,', accent: '정보 수집' },
  { from: 407, to: 454, text: '이제 안 하셔도 돼요.', accent: '안 하셔도' },
  { from: 454, to: 524, text: '진짜 핵심은 다음 편이에요.', accent: '다음 편' },
  { from: 524, to: 618, text: '유료 리포트랑 텔레그램, 유튜버 얘기까지', accent: '유료 리포트' },
  { from: 618, to: 684, text: 'AI가 실시간으로 정리해주는 거.', accent: '실시간' },
  { from: 684, to: 787, text: '근데 그건 오늘 이 기본 편을 세팅해 둬야', accent: '기본 편' },
  { from: 787, to: 830, text: '따라오실 수 있어요.', accent: '따라오실 수' },
  { from: 830, to: 920, text: '다음 편 놓치지 않게 구독 눌러주세요!', accent: '구독' },
];

const TEASERS = [
  { ic: '📑', t: '유료 리포트', at: 524 },
  { ic: '✈️', t: '텔레그램', at: 560 },
  { ic: '▶️', t: '유튜버 분석', at: 600 },
];

export const KK_Veo_Outro: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: "'Noto Sans KR', sans-serif" }}>
      <OffthreadVideo src={staticFile('kakao/ep1/outro.mp4')} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />

      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'linear-gradient(105deg, rgba(0,0,0,0.55) 0%, transparent 30%, transparent 68%, rgba(0,0,0,0.5) 100%)' }} />
      <div style={{ position: 'absolute', top: 0, bottom: 0, width: 3, left: `${68 + Math.sin(f * 0.03) * 6}%`, background: 'linear-gradient(transparent, rgba(170,255,0,0.12), transparent)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, 830, 10, 0.5), pointerEvents: 'none' }} />

      <Kicker ch="EP 01" title="NEXT PREVIEW" f={f} />

      {/* ════ B1: 결과 요약 (0~203) ════ */}
      {f < 230 && (
        <div style={{ position: 'absolute', right: 60, top: 130, width: 540, opacity: win(f, 20, 210), transform: `translateY(${bob(f, 7)}px)` }}>
          <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 5, color: LIME, marginBottom: 16 }}>RESULT</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '22px 26px', background: 'rgba(0,0,0,0.8)', border: `2px solid ${LIME}`, borderRadius: 16 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 90, fontWeight: 900, color: '#fff', lineHeight: 0.9, transform: `scale(${0.8 + pop(f, 68, { damping: 8 }) * 0.2})` }}>10</span>
              <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 40, fontWeight: 800, color: LIME }}>분</span>
            </div>
            <span style={{ fontSize: 36, color: ORANGE }}>→</span>
            <div style={{ fontSize: 36, fontWeight: 900, color: LIME, textShadow: `0 0 16px ${LIME}` }}>매일<br />자동</div>
          </div>
        </div>
      )}

      {/* ════ B2: 자동 반복 (223~454) ════ */}
      {f >= 223 && f < 460 && (
        <div style={{ position: 'absolute', right: 60, top: 140, width: 520, opacity: win(f, 230, 454), transform: `translateY(${bob(f, 6)}px)` }}>
          <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 5, color: LIME, marginBottom: 16 }}>한 번 세팅 = 무한 반복</div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
            {['내일', '모레', '매일'].map((t, i) => (
              <div key={i} style={{ flex: 1, textAlign: 'center', padding: '16px 0', background: 'rgba(0,0,0,0.72)', border: `2px solid ${LIME}`, borderRadius: 12, fontSize: 30, fontWeight: 800, color: '#fff', opacity: cl(f, 259 + i * 14, 277 + i * 14), transform: `scale(${0.8 + pop(f, 259 + i * 14, { damping: 8 }) * 0.2})` }}>
                {t} <span style={{ color: LIME }}>✓</span>
              </div>
            ))}
          </div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, padding: '12px 22px', background: 'rgba(255,68,85,0.12)', border: `2px solid ${RED}`, borderRadius: 999, fontSize: 28, fontWeight: 800, color: '#fff', opacity: cl(f, 328, 348) }}>
            <span style={{ textDecoration: 'line-through', color: SUB }}>아침 정보수집</span>
            <span style={{ color: RED }}>0</span>
          </div>
        </div>
      )}

      {/* ════ B3: 다음 편 예고 (454~684) ════ */}
      {f >= 454 && f < 690 && (
        <div style={{ position: 'absolute', right: 60, top: 130, width: 540, opacity: win(f, 460, 684), transform: `translateY(${bob(f, 6)}px)` }}>
          <div style={{ display: 'inline-block', fontFamily: MONO, fontSize: 22, letterSpacing: 5, color: ORANGE, marginBottom: 18, padding: '6px 16px', border: `1.5px solid ${ORANGE}`, borderRadius: 8, textShadow: `0 0 10px ${ORANGE}` }}>NEXT EP · 예고</div>
          {TEASERS.map((t, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 22px', marginBottom: 12, background: 'rgba(0,0,0,0.78)', borderLeft: `4px solid ${LIME}`, borderRadius: '0 12px 12px 0', opacity: cl(f, t.at, t.at + 16), transform: `translateX(${(1 - pop(f, t.at, { damping: 9 })) * 30}px)` }}>
              <span style={{ fontSize: 34 }}>{t.ic}</span>
              <span style={{ fontSize: 34, fontWeight: 800, color: '#fff' }}>{t.t}</span>
              <span style={{ marginLeft: 'auto', fontSize: 22, color: LIME, opacity: cl(f, 618, 640) }}>AI 실시간 ✓</span>
            </div>
          ))}
        </div>
      )}

      {/* ════ B4: 구독 CTA (684~914) ════ */}
      {f >= 684 && (
        <div style={{ position: 'absolute', left: 60, bottom: 210, opacity: win(f, 690, 920), transform: `translateY(${bob(f, 5)}px)` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
            <ClaudeIcon size={50} />
            <div style={{ fontSize: 38, fontWeight: 900, color: '#fff', letterSpacing: -1 }}>
              STOCK<span style={{ color: LIME, textShadow: `0 0 20px ${LIME}` }}>BRAIN</span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12, padding: '18px 38px', background: RED, borderRadius: 12, fontSize: 38, fontWeight: 900, color: '#fff', transform: `scale(${0.9 + pop(f, 830, { damping: 7 }) * 0.1})`, boxShadow: `0 0 ${30 + (f >= 830 ? bob(f, 16, 0.2) : 0)}px rgba(255,68,85,0.6)` }}>
              ▶ 구독
            </div>
            <div style={{ fontSize: 44, opacity: cl(f, 850, 868), transform: `rotate(${bob(f, 10, 0.3)}deg)` }}>🔔</div>
          </div>
        </div>
      )}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: RED, boxShadow: `0 0 12px ${RED}` }} />
    </AbsoluteFill>
  );
};
