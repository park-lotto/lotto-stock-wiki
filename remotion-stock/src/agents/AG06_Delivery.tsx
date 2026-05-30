// AG06 — 씬4-5 배포 직원 (파일전송 파이프라인 시각화)
// 시스템 → 텔레그램 → 폰 도착 / 아침 07:00 타이밍
// 총 750프레임 (25초)
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

function ip(
  f: number,
  a: number,
  b: number,
  from = 0,
  to = 1,
  ease: (t: number) => number = Easing.out(Easing.cubic),
) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ease,
  });
}

// 파이프라인 노드
const NODES = [
  { id: 'collect', icon: '📡', label: '수집',   sub: '31건 처리 완료',      col: '#FFA502', x: 180  },
  { id: 'analyze', icon: '📊', label: '분석',   sub: '8개 기준 교차 완료',  col: C.main,    x: 480  },
  { id: 'pick',    icon: '🎯', label: '탑픽',   sub: '삼성전기 7/9점',      col: '#FF4757', x: 780  },
  { id: 'brief',   icon: '📋', label: '브리핑', sub: 'HTML 1장 생성 완료',  col: C.main,    x: 1080 },
  { id: 'send',    icon: '📨', label: '배포',   sub: '텔레그램 전송 중...',  col: C.main,    x: 1380 },
  { id: 'done',    icon: '✅', label: '완료',   sub: '07:00 전송 완료',     col: '#22c55e', x: 1680 },
];

const NODE_Y = 420;
const NODE_R = 72;  // 원 반지름

// 데이터 패킷 파티클
const PACKETS = Array.from({ length: 6 }).map((_, i) => ({
  delay:  i * 22,
  segIdx: Math.floor(i * 5 / 6),  // 어느 노드 구간에 있는지
}));

