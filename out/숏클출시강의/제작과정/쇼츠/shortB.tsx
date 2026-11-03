import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, Img, OffthreadVideo, Sequence, interpolate,
  registerRoot, staticFile, useCurrentFrame,
} from "remotion";

// 숏클 쇼츠 B "이 영상 690만 회. 근데 원본은 따로 있었습니다"(세로 1080x1920) — 대본 쇼츠4편_대본_페이블_v2.md B.
// 음성 = 줄마다 따로 뽑은 필재 sh/B/bNN.mp3 를 통째로 이어 놓는다(LN). 숫자는 롱폼 조각07(라이브 실측)과 같다: 690만 → 380만 · 후보 117 · 한국 12개 · 400초.
// 소재: op/c6.mp4 = 넣은 재편집본, p7/orig.mp4 = 받은 해외 원본, p7/t1~16 = 실제 후보 영상.
const FPS = 30, S = (s: number) => Math.round(s * FPS);
const W = 1080, H = 1920;
const BG = "#0E0E10", OR = "#F6A93B", WH = "#FFFFFF", RED = "#E5484D", GR = "#6EE7B7", PAPER = "#FBF8F1", INK = "#1C1B19";
const ez = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
const pop = (f: number, at: number) => interpolate(f, [at, at + 5, at + 9], [0.6, 1.08, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

// [파일 길이, 뒤에 더 쉴 초, 자막 조각들 [파일 안 시각(실제 쉼 측정), 글]]
const LN: [number, number, [number, string][]][] = [
  [2.24, 0, [[0.37, "이 영상, 육백구십만 회예요."]]],
  [1.56, 0.3, [[0.08, "근데 이거,"], [0.76, "원본이 아니었습니다."]]],
  [2.8, 0, [[0.31, "터진 영상 보면"], [1.37, "\"나도 저거 하고 싶다\" 하시잖아요."]]],
  [2.76, 0.2, [[0.21, "그래서 따라 만들면,"], [1.74, "천 회에서 멈춰요."]]],
  [3.04, 0, [[0.17, "재편집본 말고,"], [1.37, "처음 찍은 원본을 찾아야 됩니다."]]],
  [2.8, 0.3, [[0.31, "근데 원본 하나 찾는 데"], [2.08, "하루가 가죠."]]],
  [2.76, 0, [[0.34, "자, 보시면."], [1.28, "이 영상 주소 하나 넣었어요."]]],
  [3.04, 0, [[0.17, "틱톡, 인스타, 유튜브, 구글 렌즈를"], [2.0, "한 방에 뒤집니다."]]],
  [2.76, 0.2, [[0.17, "후보 백 개를,"], [1.25, "AI가 눈으로 보고 골라내요."]]],
  [1.28, 0.6, [[0.28, "칠 분 뒤."]]],
  [3.52, 0.2, [[0.15, "처음 올린 틱톡 원본이 나왔습니다."], [1.95, "삼백팔십만 회짜리."]]],
  [2.52, 0, [[0.29, "한국에 올라온 채널은"], [1.6, "열두 개뿐이에요."]]],
  [2.52, 0, [[0.32, "원본을 찾은 사람이,"], [1.62, "다음에 터집니다."]]],
];
const L: number[] = []; LN.reduce((t, x) => { L.push(t); return t + x[0] + x[1]; }, 0);
const END = L[12] + LN[12][0] + 2.8;
const CAPS: [number, number, string][] = LN.flatMap(([d, , cs], i) => cs.map(([t, txt], k) =>
  [L[i] + t, L[i] + (cs[k + 1] ? cs[k + 1][0] : d - 0.1), txt] as [number, number, string]));

const Font = () => (
  <style>{`@font-face{font-family:'Pret';font-weight:800;src:url('${staticFile("fonts/Pretendard-ExtraBold.otf")}')}`}</style>
);
const T: React.CSSProperties = { fontFamily: "Pret", fontWeight: 800 };

const Title: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <div style={{ ...T, position: "absolute", left: 60, right: 60, top: 190, textAlign: "center", lineHeight: 1.18, color: WH,
      background: "rgba(14,14,16,.85)", borderRadius: 28, padding: "18px 0 22px", opacity: ez(f, 0, 6) }}>
      <div style={{ fontSize: 78 }}>이 영상 <span style={{ color: OR }}>690만 회</span>.</div>
      <div style={{ fontSize: 66 }}>근데 원본은 따로 있었습니다</div>
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

const Phone: React.FC<{ src: string; x: number; y: number; w: number; border?: string; from?: number; style?: React.CSSProperties }> = ({ src, x, y, w, border = "#2a2a30", from = 0, style }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, height: w * 16 / 9, borderRadius: w / 14, overflow: "hidden", border: `6px solid ${border}`, boxShadow: "0 20px 60px rgba(0,0,0,.7)", ...style }}>
    <OffthreadVideo src={staticFile(src)} startFrom={S(from)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  </div>
);
const Stamp: React.FC<{ text: string; color: string; at: number; x: number; y: number; rot?: number; size?: number }> = ({ text, color, at, x, y, rot = -12, size = 92 }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  return <div style={{ ...T, position: "absolute", left: x, top: y, padding: "10px 30px", border: `9px solid ${color}`, borderRadius: 18, color, fontSize: size,
    background: "rgba(0,0,0,.35)", transform: `rotate(${rot}deg) scale(${pop(f, at)})` }}>{text}</div>;
};

// b01~b02 재편집본 + 조회수 카운트 → 원본 아님
const Fake: React.FC = () => {
  const f = useCurrentFrame();
  const n = Math.round(6900000 * ez(f, 4, S(1.4)));
  const cut = S(L[1] + 0.76);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Phone src="op/c6.mp4" x={250} y={470} w={580} style={{ filter: f >= cut ? "grayscale(.7) brightness(.7)" : "none" }} />
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 1060, textAlign: "center" }}>
        <span style={{ fontSize: 120, color: WH, background: "rgba(0,0,0,.6)", padding: "4px 26px", borderRadius: 18 }}>▶ {n.toLocaleString()}</span>
      </div>
      {f >= cut && <div style={{ position: "absolute", left: 200, top: 1010, width: 680, height: 14, background: RED, transform: `rotate(-8deg) scaleX(${ez(f, cut, cut + 6)})`, transformOrigin: "left" }} />}
      <Stamp text="원본 아님" color={RED} at={cut + 4} x={300} y={760} />
    </AbsoluteFill>
  );
};

