// B2 — 05:00 Claude가 텔레 메시지를 분석
// 실제 Claude(또는 ChatGPT-스타일) 채팅 UI 재현
// 유저 메시지(텔레 캡처) → AI가 타이핑하며 분류·요약·점수화
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 360;

// Claude 다크 모드 컬러
const CL = {
  bg:       '#1B1B1B',     // 본체 배경 (Claude 다크)
  side:     '#1A1916',     // 사이드바 (Claude의 따뜻한 회색)
  card:     '#252420',     // 카드/입력박스
  text:     '#F5F4ED',     // 본문 (Claude 워시드 화이트)
  textSub:  '#8C8C7E',
  accent:   '#D97757',     // Claude 오렌지
  border:   '#2F2E2A',
  userBg:   '#2A2926',     // 유저 메시지
  codeBg:   '#13110F',
};

// AI 답변 텍스트 — 한 글자씩 타이핑
const AI_RESPONSE = `📊 **분류 완료**

• 섹터: 반도체 (HBM)
• 종목: SK하이닉스 (000660)
• 신호 강도: 🔴 강력

📈 **교차 분석**

1. 수출 데이터 — HBM YoY +247% (4월 잠정)
2. 컨센서스 — TP 평균 280만원 (지난주 245만)
3. 수급 — 외국인 4일 연속 매수
4. 미국 커플 — NVDA 어제 +1.9%

💡 **판단**

수출·리포트·수급·미국커플 모두 ✅ → 위키 SK하이닉스에 누적, 탑픽 점수 +2.`;

