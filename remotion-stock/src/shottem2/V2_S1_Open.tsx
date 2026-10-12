import React from 'react';
import {
  AbsoluteFill, Audio, OffthreadVideo, Img, Sequence, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import { BgFx, Slam, BarCaption, Kinetic, Flash, Wipe, Grain, ZoomPunch, EASE } from './fx';
import { C, F } from './theme2';

/* 숏템메이커 V2 광고 · S1 오프닝 (필재 TTS 94.8초, 문단 10개)
   문단 길이는 public/shottem2/v2s1/voice.mp3 를 만든 문단 파일 실측(초). 컷 = 문단 하나. */
const PARA = [7.045, 6.955, 10.773, 11.455, 15.682, 12.227, 12.364, 4.091, 4.045, 10.137];
const FPS = 30;
const START: number[] = [];
PARA.reduce((a, s, i) => { START[i] = Math.round(a * FPS); return a + s; }, 0);
export const V2_S1_FRAMES = Math.round(PARA.reduce((a, b) => a + b, 0) * FPS) + 15;
const seg = (i: number) => ({
  from: START[i],
  durationInFrames: (i + 1 < PARA.length ? START[i + 1] : V2_S1_FRAMES) - START[i],
});

const A = (n: string) => 'shottem2/v2s1/' + n;
const BG_CODE = 'shottem2/bg/bg_코드터미널.mp4';
const BG_RANK = 'shottem2/bg/bg_랭킹스크롤.mp4';

/** 세로 쇼츠를 가운데 폰 모양으로, 뒤는 같은 영상을 흐리게 */
const Phone: React.FC<{ src: string; x?: number; w?: number; delay?: number; start?: number }> = ({
  src, x = 0, w = 560, delay = 0, start = 0,
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - delay, fps, config: { damping: 16, mass: 0.7 } });
  const h = (w * 16) / 9;
  return (
    <div
      style={{
        position: 'absolute', left: 960 - w / 2 + x, top: 540 - h / 2, width: w, height: h,
        borderRadius: 34, overflow: 'hidden', border: '6px solid #111',
        boxShadow: '0 40px 120px rgba(0,0,0,0.85), 0 0 0 2px rgba(255,255,255,0.12)',
        transform: 'translateY(' + (1 - p) * 120 + 'px) scale(' + (0.85 + p * 0.15) + ')', opacity: p,
      }}
    >
      <OffthreadVideo src={staticFile(src)} muted startFrom={start} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </div>
  );
};

const BlurBg: React.FC<{ src: string }> = ({ src }) => (
  <AbsoluteFill style={{ overflow: 'hidden' }}>
    <OffthreadVideo
      src={staticFile(src)} muted
      style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(28px) brightness(0.35)', transform: 'scale(1.2)' }}
    />
  </AbsoluteFill>
);

/** ① 어머니가 만든 영상 */
const MomShort: React.FC = () => {
  const f = useCurrentFrame();
  const tag = interpolate(f, [20, 32], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill>
      <BlurBg src={A('mom1.mp4')} />
      <Phone src={A('mom1.mp4')} w={560} />
      <div
        style={{
          position: 'absolute', left: 1290, top: 360, opacity: tag,
          transform: 'translateX(' + (1 - tag) * 40 + 'px)',
        }}
      >
        <div style={{ font: '800 34px ' + F.sans, color: C.dim }}>만든 사람</div>
        <div style={{ font: '900 92px/1.1 ' + F.sans, color: C.gold }}>60대<br />우리 어머니</div>
        <div style={{ font: '700 34px ' + F.sans, color: C.paper, marginTop: 24 }}>타자 0번 · 버튼만</div>
      </div>
    </AbsoluteFill>
  );
};

