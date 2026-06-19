/**
 * KK_S8_PiP — 프롬프트 (1585f · 화면녹화 배경, CTA 20%)
 * Whisper 8세그 자막 + 프롬프트 템플릿 카드 + 고정댓글 CTA + 결과 요약 칩.
 *
 * 에셋 도착 후: BG = 'kakao/ep1/s08_bg.mp4'
 */

import React from 'react';
import { SceneBase } from './SceneBase';
import { LIME } from './theme';
import { cl, riseFade, typeReveal, Sfx, type Sub } from './fx';

export const KK_S8_PIP_FRAMES = 1585;

const BG = 'kakao/ep1/s08_bg.mp4'; // ✅ 활성화

const SUBS: Sub[] = [
  { from: 0, to: 184, text: '이제 핵심입니다. 업무 지시서를 잘 써야 AI도 똑바로 일해요.', accent: '업무 지시서' },
  { from: 184, to: 335, text: '주식용 프롬프트는 날카로워야 합니다.', accent: '날카로워야' },
  { from: 335, to: 527, text: '템플릿은 고정댓글에 넣어둘 테니 복사해서 쓰세요.', accent: '고정댓글' },
  { from: 527, to: 673, text: '네이버 검색 MCP 사용 중 — 허용 눌러줍니다.', accent: '허용' },
  { from: 673, to: 879, text: '카톡 MCP도 사용 — 허용 눌러줄게요.', accent: '허용' },
  { from: 879, to: 1063, text: '미국·한국 섹터 연결 브리핑이 잘 도착했네요.', accent: '브리핑' },
  { from: 1063, to: 1346, text: '전 섹터 종합 + 코스피·코스닥 시초 방향 예상까지.', accent: '시초 방향' },
  { from: 1346, to: 1585, text: '이번 주 리스크와 핵심 일정, 5개로 정리해줬습니다.', accent: '핵심 일정' },
];

const PROMPT = '[삼성전자] [SK하이닉스] 관련 기관 리포트와 핵심 뉴스만 추려서 카톡으로 보내줘';

const RESULTS = [
  { ic: '🌐', t: '간밤 섹터 종합', at: 900 },
  { ic: '📈', t: '코스피·코스닥 시초 방향', at: 1080 },
  { ic: '⚠️', t: '이번 주 리스크', at: 1360 },
  { ic: '📅', t: '핵심 일정', at: 1440 },
];

export const KK_S8_PiP: React.FC = () => (
  <SceneBase video={BG} subs={SUBS} dim={0.12}>
    {(f) => {
      const cardOp = cl(f, 40, 70) * cl(f, 860, 900, 1, 0);
      const typed = typeReveal(PROMPT, f, 90, 26);
      const ctaOp = cl(f, 340, 365) * cl(f, 520, 545, 1, 0);

      return (
        <>
          <Sfx at={40} file="pop_appear.mp3" vol={0.35} />
          <Sfx at={340} file="pop_appear.mp3" vol={0.35} />
          {RESULTS.map((r, i) => (
            <Sfx key={i} at={r.at} file="tick.mp3" vol={0.3} />
          ))}
          <Sfx at={900} file="chime_up.mp3" vol={0.4} />

          {/* 프롬프트 템플릿 카드 */}
          {f < 900 && (
            <div
              style={{
                position: 'absolute',
                top: 120,
                left: '50%',
                transform: 'translateX(-50%)',
                opacity: cardOp,
                width: 980,
                padding: '26px 32px',
                background: 'rgba(0,0,0,0.86)',
                border: `2px solid ${LIME}`,
                borderRadius: 16,
                boxShadow: '0 0 30px rgba(170,255,0,0.18)',
              }}
            >
              <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 13, letterSpacing: 4, color: LIME, marginBottom: 16 }}>PROMPT · 업무 지시서</div>
              <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 26, fontWeight: 700, color: '#fff', lineHeight: 1.6, minHeight: 90 }}>
                {typed}
                <span style={{ opacity: f % 16 < 8 ? 1 : 0, color: LIME }}>▋</span>
              </div>
              <div style={{ marginTop: 14, fontSize: 16, color: 'rgba(255,255,255,0.55)' }}>
                <span style={{ color: LIME, fontWeight: 700 }}>[종목명]</span> 부분만 본인 종목으로 바꾸세요
              </div>
            </div>
          )}

          {/* 고정댓글 CTA (20% 노출) */}
          {f >= 340 && f < 545 && (
            <div
              style={{
                position: 'absolute',
                bottom: 230,
                left: '50%',
                transform: 'translateX(-50%)',
                opacity: ctaOp,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '14px 30px',
                background: 'rgba(170,255,0,0.14)',
                border: `1.5px solid ${LIME}`,
                borderRadius: 999,
                fontSize: 24,
                fontWeight: 800,
                color: LIME,
              }}
            >
              📌 프롬프트 템플릿 → 고정댓글에서 복사 ↓
            </div>
          )}

          {/* 허용 콜아웃 */}
          {((f >= 527 && f < 673) || (f >= 673 && f < 879)) && (
            <div
              style={{
                position: 'absolute',
                top: 130,
                right: 60,
                opacity: 1,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '12px 22px',
                background: 'rgba(0,0,0,0.8)',
                border: '2px solid #FF4455',
                borderRadius: 12,
                fontSize: 22,
                fontWeight: 800,
                color: '#fff',
              }}
            >
              ✅ '허용' 버튼 클릭
            </div>
          )}

          {/* 결과 요약 칩 */}
          {f >= 880 && (
            <div style={{ position: 'absolute', top: 130, left: '50%', transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', gap: 14, width: 720 }}>
              <div style={{ fontFamily: "'Roboto Mono', monospace", fontSize: 14, letterSpacing: 4, color: LIME, textAlign: 'center', marginBottom: 6, opacity: cl(f, 880, 900) }}>RESULT · 카톡 브리핑 도착</div>
              {RESULTS.map((r, i) => {
                const { opacity, y } = riseFade(f, r.at, 12, 20);
                return (
                  <div key={i} style={{ opacity, transform: `translateY(${y}px)`, display: 'flex', alignItems: 'center', gap: 16, padding: '16px 24px', background: 'rgba(0,0,0,0.8)', border: '1px solid rgba(170,255,0,0.4)', borderRadius: 12 }}>
                    <span style={{ fontSize: 28 }}>{r.ic}</span>
                    <span style={{ fontSize: 26, fontWeight: 800, color: '#fff' }}>{r.t}</span>
                    <span style={{ marginLeft: 'auto', fontFamily: "'Roboto Mono', monospace", fontSize: 13, color: LIME }}>✓</span>
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
