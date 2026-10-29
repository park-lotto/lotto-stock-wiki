import React from "react";
import { AbsoluteFill, Audio, Composition, Img, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각06 '대리→부장(s15) + 왜 원본(s16)'. 진화: 비유마다 같은 그림체의 실제 그림(버텍스 생성 대리·부장·차·설치팩)을
// 마주 세워 '대비'로 보여 준다. 말하는 단어(보고·판단하고·고치는)에 맞춰 칩이 붙는다.
const PAD = 0.4;
const IDX = [15, 16];
const SC = IDX.map((i) => (PLAN as any)[i]);
const OFF: number[] = []; let acc = 0;
SC.forEach((s) => { OFF.push(acc); acc += s.sec + PAD; });
const END = acc;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const sq = (a: number, b: number, el: React.ReactNode) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{el}</Sequence>;
const pop = (f: number, at: number) => interpolate(f, [at, at + 5, at + 10], [1.6, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const Pic: React.FC<{ src: string; x: number; y: number; w: number; at?: number }> = ({ src, x, y, w, at = 0 }) => {
  const f = useCurrentFrame();
  const a = ez(f, at, at + 10);
  return <Img src={staticFile(src)} style={{ position: "absolute", left: x, top: y, width: w, opacity: a, transform: `translateY(${(1 - a) * 30}px)`, mixBlendMode: "multiply" }} />;
};
const Label: React.FC<{ text: string; x: number; y: number; at: number; color?: string; size?: number }> = ({ text, x, y, at, color = INK, size = 90 }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  return <div style={{ position: "absolute", left: x, top: y, fontFamily: "Pret", fontWeight: 800, fontSize: size, color, transform: `scale(${pop(f, at)})`, transformOrigin: "0 50%" }}>{text}</div>;
};

// 대리: 쪽지 말풍선이 쌓인다
const Daeri: React.FC<{ tAsk: number; tJudge: number }> = ({ tAsk, tJudge }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Pic src="p6/p_daeri.png" x={60} y={-20} w={900} />
      <Label text="대리급" x={1040} y={120} at={0} size={130} />
      <div style={{ position: "absolute", left: 1040, top: 290, fontFamily: "Pen", fontSize: 80, color: "#7a756d", opacity: ez(f, S(2.2), S(2.2) + 8) }}>시킨 일은 잘한다</div>
      {["이것도 만들어 줘", "저것도 만들어 줘", "이건 알아서 판단해 줘"].map((t, k) => {
        const at = S(tAsk) + k * 14;
        return f >= at && <div key={k} style={{ position: "absolute", left: 1000 + k * 60, top: 420 + k * 120, padding: "14px 30px", background: "#FFF3B0", border: `4px solid ${INK}`, borderRadius: 14,
          fontFamily: "Pen", fontSize: 70, color: INK, transform: `scale(${pop(f, at)}) rotate(${k % 2 ? 3 : -3}deg)` }}>{t}</div>;
      })}
      {f >= S(tJudge) + 20 && <div style={{ position: "absolute", left: 380, top: 120, fontSize: 130, transform: `scale(${pop(f, S(tJudge) + 20)})` }}>💦</div>}
    </AbsoluteFill>
  );
};

// 부장: 보고·판단하고·고친다
const Bujang: React.FC<{ marks: [number, string][] }> = ({ marks }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Pic src="p6/p_bujang.png" x={960} y={-20} w={900} />
      <Label text="부장급" x={140} y={120} at={0} size={130} color={OR} />
      {marks.map(([at, t], k) => <Label key={k} text={`${k + 1}. ${t}`} x={150} y={330 + k * 140} at={S(at)} size={100} />)}
    </AbsoluteFill>
  );
};

// 대비 두 칸(차·성적)
const Vs: React.FC<{ l: React.ReactNode; r: React.ReactNode; tR: number }> = ({ l, r, tR }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 80, top: 120, width: 820, height: 640, opacity: ez(f, 0, 8) }}>{l}</div>
      <div style={{ position: "absolute", left: 930, top: 360, fontFamily: "Pret", fontWeight: 800, fontSize: 90, color: "#c9c3b8", opacity: ez(f, S(tR) - 6, S(tR)) }}>vs</div>
      <div style={{ position: "absolute", left: 1040, top: 120, width: 820, height: 640, opacity: ez(f, S(tR), S(tR) + 8), transform: `scale(${pop(f, S(tR))})` }}>{r}</div>
    </AbsoluteFill>
  );
};

