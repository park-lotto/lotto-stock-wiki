import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, Img, OffthreadVideo, Sequence, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";

// 숏클 쇼츠 A "클로드로 만든 채널 50개, 유튜브 공장을 차렸습니다"(10-30 사장님: 폰이 만드는 게 아니라 클로드로 만든 채널로 공장)(세로 1080x1920, 21시 칸) — 대본 쇼츠4편_대본_페이블_v2.md A.
// 음성 = 줄마다 따로 뽑은 필재 sh/A/aNN.mp3 를 잘라내지 않고 통째로 이어 놓는다(LN). 끝줄 → 첫 컷 같은 앵글 = 루프.
const FPS = 30, S = (s: number) => Math.round(s * FPS);
const W = 1080, H = 1920;
const BG = "#0E0E10", OR = "#F6A93B", WH = "#FFFFFF", PAPER = "#FBF8F1", INK = "#1C1B19", YEL = "#FFD84D";
const ez = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

// 줄마다 따로 뽑은 필재 음성 sh/A/aNN.mp3(10-30: 한 덩어리를 정렬 시각으로 자르니 정렬이 최대 0.9초 빨라 말끝이 잘렸다).
// [파일 길이, 뒤에 더 쉴 초, 자막 조각들 [파일 안 시각(실제 쉼 측정), 글]]
const LN: [number, number, [number, string][]][] = [
  [2.36, 0, [[0.36, "이거, 제 유튜브 공장이에요."]]],
  [2.8, 0, [[0.21, "오십 개 채널,"], [1.18, "전부 클로드로 만든 채널이에요."]]],
  [3.2, 0, [[0.17, "쇼츠로 돈 번다는 강의,"], [1.92, "많이 들어 보셨잖아요."]]],
  [4.36, 0, [[0.23, "근데 막상 하면,"], [1.45, "소재 찾고, 자르고,"], [2.96, "대본 쓰고, 자막 달고."]]],
  [3.48, 0.3, [[0.34, "한 편에 하루가 가죠."], [2.45, "채널 하나도 벅차요."]]],
  [4.96, 0, [[0.32, "자, 보시면."], [1.5, "이 채널들에 올라가는 쇼츠,"], [3.41, "전부 클로드가 만들었어요."]]],
  [5.16, 1.0, [[0.37, "연예인 화장품 후기."], [1.7, "해외 대박 영상."], [2.95, "감동 썰."], [3.8, "레시피."], [4.46, "여행 숙소."]]],
  [3.48, 0, [[0.22, "원본 찾는 것부터 올리는 것까지,"], [2.48, "제가 한 게 없어요."]]],
  [1.44, 0.4, [[0.32, "제가 한 건 딱 하나."]]],
  [1.6, 0, [[0.18, "\"해외 화장품 만들어 줘.\""]]],
  [1.24, 0, [[0.38, "이 한 줄이에요."]]],
  [3.52, 0, [[0.28, "클로드로 만든 채널 오십 개,"], [2.08, "이렇게 공장이 돌아갑니다."]]],
];
const L: number[] = []; LN.reduce((t, x) => { L.push(t); return t + x[0] + x[1]; }, 0);   // L[i] = i번째 줄 시작(0부터)
const SPEECH_END = L[11] + LN[11][0];
const END = SPEECH_END + 2.8;
const CAPS: [number, number, string][] = LN.flatMap(([d, , cs], i) => cs.map(([t, txt], k) =>
  [L[i] + t, L[i] + (cs[k + 1] ? cs[k + 1][0] : d - 0.1), txt] as [number, number, string]));

const Font = () => (
  <style>{`@font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}`}</style>
);

