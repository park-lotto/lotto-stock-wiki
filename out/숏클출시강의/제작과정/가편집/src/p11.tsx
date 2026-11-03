import React from "react";
import { AbsoluteFill, Audio, Composition, Img, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각11 '올리는 것까지(s23) + 크레딧 걱정(s24)'.
// 진화: 올리기는 하루 시간표(15:00·20:00 칸)에 완성본이 스스로 꽂히고, 같은 제품 링크 카드 두 장이 말하는 순간 붙는다.
// 크레딧은 조각06의 대리·부장을 이어 받아 '회사 조직도'로 — 일거리가 말하는 순간 사원·대리 / 과장 / 부장 칸으로 날아가고, 크레딧 게이지는 초록에 머문다.
const PAD = 0.4;
const SC = [23, 24].map((i) => (PLAN as any)[i]);
const OFF = [0, SC[0].sec + PAD];
const END = OFF[1] + SC[1].sec + PAD;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const LF: React.FC<{ r: (f: number) => React.ReactNode }> = ({ r }) => <>{r(useCurrentFrame())}</>;
const sq = (a: number, b: number, el: React.ReactNode | ((f: number) => React.ReactNode)) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{typeof el === "function" ? <LF r={el} /> : el}</Sequence>;
const pop = (f: number, at: number, k = 1.4) => interpolate(f, [at, at + 5, at + 10], [k, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

// 하루 시간표: 15시·20시 칸에 완성본이 꽂힘 + 링크 카드
const Schedule: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const hours = [9, 12, 15, 18, 20, 23];
  const slot = (h: number) => 140 + hours.indexOf(h) * 290;
  const phone = (h: number, clip: string, at: number) => now >= at && (
    <div style={{ position: "absolute", left: slot(h) - 20, top: 260, width: 200, height: 356, borderRadius: 18, overflow: "hidden", border: `5px solid ${OR}`, transform: `translateY(${(1 - ez(f, S(at - base), S(at - base) + 14)) * -300}px)` }}>
      <OffthreadVideo src={staticFile(`p10/${clip}.mp4`)} muted style={{ width: 200, height: 356, objectFit: "cover" }} /></div>);
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 120, top: 40, fontFamily: "Pret", fontWeight: 800, fontSize: 52, color: INK }}>오늘 올릴 시간표</div>
      <div style={{ position: "absolute", left: 120, top: 200, width: 1680, height: 6, background: "#d8d2c6" }} />
      {hours.map((h) => {
        const hot = (h === 15 && now >= 4.85) || (h === 20 && now >= 5.13);
        return <div key={h} style={{ position: "absolute", left: slot(h), top: 130, width: 160, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: hot ? 56 : 40,
          color: hot ? OR : "#a8a296", transform: `scale(${hot ? pop(f, S((h === 15 ? 4.85 : 5.13) - base)) : 1})` }}>{h}:00</div>;
      })}
      {phone(15, "i1a_kopack", 6.6)}
      {phone(20, "j1a_ironman", 7.2)}
      {now >= 7.41 && <div style={{ position: "absolute", left: 1500, top: 300, padding: "18px 26px", background: "#16171b", borderRadius: 18, color: "#fff", fontFamily: "Pret", fontWeight: 800, fontSize: 40,
        transform: `scale(${pop(f, S(7.41 - base))})` }}>🤖 예약 담당 일꾼<div style={{ fontSize: 30, color: "#6EE7B7", marginTop: 6 }}>그 시간에 올림</div></div>}
      {now >= 8.65 && <div style={{ position: "absolute", left: 200, top: 650, padding: "14px 26px", background: "#fff", border: `4px solid ${INK}`, borderRadius: 16, fontFamily: "Pret", fontWeight: 800, fontSize: 38, color: INK,
        transform: `scale(${pop(f, S(8.65 - base))})`, transformOrigin: "0 50%" }}>🔗 쿠팡 파트너스 링크 · 같은 제품 찾아 붙임</div>}
      {now >= 11.35 && <div style={{ position: "absolute", left: 1000, top: 650, padding: "14px 26px", background: "#fff", border: `4px solid ${INK}`, borderRadius: 16, fontFamily: "Pret", fontWeight: 800, fontSize: 38, color: INK,
        transform: `scale(${pop(f, S(11.35 - base))})`, transformOrigin: "0 50%" }}>🔗 인포크 링크 · {now >= 12.18 ? "사진 + 문구까지" : ""}</div>}
    </AbsoluteFill>
  );
};

