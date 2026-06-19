/**
 * KK_Veo_Intro — AI 호스트 인트로 (917f · intro.mp4 / 4클립 합본)
 * v4: Whisper 15세그 자막 + 카드를 실제 음성 프레임에 정렬 (먼저 뜨고 먼저 사라지는 문제 해결).
 *
 * 음성 클립 경계(Whisper): C1 0~239 / C2 239~467 / C3 467~698 / C4 698~917
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame } from 'remotion';
import { cl, pop, flashAt, glitchX } from './fx';
import { Kicker, Watermark, LowerThird, LifeSubBar, ClaudeIcon, LIME, ORANGE, ORANGE_GLOW, SUB } from './life';

export const KK_VEO_INTRO_FRAMES = 917;

const MONO = "'Space Mono','Roboto Mono',monospace";
const NUM = "'Archivo',sans-serif";

const win = (f: number, a: number, b: number) => cl(f, a, a + 14) * cl(f, b - 14, b, 1, 0);
const bob = (f: number, amp = 6, speed = 0.05, phase = 0) => Math.sin(f * speed + phase) * amp;
const countUp = (f: number, start: number, dur: number, target: number) => Math.round(cl(f, start, start + dur, 0, target));

/** Whisper 자막 (실제 음성 타이밍) */
const SUBS = [
  { from: 0, to: 84, text: '방금 이 카톡, 제가 보낸 거 아니에요.', accent: '제가 보낸 거 아니에요' },
  { from: 84, to: 158, text: '어젯밤 클로드한테 한 번 시켜둔 게', accent: '클로드' },
  { from: 158, to: 239, text: '오늘 아침 7시에 저절로 온 겁니다.', accent: '저절로' },
  { from: 239, to: 298, text: '요즘 주식 좀 한다는 분들,', accent: '주식' },
  { from: 298, to: 345, text: 'GPT 잘 안 써요.', accent: 'GPT' },
  { from: 345, to: 406, text: '다 클로드로 갈아탔습니다.', accent: '클로드' },
  { from: 406, to: 467, text: '리서치에 자동화까지 되니까요.', accent: '자동화' },
  { from: 467, to: 532, text: '여러분도 딱 10분만 투자하면,', accent: '10분' },
  { from: 532, to: 634, text: '내일 아침부터 검색창 안 켜도 됩니다.', accent: '검색창 안 켜도' },
  { from: 634, to: 662, text: '코딩요?', accent: '코딩요?' },
  { from: 662, to: 698, text: '한 줄도 없어요.', accent: '한 줄도 없어요' },
  { from: 698, to: 743, text: '방금까지 설명한 저,', accent: '' },
  { from: 743, to: 806, text: '사실 클로드가 만든 AI예요.', accent: 'AI' },
  { from: 806, to: 875, text: '이제 클로드가 만드는 주식 자동화,', accent: '주식 자동화' },
  { from: 875, to: 917, text: '그 첫 단계 들어보세요.', accent: '첫 단계' },
];

