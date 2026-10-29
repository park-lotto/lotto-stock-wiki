import React from "react";
import { AbsoluteFill, Audio, Composition, Img, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Browser, Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각04 '일반 해결책 4갈래'(s07~s11). 진화: 화면 위에 '네 갈래 길' 띠가 늘 떠 있고
// 지금 말하는 길만 불이 들어온다(시청자가 지금 어디인지 안다). 문장 = 화면, 같은 그림 두 번 안 씀.
const PAD = 0.4;
const IDX = [7, 8, 9, 10, 11];
const SC = IDX.map((i) => (PLAN as any)[i]);
const OFF: number[] = []; let acc = 0;
SC.forEach((s) => { OFF.push(acc); acc += s.sec + PAD; });
const END = acc;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const sq = (a: number, b: number, el: React.ReactNode) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{el}</Sequence>;
const ROADS = ["직접 만들기", "반자동", "자동화 프로그램", "클로드"];

// 위쪽 '네 갈래 길' 띠 — 전체 조각 내내
const Roads: React.FC = () => {
  const f = useCurrentFrame();
  const now = f / 30;
  let cur = -1;
  [OFF[1], OFF[2], OFF[3], OFF[4]].forEach((t, k) => { if (now >= t) cur = k; });
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top: 22, display: "flex", flexDirection: "row", justifyContent: "center", gap: 18, zIndex: 5 }}>
      {ROADS.map((r, k) => {
        const on = k === cur;
        const a = ez(f, k * 5, k * 5 + 8);
        return <div key={k} style={{ padding: "10px 26px", borderRadius: 40, fontFamily: "Pret", fontWeight: 800, fontSize: 34, opacity: a,
          background: on ? OR : "rgba(255,255,255,.85)", color: on ? "#fff" : "#9a958d", border: `3px solid ${on ? OR : "#ddd5c8"}`,
          transform: `scale(${on ? 1.08 : 1})` }}>{k + 1}. {r}</div>;
      })}
    </div>
  );
};

// 갈림길 표지판 4개가 차례로 박힌다
const Sign: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Ink n="m_point_right_b" side="left">
      <div style={{ position: "absolute", left: 1150, top: 170, width: 16, height: 700, background: "#8a6a45", borderRadius: 8 }} />
      {ROADS.map((r, k) => {
        const at = 6 + k * 7;
        const s = interpolate(f, [at, at + 5, at + 10], [1.8, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return f >= at && <div key={k} style={{ position: "absolute", left: k % 2 ? 900 : 1170, top: 190 + k * 150, padding: "22px 46px", background: "#fff", border: `6px solid ${INK}`,
          borderRadius: 14, fontFamily: "Pen", fontSize: 84, color: INK, transform: `scale(${s}) rotate(${k % 2 ? 3 : -3}deg)` }}>{k % 2 ? "◀ " : ""}{r}{k % 2 ? "" : " ▶"}</div>;
      })}
    </Ink>
  );
};

// 캡컷 타임라인: 클립이 쌓이고 가위로 잘린다
const Timeline: React.FC = () => {
  const f = useCurrentFrame();
  const cols = ["#7CC4E8", "#F2A65A", "#9AD08B", "#E58FB0", "#B9A2E8", "#7CC4E8"];
  return (
    <AbsoluteFill style={{ background: "#1d1f24" }}>
      <div style={{ position: "absolute", left: 120, top: 150, width: 1680, height: 480, background: "#2a2d33", borderRadius: 18 }}>
        {[0, 1, 2].map((row) => cols.map((c, k) => {
          const at = row * 10 + k * 4;
          const a = ez(f, at, at + 8);
          return <div key={`${row}-${k}`} style={{ position: "absolute", left: 40 + k * 270, top: 50 + row * 140, width: 250 * a, height: 100, background: c, borderRadius: 10, opacity: 0.9 }} />;
        }))}
        <div style={{ position: "absolute", left: 40 + ((f * 18) % 1600), top: 20, width: 6, height: 440, background: "#fff" }} />
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 690, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 80, color: "#fff" }}>
        한 장면, 한 장면 <span style={{ color: OR }}>직접 자르기</span>
      </div>
      <div style={{ position: "absolute", left: 120 + ((f * 18) % 1600), top: 90, fontSize: 90, transform: `rotate(${Math.sin(f / 3) * 20}deg)` }}>✂️</div>
    </AbsoluteFill>
  );
};

