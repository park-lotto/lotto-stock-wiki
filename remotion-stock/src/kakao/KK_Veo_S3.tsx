/**
 * KK_Veo_S3 — S3 철학 선언 (Veo AI 아바타, 클로즈업 진지)
 *
 * veo_s3.mp4 전체화면 + 철학 텍스트 + 글자수 카톡 데모
 * 총 1212프레임 (40.4s @ 30fps)
 *
 * Phase 1 f0~360  : "절대 치트키는 없다" 철학 선언 텍스트
 * Phase 2 f360~720: "노가다는 기계에게" 핵심 역할 분담
 * Phase 3 f720~900: 전환 / 빈 배경
 * Phase 4 f900~1212: 카카오 글자수 데모 (질문 → 즉답)
 */

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { FONT } from '../constants';

export const KK_VEO_S3_FRAMES = 1212;

const KAKAO   = '#FAE100';
const KAKAO_D = '#3A2F00';
const CHAT_BG = '#B2C7D9';
const WHITE   = '#FFFFFF';

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

const sp = (f: number, from: number, cfg = { damping: 24, stiffness: 160, mass: 1.0 }) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: cfg });

const SUBTITLES = [
  { text: 'AI가 알아서 매수 매도 잡아준다는 프로그램들 많죠?',         from: 0,   to: 120 },
  { text: "단언컨대 그런 '절대 치트키'는 존재하지 않습니다",            from: 120, to: 260 },
  { text: '주식은 살아있는 생물 — 기계가 수치만으로 계산 불가',         from: 260, to: 400 },
  { text: "진짜 이유는 '오늘 장의 트렌드를 스크리닝'하는 것",           from: 400, to: 560 },
  { text: '노가다는 기계에게, 우리는 돈의 흐름에만 집중',              from: 560, to: 720 },
  { text: '이걸 직접 확인해봤습니다',                                  from: 860, to: 940 },
  { text: '카카오톡으로 질문 하나 보내봤습니다',                       from: 940, to: 1040 },
  { text: '즉시 답변이 왔습니다 — 73자',                              from: 1040, to: 1140 },
];

// 철학 텍스트 블록
const DECL_LINES = [
  { text: "절대 치트키",   color: '#FF3B30', delay: 40,  fontSize: 82 },
  { text: "존재하지 않는다", color: WHITE,     delay: 70,  fontSize: 60 },
];

// 역할 분담 텍스트
const ROLE_LINES = [
  { label: '기계',   task: '정보 수집 노가다',    color: '#888',   delay: 390, icon: '🤖' },
  { label: '트레이더', task: '돈의 흐름 집중',    color: '#FAE100', delay: 440, icon: '📊' },
];

// 카카오 채팅 메시지
const DEMO_START = 900;
const PHONE_W = 380;
const PHONE_H = 560;

const USER_MSG = "시장에 보면 AI가 알아서 매수 매도 타점 잡아준다는 프로그램들 많죠?\n단언컨대 주식판에 그런 '절대 치트키'는 존재하지 않습니다.\n\n이게 몇글자야?";
const CLAUDE_MSG = "공백 포함  73자\n공백 제외  57자";

