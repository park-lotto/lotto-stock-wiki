import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, Img, OffthreadVideo, Sequence, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";
import PLAN from "../public/plan.json";

// 숏클 1편 조각02 '0 공감'(52.4초). 대사 문장마다 화면이 바뀌고 같은 그림 반복 없음.
// 손그림 = 새 주인공 선화(g_)가 펜처럼 드러난 뒤 컬러(c_)로 번짐. 검색 화면 = L(이미 6.54~26.1초에 맞춰 만든 것).
const FPS = 30, S = (s: number) => Math.round(s * FPS);
const PAPER = "#FBF8F1", INK = "#1C1B19", OR = "#E07A2B";
const ez = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
type Cap = [number, number, string];
const SC = (PLAN as any)[1];
const CAPS = SC.caps as Cap[];
const END = SC.sec + 0.4;
const t = (needle: string) => (CAPS.find((c) => c[2].includes(needle)) || [0])[0] as number;

const Font = () => (
  <style>{`@font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}
  @font-face{font-family:'Pen';src:url('${staticFile("fonts/NanumPenScript.ttf")}')}`}</style>
);

const Caption: React.FC = () => {
  const now = useCurrentFrame() / FPS;
  const c = CAPS.find((x, k) => now >= x[0] && now < (CAPS[k + 1] ? CAPS[k + 1][0] : x[1] + 0.6));
  if (!c) return null;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 50, display: "flex", justifyContent: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 46, color: "#fff", background: "rgba(0,0,0,.72)", padding: "12px 30px", borderRadius: 14, maxWidth: 1640, textAlign: "center", wordBreak: "keep-all" }}>{c[2]}</div>
    </div>
  );
};

// 손그림 한 컷: 선화가 위→아래로 펜처럼 드러나고(0.8초) 0.3초 뒤 컬러로 번짐 + 느린 밀기
const Ink: React.FC<{ n: string; side?: "left" | "right" | "center"; size?: number; draw?: boolean; children?: React.ReactNode }> =
  ({ n, side = "left", size = 990, draw = true, children }) => {
    const f = useCurrentFrame();
    const reveal = draw ? ez(f, 0, 24) : 1;
    const color = draw ? ez(f, 33, 45) : 1;
    const z = interpolate(f, [0, 300], [1.0, 1.06], { extrapolateRight: "clamp" });
    const left = side === "left" ? 120 : side === "right" ? 1920 - 120 - size : (1920 - size) / 2;
    const box: React.CSSProperties = { position: "absolute", left, top: -30, width: size, height: size };
    return (
      <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ ...box, transform: `scale(${z})`, transformOrigin: "50% 60%" }}>
          <Img src={staticFile(`p2/g_${n}.png`)} style={{ position: "absolute", inset: 0, width: size, height: size, mixBlendMode: "multiply",
            clipPath: `inset(0 0 ${(1 - reveal) * 100}% 0)` }} />
          <Img src={staticFile(`p2/c_${n}.png`)} style={{ position: "absolute", inset: 0, width: size, height: size, opacity: color, mixBlendMode: "multiply" }} />
        </div>
        {children}
      </AbsoluteFill>
    );
  };