export const B2_Claude = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 18], [0, 1], { extrapolateRight: 'clamp' });
  const prog = interpolate(f, [15, DUR - 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 좌상단 시간
  const timeOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // 유저 메시지 (텔레 캡처 인용) — 일찍 등장
  const userOp = interpolate(prog, [0.05, 0.15], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const userY = interpolate(prog, [0.05, 0.15], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 타이핑 인디케이터 (점점점) — 잠깐
  const typingOn = prog > 0.18 && prog < 0.30;
  const typingDot = (i: number) => {
    const phase = (f * 0.12 + i * 0.5) % 2;
    return phase < 1 ? phase : 2 - phase;
  };

  // AI 답변 한 글자씩 — 0.30~0.80 구간
  const typeProg = interpolate(prog, [0.30, 0.80], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const visibleLen = Math.floor(typeProg * AI_RESPONSE.length);
  const visibleText = AI_RESPONSE.substring(0, visibleLen);

  // 우측 가이드 자막
  const guideOp = interpolate(prog, [0.40, 0.50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 마크다운 간단 렌더 (•/숫자/볼드/하이라이트만)
  const renderLine = (line: string, key: number) => {
    if (line.startsWith('📊') || line.startsWith('📈') || line.startsWith('💡')) {
      // 헤더
      const parts = line.split('**');
      return (
        <div key={key} style={{
          color: CL.text, fontSize: 22, fontWeight: 700,
          marginTop: 16, marginBottom: 4,
        }}>
          {parts.map((p, i) => i % 2 === 1
            ? <span key={i} style={{ color: CL.accent }}>{p}</span>
            : p)}
        </div>
      );
    }
    if (line.startsWith('•')) {
      return (
        <div key={key} style={{ color: CL.text, fontSize: 20, lineHeight: 1.7, paddingLeft: 8 }}>
          {line}
        </div>
      );
    }
    if (/^\d\./.test(line)) {
      return (
        <div key={key} style={{ color: CL.text, fontSize: 20, lineHeight: 1.7, paddingLeft: 8 }}>
          {line}
        </div>
      );
    }
    if (line.trim() === '') return <div key={key} style={{ height: 8 }} />;
    // 일반 + 볼드 처리
    const parts = line.split('**');
    return (
      <div key={key} style={{ color: CL.text, fontSize: 20, lineHeight: 1.6 }}>
        {parts.map((p, i) => i % 2 === 1
          ? <b key={i} style={{ color: CL.text }}>{p}</b>
          : p)}
      </div>
    );
  };

  return (
    <AbsoluteFill style={{ background: '#000000', opacity: fadeIn, fontFamily: FONT }}>

      {/* 우상단 샘플 라벨 */}
      <div style={{
        position: 'absolute', top: 30, right: 50,
        color: C.textSub, fontSize: 18, fontWeight: 600, letterSpacing: 3,
        opacity: timeOp, zIndex: 100,
      }}>SAMPLE B2 · 05:00 CLAUDE</div>

      {/* 좌상단 시간 */}
      <div style={{
        position: 'absolute', top: 40, left: 60,
        opacity: timeOp, zIndex: 100,
      }}>
        <div style={{ color: C.textSub, fontSize: 16, fontWeight: 500, letterSpacing: 4, marginBottom: 4 }}>NOW</div>
        <div style={{
          color: C.main, fontSize: 72, fontWeight: 900,
          fontFamily: '"Consolas", "Menlo", monospace',
          textShadow: GLOW.mid.text, letterSpacing: 2, lineHeight: 1,
        }}>05:00</div>
      </div>

      {/* === Claude 앱 본체 === */}
      <div style={{
        position: 'absolute', left: 380, top: 80, width: 1200, height: 900,
        background: CL.bg, borderRadius: 12, overflow: 'hidden',
        boxShadow: '0 30px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.05)',
        display: 'flex',
      }}>

        {/* 사이드바 */}
        <div style={{
          width: 240, background: CL.side, padding: '20px 14px',
          display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 18,
            borderBottom: `1px solid ${CL.border}`, marginBottom: 12,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6,
              background: CL.accent,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontWeight: 900, fontSize: 16,
            }}>✦</div>
            <div style={{ color: CL.text, fontSize: 16, fontWeight: 700 }}>Claude</div>
          </div>
          <div style={{
            padding: '10px 12px', borderRadius: 8,
            background: 'rgba(217, 119, 87, 0.12)',
            color: CL.text, fontSize: 13, fontWeight: 600,
          }}>+ New chat</div>
          <div style={{ color: CL.textSub, fontSize: 11, fontWeight: 700, letterSpacing: 2, marginTop: 16, paddingInline: 12 }}>
            오늘 · TODAY
          </div>
          {[
            '04:12 텔레 분류',
            '03:58 시황 요약',
            '03:45 조선 신규수주',
          ].map((c, i) => (
            <div key={i} style={{
              padding: '8px 12px', borderRadius: 6,
              color: i === 0 ? CL.text : CL.textSub,
              fontSize: 13,
              background: i === 0 ? 'rgba(255,255,255,0.04)' : 'transparent',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>{c}</div>
          ))}
        </div>

        {/* 대화 영역 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {/* 상단 모델 표시 */}
          <div style={{
            padding: '16px 28px',
            borderBottom: `1px solid ${CL.border}`,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <div style={{ color: CL.text, fontSize: 15, fontWeight: 700 }}>Claude</div>
            <div style={{
              color: CL.textSub, fontSize: 12, padding: '3px 8px',
              border: `1px solid ${CL.border}`, borderRadius: 6,
            }}>Opus 4.7</div>
          </div>

          {/* 메시지 영역 */}
          <div style={{
            flex: 1, padding: '24px 40px', overflow: 'hidden',
            display: 'flex', flexDirection: 'column', gap: 20,
          }}>
            {/* 유저 메시지 (텔레 캡처 인용) */}
            <div style={{
              alignSelf: 'flex-end', maxWidth: '75%',
              background: CL.userBg, borderRadius: 14,
              padding: '14px 18px',
              opacity: userOp, transform: `translateY(${userY}px)`,
            }}>
              <div style={{ color: CL.textSub, fontSize: 12, fontWeight: 700, marginBottom: 6, letterSpacing: 2 }}>
                FROM 반도체 인사이트 · 04:12
              </div>
              <div style={{ color: CL.text, fontSize: 16, lineHeight: 1.5 }}>
                업계 채널 정보 — SK하이닉스 HBM4 베이스다이<br />
                NVIDIA Vera Rubin 독점 공급 95% 확실시. 양산 6월 말 확정.
              </div>
              <div style={{ color: CL.textSub, fontSize: 12, marginTop: 8 }}>
                → 이 메시지 분류·교차분석해서 위키 어디에 넣을지 판단해줘
              </div>
            </div>

            {/* AI 응답 */}
            <div style={{ alignSelf: 'flex-start', maxWidth: '85%', display: 'flex', gap: 12 }}>
              {/* AI 아바타 */}
              <div style={{
                width: 30, height: 30, borderRadius: 8,
                background: CL.accent, flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#fff', fontWeight: 900, fontSize: 14,
              }}>✦</div>

              <div style={{ flex: 1 }}>
                {/* 타이핑 인디케이터 */}
                {typingOn && (
                  <div style={{ display: 'flex', gap: 6, padding: '8px 0' }}>
                    {[0, 1, 2].map(i => (
                      <div key={i} style={{
                        width: 8, height: 8, borderRadius: '50%',
                        background: CL.textSub,
                        opacity: 0.4 + typingDot(i) * 0.6,
                        transform: `translateY(${-typingDot(i) * 4}px)`,
                      }} />
                    ))}
                  </div>
                )}

                {/* 응답 본문 (타이핑) */}
                {!typingOn && visibleText.split('\n').map((line, i) => renderLine(line, i))}

                {/* 타이핑 커서 */}
                {typeProg > 0 && typeProg < 1 && (
                  <span style={{
                    display: 'inline-block', width: 2, height: 22,
                    background: CL.text, marginLeft: 4,
                    opacity: f % 30 < 15 ? 1 : 0,
                  }} />
                )}
              </div>
            </div>
          </div>

          {/* 입력바 (꺼진 상태) */}
          <div style={{ padding: 20, borderTop: `1px solid ${CL.border}` }}>
            <div style={{
              background: CL.card, borderRadius: 14, padding: '14px 18px',
              border: `1px solid ${CL.border}`,
              color: CL.textSub, fontSize: 14,
            }}>Reply to Claude...</div>
          </div>
        </div>
      </div>

      {/* 우측 가이드 자막 */}
      <div style={{
        position: 'absolute', left: 1620, top: 280, width: 280,
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
          Claude가 메시지를<br />
          섹터·종목·신호로<br />
          자동 분류
        </div>
        <div style={{ color: C.textSub, fontSize: 18, fontWeight: 500, lineHeight: 1.6 }}>
          위키 어디에 누적할지<br />
          판단까지 한 번에
        </div>

        {/* 처리 통계 */}
        <div style={{ marginTop: 32 }}>
          <div style={{
            color: C.textSub, fontSize: 14, fontWeight: 600, letterSpacing: 3, marginBottom: 6,
          }}>오늘 새벽 분류</div>
          <div style={{
            color: C.main, fontSize: 64, fontWeight: 900,
            textShadow: GLOW.mid.text, lineHeight: 1,
            fontFamily: '"Consolas", "Menlo", monospace',
          }}>312<span style={{ fontSize: 28, color: C.textSub, fontWeight: 600 }}> / 312</span></div>
          <div style={{ color: C.textSub, fontSize: 16, marginTop: 4 }}>
            놓친 거 0건
          </div>
        </div>
      </div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 30, left: 0, right: 0,
        textAlign: 'center', opacity: timeOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 28, fontWeight: 700, opacity: 0.7 }}>
          STAGE 2 · 분류
        </div>
      </div>

    </AbsoluteFill>
  );
};
