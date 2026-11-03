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

// 검색 화면 브라우저 창(조각02에서 컨펌된 모양): 실제 캡처로 천천히 밀어 들어가 형광펜·밑줄
export type Shot = { page: number; term: string; from: [number, number, number]; to: [number, number, number]; hl?: [number, number, number, number]; lines: string[]; accent?: number };
export const WIN = { x: 60, y: 70, w: 1180, h: 780 };
export const Browser: React.FC<{ shot: Shot; dur: number }> = ({ shot, dur }) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [0, dur * 0.7], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const x0 = shot.from[0] + (shot.to[0] - shot.from[0]) * p;
  const y0 = shot.from[1] + (shot.to[1] - shot.from[1]) * p;
  const w = shot.from[2] + (shot.to[2] - shot.from[2]) * p;
  const s = WIN.w / w;
  const hlA = shot.hl ? ez(f, dur * 0.62, dur * 0.62 + 10) : 0;
  const ulA = shot.hl ? ez(f, dur * 0.62 + 8, dur * 0.62 + 18) : 0;
  return (
    <div style={{ position: "absolute", left: WIN.x, top: WIN.y, width: WIN.w, height: WIN.h, borderRadius: 18, overflow: "hidden", background: "#fff", boxShadow: "0 24px 70px rgba(0,0,0,.28)", border: "1px solid #ddd" }}>
      <div style={{ height: 44, background: "#f1f1f1", display: "flex", flexDirection: "row", alignItems: "center", gap: 10, paddingLeft: 18 }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c }} />)}
        <div style={{ marginLeft: 20, fontFamily: "Pret", fontWeight: 800, fontSize: 22, color: "#555" }}>youtube.com · "{shot.term}"</div>
      </div>
      <div style={{ position: "absolute", left: 0, top: 44, width: WIN.w, height: WIN.h - 44, overflow: "hidden" }}>
        <Img src={staticFile(`srch/s${shot.page}.jpg`)} style={{ position: "absolute", width: 1920 * s, left: -x0 * s, top: -y0 * s }} />
        {shot.hl && <>
          <div style={{ position: "absolute", left: (shot.hl[0] - x0) * s - 8, top: (shot.hl[1] - y0) * s - 6, width: (shot.hl[2] * s + 16) * hlA, height: shot.hl[3] * s + 12,
            background: "rgba(255,214,0,.42)", borderRadius: 6 }} />
          <div style={{ position: "absolute", left: (shot.hl[0] - x0) * s, top: (shot.hl[1] + shot.hl[3] - y0) * s + 10, width: shot.hl[2] * s * ulA, height: 9, background: "#E5484D", borderRadius: 5 }} />
        </>}
      </div>
    </div>
  );
};
export const SideText: React.FC<{ lines: string[]; term: string; accent?: number }> = ({ lines, term, accent }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 1290, top: 150, width: 600 }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: "#9a958d", opacity: ez(f, 0, 10) }}>검색어 · {term}</div>
      {lines.map((l, k) => {
        const st = 8 + k * 14;
        const a = ez(f, st, st + 10);
        const sc = interpolate(f, [st, st + 5, st + 10], [1.5, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <div key={k} style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 84, lineHeight: 1.12, marginTop: k ? 6 : 18, color: k === accent ? OR : INK,
          opacity: a, transform: `scale(${sc})`, transformOrigin: "0 50%", wordBreak: "keep-all" }}>{l}</div>;
      })}
    </div>
  );
};