// 위 고정 제목(쇼츠 화면 위 UI 아래)
const Title: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 70, right: 70, top: 190, textAlign: "center", fontFamily: "Pret", fontWeight: 800, lineHeight: 1.18,
      color: WH, background: "rgba(14,14,16,.82)", borderRadius: 28, padding: "18px 0 22px",
      opacity: ez(f, 0, 6), transform: `scale(${0.94 + 0.06 * ez(f, 0, 8)})` }}>
      <div style={{ fontSize: 76 }}>클로드로 만든 채널 <span style={{ color: OR }}>50개</span>,</div>
      <div style={{ fontSize: 76 }}>유튜브 공장을 차렸습니다</div>
    </div>
  );
};

// 자막: 아래 UI(약 380px) 위
const Caption: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const l = CAPS.find((x) => t >= x[0] - 0.03 && t < x[1]);
  if (!l) return null;
  return (
    <div style={{ position: "absolute", left: 60, right: 60, bottom: 430, display: "flex", justifyContent: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 54, lineHeight: 1.3, color: WH, background: "rgba(0,0,0,.74)", padding: "14px 28px",
        borderRadius: 16, textAlign: "center", wordBreak: "keep-all" }}>{l[2]}</div>
    </div>
  );
};

const Factory: React.FC<{ gray: number; from: number; zoom: [number, number]; dur: number }> = ({ gray, from, zoom, dur }) => {
  const f = useCurrentFrame();
  const z = interpolate(f, [0, S(dur)], zoom, { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      <OffthreadVideo src={staticFile("op/factory.mp4")} startFrom={S(from)} muted
        style={{ width: W, height: H, objectFit: "cover", transform: `scale(${z})`,
          filter: `grayscale(${gray}) contrast(${1 + 0.12 * gray}) brightness(${1 - 0.12 * gray})` }} />
    </AbsoluteFill>
  );
};

// 2.9~4.8 "50" 카운트
const Fifty: React.FC = () => {
  const f = useCurrentFrame();
  const n = Math.round(50 * ez(f, 0, S(0.8)));
  return (
    <AbsoluteFill>
      <Factory gray={1} from={2.7} zoom={[1.08, 1.13]} dur={1.9} />
      <AbsoluteFill style={{ background: "rgba(0,0,0,.35)" }} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 690, textAlign: "center", fontFamily: "Pret", fontWeight: 800 }}>
        <div style={{ fontSize: 300, color: OR, lineHeight: 1, transform: `scale(${1 + 0.15 * (1 - ez(f, S(0.8), S(1.1)))})` }}>{n}</div>
        <div style={{ fontSize: 76, color: WH, marginTop: 10, opacity: ez(f, S(0.6), S(0.9)) }}>개 채널 · 전부 클로드로</div>
      </div>
    </AbsoluteFill>
  );
};

