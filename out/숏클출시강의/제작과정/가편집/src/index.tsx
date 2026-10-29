import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, OffthreadVideo, Sequence, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";
import TTS from "../public/tts.json";

// 숏클 데일리 1편 가편집(오프닝~5단계). 임시 음성 edge-tts → 승인 뒤 필재로 교체.
// 장면 길이 = 그 줄 음성 길이. 영상 샘플은 길이에 맞춰 재생 속도만 바꾼다(자르거나 반복하지 않음).
const FPS = 30, S = (s: number) => Math.round(s * FPS);
const BG = "#EFE9DF", INK = "#1C1B19", OR = "#E07A2B", SUB = "#6B6660";
const OUT = Easing.out(Easing.cubic);
const ez = (f: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(f, [a, b], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: OUT });
type Line = { id: string; text: string; sec: number };
const L = Object.fromEntries((TTS as Line[]).map(x => [x.id, x]));

// 장면표: 음성 줄 → 화면(영상 파일과 원래 길이, 또는 카드)
const PLAN: { tts?: string; own?: number; video?: string; srcSec?: number; from?: number; card?: string[]; title?: string }[] = [
  { own: 18, video: "K2", srcSec: 18 },  // 결과물 소리 스포트라이트(원래 소리 그대로, 나레이션 없음)
  { tts: "hook1", video: "K", srcSec: 7.5, from: 0 },
  { tts: "hook2", video: "K", srcSec: 4.5, from: 7.5 },
  { tts: "p1", video: "A", srcSec: 10 },
  { tts: "p2", video: "B", srcSec: 6 },
  { tts: "s2", card: ["직접 편집", "반자동 프로그램", "클로드에게 부탁"], title: "다들 이렇게 합니다" },
  { tts: "s3", video: "E", srcSec: 10 },
  { tts: "s4", title: "필요한 건 더 좋은 질문이 아니라,\n끝까지 일하는 엔진" },
  { tts: "s5", video: "D", srcSec: 14 },
];

const Fonts = () => (
  <style>{`
  @font-face{font-family:'Pret';font-weight:700;src:url('${staticFile("fonts/Pretendard-Bold.otf")}')}
  @font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}
  @font-face{font-family:'Serif';src:url('${staticFile("fonts/GowunBatang.ttf")}')}
  `}</style>
);

// 자막: 문장 단위로 나누고 글자 수 비율로 시간 배분
const Caption: React.FC<{ text: string; dur: number }> = ({ text, dur }) => {
  const f = useCurrentFrame();
  const parts = text.split(/(?<=[.?!])\s+/);
  const total = parts.reduce((a, p) => a + p.length, 0);
  let acc = 0, cur = parts[0];
  for (const p of parts) { const st = (acc / total) * dur; if (f >= st) cur = p; acc += p.length; }
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 56, display: "flex", justifyContent: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 50, color: "#fff", background: "rgba(0,0,0,.72)", padding: "14px 32px", borderRadius: 14, maxWidth: 1600, textAlign: "center", wordBreak: "keep-all", lineHeight: 1.35 }}>{cur}</div>
    </div>
  );
};

const Cards: React.FC<{ title?: string; card?: string[] }> = ({ title, card }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: BG, justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      {title && <div style={{ fontFamily: "Serif", fontSize: card ? 96 : 104, color: INK, whiteSpace: "pre-line", lineHeight: 1.3, opacity: ez(f, 0, 14), marginBottom: card ? 70 : 120 }}>{title}</div>}
      {card && (
        <div style={{ display: "flex", gap: 40, marginBottom: 120 }}>
          {card.map((c, i) => {
            const a = 18 + i * 20;
            return <div key={c} style={{ width: 460, height: 260, borderRadius: 28, background: "#F8F4ED", boxShadow: "0 24px 60px rgba(60,40,20,.15)", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", gap: 14, opacity: ez(f, a, a + 14), transform: `translateY(${ez(f, a, a + 18, 24, 0)}px)` }}>
              <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 30, color: OR }}>0{i + 1}</div>
              <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 58, color: INK }}>{c}</div>
            </div>;
          })}
        </div>
      )}
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  let t = 0;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <Fonts />
      {PLAN.map((p, i) => {
        const sec = p.own ?? L[p.tts!].sec + 0.35; const dur = S(sec); const from = t; t += dur;
        const rate = p.srcSec ? p.srcSec / sec : 1;
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            {p.video
              ? <OffthreadVideo src={staticFile(`v/${p.video}.mp4`)} startFrom={S(p.from ?? 0)} playbackRate={rate} muted={!p.own} volume={p.own ? 0.63 : 1} style={{ width: 1920, height: 1080 }} />
              : <Cards title={p.title} card={p.card} />}
            {p.tts && <Audio src={staticFile(`tts/${p.tts}.mp3`)} />}
            {p.tts && <Caption text={L[p.tts].text} dur={dur} />}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
const TOTAL = PLAN.reduce((a, p) => a + S(p.own ?? L[p.tts!].sec + 0.35), 0);
registerRoot(() => <Composition id="RoughCut" component={Main} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080} />);