// b03 손그림: "나도 저거"
const Want: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Img src={staticFile("hero/c_m_phone_wow.png")} style={{ position: "absolute", left: 40, top: 640, width: 1000, opacity: ez(f, 0, 8) }} />
      <div style={{ ...T, position: "absolute", left: 120, right: 120, top: 520, padding: "26px 30px", borderRadius: 60, background: WH, border: `5px solid ${INK}`,
        textAlign: "center", fontSize: 62, color: INK, opacity: ez(f, S(1.3), S(1.6)), transform: `scale(${0.9 + 0.1 * ez(f, S(1.3), S(1.6))})` }}>"나도 저거 하고 싶다"</div>
    </AbsoluteFill>
  );
};

// b04 따라 만들면 천 회의 벽
const Wall: React.FC = () => {
  const f = useCurrentFrame();
  const v = Math.round(interpolate(f, [S(0.2), S(1.7)], [0, 987], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }));
  const hit = ez(f, S(1.7), S(1.9));
  return (
    <AbsoluteFill style={{ background: "#16171c" }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 560, height: 16, background: RED, opacity: 0.85 }} />
      <div style={{ ...T, position: "absolute", right: 90, top: 500, fontSize: 44, color: RED }}>조회수 1,000의 벽</div>
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 700, textAlign: "center", fontSize: 54, color: "#9a9aa3" }}>내가 따라 만든 영상</div>
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 790, textAlign: "center", fontSize: 230, color: WH, transform: `translateX(${Math.sin(f * 2) * 10 * hit * (1 - ez(f, S(2.0), S(2.4)))}px)` }}>{v}</div>
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 1060, textAlign: "center", fontSize: 64, color: RED, opacity: hit }}>여기서 멈춤</div>
    </AbsoluteFill>
  );
};

