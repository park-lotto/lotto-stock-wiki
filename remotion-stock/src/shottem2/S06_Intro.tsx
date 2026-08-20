import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import {
  BgFx, Screen3D, BarCaption, Slam, Kinetic, Flash, Wipe, Grain, ZoomPunch, Scrim, EASE,
} from './fx';
import { C, F } from './theme2';

/* 숏템하우스 2편 · 6단계 진입 (68.68초)
   여기서 흑백이 끝나고 컬러로 넘어온다 — 문제(흑백) → 내 물건(컬러).
   커밋 로그 클립은 없음(2026-08-20 사장님 확인) → 터미널 클립으로 대체. */

const SEG: [number, number][] = [
  [0, 45], [45, 179], [224, 190], [414, 81], [495, 207], [702, 229], [931, 181],
  [1112, 142], [1254, 80], [1334, 242], [1576, 179], [1755, 164], [1919, 141],
];
export const ST2_S06_FRAMES = 2060;
const S = (i: number) => ({ from: SEG[i][0], durationInFrames: SEG[i][1] });

const BG_CODE = 'shottem2/bg/bg_코드터미널.mp4';
const BG_RANK = 'shottem2/bg/bg_랭킹스크롤.mp4';
const BG_CAT = 'shottem2/bg/bg_랭킹카테고리.mp4';
const BG_INS = 'shottem2/bg/bg_랭킹인스타.mp4';

const R = {
  desk: 'shottem2/s06/desk.mp4',      // 3모니터 실사
  term: 'shottem2/s06/terminal.mp4',  // 클로드 코드 4분할
  ch: 'shottem2/s06/channel.mp4',     // 숏템메이커 유튜브 채널(1편)
};

const Cut: React.FC<{ children: React.ReactNode; flash?: string; wipe?: boolean }> = ({
  children, flash = '#fff', wipe = true,
}) => (
  <AbsoluteFill>
    <ZoomPunch>{children}</ZoomPunch>
    {wipe ? <Wipe /> : null}
    <Flash color={flash} />
  </AbsoluteFill>
);

/** V1 → V2 업그레이드 */
const VersionUp: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.55 } });
  const p2 = spring({ frame: f - 22, fps, config: { damping: 12, mass: 0.9 } });
  const Box: React.FC<{ v: string; on: boolean; sc: number }> = ({ v, on, sc }) => (
    <div
      style={{
        padding: '30px 56px', borderRadius: 20, transform: 'scale(' + sc + ')',
        background: on ? 'rgba(250,204,21,0.16)' : 'rgba(12,12,20,0.85)',
        border: '2px solid ' + (on ? C.gold : 'rgba(255,255,255,0.18)'),
        boxShadow: on ? '0 0 80px rgba(250,204,21,0.45)' : 'none',
        font: '900 96px ' + F.sans, color: on ? C.gold : C.dim,
        opacity: on ? 1 : 0.5,
      }}
    >
      {v}
    </div>
  );
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={46} h={44} strength={0.86} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 40, opacity: p }}>
        <Box v="V1" on={false} sc={0.86} />
        <div style={{ font: '900 84px ' + F.sans, color: C.gold, opacity: p2 }}>→</div>
        <Box v="V2" on={p2 > 0.3} sc={0.9 + p2 * 0.22} />
      </div>
      <div
        style={{
          marginTop: 40, font: '800 44px ' + F.sans, color: C.paper,
          opacity: interpolate(f, [40, 60], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
          textShadow: '0 6px 24px rgba(0,0,0,1)',
        }}
      >
        기능이 추가되고 강화됐습니다
      </div>
    </AbsoluteFill>
  );
};

