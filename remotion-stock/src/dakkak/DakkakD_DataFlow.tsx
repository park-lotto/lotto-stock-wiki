// Sample D — 데이터 1인칭
// 카메라가 정보 입자가 되어 여행
// 텔레방 메시지 → 크롤러 파이프 → Claude 처리 → 위키 노드 → 대시보드 카드
// "정보 자체"가 영상의 주인공
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 240;

// 5개 스테이지
const STAGES = [
  { at: 0.00, name: 'TELEGRAM',   label: '텔레그램 메시지가 도착' },
  { at: 0.20, name: 'CRAWLER',    label: '크롤러가 수집' },
  { at: 0.40, name: 'CLAUDE',     label: 'Claude가 분류 · 분석' },
  { at: 0.60, name: 'WIKI',       label: '위키에 노드로 저장' },
  { at: 0.78, name: 'DASHBOARD',  label: '아침 대시보드 카드' },
];

export const DakkakD_DataFlow = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const prog = interpolate(f, [10, DUR - 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const labelOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.05) * 0.03 + 0.05;

  // 현재 스테이지
  const stageIdx = (() => {
    for (let i = STAGES.length - 1; i >= 0; i--) {
      if (prog >= STAGES[i].at) return i;
    }
    return 0;
  })();
  const stage = STAGES[stageIdx];

  // ── Stage 0: Telegram bubble ──────────────────────
  const s0op = interpolate(prog, [0.00, 0.04, 0.18, 0.22], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const s0scale = interpolate(prog, [0.00, 0.06], [0.7, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ── Stage 1: Crawler pipe ──────────────────────
  const s1op = interpolate(prog, [0.18, 0.22, 0.38, 0.42], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const pipeFlowProg = interpolate(prog, [0.20, 0.38], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // ── Stage 2: Claude brain ──────────────────────
  const s2op = interpolate(prog, [0.38, 0.42, 0.58, 0.62], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const claudePulse = Math.sin(f * 0.15) * 0.5 + 0.5;

  // ── Stage 3: Wiki node graph ──────────────────────
  const s3op = interpolate(prog, [0.58, 0.62, 0.76, 0.80], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // ── Stage 4: Dashboard card ──────────────────────
  const s4op = interpolate(prog, [0.76, 0.82], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const s4scale = interpolate(prog, [0.76, 0.85], [0.8, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 딸깍
  const ddakOp = interpolate(prog, [0.85, 0.93], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 스테이지 라벨 페이드
  const stageLabelOp = interpolate(prog, [stage.at, stage.at + 0.05, Math.min(1, stage.at + 0.18)], [0, 1, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 우상단 샘플 라벨 */}
      <div style={{
        position: 'absolute', top: 40, right: 60,
        color: C.textSub, fontSize: 22, fontWeight: 600, letterSpacing: 4,
        opacity: labelOp, zIndex: 50,
      }}>SAMPLE D · DATA FLOW</div>

      {/* 좌상단 스테이지 표시 */}
      <div style={{
        position: 'absolute', top: 60, left: 80, opacity: stageLabelOp,
      }}>
        <div style={{ color: C.textSub, fontSize: 20, fontWeight: 500, letterSpacing: 4, marginBottom: 6 }}>
          STAGE {stageIdx + 1} / {STAGES.length}
        </div>
        <div style={{
          color: C.main, fontSize: 48, fontWeight: 900,
          textShadow: GLOW.mid.text, letterSpacing: 2,
        }}>{stage.name}</div>
        <div style={{ color: C.textPrimary, fontSize: 26, fontWeight: 500, marginTop: 6, opacity: 0.85 }}>
          {stage.label}
        </div>
      </div>

      {/* ── Stage 0: Telegram Bubble ───────────────────── */}
      {s0op > 0.01 && (
        <div style={{
          position: 'absolute', left: 760, top: 380, width: 400, height: 200,
          background: '#1A2A36',
          border: `2px solid #2196F3`,
          borderRadius: '24px 24px 24px 4px',
          padding: '24px 28px',
          opacity: s0op,
          transform: `scale(${s0scale})`,
          boxShadow: '0 0 30px rgba(33,150,243,0.4)',
          display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          <div style={{ color: '#80C9F0', fontSize: 22, fontWeight: 700 }}>@stock_telegram</div>
          <div style={{ color: C.textPrimary, fontSize: 30, fontWeight: 600, lineHeight: 1.3 }}>
            SK하이닉스 HBM4 Vera Rubin<br />독점 가능성 95%
          </div>
          <div style={{ color: C.textSub, fontSize: 16, marginTop: 4 }}>04:12 AM</div>
        </div>
      )}

      {/* ── Stage 1: Crawler Pipe (좌→우 흐름) ───────────────────── */}
      {s1op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: s1op }}>
          {/* 파이프 */}
          <div style={{
            position: 'absolute', left: 200, top: 480, right: 200, height: 80,
            background: 'linear-gradient(90deg, rgba(0,191,154,0.15) 0%, rgba(0,255,208,0.25) 50%, rgba(0,191,154,0.15) 100%)',
            border: `1px solid ${C.borderActive}`,
            borderRadius: 40,
            boxShadow: 'inset 0 0 20px rgba(0,255,208,0.2)',
          }} />
          {/* 흐르는 입자들 */}
          {Array.from({ length: 6 }).map((_, i) => {
            const delay = i * 0.12;
            const localProg = ((pipeFlowProg - delay) + 1.5) % 1;
            const x = 220 + localProg * 1480;
            return (
              <div key={i} style={{
                position: 'absolute', left: x - 8, top: 512,
                width: 16, height: 16, borderRadius: '50%',
                background: C.main,
                boxShadow: GLOW.mid.box,
                opacity: localProg > 0.05 && localProg < 0.95 ? 1 : 0,
              }} />
            );
          })}
          {/* 라벨 */}
          <div style={{ position: 'absolute', left: 200, top: 420, color: C.textSub, fontSize: 22, fontWeight: 600 }}>
            telegram · news · blog
          </div>
          <div style={{ position: 'absolute', right: 200, top: 420, color: C.main, fontSize: 22, fontWeight: 700, textAlign: 'right' }}>
            312 items
          </div>
        </div>
      )}

      {/* ── Stage 2: Claude Brain ───────────────────── */}
      {s2op > 0.01 && (
        <div style={{
          position: 'absolute', left: 760, top: 340,
          width: 400, height: 400,
          opacity: s2op,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {/* 외곽 링 펄스 */}
          {[0, 1, 2].map(r => {
            const ringScale = 1 + r * 0.4 + claudePulse * 0.15;
            const ringOp = (1 - r * 0.3) * (0.4 + claudePulse * 0.3);
            return (
              <div key={r} style={{
                position: 'absolute',
                width: 280, height: 280, borderRadius: '50%',
                border: `2px solid ${C.main}`,
                opacity: ringOp,
                transform: `scale(${ringScale})`,
                boxShadow: r === 0 ? GLOW.strong.box : undefined,
              }} />
            );
          })}
          {/* 중앙 Claude 표식 */}
          <div style={{
            width: 220, height: 220, borderRadius: '50%',
            background: 'radial-gradient(circle at 50% 50%, #003D31 0%, #000000 70%)',
            border: `3px solid ${C.main}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: GLOW.strong.box,
            color: C.main, fontSize: 56, fontWeight: 900,
            textShadow: GLOW.strong.text,
            letterSpacing: 4,
          }}>AI</div>
          {/* 분류 라벨들 */}
          {['반도체', '조선', '방산', 'AI', '바이오'].map((t, i) => {
            const angle = (i / 5) * 360 - 90;
            const rad = (angle * Math.PI) / 180;
            const r = 280;
            const x = Math.cos(rad) * r;
            const y = Math.sin(rad) * r;
            const tagOp = interpolate(prog, [0.42 + i * 0.02, 0.46 + i * 0.02], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            return (
              <div key={i} style={{
                position: 'absolute',
                left: 200 + x - 60, top: 200 + y - 24,
                width: 120, height: 48,
                background: C.cardBg,
                border: `1px solid ${C.borderActive}`,
                borderRadius: 8,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: C.main, fontSize: 22, fontWeight: 700,
                opacity: tagOp,
                boxShadow: GLOW.weak.box,
              }}>{t}</div>
            );
          })}
        </div>
      )}

      {/* ── Stage 3: Wiki Node Graph ───────────────────── */}
      {s3op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: s3op }}>
          <svg width={1920} height={1080}>
            {/* 엣지들 */}
            {[
              [960, 540, 760, 380], [960, 540, 1160, 380],
              [960, 540, 760, 700], [960, 540, 1160, 700],
              [760, 380, 1160, 380], [760, 700, 1160, 700],
              [760, 380, 760, 700], [1160, 380, 1160, 700],
            ].map(([x1, y1, x2, y2], i) => {
              const drawAt = 0.62 + i * 0.015;
              const dp = interpolate(prog, [drawAt, drawAt + 0.04], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
              return (
                <line key={i}
                  x1={x1} y1={y1}
                  x2={x1 + (x2 - x1) * dp} y2={y1 + (y2 - y1) * dp}
                  stroke={C.main} strokeWidth={2} opacity={0.5 * dp}
                  style={{ filter: 'drop-shadow(0 0 4px rgba(0,255,208,0.6))' }}
                />
              );
            })}
          </svg>
          {/* 노드들 */}
          {[
            { x: 960, y: 540, label: 'SK하이닉스', big: true },
            { x: 760, y: 380, label: 'HBM4' },
            { x: 1160, y: 380, label: '수출🔴' },
            { x: 760, y: 700, label: '컨센↑' },
            { x: 1160, y: 700, label: '수급A' },
          ].map((n, i) => {
            const popAt = 0.60 + i * 0.025;
            const op = interpolate(prog, [popAt, popAt + 0.05], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            const sc = interpolate(prog, [popAt, popAt + 0.05], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
            const size = n.big ? 140 : 100;
            return (
              <div key={i} style={{
                position: 'absolute',
                left: n.x - size / 2, top: n.y - size / 2,
                width: size, height: size, borderRadius: '50%',
                background: n.big ? C.cardBgActive : C.cardBg,
                border: `2px solid ${C.main}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: C.main, fontSize: n.big ? 22 : 17, fontWeight: 800,
                opacity: op,
                transform: `scale(${sc})`,
                boxShadow: n.big ? GLOW.mid.box : GLOW.weak.box,
                textAlign: 'center', padding: 8,
              }}>{n.label}</div>
            );
          })}
        </div>
      )}

      {/* ── Stage 4: Dashboard Card ───────────────────── */}
      {s4op > 0.01 && (
        <div style={{
          position: 'absolute', left: 560, top: 280, width: 800, height: 480,
          background: C.cardBgActive,
          border: `2px solid ${C.main}`,
          borderRadius: 22,
          padding: 36,
          opacity: s4op,
          transform: `scale(${s4scale})`,
          boxShadow: GLOW.strong.box,
          display: 'flex', flexDirection: 'column', gap: 18,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ color: C.textSub, fontSize: 22, fontWeight: 600, letterSpacing: 4 }}>08:00 · TODAY PICK</div>
            <div style={{ color: C.main, fontSize: 22, fontWeight: 700 }}>#1</div>
          </div>
          <div style={{ color: C.textPrimary, fontSize: 64, fontWeight: 900 }}>SK하이닉스</div>
          <div style={{ color: C.main, fontSize: 96, fontWeight: 900, textShadow: GLOW.strong.text }}>8 / 9</div>
          <div style={{ color: C.textSub, fontSize: 22, fontWeight: 500, lineHeight: 1.5 }}>
            수급빈집 A · 수출🔴 · 어닝서프 · 리포트 신고가<br />
            <span style={{ color: C.mainLight }}>지난 4시간 동안 위키가 정리한 결과</span>
          </div>
        </div>
      )}

      {/* 딸깍 */}
      <div style={{
        position: 'absolute', bottom: 110, left: 0, right: 0,
        textAlign: 'center',
        color: C.main, fontSize: 96, fontWeight: 900, letterSpacing: 8,
        textShadow: GLOW.strong.text,
        opacity: ddakOp,
        transform: `scale(${0.85 + ddakOp * 0.15})`,
      }}>딸깍</div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '10%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: labelOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 32, fontWeight: 700, opacity: 0.85 }}>
          데이터 한 조각이 카드 한 장이 되기까지
        </div>
      </div>
    </AbsoluteFill>
  );
};