// b05 재편집본 더미 뒤 맨 끝 원본
const Layers: React.FC = () => {
  const f = useCurrentFrame();
  const r = ez(f, S(1.4), S(2.2));
  return (
    <AbsoluteFill style={{ background: BG }}>
      {[0, 1, 2, 3].map((k) => (
        <Phone key={k} src="op/c6.mp4" from={k} x={130 + k * 50 - r * 260} y={540 + k * 30} w={460}
          style={{ opacity: 0.85 - k * 0.12 - r * 0.5, filter: `blur(${k * 1.5 + r * 6}px)`, transform: `rotate(${(k - 1.5) * 4}deg)` }} />
      ))}
      <div style={{ ...T, position: "absolute", left: 90, top: 470, fontSize: 52, color: "#9a9aa3", opacity: 1 - r }}>재편집본 · 재편집본 · 재편집본…</div>
      <Phone src="p7/orig.mp4" x={interpolate(r, [0, 1], [640, 290])} y={520} w={interpolate(r, [0, 1], [300, 500])} border={GR} style={{ opacity: 0.4 + 0.6 * r }} />
      <Stamp text="원본" color={GR} at={S(2.0)} x={620} y={500} rot={8} size={80} />
    </AbsoluteFill>
  );
};

// b06 앱 오가기 + 시계
const Hunt: React.FC = () => {
  const f = useCurrentFrame();
  const apps: [string, string][] = [["틱톡", "#111"], ["인스타", "#C13584"], ["유튜브", "#E62117"], ["구글 렌즈", "#1A73E8"]];
  const cur = Math.floor(f / 9) % 4;
  return (
    <AbsoluteFill style={{ background: "#1a1b20" }}>
      {apps.map(([a, c], k) => (
        <div key={k} style={{ ...T, position: "absolute", left: [110, 570, 110, 570][k], top: [520, 520, 760, 760][k], width: 400, height: 190, borderRadius: 28, background: c,
          color: WH, fontSize: 64, display: "flex", alignItems: "center", justifyContent: "center", border: k === cur ? `8px solid ${OR}` : "8px solid transparent",
          transform: `scale(${k === cur ? 1.05 : 0.95})` }}>{a}</div>
      ))}
      <div style={{ position: "absolute", left: 390, top: 1010, width: 300, height: 300, borderRadius: 150, border: `10px solid ${WH}`, opacity: ez(f, S(1.8), S(2.1)) }}>
        <div style={{ position: "absolute", left: 140, top: 30, width: 10, height: 120, background: OR, transformOrigin: "50% 100%", transform: `rotate(${interpolate(f, [S(1.8), S(3.0)], [0, 720], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}deg)` }} />
      </div>
    </AbsoluteFill>
  );
};

// b07~b08 주소 하나 → 4곳 동시
const Engine: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const url = "youtube.com/shorts/••••••";
  const t0 = S(1.3);
  const n = Math.max(0, Math.min(url.length, Math.floor((f - t0) / 1.4)));
  const burst = S(L[7] - base + 0.17);
  const apps: [string, string, number][] = [["틱톡", "#111", 0], ["인스타", "#C13584", 0.67], ["유튜브", "#E62117", 1.1], ["구글 렌즈", "#1A73E8", 1.5]];
  return (
    <AbsoluteFill style={{ background: BG }}>
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 500, textAlign: "center", fontSize: 92, color: OR, opacity: ez(f, 0, 8) }}>원본 찾기 엔진</div>
      <div style={{ position: "absolute", left: 80, right: 80, top: 650, padding: "26px 30px", border: "4px solid #3a3a40", borderRadius: 18, background: "#1d1e23",
        fontFamily: "Consolas, monospace", fontSize: 46, color: "#e8e8ea", opacity: ez(f, 4, 10) }}>🔗 {url.slice(0, n)}<span style={{ opacity: Math.floor(f / 14) % 2 ? 1 : 0 }}>▌</span></div>
      {apps.map(([a, c, at], k) => {
        const s0 = burst + S(at);
        const a1 = ez(f, s0, s0 + 7);
        return (
          <div key={k} style={{ ...T, position: "absolute", left: [100, 560, 100, 560][k], top: [880, 880, 1090, 1090][k], width: 420, height: 170, borderRadius: 26, background: c, color: WH,
            fontSize: 60, display: "flex", alignItems: "center", justifyContent: "center", opacity: a1, transform: `scale(${pop(f, s0)}) rotate(${Math.sin((f - s0) / 2) * 2 * (1 - ez(f, s0 + 8, s0 + 20))}deg)` }}>{a} 🔍</div>
        );
      })}
    </AbsoluteFill>
  );
};