// 아침·저녁: 반으로 나뉜 화면에 새 주인공
const MorningEvening: React.FC<{ tEve: number }> = ({ tEve }) => {
  const f = useCurrentFrame();
  const half = (side: 0 | 1, n: string, bg: string, label: string, at: number) => (
    <div style={{ position: "absolute", left: side * 960, top: 0, width: 960, height: 1080, background: bg, overflow: "hidden", opacity: ez(f, at, at + 10) }}>
      <Img src={staticFile(`hero/c_${n}.png`)} style={{ position: "absolute", left: 120, top: 40, width: 720, mixBlendMode: "multiply" }} />
      <div style={{ position: "absolute", left: 60, top: 60, padding: "12px 30px", borderRadius: 40, background: "rgba(255,255,255,.9)", fontFamily: "Pret", fontWeight: 800, fontSize: 52, color: INK }}>{label}</div>
      <div style={{ position: "absolute", right: 60, top: 60, padding: "10px 24px", borderRadius: 40, background: "#2F9E6E", fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: "#fff",
        transform: `scale(${pop(f, at + 16)})`, opacity: f >= at + 16 ? 1 : 0 }}>✓ 올라가 있음</div>
    </div>
  );
  return <AbsoluteFill style={{ background: PAPER }}>{half(0, "f_wake_phone", "#FFF3D6", "☀ 아침에 일어나면", 0)}{half(1, "m_evening_walk", "#E3E6F5", "🌙 퇴근하면", S(tEve))}</AbsoluteFill>;
};

