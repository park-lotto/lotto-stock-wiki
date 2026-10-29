import React from "react";
import { AbsoluteFill, Audio, Composition, Img, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각12 '솔직한 결과(s25) + 비전(s26)'.
// 진화: 결과는 실측 숫자(10-28 채널 리포트: 19,164 / 12,345 / 4,302)가 필재가 말하는 순간 차오르는 막대로. '십만 회?'는 지운다(과장 없음).
// 비전은 오프닝의 흑백 공장이 컬러로 켜지는 것으로 회수하고, 흑백TV→컬러TV·2G폰→스마트폰을 실제 소품 그림으로 바꿔 보여 준다.
const PAD = 0.4;
const SC = [25, 26].map((i) => (PLAN as any)[i]);
const OFF = [0, SC[0].sec + PAD];
const END = OFF[1] + SC[1].sec + PAD;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const LF: React.FC<{ r: (f: number) => React.ReactNode }> = ({ r }) => <>{r(useCurrentFrame())}</>;
const sq = (a: number, b: number, el: React.ReactNode | ((f: number) => React.ReactNode)) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{typeof el === "function" ? <LF r={el} /> : el}</Sequence>;
const pop = (f: number, at: number, k = 1.4) => interpolate(f, [at, at + 5, at + 10], [k, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
const fmt = (n: number) => Math.round(n).toLocaleString("en-US");

// 실측 막대: [말하는 초, 이름, 값]
const BARS: [number, string, number][] = [[11.29, "10월 26일 올린 영상", 19164], [14.07, "해외 핫템", 12345], [16.05, "쇼핑 썰", 4302]];
const Bars: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  return (
    <AbsoluteFill style={{ background: "#121316" }}>
      <div style={{ position: "absolute", left: 140, top: 60, fontFamily: "Pret", fontWeight: 800, fontSize: 46, color: "#9aa" }}>일주일 된 제 채널 · 조회수 <span style={{ color: "#6EE7B7", fontSize: 34 }}>(10-28 실측)</span></div>
      {BARS.map(([at, name, v], k) => {
        if (now < at) return null;
        const p = ez(f, S(at - base), S(at - base) + 30);
        const big = k === 0;
        return <div key={k} style={{ position: "absolute", left: 140, top: 170 + k * 200 }}>
          <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: "#ddd" }}>{name}</div>
          <div style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 30, marginTop: 10 }}>
            <div style={{ width: 1200 * (v / 19164) * p, height: 74, borderRadius: 12, background: big ? OR : "#6EE7B7" }} />
            <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: big ? 96 : 76, color: big ? OR : "#fff" }}>{fmt(v * p)}회</div>
          </div>
        </div>;
      })}
      {now >= 17.31 && <div style={{ position: "absolute", left: 140, top: 760, fontFamily: "Pen", fontSize: 70, color: "#9aa", opacity: ez(f, S(17.31 - base), S(17.31 - base) + 10) }}>덜 나온 것도 있어요 · 다 잘 되는 건 아닙니다</div>}
    </AbsoluteFill>
  );
};

// 천 회의 벽(조각03) 위로 만 회가 넘어간다
const OverWall: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const up = ez(f, S(23.28 - base), S(23.28 - base) + 24);
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {Array.from({ length: 4 }).map((_, r) => Array.from({ length: 10 }).map((_, c) => (
        <div key={`${r}-${c}`} style={{ position: "absolute", left: 160 + c * 160 + (r % 2) * 80, top: 520 + r * 80, width: 152, height: 74, background: "#E9B8A0", border: "4px solid #8a4b35" }} />)))}
      <div style={{ position: "absolute", left: 0, right: 0, top: 560, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 110, color: "#fff", textShadow: "0 4px 0 #8a4b35" }}>1,000 · 2,000</div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 250 - up * 120, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 170, color: OR, opacity: now >= 23.28 ? 1 : 0, transform: `scale(${now >= 23.28 ? pop(f, S(23.28 - base)) : 1})` }}>10,000+ ↑</div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 120, textAlign: "center", fontFamily: "Pen", fontSize: 80, color: "#7a756d" }}>넘기 쉽지 않은 벽</div>
    </AbsoluteFill>
  );
};

