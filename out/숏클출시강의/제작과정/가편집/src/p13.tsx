import React from "react";
import { AbsoluteFill, Audio, Composition, Img, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각13 '그 휴대폰들 — 오프닝 회수(s27) + 질문·CTA(s28)'. 마지막 조각.
// 진화: 오프닝에서 흑백이던 공장을 이번엔 처음부터 컬러로 돌려 '회수'하고, 라이브 실제 질문 3개는 Q카드가 뒤집히며 답이 나온다.
// 끝은 '오늘 하실 일' 3단계(프리셋 → 한 줄 → 딸깍)가 말하는 순간 체크되고, 고정 댓글 모양으로 신청서 위치를 보여 준다.
const PAD = 0.4;
const SC = [27, 28].map((i) => (PLAN as any)[i]);
const OFF = [0, SC[0].sec + PAD];
const END = OFF[1] + SC[1].sec + 1.2;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const LF: React.FC<{ r: (f: number) => React.ReactNode }> = ({ r }) => <>{r(useCurrentFrame())}</>;
const sq = (a: number, b: number, el: React.ReactNode | ((f: number) => React.ReactNode)) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{typeof el === "function" ? <LF r={el} /> : el}</Sequence>;
const pop = (f: number, at: number, k = 1.4) => interpolate(f, [at, at + 5, at + 10], [k, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

// 공장(컬러) + 숫자
const Factory: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const z = interpolate(f, [0, 300], [1.15, 1.0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      <OffthreadVideo src={staticFile("op/factory.mp4")} muted style={{ width: 1920, height: 1080, objectFit: "cover", transform: `scale(${z})` }} />
      <AbsoluteFill style={{ background: "rgba(0,0,0,.45)" }} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 150, textAlign: "center", fontFamily: "Pen", fontSize: 96, color: "#fff", textShadow: "0 4px 20px #000" }}>처음에 보신 그 휴대폰들</div>
      {now >= 3.85 && <Slam text="채널 50개" at={S(3.85 - base)} y={330} size={180} color="#FFD36E" />}
      {now >= 7.87 && <div style={{ position: "absolute", left: 0, right: 0, top: 600, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 60, color: "#fff", opacity: ez(f, S(7.87 - base), S(7.87 - base) + 10) }}>
        채널 개설부터 하나하나 · 하루아침이 아니었다</div>}
    </AbsoluteFill>
  );
};

// Q카드: 질문 → 뒤집혀 답
const QA: React.FC<{ base: number; q: string; n: number; tA: number; answer: React.ReactNode }> = ({ base, q, n, tA, answer }) => {
  const f = useCurrentFrame();
  const flip = ez(f, S(tA - base), S(tA - base) + 10);
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 120, top: 50, fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: "#9a958d" }}>라이브에서 실제로 받은 질문 <span style={{ color: OR }}>{n}/3</span></div>
      <div style={{ position: "absolute", left: 120, top: 130, padding: "26px 44px", background: "#fff", border: `5px solid ${INK}`, borderRadius: "40px 40px 40px 8px", fontFamily: "Pret", fontWeight: 800, fontSize: 78, color: INK,
        transform: `scale(${pop(f, 0, 1.2)})`, transformOrigin: "0 100%" }}>Q. {q}</div>
      <div style={{ position: "absolute", left: 120, top: 340, width: 1680, height: 480, opacity: flip, transform: `perspective(1400px) rotateX(${(1 - flip) * -60}deg)`, transformOrigin: "50% 0" }}>{answer}</div>
    </AbsoluteFill>
  );
};
const A: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: INK, lineHeight: 1.35 }}>{children}</div>
);

