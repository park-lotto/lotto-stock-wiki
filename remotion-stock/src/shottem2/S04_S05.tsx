import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import { BgFx, BarCaption, Slam, Kinetic, Flash, Wipe, Grain, ZoomPunch, Scrim, EASE } from './fx';
import { C, F } from './theme2';

/* 4단계 해결의 방향 (15.57초) · 5단계 다른 대안의 한계 (44.93초)
   둘 다 사장님 촬영 없음 — 도식이 본체다.
   ⛔ 경쟁 프로그램 화면·이름 금지라서, 5단계의 파이프라인 도식이 그 자리를 대신한다. */

const BG_CODE = 'shottem2/bg/bg_코드터미널.mp4';
const BG_RANK = 'shottem2/bg/bg_랭킹스크롤.mp4';
const BG_CUT = 'shottem2/bg/bg_캡컷타임라인.mp4';

const Cut: React.FC<{ children: React.ReactNode; flash?: string; wipe?: boolean }> = ({
  children, flash = '#fff', wipe = true,
}) => (
  <AbsoluteFill>
    <ZoomPunch>{children}</ZoomPunch>
    {wipe ? <Wipe /> : null}
    <Flash color={flash} />
  </AbsoluteFill>
);

/* ══════════════ 4단계 ══════════════ */

const S4: [number, number][] = [[0, 53], [53, 78], [131, 125], [256, 126], [382, 85]];
export const ST2_S04_FRAMES = 467;
const A = (i: number) => ({ from: S4[i][0], durationInFrames: S4[i][1] });

/** 저울 — 강의 쪽이 올라가고 도구 쪽으로 기운다 */
const Scale: React.FC<{ tiltTo: number }> = ({ tiltTo }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 14, mass: 1.1 } });
  const deg = interpolate(p, [0, 1], [0, tiltTo]);
  const armY = (d: number) => Math.tan((deg * Math.PI) / 180) * d;
  const Pan: React.FC<{ side: -1 | 1; label: string; sub: string; on: boolean }> = ({
    side, label, sub, on,
  }) => (
    <div
      style={{
        position: 'absolute', left: '50%', top: '50%',
        transform:
          'translate(-50%,-50%) translate(' + side * 420 + 'px, ' + (armY(side * 420) + 130) + 'px)',
        width: 520, padding: '30px 34px', borderRadius: 18, textAlign: 'center',
        background: on ? 'rgba(250,204,21,0.14)' : 'rgba(10,10,16,0.85)',
        border: '2px solid ' + (on ? C.gold : 'rgba(255,255,255,0.18)'),
        boxShadow: on ? '0 0 70px rgba(250,204,21,0.35)' : '0 30px 70px rgba(0,0,0,0.7)',
        opacity: on ? 1 : 0.55,
      }}
    >
      <div style={{ font: '900 62px ' + F.sans, color: on ? C.gold : C.dim }}>{label}</div>
      <div style={{ marginTop: 8, font: '700 30px ' + F.sans, color: on ? C.paper : C.dim }}>{sub}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={50} strength={0.86} />
      <div style={{ position: 'absolute', width: '100%', height: '100%' }}>
        {/* 저울대 */}
        <div
          style={{
            position: 'absolute', left: '50%', top: '50%',
            transform: 'translate(-50%,-50%) rotate(' + deg + 'deg)',
            width: 900, height: 8, borderRadius: 4,
            background: 'linear-gradient(90deg, rgba(255,255,255,0.3), ' + C.gold + ')',
            boxShadow: '0 0 30px rgba(250,204,21,0.4)',
          }}
        />
        {/* 기둥 */}
        <div
          style={{
            position: 'absolute', left: '50%', top: '50%',
            transform: 'translate(-50%,0)', width: 10, height: 150,
            background: 'rgba(255,255,255,0.28)',
          }}
        />
        <Pan side={-1} label="강의 · 정보" sub="이미 다 나와 있다" on={false} />
        <Pan side={1} label="도구" sub="매일 할 수 있게" on={deg > 3} />
      </div>
    </AbsoluteFill>
  );
};