// 4.8~6.95 손그림: 강의 들은 사람
const Lecture: React.FC = () => {
  const f = useCurrentFrame();
  const q = "쇼츠로 월 천 버는 법";
  const n = Math.max(0, Math.min(q.length, Math.floor((f - 6) / 2)));
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Img src={staticFile("hero/c_m_laptop_tired.png")} style={{ position: "absolute", left: 40, top: 760, width: 1000, opacity: ez(f, 0, 8) }} />
      <div style={{ position: "absolute", left: 90, right: 90, top: 560, height: 110, borderRadius: 60, background: WH, border: `4px solid ${INK}`,
        display: "flex", alignItems: "center", padding: "0 44px", fontFamily: "Pret", fontWeight: 800, fontSize: 52, color: INK, opacity: ez(f, 2, 10) }}>
        🔍&nbsp;{q.slice(0, n)}<span style={{ opacity: Math.floor(f / 12) % 2 ? 1 : 0 }}>|</span>
      </div>
      <div style={{ position: "absolute", right: 90, top: 700, display: "flex", gap: 14 }}>
        {["강의", "강의", "강의"].map((x, k) => (
          <div key={k} style={{ padding: "8px 22px", borderRadius: 30, background: OR, color: WH, fontFamily: "Pret", fontWeight: 800, fontSize: 38,
            opacity: ez(f, S(1.0) + k * 5, S(1.0) + k * 5 + 6), transform: `rotate(${(k - 1) * 6}deg)` }}>{x} {k + 1}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// 6.95~12.7 할 일이 쌓여 화면을 덮고, 시계가 밤으로
const WORDS: [number, string][] = [
  [L[3] + 1.45, "소재 찾기"], [L[3] + 1.85, "원본 찾기"], [L[3] + 2.25, "자르기"], [L[3] + 2.96, "대본"], [L[3] + 3.3, "목소리"], [L[3] + 3.68, "자막"], [L[3] + 4.0, "썸네일"],
];
const Pile: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const t = f / FPS + base;
  const night = ez(f, S(L[4] + 0.1 - base), S(L[4] + 1.3 - base));
  return (
    <AbsoluteFill style={{ background: interpolate(night, [0, 1], [0, 1]) > 0.5 ? "#15161c" : "#2a2622" }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 480, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: "#bdb6a9", opacity: ez(f, 0, 8) }}>근데 막상 하면</div>
      {WORDS.map(([at, w], k) => {
        const a = ez(f, S(at - base), S(at - base) + 6);
        const x = [120, 520, 200, 560, 140, 470, 300][k], y = [560, 650, 780, 880, 990, 1080, 1180][k];
        return (
          <div key={k} style={{ position: "absolute", left: x, top: y, padding: "14px 30px", borderRadius: 14, background: k % 2 ? "#3d3833" : "#4a443d",
            color: WH, fontFamily: "Pret", fontWeight: 800, fontSize: 66, opacity: a * (1 - 0.85 * night),
            transform: `translateY(${(1 - a) * -80}px) rotate(${[-4, 3, -2, 5, -3, 2, -5][k]}deg) scale(${0.9 + 0.1 * a})` }}>{w}</div>
        );
      })}
      {t >= L[4] + 0.1 && (
        <div style={{ position: "absolute", left: 0, right: 0, top: 640, display: "flex", flexDirection: "column", alignItems: "center", opacity: ez(f, S(L[4] + 0.1 - base), S(L[4] + 0.3 - base)) }}>
          <div style={{ width: 300, height: 300, borderRadius: 150, border: `10px solid ${WH}`, background: "rgba(0,0,0,.55)", position: "relative" }}>
            <div style={{ position: "absolute", left: 145, top: 40, width: 10, height: 110, background: OR, transformOrigin: "50% 100%",
              transform: `rotate(${interpolate(f, [S(L[4] + 0.1 - base), S(L[4] + 2.4 - base)], [0, 720], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) })}deg)` }} />
            <div style={{ position: "absolute", left: 145, top: 80, width: 10, height: 70, background: WH, transformOrigin: "50% 100%",
              transform: `rotate(${interpolate(f, [S(L[4] + 0.1 - base), S(L[4] + 2.4 - base)], [0, 60], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}deg)` }} />
          </div>
          <div style={{ marginTop: 30, fontFamily: "Pret", fontWeight: 800, fontSize: 110, color: WH }}>한 편 = <span style={{ color: OR }}>하루</span></div>
        </div>
      )}
    </AbsoluteFill>
  );
};

// 12.7~15.9 흑백 공장 → 컬러
const Reveal: React.FC = () => {
  const f = useCurrentFrame();
  const g = 1 - ez(f, S(1.5), S(2.4));
  return (
    <AbsoluteFill>
      <Factory gray={g} from={5} zoom={[1.18, 1.05]} dur={3.2} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 1240, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 84, color: WH,
        textShadow: "0 6px 30px #000", opacity: ez(f, S(3.41), S(3.7)) }}>전부 <span style={{ color: OR }}>클로드</span>가 만든 쇼츠</div>
    </AbsoluteFill>
  );
};

