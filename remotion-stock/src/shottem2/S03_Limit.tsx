import React from 'react';
import {
  AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import {
  BgFx, Screen3D, BarCaption, Slam, Kinetic, Flash, Wipe, Grain, ZoomPunch, Scrim, EASE,
} from './fx';
import { C, F } from './theme2';

/* 숏템하우스 2편 · 3단계 그 해결책의 한계 (81.79초)
   타임코드 = TTS 실측(20문단 전부 무음 앵커에 스냅) → timing/s03.json */

const SEG: [number, number][] = [
  [0, 89], [89, 97], [186, 104], [290, 124], [414, 124], [538, 86], [624, 191],
  [815, 101], [916, 184], [1100, 32], [1132, 87], [1219, 171], [1390, 161],
  [1551, 118], [1669, 46], [1715, 133], [1848, 192], [2040, 93], [2133, 136], [2269, 185],
];
export const ST2_S03_FRAMES = 2454;
const S = (i: number) => ({ from: SEG[i][0], durationInFrames: SEG[i][1] });

const BG_CUT = 'shottem2/bg/bg_캡컷타임라인.mp4';
const BG_CODE = 'shottem2/bg/bg_코드터미널.mp4';
const BG_RANK = 'shottem2/bg/bg_랭킹스크롤.mp4';
const BG_INS = 'shottem2/bg/bg_랭킹인스타.mp4';

const R = {
  excel: 'shottem2/s03/excel.mp4',
  insta: 'shottem2/s03/insta.mp4',
  xhs2: 'shottem2/s03/xhs2.mp4',
  douyin: 'shottem2/s03/douyin.mp4',
  translate: 'shottem2/s03/translate.mp4',
  xhs: 'shottem2/s03/xhs.mp4',
  gpt: 'shottem2/s03/gpt.mp4',
  capcut_sub: 'shottem2/s03/capcut_sub.mp4',
  coupas: 'shottem2/s03/coupas.mp4',
  inpock: 'shottem2/s03/inpock.mp4',
  capcut: 'shottem2/s03/capcut.mp4',
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

/** 세 화면이 순차로 밀려 들어오는 몽타주 — 일이 쌓이는 느낌 */
const Triple: React.FC<{ srcs: string[]; labels: string[] }> = ({ srcs, labels }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', perspective: 2000 }}>
      <div style={{ display: 'flex', gap: 22 }}>
        {srcs.map((s, i) => {
          const p = spring({ frame: f - i * 12, fps, config: { damping: 200, mass: 0.5 } });
          const rot = i === 0 ? 7 : i === 2 ? -7 : 0;
          return (
            <div
              key={s}
              style={{
                width: 560,
                opacity: p,
                transform:
                  'translateY(' + (1 - p) * 110 + 'px) rotateY(' + rot + 'deg) scale(' + (0.86 + p * 0.14) + ')',
                borderRadius: 8, overflow: 'hidden', position: 'relative',
                boxShadow: '0 50px 110px rgba(0,0,0,0.85), 0 0 0 1px rgba(255,255,255,0.1)',
                background: '#05060a',
              }}
            >
              <OffthreadVideo
                src={staticFile(s)}
                playbackRate={1.6}
                muted
                style={{ width: '100%', display: 'block' }}
              />
              <div
                style={{
                  position: 'absolute', left: 12, bottom: 10,
                  padding: '6px 12px', borderRadius: 4,
                  background: 'rgba(0,0,0,0.7)',
                  font: '700 17px ' + F.mono, color: C.gold, letterSpacing: 1,
                }}
              >
                {labels[i]}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** 실패한 검색 — 화면이 좌우로 흔들리며 '허탕'을 표현 */
const FailShake: React.FC<{ src: string; label: string }> = ({ src, label }) => {
  const f = useCurrentFrame();
  const shake = Math.sin(f * 0.55) * 12 + Math.sin(f * 1.3) * 5;
  return (
    <AbsoluteFill style={{ transform: 'translateX(' + shake + 'px)' }}>
      <Screen3D src={src} label={label} w={1620} y={-50} tilt={4} speed={1.8} cropTop={0.04} />
    </AbsoluteFill>
  );
};

/** 큰 숫자 + 설명 — '평균 일주일' 같은 통계 한 방 */
const StatBig: React.FC<{ big: string; top?: string; bottom?: string }> = ({ big, top, bottom }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.5 } });
  const sc = interpolate(f, [0, 9], [1.5, 1], { extrapolateRight: 'clamp', easing: EASE.slam });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Scrim y={50} h={46} strength={0.9} />
      <div style={{ textAlign: 'center' }}>
        {top ? (
          <div style={{ font: '700 44px ' + F.sans, color: C.dim, marginBottom: 12, opacity: p }}>{top}</div>
        ) : null}
        <div
          style={{
            font: '900 210px ' + F.sans, color: C.red, lineHeight: 1,
            transform: 'scale(' + sc + ')', opacity: p,
            textShadow: '0 0 70px rgba(248,113,113,0.55), 0 10px 30px rgba(0,0,0,1)',
            WebkitTextStroke: '3px rgba(0,0,0,0.5)',
          }}
        >
          {big}
        </div>
        {bottom ? (
          <div
            style={{
              marginTop: 18, font: '800 52px ' + F.sans, color: C.paper,
              opacity: interpolate(f, [16, 32], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
              textShadow: '0 6px 24px rgba(0,0,0,1)',
            }}
          >
            {bottom}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

export const S03_Limit: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: '#05060a' }}>
    <Audio src={staticFile('shottem2/voice/s03.mp3')} />

    {/* 0 — 그럼 왜 안 될까요 */}
    <Sequence {...S(0)}>
      <Cut wipe={false}>
        <BgFx src={BG_CUT} tint="mono" speed={2.4} zoom={[1.3, 1.12]} />
        <Slam text={'그럼 왜 안 될까요'} size={128} />
        <BarCaption text="방법이 틀려서가 아닙니다" />
      </Cut>
    </Sequence>

    {/* 1 — 여덟 단계를 손으로 하면 */}
    <Sequence {...S(1)}>
      <Cut flash={C.red}>
        <BgFx src={BG_CUT} tint="mono" speed={2.8} startFrom={200} zoom={[1.38, 1.14]} />
        <Slam sub="지금 그 여덟 단계를" text={'손으로 하면\n이렇게 됩니다'} size={110} />
      </Cut>
    </Sequence>

    {/* 2 — 엑셀에 매일 정리 */}
    <Sequence {...S(2)}>
      <Cut>
        <BgFx src={BG_RANK} tint="mono" speed={2.0} />
        <Screen3D src={R.excel} label="EXCEL / 채널 관리" w={1640} y={-50} tilt={5} speed={1.5} cropTop={0.04} />
        <BarCaption text="엑셀에 매일 정리해 가면서" accent="매일" />
      </Cut>
    </Sequence>

    {/* 3 — 채널 하나씩 다 들어가 봅니다 */}
    <Sequence {...S(3)}>
      <Cut>
        <BgFx src={BG_INS} tint="mono" speed={2.2} startFrom={90} />
        <Screen3D src={R.insta} label="채널 하나씩" w={1640} y={-50} tilt={-5} speed={1.7} cropTop={0.04} />
        <BarCaption text="터진 영상 올라왔나 하나씩 다" accent="하나씩 다" />
      </Cut>
    </Sequence>

    {/* 4 — 오늘은 이 영상 해봐야겠다 */}
    <Sequence {...S(4)}>
      <Cut>
        <BgFx src={BG_INS} tint="mono" speed={2.2} startFrom={260} />
        <Screen3D src={R.insta} label="오늘은 이거" w={1640} y={-50} tilt={5} speed={1.4} startFrom={200} cropTop={0.04} />
        <BarCaption kicker="결정하면" text="그다음 뭘 하나요?" accent="뭘 하나요?" />
      </Cut>
    </Sequence>

    {/* 5 — 도우인, 샤오홍슈에서 검색 */}
    <Sequence {...S(5)}>
      <Cut flash={C.gold}>
        <BgFx src={BG_CODE} tint="mono" speed={2.4} />
        <Screen3D src={R.douyin} label="DOUYIN 抖音" w={1620} y={-50} tilt={-4} speed={1.6} cropTop={0.04} />
        <BarCaption text="도우인, 샤오홍슈에서 검색" accent="검색" />
      </Cut>
    </Sequence>

    {/* 6 — 챗지피티로 들어가 번역 */}
    <Sequence {...S(6)}>
      <Cut>
        <BgFx src={BG_CODE} tint="mono" speed={2.0} startFrom={200} />
        <Screen3D src={R.translate} label="CHATGPT / 중국어 번역" w={1620} y={-50} tilt={4} speed={1.9} cropTop={0.04} />
        <BarCaption kicker="검색하려면 또" text="번역부터 해야 합니다" accent="또" />
      </Cut>
    </Sequence>

    {/* 7 — 그걸 샤오홍슈에 검색 */}
    <Sequence {...S(7)}>
      <Cut>
        <BgFx src={BG_INS} tint="mono" speed={2.4} startFrom={400} />
        <Screen3D src={R.xhs} label="小红书 / 검색" w={1620} y={-50} tilt={-4} speed={1.7} cropTop={0.04} />
        <BarCaption text="그걸 다시 붙여넣고" />
      </Cut>
    </Sequence>

    {/* 8 — 결과는? 안 나올 때도 많고 (허탕) */}
    <Sequence {...S(8)}>
      <Cut flash={C.red}>
        <BgFx src={BG_CUT} tint="mono" speed={2.6} startFrom={300} zoom={[1.36, 1.14]} />
        <FailShake src={R.xhs2} label="결과 없음 / 키워드 변경" />
        <BarCaption kicker="안 나올 때도 많고" text="키워드 바꿔 가며 한참을" accent="한참을" />
      </Cut>
    </Sequence>

    {/* 9 — 공감하시나요 */}
    <Sequence {...S(9)}>
      <Cut flash={C.gold} wipe={false}>
        <BgFx src={BG_RANK} tint="monoWarm" speed={3.0} zoom={[1.45, 1.2]} />
        <Slam text={'공감하시나요?'} size={140} />
      </Cut>
    </Sequence>

    {/* 10 — 대본은 에이아이에게 */}
    <Sequence {...S(10)}>
      <Cut>
        <BgFx src={BG_CODE} tint="mono" speed={2.2} startFrom={340} />
        <Screen3D src={R.gpt} label="CHATGPT / 원고" w={1620} y={-50} tilt={4} speed={1.5} cropTop={0.04} />
        <BarCaption text="대본은 또 에이아이에게" accent="또" />
      </Cut>
    </Sequence>

    {/* 11 — 너는 백만 쇼츠의 작가야 */}
    <Sequence {...S(11)}>
      <Cut>
        <BgFx src={BG_CODE} tint="monoWarm" speed={2.0} startFrom={500} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={44} strength={0.88} />
          <div style={{ font: '700 34px ' + F.sans, color: C.dim, letterSpacing: 6, marginBottom: 22 }}>
            단골 멘트
          </div>
          <Kinetic text={'"너는 백만 쇼츠의 작가야"'} size={86} accent="백만 쇼츠" stagger={1.4} />
        </AbsoluteFill>
        <BarCaption text="이 프롬프트를 매일 씁니다" accent="매일" />
      </Cut>
    </Sequence>

    {/* 12 — 티티에스·자막·썸네일 */}
    <Sequence {...S(12)}>
      <Cut>
        <BgFx src={BG_CUT} tint="mono" speed={2.4} startFrom={500} />
        <Screen3D src={R.capcut_sub} label="자막 설정" w={1620} y={-50} tilt={-4} speed={2.0} cropTop={0.04} />
        <BarCaption text="성우 · 자막 제거 · 자막 설정 · 썸네일" />
      </Cut>
    </Sequence>

    {/* 13 — 쿠팡 + 인포크 + 캡컷 (삼분할) */}
    <Sequence {...S(13)}>
      <Cut flash={C.red}>
        <BgFx src={BG_CUT} tint="mono" speed={2.2} startFrom={200} dim={0.7} />
        <Triple
          srcs={[R.coupas, R.inpock, R.capcut]}
          labels={['쿠팡 링크', '인포크 링크', '캡컷']}
        />
        <BarCaption kicker="그리고 마지막" text="캡컷의 지옥" accent="지옥" />
      </Cut>
    </Sequence>

    {/* 14 — 이거 해본 사람만 압니다 */}
    <Sequence {...S(14)}>
      <Cut wipe={false}>
        <BgFx src={BG_CUT} tint="mono" speed={3.0} startFrom={620} zoom={[1.44, 1.18]} />
        <Slam text={'해본 사람만 압니다'} size={116} />
      </Cut>
    </Sequence>

    {/* 15 — 한 편에 반나절 */}
    <Sequence {...S(15)}>
      <Cut flash={C.red}>
        <BgFx src={BG_CUT} tint="mono" speed={2.4} startFrom={400} />
        <StatBig top="초보는 한 편에" big="반나절" bottom="하루 이틀은 기분 좋게 합니다" />
      </Cut>
    </Sequence>

    {/* 16 — 갈아 넣었는데 불안 */}
    <Sequence {...S(16)}>
      <Cut>
        <BgFx src={BG_CODE} tint="mono" speed={2.0} startFrom={620} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={46} strength={0.88} />
          <Kinetic text={'기세 좋게 갈아 넣었는데'} size={74} color={C.dim} stagger={1.4} />
          <div style={{ height: 16 }} />
          <Kinetic text={'시간이 갈수록 불안합니다'} size={112} accent="불안" delay={18} stagger={1.5} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    {/* 17 — 이쯤 버텼으면 많이 하신 겁니다 */}
    <Sequence {...S(17)}>
      <Cut>
        <BgFx src={BG_RANK} tint="mono" speed={2.6} startFrom={700} />
        <Slam text={'이쯤 버텼으면\n많이 하신 겁니다'} size={96} />
      </Cut>
    </Sequence>

    {/* 18 — 평균 일주일 */}
    <Sequence {...S(18)}>
      <Cut flash={C.red}>
        <BgFx src={BG_INS} tint="mono" speed={2.4} startFrom={600} />
        <StatBig top="평균" big="일주일" bottom="만세 부르고 도망칩니다" />
      </Cut>
    </Sequence>

    {/* 19 — 인풋 에너지가 높으니 매일 못 한다 */}
    <Sequence {...S(19)}>
      <Cut flash={C.gold} wipe={false}>
        <BgFx src={BG_CUT} tint="monoWarm" speed={2.0} startFrom={760} zoom={[1.28, 1.08]} />
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <Scrim y={50} h={48} strength={0.9} />
          <Kinetic text={'아는 게 부족한 게 아닙니다'} size={72} color={C.dim} stagger={1.3} />
          <div style={{ height: 22 }} />
          <Kinetic text={'매일 못 하게 되는 겁니다'} size={124} accent="매일 못 하게" delay={22} stagger={1.5} />
        </AbsoluteFill>
      </Cut>
    </Sequence>

    <Grain opacity={0.1} />
  </AbsoluteFill>
);
