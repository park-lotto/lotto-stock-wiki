import React from "react";
import { AbsoluteFill, Audio, Composition, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, INK, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각10 '결과물 등장 — 시험 8번'(s22, 52초).
// 진화: 옛 판은 결과 카드 영상을 순서대로 붙였다. 이번엔 '시험 n/8' 판이 왼쪽에 서고, 위에 그 프리셋 한 줄이 타이핑되며,
// 필재가 결과물 이름(코 팩·연어 크림…)을 말하는 바로 그 순간 그 실제 완성본이 폰으로 튀어나온다. 마지막엔 23편이 한 벽으로 모인다.
const SC = (PLAN as any)[22];
const CAPS = SC.caps as Cap[];
const END = SC.sec + 0.4;
const LF: React.FC<{ r: (f: number) => React.ReactNode }> = ({ r }) => <>{r(useCurrentFrame())}</>;
const sq = (a: number, b: number, el: React.ReactNode | ((f: number) => React.ReactNode)) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{typeof el === "function" ? <LF r={el} /> : el}</Sequence>;
const pop = (f: number, at: number, k = 1.4) => interpolate(f, [at, at + 5, at + 10], [k, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

// [시작초, 끝초, 프리셋, 한 줄 명령, 색, [이름, 클립, 등장초][]]
type T = [number, number, string, string, string, [string, string, number][]];
const TESTS: T[] = [
  [5.48, 10.88, "해외 화장품", "해외 화장품 프리셋으로 만들어 줘", "#FCE9F0", [["코 팩", "i1a_kopack", 8.59], ["연어 크림", "i1a_salmon", 8.99], ["선크림", "i1a_tirtir", 9.5]]],
  [10.88, 15.48, "원음 + 나레이션", "해외 신기템 프리셋으로 만들어 줘", "#E9F4FF", [["아이언맨 헬멧", "j1a_ironman", 13.54], ["미니카", "j1a_porsche", 14.29], ["가짜 잠자리", "j1a_dragonfly", 14.98]]],
  [15.48, 19.6, "자막 + 배경음", "썰 프리셋으로 만들어 줘", "#FFF6DA", [["하키 퍽 소년", "j2a_hockey", 17.14], ["파울볼 아빠", "j2a_foulball", 18.03], ["LED 수도꼭지", "j2a_led", 18.75]]],
  [19.6, 24.88, "숨은 이야기", "썰 비하인드 프리셋으로 만들어 줘", "#EFE9FF", [["아웃백 비밀", "outback", 22.43], ["바나나우유", "banana", 23.1], ["코스트코 가격표", "costco", 23.75]]],
  [24.88, 29.34, "연예인 + 후기", "연예인 후기 프리셋으로 만들어 줘", "#FFEDE3", [["함익병 도브", "i1b_dove", 26.94], ["강주은 가방", "i1b_tote", 27.78], ["김가연 비비", "i1b_kimbb", 28.51]]],
  [29.34, 33.36, "연예인 레시피", "연예인 레시피 프리셋으로 만들어 줘", "#E8F7EF", [["성시경 신라면", "j2b_ramyun", 30.76], ["김가연 오징어무", "j2b_squid", 31.88], ["강주은 티본", "j2b_tbone", 32.74]]],
  [33.36, 36.34, "음악으로만", "해외 핫영상 프리셋으로 만들어 줘", "#E3F1FA", [["베이스 점프", "j1b_basejump", 34.71], ["독수리 착지", "j1b_eagle", 35.21], ["사과 깎이", "j1b_apple", 35.79]]],
  [36.34, 41.07, "숙소 주소 하나", "이 숙소 주소로 숙소 쇼츠 만들어 줘", "#F1F0E8", [["숨은 계곡 1판", "stay_채널2", 39.02], ["숨은 계곡 2판", "stay_홈디노", 40.41]]],
];

const Test: React.FC<{ k: number }> = ({ k }) => {
  const f = useCurrentFrame();
  const [t0, , name, cmd, bg, items] = TESTS[k];
  const n = Math.min(cmd.length, Math.floor(f / 1.2));
  return (
    <AbsoluteFill style={{ background: bg }}>
      {/* 시험 번호판 */}
      <div style={{ position: "absolute", left: 60, top: 170, width: 420 }}>
        <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 46, color: "#8a857c" }}>시험</div>
        <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 230, color: INK, lineHeight: 1, transform: `scale(${pop(f, 0, 1.6)})`, transformOrigin: "0 50%" }}>{k + 1}<span style={{ fontSize: 90, color: "#b9b3a8" }}>/8</span></div>
        <div style={{ marginTop: 26, fontFamily: "Pen", fontSize: 92, color: OR, lineHeight: 1.05, wordBreak: "keep-all", opacity: ez(f, 6, 14) }}>{name}</div>
        <div style={{ marginTop: 30, display: "flex", flexDirection: "row", gap: 8 }}>
          {TESTS.map((_, j) => <div key={j} style={{ width: 38, height: 12, borderRadius: 6, background: j < k ? INK : j === k ? OR : "rgba(0,0,0,.12)" }} />)}
        </div>
      </div>
      {/* 한 줄 명령 */}
      <div style={{ position: "absolute", left: 540, top: 50, width: 1320, padding: "18px 30px", background: "#16171b", borderRadius: 16, fontFamily: "Consolas, monospace", fontSize: 42, color: "#eee" }}>
        <span style={{ color: OR }}>&gt; </span>{cmd.slice(0, n)}<span style={{ opacity: Math.floor(f / 10) % 2 ? 1 : 0, color: OR }}>▌</span>
      </div>
      {/* 결과물 폰: 이름이 들리는 순간 */}
      {items.map(([label, clip, at], j) => {
        const st = S(at - t0);
        const x = 560 + j * 440;
        if (f < st) return <div key={j} style={{ position: "absolute", left: x, top: 170, width: 370, height: 652, borderRadius: 30, border: "5px dashed rgba(0,0,0,.18)",
          display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 36, color: "rgba(0,0,0,.3)", opacity: ez(f, 4 + j * 4, 12 + j * 4) }}>
          만드는 중{".".repeat((Math.floor(f / 8) + j) % 3 + 1)}</div>;
        return (
          <div key={j} style={{ position: "absolute", left: x, top: 170, width: 370, transform: `scale(${pop(f, st, 1.25)}) rotate(${(j - 1) * 1.5}deg)`, transformOrigin: "50% 100%" }}>
            <div style={{ width: 370, height: 640, borderRadius: 30, overflow: "hidden", border: "6px solid #1a1a1a", boxShadow: "0 18px 40px rgba(0,0,0,.25)", background: "#000" }}>
              <OffthreadVideo src={staticFile(`p10/${clip}.mp4`)} muted style={{ width: 360, height: 640, objectFit: "cover" }} />
            </div>
            <div style={{ position: "absolute", left: 16, top: 16, padding: "8px 18px", background: "rgba(255,255,255,.95)", borderRadius: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 32, color: INK }}>{label}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// 23편이 한 벽으로 — 여덟 줄, 같은 PC·같은 클로드, 다른 건 프리셋 이름뿐
const ALL = TESTS.flatMap((t) => t[5].map((it) => it[1]));
const Wall: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const shrink = ez(f, 0, 20);
  return (
    <AbsoluteFill style={{ background: "#141519" }}>
      <div style={{ position: "absolute", left: 60, top: 150, display: "flex", flexDirection: "row", flexWrap: "wrap", gap: 10, width: 1800, justifyContent: "center" }}>
        {ALL.map((c, j) => <div key={j} style={{ width: 140, height: 249, borderRadius: 12, overflow: "hidden", opacity: ez(f, j * 0.8, j * 0.8 + 8), transform: `scale(${0.6 + 0.4 * shrink})` }}>
          <OffthreadVideo src={staticFile(`p10/${c}.mp4`)} muted style={{ width: 140, height: 249, objectFit: "cover" }} /></div>)}
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 40, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: "#fff", opacity: ez(f, 4, 12) }}>
        여덟 가지 스타일 · <span style={{ color: OR }}>여덟 줄</span></div>
      {now >= 42.22 && <div style={{ position: "absolute", left: 0, right: 0, top: 700, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#6EE7B7", transform: `scale(${pop(f, S(42.22 - base))})` }}>
        전부 같은 PC · 같은 클로드</div>}
    </AbsoluteFill>
  );
};

// 다른 건 프리셋 이름뿐 → 프리셋 하나 = 채널 하나 → 채널 8개
const Channels: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const ch = now >= 47.53;
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 60, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: INK }}>
        다른 건 딱 하나, <span style={{ color: OR, borderBottom: `8px solid ${OR}` }}>프리셋 이름</span>뿐</div>
      <div style={{ position: "absolute", left: 140, top: 210, display: "flex", flexDirection: "row", flexWrap: "wrap", gap: 22, width: 1640 }}>
        {TESTS.map((t, j) => {
          const at = S(47.53 - base) + j * 3;
          const on = ch && f >= at;
          return <div key={j} style={{ width: 385, height: 220, borderRadius: 24, background: on ? "#fff" : "rgba(0,0,0,.05)", border: `4px solid ${on ? INK : "#ddd5c8"}`, padding: "22px 26px",
            transform: `scale(${on ? pop(f, at, 1.2) : 1})`, boxShadow: on ? "0 10px 26px rgba(0,0,0,.1)" : "none", opacity: ez(f, j * 2, j * 2 + 8) }}>
            <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 30, color: "#9a958d" }}>프리셋</div>
            <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 46, color: INK, marginTop: 4 }}>{t[2]}</div>
            {on && <div style={{ marginTop: 18, display: "inline-block", padding: "8px 20px", borderRadius: 30, background: OR, fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: "#fff" }}>▶ 채널 {j + 1}</div>}
          </div>;
        })}
      </div>
      {now >= 49.92 && <Slam text="채널 8개" at={S(49.92 - base)} y={720} size={120} color={OR} />}
    </AbsoluteFill>
  );
};

