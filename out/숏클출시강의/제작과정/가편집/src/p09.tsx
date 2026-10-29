import React from "react";
import { AbsoluteFill, Audio, Composition, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각09 '만드는 과정이 보인다(s20) + 보면서 고친다(s21)'.
// 진화: 진행판을 직접 그려, 필재가 '준비 확인·소재·제품·자료조사·대본·장면·목소리·렌더'를 부르는 바로 그 순간 한 칸씩 불이 들어온다.
// 품질 관문 6개도 말하는 순간 체크, '하나라도 걸리면 그 단계만 다시' 를 실제로 대본 칸만 되돌아가 다시 켜지는 모습으로.
const PAD = 0.4;
const SC = [20, 21].map((i) => (PLAN as any)[i]);
const OFF = [0, SC[0].sec + PAD];
const END = OFF[1] + SC[1].sec + PAD;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const LF: React.FC<{ r: (f: number) => React.ReactNode }> = ({ r }) => <>{r(useCurrentFrame())}</>;
const sq = (a: number, b: number, el: React.ReactNode | ((f: number) => React.ReactNode)) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{typeof el === "function" ? <LF r={el} /> : el}</Sequence>;
const pop = (f: number, at: number, k = 1.5) => interpolate(f, [at, at + 5, at + 10], [k, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const STAGES: [number, string][] = [[11.53, "준비 확인"], [12.56, "소재"], [13.04, "제품"], [13.51, "자료조사"], [13.99, "대본"], [14.37, "장면"], [14.79, "목소리"], [15.24, "렌더"]];
const GATES: [number, string][] = [[21.62, "규격"], [22.09, "화면"], [22.49, "자막"], [22.82, "목소리"], [23.29, "대본"], [23.7, "장면"]];

// 진행판: base = 이 시퀀스 시작의 s20 초
const Board: React.FC<{ base: number; gate?: boolean; redo?: boolean }> = ({ base, gate, redo }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const redoT = 29.93, redoT2 = 31.31;
  return (
    <AbsoluteFill style={{ background: "#F4F1EA" }}>
      <div style={{ position: "absolute", left: 90, top: 70, width: 1740, height: 780, background: "#fff", borderRadius: 26, boxShadow: "0 20px 60px rgba(0,0,0,.12)", border: "1px solid #e5e0d6" }}>
        <div style={{ position: "absolute", left: 40, top: 26, fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: INK }}>숏클 진행판 <span style={{ color: "#9a958d", fontSize: 30 }}>· "해외 화장품 만들어 줘"</span></div>
        <div style={{ position: "absolute", left: 40, top: 120, display: "flex", flexDirection: "column", gap: 14 }}>
          {STAGES.map(([t, name], k) => {
            let on = now >= t;
            const back = redo && ((name === "대본" && now >= redoT && now < redoT + 1.2) || (name === "장면" && now >= redoT2 && now < redoT2 + 1.2));
            if (back) on = false;
            const at = S(t - base);
            return <div key={k} style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 20, padding: "8px 18px", borderRadius: 14, width: 620,
              background: back ? "#FFF1E6" : on ? "#E8F7EF" : "#F6F4EF", border: `3px solid ${back ? OR : on ? "#2F9E6E" : "#e5e0d6"}`, transform: `scale(${on && !back ? pop(f, at, 1.08) : 1})`, transformOrigin: "0 50%" }}>
              <div style={{ width: 44, height: 44, borderRadius: 22, background: back ? OR : on ? "#2F9E6E" : "#d8d2c6", color: "#fff", fontFamily: "Pret", fontWeight: 800, fontSize: 28, textAlign: "center", lineHeight: "44px" }}>{back ? "↺" : on ? "✓" : k + 1}</div>
              <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: on || back ? INK : "#a8a296" }}>{name}{back ? "  다시" : ""}</div>
            </div>;
          })}
        </div>
        {gate && <div style={{ position: "absolute", left: 760, top: 120, width: 940 }}>
          <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 52, color: INK, opacity: ez(f, S(19.42 - base), S(19.42 - base) + 8) }}>품질 관문</div>
          <div style={{ display: "flex", flexDirection: "row", flexWrap: "wrap", gap: 16, marginTop: 24 }}>
            {GATES.map(([t, g], k) => now >= t && <div key={k} style={{ padding: "18px 34px", borderRadius: 40, background: "#E8F7EF", border: "3px solid #2F9E6E", fontFamily: "Pret", fontWeight: 800, fontSize: 50, color: "#1F6B4A",
              transform: `scale(${pop(f, S(t - base))})` }}>✓ {g}</div>)}
          </div>
          {now >= 24.36 && <div style={{ marginTop: 40, padding: "26px 34px", borderRadius: 20, background: "#FFF6E8", border: `4px solid ${OR}`, fontFamily: "Pret", fontWeight: 800, fontSize: 52, color: INK,
            transform: `scale(${pop(f, S(24.36 - base))})`, transformOrigin: "0 50%" }}>👀 마지막: 클로드가 장면마다 눈으로</div>}
          {now >= 26.48 && <div style={{ marginTop: 26, fontFamily: "Pen", fontSize: 76, color: OR, opacity: ez(f, S(26.48 - base), S(26.48 - base) + 10) }}>걸리면 그 단계로만 돌아가 다시</div>}
        </div>}
      </div>
    </AbsoluteFill>
  );
};

