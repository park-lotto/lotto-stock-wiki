import React from "react";
import {AbsoluteFill, Composition, OffthreadVideo, Sequence, staticFile, interpolate, Easing, registerRoot, useCurrentFrame, continueRender, delayRender} from "remotion";

const FPS = 30;
const CREAM = "#f5ecd9", ORANGE = "#f0902a", TEAL = "#2ee6c9", BLACK = "#0b0b0b";

// 1920x1080 원본 좌표. step: 왼쪽 단계표 활성 칸 (x,y,w,h)
const SEGS = [
  {src: 4,    text: "원본을 찾는 중입니다",     box: [14, 180, 201, 40]},
  {src: 22,   text: "원본을 정리하는 중입니다", box: [14, 315, 201, 40]},
  {src: 32,   text: "대본을 쓰는 중입니다",     box: [14, 405, 201, 40]},
  {src: 50,   text: "장면을 맞추는 중입니다",   box: [14, 495, 201, 40]},
  {src: 94,   text: "영상을 만드는 중입니다",   box: [14, 540, 201, 62]},
  {src: 118,  text: "완성본이 나왔습니다",       box: [14, 606, 201, 40]},
];
const SEG_S = 3.5, CARD_S = 2;
const SEG_F = Math.round(SEG_S * FPS), CARD_F = CARD_S * FPS;
export const TOTAL = CARD_F * 2 + SEG_F * SEGS.length;

const FONT = "Pretendard";
const Fonts: React.FC = () => {
  const faces = [["Bold",700],["ExtraBold",800],["SemiBold",600]] as const;
  const css = faces.map(([n,w]) => `@font-face{font-family:'${FONT}';font-weight:${w};src:url('${staticFile(`fonts/Pretendard-${n}.otf`)}');}`).join("\n");
  return <style>{css}</style>;
};

const Card: React.FC<{text: string; color: string; sub?: string}> = ({text, color}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8, CARD_F - 8, CARD_F], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const y = interpolate(f, [0, 14], [18, 0], {easing: Easing.out(Easing.cubic), extrapolateRight: "clamp"});
  const w = interpolate(f, [6, 26], [0, 420], {easing: Easing.out(Easing.cubic), extrapolateRight: "clamp", extrapolateLeft: "clamp"});
  return (
    <AbsoluteFill style={{background: BLACK, alignItems: "center", justifyContent: "center", fontFamily: FONT}}>
      <div style={{opacity: o, transform: `translateY(${y}px)`, textAlign: "center"}}>
        <div style={{fontSize: 140, fontWeight: 800, color: CREAM, letterSpacing: "-0.02em"}}>{text}</div>
        <div style={{height: 8, width: w, background: color, margin: "28px auto 0", borderRadius: 4}} />
      </div>
    </AbsoluteFill>
  );
};

const Seg: React.FC<{i: number}> = ({i}) => {
  const s = SEGS[i];
  const f = useCurrentFrame();
  // 단계가 바뀌는 순간: 0.3초 뒤 확대(ease-out 0.5초) -> 1.6초 유지 -> 천천히 복귀
  const scale = interpolate(f, [9, 24, 66, 96], [1, 1.45, 1.45, 1], {easing: Easing.out(Easing.cubic), extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const boxO = interpolate(f, [0, 8, SEG_F - 10, SEG_F], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const subO = interpolate(f, [4, 14, SEG_F - 8, SEG_F], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const subY = interpolate(f, [4, 16], [14, 0], {easing: Easing.out(Easing.cubic), extrapolateRight: "clamp", extrapolateLeft: "clamp"});
  const [bx, by, bw, bh] = s.box;
  const final = i === SEGS.length - 1;
  return (
    <AbsoluteFill style={{background: BLACK}}>
      <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: "0px 380px"}}>
        <OffthreadVideo src={staticFile("src.mp4")} startFrom={Math.round(s.src * FPS)} muted style={{width: 1920, height: 1080}} />
        <div style={{position: "absolute", left: bx - 3, top: by - 3, width: bw + 6, height: bh + 6, border: `5px solid ${final ? TEAL : ORANGE}`, borderRadius: 10, opacity: boxO}} />
      </AbsoluteFill>
      <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: 70, fontFamily: FONT}}>
        <div style={{opacity: subO, transform: `translateY(${subY}px)`, background: "rgba(11,11,11,0.86)", padding: "18px 46px", borderRadius: 18, border: `3px solid ${final ? TEAL : ORANGE}`, fontSize: 72, fontWeight: 700, color: CREAM, letterSpacing: "-0.01em"}}>
          {s.text}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Main: React.FC = () => (
  <AbsoluteFill style={{background: BLACK}}>
    <Fonts />
    <Sequence from={0} durationInFrames={CARD_F}><Card text="숏클 진행판" color={ORANGE} /></Sequence>
    {SEGS.map((_, i) => (
      <Sequence key={i} from={CARD_F + i * SEG_F} durationInFrames={SEG_F}><Seg i={i} /></Sequence>
    ))}
    <Sequence from={CARD_F + SEG_F * SEGS.length} durationInFrames={CARD_F}><Card text="말 한 줄이면 됩니다" color={TEAL} /></Sequence>
  </AbsoluteFill>
);

const Root: React.FC = () => (
  <Composition id="ScreenDemoKo" component={Main} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080} />
);
registerRoot(Root);
