import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, OffthreadVideo, Sequence, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";
import PLAN from "../public/plan.json";

// 숏클 1편 오프닝 조각(38.9초). 대사 문장마다 화면이 바뀌고 같은 그림은 두 번 안 나온다.
// 시각 = 필재 음성 실제 발음 시각(plan.json caps). 유형별 결과물 = 실제 완성본(public/op/c1~c7).
const FPS = 30, S = (s: number) => Math.round(s * FPS);
const BG = "#0E0E10", OR = "#F6A93B", W = "#FFFFFF";
const ez = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
type Cap = [number, number, string];
const CAPS = (PLAN as any)[0].caps as Cap[];
const END = (PLAN as any)[0].sec + 0.4;

// 유형 7개: [시작초, 클립, 이름표] — 시작초 = 그 유형을 말하는 순간
const TYPES: [number, string, string][] = [
  [8.25, "op/c1.mp4", "연예인 화장품 후기"],
  [10.56, "op/c2.mp4", "해외 대박 영상"],
  [12.42, "op/c3.mp4", "썰 쇼핑"],
  [13.92, "op/c4.mp4", "감동 영상"],
  [15.99, "op/c5.mp4", "연예인 레시피"],
  [17.88, "op/c6.mp4", "해외 화장품"],
  [19.68, "op/c7.mp4", "여행 숙소"],
];

const Font = () => (
  <style>{`@font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}`}</style>
);

const Caption: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const c = CAPS.find((x, k) => t >= x[0] && t < (CAPS[k + 1] ? CAPS[k + 1][0] : x[1] + 0.6));
  if (!c) return null;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 50, display: "flex", justifyContent: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 46, color: W, background: "rgba(0,0,0,.72)", padding: "12px 30px", borderRadius: 14, maxWidth: 1640, textAlign: "center", wordBreak: "keep-all" }}>{c[2]}</div>
    </div>
  );
};

// 0~4.25 흑백 공장 + 글자
const Factory: React.FC<{ gray: boolean; from: number; zoom: [number, number] }> = ({ gray, from, zoom }) => {
  const f = useCurrentFrame();
  const z = interpolate(f, [0, S(4.3)], zoom, { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      <OffthreadVideo src={staticFile("op/factory.mp4")} startFrom={S(from)} muted
        style={{ width: 1920, height: 1080, objectFit: "cover", transform: `scale(${z})`, filter: gray ? "grayscale(1) contrast(1.12) brightness(.9)" : "none" }} />
    </AbsoluteFill>
  );
};

// 4.25~8.25 쇼츠 벽: 9편이 세 줄로 흘러간다
const Wall: React.FC = () => {
  const f = useCurrentFrame();
  const rows = [0, 1, 2];
  return (
    <AbsoluteFill style={{ background: BG, overflow: "hidden" }}>
      {rows.map((r) => {
        const dir = r % 2 ? 1 : -1;
        const x = dir * interpolate(f, [0, S(4)], [0, 260]);
        return (
          <div key={r} style={{ position: "absolute", top: 40 + r * 340, left: -200 + x, display: "flex", flexDirection: "row", gap: 24, opacity: ez(f, r * 4, r * 4 + 10) }}>
            {Array.from({ length: 9 }).map((_, k) => (
              <div key={k} style={{ width: 180, height: 320, borderRadius: 16, overflow: "hidden", boxShadow: "0 8px 30px rgba(0,0,0,.6)" }}>
                <OffthreadVideo src={staticFile(`op/v${((k + r * 3) % 9) + 1}.mp4`)} muted style={{ width: 180, height: 320, objectFit: "cover" }} />
              </div>
            ))}
          </div>
        );
      })}
      <div style={{ position: "absolute", left: 0, right: 0, top: 360, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 110, color: W, textShadow: "0 6px 30px #000", opacity: ez(f, 6, 18) }}>
        클로드 <span style={{ color: OR }}>한 줄</span>이면
      </div>
    </AbsoluteFill>
  );
};

// 8.25~21.18 유형 하나씩: 가운데 큰 폰 + 왼쪽 이름표 + 오른쪽에 지난 유형이 쌓임
const Types: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / FPS + TYPES[0][0];
  let cur = 0;
  TYPES.forEach((x, k) => { if (t >= x[0]) cur = k; });
  const local = S(t - TYPES[cur][0]);
  return (
    <AbsoluteFill style={{ background: BG }}>
      {TYPES.map((x, k) => (
        <Sequence key={k} from={S(x[0] - TYPES[0][0])} durationInFrames={S((TYPES[k + 1] ? TYPES[k + 1][0] : 21.18) - x[0])}>
          <div style={{ position: "absolute", left: 730, top: 46, width: 460, height: 818, borderRadius: 38, overflow: "hidden", border: "6px solid #222", boxShadow: "0 20px 60px rgba(0,0,0,.7)" }}>
            <OffthreadVideo src={staticFile(x[1])} muted style={{ width: 460, height: 818, objectFit: "cover" }} />
          </div>
        </Sequence>
      ))}
      <div style={{ position: "absolute", left: 110, top: 300, width: 600 }}>
        <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: OR, opacity: ez(local, 0, 8) }}>{String(cur + 1).padStart(2, "0")} / 07</div>
        <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 96, color: W, lineHeight: 1.15, marginTop: 10, wordBreak: "keep-all",
          transform: `translateX(${(1 - ez(local, 0, 9)) * -40}px)`, opacity: ez(local, 0, 9) }}>{TYPES[cur][2]}</div>
      </div>
      <div style={{ position: "absolute", right: 70, top: 70, display: "flex", flexDirection: "column", gap: 14 }}>
        {TYPES.slice(0, cur).map((x, k) => (
          <div key={k} style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 14, opacity: 0.85 }}>
            <div style={{ width: 54, height: 96, borderRadius: 8, overflow: "hidden" }}>
              <OffthreadVideo src={staticFile(x[1])} muted style={{ width: 54, height: 96, objectFit: "cover" }} />
            </div>
            <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 34, color: "#cfcfd4" }}>{x[2]}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// 21.18~26.26 일곱 개가 한 줄로 모여 "이거 내가 하고 싶었던 건데"
