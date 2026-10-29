import React from "react";
import { AbsoluteFill, Audio, Composition, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각05 '한계(말로 부탁) → 진짜 바라는 것 → 해결 방향'(s12~s14).
// 진화: 채팅 장면을 대사 속 따옴표 말이 '들리는 순간' 그 말풍선이 뜨도록 새로 짰다(옛 A2 재사용 안 함).
// 바라는 것 두 가지(①스타일 ②원본)는 카드 두 장으로 만들고, 해결 방향에서 그 두 장이 ①시스템 ②노하우로 바뀐다(이어지는 장치).
const PAD = 0.4;
const IDX = [12, 13, 14];
const SC = IDX.map((i) => (PLAN as any)[i]);
const OFF: number[] = []; let acc = 0;
SC.forEach((s) => { OFF.push(acc); acc += s.sec + PAD; });
const END = acc;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const sq = (a: number, b: number, el: React.ReactNode) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{el}</Sequence>;

// ── 채팅: [시각(s12 기준), 누가, 내용, 카드영상?]
type Msg = [number, "me" | "ai", string, string?];
const MSGS: Msg[] = [
  [4.89, "me", "이 영상 원본 찾아 줘."],
  [6.38, "ai", "찾았습니다.", "op/c2.mp4"],
  [7.51, "me", "아니, 이거 말고. 화장품 바르는 여자."],
  [10.05, "ai", "죄송합니다, 다시 찾아보겠습니다."],
  [12.16, "ai", "이 영상일까요?", "op/c3.mp4"],
  [14.76, "me", "세 번째 자막 조금만 위로 해 줘."],
  [18.39, "ai", "두 번째 자막을 올렸습니다."],
  [19.87, "me", "아니, 세 번째."],
  [20.83, "me", "아까 걸로 다시 해 줘."],
  [22.73, "ai", "어떤 버전을 말씀하시는 걸까요?"],
];
const CLOCK: [number, string][] = [[4.6, "19:12"], [12.9, "21:05"], [22.7, "23:48"], [29.0, "00:07"]];
const Chat: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const shown = MSGS.filter((m) => now >= m[0]);
  const forget = ez(f, S(25.0 - base), S(25.0 - base) + 30);   // "앞에 한 말을 까먹어서" — 위 대화가 옅어진다
  const H = (m: Msg) => (m[3] ? 330 : 110);
  const total = shown.reduce((a, m) => a + H(m) + 22, 0);
  const scroll = Math.max(0, total - 700);
  let y = 0;
  const clock = [...CLOCK].reverse().find((c) => now >= c[0]);
  return (
    <AbsoluteFill style={{ background: "#202124" }}>
      <div style={{ position: "absolute", left: 120, top: 80, width: 1100, height: 780, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: -scroll, transition: "none" }}>
          {shown.map((m, k) => {
            const a = ez(f, S(m[0] - base), S(m[0] - base) + 6);
            const fade = k < shown.length - 3 ? 1 - forget * 0.75 : 1;
            const top = y; y += H(m) + 22;
            const me = m[1] === "me";
            return (
              <div key={k} style={{ position: "absolute", top, left: me ? undefined : 0, right: me ? 0 : undefined, maxWidth: 900, opacity: a * fade, transform: `translateY(${(1 - a) * 30}px)` }}>
                <div style={{ padding: "22px 30px", borderRadius: 26, background: me ? "#3B3F45" : "transparent", color: "#ECECEC", fontFamily: "Pret", fontWeight: 800, fontSize: 50, lineHeight: 1.25 }}>{m[2]}</div>
                {m[3] && <div style={{ width: 300, height: 200, borderRadius: 16, overflow: "hidden", marginLeft: 30, position: "relative" }}>
                  <OffthreadVideo src={staticFile(m[3])} startFrom={S(3)} muted style={{ width: 300, height: 534, objectFit: "cover", marginTop: -150 }} />
                  <div style={{ position: "absolute", right: 10, top: 6, fontSize: 64, color: "#E5484D", fontFamily: "Pret", fontWeight: 800, opacity: ez(f, S(m[0] - base) + 12, S(m[0] - base) + 18) }}>✗</div>
                </div>}
              </div>
            );
          })}
        </div>
      </div>
      {/* 오른쪽: 시계 + 보낸 메시지 수 */}
      <div style={{ position: "absolute", left: 1320, top: 150, fontFamily: "Pret", fontWeight: 800, color: "#6EE7B7", fontSize: 150 }}>{clock ? clock[1] : ""}</div>
      {clock && clock[1] === "00:07" && <div style={{ position: "absolute", left: 1330, top: 330, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: "#9aa" }}>다음 날</div>}
      <div style={{ position: "absolute", left: 1330, top: 410, fontFamily: "Pret", fontWeight: 800, fontSize: 56, color: "#ddd" }}>보낸 메시지 <span style={{ color: "#fff" }}>{shown.filter((m) => m[1] === "me").length + Math.floor(Math.max(0, now - 25) * 2)}</span>개</div>
      {now >= 25 && <div style={{ position: "absolute", left: 1320, top: 520, width: 520, fontFamily: "Pen", fontSize: 76, color: OR, opacity: ez(f, S(25 - base), S(25 - base) + 10) }}>앞에 한 말을 까먹어서<br />처음부터 다시</div>}
    </AbsoluteFill>
  );
};

