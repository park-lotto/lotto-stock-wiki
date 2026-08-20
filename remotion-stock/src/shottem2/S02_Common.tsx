import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig,
  interpolate, spring,
} from 'remotion';
import {
  BgFx, Screen3D, BarCaption, Slam, Kinetic, Flash, Wipe, Grain, ZoomPunch, Scrim, CountUp, EASE,
} from './fx';
import { C, F } from './theme2';

/* 숏템하우스 2편 · 2단계 일반적인 해결책 (82.44초)
   타임코드 = tools/shottem2_timing.py 가 TTS 실측으로 뽑은 값
   → src/shottem2/timing/s02.json 이 원본. 여기 숫자는 그 파생물. */

const SEG: [number, number][] = [
  [0, 71], [71, 165], [236, 132], [368, 189], [557, 174], [731, 86], [817, 141],
  [958, 156], [1114, 169], [1283, 199], [1482, 263], [1745, 73], [1818, 117],
  [1935, 133], [2068, 184], [2252, 123], [2375, 98],
];
export const ST2_S02_FRAMES = 2473;

const BG_YT = 'shottem2/bg/bg_랭킹썰쇼핑.mp4';
const BG_RANK = 'shottem2/bg/bg_랭킹스크롤.mp4';
const BG_CAT = 'shottem2/bg/bg_랭킹카테고리.mp4';
const BG_INS = 'shottem2/bg/bg_랭킹인스타.mp4';
const BG_CODE = 'shottem2/bg/bg_코드터미널.mp4';
const REC1 = 'shottem2/s02/2-1.mp4';
const REC2 = 'shottem2/s02/2-2.mp4';

const Cut: React.FC<{ children: React.ReactNode; flash?: string; wipe?: boolean }> = ({
  children, flash = '#fff', wipe = true,
}) => (
  <AbsoluteFill>
    <ZoomPunch>{children}</ZoomPunch>
    {wipe ? <Wipe /> : null}
    <Flash color={flash} />
  </AbsoluteFill>
);

/** 정석 N단계 — 번호가 크게 박히고 제목이 따라 나온다 */
const StepBig: React.FC<{ no: number; title: string; note?: string }> = ({ no, title, note }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.5 } });
  const numScale = interpolate(f, [0, 8], [1.6, 1], { extrapolateRight: 'clamp', easing: EASE.slam });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={46} strength={0.85} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 46 }}>
        <div
          style={{
            font: '900 250px ' + F.sans, color: C.gold, lineHeight: 0.9,
            transform: 'scale(' + numScale + ')', opacity: p,
            textShadow: '0 0 70px rgba(250,204,21,0.5), 0 10px 30px rgba(0,0,0,1)',
            WebkitTextStroke: '3px rgba(0,0,0,0.5)',
          }}
        >
          {String(no).padStart(2, '0')}
        </div>
        <div style={{ borderLeft: '3px solid rgba(250,204,21,0.5)', paddingLeft: 40, height: 200, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <Kinetic text={title} size={74} align="left" stagger={1.5} delay={5} />
          {note ? (
            <div
              style={{
                marginTop: 16, font: '700 36px ' + F.sans, color: C.dim,
                opacity: interpolate(f, [20, 34], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
              }}
            >
              {note}
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** ❌ / ⭕ 훅 문장 비교 */
const HookLine: React.FC<{ bad?: boolean; label: string; quote: string }> = ({ bad, label, quote }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.5 } });
  const col = bad ? C.red : C.green;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={44} strength={0.88} />
      <div style={{ textAlign: 'center', transform: 'translateY(' + (1 - p) * 40 + 'px)', opacity: p }}>
        <div
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 16, marginBottom: 28,
            padding: '10px 30px', borderRadius: 999,
            border: '2px solid ' + col, color: col,
            font: '800 34px ' + F.sans,
            boxShadow: '0 0 46px ' + (bad ? 'rgba(248,113,113,0.4)' : 'rgba(74,222,128,0.4)'),
          }}
        >
          <span style={{ font: '900 40px ' + F.sans }}>{bad ? '✕' : '○'}</span>
          {label}
        </div>
        <Kinetic text={quote} size={82} stagger={1.3} delay={8} />
      </div>
    </AbsoluteFill>
  );
};