/** 체험 버전 — 되는 것 / 안 되는 것 */
const TrialCompare: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const Card: React.FC<{ ok: boolean; title: string; sub: string; delay: number }> = ({
    ok, title, sub, delay,
  }) => {
    const p = spring({ frame: f - delay, fps, config: { damping: 200, mass: 0.5 } });
    const col = ok ? C.green : C.red;
    return (
      <div
        style={{
          width: 620, padding: '44px 40px', borderRadius: 22,
          opacity: p, transform: 'translateY(' + (1 - p) * 60 + 'px) scale(' + (0.9 + p * 0.1) + ')',
          background: 'rgba(8,9,14,0.92)',
          border: '2px solid ' + col,
          boxShadow: '0 40px 100px rgba(0,0,0,0.8), 0 0 60px ' +
            (ok ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.16)'),
        }}
      >
        <div style={{ font: '900 60px ' + F.sans, color: col, marginBottom: 14 }}>
          {ok ? '○' : '✕'}
        </div>
        <div style={{ font: '900 46px ' + F.sans, color: C.paper }}>{title}</div>
        <div style={{ marginTop: 12, font: '700 30px ' + F.sans, color: C.dim }}>{sub}</div>
      </div>
    );
  };
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={48} strength={0.88} />
      <div style={{ textAlign: 'center' }}>
        <div style={{ font: '800 32px ' + F.sans, color: C.gold, letterSpacing: 8, marginBottom: 30 }}>
          체험 버전
        </div>
        <div style={{ display: 'flex', gap: 30 }}>
          <Card ok={false} title="영상 제작" sub="체험에서는 안 됩니다" delay={0} />
          <Card ok title="레퍼런스 랭킹" sub="소스 찾기·전반 기능 사용" delay={16} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** 앞으로 볼 것 — 챕터 카드 6장이 차례로 꽂힌다 */
