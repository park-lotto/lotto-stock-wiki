import React from "react";
import { AbsoluteFill, Audio, Composition, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각07 '원본 찾기 엔진 — 한 흐름'(s17, 77초) — 영상의 핵심.
// 진화: 엔진 6단계 줄이 위에 깔리고, 필재가 그 단계를 말하는 순간 그 칸에 불이 들어오며 아래 큰 화면이 그 단계 모습으로 바뀐다.
// 오른쪽 아래에는 실제 엔진 진행판 녹화(증거)가 계속 돈다.
const SC = (PLAN as any)[17];
const CAPS = SC.caps as Cap[];
const END = SC.sec + 0.4;
const sq = (a: number, b: number, el: React.ReactNode) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{el}</Sequence>;
const pop = (f: number, at: number, k = 1.6) => interpolate(f, [at, at + 5, at + 10], [k, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

// 엔진 6단계 — [불 들어오는 초, 이름]
const STEPS: [number, string][] = [[10.16, "영상 주소"], [14.51, "AI 장면 읽기"], [19.4, "4곳 동시 검색"], [24.87, "AI 같은 영상 판정"], [32.36, "받은 원본 재대조"], [38.08, "한국 업로드 수"]];
const Pipe: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  let cur = -1;
  STEPS.forEach((s, k) => { if (now >= s[0]) cur = k; });
  return (
    <div style={{ position: "absolute", left: 40, right: 40, top: 26, display: "flex", flexDirection: "row", gap: 10, zIndex: 5 }}>
      {STEPS.map(([, name], k) => {
        const on = k === cur, done = k < cur;
        return <div key={k} style={{ flex: 1, padding: "14px 6px", borderRadius: 14, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 36,
          background: on ? OR : done ? "#2F2F33" : "rgba(255,255,255,.08)", color: on || done ? "#fff" : "#7c7c84", border: `3px solid ${on ? OR : "#3a3a40"}`,
          transform: `scale(${on ? pop(f, S(STEPS[k][0] - base), 1.25) * 1.04 : 1})` }}>{done ? "✓ " : `${k + 1}. `}{name}</div>;
      })}
    </div>
  );
};
const Board: React.FC = () => (
  <div style={{ position: "absolute", right: 40, bottom: 160, width: 480, height: 270, borderRadius: 14, overflow: "hidden", border: "3px solid #444", boxShadow: "0 10px 30px rgba(0,0,0,.5)", zIndex: 6 }}>
    <OffthreadVideo src={staticFile("p7/board.mp4")} muted playbackRate={1.6} style={{ width: 480, height: 270 }} />
    <div style={{ position: "absolute", left: 8, top: 6, padding: "4px 10px", background: "rgba(0,0,0,.7)", borderRadius: 6, color: "#6EE7B7", fontFamily: "Pret", fontWeight: 800, fontSize: 20 }}>실제 엔진 화면</div>
  </div>
);
const Dark: React.FC<{ children: React.ReactNode }> = ({ children }) => <AbsoluteFill style={{ background: "#141519" }}>{children}</AbsoluteFill>;

// 1) AI 장면 읽기: 소재 영상 위에 스캔 줄 + 태그
const Read: React.FC = () => {
  const f = useCurrentFrame();
  const tags = ["여자 한 명", "코에 팩을 붙임", "떼어 내며 놀람", "화장품 후기"];
  return (
    <Dark>
      <div style={{ position: "absolute", left: 300, top: 150, width: 380, height: 676, borderRadius: 26, overflow: "hidden", border: "5px solid #333" }}>
        <OffthreadVideo src={staticFile("op/c6.mp4")} muted style={{ width: 380, height: 676, objectFit: "cover" }} />
        <div style={{ position: "absolute", left: 0, right: 0, top: ((f * 9) % 676), height: 6, background: "#6EE7B7", boxShadow: "0 0 20px #6EE7B7" }} />
      </div>
      {tags.map((t, k) => {
        const at = 12 + k * 14;
        return f >= at && <div key={k} style={{ position: "absolute", left: 780, top: 220 + k * 130, padding: "16px 34px", borderRadius: 40, background: "#1F3B33", border: "3px solid #6EE7B7",
          fontFamily: "Pret", fontWeight: 800, fontSize: 56, color: "#C9F7E5", transform: `scale(${pop(f, at)})`, transformOrigin: "0 50%" }}>🤖 {t}</div>;
      })}
    </Dark>
  );
};

// 2) 4곳 동시 검색 → 후보 100개+
const Search4: React.FC<{ tCand: number }> = ({ tCand }) => {
  const f = useCurrentFrame();
  const plats: [string, string][] = [["틱톡", "#111"], ["인스타", "#C13584"], ["유튜브", "#E62117"], ["구글 렌즈", "#1A73E8"]];
  const n = Math.min(117, Math.max(0, Math.round(interpolate(f, [S(tCand), S(tCand) + 26], [0, 117], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }))));
  return (
    <Dark>
      {f < S(tCand) && plats.map(([p, c], k) => {
        const ang = (k / 4) * Math.PI * 2 - Math.PI / 4;
        const d = 360 * ez(f, 4, 18);
        return <div key={k} style={{ position: "absolute", left: 860 + Math.cos(ang) * d * 1.4 - 130, top: 470 + Math.sin(ang) * d - 50, padding: "24px 40px", background: c, borderRadius: 26,
          fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: "#fff" }}>{p}</div>;
      })}
      {f < S(tCand) && <div style={{ position: "absolute", left: 760, top: 420, padding: "20px 34px", borderRadius: 20, background: OR, fontFamily: "Pret", fontWeight: 800, fontSize: 56, color: "#fff" }}>한 방에 동시에</div>}
      {f >= S(tCand) && <>
        <div style={{ position: "absolute", left: 80, top: 140, display: "flex", flexDirection: "row", flexWrap: "wrap", gap: 8, width: 1250 }}>
          {Array.from({ length: 40 }).map((_, k) => <div key={k} style={{ width: 116, height: 206, borderRadius: 8, overflow: "hidden", opacity: ez(f, S(tCand) + k * 0.6, S(tCand) + k * 0.6 + 6) }}>
            <OffthreadVideo src={staticFile(`p7/t${(k % 16) + 1}.mp4`)} muted style={{ width: 116, height: 206, objectFit: "cover" }} /></div>)}
        </div>
        <div style={{ position: "absolute", left: 1380, top: 220, fontFamily: "Pret", fontWeight: 800, color: "#fff" }}>
          <div style={{ fontSize: 50, color: "#9aa" }}>후보</div>
          <div style={{ fontSize: 210, color: OR }}>{n}</div>
          <div style={{ fontSize: 44, color: "#9aa" }}>개 (실제 기록)</div>
        </div>
      </>}
    </Dark>
  );
};

// 3) AI 판정: 표지만 보면 ✗, 장면을 보면 ✓
const Judge: React.FC<{ tCover: number; tScene: number }> = ({ tCover, tScene }) => {
  const f = useCurrentFrame();
  const card = (x: number, src: string, label: string, ok: boolean, at: number) => f >= at && (
    <div style={{ position: "absolute", left: x, top: 160, width: 360, height: 640, borderRadius: 24, overflow: "hidden", border: `6px solid ${ok ? "#6EE7B7" : "#E5484D"}`, transform: `scale(${pop(f, at, 1.2)})` }}>
      <OffthreadVideo src={staticFile(src)} muted style={{ width: 360, height: 640, objectFit: "cover" }} />
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: 14, background: "rgba(0,0,0,.75)", textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: "#fff" }}>{label}</div>
      <div style={{ position: "absolute", right: 14, top: 8, fontFamily: "Pret", fontWeight: 800, fontSize: 110, color: ok ? "#6EE7B7" : "#E5484D" }}>{ok ? "✓" : "✗"}</div>
    </div>
  );
  return (
    <Dark>
      {card(220, "op/c1.mp4", "표지만 비슷", false, S(tCover))}
      {card(680, "op/c6.mp4", "장면까지 같은 영상", true, S(tScene))}
      <div style={{ position: "absolute", left: 1150, top: 260, fontFamily: "Pret", fontWeight: 800, color: "#fff", lineHeight: 1.2 }}>
        <div style={{ fontSize: 72, opacity: ez(f, 4, 12) }}>🤖 AI가</div>
        <div style={{ fontSize: 96, color: OR, opacity: ez(f, 10, 18) }}>눈으로 보고</div>
        <div style={{ fontSize: 96, opacity: ez(f, 16, 24) }}>판정</div>
      </div>
    </Dark>
  );
};