/** ③ 연령대 막대 — 서버 실측(가입 회원 중 연령대 기재 509명) */
const AGES: [string, number][] = [['20대', 23], ['30대', 80], ['40대', 162], ['50대', 175]];
const AgeBars: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const max = 175;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ font: '800 44px ' + F.sans, color: C.paper, marginBottom: 40 }}>숏템메이커 가입 회원 · 가장 많은 연령대</div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 70, height: 560 }}>
        {AGES.map(([k, v], i) => {
          const top = k === '50대';
          const p = spring({ frame: f - 40 - i * 12, fps, config: { damping: 200, mass: 0.6 } });
          return (
            <div key={k} style={{ textAlign: 'center', width: 200 }}>
              <div style={{ font: '900 48px ' + F.sans, color: top ? C.gold : C.dim, opacity: p }}>{Math.round(v * p)}명</div>
              <div
                style={{
                  height: (v / max) * 440 * p, marginTop: 12, borderRadius: '14px 14px 0 0',
                  background: top ? C.gold : 'rgba(255,255,255,0.22)',
                  boxShadow: top ? '0 0 60px rgba(250,204,21,0.55)' : 'none',
                }}
              />
              <div style={{ font: '900 54px ' + F.sans, color: top ? C.gold : C.paper, marginTop: 16 }}>{k}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** ④ 회원 쇼츠 몽타주 (지금은 받은 쇼츠 3편) */
const Montage: React.FC = () => (
  <AbsoluteFill>
    <BlurBg src={A('mom2.mp4')} />
    <Phone src={A('mom2.mp4')} x={-560} w={460} delay={0} />
    <Phone src={A('mom1.mp4')} x={0} w={460} delay={8} start={300} />
    <Phone src={A('mom3.mp4')} x={560} w={460} delay={16} />
  </AbsoluteFill>
);

/** ⑥ 숫자 세 개 */
const Num: React.FC<{ to: number; unit: string; label: string; delay: number }> = ({ to, unit, label, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const v = Math.round(interpolate(f - delay, [0, 30], [0, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: EASE.out }));
  const p = spring({ frame: f - delay, fps, config: { damping: 14, mass: 0.7 } });
  return (
    <div style={{ textAlign: 'center', width: 520, opacity: Math.min(1, p * 1.5), transform: 'scale(' + (0.7 + p * 0.3) + ')' }}>
      <div style={{ font: '900 150px/1 ' + F.sans, color: C.gold, textShadow: '0 0 60px rgba(250,204,21,0.5)' }}>
        {v.toLocaleString()}<span style={{ fontSize: 64 }}>{unit}</span>
      </div>
      <div style={{ font: '800 40px ' + F.sans, color: C.paper, marginTop: 14 }}>{label}</div>
    </div>
  );
};
const Numbers: React.FC = () => {
  const f = useCurrentFrame();
  const v2 = spring({ frame: f - 250, fps: 30, config: { damping: 12, mass: 0.9 } });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      {f < 250 ? (
        <div style={{ display: 'flex', gap: 30 }}>
          <Num to={59} unit="일" label="1편 이후" delay={0} />
          <Num to={2478} unit="건" label="업데이트" delay={45} />
          <Num to={40} unit="번+" label="하루 평균" delay={110} />
        </div>
      ) : (
        <div style={{ textAlign: 'center', transform: 'scale(' + (0.6 + v2 * 0.4) + ')', opacity: v2 }}>
          <div style={{ font: '800 54px ' + F.sans, color: C.dim, letterSpacing: 12 }}>숏템메이커</div>
          <div style={{ font: '900 330px/1 ' + F.sans, color: C.gold, textShadow: '0 0 120px rgba(250,204,21,0.7)' }}>V2</div>
        </div>
      )}
    </AbsoluteFill>
  );
};

/** ⑧ 단톡방 + 1기 100명 */
const Talk: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 200, mass: 0.6 } });
  return (
    <AbsoluteFill>
      <Img
        src={staticFile(A('talk.png'))}
        style={{
          position: 'absolute', left: 260, top: 90, height: 900, borderRadius: 18,
          boxShadow: '0 30px 100px rgba(0,0,0,0.8)', transform: 'translateY(' + (1 - p) * 80 + 'px)', opacity: p,
          filter: 'brightness(0.95)',
        }}
      />
      {/* 인원수 칸은 가린다(실제 476명 표기 대신 대사로 말한다) */}
      <div style={{ position: 'absolute', left: 260 + 78 * 1.43, top: 90 + 58 * 1.43, width: 48, height: 22, background: '#bacee0', opacity: p }} />
      <div style={{ position: 'absolute', left: 1000, top: 330 }}>
        <Sequence from={10} layout="none">
          <div>
            <div style={{ font: '800 44px ' + F.sans, color: C.dim }}>영상 단 하나로</div>
            <div style={{ font: '900 150px/1.1 ' + F.sans, color: C.gold }}>1기<br />100명</div>
          </div>
        </Sequence>
      </div>
    </AbsoluteFill>
  );
};

