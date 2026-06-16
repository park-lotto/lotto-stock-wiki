/**
 * KK_S3_ClaudeLive — AI 신화파괴 + 진짜 이유 (스크리닝 도구)
 * 디자인: Claude Live 공유 시스템 (ClaudeLiveShared) 재사용
 * 1212프레임 = 40.4초 @ 30fps
 * 소스: kakao/s3_claude_live.mp4 (8K→1080p 트랜스코딩)
 */

import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import {
  Background, PresenterWindow, TopBar, SubtitleBar,
  CL, SERIF, SANS, ci, sp, blend,
  ClaudeLogo,
} from './ClaudeLiveShared';

export const KK_S3_CLAUDELIVE_FRAMES = 1212;

// ── 섹션별 챕터 + 액센트 (구간마다 다채로운 색)
const SECTIONS = [
  { id: 'A', from: 0,    to: 118,  accent: '#D97757', chapter: 'AI 자동매매 — 진실은?' },
  { id: 'B', from: 118,  to: 216,  accent: '#D9694F', chapter: '치트키는 없다' },
  { id: 'C', from: 216,  to: 340,  accent: '#4F9D9B', chapter: '주식은 살아있는 생물' },
  { id: 'D', from: 340,  to: 446,  accent: '#6E92C4', chapter: '심리와 수급의 힘' },
  { id: 'E', from: 446,  to: 528,  accent: '#E8A93C', chapter: '진짜 이유' },
  { id: 'F', from: 528,  to: 607,  accent: '#9A938A', chapter: '종목 추천이 아니다' },
  { id: 'G', from: 607,  to: 790,  accent: '#9B6A8E', chapter: '장 전 스크리닝' },
  { id: 'H', from: 790,  to: 934,  accent: '#7FA66B', chapter: '5가지 스크리닝' },
  { id: 'I', from: 934,  to: 1006, accent: '#D97757', chapter: 'AI가 수집, 나는 집중' },
  { id: 'J', from: 1006, to: 1141, accent: '#6FA86A', chapter: '돈의 흐름에만' },
  { id: 'K', from: 1141, to: 1212, accent: '#E8A93C', chapter: '스마트한 시대' },
];

const accentAt = (f: number) => {
  const cur = SECTIONS.find(s => f >= s.from && f < s.to) ?? SECTIONS[SECTIONS.length - 1];
  const idx = SECTIONS.indexOf(cur);
  const prev = idx > 0 ? SECTIONS[idx - 1] : cur;
  const t = ci(f, cur.from, Math.min(cur.from + 18, cur.to));
  return blend(prev.accent, cur.accent, t);
};

// ── 자막 (Whisper 기반, KK_S3_L30에서)
const SUBS = [
  { from: 0,    to: 118,  text: 'AI가 알아서 매수·매도 타점 잡아준다는\n프로그램들 많죠.',        accent: '프로그램들' },
  { from: 118,  to: 216,  text: '단언컨대 주식판에\n그런 절대 치트키는 존재하지 않습니다.',        accent: '치트키는 존재하지 않습니다' },
  { from: 216,  to: 340,  text: '주식은 살아있는 생물이라\nAI가 수치만으로 계산할 수 없는',        accent: '살아있는 생물' },
  { from: 340,  to: 446,  text: '인간의 심리와 수급의 힘이\n있다는 게 핵심이거든요.',              accent: '심리와 수급' },
  { from: 446,  to: 528,  text: '제가 이 아침 자동화를 돌리는 진짜 이유는',                        accent: '진짜 이유' },
  { from: 528,  to: 607,  text: 'AI에게 종목을 추천받으려는 게 아닙니다.',                          accent: '아닙니다' },
  { from: 607,  to: 790,  text: '간밤에 쌓인 뉴스·이벤트들을\n장 열리기 전 제한된 시간 안에',     accent: '제한된 시간 안에' },
  { from: 790,  to: 934,  text: '스크리닝해 두려는 겁니다.',                                        accent: '스크리닝' },
  { from: 934,  to: 1006, text: '힘든 자료 수집일은 AI에게 시키고',                                 accent: 'AI에게' },
  { from: 1006, to: 1141, text: '우리는 장이 열렸을 때\n오직 돈의 흐름에만 집중하면 됩니다.',      accent: '돈의 흐름' },
  { from: 1141, to: 1212, text: '주식도 이제 스마트한 시대가 된 겁니다.',                           accent: '스마트한 시대' },
];

