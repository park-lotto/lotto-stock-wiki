// B1 — 04:12 텔레방 수집
// 실제 텔레그램 다크 모드 UI를 그대로 재현
// 30개 채널 중 하나에서 의미있는 메시지가 도착하는 순간
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 360; // 12초

// 실제 텔레그램 다크 모드 컬러
const TG = {
  bg:        '#0E1621',  // 메인 배경
  panel:     '#17212B',  // 패널
  side:      '#0F1A24',  // 사이드바
  bubbleOut: '#2B5278',  // 보낸 메시지 (파랑)
  bubbleIn:  '#182533',  // 받은 메시지 (어두운 청회색)
  text:      '#FFFFFF',
  textSub:   '#7F92A1',
  accent:    '#5288C1',  // 텔레그램 블루
  unread:    '#5288C1',
};

// 좌측 채널 목록
const CHANNELS = [
  { name: '주식정보채널 ⓜ',     last: '오늘 시황 정리...',       time: '03:58', unread: 3,  active: false },
  { name: '반도체 인사이트 ⓟ',  last: 'SK하이닉스 HBM4...',     time: '04:12', unread: 1,  active: true },  // 클라이맥스 메시지
  { name: '조선 데일리 ⓟ',      last: '한화오션 신규수주...',    time: '03:45', unread: 7,  active: false },
  { name: '글로벌 시황',         last: 'Nasdaq +0.8%',           time: '03:32', unread: 12, active: false },
  { name: '방산 정책',           last: 'KAI 인도 수출...',       time: '02:51', unread: 2,  active: false },
  { name: '바이오 클럽',         last: 'HLB FDA 임박',           time: '02:14', unread: 5,  active: false },
  { name: '뉴스속보 ⓜ',         last: '연준 6월 동결',          time: '01:48', unread: 23, active: false },
  { name: '리포트 모음',         last: 'NH 반도체 TP↑',         time: '01:12', unread: 8,  active: false },
];