export const AG06_Delivery: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 20);
  const timeOp = ip(f, 10, 30);

  // ── 씬 전체 진행 (f20~700)
  // Phase1 (f20~300): 파이프라인 draw-on + 노드 순차 등장
  // Phase2 (f300~550): 패킷 흐름 + "전송 중" 강조
  // Phase3 (f560~720): 완료 클라이맥스

  // 노드 등장 프레임 (각 노드 50프레임 간격)
  const nodeFrame = (i: number) => 40 + i * 55;

  // ── 연결선 draw-on (노드-노드 사이) ──────────────────────────
  const segProg = (segIdx: number) => {
    const s = nodeFrame(segIdx) + 30;
    return ip(f, s, s + 45);
  };

  // ── 데이터 패킷 (공이 선을 타고 흐름, f300~) ─────────────────
  const PACKET_START = 300;
  const TRAVEL_SPEED = 88;  // 패킷이 노드 간 이동에 걸리는 프레임

  const getPacketPos = (pktIdx: number) => {
    const elapsed = f - PACKET_START - PACKETS[pktIdx].delay;
    if (elapsed < 0) return null;
    // 전체 5개 구간 이동 (NODES 6개 → 5구간)
    const totalFrames = TRAVEL_SPEED * 5;
    const t = Math.min(elapsed / totalFrames, 1);
    const segF    = t * 5;         // 현재 구간 (소수)
    const segIdx  = Math.min(Math.floor(segF), 4);
    const segT    = segF - segIdx; // 구간 내 위치 (0~1)
    const x1 = NODES[segIdx].x;
    const x2 = NODES[segIdx + 1].x;
    const px = x1 + (x2 - x1) * segT;
    const done = t >= 1;
    return { px, done, t };
  };

  // ── 완료 클라이맥스 (f560~640) ───────────────────────────────
  const doneOp    = ip(f, 560, 610);
  const doneScale = interpolate(f, [560, 610], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.7)),
  });
  const donePulse = doneOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.025 : 1;

  // 시계 클락 (f620~700)
  const clockOp = ip(f, 620, 660);
  const clockY  = interpolate(f, [620, 660], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 배포 직원 강조 (전송 구간 f380~540)
  const sendHighlight = ip(f, 380, 420) * (1 - ip(f, 520, 550));
  const sendGlowSize  = interpolate(sendHighlight, [0, 1], [0, 28]);

  // 배경 글로우
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.05;

  // 글로우
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [12, 36]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5), 0 0 ${gSz * 4}px rgba(0,191,154,0.25)`;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse at 50% 45%, rgba(0,255,208,1) 0%, transparent 65%)`,
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 4-5 · 배포 직원</div>

      {/* 좌상단 */}
      <div style={{ position: 'absolute', top: 30, left: 60, opacity: timeOp }}>
        <div style={{ color: '#4b5563', fontSize: 13, fontWeight: 600, letterSpacing: 5, marginBottom: 4 }}>DELIVERY AGENT</div>
        <div style={{
          color: C.main, fontSize: 72, fontWeight: 900,
          fontFamily: '"Consolas","Menlo",monospace',
          textShadow: GLOW.mid.text, letterSpacing: 3, lineHeight: 1,
        }}>SEND</div>
      </div>

      {/* ── 타이틀 텍스트 (f30~80) ── */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: 210,
        textAlign: 'center',
        opacity: ip(f, 30, 68),
        transform: `translateY(${interpolate(f, [30, 68], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })}px)`,
      }}>
        <div style={{ fontSize: 44, fontWeight: 700, color: '#e5e7eb' }}>
          마지막 직원이 <span style={{ color: C.main, textShadow: GLOW.weak.text }}>텔레그램으로 전송</span>합니다.
        </div>
      </div>

      {/* ── SVG 파이프라인 연결선 ── */}
      <svg style={{
        position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, pointerEvents: 'none',
      }}>
        {NODES.slice(0, -1).map((node, i) => {
          const next = NODES[i + 1];
          const prog = segProg(i);
          const x1   = node.x + NODE_R;
          const x2   = next.x - NODE_R;
          const cx   = x1 + (x2 - x1) * prog;
          return (
            <g key={i}>
              {/* 기본 선 (회색) */}
              <line x1={x1} y1={NODE_Y} x2={x2} y2={NODE_Y}
                stroke="rgba(255,255,255,0.06)" strokeWidth={3} />
              {/* 진행 선 (민트) */}
              <line x1={x1} y1={NODE_Y} x2={cx} y2={NODE_Y}
                stroke={`rgba(0,255,208,${0.5 * prog})`} strokeWidth={3}
                strokeDasharray="16 8"
              />
            </g>
          );
        })}
      </svg>

      {/* ── 데이터 패킷 공 ── */}
      <svg style={{
        position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, pointerEvents: 'none',
      }}>
        {PACKETS.map((pkt, i) => {
          const pos = getPacketPos(i);
          if (!pos || pos.t <= 0) return null;
          const glowAlpha = pos.done ? 0 : 0.8;
          return (
            <g key={i}>
              <circle
                cx={pos.px} cy={NODE_Y} r={pos.done ? 0 : 10}
                fill={C.main}
                opacity={glowAlpha}
              />
              {!pos.done && (
                <circle
                  cx={pos.px} cy={NODE_Y} r={18}
                  fill="none"
                  stroke={C.main}
                  strokeWidth={2}
                  opacity={glowAlpha * 0.4}
                />
              )}
            </g>
          );
        })}
      </svg>

      {/* ── 노드 원 + 라벨 ── */}
      {NODES.map((node, i) => {
        const nf       = nodeFrame(i);
        const nodeOp   = ip(f, nf, nf + 28);
        const nodeScale = interpolate(f, [nf, nf + 28], [0.3, 1], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.out(Easing.elastic(1.0)),
        });
        const isSend = node.id === 'send';
        const isDone = node.id === 'done';

        return (
          <div key={node.id} style={{
            position: 'absolute',
            left: node.x - NODE_R, top: NODE_Y - NODE_R,
            width: NODE_R * 2, height: NODE_R * 2,
            opacity: nodeOp,
            transform: `scale(${nodeScale})`,
            transformOrigin: 'center',
          }}>
            {/* 원 */}
            <div style={{
              width: '100%', height: '100%',
              borderRadius: '50%',
              background: isDone
                ? 'rgba(34,197,94,0.12)'
                : isSend
                ? `rgba(0,255,208,${0.08 + sendHighlight * 0.12})`
                : `${node.col}12`,
              border: `2px solid ${node.col}${isDone ? '80' : '45'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 38,
              boxShadow: (isSend && sendGlowSize > 0)
                ? `0 0 ${sendGlowSize}px rgba(0,255,208,0.6)`
                : isDone
                ? '0 0 18px rgba(34,197,94,0.5)'
                : undefined,
            }}>{node.icon}</div>

            {/* 라벨 위 */}
            <div style={{
              position: 'absolute', top: -48, left: '50%',
              transform: 'translateX(-50%)',
              textAlign: 'center', whiteSpace: 'nowrap',
              color: node.col, fontSize: 20, fontWeight: 800, letterSpacing: 2,
              textShadow: (isSend && sendHighlight > 0.3) ? GLOW.weak.text : undefined,
            }}>{node.label}</div>

            {/* 서브 라벨 아래 */}
            <div style={{
              position: 'absolute', top: NODE_R * 2 + 14, left: '50%',
              transform: 'translateX(-50%)',
              textAlign: 'center', whiteSpace: 'nowrap',
              color: isSend && sendHighlight > 0.3 ? C.main : '#4b5563',
              fontSize: 16, fontWeight: 600,
            }}>{node.sub}</div>
          </div>
        );
      })}

      {/* ── 완료 클라이맥스 ── */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 180,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', gap: 20,
        opacity: doneOp,
        transform: `scale(${doneScale * donePulse})`,
        transformOrigin: 'center bottom',
      }}>
        <div style={{
          fontSize: 72, fontWeight: 900,
          color: C.main, textShadow: dynGlow,
        }}>전송 완료</div>
        <div style={{ fontSize: 32, color: '#6b7280', fontWeight: 500 }}>
          제가 자고 있는 시간에 이미 폰에 와있어요.
        </div>
      </div>

      {/* ── 시계 07:00 ── */}
      <div style={{
        position: 'absolute', right: 80, bottom: 100,
        opacity: clockOp,
        transform: `translateY(${clockY}px)`,
        textAlign: 'right',
      }}>
        <div style={{ color: '#4b5563', fontSize: 14, fontWeight: 700, letterSpacing: 5, marginBottom: 6 }}>
          DELIVERED AT
        </div>
        <div style={{
          color: '#22c55e', fontSize: 88, fontWeight: 900, lineHeight: 1,
          fontFamily: '"Consolas","Menlo",monospace',
          textShadow: '0 0 24px rgba(34,197,94,0.6)',
        }}>07:00</div>
      </div>

      {/* 하단 */}
      <div style={{
        position: 'absolute', bottom: 18, left: 0, right: 0,
        textAlign: 'center', opacity: timeOp,
      }}>
        <div style={{ color: '#374151', fontSize: 18, fontWeight: 600, letterSpacing: 4 }}>
          SCENE 4-5 · 배포 직원 · 파이프라인 시각화
        </div>
      </div>

    </AbsoluteFill>
  );
};