// 라이브 채팅 한 줄 → 딸깍 ✗ 잡도리
const Jabdori: React.FC<{ tFact: number; tLine: number }> = ({ tFact, tLine }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 200, top: 130, padding: "30px 44px", background: "#fff", border: "4px solid #ddd", borderRadius: 24, boxShadow: "0 12px 30px rgba(0,0,0,.12)", opacity: ez(f, 0, 10) }}>
        <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: "#9a958d" }}>출시 라이브 채팅</div>
        <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 66, color: INK, marginTop: 8 }}>"저거 잡도리하는 거 진짜 지쳐요"</div>
      </div>
      {f >= S(tLine) && <div style={{ position: "absolute", left: 260, top: 470, fontFamily: "Pret", fontWeight: 800, fontSize: 170, display: "flex", flexDirection: "row", gap: 80 }}>
        <span style={{ position: "relative", color: "#b9b3a8" }}>딸깍<div style={{ position: "absolute", left: -10, right: -10, top: "52%", height: 16, background: "#E5484D", transform: `scaleX(${ez(f, S(tLine), S(tLine) + 8)})`, transformOrigin: "left" }} /></span>
        <span style={{ color: OR, transform: `scale(${interpolate(f, [S(tLine) + 8, S(tLine) + 13, S(tLine) + 18], [2, 0.94, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })})` }}>잡도리</span>
      </div>}
      {f >= S(tFact) && f < S(tLine) && <Slam text="맞습니다." at={S(tFact)} y={500} size={130} />}
    </AbsoluteFill>
  );
};