// 해외에서 터진 영상 → 1년 뒤 한국에서 또
const Loop1y: React.FC<{ tYear: number }> = ({ tYear }) => {
  const f = useCurrentFrame();
  const phone = (x: number, at: number, kr: boolean) => (
    <div style={{ position: "absolute", left: x, top: 60, width: 420, height: 746, borderRadius: 36, overflow: "hidden", border: "6px solid #222", opacity: ez(f, at, at + 10), boxShadow: "0 18px 40px rgba(0,0,0,.25)" }}>
      <OffthreadVideo src={staticFile("p6/foreign.mp4")} muted style={{ width: 420, height: 746, objectFit: "cover" }} />
      {kr && <div style={{ position: "absolute", left: 20, right: 20, top: 90, padding: "12px", background: "#fff", borderRadius: 10, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 36, color: "#111" }}>한국어로 다시</div>}
    </div>
  );
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {phone(220, 0, false)}
      <div style={{ position: "absolute", left: 230, top: 830, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: "#7a756d" }}>해외에서 터진 영상</div>
      {f >= S(tYear) && <svg width={560} height={300} style={{ position: "absolute", left: 680, top: 260 }}>
        <path d="M 20 220 C 160 20, 400 20, 540 220" fill="none" stroke={OR} strokeWidth={12} strokeLinecap="round" strokeDasharray={800} strokeDashoffset={800 * (1 - ez(f, S(tYear), S(tYear) + 14))} />
      </svg>}
      {f >= S(tYear) && <div style={{ position: "absolute", left: 830, top: 170, fontFamily: "Pen", fontSize: 110, color: OR, transform: `scale(${pop(f, S(tYear))})` }}>1년 뒤</div>}
      {phone(1280, S(tYear) + 12, true)}
      {f >= S(tYear) + 12 && <div style={{ position: "absolute", left: 1290, top: 830, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: OR }}>한국에서 또 터진다</div>}
    </AbsoluteFill>
  );
};

