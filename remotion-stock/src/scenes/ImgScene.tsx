/**
 * ImgScene.tsx — 이미지 활용 씬 패턴 2가지
 *
 * ① ImgHeroScene  — 전체 배경 이미지 + 켄번스 줌 + 텍스트 오버레이
 *    예) "조선 호황", "AI 반도체" 등 섹터 오프닝 장면
 *
 * ② ImgSplitScene — 화면 반분. 왼쪽=이미지, 오른쪽=텍스트 카드
 *    예) "젠슨황이 말했다", "대한조선 27% 마진" 등 근거 제시 장면
 *
 * 사용법 (Root.tsx에서):
 *   <Series.Sequence durationInFrames={SDUR}>
 *     <FadeWrapper>
 *       <ImgHeroScene
 *         img="images/ship_hero.jpg"
 *         label="조선 섹터"
 *         line1="도크가 없다"
 *         line2="삼각축 호황"
 *         caption="2029년까지 수주 가능 도크 — 절반도 안 남았습니다"
 *       />
 *     </FadeWrapper>
 *   </Series.Sequence>
 */

import {
  AbsoluteFill, Easing, Img, interpolate,
  staticFile, useCurrentFrame,
} from 'remotion';
import { C, FONT, GLOW } from '../constants';

// ─────────────────────────────────────────────────────────────
// ① ImgHeroScene — 전체 배경 이미지 + 켄번스 줌 + 오버레이 텍스트
// ─────────────────────────────────────────────────────────────
interface HeroProps {
  img:     string;   // public/ 기준 경로. 예: "images/ship_hero.jpg"
  label:   string;   // 상단 작은 태그. 예: "조선 섹터"
  line1:   string;   // 첫 번째 큰 타이틀
  line2:   string;   // 두 번째 큰 타이틀 (민트색)
  caption: string;   // 하단 자막
}

