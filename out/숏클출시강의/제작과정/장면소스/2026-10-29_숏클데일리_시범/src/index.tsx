import React from "react";
import {
  AbsoluteFill, Composition, Easing, Sequence, OffthreadVideo, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";

// 숏클 데일리 틀 시범(60초). 레퍼런스 = "What is Claude Code"(1,373만 회) 칼카피:
// 따뜻한 베이지 바탕 · 큰 명조 제목(단어별 페이드인) · 베이지 위에 뜬 어두운 앱 창 · 모션은 페이드/살짝 떠오름 2가지뿐.
// 매일 바뀌는 것 = DAY(그날의 한 줄·각도·숫자). 틀(장면 5종)은 고정.
const DAY = {
  prompt: "해외 화장품 쇼츠 만들어줘",
  topic: "오늘은 원본 찾기를 해 봤습니다",
  why: "원본은 왜 찾나요?",
  point1: "남의 자막이 덮인 영상은\n그대로 못 씁니다",
  point2: "처음 찍은 원본을\n찾아야 합니다",
  bigNum: 7, bigUnit: "분", bigPre: "약", bigCap: "소재 하나당 · 원본 찾기부터 검증까지 (15편 중앙값)",
  resultNum: 19164, resultCap: "구독자 9명 새 채널 · 일주일 조회수",
};
const CHECKS = ["원본 찾기 · 해외 4곳 동시 검색", "같은 영상인지 AI 판정", "대본 · 터진 채널의 틀 그대로", "장면 · 목소리 · 자막", "검사 통과 · 완성본 전송"];

const BG = "#EFE9DF", INK = "#1C1B19", SUB = "#6B6660", OR = "#E07A2B", TEAL = "#12957F", WIN = "#1F1E1C", WIN2 = "#2A2926";
const FPS = 30, S = (s: number) => Math.round(s * FPS);
const OUT = Easing.out(Easing.cubic);
const ez = (f: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(f, [a, b], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: OUT });

const Fonts = () => (
  <style>{`
  @font-face{font-family:'Pret';font-weight:400;src:url('${staticFile("fonts/Pretendard-Regular.otf")}')}
  @font-face{font-family:'Pret';font-weight:600;src:url('${staticFile("fonts/Pretendard-SemiBold.otf")}')}
  @font-face{font-family:'Pret';font-weight:700;src:url('${staticFile("fonts/Pretendard-Bold.otf")}')}
  @font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}
  @font-face{font-family:'Serif';src:url('${staticFile("fonts/GowunBatang.ttf")}')}
  `}</style>
);
const sans: React.CSSProperties = { fontFamily: "Pret", wordBreak: "keep-all", letterSpacing: "-0.02em" };
const serif: React.CSSProperties = { fontFamily: "Serif", wordBreak: "keep-all", letterSpacing: "-0.03em", color: INK };

// 장면 감싸기: 들어올 때·나갈 때 페이드(0.33초)
const Scene: React.FC<{ dur: number; children: React.ReactNode }> = ({ dur, children }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ opacity: Math.min(ez(f, 0, 10), 1 - ez(f, dur - 10, dur)) }}>{children}</AbsoluteFill>;
};
// 단어별 페이드인(Claude Code 제목 카드와 같은 동작)
const Words: React.FC<{ text: string; start: number; gap?: number; style?: React.CSSProperties }> = ({ text, start, gap = 5, style }) => {
  const f = useCurrentFrame();
  let k = 0;
  return (
    <div style={style}>
      {text.split("\n").map((line, li) => (
        <div key={li}>
          {line.split(" ").map((w, wi) => {
            const a = start + (k++) * gap;
            return <span key={wi} style={{ opacity: ez(f, a, a + 14), display: "inline-block", transform: `translateY(${ez(f, a, a + 16, 14, 0)}px)`, marginRight: "0.28em" }}>{w}</span>;
          })}
        </div>
      ))}
    </div>
  );
};
const Phone: React.FC<{ x: number; y?: number; scale?: number; blur?: number; start?: number }> = ({ x, y = 540, scale = 1, blur = 0, start = 0 }) => {
  const f = useCurrentFrame();
  const W = 470, H = 836;
  return (
    <div style={{ position: "absolute", left: x - (W + 24) / 2, top: y - (H + 24) / 2 + ez(f, 0, 22, 30, 0), width: W + 24, height: H + 24,
      transform: `scale(${scale})`, borderRadius: 64, background: "#141311", padding: 12, boxShadow: "0 40px 90px rgba(60,40,20,.28)" }}>
      <div style={{ width: W, height: H, borderRadius: 52, overflow: "hidden", background: "#000" }}>
        <OffthreadVideo src={staticFile("source_kopack.mp4")} startFrom={start} volume={0}
          style={{ width: W, height: H, objectFit: "cover", filter: blur ? `blur(${blur}px)` : undefined }} />
      </div>
    </div>
  );
};