// TV·폰 변신: 흑백 → 컬러
const Shift: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const tvColor = ez(f, S(27.2 - base), S(27.2 - base) + 14);
  const phone = ez(f, S(28.9 - base), S(28.9 - base) + 14);
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 120, top: 120, width: 760, height: 600 }}>
        <Img src={staticFile("p12/big_prop_tv_crt.png")} style={{ position: "absolute", inset: 0, width: 760, filter: "grayscale(1)", opacity: 1 - tvColor, mixBlendMode: "multiply" }} />
        <Img src={staticFile("p12/big_prop_tv_color.png")} style={{ position: "absolute", inset: 0, width: 760, opacity: tvColor, transform: `scale(${0.9 + 0.1 * tvColor})`, mixBlendMode: "multiply" }} />
      </div>
      <div style={{ position: "absolute", left: 1040, top: 120, width: 760, height: 600 }}>
        <Img src={staticFile("p12/big_prop_flipphone.png")} style={{ position: "absolute", left: 120, top: 0, width: 500, opacity: (now >= 28.0 ? 1 : 0) * (1 - phone), mixBlendMode: "multiply" }} />
        {phone > 0 && <div style={{ position: "absolute", left: 250, top: 40, width: 280, height: 498, borderRadius: 30, overflow: "hidden", border: "8px solid #1a1a1a", opacity: phone, transform: `scale(${0.85 + 0.15 * phone})` }}>
          <OffthreadVideo src={staticFile("op/c4.mp4")} muted style={{ width: 280, height: 498, objectFit: "cover" }} /></div>}
      </div>
      <div style={{ position: "absolute", left: 120, top: 740, width: 760, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 60, color: tvColor > 0.5 ? OR : "#7a756d" }}>흑백 TV → 컬러 TV</div>
      {now >= 28.0 && <div style={{ position: "absolute", left: 1040, top: 740, width: 760, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 60, color: phone > 0.5 ? OR : "#7a756d" }}>2G폰 → 스마트폰</div>}
      <div style={{ position: "absolute", left: 0, right: 0, top: 30, textAlign: "center", fontFamily: "Pen", fontSize: 64, color: "#9a958d" }}>조금 오바해서 말씀드리면</div>
    </AbsoluteFill>
  );
};

