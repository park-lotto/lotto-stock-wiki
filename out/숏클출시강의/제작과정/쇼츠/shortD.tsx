import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, OffthreadVideo, Sequence, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";

// 숏클 쇼츠 D "프리셋 이름만 바꿨습니다"(세로 1080x1920) — 대본 쇼츠4편_대본_페이블_v2.md D.
// 시험 8번 = 롱폼 조각10 과 같은 실제 결과물(public/p10). 터미널 줄은 실제로 넣은 명령(프리셋 이름)이고, 큰 글자는 그 스타일 이름.
const FPS = 30, S = (s: number) => Math.round(s * FPS);
const W = 1080, H = 1920;
const BG = "#0E0E10", OR = "#F6A93B", WH = "#FFFFFF", YEL = "#FFD84D", GR = "#6EE7B7";
const ez = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
const pop = (f: number, at: number) => interpolate(f, [at, at + 5, at + 9], [0.6, 1.08, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const LN: [number, number, [number, string][]][] = [
  [2.0, 0, [[0.25, "바꾼 건 프리셋 이름 하나예요."]]],
  [4.16, 0.2, [[0.93, "근데 여덟 편이"], [2.16, "전부 다른 채널처럼 나왔어요."]]],
  [2.96, 0.2, [[0.12, "자, 보시면."], [1.37, "같은 PC, 같은 한 줄이에요."]]],
  [2.56, 0, [[0.25, "\"해외 화장품.\""], [1.3, "외국인 코 팩 영상."]]],
  [2.44, 0, [[0.31, "\"원음에 나레이션.\""], [1.48, "아이언맨 헬멧."]]],
  [2.52, 0, [[0.26, "\"자막이랑 배경음만.\""], [1.39, "하키 퍽 소년."]]],
  [2.12, 0, [[0.24, "\"숨은 이야기.\""], [1.29, "바나나우유."]]],
  [2.16, 0, [[0.37, "\"연예인 후기.\""], [1.29, "안문숙 도브."]]],
  [3.04, 0, [[0.3, "\"연예인 레시피.\""], [1.9, "성시경 신라면."]]],
  [2.2, 0, [[0.31, "\"음악으로만.\""], [1.07, "베이스 점프."]]],
  [3.0, 0.4, [[0.27, "\"숙소 주소 하나.\""], [1.43, "가평 계곡 펜션."]]],
  [1.8, 0.2, [[0.31, "여덟 가지 스타일, 여덟 줄."]]],
  [3.8, 0.2, [[0.34, "프리셋 하나에 채널 하나씩 붙이면,"], [2.53, "채널이 여덟 개예요."]]],
  [2.96, 0, [[0.36, "그러면 다음 줄엔,"], [1.05, "뭘 넣어 보시겠어요?"]]],
];
const L: number[] = []; LN.reduce((t, x) => { L.push(t); return t + x[0] + x[1]; }, 0);
const END = L[13] + LN[13][0] + 2.6;
const CAPS: [number, number, string][] = LN.flatMap(([d, , cs], i) => cs.map(([t, txt], k) =>
  [L[i] + t, L[i] + (cs[k + 1] ? cs[k + 1][0] : d - 0.1), txt] as [number, number, string]));

// 시험 8번: [프리셋 이름(실제 명령), 스타일, 결과 파일, 결과 이름]
const TESTS: [string, string, string, string][] = [
  ["해외 화장품", "해외 화장품", "p10/i1a_kopack.mp4", "코 팩"],
  ["해외 신기템", "원음 + 나레이션", "p10/j1a_ironman.mp4", "아이언맨 헬멧"],
  ["썰", "자막 + 배경음", "p10/j2a_hockey.mp4", "하키 퍽 소년"],
  ["썰 비하인드", "숨은 이야기", "p10/banana.mp4", "바나나우유"],
  ["연예인 후기", "연예인 + 후기", "p10/i1b_dove.mp4", "안문숙 도브"],
  ["연예인 레시피", "연예인 레시피", "p10/j2b_ramyun.mp4", "성시경 신라면"],
  ["해외 핫영상", "음악으로만", "p10/j1b_basejump.mp4", "베이스 점프"],
  ["숙소 주소", "숙소 주소 하나", "p10/stay_채널2.mp4", "가평 계곡 펜션"],
];

const Font = () => (
  <style>{`@font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}`}</style>
);
const T: React.CSSProperties = { fontFamily: "Pret", fontWeight: 800 };

const Title: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <div style={{ ...T, position: "absolute", left: 60, right: 60, top: 190, textAlign: "center", color: WH, fontSize: 84,
      background: "rgba(14,14,16,.85)", borderRadius: 28, padding: "22px 0 26px", opacity: ez(f, 0, 6) }}>
      <span style={{ color: YEL }}>프리셋 이름</span>만 바꿨습니다
    </div>
  );
};
const Caption: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const l = CAPS.find((x) => t >= x[0] - 0.03 && t < x[1]);
  if (!l) return null;
  return (
    <div style={{ position: "absolute", left: 60, right: 60, bottom: 430, display: "flex", justifyContent: "center" }}>
      <div style={{ ...T, fontSize: 54, lineHeight: 1.3, color: WH, background: "rgba(0,0,0,.76)", padding: "14px 28px", borderRadius: 16, textAlign: "center", wordBreak: "keep-all" }}>{l[2]}</div>
    </div>
  );
};

