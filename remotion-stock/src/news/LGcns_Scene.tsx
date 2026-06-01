import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, interpolate, Easing } from 'remotion';
import { C, FONT } from '../constants';

export const LGcns_Scene: React.FC = () => {
  const f = useCurrentFrame();

  const leftOp  = interpolate(f, [5, 35],  [0, 1], { extrapolateRight: 'clamp' });
  const leftX   = interpolate(f, [5, 35],  [-80, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const rightOp = interpolate(f, [15, 45], [0, 1], { extrapolateRight: 'clamp' });
  const rightX  = interpolate(f, [15, 45], [80, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const pctOp   = interpolate(f, [60, 80], [0, 1], { extrapolateRight: 'clamp' });
  const pctS    = interpolate(f, [60, 80], [0.5, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.8)) });
  const tagOp   = interpolate(f, [88, 105], [0, 1], { extrapolateRight: 'clamp' });
  const subOp   = interpolate(f, [105, 125], [0, 1], { extrapolateRight: 'clamp' });
  const arrowOp = interpolate(f, [40, 55], [0, 1], { extrapolateRight: 'clamp' });
  const pulse   = Math.sin(f * 0.12) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [8, 24]);

  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT }}>

      {/* 좌우 분할 */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 88, display: 'flex' }}>

        {/* 좌 — 깐부회동 */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', opacity: leftOp, transform: `translateX(${leftX}px)` }}>
          <Img src={staticFile('images/jh/gen_s02.jpeg')}
            style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center' }} />
          <div style={{ position: 'absolute', inset: 0,
            background: 'linear-gradient(90deg, transparent 55%, rgba(0,0,0,0.95) 100%)' }} />
          <div style={{ position: 'absolute', inset: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 60%)' }} />
          <div style={{ position: 'absolute', left: 0, top: '8%', bottom: '8%', width: 3,
            background: `linear-gradient(180deg, transparent, ${C.main}, transparent)`,
            boxShadow: `0 0 12px ${C.main}` }} />
          <div style={{ position: 'absolute', left: 50, bottom: 50 }}>
            <div style={{ background: 'rgba(0,255,208,0.12)', border: `1px solid ${C.main}`,
              borderRadius: 4, padding: '4px 14px', fontSize: 20, fontWeight: 700,
              color: C.main, letterSpacing: 3, marginBottom: 12 }}>
              🤝 깐부회동 2025.10
            </div>
            <div style={{ fontSize: 48, fontWeight: 900, color: '#fff', lineHeight: 1.3 }}>
              이재용 · 정의선<br/>+ 젠슨황
            </div>
          </div>
        </div>

        {/* 화살표 */}
        <div style={{ width: 100, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', opacity: arrowOp, zIndex: 10 }}>
          <div style={{ fontSize: 52, color: C.main, textShadow: `0 0 16px ${C.main}` }}>→</div>
          <div style={{ fontSize: 16, color: C.main, fontWeight: 700, letterSpacing: 2 }}>직후</div>
        </div>

        {/* 우 — 실제 차트 */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', opacity: rightOp, transform: `translateX(${rightX}px)` }}>
          <Img src={staticFile('images/jh/lgcns_chart.jpeg')}
            style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'left 15%' }} />
          {/* 좌측 페이드 */}
          <div style={{ position: 'absolute', inset: 0,
            background: 'linear-gradient(90deg, rgba(0,0,0,0.75) 0%, transparent 30%)' }} />
          {/* 하단 다크 */}
          <div style={{ position: 'absolute', inset: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 40%)' }} />

          {/* +29.96% — 차트 중앙 오버레이 */}
          <div style={{
            position: 'absolute', left: '50%', top: '50%',
            transform: `translate(-50%, -50%) scale(${pctS})`,
            opacity: pctOp,
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            background: 'rgba(0,0,0,0.6)', borderRadius: 16, padding: '24px 40px',
            border: '2px solid rgba(255,67,54,0.5)',
            backdropFilter: 'blur(4px)',
          }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#FF9090', marginBottom: 4, letterSpacing: 2 }}>
              전일 대비
            </div>
            <div style={{ fontSize: 96, fontWeight: 900, color: '#FF4336', lineHeight: 1,
              textShadow: `0 0 ${gSz}px rgba(255,67,54,0.9), 0 0 ${gSz * 2}px rgba(255,67,54,0.4)` }}>
              +29.96%
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#fff', marginTop: 8 }}>
              ▲ 34,100원
            </div>
          </div>

          {/* 상한가 태그 — 우하단 */}
          <div style={{ position: 'absolute', right: 24, bottom: 24,
            opacity: tagOp, background: '#FF4336', borderRadius: 10,
            padding: '12px 32px', fontSize: 28, fontWeight: 900, color: '#fff',
            letterSpacing: 4, boxShadow: '0 0 24px rgba(255,67,54,0.8)' }}>
            🔴 상한가
          </div>
        </div>
      </div>

      {/* 자막바 */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 88,
        background: 'linear-gradient(to top, rgba(0,0,0,0.95) 0%, transparent 100%)',
        display: 'flex', alignItems: 'center', paddingInline: 80, opacity: subOp }}>
        <div style={{ borderLeft: `4px solid ${C.main}`, paddingLeft: 18,
          color: '#fff', fontSize: 30, fontWeight: 700,
          textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>
          깐부회동 직후 — LG씨엔에스 상한가. 이번 회동 다음 타자는?
        </div>
      </div>

    </AbsoluteFill>
  );
};

export const LGCNS_FRAMES = 180;