export const B1_Telegram = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 18], [0, 1], { extrapolateRight: 'clamp' });
  const prog = interpolate(f, [15, DUR - 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 메시지 등장 타이밍 (앱 시계가 04:12 가리킬 때)
  const msgOp = interpolate(prog, [0.20, 0.30], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const msgY = interpolate(prog, [0.20, 0.30], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 채널 목록 두번째 항목(반도체 인사이트) 강조 펄스
  const activePulse = Math.sin(f * 0.08) * 0.5 + 0.5;

  // 우측 가이드 자막 (어느 정보인지 설명)
  const guideOp = interpolate(prog, [0.45, 0.55], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 시각 자막 (좌상단 모서리)
  const timeOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // 30개 채널 카운터
  const counterOp = interpolate(prog, [0.60, 0.72], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: '#000000', opacity: fadeIn, fontFamily: FONT }}>

      {/* 우상단 샘플 라벨 */}
      <div style={{
        position: 'absolute', top: 30, right: 50,
        color: C.textSub, fontSize: 18, fontWeight: 600, letterSpacing: 3,
        opacity: timeOp, zIndex: 100,
      }}>SAMPLE B1 · 04:12 TELEGRAM</div>

      {/* 좌상단 시간 디스플레이 */}
      <div style={{
        position: 'absolute', top: 40, left: 60,
        opacity: timeOp, zIndex: 100,
      }}>
        <div style={{ color: C.textSub, fontSize: 16, fontWeight: 500, letterSpacing: 4, marginBottom: 4 }}>NOW</div>
        <div style={{
          color: C.main, fontSize: 72, fontWeight: 900,
          fontFamily: '"Consolas", "Menlo", monospace',
          textShadow: GLOW.mid.text, letterSpacing: 2, lineHeight: 1,
        }}>04:12</div>
      </div>

      {/* === 텔레그램 앱 본체 (브라우저 윈도우 안에 들어있는 느낌) === */}
      <div style={{
        position: 'absolute',
        left: 380, top: 80, width: 1200, height: 900,
        background: TG.bg,
        borderRadius: 12,
        overflow: 'hidden',
        boxShadow: '0 30px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.05)',
        display: 'flex',
      }}>

        {/* 좌측 채널 리스트 */}
        <div style={{
          width: 380, background: TG.side,
          borderRight: `1px solid rgba(255,255,255,0.05)`,
          display: 'flex', flexDirection: 'column',
        }}>
          {/* 검색바 */}
          <div style={{
            padding: '14px 16px', borderBottom: `1px solid rgba(255,255,255,0.04)`,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              background: TG.accent,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontSize: 16, fontWeight: 800,
            }}>📱</div>
            <div style={{
              flex: 1, height: 36, background: TG.panel, borderRadius: 18,
              display: 'flex', alignItems: 'center', paddingInline: 14,
              color: TG.textSub, fontSize: 14,
            }}>🔍  Search</div>
          </div>

          {/* 채널 목록 */}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            {CHANNELS.map((ch, i) => {
              const highlight = ch.active ? 0.5 + activePulse * 0.5 : 0;
              return (
                <div key={i} style={{
                  padding: '12px 14px',
                  display: 'flex', gap: 12, alignItems: 'center',
                  background: ch.active ? `rgba(82, 136, 193, ${0.15 + highlight * 0.1})` : 'transparent',
                  borderLeft: ch.active ? `3px solid ${TG.accent}` : '3px solid transparent',
                  cursor: 'pointer',
                }}>
                  <div style={{
                    width: 44, height: 44, borderRadius: '50%',
                    background: `hsl(${i * 47}, 50%, 45%)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#fff', fontSize: 18, fontWeight: 800,
                    flexShrink: 0,
                  }}>{ch.name.charAt(0)}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      display: 'flex', justifyContent: 'space-between', marginBottom: 4,
                    }}>
                      <div style={{
                        color: TG.text, fontSize: 14, fontWeight: 600,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>{ch.name}</div>
                      <div style={{ color: TG.textSub, fontSize: 11, flexShrink: 0, marginLeft: 8 }}>{ch.time}</div>
                    </div>
                    <div style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    }}>
                      <div style={{
                        color: TG.textSub, fontSize: 13,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>{ch.last}</div>
                      {ch.unread > 0 && (
                        <div style={{
                          background: ch.active ? TG.accent : '#5C6B7A',
                          color: '#fff', fontSize: 11, fontWeight: 800,
                          padding: '2px 7px', borderRadius: 10,
                          minWidth: 18, textAlign: 'center', flexShrink: 0, marginLeft: 8,
                          boxShadow: ch.active && highlight > 0.5 ? `0 0 8px ${TG.accent}` : undefined,
                        }}>{ch.unread}</div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 우측 대화 영역 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: TG.bg }}>
          {/* 헤더 */}
          <div style={{
            padding: '14px 24px',
            borderBottom: `1px solid rgba(255,255,255,0.05)`,
            display: 'flex', alignItems: 'center', gap: 14,
          }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%',
              background: `hsl(${1 * 47}, 50%, 45%)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontSize: 18, fontWeight: 800,
            }}>반</div>
            <div style={{ flex: 1 }}>
              <div style={{ color: TG.text, fontSize: 17, fontWeight: 700 }}>반도체 인사이트 ⓟ</div>
              <div style={{ color: TG.textSub, fontSize: 13 }}>구독자 12,847명</div>
            </div>
            <div style={{ color: TG.textSub, fontSize: 18 }}>⋮</div>
          </div>

          {/* 메시지 영역 */}
          <div style={{
            flex: 1, padding: '20px 60px',
            display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 12,
            opacity: msgOp, transform: `translateY(${msgY}px)`,
          }}>
            {/* 이전 메시지 (어둡게) */}
            <div style={{
              background: TG.bubbleIn, borderRadius: 12, padding: '10px 14px',
              maxWidth: '78%', opacity: 0.5,
            }}>
              <div style={{ color: TG.text, fontSize: 15, lineHeight: 1.5 }}>
                오늘도 좋은 하루 시작합니다 ☕
              </div>
              <div style={{ color: TG.textSub, fontSize: 11, marginTop: 4, textAlign: 'right' }}>03:58</div>
            </div>

            {/* 핵심 메시지 (큰 글로우) */}
            <div style={{
              background: TG.bubbleIn,
              borderRadius: 12, padding: '14px 18px',
              maxWidth: '85%',
              borderLeft: `3px solid ${C.main}`,
              boxShadow: `0 0 ${20 + activePulse * 20}px rgba(0,255,208,${0.2 + activePulse * 0.3})`,
            }}>
              <div style={{ color: TG.accent, fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                #SK하이닉스 #HBM4
              </div>
              <div style={{ color: TG.text, fontSize: 17, lineHeight: 1.55, fontWeight: 500 }}>
                업계 채널 정보 — <b>SK하이닉스 HBM4 베이스다이</b><br />
                NVIDIA Vera Rubin 독점 공급 <b style={{ color: C.main }}>95% 확실시</b>.<br />
                내부 양산 일정 6월 말 확정.
              </div>
              <div style={{
                color: TG.textSub, fontSize: 11, marginTop: 8,
                display: 'flex', justifyContent: 'space-between',
              }}>
                <span>👁 1.2K · 🔁 87</span>
                <span style={{ color: C.main, fontWeight: 700 }}>04:12 ✓✓</span>
              </div>
            </div>
          </div>

          {/* 입력바 (회색) */}
          <div style={{
            padding: 14, borderTop: `1px solid rgba(255,255,255,0.05)`,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <div style={{
              flex: 1, height: 40, background: TG.panel, borderRadius: 20,
              display: 'flex', alignItems: 'center', paddingInline: 16,
              color: TG.textSub, fontSize: 14,
            }}>Message</div>
            <div style={{ color: TG.textSub, fontSize: 20 }}>🎤</div>
          </div>
        </div>
      </div>

      {/* 우측 가이드 자막 */}
      <div style={{
        position: 'absolute',
        left: 1620, top: 280, width: 280,
        opacity: guideOp,
      }}>
        <div style={{
          color: C.main, fontSize: 22, fontWeight: 800, letterSpacing: 3,
          marginBottom: 12, textShadow: GLOW.weak.text,
        }}>지금 일어나는 일</div>
        <div style={{
          color: C.textPrimary, fontSize: 26, fontWeight: 700,
          lineHeight: 1.5, marginBottom: 18,
        }}>
          텔레방 30개에서<br />
          이 메시지가 도착했어요
        </div>
        <div style={{ color: C.textSub, fontSize: 18, fontWeight: 500, lineHeight: 1.6 }}>
          크롤러가 자동으로<br />
          가져와 다음 단계로 넘김
        </div>

        {/* 30개 채널 카운터 */}
        <div style={{
          marginTop: 32,
          opacity: counterOp,
        }}>
          <div style={{
            color: C.textSub, fontSize: 14, fontWeight: 600, letterSpacing: 3, marginBottom: 6,
          }}>구독 채널</div>
          <div style={{
            color: C.main, fontSize: 64, fontWeight: 900,
            textShadow: GLOW.mid.text, lineHeight: 1,
            fontFamily: '"Consolas", "Menlo", monospace',
          }}>30</div>
          <div style={{ color: C.textSub, fontSize: 16, marginTop: 4 }}>
            오늘 새벽 수집 312건
          </div>
        </div>
      </div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 30, left: 0, right: 0,
        textAlign: 'center', opacity: timeOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 28, fontWeight: 700, opacity: 0.7 }}>
          STAGE 1 · 수집
        </div>
      </div>

    </AbsoluteFill>
  );
};
