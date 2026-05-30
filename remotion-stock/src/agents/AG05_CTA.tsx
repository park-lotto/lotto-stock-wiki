// AG05 — 씬8 CTA (30초 / 900프레임)
// "'직원' 댓글 → 정리본 DM" + STOCK BRAIN 로고 + 알림 신청
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

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

// 파티클
const PARTICLES = Array.from({ length: 8 }).map((_, i) => ({
  x: 10 + (i * 11) % 80,
  startY: 110 - (i * 13) % 30,
  size: 4 + (i % 3) * 3,
  delay: i * 12,
  speed: 40 + (i % 4) * 15,
}));

export const AG05_CTA: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 20);
  const timeOp = ip(f, 10, 30);

  // ━━━━ Part 1 (f0~450): 댓글 CTA ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  const part1Op = ip(f, 0, 20) * (1 - ip(f, 400, 440));

  // 스캔라인 (f0~38)
  const scanY  = interpolate(f, [0, 38], [-2, 104], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 라벨 (f22~42)
  const labelOp = ip(f, 22, 42);

  // 아이콘 (f30~58)
  const iconScale = interpolate(f, [30, 58], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(1.1)),
  });
  const iconOp = ip(f, 30, 58);

  // "댓글에" 텍스트 (f68~100)
  const ct1Op = ip(f, 68, 100);
  const ct1Y  = interpolate(f, [68, 100], [40, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // "'직원'" 키워드 강조 (f105~150)
  const kwOp    = ip(f, 105, 150);
  const kwScale = interpolate(f, [105, 150], [0.4, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(1.0)),
  });
  const kwPulse = kwOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.03 : 1;

  // "라고 남겨주시면" (f160~200)
  const ct2Op = ip(f, 160, 200);
  const ct2Y  = interpolate(f, [160, 200], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 화살표 + "정리본 DM" (f230~290)
  const arrowOp    = ip(f, 230, 270);
  const arrowScaleX = ip(f, 230, 275);
  const dmOp       = ip(f, 270, 310);

  // 부가 텍스트 (f340~390)
  const subOp = ip(f, 340, 380);
  const subY  = interpolate(f, [340, 380], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ━━━━ Part 2 (f440~900): STOCK BRAIN 로고 씬 ━━━━━━━━━━━━━━━━━━
  const part2Op = ip(f, 440, 480);

  // STOCK BRAIN 로고 (f480~540)
  const logoOp    = ip(f, 480, 540);
  const logoY     = interpolate(f, [480, 540], [60, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const logoLs    = interpolate(f, [480, 540], [14, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const logoPulse = logoOp > 0.95 ? 1 + Math.sin(f * 0.07) * 0.018 : 1;

  // 뇌 아이콘 (f500~545)
  const brainScale = interpolate(f, [500, 545], [0.2, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.65)),
  });
  const brainOp = ip(f, 500, 545);
  const brainGlowSize = interpolate(Math.sin(f * 0.07) * 0.5 + 0.5, [0, 1], [20, 55]);

  // 슬로건 (f560~610)
  const slOp = ip(f, 560, 605);
  const slY  = interpolate(f, [560, 605], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // "조만간 오픈" (f630~680)
  const openOp    = ip(f, 630, 675);
  const openScale = interpolate(f, [630, 675], [0.6, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.7)),
  });

  // 구독 버튼 (f700~750)
  const btnOp    = ip(f, 700, 745);
  const btnScale = interpolate(f, [700, 745], [0.2, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.6)),
  });
  const pulseMag     = Math.min(1, ip(f, 700, 780));
  const btnGlowSize  = 20 + Math.sin(f * 0.1) * 12 * pulseMag;
  const btnPulse     = btnOp > 0.9 ? 1 + Math.sin(f * 0.09) * 0.025 * pulseMag : 1;

  // 파티클 (f700~)
  const CYCLE_LEN = 90;

  // 글로우
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [12, 40]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.3)`;
  const bgGlowBase = Math.sin(f * 0.04) * 0.035 + 0.05;
  const bgGlowAmp  = ip(f, 700, 800, 0, 0.05);

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)`,
        opacity: bgGlowBase + bgGlowAmp, pointerEvents: 'none',
      }} />

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 8 · CTA</div>

      {/* ━━━━ PART 1: 댓글 CTA ━━━━ */}
      {part1Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: part1Op,
          gap: 24,
        }}>
          {/* 스캔라인 */}
          <div style={{
            position: 'absolute', left: 0, right: 0,
            top: `${scanY}%`, height: 2,
            background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
            boxShadow: '0 0 10px rgba(0,255,208,0.9)',
            opacity: scanOp, zIndex: 10, pointerEvents: 'none',
          }} />

          {/* 라벨 */}
          <div style={{
            opacity: labelOp,
            color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 8,
          }}>CALL TO ACTION</div>

          {/* 댓글 아이콘 */}
          <div style={{
            opacity: iconOp,
            transform: `scale(${iconScale})`,
            fontSize: 90,
          }}>💬</div>

          {/* "댓글에" */}
          <div style={{
            opacity: ct1Op,
            transform: `translateY(${ct1Y}px)`,
            fontSize: 52, fontWeight: 700, color: '#9ca3af',
          }}>댓글에</div>

          {/* '직원' 키워드 */}
          <div style={{
            opacity: kwOp,
            transform: `scale(${kwScale * kwPulse})`,
            transformOrigin: 'center',
            padding: '18px 64px',
            background: `${C.main}14`,
            border: `2.5px solid ${C.main}`,
            borderRadius: 20,
            boxShadow: `0 0 28px rgba(0,255,208,0.35)`,
          }}>
            <div style={{
              fontSize: 88, fontWeight: 900,
              color: C.main, textShadow: dynGlow,
              letterSpacing: 12,
            }}>'직원'</div>
          </div>

          {/* "이라고 남겨주시면" */}
          <div style={{
            opacity: ct2Op,
            transform: `translateY(${ct2Y}px)`,
            fontSize: 52, fontWeight: 700, color: '#9ca3af',
          }}>이라고 남겨주시면</div>

          {/* 화살표 + 정리본 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 24,
            marginTop: 4,
          }}>
            <div style={{
              opacity: arrowOp,
              transform: `scaleX(${arrowScaleX})`,
              transformOrigin: 'left center',
              height: 3, width: 80,
              background: `linear-gradient(90deg, transparent, ${C.main})`,
              borderRadius: 4,
            }} />
            <div style={{
              opacity: dmOp,
              padding: '14px 36px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 14,
            }}>
              <div style={{ fontSize: 30, fontWeight: 700, color: '#e5e7eb' }}>
                📩 시스템 구성 정리본 DM 드립니다
              </div>
            </div>
          </div>

          {/* 부가 텍스트 */}
          <div style={{
            opacity: subOp,
            transform: `translateY(${subY}px)`,
            textAlign: 'center',
            color: '#4b5563', fontSize: 26, fontWeight: 500, lineHeight: 1.6,
            marginTop: 8,
          }}>
            그리고 이 분석. 저만 보기 아깝더라고요.
          </div>
        </div>
      )}

      {/* ━━━━ PART 2: STOCK BRAIN 로고 ━━━━ */}
      {part2Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: part2Op,
          gap: 28,
        }}>

          {/* 파티클 */}
          {f >= 700 && PARTICLES.map((p, i) => {
            const age      = (f - 700 + p.delay * 0.5) % CYCLE_LEN;
            const progress = age / CYCLE_LEN;
            const py       = p.startY - progress * p.speed;
            const pop      = progress < 0.2
              ? progress / 0.2
              : progress > 0.7
              ? (1 - progress) / 0.3
              : 1;
            return (
              <div key={i} style={{
                position: 'absolute',
                left: `${p.x}%`, top: `${py}%`,
                width: p.size, height: p.size, borderRadius: '50%',
                background: C.main,
                opacity: pop * 0.45,
                boxShadow: `0 0 ${p.size * 2}px ${C.main}`,
                pointerEvents: 'none',
              }} />
            );
          })}

          {/* 뇌 아이콘 */}
          <div style={{
            opacity: brainOp,
            transform: `scale(${brainScale})`,
            fontSize: 100,
            filter: `drop-shadow(0 0 ${brainGlowSize}px rgba(0,255,208,0.7))`,
          }}>🧠</div>

          {/* STOCK BRAIN 로고 */}
          <div style={{
            opacity: logoOp,
            transform: `translateY(${logoY}px) scale(${logoPulse})`,
            transformOrigin: 'center',
            textAlign: 'center',
          }}>
            <div style={{
              fontSize: 110, fontWeight: 900, lineHeight: 1,
              color: C.main, textShadow: dynGlow,
              letterSpacing: logoLs,
              fontFamily: '"Consolas","Menlo",monospace',
            }}>STOCK BRAIN</div>
          </div>

          {/* 슬로건 */}
          <div style={{
            opacity: slOp,
            transform: `translateY(${slY}px)`,
            color: '#6b7280', fontSize: 28, fontWeight: 500, letterSpacing: 4,
            textAlign: 'center',
          }}>300개 정보 중 오늘 써먹을 3가지만</div>

          {/* "조만간 오픈" */}
          <div style={{
            opacity: openOp,
            transform: `scale(${openScale})`,
            transformOrigin: 'center',
            marginTop: 12,
            padding: '14px 48px',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.10)',
            borderRadius: 14,
          }}>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#9ca3af', letterSpacing: 4 }}>
              조만간 오픈합니다
            </div>
          </div>

          {/* 구독 알림 버튼 */}
          <div style={{
            opacity: btnOp,
            transform: `scale(${btnScale * btnPulse})`,
            transformOrigin: 'center',
          }}>
            <div style={{
              padding: '22px 72px',
              background: C.main,
              borderRadius: 18,
              boxShadow: `0 0 ${btnGlowSize}px rgba(0,255,208,${0.5 + pulseMag * 0.3})`,
              display: 'flex', alignItems: 'center', gap: 16,
            }}>
              <span style={{ fontSize: 36 }}>🔔</span>
              <div style={{
                fontSize: 38, fontWeight: 900, color: '#000000', letterSpacing: 2,
              }}>알림 신청하기</div>
            </div>
          </div>

        </div>
      )}

      {/* 하단 */}
      <div style={{
        position: 'absolute', bottom: 18, left: 0, right: 0,
        textAlign: 'center', opacity: timeOp,
      }}>
        <div style={{ color: '#374151', fontSize: 18, fontWeight: 600, letterSpacing: 4 }}>
          SCENE 8 · CTA · STOCK BRAIN
        </div>
      </div>

    </AbsoluteFill>
  );
};
