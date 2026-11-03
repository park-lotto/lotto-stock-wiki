import React from "react";
import { AbsoluteFill, Audio, Composition, Img, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, INK, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각08 '나만의 보물창고(s18) + 폰으로 담기(s19)'.
// 진화: 같은 그림체로 새로 그린 '보물창고' 배경 위에서 원본 카드가 날아와 쌓이고, 말하는 순간 근거·점수·프리셋 꼬리표가 붙는다.
// 폰 담기는 사장님 지적(밋밋·모자이크·겹침·느린 첫 그림·같은 그림 두 번·자세 똑같음)을 반영해 다시 만든 판(S_phone_capture v2, s19 문장 시각에 맞춰 제작됨).
const PAD = 0.4;
const SC = [18, 19].map((i) => (PLAN as any)[i]);
const OFF = [0, SC[0].sec + PAD];
const END = OFF[1] + SC[1].sec + PAD;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const LF: React.FC<{ r: (f: number) => React.ReactNode }> = ({ r }) => <>{r(useCurrentFrame())}</>;
const sq = (a: number, b: number, el: React.ReactNode | ((f: number) => React.ReactNode)) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{typeof el === "function" ? <LF r={el} /> : el}</Sequence>;
const pop = (f: number, at: number, k = 1.5) => interpolate(f, [at, at + 5, at + 10], [k, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
const CLIPS = [2, 3, 4, 5, 6, 7, 1];

// 보물창고 배경 + 서서히 밀기
const Vault: React.FC<{ children?: React.ReactNode; dim?: number }> = ({ children, dim = 0.35 }) => {
  const f = useCurrentFrame();
  const z = interpolate(f, [0, 600], [1.0, 1.12], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: "#2a1d14", overflow: "hidden" }}>
      <Img src={staticFile("p6/p_vault.png")} style={{ position: "absolute", width: 1920, height: 1080, objectFit: "cover", transform: `scale(${z})` }} />
      <AbsoluteFill style={{ background: `rgba(20,12,6,${dim})` }} />
      {children}
    </AbsoluteFill>
  );
};
// 원본 카드: 날아와 선반에 꽂힘 + 꼬리표
const Card: React.FC<{ c: number; at: number; x: number; y: number; tags?: [number, string][] }> = ({ c, at, x, y, tags = [] }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  const p = ez(f, at, at + 14);
  return (
    <div style={{ position: "absolute", left: 960 + (x - 960) * p, top: 1100 + (y - 1100) * p, width: 230, height: 409, transform: `rotate(${(1 - p) * 20}deg)` }}>
      <div style={{ width: 230, height: 409, borderRadius: 18, overflow: "hidden", border: "5px solid #fff", boxShadow: "0 0 30px rgba(255,210,120,.6)" }}>
        <OffthreadVideo src={staticFile(`op/c${c}.mp4`)} startFrom={S(2)} muted style={{ width: 230, height: 409, objectFit: "cover" }} />
      </div>
      {tags.map(([t, label], k) => f >= t && <div key={k} style={{ position: "absolute", left: 180, top: 30 + k * 76, padding: "8px 18px", background: k % 2 ? "#FFE8A3" : "#D9F7EA", border: `3px solid ${INK}`,
        borderRadius: 12, fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: INK, whiteSpace: "nowrap", transform: `scale(${pop(f, t)})`, transformOrigin: "0 50%" }}>{label}</div>)}
    </div>
  );
};
const Big: React.FC<{ text: string; at: number; y: number; size?: number; color?: string }> = ({ text, at, y, size = 120, color = "#fff" }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  return <div style={{ position: "absolute", left: 0, right: 0, top: y, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: size, color, textShadow: "0 6px 30px rgba(0,0,0,.6)", transform: `scale(${pop(f, at)})` }}>{text}</div>;
};
const Cmd: React.FC<{ text: string; at: number; y: number }> = ({ text, at, y }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  const n = Math.min(text.length, Math.floor((f - at) / 1.5));
  return <div style={{ position: "absolute", left: 420, top: y, width: 1080, padding: "24px 34px", background: "rgba(20,20,24,.92)", border: "3px solid #555", borderRadius: 16,
    fontFamily: "Consolas, monospace", fontSize: 50, color: "#eee" }}><span style={{ color: OR }}>&gt; </span>{text.slice(0, n)}</div>;
};

const Main: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* s18 보물창고 */}
      {sq(0, 5.74, <Vault>
        <Big text="찾은 원본은 버려지지 않는다" at={2} y={120} size={84} />
        <Card c={6} at={S(0.6)} x={845} y={330} tags={[[S(2.8), "근거 ✓"], [S(3.21), "점수 ✓"]]} />
        <Big text="나만의 보물창고" at={S(4.2)} y={810} size={90} color="#FFD36E" /></Vault>)}
      {sq(5.74, 9.94, <Vault dim={0.55}>
        <Big text="여기가 중요해요" at={2} y={140} size={90} color="#FFD36E" />
        <Cmd text="해외 화장품 원본 찾아 둬" at={S(1.12)} y={420} />
        <Big text="딱 한 번만" at={S(8.55 - 5.74)} y={620} size={120} color={OR} /></Vault>)}
      {sq(9.94, 13.53, <Vault>
        {CLIPS.slice(0, 5).map((c, k) => <Card key={k} c={c} at={k * 9} x={130 + k * 340} y={300} />)}
        <Big text="엔진이 계속 돌며 쌓는다" at={2} y={110} size={80} />
        <Big text="저는 12시간씩 돌려놔요" at={S(12.18 - 9.94)} y={780} size={80} color="#FFD36E" /></Vault>)}
      {sq(13.53, 21.71, <Vault>
        <Big text="어느 프리셋으로 만들지까지 미리" at={2} y={100} size={70} />
        <Card c={6} at={4} x={420} y={300} tags={[[S(18.83 - 13.53), "→ 해외 화장품 프리셋"]]} />
        <Card c={2} at={16} x={1180} y={300} tags={[[S(20.66 - 13.53), "→ 해외 신기템 프리셋"]]} /></Vault>)}
      {sq(21.71, 28.59, <Vault dim={0.5}>
        <Big text="만들고 싶을 때 언제든 꺼내요" at={S(22.73 - 21.71)} y={110} size={80} color="#FFD36E" />
        <Cmd text="해외 화장품 만들어 줘" at={S(24.04 - 21.71)} y={320} />
        {f >= S(25.6) && <div style={{ position: "absolute", left: 845, top: 470, width: 230, height: 409, borderRadius: 18, overflow: "hidden", border: `6px solid ${OR}`,
          transform: `translateY(${(1 - ez(f, S(25.6), S(25.6) + 12)) * 300}px)` }}>
          <OffthreadVideo src={staticFile("op/c6.mp4")} startFrom={S(3)} muted style={{ width: 230, height: 409, objectFit: "cover" }} /></div>}
        <Big text="▶ 바로 제작 시작" at={S(26.6)} y={500} size={64} color="#6EE7B7" /></Vault>)}
      {sq(28.59, 30.52, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 160, top: 380, width: 1600, height: 120, display: "flex", flexDirection: "row", borderRadius: 18, overflow: "hidden", border: `5px solid ${INK}` }}>
          {[["원본 찾기", 0.45, "#F6C8B0"], ["대본", 0.2, "#CFE3F7"], ["목소리·자막", 0.2, "#D9F7EA"], ["렌더", 0.15, "#EDE1FF"]].map(([l, w, c], k) => {
            const gone = k === 0 ? ez(lf, S(29.42 - 28.59), S(29.42 - 28.59) + 12) : 0;
            return <div key={k} style={{ width: `${(w as number) * (1 - gone) * 100}%`, background: c as string, display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
              fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: INK, whiteSpace: "nowrap", borderRight: "3px solid #fff" }}>{l as string}</div>;
          })}
        </div>
        <Slam text="원본 찾는 시간이 통째로 빠진다" at={S(1.0)} y={600} size={84} color={OR} /></AbsoluteFill>)}
      {sq(30.52, 34.82, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 200, top: 140, fontFamily: "Pret", fontWeight: 800, fontSize: 44, color: "#9a958d" }}>출시 라이브 채팅</div>
        <div style={{ position: "absolute", left: 200, top: 220, padding: "30px 46px", background: "#fff", border: "4px solid #ddd", borderRadius: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 76, color: INK,
          opacity: ez(lf, 0, 10) }}>"소재가 누적되면 활용하기 좋겠네요"</div>
        <Slam text="정확히 그겁니다" at={S(2.4)} y={520} size={130} color={OR} /></AbsoluteFill>)}
      {sq(34.82, 38.37, <AbsoluteFill><OffthreadVideo src={staticFile("p8/h.mp4")} muted style={{ width: 1920, height: 1080 }} /></AbsoluteFill>)}
      {sq(38.37, OFF[1], <Vault dim={0.4}>
        <Big text="언제든 꺼내서 바로 만드는" at={2} y={300} size={90} />
        <Big text="나만의 창고" at={S(1.1)} y={450} size={170} color="#FFD36E" />
        <Big text="아시겠죠?" at={S(41.64 - 38.37)} y={700} size={80} /></Vault>)}
      {/* s19 폰으로 담기 — 지적 반영판(v2) */}
      {sq(OFF[1], END, <OffthreadVideo src={staticFile("p8/phone.mp4")} muted style={{ width: 1920, height: 1080 }} />)}
      <Audio src={staticFile("full/s18.mp3")} />
      <Sequence from={S(OFF[1])}><Audio src={staticFile("full/s19.mp3")} /></Sequence>
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P08" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
