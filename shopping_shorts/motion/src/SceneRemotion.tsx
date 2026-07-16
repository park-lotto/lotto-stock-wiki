import {AbsoluteFill, interpolate, OffthreadVideo, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

// 씬별 리모션(B): 화면 전체를 리모션이 소유한다.
// 원본 클립(자막 제거본)을 배경으로 깔고 그 위에 채널 크롬 + 데이터 패널 + 작은 자막을 통합.
// 오버레이(A)와 달리 자막을 우리가 작게 통제하고 씬 전체를 디자인한다.
export type SceneRemotionProps = {
  videoSrc: string;   // public/ 안 파일명
  header: string;     // 좌상단 채널/스텝 라벨
  tc: string;         // 우상단 타임코드
  caption: string;    // 하단 작은 자막
  items: string[];    // 재료 패널 항목
  accent?: string;
};

export const SceneRemotion: React.FC<SceneRemotionProps> = ({
  videoSrc, header, tc, caption, items, accent = '#c6f04a',
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const headerIn = interpolate(frame, [2, 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const panelIn = spring({frame: frame - 8, fps, config: {damping: 16, stiffness: 180}});
  const panelY = interpolate(panelIn, [0, 1], [30, 0]);
  const capIn = interpolate(frame, [6, 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const ROW0 = 16, STAG = 5;

  const mono = '"Consolas","Courier New",monospace';
  const sans = '"Malgun Gothic","맑은 고딕",system-ui,sans-serif';

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      {/* 배경: 원본 클립 (자막 제거본 가정) */}
      <OffthreadVideo src={staticFile(videoSrc)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />

      {/* 상·하단 스크림: 텍스트 가독성 */}
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 62%, rgba(0,0,0,0.72) 100%)'}} />

      {/* 좌상단 채널 헤더 */}
      <div style={{position: 'absolute', top: 40, left: 36, opacity: headerIn, transform: `translateX(${(1 - headerIn) * -20}px)`}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
          <span style={{width: 26, height: 3, background: accent, display: 'inline-block', boxShadow: `0 0 8px ${accent}`}} />
          <span style={{fontFamily: mono, fontSize: 22, letterSpacing: '0.24em', color: '#fff', fontWeight: 700}}>
            {header}
          </span>
        </div>
      </div>

      {/* 우상단 타임코드 */}
      <div style={{position: 'absolute', top: 42, right: 36, opacity: headerIn * 0.8, fontFamily: mono, fontSize: 20, letterSpacing: '0.18em', color: accent}}>
        {tc}
      </div>

      {/* 재료 패널 (좌하단, 작게 통합) */}
      <div
        style={{
          position: 'absolute', left: 36, bottom: 190,
          opacity: interpolate(panelIn, [0, 1], [0, 1]),
          transform: `translateY(${panelY}px)`,
          padding: '18px 24px 20px',
          background: 'rgba(6,10,4,0.7)',
          border: `1px solid ${accent}40`,
          boxShadow: `0 0 14px ${accent}33`,
          fontFamily: sans,
          minWidth: 300,
        }}
      >
        <div style={{fontFamily: mono, fontSize: 17, letterSpacing: '0.2em', color: accent, textTransform: 'uppercase', fontWeight: 700, marginBottom: 12, borderBottom: `1px solid ${accent}30`, paddingBottom: 8}}>
          준비물 · READY
        </div>
        {items.map((it, i) => {
          const t0 = ROW0 + i * STAG;
          const p = interpolate(frame, [t0, t0 + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 12, padding: '5px 0', opacity: p, transform: `translateX(${interpolate(p, [0, 1], [-20, 0])}px)`}}>
              <span style={{fontFamily: mono, fontSize: 18, fontWeight: 700, color: accent, minWidth: 30}}>{String(i + 1).padStart(2, '0')}</span>
              <span style={{fontSize: 28, fontWeight: 800, color: '#fff'}}>{it}</span>
            </div>
          );
        })}
      </div>

      {/* 하단 작은 자막 — 우리가 통제 (자막 최대한 작게) */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 70, display: 'flex', justifyContent: 'center', opacity: capIn}}>
        <span
          style={{
            fontFamily: sans,
            fontSize: 34,
            fontWeight: 700,
            color: '#fff',
            padding: '8px 20px',
            background: 'rgba(0,0,0,0.42)',
            borderRadius: 6,
            letterSpacing: '-0.01em',
            textShadow: '0 2px 8px rgba(0,0,0,0.8)',
          }}
        >
          {caption}
        </span>
      </div>
    </AbsoluteFill>
  );
};
