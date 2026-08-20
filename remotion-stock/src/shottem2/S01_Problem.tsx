import React from 'react';
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
import { BgFx, Screen3D, BarCaption, Slam, Kinetic, Flash, Wipe, Grain, ZoomPunch, EASE } from './fx';
import { C, F } from './theme2';

/* 숏템하우스 2편 · 1단계 (0:00–0:33) — CF 톤
   원칙: 정지 화면 금지. 매 컷 (플래시 → 카메라 이동 → 글자 운동)이 겹친다. */

const B = {
  b1: 96,   // 0.00–3.19  쇼핑쇼츠 돈 된다고 / 다들 많이 들으셨죠
  b2: 92,   // 3.19–6.25  유튜브 영상들 여러 개 보셨을
  b3: 100,  // 6.25–9.59  무료 강의나 유료 강의도
  b4: 88,   // 9.59–12.52 만드는 법 / 이미 알고 계십니다
  b5: 119,  // 12.52–16.51 소재는 중국에서…자막 지우고
  b6: 108,  // 16.51–20.09 근데 지금 / 잘 되고 계십니까
  b7: 63,   // 20.09–22.20 저장해둔 레퍼런스는 수십 개인데
  b8: 59,   // 22.20–24.16 잘 안 되지 않던가요
  b9: 132,  // 24.16–28.56 문제는 몰라서가 아닙니다 / 진도가 안 나가는 거죠
  b10: 75,  // 28.56–31.06 하나 만드는 데 반나절
  b11: 106, // 31.06–34.60 그리고 내일 또 해야 하니까요
  b12: 129, // 34.60–38.90 수익이 언제 찍힐지 모르는 막연함 / 병목
  b13: 118, // 38.90–42.83 안 된다 힘들다 그런 얘기 그만하고
  b14: 113, // 42.83–46.60 지금부터 왜 숏템메이커는 되는지
};
const K = Object.keys(B) as (keyof typeof B)[];
const at = (n: number) => K.slice(0, n).reduce((a, k) => a + B[k], 0);
export const ST2_S01_FRAMES = at(K.length);

const BG_YT = 'shottem2/bg/bg_랭킹썰쇼핑.mp4';
const BG_RANK = 'shottem2/bg/bg_랭킹스크롤.mp4';
const BG_CAT = 'shottem2/bg/bg_랭킹카테고리.mp4';
const BG_INS = 'shottem2/bg/bg_랭킹인스타.mp4';
const BG_CUT = 'shottem2/bg/bg_캡컷타임라인.mp4';
const BG_CODE = 'shottem2/bg/bg_코드터미널.mp4';

/** 컷 껍데기 — 플래시 + 와이프가 항상 붙는다 */
const Cut: React.FC<{ children: React.ReactNode; flash?: string; wipe?: boolean }> = ({
  children, flash = '#fff', wipe = true,
}) => (
  <AbsoluteFill>
    <ZoomPunch>{children}</ZoomPunch>
    {wipe ? <Wipe /> : null}
    <Flash color={flash} />
  </AbsoluteFill>
);