export const KK_Veo_Intro: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: "'Noto Sans KR', sans-serif" }}>
      <OffthreadVideo src={staticFile('kakao/ep1/intro.mp4')} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />

      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'linear-gradient(105deg, rgba(0,0,0,0.55) 0%, transparent 30%, transparent 68%, rgba(0,0,0,0.5) 100%)' }} />
      <div style={{ position: 'absolute', top: 0, bottom: 0, width: 3, left: `${30 + Math.sin(f * 0.03) * 6}%`, background: 'linear-gradient(transparent, rgba(170,255,0,0.12), transparent)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, 743, 10, 0.6), pointerEvents: 'none' }} />

      <Kicker ch="EP 01" title="STOCK BRAIN" f={f} />

      {/* ════ C1: 카톡 자동 수신 (음성 0~239) ════ */}
      {f < 245 && (
        <div style={{ position: 'absolute', right: 60, top: 120, width: 560, opacity: win(f, 40, 239), transform: `translateX(${(1 - pop(f, 40, { damping: 11 })) * 60}px) translateY(${bob(f, 7)}px)` }}>
          <div style={{ background: '#FEE500', borderRadius: '18px 18px 0 0', padding: '18px 26px', display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 40, height: 40, borderRadius: 11, background: '#3C1E1E', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22 }}>💬</div>
            <span style={{ fontSize: 28, fontWeight: 900, color: '#3C1E1E' }}>카카오톡</span>
            <span style={{ marginLeft: 'auto', fontFamily: MONO, fontSize: 24, fontWeight: 700, color: '#3C1E1E', transform: `scale(${1 + (f >= 158 ? bob(f, 0.06, 0.3) : 0)})` }}>오전 7:00</span>
          </div>
          <div style={{ background: 'rgba(0,0,0,0.85)', borderRadius: '0 0 18px 18px', border: '1.5px solid rgba(255,229,0,0.45)', borderTop: 'none', padding: '26px 30px' }}>
            <div style={{ fontSize: 34, fontWeight: 900, color: '#fff', marginBottom: 16 }}>📊 오늘의 시장 브리핑</div>
            {['🌐 간밤 미국 증시', '📈 코스피 시초 방향', '⚠️ 핵심 일정 5'].map((t, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '7px 0', fontSize: 25, fontWeight: 700, color: '#fff', opacity: cl(f, 70 + i * 16, 88 + i * 16), transform: `translateX(${(1 - cl(f, 70 + i * 16, 90 + i * 16)) * 20}px)` }}>
                <span style={{ color: LIME, fontSize: 22 }}>✓</span>{t}
              </div>
            ))}
            <div style={{ marginTop: 18, display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 22, fontFamily: MONO, color: LIME, padding: '8px 16px', background: 'rgba(170,255,0,0.14)', borderRadius: 9, opacity: cl(f, 158, 176), boxShadow: `0 0 ${14 + bob(f, 8, 0.15)}px rgba(170,255,0,0.4)` }}>
              ✓ 클로드가 자동 발송
            </div>
          </div>
        </div>
      )}

      {/* ════ C2: GPT → Claude (음성 239~467) ════ */}
      {f >= 239 && f < 472 && (
        <div style={{ position: 'absolute', right: 60, top: 130, width: 560, opacity: win(f, 252, 467), transform: `translateY(${bob(f, 6)}px)` }}>
          <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 5, color: ORANGE, marginBottom: 18, textShadow: `0 0 10px ${ORANGE}` }}>WHY CLAUDE</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 22, marginBottom: 24 }}>
            <span style={{ fontSize: 46, fontWeight: 800, color: SUB, textDecoration: 'line-through', opacity: 0.4 + cl(f, 298, 320) * 0.6, transform: `scale(${1 - cl(f, 298, 330) * 0.12})` }}>GPT</span>
            <span style={{ fontSize: 40, color: ORANGE, opacity: cl(f, 345, 365), transform: `translateX(${cl(f, 345, 375, -10, 0)}px)` }}>→</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, opacity: cl(f, 345, 370), transform: `scale(${0.8 + pop(f, 345, { damping: 9 }) * 0.2})` }}>
              <ClaudeIcon size={54} />
              <span style={{ fontSize: 48, fontWeight: 900, color: '#fff' }}>Claude</span>
            </div>
          </div>
          {['🔍 리서치 자동', '⚙️ 카톡 자동화'].map((t, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '11px 0', opacity: cl(f, 406 + i * 16, 424 + i * 16), transform: `translateX(${(1 - cl(f, 406 + i * 16, 426 + i * 16)) * 24}px)` }}>
              <span style={{ fontSize: 28, color: LIME }}>✓</span>
              <span style={{ fontSize: 32, fontWeight: 700, color: '#fff' }}>{t}</span>
            </div>
          ))}
          <div style={{ marginTop: 16, display: 'inline-block', fontFamily: MONO, fontSize: 24, fontWeight: 700, color: LIME, padding: '10px 22px', border: `2px solid ${LIME}`, borderRadius: 10, transform: `rotate(-6deg) scale(${pop(f, 444, { damping: 6, stiffness: 200 })})`, opacity: cl(f, 444, 458), boxShadow: '0 0 20px rgba(170,255,0,0.3)' }}>
            갈아타기 완료 ✓
          </div>
        </div>
      )}

      {/* ════ C3: 10분 · 코딩 0줄 (음성 467~698) ════ */}
      {f >= 467 && f < 704 && (
        <div style={{ position: 'absolute', right: 60, top: 140, opacity: win(f, 472, 698), textAlign: 'right', transform: `translateY(${bob(f, 6)}px)` }}>
          <div style={{ fontFamily: MONO, fontSize: 22, letterSpacing: 5, color: LIME, marginBottom: 10 }}>SETUP TIME</div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'flex-end', gap: 10, transform: `scale(${0.7 + pop(f, 472, { damping: 8 }) * 0.3})`, transformOrigin: 'right' }}>
            <span style={{ fontFamily: NUM, fontSize: 230, fontWeight: 900, color: '#fff', letterSpacing: -10, lineHeight: 0.85, textShadow: `0 0 ${50 + bob(f, 20, 0.12)}px rgba(170,255,0,0.45)` }}>{countUp(f, 472, 40, 10)}</span>
            <span style={{ fontFamily: NUM, fontSize: 84, fontWeight: 800, color: LIME }}>분</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 14, marginTop: 26 }}>
            {/* 검색창 0번 (음성 532 검색창) / 코딩 0줄 (음성 662 한줄도없어요) */}
            {[['🔎', '검색창', '0번', 532], ['⌨️', '코딩', '0줄', 662]].map((c, i) => (
              <div key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 12, padding: '14px 28px', background: 'rgba(0,0,0,0.72)', border: `2px solid ${LIME}`, borderRadius: 999, opacity: cl(f, c[3] as number, (c[3] as number) + 18), transform: `translateX(${(1 - pop(f, c[3] as number, { damping: 8 })) * 40}px)` }}>
                <span style={{ fontSize: 30 }}>{c[0]}</span>
                <span style={{ fontSize: 36, fontWeight: 800, color: '#fff' }}>{c[1]} <span style={{ color: LIME }}>{c[2]}</span></span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ════ C4: 리빌 (음성 743 사실 AI / 806 자동화) ════ */}
      {f >= 698 && (
        <>
          <div style={{ position: 'absolute', left: 60, top: 120, opacity: win(f, 743, 917), transform: `translateX(${glitchX(f, 743, 761, 10)}px) translateY(${bob(f, 5)}px)`, display: 'inline-flex', alignItems: 'center', gap: 20, padding: '24px 36px', background: 'rgba(20,16,14,0.88)', border: `2.5px solid ${ORANGE}`, borderRadius: 18, boxShadow: `0 0 ${50 + bob(f, 14, 0.1)}px ${ORANGE_GLOW}` }}>
            <ClaudeIcon size={66} />
            <div>
              <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 4, color: ORANGE }}>REVEAL</div>
              <div style={{ fontSize: 42, fontWeight: 900, color: '#fff' }}>이 앵커, 사실 <span style={{ color: ORANGE, textShadow: `0 0 20px ${ORANGE_GLOW}` }}>AI</span>입니다</div>
            </div>
          </div>
          <LowerThird tagline="Claude가 만드는 주식 자동화 — 첫 단계" accent={LIME} f={f} at={806} />
        </>
      )}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: '#FF4455', boxShadow: '0 0 12px #FF4455' }} />
    </AbsoluteFill>
  );
};