// 바라는 것 두 장 → 해결 방향 두 장(같은 카드가 바뀐다)
const Two: React.FC<{ mode: "want" | "need"; t1: number; t2: number; final?: number }> = ({ mode, t1, t2, final }) => {
  const f = useCurrentFrame();
  const card = (k: number, at: number) => {
    const a = ez(f, S(at), S(at) + 10);
    const s = interpolate(f, [S(at), S(at) + 5, S(at) + 10], [1.3, 0.96, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const want = [["저 채널 스타일", "나도 그대로"], ["원본만 찾으면", "나도 터진다"]][k];
    const need = [["누구나 쉽게", "돌리는 시스템"], ["채널 여러 개", "같이 돌리는 노하우"]][k];
    const [l1, l2] = mode === "want" ? want : need;
    return (
      <div key={k} style={{ position: "absolute", left: 170 + k * 820, top: 150, width: 760, height: 620, background: "#fff", border: `6px solid ${INK}`, borderRadius: 30, opacity: a, transform: `scale(${s})`,
        boxShadow: "0 16px 40px rgba(0,0,0,.12)" }}>
        <div style={{ position: "absolute", left: 40, top: 30, width: 110, height: 110, borderRadius: 55, background: OR, color: "#fff", fontFamily: "Pret", fontWeight: 800, fontSize: 70, textAlign: "center", lineHeight: "110px" }}>{k + 1}</div>
        <div style={{ position: "absolute", left: 50, top: 190, right: 40 }}>
          <div style={{ fontFamily: "Pen", fontSize: 100, color: "#7a756d" }}>{l1}</div>
          <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: mode === "need" && k === 1 ? 74 : 92, color: INK, marginTop: 10, wordBreak: "keep-all" }}>{l2}</div>
        </div>
        {mode === "want" && k === 1 && <div style={{ position: "absolute", right: 40, bottom: 30, fontSize: 120 }}>🔍</div>}
        {mode === "need" && k === 0 && <div style={{ position: "absolute", left: 50, bottom: 40, padding: "14px 30px", background: OR, color: "#fff", borderRadius: 40, fontFamily: "Pret", fontWeight: 800, fontSize: 50 }}>▶ 한 줄</div>}
        {mode === "need" && k === 1 && <div style={{ position: "absolute", left: 50, bottom: 30, display: "flex", flexDirection: "row", gap: 12 }}>
          {[1, 2, 3, 4, 5, 6].map((v) => <div key={v} style={{ width: 70, height: 124, borderRadius: 10, overflow: "hidden" }}>
            <OffthreadVideo src={staticFile(`op/v${v}.mp4`)} muted style={{ width: 70, height: 124, objectFit: "cover" }} /></div>)}</div>}
      </div>
    );
  };
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {card(0, t1)}{card(1, t2)}
      {final !== undefined && f >= S(final) && <div style={{ position: "absolute", left: 0, right: 0, top: 800, textAlign: "center", fontFamily: "Pen", fontSize: 70, color: OR, opacity: ez(f, S(final), S(final) + 8) }}>
        더 좋은 강의가 아니라, 이 두 개</div>}
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const o = OFF;
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* s12 한계 */}
      {sq(o[0], o[0] + 3.29, <Ink n="m_phone_wow" side="right"><Hand text={"말로 시키면\n되지 않나?"} x={140} y={240} size={160} /></Ink>)}
      {sq(o[0] + 3.29, o[0] + 4.89, <Ink n="m_phone_cu_blink" side="left" draw={false}><Hand text="(웃음)" x={1150} y={330} size={170} color={OR} /></Ink>)}
      {sq(o[0] + 4.89, o[0] + 29.05, <Chat base={4.89} />)}
      {sq(o[0] + 29.05, o[0] + 31.23, <AbsoluteFill style={{ background: "#0e0f12" }}><Slam text="하루가 끝" at={S(0.3)} y={360} size={200} color="#fff" /></AbsoluteFill>)}
      {sq(o[0] + 31.23, o[1], <Jabdori tFact={34.87 - 31.23} tLine={35.44 - 31.23} />)}
      {/* s13 진짜 바라는 것 */}
      {sq(o[1], o[1] + 3.58, <Ink n="m_subway_swipe_a" side="right"><Hand text={"우리가 원하는 건\n그게 아니잖아요"} x={130} y={230} size={140} /></Ink>)}
      {sq(o[1] + 3.58, o[1] + 5.47, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 330, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 150, color: INK }}>
          <span style={{ position: "relative" }}>AI랑 말씨름<div style={{ position: "absolute", left: -10, right: -10, top: "52%", height: 16, background: "#E5484D", transform: `scaleX(${ez(useCurrentFrame(), 10, 20)})`, transformOrigin: "left" }} /></span></div></AbsoluteFill>)}
      {sq(o[1] + 5.47, o[2], <Two mode="want" t1={0} t2={8.23 - 5.47} />)}
      {sq(o[2], o[2] + 6.34, <Two mode="need" t1={1.2} t2={3.54} />)}
      {sq(o[2] + 6.34, o[2] + 9.36, <Ink n="m_subway_swipe_b" side="left"><Hand text={"아이디어는 있는데\n찍어낼 도구가 없었다"} x={1000} y={250} size={120} /></Ink>)}
      {sq(o[2] + 9.36, END, <Two mode="need" t1={-1} t2={-1} final={0.2} />)}
      {IDX.map((i, k) => <Sequence key={i} from={S(o[k])}><Audio src={staticFile(`full/s${i}.mp3`)} /></Sequence>)}
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P05" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