// 터미널 한 줄: 프리셋 자리만 노란 칸, 바뀔 때 위로 넘어가며 바뀜
const Cmd: React.FC<{ name: string; flipAt?: number; y?: number; blank?: boolean }> = ({ name, flipAt = -99, y = 400, blank }) => {
  const f = useCurrentFrame();
  const a = ez(f, flipAt, flipAt + 7);
  return (
    <div style={{ position: "absolute", left: 50, right: 50, top: y, padding: "22px 26px", border: "3px solid #3a3a40", borderRadius: 18, background: "#16171c",
      display: "flex", alignItems: "center", ...T, fontSize: 46, color: "#e8e8ea", whiteSpace: "nowrap" }}>
      <span style={{ color: OR, fontFamily: "Consolas, monospace" }}>&gt;&nbsp;</span>
      <span style={{ display: "inline-block", background: YEL, color: "#111", borderRadius: 10, padding: "2px 16px", minWidth: blank ? 240 : undefined,
        transform: `translateY(${(1 - a) * 18}px)`, opacity: 0.35 + 0.65 * a }}>{blank ? <span style={{ opacity: Math.floor(f / 14) % 2 ? 1 : 0 }}>▌</span> : name}</span>
      <span>&nbsp;프리셋으로 만들어 줘</span>
    </div>
  );
};

const Clip: React.FC<{ src: string; x: number; y: number; w: number; border?: string; style?: React.CSSProperties }> = ({ src, x, y, w, border = "#2a2a30", style }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, height: w * 16 / 9, borderRadius: w / 14, overflow: "hidden", border: `5px solid ${border}`, boxShadow: "0 16px 50px rgba(0,0,0,.7)", ...style }}>
    <OffthreadVideo src={staticFile(src)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  </div>
);

// d01~d03: 한 줄 → 여덟 편이 한꺼번에 → 같은 PC 같은 한 줄
const Intro: React.FC = () => {
  const f = useCurrentFrame();
  const burst = S(L[1] + 0.93);
  const same = S(L[2] + 1.37);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Cmd name="해외 화장품" y={420} />
      {TESTS.map(([, , src], k) => (
        <Clip key={k} src={src} x={60 + (k % 4) * 245} y={600 + Math.floor(k / 4) * 420} w={225}
          style={{ opacity: ez(f, burst + k, burst + k + 5), transform: `scale(${pop(f, burst + k)})` }} />
      ))}
      {f >= same && <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 560, textAlign: "center", fontSize: 40, color: "#9a9aa3", opacity: ez(f, same, same + 8) }}>같은 PC · 같은 클로드 · 같은 한 줄</div>}
    </AbsoluteFill>
  );
};