// 반자동 흐름: 말하는 순간 칩이 하나씩
const Flow: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const steps: [number, string, boolean][] = [[1.77, "영상 찾아 저장", true], [3.42, "프롬프트로 AI 대본", false], [5.36, "복사", true], [5.8, "캡컷으로", true]];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 100, top: 200, display: "flex", flexDirection: "row", alignItems: "center", gap: 24 }}>
        {steps.map(([at, label, hand], k) => {
          const st = S(at - base);
          const a = ez(f, st, st + 8);
          return <React.Fragment key={k}>
            {k > 0 && <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#c9c3b8", opacity: a }}>→</div>}
            <div style={{ padding: "30px 34px", borderRadius: 24, background: hand ? "#fff" : "#E9F4FF", border: `5px solid ${hand ? INK : "#5B8DEF"}`, opacity: a,
              transform: `translateY(${(1 - a) * 40}px)`, fontFamily: "Pret", fontWeight: 800, fontSize: 54, color: INK, textAlign: "center" }}>
              <div style={{ fontSize: 40 }}>{hand ? "✋ 내 손" : "🤖 AI"}</div>{label}
            </div>
          </React.Fragment>;
        })}
      </div>
    </AbsoluteFill>
  );
};

// 반은 자동, 반은 노가다 — 화면을 반으로
const Half: React.FC = () => {
  const f = useCurrentFrame();
  const split = ez(f, 0, 12);
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 960 * split, height: 880, background: "#E9F4FF" }} />
      <div style={{ position: "absolute", left: 1920 - 960 * split, top: 0, width: 960 * split, height: 880, background: "#FCE9DA" }} />
      <Slam text="반은 자동" at={4} x={180} y={330} size={140} color="#2F6FD8" center={false} />
      <Slam text="반은 노가다" at={16} x={1080} y={330} size={140} color={OR} center={false} />
    </AbsoluteFill>
  );
};

// 다시 만들어 줘 → 크레딧이 빠진다
const Credits: React.FC = () => {
  const f = useCurrentFrame();
  const n = Math.min(3, Math.floor(f / 22) + 1);
  const gauge = 1 - n * 0.27;
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {Array.from({ length: n }).map((_, k) => (
        <div key={k} style={{ position: "absolute", left: 160, top: 140 + k * 170, padding: "22px 40px", background: "#fff", border: `5px solid ${INK}`, borderRadius: "40px 40px 40px 8px",
          fontFamily: "Pret", fontWeight: 800, fontSize: 68, color: INK, opacity: ez(f, k * 22, k * 22 + 8) }}>"다시 만들어 줘"</div>
      ))}
      <div style={{ position: "absolute", left: 1100, top: 160, fontFamily: "Pret", fontWeight: 800, fontSize: 56, color: "#9a958d" }}>크레딧</div>
      <div style={{ position: "absolute", left: 1100, top: 240, width: 620, height: 90, border: `6px solid ${INK}`, borderRadius: 20, overflow: "hidden" }}>
        <div style={{ width: `${gauge * 100}%`, height: "100%", background: gauge > 0.4 ? "#7DCB7A" : "#E5484D" }} />
      </div>
      {Array.from({ length: n }).map((_, k) => {
        const p = interpolate(f, [k * 22 + 4, k * 22 + 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <div key={k} style={{ position: "absolute", left: 1300 + k * 80, top: 360 + p * 360, fontSize: 90, opacity: 1 - p }}>🪙</div>;
      })}
    </AbsoluteFill>
  );
};

// AI 생성 영상 느낌(매끈한 그림) — 실제 회사 로고·화면은 쓰지 않는다
const AiArt: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "linear-gradient(135deg,#1b1640,#3b1f6b 50%,#0f3c5a)" }}>
      {Array.from({ length: 24 }).map((_, k) => (
        <div key={k} style={{ position: "absolute", left: (k * 173) % 1800, top: (k * 97) % 800, width: 8, height: 8, borderRadius: 4, background: "#fff", opacity: 0.3 + 0.7 * Math.abs(Math.sin((f + k * 7) / 9)) }} />
      ))}
      <div style={{ position: "absolute", left: 0, right: 0, top: 260, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 120, color: "#fff", opacity: ez(f, 0, 10) }}>AI가 그려 낸 영상</div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 440, textAlign: "center", fontFamily: "Pen", fontSize: 110, color: "#FFD36E", opacity: ez(f, S(1.9), S(1.9) + 10) }}>그림은 근사합니다</div>
    </AbsoluteFill>
  );
};