// 폰으로 명령 ↔ 집 PC
const Remote: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const dot = (f * 14) % 700;
  return (
    <div style={{ position: "relative", width: 1680, height: 480 }}>
      <div style={{ position: "absolute", left: 60, top: 20, width: 230, height: 410, borderRadius: 30, border: `7px solid ${INK}`, background: "#16171b", padding: 16 }}>
        <div style={{ fontFamily: "Consolas, monospace", fontSize: 24, color: "#eee" }}><span style={{ color: OR }}>&gt;</span> 해외 화장품 만들어 줘</div>
        {now >= 13.39 && [0, 1, 2, 3].map((k) => <div key={k} style={{ marginTop: 14, height: 30, borderRadius: 8, background: k < Math.min(4, Math.floor((now - 13.39) * 3)) ? "#2F9E6E" : "#333" }} />)}
      </div>
      <div style={{ position: "absolute", left: 340 + dot, top: 200, width: 26, height: 26, borderRadius: 13, background: OR }} />
      <div style={{ position: "absolute", left: 330, top: 212, width: 760, height: 4, background: "#d8d2c6" }} />
      <div style={{ position: "absolute", left: 1120, top: 40, width: 460, height: 320, borderRadius: 18, border: `7px solid ${INK}`, background: "#fff", textAlign: "center", paddingTop: 110, fontFamily: "Pret", fontWeight: 800, fontSize: 52, color: INK }}>
        🏠 집 PC<div style={{ fontSize: 34, color: "#2F9E6E", marginTop: 10 }}>● 켜져 있음</div></div>
      <div style={{ position: "absolute", left: 330, top: 280, fontFamily: "Pen", fontSize: 64, color: OR }}>밖에서 폰으로 명령 · 진행도 폰으로</div>
    </div>
  );
};

// 갈림길: 숏템메이커 vs 숏클
const Fork: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const card = (x: number, at: number, who: string, name: string, color: string) => now >= at && (
    <div style={{ position: "absolute", left: x, top: 260, width: 760, height: 480, borderRadius: 30, background: "#fff", border: `6px solid ${color}`, padding: "40px 46px", transform: `scale(${pop(f, S(at - base), 1.15)})` }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 50, color: "#7a756d", lineHeight: 1.3, wordBreak: "keep-all" }}>{who}</div>
      <div style={{ position: "absolute", left: 46, bottom: 40, fontFamily: "Pret", fontWeight: 800, fontSize: 110, color }}>→ {name}</div>
    </div>);
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 90, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: INK }}>분명하게 말씀드릴게요</div>
      {card(140, 21.02, "하루 한두 편, 채널 하나 꾸준히", "숏템메이커", "#2F6FD8")}
      {card(1020, 24.93, "많이, 다양하게, 채널 여러 개로", "숏클", OR)}
    </AbsoluteFill>
  );
};