// 채널 하나 → 수십 개
const Many: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const n = Math.min(40, Math.floor(interpolate(f, [S(1.2), S(3.4)], [1, 40], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })));
  const clips = ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9"];
  return (
    <AbsoluteFill style={{ background: "#121316" }}>
      <div style={{ position: "absolute", left: 120, top: 120, display: "flex", flexDirection: "row", flexWrap: "wrap", gap: 10, width: 1300 }}>
        {Array.from({ length: n }).map((_, k) => <div key={k} style={{ width: 120, height: 213, borderRadius: 10, overflow: "hidden" }}>
          <OffthreadVideo src={staticFile(`op/${clips[k % clips.length]}.mp4`)} muted style={{ width: 120, height: 213, objectFit: "cover" }} /></div>)}
      </div>
      <div style={{ position: "absolute", left: 1460, top: 220, width: 420, fontFamily: "Pret", fontWeight: 800, color: "#fff", wordBreak: "keep-all" }}>
        <div style={{ fontSize: 44, color: "#9aa" }}>채널 하나도 벅찼던 우리가</div>
        <div style={{ fontSize: 200, color: OR }}>{n}</div>
        <div style={{ fontSize: 60 }}>개를 돌리는 상상</div>
      </div>
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const b = OFF[1];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* s25 솔직한 결과 */}
      {sq(0, 3.2, <Ink n="m_sincere" side="right"><Hand text={"과장 없이\n말씀드릴게요"} x={140} y={250} size={160} /></Ink>)}
      {sq(3.2, 7.48, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 230, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 170, color: "#b9b3a8" }}>
          <span style={{ position: "relative" }}>올리자마자 10만 회?<div style={{ position: "absolute", left: -10, right: -10, top: "52%", height: 16, background: "#E5484D", transform: `scaleX(${ez(lf, S(1.4), S(1.4) + 10)})`, transformOrigin: "left" }} /></span></div>
        <Slam text="모르겠어요" at={S(1.5)} y={520} size={130} color={INK} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 700, textAlign: "center", fontFamily: "Pen", fontSize: 76, color: "#9a958d", opacity: ez(lf, S(3.0), S(3.0) + 10) }}>운이 좋은 걸 수도 있고요</div></AbsoluteFill>)}
      {sq(7.48, 11.29, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <OffthreadVideo src={staticFile("op/factory.mp4")} muted style={{ position: "absolute", left: 200, top: 120, width: 1000, height: 562, objectFit: "cover", borderRadius: 20, filter: "grayscale(1)" }} />
        <div style={{ position: "absolute", left: 640, top: 300, width: 120, height: 200, border: `8px solid ${OR}`, borderRadius: 18, opacity: ez(lf, S(1.6), S(1.6) + 8), transform: `scale(${pop(lf, S(1.6))})` }} />
        <div style={{ position: "absolute", left: 1260, top: 220, fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: INK, lineHeight: 1.3, opacity: ez(lf, S(1.2), S(1.2) + 10) }}>투명하게<br /><span style={{ color: OR }}>이 폰 하나,</span><br />일주일 된 채널</div></AbsoluteFill>)}
      {sq(11.29, 19.48, <Bars base={11.29} />)}
      {sq(19.48, 27.83, <OverWall base={19.48} />)}
      {sq(27.83, 31.35, (lf: number) => <AbsoluteFill style={{ background: "#141519" }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 240, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 80, color: "#9aa" }}>이거 만들려고 제가 한 것</div>
        <div style={{ position: "absolute", left: 360, top: 420, width: 1200, padding: "30px 40px", border: `4px solid ${OR}`, borderRadius: 18, fontFamily: "Consolas, monospace", fontSize: 60, color: "#fff", opacity: ez(lf, S(1.4), S(1.4) + 8) }}>
          <span style={{ color: OR }}>&gt; </span>만들어 줘</div>
        <Slam text="한마디" at={S(2.4)} y={640} size={130} color={OR} /></AbsoluteFill>)}
      {sq(31.35, b, <AbsoluteFill style={{ background: "#000" }}>
        <OffthreadVideo src={staticFile("p12/report.mp4")} startFrom={S(31.35)} muted style={{ width: 1920, height: 1080 }} />
        <div style={{ position: "absolute", left: 60, top: 40, padding: "12px 26px", background: OR, borderRadius: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: "#fff" }}>채널이 늘어나도 리포트 한 장</div></AbsoluteFill>)}
      {/* s26 비전 */}
      {sq(b, b + 3.45, <Ink n="m_heart" side="right"><Hand text={"여러분,\n설레지 않으십니까"} x={130} y={230} size={150} color={OR} /></Ink>)}
      {sq(b + 3.45, b + 6.69, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 240, top: 300, fontSize: 200, opacity: ez(lf, 0, 10) }}>💡</div>
        <Slam text="아이디어는 있었다" at={4} x={480} y={330} size={100} center={false} />
        <Slam text="찍어낼 도구가 없었을 뿐" at={S(1.43)} x={480} y={500} size={100} color={OR} center={false} /></AbsoluteFill>)}
      {sq(b + 6.69, b + 13.84, (lf: number) => <AbsoluteFill style={{ background: "#000" }}>
        <OffthreadVideo src={staticFile("op/factory.mp4")} muted style={{ width: 1920, height: 1080, objectFit: "cover", filter: `grayscale(${1 - ez(lf, S(3.6), S(3.6) + 30)})` }} />
        <AbsoluteFill style={{ background: "rgba(0,0,0,.58)" }} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 140, textAlign: "center", fontFamily: "Pen", fontSize: 100, color: "#fff", textShadow: "0 4px 20px #000" }}>맨 처음 그 휴대폰들</div>
        <Slam text="채널 50개, 공장처럼" at={S(3.81)} y={400} size={140} color="#FFD36E" /></AbsoluteFill>)}
      {sq(b + 13.84, b + 18.55, <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 230, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 100, color: "#9a958d" }}>안 되는 채널도 있겠죠</div>
        <Slam text="숨기지 않고 공유합니다" at={S(2.79)} y={440} size={120} color={OR} /></AbsoluteFill>)}
      {sq(b + 18.55, b + 24.7, (lf: number) => <AbsoluteFill style={{ background: "#EAF3FB" }}>
        <Img src={staticFile("p12/big_prop_globe.png")} style={{ position: "absolute", left: 1080, top: 60, width: 720, mixBlendMode: "multiply", transform: `rotate(${lf * 0.3}deg)` }} />
        <Slam text="크루와 같이" at={S(0.2)} x={160} y={200} size={120} center={false} />
        <Slam text="해외로" at={S(1.6)} x={160} y={380} size={160} color={OR} center={false} />
        <div style={{ position: "absolute", left: 160, top: 610, fontFamily: "Pen", fontSize: 80, color: "#5a6b7d", opacity: ez(lf, S(2.77), S(2.77) + 10) }}>유튜브는 전 세계 · 한국은 좁다</div></AbsoluteFill>)}
      {sq(b + 24.7, b + 31.08, <Shift base={24.7} />)}
      {sq(b + 31.08, b + 37.33, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 200, textAlign: "center", fontFamily: "Pen", fontSize: 90, color: "#9a958d" }}>몇 년 뒤 돌아보면</div>
        <Slam text="2026년" at={S(2.0)} y={330} size={240} color={OR} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 620, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 80, color: INK, opacity: ez(lf, S(3.4), S(3.4) + 10) }}>"정말 대단한 한 해였구나"</div></AbsoluteFill>)}
      {sq(b + 37.33, b + 41.87, (lf: number) => <Ink n="f_look_far" side="right" >
        <Hand text={"그 한가운데\n지금 여러분"} x={130} y={160} size={140} />
        <div style={{ position: "absolute", left: 140, top: 560, fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: OR, opacity: ez(lf, S(2.27), S(2.27) + 10) }}>시간적 자유 · 경제적 자유</div></Ink>)}
      {sq(b + 41.87, b + 46.03, <Many base={41.87} />)}
      {sq(b + 46.03, END, <Ink n="m_open_arms" side="right"><Hand text={"현실이 될 수 있게\n제가 돕겠습니다"} x={120} y={250} size={140} color={OR} /></Ink>)}
      <Audio src={staticFile("full/s25.mp3")} />
      <Sequence from={S(b)}><Audio src={staticFile("full/s26.mp3")} /></Sequence>
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P12" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