// 조직도: 일거리가 말하는 순간 직급 칸으로
const Org: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const box = (x: number, title: string, sub: string, at: number, img?: string, hot?: boolean) => (
    <div style={{ position: "absolute", left: x, top: 150, width: 520, height: 560, borderRadius: 28, background: "#fff", border: `5px solid ${hot ? OR : INK}`, opacity: ez(f, S(at - base) - 4, S(at - base) + 6),
      transform: `scale(${pop(f, S(at - base), 1.12)})`, overflow: "hidden" }}>
      {img && <Img src={staticFile(img)} style={{ position: "absolute", left: 60, top: 70, width: 400, mixBlendMode: "multiply", opacity: 0.95 }} />}
      <div style={{ position: "absolute", left: 0, right: 0, top: 18, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 58, color: hot ? OR : INK }}>{title}</div>
      <div style={{ position: "absolute", left: 20, right: 20, bottom: 20, padding: "14px", borderRadius: 16, background: hot ? "#FFF1E6" : "#F4F1EA", textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 36, color: INK }}>{sub}</div>
    </div>
  );
  const gauge = 0.82 - Math.max(0, Math.min(1, (now - 13.9) / 8)) * 0.06;
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 120, top: 40, fontFamily: "Pret", fontWeight: 800, fontSize: 52, color: INK }}>숏클 안의 일꾼들 <span style={{ color: "#9a958d", fontSize: 38 }}>· 직급대로</span></div>
      {box(110, "사원 · 대리", "그냥 보면 되는 일", 13.93, "p6/p_daeri.png")}
      {box(700, "과장", "같은 영상인지 판정", 16.43, undefined)}
      {now >= 16.43 && <div style={{ position: "absolute", left: 780, top: 290, fontSize: 220, opacity: ez(f, S(16.43 - base), S(16.43 - base) + 8) }}>🔍</div>}
      {box(1290, "부장", "두뇌가 들어가는 일만", 19.08, "p6/p_bujang.png", true)}
      {now >= 21.15 && <div style={{ position: "absolute", left: 1340, top: 40, display: "flex", flexDirection: "row", alignItems: "center", gap: 14, opacity: ez(f, S(21.15 - base), S(21.15 - base) + 8) }}>
        <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: "#9a958d" }}>크레딧</div>
        <div style={{ width: 300, height: 40, border: `4px solid ${INK}`, borderRadius: 12, overflow: "hidden" }}><div style={{ width: `${gauge * 100}%`, height: "100%", background: "#7DCB7A" }} /></div>
      </div>}
      {now >= 23.13 && <div style={{ position: "absolute", left: 110, top: 740, fontFamily: "Pen", fontSize: 72, color: OR, opacity: ez(f, S(23.13 - base), S(23.13 - base) + 10) }}>누구한테 줄지, 개발자가 엔진에 다 세팅해 둠</div>}
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const b = OFF[1];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* s23 */}
      {sq(0, 2.69, <AbsoluteFill style={{ background: PAPER }}><Slam text="올리는 것도" at={S(0.3)} y={260} size={150} />
        <Slam text="손댈 게 없다" at={S(1.3)} y={480} size={150} color={OR} /></AbsoluteFill>)}
      {sq(2.69, 4.34, (lf: number) => <AbsoluteFill style={{ background: "#141519" }}>
        <div style={{ position: "absolute", left: 300, top: 400, width: 1320, padding: "28px 40px", border: "3px solid #555", borderRadius: 18, fontFamily: "Consolas, monospace", fontSize: 54, color: "#eee" }}>
          <span style={{ color: OR }}>&gt; </span>{"나는 세 시, 여덟 시에 하나씩 올릴 거야".slice(0, Math.floor(lf / 1.4))}</div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 260, textAlign: "center", fontFamily: "Pen", fontSize: 90, color: "#9aa" }}>딱 한 번만 정해 둔다</div></AbsoluteFill>)}
      {sq(4.34, 14.18, <Schedule base={4.34} />)}
      {sq(14.18, 15.94, <Ink n="f_thumb" side="right"><Hand text={"내가 할 게\n아무것도 없다"} x={140} y={260} size={160} color={OR} /></Ink>)}
      {sq(15.94, 20.1, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 200, top: 150, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: "#9a958d" }}>출시 라이브 채팅</div>
        <div style={{ position: "absolute", left: 200, top: 230, padding: "30px 46px", background: "#fff", border: "4px solid #ddd", borderRadius: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 84, color: INK }}>"인포크 링크도요?"</div>
        <Slam text="네, 그것까지요" at={S(3.2)} y={520} size={140} color={OR} /></AbsoluteFill>)}
      {sq(20.1, 23.05, <MorningEvening tEve={21.58 - 20.1} />)}
      {sq(23.05, b, <AbsoluteFill style={{ background: "#141519" }}><Slam text="자동화의 끝" at={S(0.8)} y={380} size={200} color={OR} /></AbsoluteFill>)}
      {/* s24 크레딧 */}
      {sq(b, b + 5.3, (lf: number) => <Ink n="f_ask_hand" side="right"><div style={{ position: "absolute", left: 120, top: 230, width: 820, padding: "34px 44px", background: "#fff", border: `5px solid ${INK}`, borderRadius: "50px 50px 10px 50px",
        fontFamily: "Pret", fontWeight: 800, fontSize: 66, color: INK, lineHeight: 1.25, opacity: ez(lf, S(2.28), S(2.28) + 8) }}>"클로드 계속 돌리면<br />크레딧 엄청 나가는 거 아니에요?"</div></Ink>)}
      {sq(b + 5.3, b + 9.79, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 220, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 90, color: "#9a958d" }}>아무렇게나 쓰면 → 그렇다</div>
        <Img src={staticFile("p6/p_daeri.png")} style={{ position: "absolute", left: 420, top: 380, width: 440, mixBlendMode: "multiply", opacity: ez(lf, S(1.5), S(1.5) + 10) }} />
        <Img src={staticFile("p6/p_bujang.png")} style={{ position: "absolute", left: 1060, top: 380, width: 440, mixBlendMode: "multiply", opacity: ez(lf, S(2.0), S(2.0) + 10) }} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 330, textAlign: "center", fontFamily: "Pen", fontSize: 76, color: OR, opacity: ez(lf, S(1.5), S(1.5) + 10) }}>아까 그 대리·부장, 기억나시죠</div></AbsoluteFill>)}
      {sq(b + 9.79, b + 13.93, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 250, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 110, color: INK }}>회사도 모든 일을</div>
        <Slam text="부장한테 시키진 않는다" at={S(1.6)} y={420} size={120} color={OR} /></AbsoluteFill>)}
      {sq(b + 13.93, b + 26.41, <Org base={13.93} />)}
      {sq(b + 26.41, b + 30.62, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 200, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#9a958d" }}>크레딧</div>
        <div style={{ position: "absolute", left: 460, top: 320, width: 1000, height: 110, border: `6px solid ${INK}`, borderRadius: 24, overflow: "hidden" }}>
          <div style={{ width: `${interpolate(lf, [0, 120], [86, 80], { extrapolateRight: "clamp" })}%`, height: "100%", background: "#7DCB7A" }} /></div>
        <Slam text="비정상적으로 나가지 않는다" at={S(2.1)} y={520} size={100} color="#2F9E6E" /></AbsoluteFill>)}
      {sq(b + 30.62, END, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <Img src={staticFile("p6/p_pack.png")} style={{ position: "absolute", left: 1080, top: 60, width: 700, mixBlendMode: "multiply" }} />
        <div style={{ position: "absolute", left: 140, top: 230, fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#9a958d", opacity: ez(lf, 0, 10) }}>세팅은 건드릴 필요 없음</div>
        <Slam text="설치팩 깔고" at={S(32.85 - 30.62)} x={140} y={360} size={130} center={false} />
        <Slam text="엔진 돌리면 끝" at={S(33.9 - 30.62)} x={140} y={530} size={130} color={OR} center={false} /></AbsoluteFill>)}
      <Audio src={staticFile("full/s23.mp3")} />
      <Sequence from={S(b)}><Audio src={staticFile("full/s24.mp3")} /></Sequence>
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P11" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