// 우리가 하려는 쇼츠: 실제 터진 결과물들이 줄지어
const OurShorts: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 110, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 84, color: INK, opacity: ez(f, 0, 10) }}>
        터진 걸 찾아서 → <span style={{ color: OR }}>내 식으로</span>
      </div>
      <div style={{ position: "absolute", left: 160, top: 280, display: "flex", flexDirection: "row", gap: 30 }}>
        {[2, 3, 4, 5, 7].map((c, k) => {
          const a = ez(f, 6 + k * 5, 16 + k * 5);
          return <div key={k} style={{ width: 290, height: 516, borderRadius: 22, overflow: "hidden", opacity: a, transform: `translateY(${(1 - a) * 60}px)`, boxShadow: "0 12px 30px rgba(0,0,0,.25)" }}>
            <OffthreadVideo src={staticFile(`op/c${c}.mp4`)} startFrom={S(3)} muted style={{ width: 290, height: 516, objectFit: "cover" }} />
          </div>;
        })}
      </div>
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const o = OFF;
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* s07 네 갈래 */}
      {sq(o[0], o[1], <Sign />)}
      {/* s08 직접 만들기 */}
      {sq(o[1], o[1] + 2.67, <Ink n="m_laptop_hope" side="right"><Hand text={"강의 듣고\n직접 만들기"} x={140} y={230} size={160} /></Ink>)}
      {sq(o[1] + 2.67, o[1] + 6.04, <Timeline />)}
      {sq(o[1] + 6.04, o[1] + 8.12, <Ink n="m_excited" side="left"><Hand text={"실력은 확실히 늘어요"} x={1030} y={300} size={130} color={OR} /></Ink>)}
      {sq(o[1] + 8.12, o[1] + 10.99, <AbsoluteFill style={{ background: PAPER }}>
        <Slam text="빠른 분 2~3시간" at={S(0.6)} y={250} size={130} color="#9a958d" />
        <Slam text="보통 5~6시간" at={S(2.15)} y={470} size={170} color={INK} /></AbsoluteFill>)}
      {sq(o[1] + 10.99, o[2], <Ink n="m_laptop_blank_b" side="right"><Hand text={"하루 한 편이\n한계"} x={150} y={250} size={170} color={OR} /></Ink>)}
      {/* s09 반자동 */}
      {sq(o[2], o[2] + 1.77, <AbsoluteFill style={{ background: PAPER }}><Slam text="둘째, 반자동" at={S(0.2)} y={360} size={180} /></AbsoluteFill>)}
      {sq(o[2] + 1.77, o[2] + 7.25, <Flow base={1.77} />)}
      {sq(o[2] + 7.25, o[2] + 8.28, <AbsoluteFill style={{ background: PAPER }}><Slam text="시간은 줄죠 ↓" at={2} y={360} size={170} color="#2F6FD8" /></AbsoluteFill>)}
      {sq(o[2] + 8.28, o[2] + 10.71, <Ink n="m_phone_meh_b" side="left"><Hand text={"찾기·편집은\n여전히 내 손"} x={1050} y={250} size={150} /></Ink>)}
      {sq(o[2] + 10.71, o[3], <Half />)}
      {/* s10 숏템메이커: 실제 화면(B2, 이 문장들에 맞춰 만든 것) */}
      {sq(o[3], o[3] + 4.14, <AbsoluteFill style={{ background: PAPER }}>
        <Slam text="셋째, 자동화 프로그램" at={S(0.3)} y={300} size={140} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 520, textAlign: "center", fontFamily: "Pen", fontSize: 96, color: "#9a958d" }}>단계만 따라가면 버튼으로</div></AbsoluteFill>)}
      {sq(o[3] + 4.14, o[4], <OffthreadVideo src={staticFile("p4/b2.mp4")} startFrom={S(4.14)} muted style={{ width: 1920, height: 1080 }} />)}
      {/* s11 클로드 */}
      {sq(o[4], o[4] + 2.88, <AbsoluteFill style={{ background: PAPER }}><Slam text="넷째, 클로드" at={S(2.33)} y={330} size={200} color={OR} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 230, textAlign: "center", fontFamily: "Pen", fontSize: 90, color: "#9a958d", opacity: ez(useCurrentFrame(), 0, 10) }}>요즘 제일 많이 보시는 거</div></AbsoluteFill>)}
      {sq(o[4] + 2.88, o[4] + 7.54, <AbsoluteFill style={{ background: PAPER }}>
        <Browser shot={{ page: 4, term: "클로드 쇼츠 자동화", from: [300, 900, 1500], to: [950, 1050, 720], hl: [971, 1252, 601, 26], lines: [] }} dur={S(4.66)} />
        <Slam text="힉스필드 + MCP" at={S(2.73)} x={1300} y={330} size={84} color={OR} center={false} /></AbsoluteFill>)}
      {sq(o[4] + 7.54, o[4] + 10.74, <AiArt />)}
      {sq(o[4] + 10.74, o[4] + 14.89, <Credits />)}
      {sq(o[4] + 14.89, o[4] + 17.84, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 330, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 130, color: INK }}>
          <span style={{ position: "relative" }}>AI가 그린 쇼츠<div style={{ position: "absolute", left: -10, right: -10, top: "55%", height: 14, background: "#E5484D",
            transform: `scaleX(${ez(useCurrentFrame(), 14, 26)})`, transformOrigin: "left" }} /></span></div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 560, textAlign: "center", fontFamily: "Pen", fontSize: 100, color: OR }}>우리가 하려는 건 이게 아니잖아요</div></AbsoluteFill>)}
      {sq(o[4] + 17.84, END, <OurShorts />)}
      <Roads />
      {IDX.map((i, k) => <Sequence key={i} from={S(o[k])}><Audio src={staticFile(`full/s${String(i).padStart(2, "0")}.mp3`)} /></Sequence>)}
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P04" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