export const S04_Direction: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: '#05060a' }}>
    <Audio src={staticFile('shottem2/voice/s04.mp3')} />

    <Sequence {...A(0)}>
      <Cut wipe={false}>
        <BgFx src={BG_CODE} tint="monoWarm" speed={2.4} zoom={[1.3, 1.12]} />
        <Slam text={'그래서 결론은'} size={124} />
      </Cut>
    </Sequence>

    <Sequence {...A(1)}>
      <Cut flash={C.red}>
        <BgFx src={BG_RANK} tint="mono" speed={2.6} startFrom={200} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={44} strength={0.88} />
          <Kinetic text={'지금 필요한 건'} size={70} color={C.dim} stagger={1.4} />
          <div style={{ height: 14 }} />
          <Kinetic text={'더 좋은 강의가 아닙니다'} size={104} accent="아닙니다" delay={12} stagger={1.4} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    <Sequence {...A(2)}>
      <Cut>
        <BgFx src={BG_CODE} tint="mono" speed={2.2} startFrom={300} />
        <Scale tiltTo={0} />
        <BarCaption text="방법은 이미 다 나와 있습니다" accent="이미 다" />
      </Cut>
    </Sequence>

    <Sequence {...A(3)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_CODE} tint="amber" speed={2.0} startFrom={420} />
        <Scale tiltTo={11} />
        <BarCaption kicker="필요한 건" text="매일 할 수 있게 만드는 도구" accent="도구" />
      </Cut>
    </Sequence>

    <Sequence {...A(4)}>
      <Cut wipe={false}>
        <BgFx src={BG_CODE} tint="amber" speed={2.4} startFrom={540} zoom={[1.3, 1.1]} />
        <Slam text={'배우는 문제가 아니라\n실행 시간 문제입니다'} size={92} />
      </Cut>
    </Sequence>

    <Grain opacity={0.1} />
  </AbsoluteFill>
);

/* ══════════════ 5단계 ══════════════ */

const S5: [number, number][] = [
  [0, 131], [131, 105], [236, 74], [310, 140], [450, 169],
  [619, 241], [860, 84], [944, 124], [1068, 137], [1205, 143],
];
export const ST2_S05_FRAMES = 1348;
const B = (i: number) => ({ from: S5[i][0], durationInFrames: S5[i][1] });

const STEPS = ['소재', '원고', '성우', '자막제거', '편집', '자막', '썸네일', '업로드'];

/** 파이프라인 — 이 영상에서 제일 중요한 도식.
 *  mode: 'idle' 전체 회색 / 'partial' 일부만 초록 / 'gap' 이음매가 빨갛게 벌어짐 / 'one' 한 줄로 이어짐 */
