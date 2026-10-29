import React from "react";
import {
  AbsoluteFill, Composition, Easing, Sequence, OffthreadVideo, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";

// Art direction (atelier, hand-authored): dark ink #0b0a11, cream #f3ece0, orange #f0902a, teal #2ee6c9.
// Signature device: the phone frame appears only in the two bookend beats. Motion = ease-out only, no glitch.
const INK = "#0b0a11", CREAM = "#f3ece0", ORANGE = "#f0902a", TEAL = "#2ee6c9";
const FPS = 30;
const S = (sec: number) => Math.round(sec * FPS);
const OUT = Easing.out(Easing.cubic);
const ease = (f: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(f, [a, b], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: OUT });

const FontFaces = () => (
  <style>{`
  @font-face{font-family:'PretendardK';font-weight:400;src:url('${staticFile("fonts/Pretendard-Regular.otf")}')}
  @font-face{font-family:'PretendardK';font-weight:600;src:url('${staticFile("fonts/Pretendard-SemiBold.otf")}')}
  @font-face{font-family:'PretendardK';font-weight:700;src:url('${staticFile("fonts/Pretendard-Bold.otf")}')}
  @font-face{font-family:'PretendardK';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}
  `}</style>
);
const base: React.CSSProperties = { fontFamily: "PretendardK", wordBreak: "keep-all", letterSpacing: "-0.02em" };

// scene wrapper: fade in / fade out (ease-out), overlap handled by sequence extents
const Scene: React.FC<{ dur: number; children: React.ReactNode }> = ({ dur, children }) => {
  const f = useCurrentFrame();
  const o = Math.min(ease(f, 0, 10), 1 - ease(f, dur - 10, dur));
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};

const Phone: React.FC<{ x: number }> = ({ x }) => {
  const f = useCurrentFrame();
  const y = ease(f, 0, 24, 40, 0);
  const W = 506, H = 900;
  return (
    <div style={{
      position: "absolute", left: x - (W + 28) / 2, top: (1080 - (H + 28)) / 2 + y,
      width: W + 28, height: H + 28, borderRadius: 66, background: "#1b1a24",
      boxShadow: `0 0 0 2px #2b2a38, 0 30px 80px rgba(46,230,201,0.12)`, padding: 14,
    }}>
      <div style={{ width: W, height: H, borderRadius: 52, overflow: "hidden", background: "#000" }}>
        <OffthreadVideo src={staticFile("source_kopack.mp4")} startFrom={0} volume={0.126}
          style={{ width: W, height: H, objectFit: "cover" }} />
      </div>
    </div>
  );
};

// 1) 0-4s: finished short in a phone frame + headline
const S1: React.FC = () => {
  const f = useCurrentFrame();
  const L = (a: number): React.CSSProperties => ({ opacity: ease(f, a, a + 14), transform: `translateY(${ease(f, a, a + 18, 28, 0)}px)` });
  return (
    <Scene dur={S(4) + 10}>
      <Phone x={600} />
      <div style={{ ...base, position: "absolute", left: 1010, top: 270, width: 800, color: CREAM, fontWeight: 800, fontSize: 112, lineHeight: 1.22 }}>
        <div style={L(10)}>이 쇼츠,</div>
        <div style={{ ...L(20), color: ORANGE }}>말 한 줄로</div>
        <div style={L(30)}>나왔습니다</div>
      </div>
    </Scene>
  );
};

// 2) 4-7s: beige question card
const S2: React.FC = () => {
  const f = useCurrentFrame();
  const sc = ease(f, 0, 22, 0.94, 1);
  return (
    <Scene dur={S(3) + 10}>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{
          ...base, width: 1240, height: 560, borderRadius: 56, background: CREAM, transform: `scale(${sc})`,
          display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", gap: 28,
        }}>
          <div style={{ width: 120, height: 12, borderRadius: 6, background: ORANGE, opacity: ease(f, 8, 24) }} />
          <div style={{ color: INK, fontWeight: 800, fontSize: 180, opacity: ease(f, 4, 22) }}>어떻게요?</div>
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

// 3) 7-18s: prompt box typing -> send -> status chip changes
const PROMPT = "해외 화장품 쇼츠 만들어줘";
const STEPS = ["원본 찾는 중…", "대본 쓰는 중…", "장면 맞추는 중…", "완성 ✓"];
const S3: React.FC = () => {
  const f = useCurrentFrame(); // 0 == 7.0s
  const typeStart = S(0.6), typeEnd = S(2.6);
  const n = Math.round(interpolate(f, [typeStart, typeEnd], [0, PROMPT.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const sendT = S(3.2);
  const press = f >= sendT && f < sendT + 6 ? 0.94 : 1;
  const sent = f >= sendT;
  const caretOn = !sent && Math.floor(f / 15) % 2 === 0;
  const stepStarts = [S(3.6), S(5.9), S(8.0), S(9.9)]; // 10.6s, 12.9s, 15.0s, 16.9s (abs)
  let idx = -1; stepStarts.forEach((t, i) => { if (f >= t) idx = i; });
  const chipF = idx >= 0 ? f - stepStarts[idx] : 0;
  const done = idx === 3;
  const spin = (f * 9) % 360;
  return (
    <Scene dur={S(11) + 10}>
      <div style={{ ...base, position: "absolute", left: 0, right: 0, top: 0, bottom: 0 }}>
        <div style={{ position: "absolute", left: 310, top: 330, width: 1300, height: 190, borderRadius: 48, background: CREAM,
          display: "flex", alignItems: "center", padding: "0 44px", gap: 24, opacity: ease(f, 0, 16),
          transform: `translateY(${ease(f, 0, 20, 24, 0)}px)` }}>
          <div style={{ flex: 1, fontSize: 80, fontWeight: 700, color: INK, whiteSpace: "nowrap" }}>
            {PROMPT.slice(0, n)}
            <span style={{ display: "inline-block", width: 6, height: 76, background: ORANGE, marginLeft: 6, verticalAlign: "-8px", opacity: caretOn ? 1 : 0 }} />
          </div>
          <div style={{ width: 112, height: 112, borderRadius: 56, background: ORANGE, display: "flex", justifyContent: "center", alignItems: "center",
            transform: `scale(${press})`, flex: "none" }}>
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke={INK} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
          </div>
        </div>
        {idx >= 0 && (
          <div key={idx} style={{
            position: "absolute", left: 310, top: 640, height: 150, borderRadius: 75, padding: "0 56px",
            display: "flex", alignItems: "center", gap: 28, fontSize: 84, fontWeight: 700,
            color: done ? INK : CREAM, background: done ? TEAL : "#1b1a24",
            boxShadow: done ? "none" : `inset 0 0 0 3px ${TEAL}55`,
            opacity: ease(chipF, 0, 12), transform: `translateY(${ease(chipF, 0, 16, 20, 0)}px)`,
          }}>
            {!done && (
              <svg width="64" height="64" viewBox="0 0 64 64" style={{ transform: `rotate(${spin}deg)` }}>
                <circle cx="32" cy="32" r="24" fill="none" stroke={`${TEAL}33`} strokeWidth="8" />
                <path d="M32 8a24 24 0 0 1 24 24" fill="none" stroke={TEAL} strokeWidth="8" strokeLinecap="round" />
              </svg>
            )}
            <span>{STEPS[idx]}</span>
          </div>
        )}
      </div>
    </Scene>
  );
};

// 4) 18-25s: replay + closing line + brand
const S4: React.FC = () => {
  const f = useCurrentFrame();
  const L = (a: number): React.CSSProperties => ({ opacity: ease(f, a, a + 14), transform: `translateY(${ease(f, a, a + 18, 28, 0)}px)` });
  return (
    <Scene dur={S(7)}>
      <Phone x={600} />
      <div style={{ ...base, position: "absolute", left: 1010, top: 300, width: 800, color: CREAM }}>
        <div style={{ ...L(10), fontWeight: 800, fontSize: 112, lineHeight: 1.22 }}>
          <div>말 한 줄이면</div><div style={{ color: ORANGE }}>됩니다</div>
        </div>
        <div style={{ ...L(40), marginTop: 56, fontWeight: 700, fontSize: 88, color: TEAL }}>숏클메이커</div>
      </div>
    </Scene>
  );
};

const Main: React.FC = () => (
  <AbsoluteFill style={{ background: INK }}>
    <FontFaces />
    <Sequence from={0} durationInFrames={S(4) + 10}><S1 /></Sequence>
    <Sequence from={S(4)} durationInFrames={S(3) + 10}><S2 /></Sequence>
    <Sequence from={S(7)} durationInFrames={S(11) + 10}><S3 /></Sequence>
    <Sequence from={S(18)} durationInFrames={S(7)}><S4 /></Sequence>
  </AbsoluteFill>
);

const Root: React.FC = () => (
  <Composition id="HybridKopack" component={Main} durationInFrames={S(25)} fps={FPS} width={1920} height={1080} />
);
registerRoot(Root);