// ① 결과 먼저
const S1: React.FC<{ d: number }> = ({ d }) => (
  <Scene dur={d}>
    <Phone x={640} />
    <div style={{ position: "absolute", left: 1010, top: 330, width: 820 }}>
      <Words text="이 쇼츠," start={14} style={{ ...serif, fontSize: 104, lineHeight: 1.25 }} />
      <Words text="말 한 줄로 나왔습니다" start={26} gap={6} style={{ ...serif, fontSize: 104, lineHeight: 1.25 }} />
      <Under start={60} />
    </div>
  </Scene>
);
const Under: React.FC<{ start: number }> = ({ start }) => {
  const f = useCurrentFrame();
  return <div style={{ marginTop: 28, height: 8, width: 360 * ez(f, start, start + 24), background: OR, borderRadius: 4 }} />;
};

// ② 질문/주제 카드
const Card: React.FC<{ d: number; text: string }> = ({ d, text }) => (
  <Scene dur={d}>
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      <Words text={text} start={8} gap={6} style={{ ...serif, fontSize: 116, lineHeight: 1.3 }} />
    </AbsoluteFill>
  </Scene>
);

// ③ 한 줄 입력 → 진행(진행판을 찍지 않고 큰 글씨로 다시 그림)
const S3: React.FC<{ d: number }> = ({ d }) => {
  const f = useCurrentFrame();
  const n = Math.round(interpolate(f, [S(0.8), S(2.8)], [0, DAY.prompt.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const sent = f >= S(3.2);
  const caret = !sent && Math.floor(f / 15) % 2 === 0;
  const checkAt = (i: number) => S(4.4) + i * S(1.9);
  const allDone = f >= checkAt(CHECKS.length - 1) + S(0.6);
  const sc = ez(f, 0, 24, 0.97, 1);
  return (
    <Scene dur={d}>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ ...sans, width: 1520, height: 860, borderRadius: 28, background: WIN, transform: `scale(${sc})`, boxShadow: "0 50px 120px rgba(60,40,20,.30)", overflow: "hidden" }}>
          <div style={{ height: 64, background: WIN2, display: "flex", alignItems: "center", gap: 14, padding: "0 28px" }}>
            {["#E8584A", "#E0A83A", "#4F5266"].map(c => <div key={c} style={{ width: 18, height: 18, borderRadius: 9, background: c }} />)}
            <div style={{ marginLeft: 18, fontSize: 26, color: "#8A857C" }}>숏클메이커</div>
          </div>
          <div style={{ padding: "56px 80px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 26, fontSize: 64, fontWeight: 700, color: "#F3ECE0" }}>
              <span style={{ color: OR }}>›</span>
              <span>{DAY.prompt.slice(0, n)}</span>
              <span style={{ width: 6, height: 64, background: OR, opacity: caret ? 1 : 0 }} />
            </div>
            <div style={{ marginTop: 34, height: 2, background: "#3A3834", opacity: ez(f, S(3.2), S(3.6)) }} />
            <div style={{ marginTop: 30, fontFamily: "Serif", fontSize: 46, color: allDone ? "#5FD3BC" : "#B8B1A6", opacity: ez(f, S(3.4), S(3.9)) }}>
              {allDone ? "✓ 완성본이 나왔습니다" : "✳ 만드는 중…"}
            </div>
            <div style={{ marginTop: 26 }}>
              {CHECKS.map((c, i) => {
                const a = checkAt(i), done = f >= a + S(0.7);
                return (
                  <div key={c} style={{ display: "flex", alignItems: "center", gap: 26, height: 82, fontSize: 52, fontWeight: 600,
                    color: done ? "#F3ECE0" : "#8A857C", opacity: ez(f, a, a + 12), transform: `translateY(${ez(f, a, a + 14, 12, 0)}px)` }}>
                    <div style={{ width: 46, height: 46, borderRadius: 23, border: `4px solid ${done ? "#5FD3BC" : "#5A5650"}`, background: done ? "#5FD3BC" : "transparent",
                      display: "flex", alignItems: "center", justifyContent: "center", color: WIN, fontSize: 30, fontWeight: 800 }}>{done ? "✓" : ""}</div>
                    {c}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

// ④ 핵심 하나: 남의 자막 띠가 벗겨지는 그림 + 설명 문장
const S5: React.FC<{ d: number }> = ({ d }) => {
  const f = useCurrentFrame();
  const peel = ez(f, S(4.2), S(5.4));
  // 완성본에는 자막이 박혀 있어 '원본'처럼 보이면 거짓이 된다 → 벗겨진 뒤엔 강하게 흐려 설명 그림으로만 쓴다
  const label = peel > 0.5 ? "원본 = 자막 없는 처음 영상" : "재편집본";
  const bar = (top: number, h: number, c: string, txt: string, delay: number) => (
    <div style={{ ...sans, position: "absolute", left: 412 - 235 + 20, top, width: 430, height: h, borderRadius: 10, background: c,
      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36, fontWeight: 800, color: INK,
      opacity: 1 - ez(f, S(4.2) + delay, S(5.0) + delay), transform: `translateX(${ez(f, S(4.2) + delay, S(5.2) + delay, 0, 560)}px)` }}>{txt}</div>
  );
  return (
    <Scene dur={d}>
      <Phone x={412} blur={10 + 22 * peel} start={S(3)} />
      {bar(250, 96, "#F6D34A", "남의 제목 자막", 0)}
      {bar(640, 76, "#F2F0EA", "남의 자막", 4)}
      <div style={{ ...sans, position: "absolute", left: 412 - 300, top: 978, width: 600, textAlign: "center", fontSize: 40, fontWeight: 700, color: peel > 0.5 ? TEAL : SUB }}>{label}</div>
      <div style={{ position: "absolute", left: 860, top: 300, width: 980 }}>
        <Words text={DAY.point1} start={10} gap={5} style={{ ...serif, fontSize: 84, lineHeight: 1.32 }} />
        <div style={{ height: 70 }} />
        <Words text={DAY.point2} start={S(5.6)} gap={6} style={{ ...serif, fontSize: 84, lineHeight: 1.32, color: OR }} />
      </div>
    </Scene>
  );
};

// ⑤ 숫자 하나(카운트업)
const Num: React.FC<{ d: number; to: number; pre?: string; unit?: string; cap: string; color?: string }> = ({ d, to, pre = "", unit = "", cap, color = INK }) => {
  const f = useCurrentFrame();
  const v = Math.round(interpolate(f, [S(0.4), S(2.2)], [0, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: OUT }));
  return (
    <Scene dur={d}>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center" }}>
        <div style={{ ...serif, fontSize: 250, lineHeight: 1, color, opacity: ez(f, 0, 12) }}>
          {pre && <span style={{ fontSize: 120, marginRight: 24 }}>{pre}</span>}{v.toLocaleString("ko-KR")}<span style={{ fontSize: 150, marginLeft: 12 }}>{unit}</span>
        </div>
        <div style={{ ...sans, marginTop: 56, fontSize: 52, fontWeight: 600, color: SUB, opacity: ez(f, S(1.2), S(1.8)) }}>{cap}</div>
      </AbsoluteFill>
    </Scene>
  );
};

// 마무리
const End: React.FC<{ d: number }> = ({ d }) => {
  const f = useCurrentFrame();
  return (
    <Scene dur={d}>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center" }}>
        <Words text="말 한 줄이면 됩니다" start={8} gap={6} style={{ ...serif, fontSize: 120 }} />
        <div style={{ ...sans, marginTop: 70, fontSize: 84, fontWeight: 800, color: INK, opacity: ez(f, S(1.4), S(2.0)) }}>
          숏클메이커
          <div style={{ margin: "16px auto 0", height: 8, width: 420 * ez(f, S(1.8), S(2.6)), background: OR, borderRadius: 4 }} />
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

const PLAN: [number, React.FC<{ d: number }>][] = [
  [6, S1],
  [4.5, ({ d }) => <Card d={d} text={DAY.topic} />],
  [15, S3],
  [4, ({ d }) => <Card d={d} text={DAY.why} />],
  [11, S5],
  [6.5, ({ d }) => <Num d={d} to={DAY.bigNum} pre={DAY.bigPre} unit={DAY.bigUnit} cap={DAY.bigCap} />],
  [6.5, ({ d }) => <Num d={d} to={DAY.resultNum} unit="회" cap={DAY.resultCap} color={OR} />],
  [6.5, End],
];
const TOTAL = PLAN.reduce((a, [s]) => a + S(s), 0);

const Main: React.FC = () => {
  let t = 0;
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Fonts />
      {PLAN.map(([sec, C], i) => {
        const from = t, d = S(sec); t += d;
        return <Sequence key={i} from={from} durationInFrames={d}><C d={d} /></Sequence>;
      })}
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="ShortclDaily" component={Main} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080} />);
