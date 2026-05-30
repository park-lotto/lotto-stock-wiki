// AG_S07 — 씬7 여운 (930프레임 / 31초)
// ※ 녹음 후 Whisper 싱크로 타이밍 조정 필요
// [01] f0000~0060  "이 시스템."
// [02] f0070~0180  "어떻게 설계됐는지 궁금하시죠?"
// [03] f0200~0330  "총괄이 직원들한테 어떻게 지시를 내리는지"
// [04] f0350~0470  "직원들이 서로 어떻게 정보를 넘기는지"
// [05] f0490~0570  "실제 설계 구조"
// [06] f0580~0730  "다음 영상에서 전부 보여드리겠습니다"

import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

function ip(
  f: number, a: number, b: number,
  from = 0, to = 1,
  ease: (t: number) => number = Easing.out(Easing.cubic),
) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease,
  });
}

const SUBS = [
  { s: 0,   e: 60,  text: '이 시스템.' },
  { s: 70,  e: 180, text: '어떻게 설계됐는지 궁금하시죠?' },
  { s: 200, e: 330, text: '총괄이 직원들한테 어떻게 지시를 내리는지.' },
  { s: 350, e: 470, text: '직원들이 서로 어떻게 정보를 넘기는지.' },
  { s: 490, e: 570, text: '실제 설계 구조.' },
  { s: 580, e: 730, text: '다음 영상에서 전부 보여드리겠습니다.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// 다이어그램 노드 위치 (총괄 + 직원 5개 표시)
const NODES = [
  { x: 960, y: 200, label: '총괄', icon: '🧠', col: C.main, size: 80 },
  { x: 540, y: 420, label: '수집',   icon: '📡', col: '#FFA502', size: 56 },
  { x: 760, y: 440, label: '수급',   icon: '🔍', col: C.main,   size: 56 },
  { x: 960, y: 480, label: '탑픽',   icon: '🎯', col: '#FF4757', size: 56 },
  { x: 1160, y: 440, label: '브리핑', icon: '📋', col: C.main,   size: 56 },
  { x: 1380, y: 420, label: '배포',  icon: '📨', col: C.main,   size: 56 },
];

// 연결선 (총괄 → 각 직원)
const EDGES = NODES.slice(1).map((n, i) => ({ x1: 960, y1: 200, x2: n.x, y2: n.y, i }));

// 떠다니는 질문 텍스트들
const QUESTIONS = [
  { text: '어떻게 지시하지?',    x: 300,  y: 320, startF: 90  },
  { text: '데이터는 어디서?',    x: 1200, y: 270, startF: 170 },
  { text: '결과를 어떻게 넘겨?', x: 680,  y: 620, startF: 250 },
  { text: '스케줄은 누가?',      x: 1300, y: 580, startF: 350 },
];

export const AG_S07_Tease: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 18);
  const timeOp = ip(f, 10, 28);
  const sub    = getSub(f);

  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse  = Math.sin(f * 0.06) * 0.5 + 0.5;
  const gSz    = interpolate(pulse, [0, 1], [10, 28]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // 전체 다이어그램 블러 — f0~490: 흐림 / f490~600: 점점 선명 / f600~: 다시 흐림(사라짐)
  const blurAmt = interpolate(
    f, [0, 10, 490, 580, 730, 800],
    [24, 22, 12, 16, 20, 28],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  const diagramOp = ip(f, 10, 50, 0.3, 0.65);

  // 노드 등장 (순차 — f30~200)
  const nodeStart = [30, 50, 70, 90, 110, 130];

  // 연결선 draw-on (f60~160)
  const lineProgress = ip(f, 60, 160, 0, 1, Easing.inOut(Easing.cubic));

  // 질문 텍스트 부유
  const questionFloat = (i: number) => Math.sin(f * 0.05 + i * 1.2) * 10;

  // "실제 설계 구조" 등장 (f490~)
  const designOp    = ip(f, 490, 550);
  const designScale = interpolate(f, [490, 550], [0.4, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.8)),
  });

  // "다음 영상에서" 큰 텍스트 등장 (f580~)
  const nextOp = ip(f, 580, 640);
  const nextTy = interpolate(f, [580, 640], [40, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // "실제 설계 공개" 클라이맥스 (f680~)
  const revealOp    = ip(f, 680, 740);
  const revealScale = interpolate(f, [680, 740], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.75)),
  });
  const revealPulse = revealOp > 0.95 ? 1 + Math.sin(f * 0.1) * 0.025 : 1;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s07.m4a')} volume={1} />

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 40%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 7 · 여운</div>

      {/* 블러 처리된 다이어그램 */}
      <div style={{
        position: 'absolute', inset: 0,
        opacity: diagramOp,
        filter: `blur(${blurAmt}px)`,
        pointerEvents: 'none',
      }}>
        {/* SVG 연결선 */}
        <svg style={{ position: 'absolute', inset: 0, width: 1920, height: 1080 }}>
          {EDGES.map((e) => {
            const r = Math.min(1, lineProgress);
            return (
              <line key={e.i}
                x1={e.x1} y1={e.y1}
                x2={e.x1 + (e.x2 - e.x1) * r}
                y2={e.y1 + (e.y2 - e.y1) * r}
                stroke={`${C.main}40`}
                strokeWidth={2}
                strokeDasharray="12 8"
              />
            );
          })}
          {/* 총괄에서 방사형 글로우 링 */}
          <circle
            cx={960} cy={200}
            r={60 + Math.sin(f * 0.07) * 15}
            fill="none"
            stroke={`${C.main}20`}
            strokeWidth={2}
          />
        </svg>

        {/* 노드들 */}
        {NODES.map((n, i) => {
          const nOp = ip(f, nodeStart[i], nodeStart[i] + 30);
          return (
            <div key={i} style={{
              position: 'absolute',
              left: n.x - n.size / 2,
              top: n.y - n.size / 2,
              width: n.size, height: n.size,
              opacity: nOp,
            }}>
              <div style={{
                width: '100%', height: '100%', borderRadius: '50%',
                background: `${n.col}18`,
                border: `2px solid ${n.col}55`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column',
                boxShadow: `0 0 ${12 + Math.sin(f * 0.08 + i) * 6}px ${n.col}44`,
              }}>
                <span style={{ fontSize: n.size * 0.36 }}>{n.icon}</span>
                <div style={{ color: n.col, fontSize: n.size * 0.18, fontWeight: 700, letterSpacing: 1 }}>
                  {n.label}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 부유하는 질문 텍스트들 */}
      {QUESTIONS.map((q, i) => {
        const qOp = ip(f, q.startF, q.startF + 40) * (1 - ip(f, 490, 550));
        return (
          <div key={i} style={{
            position: 'absolute',
            left: q.x, top: q.y + questionFloat(i),
            opacity: qOp * 0.7,
            color: '#4b5563', fontSize: 22, fontWeight: 600,
            background: 'rgba(8,12,20,0.6)',
            padding: '6px 18px', borderRadius: 20,
            border: '1px solid rgba(255,255,255,0.06)',
            transform: 'translateX(-50%)',
            whiteSpace: 'nowrap',
          }}>{q.text}</div>
        );
      })}

      {/* "실제 설계 구조" 등장 */}
      {designOp > 0.01 && (
        <div style={{
          position: 'absolute', top: '36%', left: 0, right: 0,
          textAlign: 'center',
          opacity: designOp,
          transform: `scale(${designScale})`,
        }}>
          <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8, marginBottom: 12 }}>
            COMING NEXT
          </div>
          <div style={{ fontSize: 56, fontWeight: 900, color: '#e5e7eb' }}>
            실제 설계 구조.
          </div>
        </div>
      )}

      {/* "다음 영상에서 전부 보여드리겠습니다" */}
      {nextOp > 0.01 && (
        <div style={{
          position: 'absolute', top: '54%', left: 0, right: 0,
          textAlign: 'center',
          opacity: nextOp,
          transform: `translateY(${nextTy}px)`,
        }}>
          <div style={{
            fontSize: 36, fontWeight: 700, color: '#9ca3af',
          }}>다음 영상에서 전부 보여드리겠습니다.</div>
        </div>
      )}

      {/* "실제 설계 공개" 클라이맥스 뱃지 */}
      {revealOp > 0.01 && (
        <div style={{
          position: 'absolute', bottom: 160, left: 0, right: 0,
          textAlign: 'center',
          opacity: revealOp,
          transform: `scale(${revealScale * revealPulse})`,
        }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 20,
            padding: '14px 48px',
            background: `${C.main}0d`,
            border: `1.5px solid ${C.main}38`,
            borderRadius: 36,
          }}>
            <span style={{ fontSize: 36 }}>🔓</span>
            <div style={{
              color: C.main, fontSize: 32, fontWeight: 900,
              textShadow: dynGlow, letterSpacing: 2,
            }}>다음 편 : 실제 설계 공개</div>
            <span style={{ fontSize: 36 }}>→</span>
          </div>
        </div>
      )}

      {/* 자막바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        paddingInline: 80,
        background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)',
      }}>
        {sub && (
          <div style={{
            color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center',
            opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)',
          }}>{sub.text}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};