export const KK_Veo_S3: React.FC = () => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const activeSub = SUBTITLES.find(s => f >= s.from && f < s.to);

  // ── Phase 1: 철학 선언 텍스트 (f40~320) ──────────────────────────
  const declOp = f < 340
    ? clamp(f, 30, 60)
    : clamp(f, 340, 368, 1, 0);

  // ── Phase 2: 역할 분담 (f360~720) ────────────────────────────────
  const roleOp = f < 730
    ? clamp(f, 360, 390)
    : clamp(f, 730, 755, 1, 0);

  // ── Phase 4: 폰 데모 ─────────────────────────────────────────────
  const phoneProg = spring({
    frame: Math.max(0, f - DEMO_START),
    fps,
    config: { damping: 18, stiffness: 130, mass: 1.0 },
    durationInFrames: 40,
  });
  const phoneX = interpolate(phoneProg, [0, 1], [PHONE_W + 60, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const phoneOp = clamp(f, DEMO_START, DEMO_START + 28);

  // 사용자 메시지 (f=DEMO_START+40)
  const userMsgAt  = DEMO_START + 40;
  const userMsgOp  = clamp(f, userMsgAt, userMsgAt + 20);
  const userMsgY   = interpolate(f, [userMsgAt, userMsgAt + 20], [14, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
  });

  // "입력 중..." 타이핑 표시
  const typingAt  = userMsgAt + 20;
  const typingOp  = f > typingAt && f < typingAt + 60
    ? clamp(f, typingAt, typingAt + 16)
    : 0;
  const typingDot = (d: number) => 0.3 + Math.abs(Math.sin((f - typingAt - d * 5) * 0.35)) * 0.7;

  // Claude 답변 (f=DEMO_START+120)
  const claudeAt = DEMO_START + 120;
  const claudeOp = clamp(f, claudeAt, claudeAt + 22);
  const claudeY  = interpolate(f, [claudeAt, claudeAt + 22], [12, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
  });

  // 73자 숫자 강조
  const numScale = 0.8 + sp(f, claudeAt + 4, { damping: 10, stiffness: 300, mass: 0.5 }) * 0.2;

  return (
    <AbsoluteFill style={{ fontFamily: FONT, overflow: 'hidden', background: '#000' }}>

      {/* 아바타 동영상 */}
      <OffthreadVideo
        src={staticFile('kakao/veo_s3.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* 그라디언트 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.28) 0%, transparent 40%, transparent 58%, rgba(0,0,0,0.55) 100%)',
      }} />

      {/* ── Phase 1: 철학 선언 블록 ─────────────────────────────── */}
      <div style={{
        position: 'absolute',
        top: '50%', left: 80,
        transform: 'translateY(-60%)',
        opacity: declOp, pointerEvents: 'none',
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {/* 작은 라벨 */}
        <div style={{
          fontSize: 13, fontWeight: 700, letterSpacing: 4,
          color: 'rgba(255,255,255,0.50)',
          textTransform: 'uppercase',
        }}>AI 한계 선언</div>
        {DECL_LINES.map((line, i) => {
          const prog = sp(f, 40 + line.delay);
          return (
            <div key={i} style={{
              fontSize: line.fontSize,
              fontWeight: 900,
              color: line.color,
              lineHeight: 1.05,
              opacity: interpolate(prog, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(prog, [0, 1], [20, 0], {
                extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
              })}px)`,
              textShadow: line.color === '#FF3B30'
                ? '0 0 30px rgba(255,59,48,0.5)'
                : 'none',
              letterSpacing: line.color === '#FF3B30' ? -2 : -1,
            }}>{line.text}</div>
          );
        })}
        {/* 밑줄 강조 */}
        <div style={{
          height: 3, borderRadius: 2,
          background: '#FF3B30',
          width: interpolate(sp(f, 110), [0, 1], [0, 260], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          }),
          boxShadow: '0 0 12px rgba(255,59,48,0.6)',
        }} />
      </div>

      {/* ── Phase 2: 역할 분담 카드 ─────────────────────────────── */}
      <div style={{
        position: 'absolute',
        top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        opacity: roleOp, pointerEvents: 'none',
        display: 'flex', flexDirection: 'column', gap: 20, width: 660,
      }}>
        <div style={{
          fontSize: 16, fontWeight: 700, letterSpacing: 4,
          color: 'rgba(255,255,255,0.45)',
          textTransform: 'uppercase', textAlign: 'center',
        }}>역할 분담</div>

        {ROLE_LINES.map((row, i) => {
          const rp = sp(f, row.delay);
          return (
            <div key={i} style={{
              opacity: interpolate(rp, [0, 1], [0, 1]),
              transform: `translateX(${interpolate(rp, [0, 1], [-24, 0], {
                extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
              })}px)`,
              background: 'rgba(0,0,0,0.55)',
              backdropFilter: 'blur(12px)',
              borderRadius: 14,
              border: `1.5px solid ${row.color}44`,
              padding: '16px 24px',
              display: 'flex', alignItems: 'center', gap: 18,
            }}>
              <span style={{ fontSize: 36 }}>{row.icon}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,0.45)', letterSpacing: 2 }}>
                  {row.label}
                </div>
                <div style={{ fontSize: 30, fontWeight: 800, color: row.color, letterSpacing: -0.5 }}>
                  {row.task}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Phase 4: 카카오 폰 데모 ─────────────────────────────── */}
      <div style={{
        position: 'absolute',
        right: 72,
        top: '50%',
        transform: `translateY(-50%) translateX(${phoneX}px)`,
        opacity: phoneOp,
        width: PHONE_W,
        height: PHONE_H,
        background: WHITE,
        borderRadius: 46,
        border: '2px solid rgba(0,0,0,0.08)',
        boxShadow: '0 24px 72px rgba(0,0,0,0.40)',
        overflow: 'hidden',
        zIndex: 10,
      }}>
        {/* 다이나믹 아일랜드 */}
        <div style={{
          position: 'absolute', top: 12, left: '50%',
          transform: 'translateX(-50%)',
          width: 96, height: 28, background: '#111', borderRadius: 15, zIndex: 2,
        }} />

        {/* 카카오 헤더 */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 82,
          background: KAKAO,
          display: 'flex', alignItems: 'flex-end',
          paddingBottom: 11, paddingInline: 15, gap: 9,
        }}>
          {/* 백버튼 */}
          <span style={{ color: KAKAO_D, fontSize: 18, fontWeight: 700, marginRight: 4 }}>‹</span>
          <div style={{
            width: 28, height: 28, borderRadius: '50%',
            background: KAKAO_D,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14,
          }}>🙋</div>
          <div style={{ color: KAKAO_D, fontSize: 13, fontWeight: 700 }}>나에게 쓰기</div>
        </div>

        {/* 채팅 본문 */}
        <div style={{
          position: 'absolute', top: 82, left: 0, right: 0, bottom: 48,
          background: CHAT_BG,
          padding: '10px 8px',
          display: 'flex', flexDirection: 'column', gap: 8,
          overflow: 'hidden',
        }}>

          {/* 타임스탬프 */}
          <div style={{
            textAlign: 'center', color: 'rgba(0,0,0,0.38)',
            fontSize: 10, fontWeight: 500, marginBottom: 2,
          }}>오전 11:24</div>

          {/* 사용자 메시지 (오른쪽, 노란색) */}
          <div style={{
            opacity: userMsgOp,
            transform: `translateY(${userMsgY}px)`,
            display: 'flex', justifyContent: 'flex-end',
          }}>
            <div style={{
              background: KAKAO,
              borderRadius: '14px 4px 14px 14px',
              padding: '9px 11px',
              maxWidth: '84%',
              boxShadow: '0 2px 6px rgba(0,0,0,0.12)',
            }}>
              <div style={{
                fontSize: 10, color: KAKAO_D, lineHeight: 1.75,
                whiteSpace: 'pre-line',
              }}>{USER_MSG}</div>
            </div>
          </div>

          {/* 입력 중... */}
          {typingOp > 0 && (
            <div style={{
              opacity: typingOp,
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <div style={{
                background: WHITE,
                borderRadius: '4px 14px 14px 14px',
                padding: '8px 14px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
                display: 'flex', gap: 4, alignItems: 'center',
              }}>
                {[0, 1, 2].map(d => (
                  <div key={d} style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: `rgba(0,0,0,${typingDot(d).toFixed(2)})`,
                  }} />
                ))}
              </div>
              <div style={{ fontSize: 9, color: 'rgba(0,0,0,0.35)' }}>Claude</div>
            </div>
          )}

          {/* Claude 답변 (왼쪽, 흰색) */}
          <div style={{
            opacity: claudeOp,
            transform: `translateY(${claudeY}px)`,
            display: 'flex', alignItems: 'flex-start', gap: 6,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: '#6B48FF',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, flexShrink: 0, marginTop: 2,
            }}>C</div>
            <div>
              <div style={{ fontSize: 9, color: 'rgba(0,0,0,0.38)', marginBottom: 3 }}>Claude</div>
              <div style={{
                background: WHITE,
                borderRadius: '4px 14px 14px 14px',
                padding: '10px 12px',
                boxShadow: '0 2px 6px rgba(0,0,0,0.10)',
                maxWidth: '82%',
              }}>
                <div style={{
                  fontSize: 10.5, color: '#222', lineHeight: 1.9,
                  whiteSpace: 'pre-line',
                  transform: `scale(${numScale})`, transformOrigin: 'left top',
                }}>{CLAUDE_MSG}</div>
                <div style={{
                  marginTop: 6, paddingTop: 6,
                  borderTop: '1px solid rgba(0,0,0,0.07)',
                  fontSize: 10, color: '#6B48FF', fontWeight: 700,
                }}>⚡ 즉시 응답</div>
              </div>
            </div>
          </div>

        </div>

        {/* 입력창 */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: 48,
          background: '#F0EFE9',
          borderTop: '1px solid rgba(0,0,0,0.10)',
          display: 'flex', alignItems: 'center',
          paddingInline: 10, gap: 8,
        }}>
          <div style={{
            flex: 1, height: 30, borderRadius: 15,
            background: WHITE, border: '1px solid rgba(0,0,0,0.12)',
          }} />
          <div style={{
            width: 30, height: 30, borderRadius: '50%',
            background: KAKAO,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15,
          }}>↑</div>
        </div>
      </div>

      {/* ── 채널 배지 ─────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 36, left: 52,
        opacity: clamp(f, 20, 45),
        display: 'flex', flexDirection: 'column', gap: 4,
      }}>
        <div style={{
          background: KAKAO, color: KAKAO_D,
          fontSize: 12, fontWeight: 900, letterSpacing: 0.5,
          padding: '3px 11px', borderRadius: 6,
        }}>카카오 × 클로드</div>
        <div style={{ color: 'rgba(255,255,255,0.55)', fontSize: 11, fontWeight: 500 }}>
          STOCKBRAIN
        </div>
      </div>

      {/* ── 자막 바 ───────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, transparent 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {activeSub && (
          <div style={{
            fontSize: 40, fontWeight: 700, color: WHITE,
            textAlign: 'center', paddingInline: 80,
            textShadow: '0 2px 12px rgba(0,0,0,0.90)',
            lineHeight: 1.35,
          }}>
            {activeSub.text}
          </div>
        )}
      </div>

    </AbsoluteFill>
  );
};