export const V2_S1_Open: React.FC = () => (
  <AbsoluteFill style={{ background: C.ink }}>
    <Audio src={staticFile(A('voice.mp3'))} />
    <Audio src={staticFile('shottem2/v2bgm/epic.mp3')} loop volume={0.11} />

    <Sequence {...seg(0)}><MomShort /></Sequence>

    <Sequence {...seg(1)}>
      <BgFx src={A('mom2.mp4')} tint="amber" dim={0.7} />
      <Slam text={'"60대 우리 엄마도\n직접 할 수 있게"'} size={112} sub="1편의 약속" />
      <Sequence from={130}><Flash /><BarCaption text="그 약속, 지켰습니다" accent="지켰습니다" /></Sequence>
    </Sequence>

    <Sequence {...seg(2)}>
      <BgFx src={BG_RANK} tint="amber" dim={0.45} />
      <AgeBars />
    </Sequence>

    <Sequence {...seg(3)}>
      <Montage />
      <Wipe />
      <Sequence from={60}><BarCaption text="회원분들이 직접 만든 쇼츠" accent="직접" /></Sequence>
    </Sequence>

    <Sequence {...seg(4)}>
      <BgFx src={BG_CODE} tint="cyan" dim={0.8} />
      <Kinetic text={'책상 하나,\n개발자 한 명'} size={120} accent="개발자 한 명" />
      <Sequence from={170}>
        <AbsoluteFill style={{ background: 'rgba(0,0,0,0.55)' }} />
        <Kinetic text={'찾고 · 쓰고 · 자르고\n지우고 · 입히고 · 매일'} size={96} accent="매일" />
      </Sequence>
    </Sequence>

    <Sequence {...seg(5)}>
      <BgFx src={BG_CODE} tint="amber" dim={0.6} />
      <Numbers />
      <Sequence from={250}><Flash /></Sequence>
    </Sequence>

    <Sequence {...seg(6)}>
      <BgFx src={BG_RANK} tint="amber" dim={0.7} />
      <Sequence from={0} durationInFrames={190}>
        <Kinetic text={'보는 것과\n직접 써 보는 건 다릅니다'} size={100} accent="직접 써 보는 건" />
      </Sequence>
      <Sequence from={190}>
        <ZoomPunch><Slam text={'지금 나와 있는 것 중\n숏템메이커가 제일 셉니다'} size={104} /></ZoomPunch>
        <Flash />
      </Sequence>
    </Sequence>

    <Sequence {...seg(7)}>
      <BgFx src={BG_RANK} tint="amber" dim={0.5} />
      <Talk />
    </Sequence>

    <Sequence {...seg(8)}>
      <BgFx src={A('mom1.mp4')} tint="amber" dim={0.6} />
      <Slam text={'먼저 보신 분이,\n먼저 가져갑니다'} size={118} />
    </Sequence>

    <Sequence {...seg(9)}>
      <BgFx src={BG_RANK} tint="mono" dim={0.6} />
      <Kinetic text={'강의나 프로그램,\n이미 결제해 보셨습니까?'} size={100} accent="이미 결제" />
      <Sequence from={150}><BarCaption text="끝까지 보고, 직접 비교해 보십시오" accent="직접 비교" /></Sequence>
    </Sequence>

    <Grain opacity={0.08} />
  </AbsoluteFill>
);