// 15.9~21.7 결과물: 부르는 순간 큰 폰, 지난 것은 아래 줄에 쌓임 → 쉼에 다섯 칸이 함께
const RES: [number, string, string][] = [
  [L[6] + 0.37, "op/c1.mp4", "연예인 화장품 후기"],
  [L[6] + 1.7, "op/c2.mp4", "해외 대박 영상"],
  [L[6] + 2.95, "op/c4.mp4", "감동 썰"],
  [L[6] + 3.8, "op/c5.mp4", "레시피"],
  [L[6] + 4.46, "op/c7.mp4", "여행 숙소"],
];
const Results: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const t = f / FPS + base;
  let cur = 0;
  RES.forEach((x, k) => { if (t >= x[0]) cur = k; });
  const all = ez(f, S(L[6] + 5.2 - base), S(L[6] + 5.7 - base));
  const local = S(t - RES[cur][0]);
  return (
    <AbsoluteFill style={{ background: BG }}>
      {RES.map((x, k) => {
        const on = k === cur ? 1 - all : 0;
        // 다섯 칸 자리(쉼): 3+2
        const gx = [70, 390, 710, 230, 550][k], gy = [560, 560, 560, 1060, 1060][k];
        const bx = 270, by = 560, bw = 540, bh = 960;
        const px = interpolate(all, [0, 1], [bx, gx]), py = interpolate(all, [0, 1], [by, gy]);
        const w = interpolate(all, [0, 1], [bw, 300]), h = interpolate(all, [0, 1], [bh, 533]);
        const show = k === cur || all > 0;
        return show ? (
          <div key={k} style={{ position: "absolute", left: px, top: py, width: w, height: h, borderRadius: 26, overflow: "hidden", border: `5px solid ${k === cur && all < 0.5 ? OR : "#2a2a30"}`,
            boxShadow: "0 20px 60px rgba(0,0,0,.7)", opacity: k === cur ? 1 : all, transform: k === cur && all === 0 ? `scale(${0.92 + 0.08 * ez(local, 0, 7)})` : undefined }}>
            <OffthreadVideo src={staticFile(x[1])} startFrom={S(0.5)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </div>
        ) : null;
      })}
      <div style={{ position: "absolute", left: 0, right: 0, top: 470, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 68, color: OR,
        opacity: 1 - all, transform: `translateY(${(1 - ez(local, 0, 7)) * 20}px)` }}>{RES[cur][2]}</div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 470, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 68, color: WH, opacity: all }}>
        전부 <span style={{ color: OR }}>한 줄</span>로 나온 쇼츠
      </div>
    </AbsoluteFill>
  );
};

// 21.7~25.5 원본 찾기부터 올리기까지 — 단계가 저절로 체크, 내 손은 0번
const STEPS = ["원본 찾기", "대본 쓰기", "목소리", "자막 · 편집", "렌더", "올리기"];
const Auto: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 140, top: 470 }}>
        {STEPS.map((s, k) => {
          const a = ez(f, 4 + k * 9, 10 + k * 9);
          return (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 30, height: 118, fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: INK }}>
              <div style={{ width: 78, height: 78, borderRadius: 39, border: `6px solid ${a > 0.5 ? "#2f8f5b" : "#c9c2b4"}`, background: a > 0.5 ? "#2f8f5b" : "transparent",
                color: WH, fontSize: 50, display: "flex", alignItems: "center", justifyContent: "center", transform: `scale(${0.85 + 0.15 * a})` }}>{a > 0.5 ? "✓" : ""}</div>
              <div style={{ opacity: 0.35 + 0.65 * a }}>{s}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 1195, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 72, color: INK, opacity: ez(f, S(2.2), S(2.5)) }}>
        제가 손댄 것 <span style={{ color: OR, fontSize: 110 }}>0</span>
      </div>
    </AbsoluteFill>
  );
};