// d04~d11: 시험 하나씩 — 프리셋 칸이 바뀌고 큰 스타일 이름 → 결과 등장
const Test: React.FC<{ k: number }> = ({ k }) => {
  const f = useCurrentFrame();
  const [preset, style, src, item] = TESTS[k];
  const sAt = S(LN[3 + k][2][0][0]);
  const iAt = S(LN[3 + k][2][1][0]);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Cmd name={preset} flipAt={0} y={420} />
      <div style={{ ...T, position: "absolute", left: 60, top: 560, fontSize: 40, color: OR }}>{k + 1} / 8</div>
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 620, textAlign: "center", fontSize: 92, color: WH, opacity: ez(f, sAt - 3, sAt + 4),
        transform: `scale(${0.9 + 0.1 * ez(f, sAt - 3, sAt + 4)})` }}>{style}</div>
      <Clip src={src} x={310} y={760} w={460} border={OR} style={{ opacity: ez(f, iAt - 4, iAt + 3), transform: `translateY(${(1 - ez(f, iAt - 4, iAt + 5)) * 60}px)` }} />
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 1580, textAlign: "center", fontSize: 44, color: "#bdbdc4", opacity: ez(f, iAt, iAt + 6) }}>{item}</div>
    </AbsoluteFill>
  );
};

// d12~d13: 여덟 줄 쌓기 → 채널 여덟 개
const Stack: React.FC = () => {
  const f = useCurrentFrame();
  const ch = S(L[12] - L[11] + 0.6);
  return (
    <AbsoluteFill style={{ background: BG }}>
      {TESTS.map(([preset, , src], k) => {
        const a = ez(f, k * 2, k * 2 + 6);
        const c = ez(f, ch + k * 5, ch + k * 5 + 6);
        return (
          <div key={k} style={{ position: "absolute", left: 60, top: 440 + k * 120, width: 960, height: 104, display: "flex", alignItems: "center", gap: 20, opacity: a,
            transform: `translateX(${(1 - a) * -60}px)` }}>
            <div style={{ width: 58, height: 104, borderRadius: 8, overflow: "hidden" }}><OffthreadVideo src={staticFile(src)} muted style={{ width: 58, height: 104, objectFit: "cover" }} /></div>
            <div style={{ ...T, fontSize: 44, color: "#111", background: YEL, borderRadius: 10, padding: "4px 16px" }}>{preset}</div>
            <div style={{ ...T, fontSize: 40, color: "#cfcfd4" }}>프리셋</div>
            <div style={{ ...T, marginLeft: "auto", fontSize: 40, color: WH, background: "#E62117", borderRadius: 30, padding: "6px 22px", opacity: c, transform: `scale(${pop(f, ch + k * 5)})` }}>▶ 채널 {k + 1}</div>
          </div>
        );
      })}
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 1420, textAlign: "center", fontSize: 72, color: WH, opacity: ez(f, ch + 40, ch + 48) }}>채널 <span style={{ color: OR }}>8개</span></div>
    </AbsoluteFill>
  );
};

// d14 + 끝: 빈 칸 커서
const Next: React.FC = () => {
  const f = useCurrentFrame();
  const fin = S(LN[13][0] + 0.1);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Cmd name="" blank y={760} />
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 960, textAlign: "center", color: WH, opacity: ez(f, fin, fin + 10) }}>
        <div style={{ fontSize: 84 }}>다음 줄엔,</div>
        <div style={{ fontSize: 84 }}><span style={{ color: YEL }}>뭘</span> 넣으시겠어요?</div>
        <div style={{ fontSize: 50, color: OR, marginTop: 34 }}>숏클</div>
      </div>
    </AbsoluteFill>
  );
};

const Main: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    <Font />
    <Sequence from={0} durationInFrames={S(L[3])}><Intro /></Sequence>
    {TESTS.map((_, k) => (
      <Sequence key={k} from={S(L[3 + k])} durationInFrames={S(L[4 + k] - L[3 + k])}><Test k={k} /></Sequence>
    ))}
    <Sequence from={S(L[11])} durationInFrames={S(L[13] - L[11])}><Stack /></Sequence>
    <Sequence from={S(L[13])} durationInFrames={S(END - L[13])}><Next /></Sequence>
    <Sequence from={0} durationInFrames={S(L[13] + LN[13][0])}><Title /></Sequence>
    {LN.map((x, i) => (
      <Sequence key={i} from={S(L[i])} durationInFrames={S(x[0])}>
        <Audio src={staticFile(`sh/D/d${String(i + 1).padStart(2, "0")}.mp3`)} />
      </Sequence>
    ))}
    <Caption />
  </AbsoluteFill>
);
registerRoot(() => <Composition id="ShortD" component={Main} durationInFrames={S(END)} fps={FPS} width={W} height={H} />);