// 4) 받은 원본 다시 대조 ✓  5) 한국 업로드 수 → 될 소재 / 안 될 소재
const Recheck: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Dark>
      {[0, 1].map((k) => <div key={k} style={{ position: "absolute", left: 300 + k * 520, top: 170, width: 360, height: 640, borderRadius: 24, overflow: "hidden", border: "5px solid #444" }}>
        <OffthreadVideo src={staticFile("op/c6.mp4")} startFrom={S(1)} muted style={{ width: 360, height: 640, objectFit: "cover" }} /></div>)}
      <div style={{ position: "absolute", left: 690, top: 420, fontFamily: "Pret", fontWeight: 800, fontSize: 110, color: "#6EE7B7", transform: `scale(${pop(f, 14)})`, opacity: ez(f, 14, 20) }}>=</div>
      <div style={{ position: "absolute", left: 1260, top: 330, fontFamily: "Pret", fontWeight: 800, fontSize: 80, color: "#fff", opacity: ez(f, 18, 26) }}>받은 원본<br /><span style={{ color: "#6EE7B7" }}>한 번 더 대조 ✓</span></div>
    </Dark>
  );
};
const Korea: React.FC<{ tSplit: number }> = ({ tSplit }) => {
  const f = useCurrentFrame();
  return (
    <Dark>
      <div style={{ position: "absolute", left: 180, top: 160, fontFamily: "Pret", fontWeight: 800, color: "#fff" }}>
        <div style={{ fontSize: 60, color: "#9aa" }}>이 원본, 한국에 이미</div>
        <div style={{ fontSize: 150 }}>몇 번 올라왔나 <span style={{ color: OR }}>🇰🇷</span></div>
      </div>
      {f >= S(tSplit) && <>
        <div style={{ position: "absolute", left: 220, top: 520, padding: "26px 50px", borderRadius: 24, background: "#1F3B33", border: "4px solid #6EE7B7", fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#C9F7E5", transform: `scale(${pop(f, S(tSplit))})` }}>될 만한 소재</div>
        <div style={{ position: "absolute", left: 900, top: 520, padding: "26px 50px", borderRadius: 24, background: "#3B1F22", border: "4px solid #E5484D", fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#F7C9CC", transform: `scale(${pop(f, S(tSplit) + 8)})` }}>안 될 소재</div>
      </>}
    </Dark>
  );
};

// 실제 사례 숫자(라이브 실측): 690만 재편집본 → 380만 틱톡 원본 → 한국 채널 12개 → 400초(7분)
const Case: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const row = (at: number, label: string, big: string, y: number, color = "#fff") => {
    const st = S(at - base);
    return f >= st && <div style={{ position: "absolute", left: 200, top: y, display: "flex", flexDirection: "row", alignItems: "baseline", gap: 30, transform: `scale(${pop(f, st, 1.3)})`, transformOrigin: "0 50%" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 52, color: "#9aa", width: 520 }}>{label}</div>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 120, color }}>{big}</div>
    </div>;
  };
  return (
    <Dark>
      <div style={{ position: "absolute", left: 200, top: 80, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: OR }}>실제로 넣어 본 사례 (출시 라이브)</div>
      {row(48.21, "넣은 재편집본", "690만 회", 170)}
      {row(50.99, "찾아온 틱톡 원본", "380만 회", 330, OR)}
      {row(54.3, "한국에 올라온 채널", "12개", 490)}
      {row(56.04, "걸린 시간", "약 400초 (7분)", 650, "#6EE7B7")}
    </Dark>
  );
};

const Main: React.FC = () => (
  <AbsoluteFill style={{ background: PAPER }}>
    <Fonts />
    {sq(0, 3.49, <Ink n="m_phone_wow_b" side="right"><Hand text={"구글 렌즈로\n직접 찾아보셨죠?"} x={140} y={230} size={150} /></Ink>)}
    {sq(3.49, 6.54, <AbsoluteFill style={{ background: PAPER }}>
      <Slam text="운 좋으면 ✓" at={S(0.2)} x={200} y={250} size={130} color="#2F9E6E" center={false} />
      <Slam text="대부분 ✗ ✗ ✗" at={S(1.3)} x={200} y={460} size={150} color="#E5484D" center={false} /></AbsoluteFill>)}
    {sq(6.54, 12.62, <Dark>
      <Slam text="원본 찾기 엔진" at={S(0.3)} y={220} size={170} color={OR} />
      {useCurrentFrame() >= S(3.6) && <div style={{ position: "absolute", left: 380, top: 520, width: 1160, padding: "28px 36px", border: "4px solid #555", borderRadius: 18, background: "#1d1e23",
        fontFamily: "Consolas, monospace", fontSize: 48, color: "#ddd" }}>🔗 소재 영상 주소 하나<span style={{ color: OR }}>▌</span></div>}</Dark>)}
    {sq(12.62, 14.51, <Dark><Slam text="쭉 흘러갑니다 →" at={S(0.2)} y={420} size={140} color="#fff" /></Dark>)}
    {sq(14.51, 19.4, <Read />)}
    {sq(19.4, 24.87, <Search4 tCand={23.51 - 19.4} />)}
    {sq(24.87, 32.36, <Judge tCover={28.61 - 24.87} tScene={31.45 - 24.87} />)}
    {sq(32.36, 38.08, <Recheck />)}
    {sq(38.08, 43.58, <Korea tSplit={40.97 - 38.08} />)}
    {sq(43.58, 47.34, <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 230, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 110, color: "#b9b3a8" }}>
        <span style={{ position: "relative" }}>"어, 똑같네"<div style={{ position: "absolute", left: -10, right: -10, top: "52%", height: 14, background: "#E5484D", transform: `scaleX(${ez(useCurrentFrame(), 14, 24)})`, transformOrigin: "left" }} /></span></div>
      <Slam text="검증까지 쭉" at={S(1.6)} y={430} size={200} color={OR} /></AbsoluteFill>)}
    {sq(47.34, 48.21, <AbsoluteFill style={{ background: PAPER }}><Slam text="아시겠죠?" at={1} y={380} size={170} /></AbsoluteFill>)}
    {sq(48.21, 58.74, <Case base={48.21} />)}
    {sq(58.74, 62.43, <AbsoluteFill style={{ background: PAPER }}>
      <Slam text="클로드가 대단하죠" at={S(0.1)} y={240} size={140} color={OR} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 520, textAlign: "center", fontFamily: "Pen", fontSize: 100, color: "#7a756d", opacity: ez(useCurrentFrame(), S(1.3), S(1.3) + 10) }}>여기까지 만든 것도 대단하고요 😄</div></AbsoluteFill>)}
    {sq(62.43, 67.32, <AbsoluteFill style={{ background: PAPER }}>
      <Slam text="물론, 안 되는 것도 있어요" at={S(0.1)} y={140} size={90} />
      <div style={{ position: "absolute", left: 260, top: 360, padding: "36px 50px", borderRadius: 24, background: "#E8F7EF", border: "4px solid #2F9E6E", fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#1F6B4A", opacity: ez(useCurrentFrame(), S(1.8), S(1.8) + 8) }}>⏱ 2~3분이면 찾는 것</div>
      <div style={{ position: "absolute", left: 1000, top: 360, padding: "36px 50px", borderRadius: 24, background: "#FFF1E6", border: `4px solid ${OR}`, fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: OR, opacity: ez(useCurrentFrame(), S(3.0), S(3.0) + 8) }}>🔄 계속 도는 것</div></AbsoluteFill>)}
    {sq(67.32, 70.79, <Ink n="f_dream" side="right" draw={false}><Hand text={"사람은 개입 안 함\n가만히 냅두면 끝"} x={130} y={260} size={140} color={OR} /></Ink>)}
    {sq(70.79, END, <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 200, top: 120, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: "#9a958d" }}>출시 라이브 · 이 장면에서 채팅이 제일 많았어요</div>
      {["원본 찾기 진짜 힘들었는데", "검증까지?"].map((t, k) => <div key={k} style={{ position: "absolute", left: 220 + k * 120, top: 230 + k * 170, padding: "24px 40px", background: "#fff", border: "4px solid #ddd", borderRadius: 30,
        fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: INK, opacity: ez(useCurrentFrame(), S(2.99) + k * 20, S(2.99) + k * 20 + 8) }}>"{t}"</div>)}
      <Slam text="네, 검증까지입니다" at={S(75.0 - 70.79)} y={600} size={130} color={OR} /></AbsoluteFill>)}
    {/* 엔진 단계 줄 + 실제 진행판 — 엔진 설명 구간(12.62~47.34) */}
    {sq(12.62, 47.34, <><Pipe base={12.62} /><Board /></>)}
    <Audio src={staticFile("full/s17.mp3")} />
    <Caption caps={CAPS} />
  </AbsoluteFill>
);
registerRoot(() => <Composition id="P07" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