// 원본 vs 재편집(남의 자막) — 나란히 비교, 원본에 돋보기
const OriginalVsReup: React.FC<{ tFind: number }> = ({ tFind }) => {
  const f = useCurrentFrame();
  const card = (x: number, label: string, cover: boolean, glow: boolean) => (
    <div style={{ position: "absolute", left: x, top: 60, width: 420, height: 746, borderRadius: 36, overflow: "hidden", border: `6px solid ${glow ? OR : "#222"}`, boxShadow: glow ? `0 0 ${40 * ez(f, S(tFind), S(tFind) + 10)}px ${OR}` : "0 18px 40px rgba(0,0,0,.25)" }}>
      <OffthreadVideo src={staticFile("p6/foreign.mp4")} startFrom={S(3)} muted style={{ width: 420, height: 746, objectFit: "cover" }} />
      {cover && <>
        <div style={{ position: "absolute", left: 0, right: 0, top: 70, padding: "16px", background: "#FFE14D", textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: "#111" }}>남의 채널 제목</div>
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 120, padding: "16px", background: "#111", textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: "#fff" }}>남의 자막</div>
      </>}
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "10px", background: "rgba(0,0,0,.65)", textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: "#fff" }}>{label}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {card(240, "재편집본", true, false)}
      <div style={{ position: "absolute", left: 360, top: 360, fontFamily: "Pret", fontWeight: 800, fontSize: 200, color: "#E5484D", opacity: ez(f, 10, 18) }}>✗</div>
      {f >= S(tFind) && card(1260, "처음 찍은 원본", false, true)}
      {f >= S(tFind) && <div style={{ position: "absolute", left: 1500, top: 600, fontSize: 160, transform: `rotate(${Math.sin(f / 6) * 10}deg)` }}>🔍</div>}
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const o = OFF;
  const b = o[1];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* s15 */}
      {sq(o[0], o[0] + 1.46, <Ink n="m_hope" side="right"><Hand text={"저도\n똑같이 고민했어요"} x={140} y={240} size={150} /></Ink>)}
      {sq(o[0] + 1.46, o[0] + 7.97, <AbsoluteFill style={{ background: "#101114" }}>
        <Img src={staticFile("p2/shortem.png")} style={{ position: "absolute", left: 620, top: 80, width: 1240, borderRadius: 16, opacity: 0.95 }} />
        <Label text="회원 요청" x={110} y={200} at={0} color="#fff" size={90} />
        {[0, 1, 2, 3].map((k) => <Label key={k} text="✓ 반영" x={130} y={340 + k * 110} at={S(1.2 + k * 0.5)} color="#6EE7B7" size={70} />)}
        <Label text="다 필요한 것들" x={110} y={800} at={S(4.98)} color={OR} size={60} /></AbsoluteFill>)}
      {sq(o[0] + 7.97, o[0] + 10.23, <AbsoluteFill style={{ background: PAPER }}>
        {Array.from({ length: 6 }).map((_, r) => Array.from({ length: 9 }).map((_, c) => (
          <div key={`${r}-${c}`} style={{ position: "absolute", left: 220 + c * 170 + (r % 2) * 85, top: 120 + r * 110, width: 160, height: 100, background: "#E9B8A0", border: "4px solid #8a4b35",
            opacity: ez(useCurrentFrame(), r * 3, r * 3 + 6) }} />)))}
        <div style={{ position: "absolute", left: 0, right: 0, top: 300, height: 260, background: "rgba(28,27,25,.82)" }} /><Slam text="넘을 수 없는 벽" at={S(0.5)} y={330} size={150} color="#fff" /></AbsoluteFill>)}
      {sq(o[0] + 10.23, o[0] + 12.79, <AbsoluteFill style={{ background: PAPER }}>
        <Slam text="숏템 = 무료 AI" at={S(0.1)} y={300} size={160} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 520, textAlign: "center", fontFamily: "Pen", fontSize: 100, color: "#7a756d" }}>(제미나이)</div></AbsoluteFill>)}
      {sq(o[0] + 12.79, o[0] + 20.96, <Daeri tAsk={16.3 - 12.79} tJudge={18.48 - 12.79} />)}
      {sq(o[0] + 20.96, o[0] + 24.83, <Bujang marks={[[22.51 - 20.96, "원본을 보고"], [22.88 - 20.96, "판단하고"], [23.45 - 20.96, "고친다"]]} />)}
      {sq(o[0] + 24.83, o[0] + 26.72, <Vs tR={0.9}
        l={<><Img src={staticFile("p6/p_sedan.png")} style={{ width: 820, mixBlendMode: "multiply" }} /><div style={{ textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 90, color: "#7a756d" }}>아반떼</div></>}
        r={<><Img src={staticFile("p6/p_sports.png")} style={{ width: 820, mixBlendMode: "multiply" }} /><div style={{ textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 90, color: OR }}>포르쉐</div></>} />)}
      {sq(o[0] + 26.72, o[0] + 29.06, <Vs tR={1.1}
        l={<div style={{ marginTop: 160, textAlign: "center", fontFamily: "Pret", fontWeight: 800, color: "#7a756d" }}><div style={{ fontSize: 70 }}>전교</div><div style={{ fontSize: 200 }}>30등</div></div>}
        r={<div style={{ marginTop: 160, textAlign: "center", fontFamily: "Pret", fontWeight: 800, color: OR }}><div style={{ fontSize: 70 }}>전교</div><div style={{ fontSize: 240 }}>1등</div></div>} />)}
      {sq(o[0] + 29.06, o[0] + 31.89, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 300, top: 470, width: 260, height: 180, border: `6px solid ${INK}`, borderRadius: 14, opacity: ez(useCurrentFrame(), 0, 8) }} />
        <div style={{ position: "absolute", left: 300, top: 670, fontFamily: "Pen", fontSize: 70, color: "#7a756d" }}>대리가 맡는 일</div>
        <div style={{ position: "absolute", left: 900, top: 120, width: 700, height: 530, border: `8px solid ${OR}`, borderRadius: 24, opacity: ez(useCurrentFrame(), 20, 30), transform: `scale(${pop(useCurrentFrame(), 20)})` }} />
        <div style={{ position: "absolute", left: 900, top: 670, fontFamily: "Pen", fontSize: 70, color: OR, opacity: ez(useCurrentFrame(), 26, 34) }}>부장이 맡는 일</div></AbsoluteFill>)}
      {sq(o[0] + 31.89, o[0] + 32.53, <AbsoluteFill style={{ background: PAPER }}><Slam text="아시겠죠?" at={1} y={360} size={180} color={OR} /></AbsoluteFill>)}
      {sq(o[0] + 32.53, o[0] + 34.72, <AbsoluteFill style={{ background: PAPER }}>
        <Label text="엔진" x={160} y={150} at={0} size={80} color="#9a958d" />
        <div style={{ position: "absolute", left: 160, top: 300, fontFamily: "Pret", fontWeight: 800, fontSize: 150, color: "#b9b3a8", opacity: 1 - ez(useCurrentFrame(), 14, 24) }}>제미나이</div>
        <Label text="→ 클로드" x={160} y={300} at={20} size={170} color={OR} /></AbsoluteFill>)}
      {sq(o[0] + 34.72, o[0] + 38.04, <AbsoluteFill style={{ background: PAPER }}>
        <Pic src="p6/p_pack.png" x={1000} y={40} w={780} />
        <Label text="제 클로드의 노하우" x={150} y={230} at={0} size={84} />
        <Label text="→ 설치팩 하나" x={150} y={380} at={S(36.4 - 34.72)} size={120} color={OR} /></AbsoluteFill>)}
      {sq(o[0] + 38.04, o[0] + 44.96, <AbsoluteFill style={{ background: PAPER }}>
        {[0, 1].map((k) => <div key={k} style={{ position: "absolute", left: 220 + k * 820, top: 140, width: 660, height: 420, border: `10px solid ${INK}`, borderRadius: 24, background: "#fff", opacity: ez(useCurrentFrame(), k * 10, k * 10 + 10) }}>
          <div style={{ position: "absolute", left: 0, right: 0, top: 130, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 80, color: OR }}>설치팩 ✓</div></div>)}
        <Label text="제 PC" x={420} y={600} at={0} size={70} />
        <Label text="회원님 PC" x={1170} y={600} at={10} size={70} />
        <Label text="=" x={920} y={280} at={S(40.59 - 38.04)} size={150} color={OR} /></AbsoluteFill>)}
      {sq(o[0] + 44.96, b, <Ink n="m_point_right_b" side="right"><Hand text={"그 전에\n먼저 보실 게 하나"} x={140} y={240} size={150} color={OR} /></Ink>)}
      {/* s16 왜 원본 */}
      {sq(b, b + 2.96, <AbsoluteFill style={{ background: PAPER }}><Slam text="터지는 쇼츠의 비밀" at={S(0.3)} y={360} size={150} /></AbsoluteFill>)}
      {sq(b + 2.96, b + 7.73, <Loop1y tYear={3.96 - 2.96} />)}
      {sq(b + 7.73, b + 10.79, <AbsoluteFill style={{ background: PAPER }}>
        <Label text="우리 나름대로 각색" x={160} y={230} at={0} size={110} />
        <svg width={420} height={420} viewBox="-60 -60 120 120" style={{ position: "absolute", left: 1300, top: 160, transform: `rotate(${useCurrentFrame() * 4}deg)` }}>
          <path d="M 40 0 A 40 40 0 1 1 28 -28" fill="none" stroke={OR} strokeWidth={8} strokeLinecap="round" /><path d="M 18 -36 L 30 -28 L 22 -16" fill="none" stroke={OR} strokeWidth={8} strokeLinecap="round" /></svg>
        <Label text="돌고 도는 것" x={160} y={420} at={S(9.66 - 7.73)} size={140} color={OR} /></AbsoluteFill>)}
      {sq(b + 10.79, b + 13.87, <Ink n="m_phone_show_b" side="right"><Hand text={"잘하는 채널은\n이미 다 한다\n(수작업으로)"} x={140} y={200} size={130} /></Ink>)}
      {sq(b + 13.87, b + 19.37, <OriginalVsReup tFind={99} />)}
      {sq(b + 19.37, b + 24.55, <OriginalVsReup tFind={0} />)}
      {sq(b + 24.55, END, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 260, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 150, color: "#b9b3a8" }}>
          <span style={{ position: "relative" }}>사람이<div style={{ position: "absolute", left: -10, right: -10, top: "52%", height: 16, background: "#E5484D", transform: `scaleX(${ez(useCurrentFrame(), 10, 20)})`, transformOrigin: "left" }} /></span></div>
        <Slam text="엔진이 한다" at={S(27.37 - 24.55)} y={470} size={200} color={OR} /></AbsoluteFill>)}
      {IDX.map((i, k) => <Sequence key={i} from={S(o[k])}><Audio src={staticFile(`full/s${i}.mp3`)} /></Sequence>)}
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P06" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