/** 5분류 칩이 순차로 튀어나온다 */
const ChipRow: React.FC<{ items: string[] }> = ({ items }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={40} strength={0.85} />
      <div style={{ textAlign: 'center' }}>
        <Kinetic text={'구조는 다섯 개'} size={92} accent="다섯" stagger={1.5} />
        <div style={{ display: 'flex', gap: 18, marginTop: 44, justifyContent: 'center' }}>
          {items.map((t, i) => {
            const p = spring({ frame: f - 26 - i * 9, fps, config: { damping: 200, mass: 0.4 } });
            return (
              <div
                key={t}
                style={{
                  opacity: p,
                  transform: 'translateY(' + (1 - p) * 44 + 'px) scale(' + (0.85 + p * 0.15) + ')',
                  padding: '20px 30px', borderRadius: 14,
                  background: 'rgba(250,204,21,0.10)',
                  border: '1.5px solid rgba(250,204,21,0.55)',
                  font: '800 40px ' + F.sans, color: C.paper,
                  boxShadow: '0 20px 50px rgba(0,0,0,0.7)',
                }}
              >
                {t}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** 오용형 실측 막대 — 어두운 패널 위에서 차오른다 */
const RankBars: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rows = [
    { k: '오용형 — 원래 용도를 뒤집는다', v: 92, pct: 46, hi: true },
    { k: '기타(미분류)', v: 76, pct: 38, hi: false },
    { k: '은폐형', v: 15, pct: 7, hi: false },
    { k: '권위자형', v: 12, pct: 6, hi: false },
    { k: '나열형', v: 4, pct: 2, hi: false },
  ];
  const BAR = 620; // 46%가 이 폭을 꽉 채운다
  const panel = spring({ frame: f, fps, config: { damping: 200, mass: 0.5 } });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div
        style={{
          width: 1500, padding: '46px 56px', borderRadius: 20,
          background: 'rgba(6,7,12,0.90)',
          border: '1px solid rgba(250,204,21,0.30)',
          boxShadow: '0 50px 120px rgba(0,0,0,0.85)',
          opacity: panel,
          transform: 'translateY(' + (1 - panel) * 40 + 'px)',
        }}
      >
        <div style={{ font: '800 26px ' + F.sans, color: C.gold, letterSpacing: 6, marginBottom: 24 }}>
          자체 분석 · 조회수 상위 200편
        </div>
        {rows.map((r, i) => {
          const p = spring({ frame: f - 10 - i * 7, fps, config: { damping: 200, mass: 0.5 } });
          const w = interpolate(p, [0, 1], [0, (r.pct / 46) * BAR]);
          return (
            <div
              key={r.k}
              style={{
                display: 'flex', alignItems: 'center', gap: 22, opacity: p,
                marginBottom: r.hi ? 18 : 10,
                paddingBottom: r.hi ? 18 : 0,
                borderBottom: r.hi ? '1px solid rgba(250,204,21,0.28)' : 'none',
              }}
            >
              <div
                style={{
                  width: 560, whiteSpace: 'nowrap', overflow: 'hidden',
                  font: (r.hi ? '900 40px ' : '700 30px ') + F.sans,
                  color: r.hi ? C.gold : C.dim,
                }}
              >
                {r.k}
              </div>
              <div style={{ width: BAR, display: 'flex', alignItems: 'center' }}>
                <div
                  style={{
                    height: r.hi ? 26 : 14, width: w, borderRadius: 4,
                    background: r.hi ? C.gold : 'rgba(255,255,255,0.26)',
                    boxShadow: r.hi ? '0 0 30px rgba(250,204,21,0.65)' : 'none',
                  }}
                />
              </div>
              <div
                style={{
                  width: 150, textAlign: 'right', whiteSpace: 'nowrap',
                  font: (r.hi ? '900 40px ' : '700 28px ') + F.sans,
                  color: r.hi ? C.gold : C.dim,
                }}
              >
                {r.v}편 · {r.pct}%
              </div>
            </div>
          );
        })}
        <div
          style={{
            marginTop: 22, font: '800 34px ' + F.sans, color: C.green,
            opacity: interpolate(f, [70, 92], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
          }}
        >
          천만 넘긴 것들은 거의 다 여기였습니다
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** 8단계 전체 그리드 — 마지막에 한 번에 보여준다 */
const AllSteps: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const items = ['원고 구조 분석', '내 제품 원고', '소재 영상 수집', '자막 제거',
    '성우 입히기', '편집·자막', '썸네일·훅', '해시태그·업로드'];
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={50} strength={0.88} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 330px)', gap: 18 }}>
        {items.map((t, i) => {
          const p = spring({ frame: f - i * 3, fps, config: { damping: 200, mass: 0.4 } });
          return (
            <div
              key={t}
              style={{
                opacity: p, transform: 'scale(' + (0.86 + p * 0.14) + ')',
                padding: '22px 26px', borderRadius: 14,
                background: 'rgba(12,12,20,0.88)',
                border: '1.5px solid rgba(250,204,21,0.42)',
                display: 'flex', alignItems: 'center', gap: 18,
              }}
            >
              <span style={{ font: '900 40px ' + F.sans, color: C.gold }}>{i + 1}</span>
              <span style={{ font: '800 30px ' + F.sans, color: C.paper }}>{t}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const S = (i: number) => ({ from: SEG[i][0], durationInFrames: SEG[i][1] });

export const S02_Common: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: '#05060a' }}>
    <Audio src={staticFile('shottem2/voice/s02.mp3')} />

    {/* 0 — 방법 자체는 이미 공개돼 있습니다 */}
    <Sequence {...S(0)}>
      <Cut wipe={false}>
        <BgFx src={BG_YT} tint="mono" speed={2.4} zoom={[1.3, 1.12]} />
        <Slam text={'방법 자체는\n이미 공개돼 있습니다'} size={112} />
      </Cut>
    </Sequence>

    {/* 1 — 유튜브에 치면 잘 알려주는 분들 많습니다 */}
    <Sequence {...S(1)}>
      <Cut>
        <BgFx src={BG_CAT} tint="mono" speed={2.0} startFrom={60} />
        <Screen3D src={REC1} label="YOUTUBE / 쇼핑쇼츠 만드는 법" w={1700} y={-60} tilt={5} speed={1.3} cropTop={0.05} />
        <BarCaption kicker="저도 다 봤습니다" text="잘 알려주는 분들 많습니다" accent="많습니다" />
      </Cut>
    </Sequence>

    {/* 2 — 숨어 있는 비밀은 없다 */}
    <Sequence {...S(2)}>
      <Cut>
        <BgFx src={BG_INS} tint="mono" speed={2.0} startFrom={120} />
        <Screen3D src={REC2} label="검색결과" w={1700} y={-60} tilt={-5} speed={1.3} cropTop={0.05} />
        <BarCaption text="숨어 있는 비밀은 없습니다" accent="없습니다" />
      </Cut>
    </Sequence>

    {/* 3 — 순서 그대로 알려드립니다 */}
    <Sequence {...S(3)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_RANK} tint="monoWarm" speed={2.4} zoom={[1.34, 1.12]} />
        <Slam sub="핵심 강의들에서 나오는" text={'순서 그대로\n말씀드리겠습니다'} size={104} />
        <BarCaption text="오늘 이거 하나만 가져가셔도 됩니다" accent="하나만" />
      </Cut>
    </Sequence>

    {/* 4 — 하나. 원고 구조 */}
    <Sequence {...S(4)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_CODE} tint="mono" speed={2.2} />
        <StepBig no={1} title={'잘되는 영상의\n원고 구조를 뜯는다'} note="여기가 제일 중요합니다" />
      </Cut>
    </Sequence>

    {/* 5 — ❌ 장점만 나열 */}
    <Sequence {...S(5)}>
      <Cut flash={C.red}>
        <BgFx src={BG_RANK} tint="mono" speed={2.6} startFrom={240} />
        <HookLine bad label="안 되는 영상" quote={'좋아요, 튼튼해요'} />
      </Cut>
    </Sequence>

    {/* 6 — ⭕ 공감 훅 */}
    <Sequence {...S(6)}>
      <Cut flash={C.green}>
        <BgFx src={BG_CAT} tint="mono" speed={2.2} startFrom={200} />
        <HookLine label="터지는 영상" quote={'여행 가서 짐\n떨어뜨린 적 있으시죠?'} />
      </Cut>
    </Sequence>

    {/* 7 — 공감이 전부입니다 */}
    <Sequence {...S(7)}>
      <Cut>
        <BgFx src={BG_INS} tint="monoWarm" speed={2.0} startFrom={300} />
        <Slam text={'공감이 전부입니다'} size={132} />
        <BarCaption text="끝까지 보니까 삽니다" accent="삽니다" />
      </Cut>
    </Sequence>

    {/* 8 — 5분류 */}
    <Sequence {...S(8)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_RANK} tint="mono" speed={2.0} startFrom={420} />
        <ChipRow items={['공감형', '충격형', '손해회피형', '스토리형', '리스트형']} />
      </Cut>
    </Sequence>

    {/* 9 — 저는 한 발 더 갔습니다 / 200편 */}
    <Sequence {...S(9)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_INS} tint="amber" speed={2.4} zoom={[1.3, 1.1]} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={44} strength={0.85} />
          <Kinetic text={'저는 여기서 한 발 더'} size={72} color={C.dim} stagger={1.4} />
          <div style={{ height: 10 }} />
          <CountUp to={200} suffix="편" label="조회수 상위 · 자막까지 전부" frames={46} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 10 — 오용형 실측 막대 */}
    <Sequence {...S(10)}>
      <Cut>
        <BgFx src={BG_CAT} tint="amber" speed={1.8} startFrom={120} dim={0.7} />
        <RankBars />
      </Cut>
    </Sequence>

    {/* 11 — 다음 편 예고 */}
    <Sequence {...S(11)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_RANK} tint="amber" speed={2.6} startFrom={520} />
        <Slam sub="이건" text={'다음 편에서\n제대로 뜯겠습니다'} size={100} />
      </Cut>
    </Sequence>

    {/* 12 — 둘 */}
    <Sequence {...S(12)}>
      <Cut>
        <BgFx src={BG_CODE} tint="mono" speed={2.2} startFrom={200} />
        <StepBig no={2} title={'그 구조에 맞춰\n내 제품 원고를 쓴다'} />
      </Cut>
    </Sequence>

    {/* 13 — 셋 */}
    <Sequence {...S(13)}>
      <Cut>
        <BgFx src={BG_INS} tint="mono" speed={2.2} startFrom={420} />
        <StepBig no={3} title={'소재 영상을 구한다'} note="중국 쪽 플랫폼에서 실사용 영상" />
      </Cut>
    </Sequence>

    {/* 14 — 넷·다섯·여섯 */}
    <Sequence {...S(14)}>
      <Cut>
        <BgFx src={BG_CAT} tint="mono" speed={2.4} startFrom={300} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={46} strength={0.86} />
          <div style={{ display: 'flex', gap: 30 }}>
            {[[4, '원본 자막 제거'], [5, '성우 입히기'], [6, '편집·자막']].map(([n, t], i) => (
              <StepChip key={String(n)} no={n as number} title={t as string} delay={i * 42} />
            ))}
          </div>
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 15 — 일곱·여덟 */}
    <Sequence {...S(15)}>
      <Cut>
        <BgFx src={BG_RANK} tint="mono" speed={2.4} startFrom={600} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={46} strength={0.86} />
          <div style={{ display: 'flex', gap: 30 }}>
            {[[7, '썸네일·훅 문구'], [8, '해시태그·업로드']].map(([n, t], i) => (
              <StepChip key={String(n)} no={n as number} title={t as string} delay={i * 46} />
            ))}
          </div>
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 16 — 이게 전부입니다 */}
    <Sequence {...S(16)}>
      <Cut flash={C.gold} wipe={false}>
        <BgFx src={BG_RANK} tint="amber" speed={2.0} startFrom={700} />
        <AllSteps />
        <BarCaption kicker="이게 전부입니다" text="숨긴 거 없습니다" accent="없습니다" />
      </Cut>
    </Sequence>

    <Grain opacity={0.1} />
  </AbsoluteFill>
);

/** 여러 단계를 나란히 보여줄 때 쓰는 작은 카드 */
function StepChip({ no, title, delay }: { no: number; title: string; delay: number }) {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - delay, fps, config: { damping: 200, mass: 0.45 } });
  return (
    <div
      style={{
        opacity: p,
        transform: 'translateY(' + (1 - p) * 70 + 'px) scale(' + (0.85 + p * 0.15) + ')',
        width: 380, padding: '34px 30px', borderRadius: 18,
        background: 'rgba(12,12,20,0.9)',
        border: '1.5px solid rgba(250,204,21,0.5)',
        boxShadow: '0 34px 80px rgba(0,0,0,0.75)',
      }}
    >
      <div style={{ font: '900 96px ' + F.sans, color: C.gold, lineHeight: 1 }}>
        {String(no).padStart(2, '0')}
      </div>
      <div style={{ marginTop: 14, font: '800 38px ' + F.sans, color: C.paper }}>{title}</div>
    </div>
  );
}