/** 정석 단계가 카드로 날아와 쌓인다 */
const StepCards: React.FC<{ items: string[] }> = ({ items }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ display: 'flex', gap: 26 }}>
        {items.map((t, i) => {
          const d = i * 13;
          const p = spring({ frame: f - d, fps, config: { damping: 200, mass: 0.45 } });
          const rot = interpolate(p, [0, 1], [-14, i % 2 === 0 ? -2.5 : 2.5]);
          return (
            <div
              key={t}
              style={{
                opacity: p,
                transform:
                  'translateY(' + (1 - p) * 130 + 'px) rotate(' + rot + 'deg) scale(' + (0.8 + p * 0.2) + ')',
                width: 310, height: 350,
                borderRadius: 22,
                background: 'linear-gradient(160deg, rgba(16,14,26,0.92), rgba(8,8,16,0.86))',
                backdropFilter: 'blur(8px)',
                border: '1.5px solid rgba(250,204,21,0.55)',
                boxShadow: '0 40px 90px rgba(0,0,0,0.75), 0 0 60px rgba(250,204,21,0.10)',
                display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                padding: 28,
              }}
            >
              <div style={{ font: '900 84px ' + F.sans, color: C.gold, opacity: 0.85, lineHeight: 1 }}>
                {String(i + 1).padStart(2, '0')}
              </div>
              <div style={{ font: '900 40px/1.25 ' + F.sans, color: C.paper, whiteSpace: 'pre-line' }}>{t}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** 엔딩 — 로고가 빛을 뚫고 나온다 */
const EndTitle: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.7 } });
  const ring = interpolate(f, [8, 40], [0, 1], { extrapolateRight: 'clamp', easing: EASE.out });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      {/* 빛 폭발 */}
      <div
        style={{
          position: 'absolute', width: 1400 * ring, height: 1400 * ring, borderRadius: 999,
          background: 'radial-gradient(circle, rgba(250,204,21,0.22) 0%, rgba(250,204,21,0) 62%)',
          opacity: 1 - ring * 0.45,
        }}
      />
      <div style={{ textAlign: 'center', transform: 'scale(' + (0.92 + p * 0.08) + ')' }}>
        <div style={{ font: '800 28px ' + F.sans, color: C.gold, letterSpacing: 14, marginBottom: 22, opacity: p }}>
          지금부터
        </div>
        <Kinetic text={'왜 숏템메이커는'} size={122} accent="숏템메이커" stagger={1.5} />
        <Kinetic text={'되는지'} size={122} delay={10} stagger={1.5} />
        <div
          style={{
            marginTop: 36, display: 'inline-block', padding: '16px 46px',
            border: '2px solid ' + C.gold, borderRadius: 999,
            font: '800 34px ' + F.sans, color: C.gold,
            boxShadow: '0 0 60px rgba(250,204,21,0.35)',
            opacity: interpolate(f, [26, 44], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
          }}
        >
          보여드리겠습니다
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const S01_Problem: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: '#05060a' }}>
    <Audio src={staticFile('shottem2/voice/s01.mp3')} />

    {/* 1 — 훅 */}
    <Sequence durationInFrames={B.b1}>
      <Cut wipe={false}>
        <BgFx src={BG_YT} tint="monoWarm" speed={2.2} zoom={[1.28, 1.12]} drift={90} />
        <Slam text={'쇼핑쇼츠\n돈 된다고'} size={140} />
        <BarCaption text="다들 들으셨죠?" />
      </Cut>
    </Sequence>

    {/* 2 — 유튜브 검색결과 */}
    <Sequence from={at(1)} durationInFrames={B.b2}>
      <Cut>
        <BgFx src={BG_CAT} tint="mono" speed={2.0} startFrom={90} />
        <Screen3D src="shottem2/s01/1-1.mp4" label="YOUTUBE / 쇼핑쇼츠" w={1700} y={-60} tilt={5} speed={1.8} cropTop={0.10} />
        <BarCaption kicker="이미 보셨을 겁니다" text="영상만 수십 개" accent="수십 개" />
      </Cut>
    </Sequence>

    {/* 3 — 시청기록 */}
    <Sequence from={at(2)} durationInFrames={B.b3}>
      <Cut>
        <BgFx src={BG_INS} tint="mono" speed={2.0} startFrom={60} />
        <Screen3D src="shottem2/s01/1-2.mp4" label="WATCH HISTORY" w={1700} y={-60} tilt={-5} speed={1.8} cropTop={0.06} />
        <BarCaption text="무료 강의도, 유료 강의도" accent="유료 강의" />
      </Cut>
    </Sequence>

    {/* 4 — 큰 문장 */}
    <Sequence from={at(3)} durationInFrames={B.b4}>
      <Cut flash={C.gold}>
        <BgFx src={BG_RANK} tint="mono" speed={2.4} zoom={[1.35, 1.15]} />
        <Slam text={'만드는 법.\n이미 알고 계십니다'} size={116} />
      </Cut>
    </Sequence>

    {/* 5 — 정석 4단계 카드가 날아와 쌓임 */}
    <Sequence from={at(4)} durationInFrames={B.b5}>
      <Cut>
        <BgFx src={BG_CUT} tint="mono" speed={1.8} dim={0.85} />
        <StepCards items={['소재는\n중국에서', '원고\n쓰고', '성우\n입히고', '자막\n지우고']} />
      </Cut>
    </Sequence>

    {/* 6 — 질문 한 방 (빨강) */}
    <Sequence from={at(5)} durationInFrames={B.b6}>
      <Cut flash={C.red}>
        <BgFx src={BG_RANK} tint="mono" speed={2.6} startFrom={200} zoom={[1.4, 1.18]} />
        <Slam text={'근데 지금,\n잘 되고 계십니까?'} size={118} />
      </Cut>
    </Sequence>

    {/* 7 — 빽빽한 저장 목록 */}
    <Sequence from={at(6)} durationInFrames={B.b7}>
      <Cut>
        <BgFx src={BG_RANK} tint="mono" speed={2.0} startFrom={320} />
        <Screen3D src="shottem2/s01/1-5.mp4" label="SAVED / 60+" w={1740} y={-50} tilt={4} speed={2.0} cropTop={0.06} />
        <BarCaption text="레퍼런스는 수십 개인데" accent="수십 개" />
      </Cut>
    </Sequence>

    {/* 8 — 비어 있는 내 채널 */}
    <Sequence from={at(7)} durationInFrames={B.b8}>
      <Cut flash={C.red}>
        <BgFx src={BG_INS} tint="mono" speed={2.0} startFrom={200} />
        <Screen3D src="shottem2/s01/1-6_내채널.mp4" label="MY CHANNEL" w={1740} y={-50} tilt={-4} speed={1.6} cropTop={0.08} />
        <BarCaption text="잘 안 되지 않던가요?" accent="안 되지" />
      </Cut>
    </Sequence>

    {/* 9 — 문제는 몰라서가 아닙니다 */}
    <Sequence from={at(8)} durationInFrames={B.b9}>
      <Cut flash={C.gold}>
        <BgFx src={BG_CODE} tint="monoWarm" speed={2.2} zoom={[1.3, 1.1]} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Kinetic text={'문제는'} size={78} color={C.dim} stagger={2} />
          <Kinetic text={'몰라서가 아닙니다'} size={128} delay={8} stagger={1.8} />
        </AbsoluteFill>
        <BarCaption text="알아도 진도가 안 나가는 거죠" />
      </Cut>
    </Sequence>

    {/* 10 — 반나절 */}
    <Sequence from={at(9)} durationInFrames={B.b10}>
      <Cut>
        <BgFx src={BG_CUT} tint="mono" speed={2.4} startFrom={200} zoom={[1.4, 1.16]} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Kinetic text={'한 편에 반나절'} size={150} accent="반나절" stagger={1.6} />
          <div style={{ height: 24 }} />
          <Kinetic text={'그리고 내일 또'} size={72} color={C.dim} delay={26} stagger={1.6} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 11 — 그리고 내일 또 */}
    <Sequence from={at(10)} durationInFrames={B.b11}>
      <Cut>
        <BgFx src={BG_CUT} tint="mono" speed={2.6} startFrom={330} zoom={[1.42, 1.14]} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Kinetic text={'그리고'} size={74} color={C.dim} stagger={2} />
          <Kinetic text={'내일 또'} size={148} accent="또" delay={10} stagger={2} />
        </AbsoluteFill>
        <BarCaption text="해야 하니까요" />
      </Cut>
    </Sequence>

    {/* 12 — 막연함 = 병목 */}
    <Sequence from={at(11)} durationInFrames={B.b12}>
      <Cut flash={C.red}>
        <BgFx src={BG_CUT} tint="mono" speed={2.0} startFrom={480} dim={0.8} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Kinetic text={'수익이 언제 찍힐지'} size={82} color={C.dim} stagger={1.4} />
          <Kinetic text={'모르는 막연함'} size={132} accent="막연함" delay={14} stagger={1.6} />
        </AbsoluteFill>
        <BarCaption kicker="그게" text="병목이고 포인트입니다" accent="병목" />
      </Cut>
    </Sequence>

    {/* 13 — 그런 얘기 그만하고 */}
    <Sequence from={at(12)} durationInFrames={B.b13}>
      <Cut>
        <BgFx src={BG_RANK} tint="mono" speed={2.8} startFrom={520} dim={0.5} zoom={[1.45, 1.1]} blur={9} />
        <Slam text={'안 된다, 힘들다.\n그런 얘기 그만하고'} size={104} />
      </Cut>
    </Sequence>

    {/* 14 — 타이틀 */}
    <Sequence from={at(13)} durationInFrames={B.b14}>
      <Cut flash={C.gold} wipe={false}>
        <BgFx src={BG_RANK} tint="amber" speed={2.0} startFrom={640} zoom={[1.22, 1.05]} />
        <EndTitle />
      </Cut>
    </Sequence>

    <Grain opacity={0.10} />
  </AbsoluteFill>
);