// 손글씨 — 사장님 10-30 "글자들 좀 더 크고 생동감 있게": 글자마다 튀어나오며(살짝 커졌다 제자리) 기울기가 제각각,
// 다 써지면 주황 밑줄이 손으로 그어지고 글자 덩어리가 아주 천천히 숨 쉬듯 움직인다.
const Hand: React.FC<{ text: string; x: number; y: number; size?: number; color?: string; delay?: number; underline?: boolean }> =
  ({ text, x, y, size = 150, color = INK, delay = 6, underline = true }) => {
    const f = useCurrentFrame();
    const chars = Array.from(text);
    const per = 2;
    const doneAt = delay + chars.length * per;
    const breathe = 1 + 0.015 * Math.sin((f - doneAt) / 14) * (f > doneAt ? 1 : 0);
    const ul = ez(f, doneAt + 2, doneAt + 12);
    return (
      <div style={{ position: "absolute", left: x, top: y, maxWidth: 900, transform: `scale(${breathe}) rotate(-2deg)`, transformOrigin: "0 50%" }}>
        <div style={{ fontFamily: "Pen", fontSize: size, color, lineHeight: 1.08, whiteSpace: "pre-wrap", wordBreak: "keep-all" }}>
          {chars.map((c, k) => {
            const st = delay + k * per;
            const a = ez(f, st, st + 6);
            const pop = interpolate(f, [st, st + 4, st + 9], [0.4, 1.25, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const rot = ((k * 37) % 11) - 5;
            return c === "\n" ? <br key={k} /> : (
              <span key={k} style={{ display: "inline-block", opacity: a, transform: `scale(${pop}) rotate(${rot * (1 - a * 0.6)}deg)`, minWidth: c === " " ? size * 0.3 : undefined }}>{c}</span>
            );
          })}
        </div>
        {underline && <svg width={700} height={40} style={{ display: "block", marginTop: -6 }}>
          <path d="M6 24 C 160 6, 360 36, 690 14" stroke={OR} strokeWidth={10} fill="none" strokeLinecap="round"
            strokeDasharray={720} strokeDashoffset={720 * (1 - ul)} />
        </svg>}
      </div>
    );
  };

const Bubble: React.FC<{ text: string; x: number; y: number }> = ({ text, x, y }) => {
  const f = useCurrentFrame();
  const a = ez(f, 10, 20);
  return (
    <div style={{ position: "absolute", left: x, top: y, padding: "26px 40px", background: "#fff", border: `5px solid ${INK}`, borderRadius: 50,
      fontFamily: "Pen", fontSize: 112, color: INK, opacity: a, transform: `scale(${0.9 + 0.1 * a})` }}>{text}</div>
  );
};

// 숏템 v1 → 숏템 v2 → 숏클 v1 — 키네틱 타이포(사장님 10-30).
// 지금 말하는 단계가 화면 가운데에 크게 '쾅' 박히고(넘침 튕김), 앞 단계는 작아지며 위 줄로 밀려 올라가 이어진다.
// 시각 = 필재 발음 시각(숏템 v1=장면 시작, v2="브이투", 숏클="숏클까지"). '거의 다 반영'은 도장처럼 찍힌다.
const Evolve: React.FC<{ tV2: number; tSC: number; tStamp: number }> = ({ tV2, tSC, tStamp }) => {
  const f = useCurrentFrame();
  const steps = [
    { label: "숏템 v1", at: 0.15, color: INK },
    { label: "숏템 v2", at: tV2, color: INK },
    { label: "숏클 v1", at: tSC, color: OR },
  ];
  let cur = 0;
  steps.forEach((s, k) => { if (f >= S(s.at)) cur = k; });
  const slam = (at: number) => interpolate(f, [S(at), S(at) + 5, S(at) + 10], [2.2, 0.92, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const stampA = ez(f, S(tStamp), S(tStamp) + 5);
  const stampS = interpolate(f, [S(tStamp), S(tStamp) + 5, S(tStamp) + 9], [2.4, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const burst = ez(f, S(tSC) + 2, S(tSC) + 14);
  return (
    <AbsoluteFill style={{ background: PAPER, overflow: "hidden" }}>
      {/* 위 줄: 지나간 단계들이 작게 이어짐 */}
      <div style={{ position: "absolute", left: 0, right: 0, top: 90, display: "flex", flexDirection: "row", justifyContent: "center", gap: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: "#9a958d" }}>
        {steps.slice(0, cur).map((s, k) => {
          const a = ez(f, S(steps[k + 1].at), S(steps[k + 1].at) + 8);
          return <div key={k} style={{ opacity: a, transform: `translateY(${(1 - a) * 220}px)` }}>{s.label} <span style={{ color: "#c9c3b8" }}>→</span></div>;
        })}
      </div>
      {/* 가운데: 지금 단계 쾅 */}
      {steps.map((s, k) => k === cur && (
        <div key={k} style={{ position: "absolute", left: 0, right: 0, top: 300, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 260, color: s.color,
          letterSpacing: -6, transform: `scale(${slam(s.at)}) rotate(${k === 2 ? -3 : 0}deg)`, textShadow: k === 2 ? "0 10px 40px rgba(224,122,43,.35)" : "none" }}>{s.label}</div>
      ))}
      {/* 숏클 등장 때 집중선 */}
      {cur === 2 && Array.from({ length: 16 }).map((_, k) => {
        const ang = (k / 16) * Math.PI * 2;
        return <div key={k} style={{ position: "absolute", left: 960, top: 440, width: 900 * burst, height: 8, background: OR, opacity: 0.55 * (1 - burst * 0.6),
          transformOrigin: "0 50%", transform: `rotate(${ang}rad) translateX(${260 + 200 * burst}px)`, borderRadius: 4 }} />;
      })}
      {/* 도장: 회원님 요청, 거의 다 반영 */}
      <div style={{ position: "absolute", left: 1290, top: 650, padding: "14px 28px", border: `8px solid ${OR}`, borderRadius: 16, color: OR, fontFamily: "Pen", fontSize: 76,
        opacity: stampA, transform: `scale(${stampS}) rotate(-8deg)` }}>회원님 요청 거의 다 반영</div>
    </AbsoluteFill>
  );
};

// ── 검색 화면 (사장님 10-30 "글자 줌할 때 강조효과·밑줄, 화면이 밋밋하고 너무 빠르니 천천히")
// 실제 유튜브 검색 결과 캡처(2배, CSS 1920 폭 기준 좌표 v4_titles_*.json)를 브라우저 창에 넣고,
// 문장 하나 = 검색 한 장. 넓게 → 천천히 그 제목으로 밀어 들어가고 → 형광펜이 그어지고 밑줄. 오른쪽 큰 글자 모션.
type Shot = { page: number; term: string; from: [number, number, number]; to: [number, number, number]; hl?: [number, number, number, number]; lines: string[]; accent?: number };
const WIN = { x: 60, y: 70, w: 1180, h: 780 };
const Browser: React.FC<{ shot: Shot; dur: number }> = ({ shot, dur }) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [0, dur * 0.7], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const x0 = shot.from[0] + (shot.to[0] - shot.from[0]) * p;
  const y0 = shot.from[1] + (shot.to[1] - shot.from[1]) * p;
  const w = shot.from[2] + (shot.to[2] - shot.from[2]) * p;
  const s = WIN.w / w;
  const hlA = shot.hl ? ez(f, dur * 0.62, dur * 0.62 + 10) : 0;
  const ulA = shot.hl ? ez(f, dur * 0.62 + 8, dur * 0.62 + 18) : 0;
  return (
    <div style={{ position: "absolute", left: WIN.x, top: WIN.y, width: WIN.w, height: WIN.h, borderRadius: 18, overflow: "hidden", background: "#fff", boxShadow: "0 24px 70px rgba(0,0,0,.28)", border: "1px solid #ddd" }}>
      <div style={{ height: 44, background: "#f1f1f1", display: "flex", flexDirection: "row", alignItems: "center", gap: 10, paddingLeft: 18 }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c }} />)}
        <div style={{ marginLeft: 20, fontFamily: "Pret", fontWeight: 800, fontSize: 22, color: "#555" }}>youtube.com · "{shot.term}"</div>
      </div>
      <div style={{ position: "absolute", left: 0, top: 44, width: WIN.w, height: WIN.h - 44, overflow: "hidden" }}>
        <Img src={staticFile(`srch/s${shot.page}.jpg`)} style={{ position: "absolute", width: 1920 * s, left: -x0 * s, top: -y0 * s }} />
        {shot.hl && <>
          <div style={{ position: "absolute", left: (shot.hl[0] - x0) * s - 8, top: (shot.hl[1] - y0) * s - 6, width: (shot.hl[2] * s + 16) * hlA, height: shot.hl[3] * s + 12,
            background: "rgba(255,214,0,.42)", borderRadius: 6 }} />
          <div style={{ position: "absolute", left: (shot.hl[0] - x0) * s, top: (shot.hl[1] + shot.hl[3] - y0) * s + 10, width: shot.hl[2] * s * ulA, height: 9, background: "#E5484D", borderRadius: 5 }} />
        </>}
      </div>
    </div>
  );
};
const SideText: React.FC<{ lines: string[]; term: string; accent?: number }> = ({ lines, term, accent }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 1290, top: 150, width: 600 }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: "#9a958d", opacity: ez(f, 0, 10) }}>검색어 · {term}</div>
      {lines.map((l, k) => {
        const st = 8 + k * 14;
        const a = ez(f, st, st + 10);
        const sc = interpolate(f, [st, st + 5, st + 10], [1.5, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <div key={k} style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 84, lineHeight: 1.12, marginTop: k ? 6 : 18, color: k === accent ? OR : INK,
          opacity: a, transform: `scale(${sc})`, transformOrigin: "0 50%", wordBreak: "keep-all" }}>{l}</div>;
      })}
    </div>
  );
};
const Search: React.FC<{ cuts: [number, Shot][]; end: number }> = ({ cuts, end }) => (
  <AbsoluteFill style={{ background: PAPER }}>
    {cuts.map(([at, shot], k) => {
      const nxt = k + 1 < cuts.length ? cuts[k + 1][0] : end;
      const dur = S(nxt - at);
      return <Sequence key={k} from={S(at - cuts[0][0])} durationInFrames={dur}>
        <Browser shot={shot} dur={dur} />
        <SideText lines={shot.lines} term={shot.term} accent={shot.accent} />
      </Sequence>;
    })}
  </AbsoluteFill>
);
const Fan: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {[1, 2, 3, 4].map((p, k) => {
        const a = ez(f, k * 3, k * 3 + 10);
        return <div key={p} style={{ position: "absolute", left: 120 + k * 150, top: 120 + k * 40, width: 760, height: 520, overflow: "hidden", borderRadius: 14, boxShadow: "0 16px 40px rgba(0,0,0,.25)",
          transform: `rotate(${(k - 1.5) * 4}deg) translateY(${(1 - a) * 80}px)`, opacity: a, background: "#fff" }}>
          <Img src={staticFile(`srch/s${p}.jpg`)} style={{ width: 760 * 1.6, marginLeft: -200 }} />
        </div>;
      })}
      <div style={{ position: "absolute", left: 1150, top: 260, fontFamily: "Pret", fontWeight: 800, lineHeight: 1.15 }}>
        <div style={{ fontSize: 100, color: INK, opacity: ez(f, 4, 14) }}>다 해 보셨죠?</div>
        <div style={{ fontSize: 100, color: OR, opacity: ez(f, S(0.7), S(0.7) + 10) }}>갈증은<br />그대로</div>
      </div>
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const T = {
    q: 0, night: t("밤에 쇼츠로"), heart: t("가슴이 뛰어"), search: t("자, 보시면"), done: t("다 해 보셨잖아요"),
    notFirst: t("처음 시작하신"), paid: t("결제해 보고"), around: t("돌고 돌아"), know: t("저는 압니다"),
    sept: t("구월에"), lost: t("헤매지 않게"), req: t("거의 다 반영"), why: t("왜 안 됐는지"),
  };
  const searchEnd = Math.min(T.notFirst, T.search + 19.6);
  const seq = (a: number, b: number, el: React.ReactNode) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{el}</Sequence>;
  const rel = (x: number) => x - T.req;
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Font />
      {seq(0, T.night, <Ink n="f_tired" side="right"><Hand text={"혹시\n이런 적\n없으셨나요?"} x={160} y={170} size={175} /></Ink>)}
      {seq(T.night, T.heart, <Ink n="f_night_phone" side="left"><Bubble text="쇼츠로 돈 번다" x={1080} y={250} /></Ink>)}
      {seq(T.heart, T.search, <Ink n="f_excited" side="right"><Hand text={"두근두근\n잠이 안 와"} x={180} y={220} size={175} color={OR} /></Ink>)}
      {seq(T.search, T.done, <Search end={T.done} cuts={[
        [T.search, { page: 1, term: "쇼츠 자동화 프로그램", from: [0, 0, 1920], to: [300, 0, 1500], lines: ["많은 분들이", "검색하는 말"], accent: 1 }],
        [t("하나씩 보시면"), { page: 1, term: "쇼츠 자동화 프로그램", from: [300, 0, 1500], to: [380, 420, 1400], lines: ["하나씩 보면", "어디서 막혔는지", "보입니다"], accent: 1 }],
        [t("눌러 봤더니"), { page: 1, term: "쇼츠 자동화 프로그램", from: [380, 600, 1400], to: [950, 740, 720], hl: [971, 947, 639, 26], lines: ["버튼 하나면", "된다더니"], accent: 1 }],
        [t("폴더엔 강의가"), { page: 2, term: "쇼츠 수익화 강의", from: [300, 1400, 1500], to: [950, 1560, 720], hl: [971, 1767, 686, 52], lines: ["강의는 쌓이는데", "통장은 그대로"], accent: 1 }],
        [t("저녁에 잠깐"), { page: 3, term: "AI 쇼츠 부업", from: [300, 600, 1500], to: [950, 760, 720], hl: [971, 963, 686, 52], lines: ["부업이", "본업보다 바빠졌다"], accent: 1 }],
        [t("까만 창"), { page: 4, term: "클로드 쇼츠 자동화", from: [300, 100, 1500], to: [950, 220, 720], hl: [971, 425, 686, 52], lines: ["까만 창 앞에서", "멈춘 밤"], accent: 1 }],
      ]} />)}
      {seq(T.done, searchEnd, <Fan />)}
      {seq(searchEnd, T.paid, <Ink n="m_tired" side="left"><Hand text={"처음이 아닌\n분들이 대부분"} x={1060} y={240} size={160} /></Ink>)}
      {seq(T.paid, T.around, <Ink n="f_frustr_head" side="right"><Hand text={"프로그램 결제\n유료 강의"} x={170} y={240} size={160} /></Ink>)}
      {seq(T.around, T.know, <Ink n="f_dream" side="left"><Hand text={"돌고 돌아\n정착"} x={1100} y={260} size={185} color={OR} /></Ink>)}
      {seq(T.know, T.sept, <AbsoluteFill style={{ background: PAPER, justifyContent: "center", alignItems: "center" }}>
        <Hand text="그 마음, 저는 압니다" x={330} y={330} size={210} delay={0} /></AbsoluteFill>)}
      {seq(T.sept, T.req, <AbsoluteFill style={{ background: "#101114" }}>
        <Img src={staticFile("p2/shortem.png")} style={{ position: "absolute", left: 560, top: 70, width: 1300, borderRadius: 16, boxShadow: "0 20px 60px rgba(0,0,0,.6)" }} />
        <div style={{ position: "absolute", left: 90, top: 300, fontFamily: "Pret", fontWeight: 800, color: "#fff" }}>
          <div style={{ fontSize: 56, color: OR }}>2026. 9</div>
          <div style={{ fontSize: 96, lineHeight: 1.1 }}>숏템<br />메이커</div>
        </div>
      </AbsoluteFill>)}
      {seq(T.req, T.why, <Evolve tV2={rel(46.17)} tSC={rel(47.69)} tStamp={rel(44.66)} />)}{/* 46.17·47.69·44.66 = s01 필재 발음 실측(브이투·숏클까지·거의 다) */}
      {seq(T.why, END, <Ink n="m_laptop_hope" side="right"><Hand text={"왜 안 됐을까?"} x={170} y={300} size={190} color={OR} /></Ink>)}
      <Audio src={staticFile("full/s01.mp3")} />
      <Caption />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P02" component={Main} durationInFrames={S(END)} fps={FPS} width={1920} height={1080} />);
