import {AbsoluteFill, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveLilyPreset, LilyPreset} from './lily_presets';

// 릴리리아(by. Lily) 자막. text 만 바꾸면 프리셋 스타일(색·글로우·외곽선·반짝이·등장)로 그려진다.
// highlight 로 한 단어만 강조색. drawtext 로 못 하던 글로우·반짝이를 CSS/SVG 로 재현한다.
export type LilySubProps = {
  text: string;
  highlight?: string;      // 이 단어만 강조색(원본의 "행복"처럼)
  preset?: string | LilyPreset;
  position?: 'top' | 'mid' | 'bottom';
};

const Star: React.FC<{x: number; y: number; s: number; phase: number}> = ({x, y, s, phase}) => {
  const frame = useCurrentFrame();
  const tw = 0.55 + 0.45 * Math.abs(Math.sin((frame / 9) + phase));
  return (
    <div style={{position: 'absolute', left: x, top: y, transform: `scale(${s * tw})`, opacity: tw}}>
      <svg width="40" height="40" viewBox="0 0 40 40">
        <path d="M20 2 L23 17 L38 20 L23 23 L20 38 L17 23 L2 20 L17 17 Z" fill="#fff" />
      </svg>
    </div>
  );
};

export const LilySub: React.FC<LilySubProps> = ({text, highlight, preset, position = 'mid'}) => {
  const p = resolveLilyPreset(preset);
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();

  const enter = spring({frame, fps, config: {damping: 12, stiffness: 200, mass: 0.7}});
  const scale = p.anim === 'pop' ? interpolate(enter, [0, 1], [0.6, 1]) : 1;
  const bounce = p.anim === 'bounce' ? interpolate(enter, [0, 1], [40, 0]) : 0;
  const opacity = interpolate(frame, [0, 5], [0, 1], {extrapolateRight: 'clamp'});

  // 글로우 = 외곽선 위에 여러 겹 번짐. 외곽선 = paintOrder 로 획을 글자 뒤에.
  const glowShadow = [
    `0 0 10px ${p.glow}`,
    `0 0 22px ${p.glow}`,
    `0 0 40px ${p.glow}`,
    '0 4px 10px rgba(0,0,0,0.45)',
  ].join(', ');

  const marginTop = position === 'top' ? '12%' : position === 'bottom' ? '74%' : '42%';
  // 화면 폭을 넘으면 자동 축소(원본은 한 줄이 화면 안에 딱 맞는다). 대략 글자당 폭으로 추정.
  const estW = text.length * p.fontSize * 0.62 + 160; // 글자폭 + 반짝이 여백
  const fit = Math.min(1, (width * 0.9) / estW);

  const parts: {t: string; hl: boolean}[] = [];
  if (highlight && text.includes(highlight)) {
    const [a, b] = text.split(highlight);
    if (a) parts.push({t: a, hl: false});
    parts.push({t: highlight, hl: true});
    if (b) parts.push({t: b, hl: false});
  } else {
    parts.push({t: text, hl: false});
  }

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', opacity, transform: `translateY(${bounce}px) scale(${scale * fit})`}}>
        {/* 왼쪽 반짝이 — 글자 바깥 */}
        {p.sparkle && (
          <div style={{position: 'absolute', right: '100%', top: '50%', transform: 'translateY(-50%)', width: 90, height: 120}}>
            <Star x={40} y={6} s={0.95} phase={0} />
            <Star x={12} y={62} s={0.55} phase={2.2} />
          </div>
        )}
        <div
          style={{
            fontFamily: `"${p.fontFamily}", "Malgun Gothic", sans-serif`,
            fontWeight: 900,
            fontSize: p.fontSize,
            letterSpacing: '-0.02em',
            whiteSpace: 'nowrap',
            transform: p.italic ? `skewX(-${p.italic}deg)` : undefined,
            paintOrder: 'stroke fill',
            textShadow: glowShadow,
          }}
        >
          {parts.map((seg, i) => (
            // 강조어는 대비를 뒤집어 도드라지게: 핑크 글자 + 흰 외곽선(+살짝 크게).
            // 일반은 흰 글자 + 핑크 외곽선. 굵은 폰트라 강조어를 같은 색조로 두면 뭉쳐 안 보인다.
            <span
              key={i}
              style={{
                color: seg.hl ? p.hlColor : p.fillColor,
                WebkitTextStroke: seg.hl
                  ? `${p.strokeW + 1}px ${p.hlStroke || '#ffffff'}`
                  : `${p.strokeW}px ${p.strokeColor}`,
                fontSize: seg.hl ? '1.1em' : undefined,
                display: 'inline-block',
                margin: seg.hl ? '0 0.12em' : undefined,
              }}
            >
              {seg.t}
            </span>
          ))}
        </div>
        {/* 오른쪽 반짝이 — 글자 바깥 */}
        {p.sparkle && (
          <div style={{position: 'absolute', left: '100%', top: '50%', transform: 'translateY(-50%)', width: 90, height: 120}}>
            <Star x={10} y={2} s={0.95} phase={1.1} />
            <Star x={40} y={64} s={0.55} phase={3.3} />
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