const Row: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: BG }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 70, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 80, color: W, opacity: ez(f, 4, 16) }}>
        "어, 이거 <span style={{ color: OR }}>내가 하고 싶었던</span> 건데"
      </div>
      <div style={{ position: "absolute", left: 70, top: 230, display: "flex", flexDirection: "row", gap: 22 }}>
        {TYPES.map((x, k) => {
          const a = ez(f, k * 3, k * 3 + 12);
          const pulse = 1 + 0.06 * Math.max(0, Math.sin((f - S(1.5) - k * 9) / 6)) * (f > S(1.5) ? 1 : 0);
          return (
            <div key={k} style={{ width: 230, height: 409, borderRadius: 20, overflow: "hidden", opacity: a, transform: `translateY(${(1 - a) * 60}px) scale(${pulse})`, boxShadow: "0 10px 30px rgba(0,0,0,.6)" }}>
              <OffthreadVideo src={staticFile(x[1])} startFrom={S(4)} muted style={{ width: 230, height: 409, objectFit: "cover" }} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// 26.26~29.5 컬러 공장 + "전부 한 줄로"
const OneLine: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Factory gray={false} from={6} zoom={[1.15, 1.0]} />
      <div style={{ position: "absolute", left: 110, top: 110, fontFamily: "Pret", fontWeight: 800, fontSize: 100, color: W, textShadow: "0 6px 30px #000", lineHeight: 1.15 }}>
        <div style={{ opacity: ez(f, 0, 10) }}>전부 <span style={{ color: OR }}>한 줄</span>로</div>
        <div style={{ fontSize: 64, opacity: ez(f, S(1.2), S(1.2) + 10) }}>원본 찾기부터 올리기까지</div>
      </div>
    </AbsoluteFill>
  );
};

// 29.5~34.68 "클로드 딸깍 영상… 열에 아홉은 AI가 그린 영상"
const Fake: React.FC = () => {
  const f = useCurrentFrame();
  const strike = ez(f, S(3.1), S(3.6));
  return (
    <AbsoluteFill style={{ background: "#111" }}>
      <AbsoluteFill style={{ display: "flex", flexDirection: "row", flexWrap: "wrap", gap: 18, padding: 60, opacity: 0.28, filter: "grayscale(1)" }}>
        {Array.from({ length: 9 }).map((_, k) => (
          <div key={k} style={{ width: 180, height: 320, borderRadius: 14, overflow: "hidden" }}>
            <OffthreadVideo src={staticFile(`op/v${k + 1}.mp4`)} startFrom={S(6)} muted style={{ width: 180, height: 320, objectFit: "cover" }} />
          </div>
        ))}
      </AbsoluteFill>
      <div style={{ position: "absolute", left: 0, right: 0, top: 250, textAlign: "center", fontFamily: "Pret", fontWeight: 800 }}>
        <div style={{ fontSize: 84, color: W, opacity: ez(f, 0, 10) }}>"클로드로 딸깍, 수백 편"</div>
        <div style={{ position: "relative", display: "inline-block", fontSize: 110, color: OR, marginTop: 40, opacity: ez(f, S(3.0), S(3.0) + 8) }}>
          열에 아홉은 AI 그림
          <div style={{ position: "absolute", left: -10, right: -10, top: "52%", height: 12, background: "#E5484D", transform: `scaleX(${strike})`, transformOrigin: "left" }} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

// 34.68~끝 "오늘은 다릅니다 / 진짜 클로드의 딸깍" + 입력줄 한 글자씩
const Real: React.FC = () => {
  const f = useCurrentFrame();
  const cmd = "해외+화장품 프리셋으로 한 편 만들어 줘";
  const n = Math.max(0, Math.min(cmd.length, Math.floor((f - S(1.4)) / 2)));
  return (
    <AbsoluteFill style={{ background: BG, justifyContent: "center", alignItems: "center" }}>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 70, color: "#9b9ba3", opacity: ez(f, 0, 8) }}>오늘은 다릅니다</div>
      <div style={{ fontFamily: "Pret", fontWeight: 800, fontSize: 130, color: W, marginTop: 10, opacity: ez(f, S(0.9), S(0.9) + 10) }}>
        진짜 클로드의 <span style={{ color: OR }}>딸깍</span>
      </div>
      <div style={{ marginTop: 60, width: 1200, border: "2px solid #3a3a40", borderRadius: 12, padding: "22px 28px", fontFamily: "Consolas, monospace", fontSize: 44, color: "#e8e8ea", opacity: ez(f, S(1.2), S(1.2) + 8) }}>
        <span style={{ color: OR }}>&gt; </span>{cmd.slice(0, n)}<span style={{ opacity: Math.floor(f / 15) % 2 ? 1 : 0 }}>▌</span>
      </div>
    </AbsoluteFill>
  );
};

const Main: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    <Font />
    <Sequence from={0} durationInFrames={S(4.25)}>
      <Factory gray from={0} zoom={[1.0, 1.08]} />
      <div style={{ position: "absolute", left: 110, top: 640, fontFamily: "Pret", fontWeight: 800 }}>
        <div style={{ fontSize: 46, color: OR }}>지금 이 순간에도 돌아가는</div>
        <div style={{ fontSize: 118, color: W, textShadow: "0 6px 30px #000" }}>이게 쇼츠 공장입니다</div>
      </div>
    </Sequence>
    <Sequence from={S(4.25)} durationInFrames={S(8.25 - 4.25)}><Wall /></Sequence>
    <Sequence from={S(8.25)} durationInFrames={S(21.18 - 8.25)}><Types /></Sequence>
    <Sequence from={S(21.18)} durationInFrames={S(26.26 - 21.18)}><Row /></Sequence>
    <Sequence from={S(26.26)} durationInFrames={S(29.5 - 26.26)}><OneLine /></Sequence>
    <Sequence from={S(29.5)} durationInFrames={S(34.68 - 29.5)}><Fake /></Sequence>
    <Sequence from={S(34.68)} durationInFrames={S(END - 34.68)}><Real /></Sequence>
    <Audio src={staticFile("full/s00.mp3")} />
    <Caption />
  </AbsoluteFill>
);
registerRoot(() => <Composition id="Opening" component={Main} durationInFrames={S(END)} fps={FPS} width={1920} height={1080} />);