// ── AI 한계 항목 (C/D 구간)
const AI_LIMITS = [
  { icon: '🧠', label: '인간의 심리',   sub: '공포·탐욕 — 비선형 반응',  delay: 228 },
  { icon: '📡', label: '수급의 힘',     sub: '세력·외인 — 보이지 않는 손', delay: 252 },
  { icon: '💬', label: '시장 분위기',   sub: '정성적 맥락 — 숫자 밖',     delay: 276 },
  { icon: '⚡', label: '뉴스 뉘앙스',   sub: '맥락 해석 — AI의 한계',     delay: 300 },
];

// ── 스크리닝 목록 (G/H 구간)
const SCREEN_ITEMS = [
  { icon: '🌐', label: '미국·유럽 간밤 증시',  delay: 618 },
  { icon: '📰', label: '오버나이트 뉴스 필터', delay: 644 },
  { icon: '📋', label: '주요 이벤트 캘린더',   delay: 670 },
  { icon: '🏢', label: '국내 공시·실적',        delay: 696 },
  { icon: '📊', label: '관심 종목 동향',        delay: 722 },
];

const COL_X = 1230, COL_W = 650;
const colCard = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  position: 'absolute', left: COL_X, width: COL_W, borderRadius: 16, overflow: 'hidden', ...extra,
});