export const ImgHeroScene: React.FC<HeroProps> = ({ img, label, line1, line2, caption }) => {
  const f = useCurrentFrame();

  // 씬 페이드인
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });

  // 켄번스 효과: 이미지가 서서히 줌인 (1.0 → 1.08)
  const kenBurns = interpolate(f, [0, 180], [1.0, 1.08], { extrapolateRight: 'clamp' });

  // 이미지 어두운 오버레이 — 등장 시 점점 밝아짐
  const overlayOp = interpolate(f, [0, 40], [0.9, 0.62], { extrapolateRight: 'clamp' });

  // 스캔 라인
  const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // 라벨
  const labelOp = interpolate(f, [20, 40], [0, 1], { extrapolateRight: 'clamp' });
  const labelY  = interpolate(f, [20, 40], [14, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Line1 — 왼쪽에서 슬라이드 + 자간 수축
  const t1X  = interpolate(f, [36, 64], [-140, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [36, 64], [0, 1],    { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [36, 64], [16, 0],   { extrapolateRight: 'clamp' });

  // Line2 — 오른쪽에서 슬라이드 + 민트 글로우
  const t2X  = interpolate(f, [52, 82], [140, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = interpolate(f, [52, 82], [0, 1],    { extrapolateRight: 'clamp' });

  // 동적 글로우 + 브리드
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 32]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;
  const breathe = t2Op > 0.9 ? Math.sin(f * 0.07) * 0.018 + 1 : 1;

  // 하단 구분선
  const lineW = interpolate(f, [70, 100], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 자막
  const capOp = interpolate(f, [90, 112], [0, 1], { extrapolateRight: 'clamp' });

  // 배경 글로우 펄스
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT, overflow: 'hidden' }}>

      {/* 배경 이미지 — 켄번스 */}
      <div style={{
        position: 'absolute', inset: 0,
        transform: `scale(${kenBurns})`,
        transformOrigin: 'center center',
      }}>
        <Img
          src={staticFile(img)}
          style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center 55%' }}
        />
      </div>

      {/* 어두운 오버레이 그라데이션 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `linear-gradient(
          to top,
          rgba(0,0,0,${overlayOp}) 0%,
          rgba(0,0,0,${overlayOp * 0.85}) 40%,
          rgba(0,0,0,${overlayOp * 0.5}) 100%
        )`,
      }} />

      {/* 배경 민트 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 60%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 스캔 라인 */}
      <div style={{
        position: 'absolute', left: 0, right: 0,
        top: `${scanY}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scanOp, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* 콘텐츠 — 화면 하단 40%에 집중 배치 */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: '18%',
        top: '45%',
        display: 'flex', flexDirection: 'column',
        alignItems: 'flex-start', justifyContent: 'flex-end',
        paddingInline: 100, paddingBottom: 20,
        gap: 0,
      }}>

        {/* 라벨 태그 */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: 'rgba(0,255,208,0.15)',
          border: '1px solid #00FFD0',
          borderRadius: 4,
          padding: '4px 14px',
          fontSize: 24, fontWeight: 700, color: C.main,
          letterSpacing: 4,
          opacity: labelOp,
          transform: `translateY(${labelY}px)`,
          marginBottom: 22,
        }}>
          {label}
        </div>

        {/* Line1 */}
        <div style={{
          color: C.textPrimary, fontSize: 130, fontWeight: 900,
          lineHeight: 1.1, letterSpacing: t1Ls,
          opacity: t1Op,
          transform: `translateX(${t1X}px)`,
        }}>
          {line1}
        </div>

        {/* Line2 민트 */}
        <div style={{
          color: C.main, fontSize: 130, fontWeight: 900,
          lineHeight: 1.1,
          opacity: t2Op,
          transform: `translateX(${t2X}px) scale(${breathe})`,
          textShadow: t2Op > 0.5 ? dynGlow : undefined,
        }}>
          {line2}
        </div>

        {/* 구분선 */}
        <div style={{
          width: `${lineW * 320}px`, height: 2,
          background: `linear-gradient(90deg, ${C.main}, transparent)`,
          marginTop: 18, marginBottom: 0,
        }} />

      </div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'flex-start',
        paddingInline: 100, opacity: capOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 36, fontWeight: 700 }}>
          {caption}
        </div>
      </div>

    </AbsoluteFill>
  );
};


// ─────────────────────────────────────────────────────────────
// ② ImgSplitScene — 왼쪽 이미지 | 오른쪽 텍스트
// ─────────────────────────────────────────────────────────────
interface SplitProps {
  img:      string;         // public/ 기준 경로
  imgPos?:  string;         // object-position (기본: "center top")
  label:    string;         // 우측 상단 작은 태그
  title:    string;         // 우측 큰 제목
  points:   string[];       // 불릿 포인트 (최대 4개)
  caption:  string;         // 하단 자막
}

export const ImgSplitScene: React.FC<SplitProps> = ({
  img, imgPos = 'center top', label, title, points, caption,
}) => {
  const f = useCurrentFrame();

  const fadeIn  = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow  = Math.sin(f * 0.04) * 0.03 + 0.04;

  // 이미지 — 왼쪽에서 슬라이드인
  const imgX    = interpolate(f, [8, 35],  [-60, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const imgOp   = interpolate(f, [8, 35],  [0, 1],   { extrapolateRight: 'clamp' });

  // 우측 컨텐츠
  const labelOp = interpolate(f, [28, 48], [0, 1],  { extrapolateRight: 'clamp' });
  const titleY  = interpolate(f, [38, 62], [30, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const titleOp = interpolate(f, [38, 62], [0, 1],  { extrapolateRight: 'clamp' });

  // 불릿 순차 등장
  const bulletStart = [60, 80, 100, 120];

  // 자막
  const capOp = interpolate(f, [130, 148], [0, 1], { extrapolateRight: 'clamp' });

  // 스캔 라인
  const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 25% 50%, rgba(0,255,208,1) 0%, transparent 55%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 스캔 라인 */}
      <div style={{
        position: 'absolute', left: 0, right: 0,
        top: `${scanY}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scanOp, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* 레이아웃 — 콘텐츠 영역 (하단 16% 제외) */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '16%',
        display: 'grid', gridTemplateColumns: '1fr 1fr',
      }}>

        {/* 왼쪽 — 이미지 */}
        <div style={{
          position: 'relative', overflow: 'hidden',
          opacity: imgOp, transform: `translateX(${imgX}px)`,
        }}>
          <Img
            src={staticFile(img)}
            style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: imgPos }}
          />
          {/* 오른쪽 페이드아웃 */}
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(90deg, transparent 50%, rgba(0,0,0,0.95) 100%)',
          }} />
          {/* 하단 페이드아웃 */}
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 50%)',
          }} />
          {/* 민트 왼쪽 보더 */}
          <div style={{
            position: 'absolute', left: 0, top: '10%', bottom: '10%',
            width: 3,
            background: `linear-gradient(180deg, transparent, ${C.main}, transparent)`,
            boxShadow: `0 0 12px ${C.main}`,
            opacity: imgOp,
          }} />
        </div>

        {/* 오른쪽 — 텍스트 */}
        <div style={{
          display: 'flex', flexDirection: 'column',
          justifyContent: 'center',
          paddingLeft: 60, paddingRight: 80, gap: 0,
        }}>

          {/* 라벨 */}
          <div style={{
            color: C.main, fontSize: 22, fontWeight: 700,
            letterSpacing: 4, opacity: labelOp, marginBottom: 20,
          }}>
            {label}
          </div>

          {/* 제목 */}
          <div style={{
            color: C.textPrimary, fontSize: 72, fontWeight: 900,
            lineHeight: 1.2,
            opacity: titleOp,
            transform: `translateY(${titleY}px)`,
            marginBottom: 32,
          }}>
            {title}
          </div>

          {/* 불릿 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {points.slice(0, 4).map((pt, i) => {
              const s   = bulletStart[i] ?? 60 + i * 20;
              const bOp = interpolate(f, [s, s + 18], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
              const bY  = interpolate(f, [s, s + 18], [16, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
              return (
                <div key={i} style={{
                  display: 'flex', gap: 14, alignItems: 'flex-start',
                  opacity: bOp, transform: `translateY(${bY}px)`,
                }}>
                  <div style={{
                    color: C.main, fontSize: 26, fontWeight: 900,
                    lineHeight: 1, marginTop: 4, flexShrink: 0,
                    textShadow: GLOW.weak.text,
                  }}>▲</div>
                  <div style={{
                    color: C.textPrimary, fontSize: 28, fontWeight: 500,
                    lineHeight: 1.55,
                  }}>
                    {pt}
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      </div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        paddingInline: 80, opacity: capOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 36, fontWeight: 700, textAlign: 'center' }}>
          {caption}
        </div>
      </div>

    </AbsoluteFill>
  );
};
