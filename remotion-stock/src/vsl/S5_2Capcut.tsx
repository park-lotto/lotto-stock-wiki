/**
 * S5-2 (캡컷본 위에 얹기) — 2026-08-11
 *
 * 사장님이 캡컷으로 **확대·이동 편집 + 내레이션**까지 끝낸 영상(63.44s)을 주셨다.
 * 그래서 내가 할 일은 딱 셋이다: **자막 · 애니메이션 · 효과음.**
 *
 * ★배경을 건드리지 않는다. 사장님 지시: "백그라운드 천천히 움직이게 그런 거 하지 마라."
 *   화면은 이미 캡컷에서 움직인다. 여기에 또 줌을 걸면 두 개가 싸워서 멀미 난다.
 *   그래서 베이스는 손대지 않고 **위에만 얹는다**(스케일·패닝 전부 없음).
 *
 * 싱크: whisper로 뜬 s5-2 실측 시각을 그대로 쓴다(캡컷본 63.437s ≒ 원본 mp3 63.399s
 *       → 내레이션은 재배치되지 않았다). 오디오는 캡컷본 것을 그대로 살린다.
 */

import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile, OffthreadVideo,
  useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import { KineticWord, MINT, BG, FONT } from './motion';
import { S5_2_CUTS, S5_2_END, S5_FPS } from './S5_2';

const BASE = 'vsl/s5/capcut_s5_2.mp4';

/** 라벨 카드 — 말이 짚는 것을 글자로 한 번 더 박는다. 들어올 때만 움직이고 그 뒤엔 가만히 있는다 */
const Chip: React.FC<{ label: string }> = ({ label }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const p = spring({ frame: frame - 3, fps, config: { damping: 15, stiffness: 210 } });
  const out = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  return (
    <div style={{
      position: 'absolute', left: 54, top: 46,
      transform: `translateY(${interpolate(p, [0, 1], [-34, 0])}px)`,
      opacity: Math.min(p, out),
      padding: '14px 26px', borderRadius: 14,
      background: 'rgba(5,19,14,0.9)', border: `2px solid ${MINT}99`,
      boxShadow: `0 0 40px ${MINT}44`,
      fontFamily: FONT, fontWeight: 900, fontSize: 36, color: MINT,
      letterSpacing: '-0.5px',
    }}>{label}</div>
  );
};

/** 컷이 바뀌는 순간에만 도는 장치들 — 화면을 계속 흔들지 않는다 */
const CutFx: React.FC<{ hasSfx: boolean }> = ({ hasSfx }) => {
  const frame = useCurrentFrame();
  // 얇은 민트 선이 위에서 한 번 지나간다(0.4초). 전환을 알리되 배경은 안 건드린다
  const y = interpolate(frame, [0, 12], [-4, 104], { extrapolateRight: 'clamp' });
  const a = interpolate(frame, [0, 4, 12], [0, 0.5, 0], { extrapolateRight: 'clamp' });
  const flash = interpolate(frame, [0, 3], [hasSfx ? 0.1 : 0.06, 0], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ pointerEvents: 'none', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', left: 0, right: 0, top: `${y}%`, height: 3,
        background: MINT, opacity: a, boxShadow: `0 0 24px ${MINT}`,
      }} />
      <AbsoluteFill style={{ background: '#fff', opacity: flash }} />
    </AbsoluteFill>
  );
};

/** 하단 진행바 — 전체 길이 기준(씬 안에서 리셋되지 않는다) */
const Bar: React.FC<{ p: number }> = ({ p }) => (
  <div style={{
    position: 'absolute', left: 0, bottom: 0, height: 6,
    width: `${Math.max(0, Math.min(1, p)) * 100}%`,
    background: `linear-gradient(90deg, ${MINT}, ${MINT}88)`,
    boxShadow: `0 0 18px ${MINT}88`,
  }} />
);

const Overlay: React.FC<{ cut: typeof S5_2_CUTS[number] }> = ({ cut }) => (
  <AbsoluteFill>
    <CutFx hasSfx={!!cut.sfx?.length} />
    {cut.chip ? <Chip label={cut.chip} /> : null}
    {/* 자막 바닥 — 화면이 밝은 구간이 있어 이게 없으면 흰 글자가 사라진다 */}
    <AbsoluteFill style={{
      background: 'linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.5) 15%, rgba(0,0,0,0) 32%)',
      pointerEvents: 'none',
    }} />
    <KineticWord text={cut.text} size={58} perWord={1.3} />
    {(cut.sfx ?? []).map((s, i) => (
      <Sequence key={i} from={Math.round(s.at * S5_FPS)} layout="none">
        <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.28} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

export const S5_2Capcut: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: BG }}>
      {/* 베이스 — 사장님 캡컷본 그대로. 변형 없음, 소리도 이쪽 것을 쓴다 */}
      <OffthreadVideo
        src={staticFile(BASE)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />
      {S5_2_CUTS.map((cut, i) => {
        const from = Math.round(cut.t * S5_FPS);
        const next = S5_2_CUTS[i + 1]?.t ?? S5_2_END;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.max(1, Math.round((next - cut.t) * S5_FPS))}>
            <Overlay cut={cut} />
          </Sequence>
        );
      })}
      <Bar p={frame / durationInFrames} />
    </AbsoluteFill>
  );
};

export const S5_2CAPCUT_FRAMES = Math.round(63.43 * S5_FPS);