// 오늘 하실 일 3단계
const Today: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const steps: [number, string][] = [[48.6, "프리셋 하나 고르기"], [49.75, "한 줄 넣기"], [54.66, "딸깍 한 번"]];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 140, top: 70, fontFamily: "Pret", fontWeight: 800, fontSize: 72, color: INK }}>오늘 하실 일은 <span style={{ color: OR }}>하나</span></div>
      {steps.map(([t, label], k) => {
        const on = now >= t;
        return <div key={k} style={{ position: "absolute", left: 140, top: 230 + k * 170, display: "flex", flexDirection: "row", alignItems: "center", gap: 30, opacity: on ? 1 : 0.25,
          transform: `scale(${on ? pop(f, S(t - base), 1.15) : 1})`, transformOrigin: "0 50%" }}>
          <div style={{ width: 110, height: 110, borderRadius: 55, background: on ? OR : "#d8d2c6", color: "#fff", fontFamily: "Pret", fontWeight: 800, fontSize: 64, textAlign: "center", lineHeight: "110px" }}>{on ? "✓" : k + 1}</div>
          <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 90, color: INK }}>{label}</div>
        </div>;
      })}
      {now >= 51.55 && <div style={{ position: "absolute", left: 1220, top: 160, width: 560, opacity: ez(f, S(51.55 - base), S(51.55 - base) + 10) }}>
        <Img src={staticFile("p6/p_bujang_pc.png")} style={{ width: 560, mixBlendMode: "multiply" }} />
        <div style={{ textAlign: "center", fontFamily: "Pen", fontSize: 64, color: OR }}>부장님 한 분, 내 PC에</div></div>}
      {now >= 56.13 && <div style={{ position: "absolute", left: 140, top: 760, fontFamily: "Pen", fontSize: 72, color: "#7a756d", opacity: ez(f, S(56.13 - base), S(56.13 - base) + 8) }}>나머지는 일꾼들이 해요</div>}
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const b = OFF[1];
  const Q = (t: number) => b + t;
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* s27 오프닝 회수 */}
      {sq(0, 10.09, <Factory base={0} />)}
      {sq(10.09, 17.29, (lf: number) => <Ink n="mf_crew" side="right"><Hand text={"혼자 가려고\n만든 게 아니에요"} x={120} y={170} size={130} />
        <div style={{ position: "absolute", left: 130, top: 560, padding: "16px 30px", borderRadius: 40, background: OR, fontFamily: "Pret", fontWeight: 800, fontSize: 54, color: "#fff",
          opacity: ez(lf, S(12.77 - 10.09), S(12.77 - 10.09) + 8) }}>숏클 크루 · 세팅을 같이 잡아 드립니다</div></Ink>)}
      {sq(17.29, 21.11, (lf: number) => <Ink n="m_headset" side="right"><div style={{ position: "absolute", left: 130, top: 220, fontFamily: "Pret", fontWeight: 800, color: INK, lineHeight: 1.3 }}>
        <div style={{ fontSize: 80 }}>클로드부터</div><div style={{ fontSize: 80 }}>채널 여러 개 세팅까지</div>
        <div style={{ fontSize: 90, color: OR, opacity: ez(lf, S(19.79 - 17.29), S(19.79 - 17.29) + 8) }}>어려우면 원격으로</div></div></Ink>)}
      {sq(21.11, b, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 140, top: 120, fontFamily: "Pret", fontWeight: 800, fontSize: 80, color: INK }}>잘 되는 방법은 <span style={{ color: OR }}>서로 공유</span></div>
        {lf >= S(25.77 - 21.11) && <div style={{ position: "absolute", left: 200, top: 340, display: "flex", flexDirection: "row", alignItems: "center", gap: 40 }}>
          <div style={{ width: 240, height: 427, borderRadius: 24, overflow: "hidden", border: "5px solid #1a1a1a", transform: `scale(${pop(lf, S(25.77 - 21.11))})` }}>
            <OffthreadVideo src={staticFile("p10/j1b_eagle.mp4")} muted style={{ width: 240, height: 427, objectFit: "cover" }} /></div>
          <div style={{ padding: "26px 40px", background: "#fff", border: "4px solid #ddd", borderRadius: "40px 40px 40px 8px", fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: INK,
            opacity: ez(lf, S(27.0 - 21.11), S(27.0 - 21.11) + 8) }}>"이거 우리 같이 가 보시죠"</div></div>}</AbsoluteFill>)}
      {/* s28 질문 */}
      {sq(Q(0), Q(3.6), <AbsoluteFill style={{ background: PAPER }}><Slam text="질문 세 개만" at={S(0.6)} y={330} size={170} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 560, textAlign: "center", fontFamily: "Pen", fontSize: 80, color: "#9a958d" }}>라이브에서 실제로 받은</div></AbsoluteFill>)}
      {sq(Q(3.6), Q(9.35), <QA base={3.6} n={1} q="PC 사양이 높아야 하나요?" tA={4.99} answer={<A>받고 · 자르고 · 렌더 = <span style={{ color: OR }}>내 PC가</span><br /><span style={{ fontSize: 52, color: "#7a756d" }}>설치 안내 때 기준을 같이 봐 드립니다</span></A>} />)}
      {sq(Q(9.35), Q(14.71), <QA base={9.35} n={2} q="폰에서도 되나요?" tA={10.94} answer={<Remote base={9.35} />} />)}
      {sq(Q(14.71), Q(19.49), <QA base={14.71} n={3} q="하루 몇 편까지 되나요?" tA={16.51} answer={<A>PC 성능 · 클로드 요금제에 따라<br /><span style={{ fontSize: 150, color: OR }}>수십 편</span>도</A>} />)}
      {sq(Q(19.49), Q(29.11), <Fork base={19.49} />)}
      {sq(Q(29.11), Q(39.15), (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 140, top: 90, fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: INK }}>저작권, 미리 말씀드려요</div>
        <div style={{ position: "absolute", left: 140, top: 250, width: 760, padding: "34px 40px", borderRadius: 26, background: "#FFF1E6", border: `5px solid ${OR}`, fontFamily: "Pret", fontWeight: 800, fontSize: 58, color: INK,
          opacity: ez(lf, S(31.68 - 29.11), S(31.68 - 29.11) + 8) }}>⚠ 쇼츠는 "잘릴 수 있다"가 기본</div>
        <div style={{ position: "absolute", left: 1000, top: 250, width: 780, padding: "34px 40px", borderRadius: 26, background: "#E8F7EF", border: "5px solid #2F9E6E", fontFamily: "Pret", fontWeight: 800, fontSize: 58, color: INK,
          opacity: ez(lf, S(34.14 - 29.11), S(34.14 - 29.11) + 8) }}>✓ 중복 피하는 처리는 자동</div>
        <div style={{ position: "absolute", left: 140, top: 560, fontFamily: "Pen", fontSize: 76, color: "#7a756d", opacity: ez(lf, S(37.65 - 29.11), S(37.65 - 29.11) + 10) }}>그래도 이 시장에 들어온 이상, 감당할 몫은 있다</div></AbsoluteFill>)}
      {sq(Q(39.15), Q(46.4), (lf: number) => <Ink n="m_teach_senior" side="left">
        <div style={{ position: "absolute", left: 1060, top: 170, fontFamily: "Pret", fontWeight: 800, color: INK, lineHeight: 1.3 }}>
          <div style={{ fontSize: 60, color: "#7a756d" }}>클로드가 어렵다면</div>
          <div style={{ fontSize: 86, color: OR, opacity: ez(lf, S(1.15), S(1.15) + 8) }}>세팅은 제가 대신</div>
          <div style={{ fontSize: 60, opacity: ez(lf, S(2.54), S(2.54) + 8) }}>원격으로든 뭐든</div>
          <div style={{ marginTop: 30, padding: "16px 30px", borderRadius: 40, background: INK, color: "#fff", fontSize: 50, display: "inline-block", opacity: ez(lf, S(44.48 - 39.15), S(44.48 - 39.15) + 8) }}>1:1 밀착 과정 따로</div>
        </div></Ink>)}
      {sq(Q(46.4), Q(46.84), <AbsoluteFill style={{ background: PAPER }}><Slam text="아시겠죠?" at={0} y={380} size={170} /></AbsoluteFill>)}
      {sq(Q(46.84), Q(57.21), <Today base={46.84} />)}
      {sq(Q(57.21), Q(58.92), (lf: number) => <AbsoluteFill style={{ background: "#0f0f0f" }}>
        <div style={{ position: "absolute", left: 360, top: 260, width: 1200, padding: "34px 40px", borderRadius: 20, background: "#1f1f1f", border: `4px solid ${OR}`, transform: `scale(${pop(lf, 0, 1.15)})` }}>
          <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 36, color: "#aaa" }}>📌 고정 댓글</div>
          <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#fff", marginTop: 16 }}>숏클 크루 신청서는 여기 👇</div></div></AbsoluteFill>)}
      {sq(Q(58.92), END, <Ink n="m_bow" side="right"><Hand text={"집요하게\n계속 업데이트"} x={130} y={150} size={140} />
        <Slam text="끝까지 같이 갑니다" at={S(63.02 - 58.92)} x={130} y={560} size={96} color={OR} center={false} /></Ink>)}
      <Audio src={staticFile("full/s27.mp3")} />
      <Sequence from={S(b)}><Audio src={staticFile("full/s28.mp3")} /></Sequence>
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P13" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