// b09 후보 117 → AI 판정, 하나만 ✓
const Cands: React.FC = () => {
  const f = useCurrentFrame();
  const n = Math.round(117 * ez(f, 0, S(1.0)));
  const judge = S(1.25);
  const WIN = 9;
  return (
    <AbsoluteFill style={{ background: BG }}>
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 470, textAlign: "center", fontSize: 64, color: WH }}>후보 <span style={{ color: OR, fontSize: 110 }}>{n}</span>개</div>
      <div style={{ position: "absolute", left: 60, top: 640, display: "flex", flexWrap: "wrap", gap: 10, width: 980 }}>
        {Array.from({ length: 20 }).map((_, k) => {
          const xAt = judge + 3 + ((k * 7) % 20) * 1.3;
          const isWin = k === WIN;
          return (
            <div key={k} style={{ position: "relative", width: 184, height: 210, borderRadius: 10, overflow: "hidden", opacity: ez(f, k * 0.8, k * 0.8 + 5),
              border: isWin && f > judge + 30 ? `6px solid ${GR}` : "6px solid transparent", transform: isWin && f > judge + 30 ? `scale(${pop(f, judge + 30)})` : undefined }}>
              <OffthreadVideo src={staticFile(isWin ? "p7/orig.mp4" : `p7/t${(k % 16) + 1}.mp4`)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              {!isWin && f > xAt && <AbsoluteFill style={{ background: "rgba(0,0,0,.55)", alignItems: "center", justifyContent: "center", ...T, fontSize: 90, color: RED }}>✗</AbsoluteFill>}
              {isWin && f > judge + 30 && <div style={{ ...T, position: "absolute", right: 8, top: 0, fontSize: 80, color: GR }}>✓</div>}
            </div>
          );
        })}
      </div>
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 1150, textAlign: "center", fontSize: 58, color: WH, opacity: ez(f, judge, judge + 8) }}>🤖 AI가 <span style={{ color: OR }}>눈으로</span> 판정</div>
    </AbsoluteFill>
  );
};

// b10 칠 분 뒤 — 타이머
const Timer: React.FC = () => {
  const f = useCurrentFrame();
  const sec = Math.round(400 * ez(f, 4, S(1.6)));
  return (
    <AbsoluteFill style={{ background: "#000", justifyContent: "center", alignItems: "center" }}>
      <div style={{ fontFamily: "Consolas, monospace", fontSize: 200, color: WH }}>{String(Math.floor(sec / 60)).padStart(2, "0")}:{String(sec % 60).padStart(2, "0")}</div>
      <div style={{ ...T, fontSize: 56, color: "#8d8d95", marginTop: 20 }}>실제 걸린 시간 · 약 400초</div>
    </AbsoluteFill>
  );
};

// b11~b12 원본 등장 + 380만 + 한국 12개
const Found: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const n380 = S(L[10] - base + 1.95);
  const k12 = S(L[11] - base + 0.3);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Phone src="p7/orig.mp4" x={250} y={470} w={580} border={GR} style={{ transform: `scale(${0.85 + 0.15 * ez(f, 0, 10)})` }} />
      <Stamp text="원본" color={GR} at={6} x={640} y={470} rot={10} size={86} />
      {f >= n380 && <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 1040, textAlign: "center", transform: `scale(${pop(f, n380)})` }}>
        <span style={{ fontSize: 110, color: OR, background: "rgba(0,0,0,.7)", padding: "4px 26px", borderRadius: 18 }}>▶ 380만 회</span></div>}
      {f >= k12 && <AbsoluteFill style={{ background: `rgba(14,14,16,${0.82 * ez(f, k12, k12 + 8)})` }}>
        <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 560, textAlign: "center", fontSize: 64, color: WH }}>한국에 올라온 채널</div>
        <div style={{ position: "absolute", left: 140, top: 700, width: 800, display: "flex", flexWrap: "wrap", gap: 28, justifyContent: "center" }}>
          {Array.from({ length: 12 }).map((_, k) => (
            <div key={k} style={{ width: 110, height: 110, borderRadius: 55, background: OR, opacity: ez(f, k12 + 4 + k * 2, k12 + 8 + k * 2), transform: `scale(${pop(f, k12 + 4 + k * 2)})` }} />
          ))}
        </div>
        <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 1110, textAlign: "center", fontSize: 120, color: OR, opacity: ez(f, S(1.6) + k12, S(1.6) + k12 + 8) }}>12개뿐</div>
      </AbsoluteFill>}
    </AbsoluteFill>
  );
};

