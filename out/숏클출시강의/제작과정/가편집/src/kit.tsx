import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";

// 조각들이 같이 쓰는 부품(조각02 에서 사장님 컨펌받은 모양 그대로). 새 조각은 이걸 import 한다.
export const FPS = 30;
export const S = (s: number) => Math.round(s * FPS);
export const PAPER = "#FBF8F1", INK = "#1C1B19", OR = "#E07A2B";
export const ez = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
export const slam = (f: number, at: number) =>
  interpolate(f, [at, at + 5, at + 10], [2.0, 0.93, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
export type Cap = [number, number, string];

export const Fonts = () => (
  <style>{`@font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}
  @font-face{font-family:'Pen';src:url('${staticFile("fonts/NanumPenScript.ttf")}')}`}</style>
);

// 나레이션 자막(화면 아래 가운데 — 장면 글자는 이 자리에 두지 않는다)
export const Caption: React.FC<{ caps: Cap[] }> = ({ caps }) => {
  const now = useCurrentFrame() / FPS;
  const c = caps.find((x, k) => now >= x[0] && now < (caps[k + 1] ? caps[k + 1][0] : x[1] + 0.6));
  if (!c) return null;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 50, display: "flex", justifyContent: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 46, color: "#fff", background: "rgba(0,0,0,.72)", padding: "12px 30px", borderRadius: 14, maxWidth: 1640, textAlign: "center", wordBreak: "keep-all" }}>{c[2]}</div>
    </div>
  );
};

// 손그림 컷: 선화(g_)가 위→아래로 드러나고 컬러(c_)가 번짐 + 느린 밀기. draw=false 면 그려진 채로.
export const Ink: React.FC<{ n: string; side?: "left" | "right" | "center"; size?: number; draw?: boolean; children?: React.ReactNode }> =
  ({ n, side = "left", size = 990, draw = true, children }) => {
    const f = useCurrentFrame();
    const reveal = draw ? ez(f, 0, 24) : 1;
    const color = draw ? ez(f, 33, 45) : 1;
    const z = interpolate(f, [0, 300], [1.0, 1.06], { extrapolateRight: "clamp" });
    const left = side === "left" ? 100 : side === "right" ? 1920 - 100 - size : (1920 - size) / 2;
    return (
      <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left, top: -30, width: size, height: size, transform: `scale(${z})`, transformOrigin: "50% 60%" }}>
          <Img src={staticFile(`hero/g_${n}.png`)} style={{ position: "absolute", inset: 0, width: size, height: size, mixBlendMode: "multiply", clipPath: `inset(0 0 ${(1 - reveal) * 100}% 0)` }} />
          <Img src={staticFile(`hero/c_${n}.png`)} style={{ position: "absolute", inset: 0, width: size, height: size, opacity: color, mixBlendMode: "multiply" }} />
        </div>
        {children}
      </AbsoluteFill>
    );
  };

// 손글씨: 글자마다 튀어나오고 기울기 제각각, 다 쓰면 주황 밑줄 + 숨쉬기
export const Hand: React.FC<{ text: string; x: number; y: number; size?: number; color?: string; delay?: number; underline?: boolean }> =
  ({ text, x, y, size = 160, color = INK, delay = 6, underline = true }) => {
    const f = useCurrentFrame();
    const chars = Array.from(text);
    const doneAt = delay + chars.length * 2;
    const breathe = 1 + 0.015 * Math.sin((f - doneAt) / 14) * (f > doneAt ? 1 : 0);
    const ul = ez(f, doneAt + 2, doneAt + 12);
    return (
      <div style={{ position: "absolute", left: x, top: y, maxWidth: 900, transform: `scale(${breathe}) rotate(-2deg)`, transformOrigin: "0 50%" }}>
        <div style={{ fontFamily: "Pen", fontSize: size, color, lineHeight: 1.08, whiteSpace: "pre-wrap", wordBreak: "keep-all" }}>
          {chars.map((c, k) => {
            const st = delay + k * 2;
            const a = ez(f, st, st + 6);
            const pop = interpolate(f, [st, st + 4, st + 9], [0.4, 1.25, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const rot = ((k * 37) % 11) - 5;
            return c === "\n" ? <br key={k} /> : <span key={k} style={{ display: "inline-block", opacity: a, transform: `scale(${pop}) rotate(${rot * (1 - a * 0.6)}deg)`, minWidth: c === " " ? size * 0.3 : undefined }}>{c}</span>;
          })}
        </div>
        {underline && <svg width={700} height={40} style={{ display: "block", marginTop: -6 }}>
          <path d="M6 24 C 160 6, 360 36, 690 14" stroke={OR} strokeWidth={10} fill="none" strokeLinecap="round" strokeDasharray={720} strokeDashoffset={720 * (1 - ul)} />
        </svg>}
      </div>
    );
  };

// 큰 글자 '쾅'(키네틱): at 프레임에 넘쳐 들어와 제자리
export const Slam: React.FC<{ text: string; at: number; x?: number; y: number; size?: number; color?: string; rot?: number; center?: boolean }> =
  ({ text, at, x = 0, y, size = 220, color = INK, rot = 0, center = true }) => {
    const f = useCurrentFrame();
    if (f < at) return null;
    return <div style={{ position: "absolute", left: center ? 0 : x, right: center ? 0 : undefined, top: y, textAlign: center ? "center" : "left", fontFamily: "Pret", fontWeight: 800, fontSize: size, color,
      letterSpacing: -4, transform: `scale(${slam(f, at)}) rotate(${rot}deg)`, transformOrigin: center ? "50% 50%" : "0 50%" }}>{text}</div>;
  };