// 25.5~29.9 검은 화면 커서 → 한 줄 타이핑 → 노란 밑줄
const OneLine: React.FC = () => {
  const f = useCurrentFrame();
  const cmd = "해외 화장품 만들어 줘";
  const t0 = S(L[9] + 0.18 - L[8]);
  const n = Math.max(0, Math.min(cmd.length, Math.floor((f - t0) / 2.6)));
  const ul = ez(f, S(L[10] + 0.38 - L[8]), S(L[10] + 0.38 - L[8]) + 12);
  return (
    <AbsoluteFill style={{ background: "#000", justifyContent: "center", alignItems: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: "#8d8d95", marginBottom: 50, opacity: ez(f, 2, 10) * (1 - ez(f, t0 - 6, t0)) }}>제가 한 건, 딱 하나</div>
      <div style={{ position: "relative", padding: "30px 40px", border: "3px solid #3a3a40", borderRadius: 18, width: 940, fontFamily: "Consolas, monospace", fontSize: 66, color: "#f0f0f2" }}>
        <span style={{ color: OR }}>&gt; </span><span style={{ fontFamily: "Pret", fontWeight: 800 }}>{cmd.slice(0, n)}</span>
        <span style={{ opacity: Math.floor(f / 14) % 2 ? 1 : 0 }}>▌</span>
        <div style={{ position: "absolute", left: 92, bottom: 18, height: 14, width: 700, background: YEL, transform: `scaleX(${ul})`, transformOrigin: "left", borderRadius: 7, opacity: 0.9 }} />
      </div>
      <div style={{ marginTop: 60, fontFamily: "Pret", fontWeight: 800, fontSize: 96, color: WH, opacity: ul }}>이 <span style={{ color: YEL }}>한 줄</span></div>
    </AbsoluteFill>
  );
};

// 29.9~끝 컬러 공장, 첫 컷과 같은 앵글(루프) + 끝 글자
const Loop: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Factory gray={0} from={0} zoom={[1.0, 1.06]} dur={END - L[11]} />
      <AbsoluteFill style={{ background: `rgba(0,0,0,${0.45 * ez(f, S(3.4), S(3.9))})` }} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 780, textAlign: "center", fontFamily: "Pret", fontWeight: 800, color: WH, textShadow: "0 6px 30px #000",
        opacity: ez(f, S(3.4), S(3.8)), transform: `translateY(${(1 - ez(f, S(3.4), S(3.8))) * 30}px)` }}>
        <div style={{ fontSize: 96 }}><span style={{ color: YEL }}>한 줄</span>로 돌리는</div>
        <div style={{ fontSize: 96 }}>유튜브 공장</div>
        <div style={{ fontSize: 52, color: OR, marginTop: 40 }}>숏클</div>
      </div>
    </AbsoluteFill>
  );
};

const Main: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    <Font />
    <Sequence from={0} durationInFrames={S(L[1])}><Factory gray={1} from={0} zoom={[1.0, 1.08]} dur={L[1]} /></Sequence>
    <Sequence from={S(L[1])} durationInFrames={S(L[2] - L[1])}><Fifty /></Sequence>
    <Sequence from={S(L[2])} durationInFrames={S(L[3] - L[2])}><Lecture /></Sequence>
    <Sequence from={S(L[3])} durationInFrames={S(L[5] - L[3])}><Pile base={L[3]} /></Sequence>
    <Sequence from={S(L[5])} durationInFrames={S(L[6] - L[5])}><Reveal /></Sequence>
    <Sequence from={S(L[6])} durationInFrames={S(L[7] - L[6])}><Results base={L[6]} /></Sequence>
    <Sequence from={S(L[7])} durationInFrames={S(L[8] - L[7])}><Auto /></Sequence>
    <Sequence from={S(L[8])} durationInFrames={S(L[11] - L[8])}><OneLine /></Sequence>
    <Sequence from={S(L[11])} durationInFrames={S(END - L[11])}><Loop /></Sequence>
    <Sequence from={0} durationInFrames={S(L[11])}><Title /></Sequence>
    {LN.map((x, i) => (
      <Sequence key={i} from={S(L[i])} durationInFrames={S(x[0])}>
        <Audio src={staticFile(`sh/A/a${String(i + 1).padStart(2, "0")}.mp3`)} />
      </Sequence>
    ))}
    <Caption />
  </AbsoluteFill>
);
registerRoot(() => <Composition id="ShortA" component={Main} durationInFrames={S(END)} fps={FPS} width={W} height={H} />);