// b13 + 끝: 690만(재편집) vs 380만(원본) → 끝 글자
const End: React.FC = () => {
  const f = useCurrentFrame();
  const fin = S(LN[12][0] + 0.1);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Phone src="op/c6.mp4" x={70} y={540} w={430} style={{ filter: "grayscale(.6) brightness(.75)" }} />
      <Phone src="p7/orig.mp4" x={580} y={540} w={430} border={GR} style={{ transform: `scale(${1 + 0.05 * ez(f, S(1.6), S(2.0))})` }} />
      <div style={{ ...T, position: "absolute", left: 70, width: 430, top: 1330, textAlign: "center", fontSize: 44, color: "#9a9aa3" }}>재편집본 690만</div>
      <div style={{ ...T, position: "absolute", left: 580, width: 430, top: 1330, textAlign: "center", fontSize: 44, color: GR }}>원본 380만</div>
      <div style={{ ...T, position: "absolute", left: 480, top: 840, fontSize: 110, color: OR, opacity: ez(f, S(1.6), S(1.9)) }}>→</div>
      <AbsoluteFill style={{ background: `rgba(0,0,0,${0.7 * ez(f, fin, fin + 10)})` }} />
      <div style={{ ...T, position: "absolute", left: 0, right: 0, top: 800, textAlign: "center", color: WH, opacity: ez(f, fin, fin + 10), transform: `translateY(${(1 - ez(f, fin, fin + 10)) * 30}px)` }}>
        <div style={{ fontSize: 92 }}><span style={{ color: GR }}>원본</span>만 찾으면,</div>
        <div style={{ fontSize: 92 }}>다음은 <span style={{ color: OR }}>내 차례</span></div>
        <div style={{ fontSize: 52, color: OR, marginTop: 40 }}>숏클</div>
      </div>
    </AbsoluteFill>
  );
};

const Main: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    <Font />
    <Sequence from={0} durationInFrames={S(L[2])}><Fake /></Sequence>
    <Sequence from={S(L[2])} durationInFrames={S(L[3] - L[2])}><Want /></Sequence>
    <Sequence from={S(L[3])} durationInFrames={S(L[4] - L[3])}><Wall /></Sequence>
    <Sequence from={S(L[4])} durationInFrames={S(L[5] - L[4])}><Layers /></Sequence>
    <Sequence from={S(L[5])} durationInFrames={S(L[6] - L[5])}><Hunt /></Sequence>
    <Sequence from={S(L[6])} durationInFrames={S(L[8] - L[6])}><Engine base={L[6]} /></Sequence>
    <Sequence from={S(L[8])} durationInFrames={S(L[9] - L[8])}><Cands /></Sequence>
    <Sequence from={S(L[9])} durationInFrames={S(L[10] - L[9])}><Timer /></Sequence>
    <Sequence from={S(L[10])} durationInFrames={S(L[12] - L[10])}><Found base={L[10]} /></Sequence>
    <Sequence from={S(L[12])} durationInFrames={S(END - L[12])}><End /></Sequence>
    <Sequence from={0} durationInFrames={S(L[12] + LN[12][0])}><Title /></Sequence>
    {LN.map((x, i) => (
      <Sequence key={i} from={S(L[i])} durationInFrames={S(x[0])}>
        <Audio src={staticFile(`sh/B/b${String(i + 1).padStart(2, "0")}.mp3`)} />
      </Sequence>
    ))}
    <Caption />
  </AbsoluteFill>
);
registerRoot(() => <Composition id="ShortB" component={Main} durationInFrames={S(END)} fps={FPS} width={W} height={H} />);