// 까만 채팅창에서 글자만 보며 기다리던 기억
const Waiting: React.FC = () => {
  const f = useCurrentFrame();
  const dots = ".".repeat((Math.floor(f / 10) % 3) + 1);
  return (
    <AbsoluteFill style={{ background: "#202124" }}>
      <div style={{ position: "absolute", left: 220, top: 280, fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: "#777" }}>✻ Working{dots}</div>
      <div style={{ position: "absolute", left: 220, top: 380, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: "#555" }}>지금 뭐 하는 중인지 모름</div>
      <Hand text="그 까만 창, 기억나시죠" x={900} y={560} size={110} color="#ddd" underline={false} />
    </AbsoluteFill>
  );
};

// 수정 지옥 말풍선이 마구 쌓임(조각05 기억 소환)
const Hell: React.FC = () => {
  const f = useCurrentFrame();
  const b = ["세 번째 자막", "아니 그거 말고", "아까 걸로", "다시", "그거 말고…"];
  return (
    <AbsoluteFill style={{ background: "#202124" }}>
      {b.map((t, k) => f >= k * 9 && <div key={k} style={{ position: "absolute", left: 160 + (k * 317) % 1300, top: 140 + (k * 173) % 560, padding: "20px 34px", background: "#3B3F45", borderRadius: 26,
        fontFamily: "Pret", fontWeight: 800, fontSize: 60, color: "#eee", transform: `rotate(${(k % 2 ? 4 : -5)}deg) scale(${pop(f, k * 9)})` }}>"{t}"</div>)}
      <Slam text="수정 지옥" at={S(0.6)} y={760} size={110} color="#E5484D" />
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const b = OFF[1];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* s20 */}
      {sq(0, 1.93, <AbsoluteFill style={{ background: PAPER }}><Slam text="이제 만들 차례" at={S(0.2)} y={360} size={170} /></AbsoluteFill>)}
      {sq(1.93, 4.81, (lf: number) => <AbsoluteFill style={{ background: "#141519" }}>
        <div style={{ position: "absolute", left: 360, top: 420, width: 1200, padding: "30px 40px", border: "3px solid #555", borderRadius: 18, fontFamily: "Consolas, monospace", fontSize: 60, color: "#eee" }}>
          <span style={{ color: OR }}>&gt; </span>{"해외 화장품 만들어 줘".slice(0, Math.floor(lf / 2))}</div>
        <Slam text="한 줄" at={S(1.6)} y={620} size={120} color={OR} /></AbsoluteFill>)}
      {sq(4.81, 10.11, <Waiting />)}
      {sq(10.11, 19.42, <Board base={10.11} />)}
      {sq(19.42, 32.03, <Board base={19.42} gate redo />)}
      {sq(32.03, 33.02, <AbsoluteFill style={{ background: PAPER }}><Slam text="아시겠죠?" at={1} y={380} size={170} /></AbsoluteFill>)}
      {sq(33.02, 36.91, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 200, top: 150, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: "#9a958d" }}>출시 라이브 채팅</div>
        <div style={{ position: "absolute", left: 200, top: 230, padding: "30px 46px", background: "#fff", border: "4px solid #ddd", borderRadius: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 76, color: INK }}>"과정을 볼 수 있으니 너무 좋네요"</div>
        <Slam text="그래서 만들었습니다" at={S(2.44)} y={520} size={120} color={OR} /></AbsoluteFill>)}
      {sq(36.91, 41.41, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 200, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 90, color: "#9a958d" }}>기다리는 건 괜찮은데</div>
        <Slam text="모르고 기다리는 게 힘들다" at={S(1.2)} y={340} size={110} />
        <Slam text="한 편 30~40분" at={S(39.91 - 36.91)} y={560} size={120} color={OR} /></AbsoluteFill>)}
      {sq(41.41, b, <Ink n="m_relax" side="right"><Hand text={"그동안\n제가 하는 일은\n없습니다"} x={150} y={180} size={150} color={OR} /></Ink>)}
      {/* s21 보면서 고친다 */}
      {sq(b, b + 3.94, <Hell />)}
      {sq(b + 3.94, b + 17.05, <AbsoluteFill style={{ background: "#F4F1EA" }}>
        <OffthreadVideo src={staticFile("p9/r1.mp4")} muted playbackRate={1.5} style={{ width: 1920, height: 1080 }} />
        <div style={{ position: "absolute", left: 60, top: 40, padding: "12px 26px", background: OR, borderRadius: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: "#fff" }}>완성본을 틀어 놓고 → 짚어서 고친다</div></AbsoluteFill>)}
      {sq(b + 17.05, b + 22.42, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 200, top: 150, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: "#9a958d" }}>출시 라이브 채팅 · 두 번째로 많았던 반응</div>
        <div style={{ position: "absolute", left: 200, top: 230, padding: "30px 46px", background: "#fff", border: "4px solid #ddd", borderRadius: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 84, color: INK }}>"나의 과거가 떠오른다"</div>
        <Slam text="그 과거, 여기서 끝" at={S(3.4)} y={520} size={130} color={OR} /></AbsoluteFill>)}
      {sq(b + 22.42, END, <AbsoluteFill style={{ background: "#141519" }}>
        <Slam text="이게 진짜 딸깍" at={S(0.2)} y={200} size={170} color={OR} />
        <Slam text="만드는 것도 한 줄" at={S(2.44)} y={480} size={100} color="#fff" />
        <Slam text="고치는 것도 딱 한 번" at={S(4.0)} y={630} size={100} color="#6EE7B7" /></AbsoluteFill>)}
      <Audio src={staticFile("full/s20.mp3")} />
      <Sequence from={S(b)}><Audio src={staticFile("full/s21.mp3")} /></Sequence>
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P09" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
