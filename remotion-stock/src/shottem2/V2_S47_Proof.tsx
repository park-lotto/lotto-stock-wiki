import React from 'react';
import {
  AbsoluteFill, Img, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import { BgFx, Slam, BarCaption, Flash, Grain, Wipe, EASE } from './fx';
import { C, F } from './theme2';

/* 숏템메이커 V2 광고 · S4-7 증거 — 1기 회원 실제 한 달 (2026-10-12 사장님 지시)
   수익 금액보다 판매 수량(구매 80건)·팔린 금액을 주인공으로, 마지막에 한 달 수익을 솔직하게.
   캡처 숫자는 원본 그대로 쓴다(가공 금지). 재료: public/shottem2/s47/list.png · rev.jpg */

export const V2_S47_FRAMES = 1080;
const LIST = 'shottem2/s47/list.png'; // 1092x3478 — 실전30일 5장(최신→과거)
const REV = 'shottem2/s47/rev.jpg';   // 1079x871 — 일별 실적
const REV_W = 1079;
const REV_H = 871;
const BG = 'shottem2/bg/bg_랭킹스크롤.mp4';

/** 캡처 한 장을 (cx,cy) 지점으로 확대해 들어간다. 나머지는 어둡게 */
const ZoomShot: React.FC<{
  from: [number, number, number]; to: [number, number, number];
  frames?: number; spot?: [number, number, number, number];
}> = ({ from, to, frames = 24, spot }) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, frames], [0, 1], { extrapolateRight: 'clamp', easing: EASE.out });
  const cx = from[0] + (to[0] - from[0]) * t;
  const cy = from[1] + (to[1] - from[1]) * t;
  const s = from[2] + (to[2] - from[2]) * t;
  const left = 960 - cx * s;
  const top = 540 - cy * s;
  const so = interpolate(f, [frames - 4, frames + 6], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Img
        src={staticFile(REV)}
        style={{
          position: 'absolute', left, top, width: REV_W * s, height: REV_H * s,
          borderRadius: 18, boxShadow: '0 30px 120px rgba(0,0,0,0.8)',
        }}
      />
      {spot ? (
        <div
          style={{
            position: 'absolute', opacity: so,
            left: left + spot[0] * s, top: top + spot[1] * s,
            width: spot[2] * s, height: spot[3] * s, borderRadius: 14,
            border: '5px solid ' + C.gold,
            boxShadow: '0 0 0 4000px rgba(0,0,0,' + 0.62 * so + '), 0 0 50px rgba(250,204,21,0.7)',
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};

/** 큰 숫자 + 설명 — 화면 아래쪽에 크게 */
const BigNum: React.FC<{ to: number; pre?: string; suffix?: string; label: string; color?: string; y?: number }> = ({
  to, pre = '', suffix = '', label, color = C.gold, y = 640,
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const v = Math.round(interpolate(f, [0, 36], [0, to], { extrapolateRight: 'clamp', easing: EASE.out }));
  const p = spring({ frame: f, fps, config: { damping: 14, mass: 0.8 } });
  return (
    <div
      style={{
        position: 'absolute', left: 0, right: 0, top: y, textAlign: 'center',
        transform: 'scale(' + (0.7 + p * 0.3) + ')', opacity: Math.min(1, p * 1.4),
      }}
    >
      <div
        style={{
          display: 'inline-block', padding: '18px 54px', borderRadius: 26,
          background: 'rgba(8,10,14,0.88)', border: '2px solid ' + color,
        }}
      >
        <div style={{ font: '900 170px/1 ' + F.sans, color, letterSpacing: -4, textShadow: '0 0 60px ' + color + '88' }}>
          {pre}{v.toLocaleString()}{suffix}
        </div>
        <div style={{ font: '800 44px ' + F.sans, color: C.paper, marginTop: 14 }}>{label}</div>
      </div>
    </div>
  );
};

/** 실전30일 목록 — 점점 빨라지는 스크롤 + 날짜 칸 강조 + '매일' 카운터 */
const ListScroll: React.FC = () => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const W = 1500;
  const s = W / 1092;
  const H = 3478 * s;
  const y = interpolate(f, [0, durationInFrames], [0, -(H - 1080)], {
    extrapolateRight: 'clamp', easing: (x) => x * x * (3 - 2 * x),
  });
  const day = Math.round(interpolate(f, [0, durationInFrames - 20], [20, 1], { extrapolateRight: 'clamp' }));
  const left = (1920 - W) / 2;
  return (
    <AbsoluteFill style={{ background: '#fff', overflow: 'hidden' }}>
      <Img src={staticFile(LIST)} style={{ position: 'absolute', left, top: y, width: W, height: H }} />
      {/* 날짜 칸 강조 띠 (원본 x 720~870) */}
      <div
        style={{
          position: 'absolute', top: 0, bottom: 0, left: left + 715 * s, width: 160 * s,
          background: 'rgba(250,204,21,0.22)', borderLeft: '4px solid ' + C.gold, borderRight: '4px solid ' + C.gold,
        }}
      />
      <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(0,0,0,0.55), transparent 22%, transparent 78%, rgba(0,0,0,0.55))' }} />
      <div
        style={{
          position: 'absolute', right: 50, top: 46, padding: '16px 30px', borderRadius: 18,
          background: 'rgba(8,10,14,0.9)', border: '2px solid ' + C.gold, textAlign: 'center',
        }}
      >
        <div style={{ font: '800 30px ' + F.sans, color: C.dim }}>2026. 9. {day}.</div>
        <div style={{ font: '900 64px ' + F.sans, color: C.gold }}>매일 업로드</div>
      </div>
    </AbsoluteFill>
  );
};

/** 그래프 끝 — 마지막 급등으로 밀고 들어간다 */
const GraphEnd: React.FC = () => {
  const f = useCurrentFrame();
  const glow = interpolate(f, [30, 44, 70], [0, 1, 0.6], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill>
      <ZoomShot from={[540, 560, 1.15]} to={[640, 470, 2.2]} frames={40} />
      <div
        style={{
          position: 'absolute', left: 960 + (741 - 640) * 2.2 - 70, top: 540 + (395 - 470) * 2.2 - 70,
          width: 140, height: 140, borderRadius: 70, opacity: glow,
          border: '6px solid ' + C.gold, boxShadow: '0 0 80px rgba(250,204,21,0.9)',
        }}
      />
    </AbsoluteFill>
  );
};

export const V2_S47_Proof: React.FC = () => (
  <AbsoluteFill style={{ background: C.ink }}>
    <BgFx src={BG} tint="amber" dim={0.8} />

    {/* ① 오프닝 */}
    <Sequence from={0} durationInFrames={90}>
      <Slam text={'1기 회원님의\n실제 한 달'} size={140} sub="REAL · 30 DAYS" />
      <Flash />
    </Sequence>

    {/* ② 매일 올린 목록 */}
    <Sequence from={90} durationInFrames={300}>
      <ListScroll />
      <Wipe />
      <Sequence from={40} durationInFrames={250}>
        <BarCaption text="한 달 동안, 매일 올렸습니다" accent="매일" />
      </Sequence>
    </Sequence>

    {/* ③ 판매 수량 — 주인공 */}
    <Sequence from={390} durationInFrames={210}>
      <ZoomShot from={[540, 435, 1.2]} to={[142, 226, 3.2]} frames={30} spot={[100, 112, 85, 92]} />
      <Flash />
      <Sequence from={34}>
        <BigNum to={80} suffix="건" label="쿠팡 링크로 실제 팔린 수량" y={600} />
      </Sequence>
    </Sequence>

    {/* ④ 팔린 금액 */}
    <Sequence from={600} durationInFrames={150}>
      <ZoomShot from={[142, 226, 3.2]} to={[257, 235, 2.8]} frames={22} spot={[195, 112, 148, 92]} />
      <Sequence from={24}>
        <BigNum to={1593159} pre="₩" label="한 달 동안 팔려 나간 금액" y={600} />
      </Sequence>
    </Sequence>

    {/* ⑤ 한 달 수익 — 솔직하게, 힘을 뺀다 */}
    <Sequence from={750} durationInFrames={150}>
      <ZoomShot from={[257, 235, 2.8]} to={[420, 230, 3.0]} frames={22} spot={[372, 112, 100, 92]} />
      <Sequence from={24}>
        <BigNum to={47820} pre="₩" label="한 달 수익 · 크지 않습니다" color={C.paper} y={600} />
      </Sequence>
    </Sequence>

    {/* ⑥ 그래프 끝 급등 */}
    <Sequence from={900} durationInFrames={180}>
      <GraphEnd />
      <Sequence from={44}>
        <Flash />
        <BarCaption text="이제 막, 올라가기 시작했습니다" accent="올라가기" />
      </Sequence>
    </Sequence>

    <Grain opacity={0.08} />
  </AbsoluteFill>
);
