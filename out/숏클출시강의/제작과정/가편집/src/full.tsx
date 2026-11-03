import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, Loop, OffthreadVideo, Sequence, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";
import PLAN from "../public/plan.json";

// 숏클 1편 전체 가편집(임시 음성). 장면 길이 = 그 장면 음성 길이.
// 영상이 짧으면 반복, 여러 개면 시간을 나눠 차례로. 영상이 아직 없으면 '스타일 자리' 카드.
// 왼쪽 위 이름표 = 장면 이름 · 모션 스타일 (사장님이 배치를 한눈에 보게).
const FPS = 30, S = (s: number) => Math.round(s * FPS);
const BG = "#EFE9DF", INK = "#1C1B19", OR = "#E07A2B", SUB = "#6B6660";
const ez = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
type V = { src: string; sec: number; at: number };
type Cap = [number, number, string];
type Sc = { i: number; name: string; style: string; sec: number; caps: Cap[]; vids: V[] };
const P = PLAN as Sc[];
const PAD = 0.4;

const Fonts = () => (
  <style>{`
  @font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}
  @font-face{font-family:'Pret';font-weight:700;src:url('${staticFile("fonts/Pretendard-Bold.otf")}')}
  @font-face{font-family:'Serif';src:url('${staticFile("fonts/GowunBatang.ttf")}')}
  `}</style>
);

// 자막 = 필재 음성의 실제 발음 시각(build_plan.py 가 align.json 에서 뽑은 [시작, 끝, 글]).
const Caption: React.FC<{ caps: Cap[] }> = ({ caps }) => {
  const t = useCurrentFrame() / FPS;
  const c = caps.find((x, k) => t >= x[0] && t < (caps[k + 1] ? caps[k + 1][0] : x[1] + 0.6));
  if (!c) return null;
  const cur = c[2];
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 50, display: "flex", justifyContent: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 46, color: "#fff", background: "rgba(0,0,0,.72)", padding: "12px 30px", borderRadius: 14, maxWidth: 1640, textAlign: "center", wordBreak: "keep-all", lineHeight: 1.35 }}>{cur}</div>
    </div>
  );
};

const Tag: React.FC<{ s: Sc }> = ({ s }) => (
  <div style={{ position: "absolute", left: 28, top: 24, fontFamily: "Pret", fontWeight: 700, fontSize: 24, color: "#fff", background: "rgba(28,27,25,.78)", padding: "8px 16px", borderRadius: 10 }}>
    <span style={{ color: OR }}>{s.name}</span> · {s.style}
  </div>
);

const Placeholder: React.FC<{ s: Sc }> = ({ s }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: BG, justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 30, color: OR, opacity: ez(f, 0, 12) }}>제작 예정 장면</div>
      <div style={{ fontFamily: "Serif", fontSize: 84, color: INK, marginTop: 16, opacity: ez(f, 4, 18), wordBreak: "keep-all", maxWidth: 1500 }}>{s.style}</div>
      <div style={{ fontFamily: "Pret", fontWeight: 700, fontSize: 30, color: SUB, marginTop: 20, opacity: ez(f, 8, 22) }}>{s.name}</div>
    </AbsoluteFill>
  );
};

const Visual: React.FC<{ s: Sc; dur: number }> = ({ s, dur }) => {
  if (!s.vids.length) return <Placeholder s={s} />;
  // 영상 전환 = 나레이션 기준 구절이 들리는 시각(v.at, build_plan.py ANCHOR)
  const st = s.vids.map((v) => S(v.at));
  return (
    <>
      {s.vids.map((v, k) => (
        <Sequence key={k} from={st[k]} durationInFrames={Math.max(1, (k === s.vids.length - 1 ? dur : st[k + 1]) - st[k])}>
          <AbsoluteFill style={{ background: "#000" }}>
            <Loop durationInFrames={Math.max(1, S(v.sec) - 1)}>
              <OffthreadVideo src={staticFile(v.src)} muted style={{ width: 1920, height: 1080, objectFit: "contain" }} />
            </Loop>
          </AbsoluteFill>
        </Sequence>
      ))}
    </>
  );
};

const Main: React.FC = () => {
  let t = 0;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <Fonts />
      {P.map((s) => {
        const dur = S(s.sec + PAD); const from = t; t += dur;
        return (
          <Sequence key={s.i} from={from} durationInFrames={dur}>
            <Visual s={s} dur={dur} />
            <Audio src={staticFile(`full/s${String(s.i).padStart(2, "0")}.mp3`)} />
            <Caption caps={s.caps} />
            <Tag s={s} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
const TOTAL = P.reduce((a, s) => a + S(s.sec + PAD), 0);
registerRoot(() => <Composition id="FullRough" component={Main} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080} />);