const Chapters: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const items = ['소재', '대본·장면', '자막 제거·성우', '꾸미기', '썸네일·렌더', '완성'];
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={50} strength={0.86} />
      <div style={{ textAlign: 'center' }}>
        <Kinetic text={'지금부터 보실 것'} size={64} color={C.dim} stagger={1.3} />
        <div style={{ display: 'flex', gap: 16, marginTop: 40 }}>
          {items.map((t, i) => {
            const p = spring({ frame: f - 18 - i * 8, fps, config: { damping: 200, mass: 0.42 } });
            return (
              <div
                key={t}
                style={{
                  opacity: p,
                  transform: 'translateY(' + (1 - p) * 60 + 'px) rotate(' + (1 - p) * (i % 2 ? 6 : -6) + 'deg)',
                  width: 280, height: 190, borderRadius: 18, padding: 24,
                  background: 'linear-gradient(160deg, rgba(250,204,21,0.14), rgba(10,10,18,0.92))',
                  border: '1.5px solid rgba(250,204,21,0.5)',
                  boxShadow: '0 30px 70px rgba(0,0,0,0.75)',
                  display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                }}
              >
                <div style={{ font: '900 56px ' + F.sans, color: C.gold, lineHeight: 1 }}>
                  {String(i + 1).padStart(2, '0')}
                </div>
                <div style={{ font: '800 34px ' + F.sans, color: C.paper, textAlign: 'left' }}>{t}</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const S06_Intro: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: '#05060a' }}>
    <Audio src={staticFile('shottem2/voice/s06.mp3')} />

    {/* 0 — 그래서 직접 만들었습니다 (여기서 컬러가 들어온다) */}
    <Sequence {...S(0)}>
      <Cut flash={C.gold} wipe={false}>
        <BgFx src={BG_CODE} tint="amber" speed={2.2} zoom={[1.32, 1.14]} />
        <Slam text={'그래서\n직접 만들었습니다'} size={116} />
      </Cut>
    </Sequence>

    {/* 1 — 설계를 잘하는 재주 */}
    <Sequence {...S(1)}>
      <Cut>
        <BgFx src={BG_CODE} tint="amber" speed={2.0} startFrom={200} dim={0.8} />
        <Screen3D src={R.term} label="CLAUDE CODE" w={1660} y={-56} tilt={5} speed={1.5} cropTop={0.04} />
        <BarCaption kicker="제 자랑이지만" text="설계를 잘하는 재주가 있죠" accent="설계" />
      </Cut>
    </Sequence>

    {/* 2 — 팔려고 만든 게 아니라 매일 쓰려고 */}
    <Sequence {...S(2)}>
      <Cut>
        <BgFx src={BG_RANK} tint="amber" speed={2.0} startFrom={300} dim={0.75} />
        <Screen3D src={R.desk} label="작업 책상" w={1660} y={-56} tilt={-5} speed={1.2} />
        <BarCaption kicker="팔려고 만든 게 아니라" text="제가 매일 쓰려고" accent="매일 쓰려고" />
      </Cut>
    </Sequence>

    {/* 3 — 실용성에 초점 */}
    <Sequence {...S(3)}>
      <Cut flash={C.gold} wipe={false}>
        <BgFx src={BG_CAT} tint="amber" speed={2.6} zoom={[1.4, 1.16]} />
        <Slam text={'실용성에 초점을 뒀습니다'} size={104} />
      </Cut>
    </Sequence>

    {/* 4 — 1편 이후 V2로 */}
    <Sequence {...S(4)}>
      <Cut>
        <BgFx src={BG_INS} tint="amber" speed={2.0} startFrom={120} dim={0.7} />
        <VersionUp />
      </Cut>
    </Sequence>

    {/* 5 — 조회수는 안 나왔지만 문의가 많았다 */}
    <Sequence {...S(5)}>
      <Cut>
        <BgFx src={BG_RANK} tint="amber" speed={2.0} startFrom={420} dim={0.75} />
        <Screen3D src={R.ch} label="1편 · 숏템메이커 쇼핑쇼츠" w={1660} y={-56} tilt={4} speed={1.3} cropTop={0.04} />
        <BarCaption kicker="조회수는 얼마 안 나왔지만" text="문의가 정말 많았습니다" accent="많았습니다" />
      </Cut>
    </Sequence>

    {/* 6 — 니즈가 공감된 키 영상 */}
    <Sequence {...S(6)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_CODE} tint="amber" speed={2.2} startFrom={520} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={46} strength={0.88} />
          <Kinetic text={'그만큼 니즈가 공감됐고'} size={70} color={C.dim} stagger={1.3} />
          <div style={{ height: 16 }} />
          <Kinetic text={'문제를 푸는 키 영상'} size={116} accent="키 영상" delay={16} stagger={1.5} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 7 — 오늘은 구체적으로 보여드립니다 */}
    <Sequence {...S(7)}>
      <Cut wipe={false}>
        <BgFx src={BG_CAT} tint="amber" speed={2.4} startFrom={200} zoom={[1.34, 1.12]} />
        <Slam sub="그래서 오늘은" text={'보완된 프로그램을\n구체적으로'} size={100} />
      </Cut>
    </Sequence>

    {/* 8 — 체험 문의도 많이 받았습니다 */}
    <Sequence {...S(8)}>
      <Cut>
        <BgFx src={BG_INS} tint="amber" speed={2.6} startFrom={340} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={42} strength={0.86} />
          <Kinetic text={'체험 문의도 많았습니다'} size={104} accent="체험" stagger={1.4} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 9 — 체험 버전에서 되는 것 / 안 되는 것 */}
    <Sequence {...S(9)}>
      <Cut flash={C.green}>
        <BgFx src={BG_RANK} tint="amber" speed={1.8} startFrom={560} dim={0.7} />
        <TrialCompare />
      </Cut>
    </Sequence>

    {/* 10 — 1기 + 크루 체험단 */}
    <Sequence {...S(10)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_CAT} tint="amber" speed={2.0} startFrom={420} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={46} strength={0.88} />
          <Kinetic text={'1기 시작과 함께'} size={68} color={C.dim} stagger={1.3} />
          <div style={{ height: 16 }} />
          <Kinetic text={'크루 체험단도 모집합니다'} size={108} accent="크루 체험단" delay={16} stagger={1.4} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 11 — 피드백과 함께 결과를 만들어 간다 */}
    <Sequence {...S(11)}>
      <Cut>
        <BgFx src={BG_CODE} tint="amber" speed={2.2} startFrom={640} dim={0.8} />
        <Screen3D src={R.term} label="매일 고치는 중" w={1600} y={-56} tilt={-4} speed={2.0} startFrom={180} cropTop={0.04} />
        <BarCaption text="피드백과 함께 결과를 만들어 갑니다" accent="함께" />
      </Cut>
    </Sequence>

    {/* 12 — 지금부터 보실 것 (챕터 카드) */}
    <Sequence {...S(12)}>
      <Cut flash={C.gold} wipe={false}>
        <BgFx src={BG_CAT} tint="amber" speed={2.0} startFrom={600} dim={0.75} />
        <Chapters />
      </Cut>
    </Sequence>

    <Grain opacity={0.1} />
  </AbsoluteFill>
);
