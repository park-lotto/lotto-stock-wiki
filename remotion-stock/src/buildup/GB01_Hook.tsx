// GB01 — 씬1 훅 임팩트형 (17.96초 = 539프레임) ← Whisper 싱크 적용
// 임팩트형: 좌←→우 교차 X슬라이드 + letterSpacing 22→0 + 글로우버스트
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO = 'audio/국씬1 수정.m4a';
const HAS_AUDIO = true;

export const GB01_Hook = () => {
  const f = useCurrentFrame();

  // ── 페이드인 ──
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });

  // ── 배경 글로우 펄스 (임팩트형 기준) ──
  const bgGlow = Math.sin(f * 0.04) * 0.035 + 0.05;

  // ── 수평 스캔라인 (f0-38) ──
  const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // ── 라벨 (f22-42) ──
  const labelOp = interpolate(f, [22, 42], [0, 1], { extrapolateRight: 'clamp' });

  // ── Line1: "국민성장펀드" 좌→ 슬라이드 + 자간 22→0 (f38-68) ──
  const t1X  = interpolate(f, [38, 68], [-180, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [38, 68], [0, 1],    { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [38, 68], [22, 0],   { extrapolateRight: 'clamp' });

  // ── Line2: "넣지 마세요" 우← 슬라이드 (f55-88) ──
  const t2X  = interpolate(f, [55, 88], [180, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = interpolate(f, [55, 88], [0, 1],    { extrapolateRight: 'clamp' });

  // ── 브리드 (t2 완전 등장 후) ──
  const breathe = t2Op > 0.9 ? Math.sin(f * 0.07) * 0.018 + 1 : 1;

  // ── 동적 글로우 (Line2) ──
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 34]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.3)`;

  // ── 글로우 버스트 (f85-118) ──
  const burstOp    = interpolate(f, [85, 92, 118], [0, 0.55, 0], { extrapolateRight: 'clamp' });
  const burstScale = interpolate(f, [85, 118], [0.2, 2.8], { extrapolateRight: 'clamp' });

  // ── 통계 수치 등장 → f166 "6천억 모집" (Whisper: 5.52s) ──
  const statOp = interpolate(f, [166, 209], [0, 1], { extrapolateRight: 'clamp' });
  const statY  = interpolate(f, [166, 209], [30, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ── 반전 박스 → f273 "완판이라는데" (Whisper: 9.10s) + f403 "저는 안 넣었어요" ──
  const revealOp = interpolate(f, [273, 324], [0, 1], { extrapolateRight: 'clamp' });
  const revealY  = interpolate(f, [273, 324], [24, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  // "저는 안 넣었어요" 강조 글로우 (f403, Whisper: 13.44s)
  const revealGlow = interpolate(f, [403, 443], [0, 1], { extrapolateRight: 'clamp' });

  // ── 서브 텍스트 → f468 "지금부터 이유 말씀드려볼게요" (Whisper: 15.60s) ──
  const subOp = interpolate(f, [468, 515], [0, 1], { extrapolateRight: 'clamp' });


  // ── 자막 바 (f80-105) ──
  const capOp = interpolate(f, [80, 105], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}

      {/* 배경 중앙 글로우 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow,
      }} />

      {/* 수평 스캔라인 f0-38 */}
      <div style={{
        position: 'absolute', left: 0, right: 0,
        top: `${scanY}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scanOp, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* 글로우 버스트 */}
      <div style={{
        position: 'absolute', top: '45%', left: '50%',
        width: 560, height: 560, marginLeft: -280, marginTop: -280,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
        opacity: burstOp, transform: `scale(${burstScale})`, pointerEvents: 'none',
      }} />

      {/* 콘텐츠 영역 (상단 82%) */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 0,
      }}>

        {/* 라벨 */}
        <div style={{
          fontSize: 28, fontWeight: 500, color: C.textSub, letterSpacing: 5,
          opacity: labelOp, marginBottom: 24,
        }}>2026 정책 이슈</div>

        {/* Line1 — 국민성장펀드 */}
        <div style={{
          fontSize: 148, fontWeight: 900, color: C.textPrimary,
          opacity: t1Op,
          transform: `translateX(${t1X}px)`,
          letterSpacing: t1Ls,
          lineHeight: 1,
        }}>국민성장펀드</div>

        {/* Line2 — 청약하셨나요? */}
        <div style={{
          fontSize: 148, fontWeight: 900, color: C.main,
          opacity: t2Op,
          transform: `translateX(${t2X}px) scale(${breathe})`,
          textShadow: dynGlow,
          lineHeight: 1, marginTop: 8,
        }}>청약하셨나요?</div>

        {/* 통계 */}
        <div style={{
          display: 'flex', gap: 64, marginTop: 48,
          opacity: statOp,
          transform: `translateY(${statY}px)`,
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 5, marginBottom: 8 }}>모집 규모</div>
            <div style={{
              color: C.main, fontSize: 72, fontWeight: 900,
              fontFamily: '"Consolas","Menlo",monospace',
              textShadow: GLOW.mid.text,
            }}>6,000억</div>
          </div>
          <div style={{ width: 1, background: 'rgba(255,255,255,0.12)', alignSelf: 'stretch' }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 5, marginBottom: 8 }}>판매 기간</div>
            <div style={{
              color: C.textPrimary, fontSize: 72, fontWeight: 900,
              fontFamily: '"Consolas","Menlo",monospace',
            }}>3주 한정</div>
          </div>
        </div>

        {/* 반전 박스 */}
        <div style={{
          marginTop: 40,
          opacity: revealOp,
          transform: `translateY(${revealY}px)`,
          border: `1.5px solid rgba(0,255,208,${0.4 + revealGlow * 0.4})`,
          borderRadius: 16, padding: '20px 48px',
          background: `rgba(0,255,208,${0.05 + revealGlow * 0.05})`,
          boxShadow: revealGlow > 0.3 ? `0 0 ${24 * revealGlow}px rgba(0,255,208,${0.18 * revealGlow})` : undefined,
        }}>
          <div style={{ color: C.textPrimary, fontSize: 44, fontWeight: 700 }}>
            수십만 명이 몰렸는데&nbsp;—&nbsp;
            <span style={{ color: C.main, textShadow: GLOW.mid.text }}>저는 안 넣었어요.</span>
          </div>
        </div>

        {/* 서브 */}
        <div style={{
          marginTop: 24,
          opacity: subOp,
          color: C.textSub, fontSize: 32, fontWeight: 500, letterSpacing: 2,
        }}>조건 3가지, 확인해드릴게요 ↓</div>

      </div>

      {/* 하단 자막 바 (하단 16%) */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: capOp,
      }}>
        <div style={{
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80,
        }}>
          조건이 있습니다. 하나라도 안 맞으면&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>반도체 ETF가 유리합니다.</span>
        </div>
      </div>

    </AbsoluteFill>
  );
};