// ── 우측 컬럼 (S3 전용)
const RightColumn: React.FC<{ f: number; accent: string }> = ({ f, accent }) => {
  const op = (a: number, b: number, fi = 18, fo = 14) =>
    Math.min(ci(f, a, a + fi), ci(f, b - fo, b, 1, 0));

  return (
    <>
      {/* A: AI 자동매매 소개 카드 (0–117) */}
      {op(6, 118) > 0.01 && (() => {
        const o = op(6, 118); const rise = (1 - sp(f, 8, 11, 240)) * 24;
        return (
          <div style={{ ...colCard({ top: 280, opacity: o, background: CL.cardDark,
            border: `2px solid ${accent}`,
            boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 36px ${accent}44` }),
            transform: `translateY(${rise}px)`, padding: '36px 40px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
              <ClaudeLogo size={52} />
              <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700,
                color: accent, letterSpacing: '0.10em', textTransform: 'uppercase' }}>AI 자동매매</span>
            </div>
            <div style={{ fontFamily: SERIF, fontSize: 52, fontWeight: 700, color: CL.onDark, lineHeight: 1.1 }}>
              AI가 알아서<br />타점을 잡는다?
            </div>
            <div style={{ fontFamily: SANS, fontSize: 20, fontWeight: 500, color: CL.muted, marginTop: 18 }}>
              이 주장, 사실일까요?
            </div>
          </div>
        );
      })()}

      {/* B: 치트키 없다 (118–215) */}
      {op(118, 216) > 0.01 && (() => {
        const o = op(118, 216); const pop = 0.6 + sp(f, 122, 8, 240) * 0.4;
        return (
          <div style={{ ...colCard({ top: 300, opacity: o, background: CL.cardDark,
            border: `2px solid ${accent}`,
            boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 40px ${accent}55`,
            padding: '40px', textAlign: 'center' }),
            transform: `scale(${pop})` }}>
            <div style={{ fontSize: 56, marginBottom: 16 }}>❌</div>
            <div style={{ fontFamily: SERIF, fontSize: 22, fontWeight: 600, color: accent,
              letterSpacing: '0.06em', marginBottom: 16 }}>MYTH</div>
            <div style={{ fontFamily: SERIF, fontSize: 56, fontWeight: 700, color: CL.onDark, lineHeight: 1.1 }}>
              절대 치트키는<br />존재하지 않는다
            </div>
          </div>
        );
      })()}

      {/* C/D: AI 한계 리스트 (216–445) */}
      {op(216, 446) > 0.01 && (() => {
        const o = op(216, 446);
        return (
          <div style={{ ...colCard({ top: 210, opacity: o, background: CL.cardDark,
            border: `2px solid ${accent}`,
            boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 28px ${accent}44` }) }}>
            <div style={{ padding: '20px 26px', borderBottom: `1px solid ${accent}40`,
              background: `linear-gradient(90deg, ${accent}22 0%, transparent 100%)` }}>
              <div style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
                letterSpacing: '0.10em', textTransform: 'uppercase' }}>AI가 못 보는 것</div>
              <div style={{ fontFamily: SERIF, fontSize: 36, fontWeight: 700, color: CL.onDark, marginTop: 4 }}>
                수치 너머의 세계
              </div>
            </div>
            <div style={{ padding: '10px 0 16px' }}>
              {AI_LIMITS.map((item, i) => {
                const io = ci(f, item.delay, item.delay + 14);
                const ix = (1 - sp(f, item.delay, 11, 260)) * 22;
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14,
                    padding: '12px 26px', opacity: io, transform: `translateX(${ix}px)` }}>
                    <div style={{ fontSize: 28, flexShrink: 0 }}>{item.icon}</div>
                    <div>
                      <div style={{ fontFamily: SANS, fontSize: 22, fontWeight: 700, color: CL.onDark }}>{item.label}</div>
                      <div style={{ fontFamily: SANS, fontSize: 16, fontWeight: 400, color: CL.muted, marginTop: 2 }}>{item.sub}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* E/F: 진짜 이유 reveal (446–606) */}
      {op(446, 607) > 0.01 && (() => {
        const o = op(446, 607); const rise = (1 - sp(f, 450, 10, 240)) * 30;
        const line2Op = ci(f, 534, 554);
        return (
          <div style={{ ...colCard({ top: 300, opacity: o, background: CL.cardCream,
            border: `2px solid ${accent}`,
            boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 36px ${accent}55`,
            padding: '40px 44px' }),
            transform: `translateY(${rise}px)` }}>
            <div style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
              letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 16 }}>진짜 이유</div>
            <div style={{ fontFamily: SERIF, fontSize: 48, fontWeight: 700, color: CL.ink, lineHeight: 1.2 }}>
              종목 추천이<br />아닙니다
            </div>
            <div style={{ fontFamily: SANS, fontSize: 20, fontWeight: 500, color: CL.muted,
              marginTop: 18, opacity: line2Op }}>
              그렇다면 무엇을 위해?
            </div>
          </div>
        );
      })()}

      {/* G/H: 스크리닝 리스트 (607–933) */}
      {op(607, 934) > 0.01 && (() => {
        const o = op(607, 934);
        return (
          <div style={{ ...colCard({ top: 190, opacity: o, background: CL.cardDark,
            border: `2px solid ${accent}`,
            boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 28px ${accent}44` }) }}>
            <div style={{ padding: '20px 26px', borderBottom: `1px solid ${accent}40`,
              background: `linear-gradient(90deg, ${accent}22 0%, transparent 100%)` }}>
              <div style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
                letterSpacing: '0.10em', textTransform: 'uppercase' }}>장 전 스크리닝</div>
              <div style={{ fontFamily: SERIF, fontSize: 36, fontWeight: 700, color: CL.onDark, marginTop: 4 }}>
                5가지를 선별한다
              </div>
            </div>
            <div style={{ padding: '10px 0 16px' }}>
              {SCREEN_ITEMS.map((item, i) => {
                const io = ci(f, item.delay, item.delay + 14);
                const ix = (1 - sp(f, item.delay, 11, 260)) * 22;
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14,
                    padding: '12px 26px', opacity: io, transform: `translateX(${ix}px)` }}>
                    <div style={{ fontSize: 28 }}>{item.icon}</div>
                    <span style={{ fontFamily: SANS, fontSize: 22, fontWeight: 600, color: CL.onDark }}>{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* I: AI 수집 → 나는 집중 대비 (934–1005) */}
      {op(934, 1006) > 0.01 && (() => {
        const o = op(934, 1006);
        const leftO  = ci(f, 938, 956); const rightO = ci(f, 956, 974);
        const arrowO = ci(f, 970, 988);
        return (
          <div style={{ ...colCard({ top: 290, opacity: o }) }}>
            <div style={{ display: 'flex', alignItems: 'stretch', gap: 0 }}>
              {/* AI 박스 */}
              <div style={{ flex: 1, background: CL.cardDark, border: `2px solid ${accent}`,
                borderRadius: 14, padding: '28px 24px', textAlign: 'center', opacity: leftO }}>
                <div style={{ fontSize: 40, marginBottom: 10 }}>🤖</div>
                <div style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
                  letterSpacing: '0.08em' }}>AI</div>
                <div style={{ fontFamily: SERIF, fontSize: 32, fontWeight: 700,
                  color: CL.onDark, marginTop: 6 }}>수집·정리</div>
              </div>
              {/* 화살표 */}
              <div style={{ display: 'flex', alignItems: 'center', padding: '0 14px', opacity: arrowO }}>
                <span style={{ fontFamily: SERIF, fontSize: 36, color: CL.muted }}>→</span>
              </div>
              {/* 나 박스 */}
              <div style={{ flex: 1, background: CL.cardCream, border: `2px solid ${accent}`,
                borderRadius: 14, padding: '28px 24px', textAlign: 'center', opacity: rightO }}>
                <div style={{ fontSize: 40, marginBottom: 10 }}>👤</div>
                <div style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: CL.ink,
                  letterSpacing: '0.08em' }}>나</div>
                <div style={{ fontFamily: SERIF, fontSize: 32, fontWeight: 700,
                  color: CL.ink, marginTop: 6 }}>판단·집중</div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* J: 돈의 흐름 (1006–1140) */}
      {op(1006, 1141) > 0.01 && (() => {
        const o = op(1006, 1141); const pop = 0.7 + sp(f, 1010, 8, 240) * 0.3;
        return (
          <div style={{ ...colCard({ top: 310, opacity: o, background: CL.cardCream,
            border: `2px solid ${accent}`,
            boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 40px ${accent}55`,
            padding: '44px', textAlign: 'center' }),
            transform: `scale(${pop})` }}>
            <div style={{ fontSize: 52, marginBottom: 16 }}>💰</div>
            <div style={{ fontFamily: SERIF, fontSize: 22, fontWeight: 600, color: accent,
              letterSpacing: '0.06em', marginBottom: 14 }}>FOCUS</div>
            <div style={{ fontFamily: SERIF, fontSize: 60, fontWeight: 700, color: CL.ink, lineHeight: 1.1 }}>
              오직<br />돈의 흐름
            </div>
          </div>
        );
      })()}

      {/* K: 스마트한 시대 완료 (1141–1212) */}
      {op(1141, 1212) > 0.01 && (() => {
        const o = op(1141, 1212); const pop = 0.6 + sp(f, 1145, 8, 240) * 0.4;
        return (
          <div style={{ ...colCard({ top: 300, opacity: o, background: CL.cardCream,
            border: `2px solid ${accent}`,
            boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 44px ${accent}66`,
            padding: '44px', textAlign: 'center' }),
            transform: `scale(${pop})` }}>
            <div style={{ width: 90, height: 90, borderRadius: '50%', margin: '0 auto 20px',
              background: `${accent}26`, border: `2px solid ${accent}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 44 }}>✨</div>
            <div style={{ fontFamily: SERIF, fontSize: 50, fontWeight: 700, color: CL.ink }}>스마트한 시대</div>
            <div style={{ fontFamily: SANS, fontSize: 20, fontWeight: 500, color: CL.muted, marginTop: 12 }}>
              주식 투자도 이제 달라졌습니다
            </div>
          </div>
        );
      })()}
    </>
  );
};

// ── 메인
export const KK_S3_ClaudeLive: React.FC = () => {
  const f = useCurrentFrame();
  const accent = accentAt(f);
  const globalFade = ci(f, KK_S3_CLAUDELIVE_FRAMES - 12, KK_S3_CLAUDELIVE_FRAMES, 1, 0);

  return (
    <AbsoluteFill style={{ overflow: 'hidden', opacity: globalFade }}>
      <Background f={f} accent={accent} />
      <PresenterWindow f={f} accent={accent} videoSrc="kakao/s3_claude_live.mp4" />
      <RightColumn f={f} accent={accent} />
      <TopBar f={f} accent={accent} sections={SECTIONS} totalFrames={KK_S3_CLAUDELIVE_FRAMES} />
      <SubtitleBar f={f} accent={accent} subs={SUBS} />
    </AbsoluteFill>
  );
};