const Pipeline: React.FC<{
  mode: 'idle' | 'partial' | 'gap' | 'one';
  green?: number[];
  shuttle?: boolean;
}> = ({ mode, green = [], shuttle = false }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const W = 196;
  const GAP = mode === 'gap' ? 42 : mode === 'one' ? 6 : 22;
  const gapS = spring({ frame: f, fps, config: { damping: 200, mass: 0.6 } });
  const gapNow = interpolate(gapS, [0, 1], [22, GAP]);

  // 왕복하는 커서 — 자동화 구간 사이를 사람이 오간다
  const t = (f % 70) / 70;
  const bounce = Math.sin(t * Math.PI * 2);
  const cursorX = interpolate(bounce, [-1, 1], [-420, 420]);

  const oneLine = spring({ frame: f - 20, fps, config: { damping: 200, mass: 0.7 } });

  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={52} strength={0.9} />
      <div style={{ position: 'relative' }}>
        {/* 한 줄 레일 — 'one'일 때 관통해 흐른다 */}
        {mode === 'one' ? (
          <div
            style={{
              position: 'absolute', top: '50%', left: 0,
              width: (W + 6) * STEPS.length * oneLine, height: 10,
              transform: 'translateY(-50%)', borderRadius: 5,
              background: 'linear-gradient(90deg, ' + C.gold + ', rgba(74,222,128,0.9))',
              boxShadow: '0 0 44px rgba(250,204,21,0.6)',
            }}
          />
        ) : null}

        <div style={{ display: 'flex', gap: gapNow, position: 'relative' }}>
          {STEPS.map((s, i) => {
            const on = mode === 'one' || (mode !== 'idle' && green.includes(i));
            const p = spring({ frame: f - i * 4, fps, config: { damping: 200, mass: 0.45 } });
            return (
              <div
                key={s}
                style={{
                  width: W, height: 128, borderRadius: 12,
                  opacity: p,
                  transform: 'translateY(' + (1 - p) * 40 + 'px)',
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center', gap: 8,
                  background: on ? 'rgba(74,222,128,0.16)' : 'rgba(12,12,20,0.9)',
                  border: '2px solid ' + (on ? C.green : 'rgba(255,255,255,0.16)'),
                  boxShadow: on ? '0 0 44px rgba(74,222,128,0.28)' : '0 18px 44px rgba(0,0,0,0.6)',
                }}
              >
                <div style={{ font: '700 20px ' + F.mono, color: on ? C.green : C.dim }}>
                  {String(i + 1).padStart(2, '0')}
                </div>
                <div style={{ font: '800 30px ' + F.sans, color: on ? C.paper : C.dim }}>{s}</div>
              </div>
            );
          })}

          {/* 이음매의 빨간 틈 */}
          {mode === 'gap'
            ? [1, 3, 5].map((i) => (
                <div
                  key={i}
                  style={{
                    position: 'absolute', top: '50%', left: (W + gapNow) * i - gapNow / 2 - 3,
                    transform: 'translateY(-50%)',
                    width: 6, height: 150, borderRadius: 3,
                    background: C.red,
                    boxShadow: '0 0 30px rgba(248,113,113,0.9)',
                    opacity: 0.55 + Math.abs(Math.sin(f * 0.2)) * 0.45,
                  }}
                />
              ))
            : null}
        </div>

        {/* 왕복 커서 */}
        {shuttle ? (
          <div
            style={{
              position: 'absolute', top: -78, left: '50%',
              transform: 'translateX(' + (cursorX - 30) + 'px)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
            }}
          >
            <div
              style={{
                padding: '8px 18px', borderRadius: 999,
                background: C.red, color: '#fff',
                font: '800 24px ' + F.sans,
                boxShadow: '0 0 34px rgba(248,113,113,0.8)',
              }}
            >
              나
            </div>
            <div style={{ font: '900 28px ' + F.sans, color: C.red }}>↓</div>
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

export const S05_Alternatives: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: '#05060a' }}>
    <Audio src={staticFile('shottem2/voice/s05.mp3')} />

    {/* 0 — 도구를 쓰면 되지 않느냐 */}
    <Sequence {...B(0)}>
      <Cut wipe={false}>
        <BgFx src={BG_CODE} tint="mono" speed={2.2} zoom={[1.3, 1.12]} />
        <Slam text={'도구를 쓰면\n되지 않느냐'} size={112} />
        <BarCaption text="맞습니다. 저도 여러 개 써봤습니다" />
      </Cut>
    </Sequence>

    {/* 1 — 구조 얘기입니다 */}
    <Sequence {...B(1)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_RANK} tint="mono" speed={2.4} startFrom={200} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={44} strength={0.88} />
          <Kinetic text={'어디가 나쁘다는 게 아니라'} size={68} color={C.dim} stagger={1.3} />
          <div style={{ height: 16 }} />
          <Kinetic text={'구조 얘기입니다'} size={116} accent="구조" delay={14} stagger={1.5} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 2 — 한 토막씩만 자동화 */}
    <Sequence {...B(2)}>
      <Cut>
        <BgFx src={BG_CODE} tint="mono" speed={2.2} startFrom={300} dim={0.7} />
        <Pipeline mode="idle" />
        <BarCaption text="대부분 한 토막씩만 자동화합니다" accent="한 토막씩만" />
      </Cut>
    </Sequence>

    {/* 3 — 원고만 / 편집만 / 소재만 */}
    <Sequence {...B(3)}>
      <Cut flash={C.green}>
        <BgFx src={BG_CODE} tint="mono" speed={2.0} startFrom={380} dim={0.7} />
        <Pipeline mode="partial" green={[1, 4]} />
        <BarCaption text="원고만 · 편집만 · 소재만" accent="만" />
      </Cut>
    </Sequence>

    {/* 4 — 그 사이를 내가 왔다 갔다 */}
    <Sequence {...B(4)}>
      <Cut flash={C.red}>
        <BgFx src={BG_CUT} tint="mono" speed={2.4} startFrom={200} dim={0.7} />
        <Pipeline mode="partial" green={[1, 4]} shuttle />
        <BarCaption kicker="자동화된 구간 사이를" text="제가 왔다 갔다 합니다" accent="왔다 갔다" />
      </Cut>
    </Sequence>

    {/* 5 — 여기서 뽑고 저기서 만들고 (틈이 벌어진다) */}
    <Sequence {...B(5)}>
      <Cut>
        <BgFx src={BG_CUT} tint="mono" speed={2.0} startFrom={400} dim={0.65} />
        <Pipeline mode="gap" green={[1, 4]} shuttle />
        <BarCaption text="원고는 여기, 성우는 저기, 편집은 또 다른 데" accent="또" />
      </Cut>
    </Sequence>

    {/* 6 — 왕복이 그대로 남는다 */}
    <Sequence {...B(6)}>
      <Cut flash={C.red} wipe={false}>
        <BgFx src={BG_CUT} tint="mono" speed={2.8} startFrom={600} zoom={[1.42, 1.16]} />
        <Slam text={'왕복이\n그대로 남습니다'} size={116} color={C.paper} />
      </Cut>
    </Sequence>

    {/* 7 — 자동화를 써도 시간이 안 줄어든다 */}
    <Sequence {...B(7)}>
      <Cut>
        <BgFx src={BG_RANK} tint="mono" speed={2.4} startFrom={500} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={46} strength={0.88} />
          <Kinetic text={'자동화를 써도'} size={70} color={C.dim} stagger={1.4} />
          <div style={{ height: 14 }} />
          <Kinetic text={'시간이 안 줄어듭니다'} size={110} accent="안 줄어듭니다" delay={14} stagger={1.4} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 8 — 이음매가 느리면 전체는 안 빨라진다 */}
    <Sequence {...B(8)}>
      <Cut flash={C.red}>
        <BgFx src={BG_CUT} tint="mono" speed={2.2} startFrom={700} dim={0.7} />
        <Pipeline mode="gap" green={[1, 4]} />
        <BarCaption kicker="부분을 아무리 빠르게 해도" text="이음매가 느리면 전체는 그대로" accent="이음매" />
      </Cut>
    </Sequence>

    {/* 9 — 답은 하나, 한 줄로 이어져 있어야 한다 */}
    <Sequence {...B(9)}>
      <Cut flash={C.gold} wipe={false}>
        <BgFx src={BG_CODE} tint="amber" speed={2.0} startFrom={620} dim={0.8} />
        <Pipeline mode="one" />
        <BarCaption kicker="답은 하나" text="처음부터 끝까지 한 줄로" accent="한 줄로" />
      </Cut>
    </Sequence>

    <Grain opacity={0.1} />
  </AbsoluteFill>
);