const Main: React.FC = () => (
  <AbsoluteFill style={{ background: PAPER }}>
    <Fonts />
    {sq(0, 1.52, (lf: number) => <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 330, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 140, color: "#b9b3a8" }}>
        <span style={{ position: "relative" }}>말로만<div style={{ position: "absolute", left: -10, right: -10, top: "52%", height: 14, background: "#E5484D", transform: `scaleX(${ez(lf, 10, 22)})`, transformOrigin: "left" }} /></span> = 광고</div></AbsoluteFill>)}
    {sq(1.52, 5.48, (lf: number) => <AbsoluteFill style={{ background: "#141519" }}>
      <Slam text="8" at={S(0.4)} y={90} size={420} color={OR} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 560, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 72, color: "#fff", opacity: ez(lf, S(0.6), S(0.6) + 8) }}>번 돌려 봤어요</div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 680, textAlign: "center", fontFamily: "Pen", fontSize: 80, color: "#9aa", opacity: ez(lf, S(1.6), S(1.6) + 10) }}>프리셋만 바꾸고, 한 줄씩</div></AbsoluteFill>)}
    {TESTS.map((t, k) => <React.Fragment key={k}>{sq(t[0], t[1], <Test k={k} />)}</React.Fragment>)}
    {sq(41.07, 44.85, <Wall base={41.07} />)}
    {sq(44.85, 51.08, <Channels base={44.85} />)}
    {sq(51.08, END, <AbsoluteFill style={{ background: PAPER }}><Slam text="무슨 말인지 아시겠죠?" at={2} y={380} size={120} /></AbsoluteFill>)}
    <Audio src={staticFile("full/s22.mp3")} />
    <Caption caps={CAPS} />
  </AbsoluteFill>
);
registerRoot(() => <Composition id="P10" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
