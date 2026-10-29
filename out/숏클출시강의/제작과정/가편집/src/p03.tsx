import React from "react";
import { AbsoluteFill, Audio, Composition, Freeze, OffthreadVideo, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from "remotion";
import PLAN from "../public/plan.json";
import { Caption, Cap, Fonts, Hand, INK, Ink, OR, PAPER, S, Slam, ez } from "./kit";

// 숏클 1편 조각03 '문제 인식 ①~⑤'(대본 s02~s06 이어 붙임). 문장 = 화면, 같은 그림 두 번 안 씀.
// 할 일 목록은 필재가 그 단어를 말하는 순간 한 줄씩 체크된다(발음 실측 초).
const PAD = 0.4;
const SC = [2, 3, 4, 5, 6].map((i) => (PLAN as any)[i]);
const OFF: number[] = []; let acc = 0;
SC.forEach((s) => { OFF.push(acc); acc += s.sec + PAD; });
const END = acc;
const CAPS: Cap[] = SC.flatMap((s, k) => (s.caps as Cap[]).map((c) => [c[0] + OFF[k], c[1] + OFF[k], c[2]] as Cap));
const sq = (a: number, b: number, el: React.ReactNode) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{el}</Sequence>;

// ① 할 일 7개 — 말하는 순간 체크
const TODO: [number, string][] = [[5.74, "소재 찾기"], [6.57, "원본 찾기"], [7.49, "자르기"], [8.04, "대본 쓰기"], [8.98, "목소리"], [9.93, "자막"], [11.21, "썸네일"]];
const Todo: React.FC<{ base: number }> = ({ base }) => {
  const f = useCurrentFrame();
  const now = f / 30 + base;
  const spin = interpolate(now, [5.6, 12.9], [0, 360 * 6]);
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 140, top: 60 }}>
        {TODO.map(([at, label], k) => {
          const a = ez(f, S(at - base), S(at - base) + 6);
          const pop = interpolate(f, [S(at - base), S(at - base) + 4, S(at - base) + 8], [1.4, 0.95, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={k} style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 26, height: 112, opacity: a, transform: `scale(${pop})`, transformOrigin: "0 50%" }}>
              <div style={{ width: 70, height: 70, border: `6px solid ${INK}`, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 60, color: OR }}>✓</div>
              <div style={{ fontFamily: "Pen", fontSize: 108, color: INK }}>{label}</div>
            </div>
          );
        })}
      </div>
      {/* 오른쪽 벽시계: 체크될 때마다 빨라진다 */}
      <svg width={560} height={560} style={{ position: "absolute", left: 1220, top: 90 }} viewBox="-110 -110 220 220">
        <circle r={100} fill="#fff" stroke={INK} strokeWidth={7} />
        {Array.from({ length: 12 }).map((_, k) => <line key={k} x1={0} y1={-86} x2={0} y2={-76} stroke={INK} strokeWidth={5} transform={`rotate(${k * 30})`} />)}
        <line x1={0} y1={0} x2={0} y2={-56} stroke={INK} strokeWidth={8} strokeLinecap="round" transform={`rotate(${spin / 12})`} />
        <line x1={0} y1={0} x2={0} y2={-80} stroke={OR} strokeWidth={5} strokeLinecap="round" transform={`rotate(${spin})`} />
        <circle r={7} fill={INK} />
      </svg>
      {now >= 11.64 && <div style={{ position: "absolute", left: 1190, top: 690, padding: "10px 26px", border: `7px solid ${OR}`, borderRadius: 14, color: OR, fontFamily: "Pen", fontSize: 84,
        transform: `rotate(-7deg) scale(${interpolate(now, [11.64, 11.8, 11.95], [2.2, 0.95, 1], { extrapolateRight: "clamp" })})` }}>하나 끝내면 또 하나</div>}
    </AbsoluteFill>
  );
};

// 캡컷: '하나 더…'가 계속 쌓인다
const More: React.FC = () => {
  const f = useCurrentFrame();
  const items = ["효과음 하나 더", "자막 색 바꾸고", "컷 하나 더", "음악 다시", "글씨 키우고"];
  return (
    <Ink n="m_laptop_tired" side="left" draw={false}>
      {items.map((t, k) => {
        const a = ez(f, k * 12, k * 12 + 8);
        return <div key={k} style={{ position: "absolute", left: 1080 + (k % 2) * 90, top: 110 + k * 130, padding: "12px 26px", background: "#fff", border: `4px solid ${INK}`, borderRadius: 40,
          fontFamily: "Pen", fontSize: 76, color: INK, opacity: a, transform: `translateY(${(1 - a) * 30}px) rotate(${(k % 2 ? 3 : -3)}deg)` }}>{t}</div>;
      })}
    </Ink>
  );
};

// 원본 찾기: 플랫폼 이름이 차례로 튀어나옴
const Hop: React.FC = () => {
  const f = useCurrentFrame();
  const names: [string, string][] = [["틱톡", "#111"], ["인스타", "#C13584"], ["구글 렌즈", "#1A73E8"]];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {names.map(([n, c], k) => {
        const at = k * 20;
        return f >= at && <div key={k} style={{ position: "absolute", left: 180 + k * 520, top: 260 + (k % 2) * 120, padding: "26px 44px", background: c, color: "#fff", borderRadius: 30,
          fontFamily: "Pret", fontWeight: 800, fontSize: 92, transform: `scale(${interpolate(f, [at, at + 5, at + 10], [1.8, 0.94, 1], { extrapolateRight: "clamp" })}) rotate(${k % 2 ? 4 : -4}deg)` }}>{n}</div>;
      })}
      {[0, 1].map((k) => f >= 10 + k * 20 && <div key={k} style={{ position: "absolute", left: 590 + k * 520, top: 330, fontFamily: "Pret", fontWeight: 800, fontSize: 90, color: "#bbb" }}>→</div>)}
      <Hand text="원본 하나에 하루" x={520} y={620} size={150} color={OR} delay={50} />
    </AbsoluteFill>
  );
};

// 남의 자막이 덮인 재편집본 — 우리 완성본을 '남의 것'으로 보이면 사실과 달라서 그림으로 그린다
// (손그림 폰 + 위·아래에 다른 채널이 박아 넣은 자막 띠 두 줄 + 빨간 동그라미)
const Covered: React.FC = () => {
  const f = useCurrentFrame();
  const bar = (top: number, txt: string, at: number) => {
    const a = ez(f, at, at + 8);
    return <div style={{ position: "absolute", left: 20, right: 20, top, padding: "14px 10px", background: "#FFE14D", borderRadius: 8, textAlign: "center",
      fontFamily: "Pret", fontWeight: 800, fontSize: 40, color: "#111", opacity: a, transform: `scaleX(${0.6 + 0.4 * a})` }}>{txt}</div>;
  };
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 300, top: 50, width: 450, height: 800, borderRadius: 40, border: `7px solid ${INK}`, background: "#e9e4da", overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 60, top: 300, width: 330, height: 260, borderRadius: 20, background: "#cfd8e3" }} />
        <div style={{ position: "absolute", left: 175, top: 380, width: 0, height: 0, borderLeft: "70px solid #fff", borderTop: "45px solid transparent", borderBottom: "45px solid transparent" }} />
        {bar(80, "남의 채널 제목 자막", 2)}
        {bar(620, "남의 채널 자막", 6)}
      </div>
      <svg width={560} height={820} style={{ position: "absolute", left: 250, top: 40 }}>
        <ellipse cx={280} cy={95} rx={250} ry={80} fill="none" stroke="#E5484D" strokeWidth={10} strokeDasharray={1200} strokeDashoffset={1200 * (1 - ez(f, 10, 24))} />
        <ellipse cx={280} cy={635} rx={250} ry={70} fill="none" stroke="#E5484D" strokeWidth={10} strokeDasharray={1200} strokeDashoffset={1200 * (1 - ez(f, 16, 30))} />
      </svg>
      <Hand text={"찾았는데\n남의 자막이"} x={900} y={240} size={170} delay={10} />
    </AbsoluteFill>
  );
};

// ── 진화판(사장님 10-30 "앞에서 부족했던 것 그대로 반영하지 말고 진화해서"): 옛 손그림 영상(P2~P5) 대신 문장 단위 새 컷

// 질문 말풍선(DM): 글자가 타이핑되며 들어온다
const Dm: React.FC<{ text: string }> = ({ text }) => {
  const f = useCurrentFrame();
  const n = Math.max(0, Math.min(text.length, Math.floor((f - 8) / 1.6)));
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 120, top: 120, fontFamily: "Pen", fontSize: 96, color: "#9a958d", opacity: ez(f, 0, 8) }}>제일 많이 받는 질문</div>
      <div style={{ position: "absolute", left: 160, top: 300, maxWidth: 1500, padding: "40px 56px", background: "#fff", border: `6px solid ${INK}`, borderRadius: "60px 60px 60px 10px",
        fontFamily: "Pret", fontWeight: 800, fontSize: 96, color: INK, lineHeight: 1.2, wordBreak: "keep-all", transform: `scale(${0.9 + 0.1 * ez(f, 4, 12)})`, transformOrigin: "0 100%" }}>
        {text.slice(0, n)}<span style={{ opacity: Math.floor(f / 12) % 2 ? 1 : 0, color: OR }}>|</span>
      </div>
    </AbsoluteFill>
  );
};

// 조회수 999에서 멈춘 계기판 + 새로고침이 계속 돈다
const Stuck: React.FC = () => {
  const f = useCurrentFrame();
  const nums = [987, 993, 996, 998, 999];
  const v = nums[Math.min(nums.length - 1, Math.floor(f / 8))];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 120, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 64, color: "#9a958d" }}>조회수</div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 200, textAlign: "center", fontFamily: "Pret", fontWeight: 800, fontSize: 340, color: v === 999 ? "#E5484D" : INK, letterSpacing: -10 }}>{v}</div>
      <svg width={180} height={180} viewBox="-50 -50 100 100" style={{ position: "absolute", left: 1500, top: 300, transform: `rotate(${f * 14}deg)` }}>
        <path d="M 30 -10 A 32 32 0 1 0 32 8" fill="none" stroke={OR} strokeWidth={9} strokeLinecap="round" />
        <path d="M 22 -24 L 34 -10 L 16 -6" fill="none" stroke={OR} strokeWidth={9} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <Hand text="새로고침, 또 새로고침" x={540} y={660} size={110} delay={14} />
    </AbsoluteFill>
  );
};

// 달력이 넘어간다: 한 달 → 두 달 → 수익 0원
const Months: React.FC<{ t2: number; t3: number }> = ({ t2, t3 }) => {
  const f = useCurrentFrame();
  const page = (label: string, at: number, k: number) => {
    const a = ez(f, at, at + 8);
    const flip = interpolate(f, [at, at + 8], [-70, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return <div key={k} style={{ position: "absolute", left: 220 + k * 60, top: 120 + k * 30, width: 560, height: 620, background: "#fff", border: `6px solid ${INK}`, borderRadius: 18,
      opacity: a, transform: `perspective(1200px) rotateX(${flip}deg)`, transformOrigin: "50% 0", boxShadow: "0 12px 30px rgba(0,0,0,.15)" }}>
      <div style={{ height: 120, background: OR, borderRadius: "12px 12px 0 0" }} />
      <div style={{ textAlign: "center", fontFamily: "Pen", fontSize: 150, color: INK, marginTop: 120 }}>{label}</div>
    </div>;
  };
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {page("한 달", 0, 0)}
      {page("두 달", S(t2), 1)}
      {f >= S(t3) && <div style={{ position: "absolute", left: 1000, top: 300, fontFamily: "Pret", fontWeight: 800, color: INK }}>
        <div style={{ fontSize: 70, color: "#9a958d" }}>수익</div>
        <div style={{ fontSize: 260, color: "#E5484D", transform: `scale(${interpolate(f, [S(t3), S(t3) + 5, S(t3) + 10], [2, 0.94, 1], { extrapolateRight: "clamp" })})`, transformOrigin: "0 50%" }}>0원</div>
      </div>}
    </AbsoluteFill>
  );
};

// 강의 카드가 쌓였다가 → '남은 건 캡컷 실력' 하나로 쪼그라든다
const Courses: React.FC<{ tLeft: number }> = ({ tLeft }) => {
  const f = useCurrentFrame();
  const shrink = ez(f, S(tLeft), S(tLeft) + 14);
  const cards = ["쇼츠 수익화 강의", "AI 자동화 강의", "편집 마스터 강의", "부업 로드맵 강의"];
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {cards.map((c, k) => {
        const a = ez(f, k * 6, k * 6 + 10);
        return <div key={k} style={{ position: "absolute", left: 160 + k * 40 + shrink * (500 - k * 40), top: 120 + k * 120 + shrink * (300 - k * 120), width: 900 * (1 - shrink * 0.7), padding: "26px 40px",
          background: "#fff", border: `5px solid ${INK}`, borderRadius: 18, fontFamily: "Pret", fontWeight: 800, fontSize: 70 * (1 - shrink * 0.6), color: INK, opacity: a * (1 - shrink * 0.85),
          transform: `rotate(${(k % 2 ? 2 : -2)}deg)` }}>{c} ✓</div>;
      })}
      {f >= S(tLeft) && <div style={{ position: "absolute", left: 1040, top: 330, fontFamily: "Pret", fontWeight: 800 }}>
        <div style={{ fontSize: 70, color: "#9a958d", opacity: ez(f, S(tLeft), S(tLeft) + 8) }}>남은 건</div>
        <div style={{ fontSize: 160, color: OR, transform: `scale(${interpolate(f, [S(tLeft) + 8, S(tLeft) + 13, S(tLeft) + 18], [2, 0.94, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })})`, transformOrigin: "0 50%" }}>캡컷 실력</div>
      </div>}
    </AbsoluteFill>
  );
};

// 원본 하나에 하루: 해가 지고 달이 뜬다
const Day: React.FC<{ tDay: number }> = ({ tDay }) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [0, S(tDay) + 20], [0, 1], { extrapolateRight: "clamp" });
  const sky = `rgb(${Math.round(250 - 205 * p)},${Math.round(232 - 190 * p)},${Math.round(200 - 120 * p)})`;
  return (
    <AbsoluteFill style={{ background: sky }}>
      <div style={{ position: "absolute", left: 200 + 1300 * p, top: 140 + 300 * Math.sin(p * Math.PI) * -1 + 300 * p, width: 150, height: 150, borderRadius: 75, background: p < 0.6 ? "#FFC94D" : "#F3EBD3",
        boxShadow: p < 0.6 ? "0 0 80px #FFC94D" : "0 0 40px #fff" }} />
      <Hand text="원본 하나 찾는 데" x={180} y={420} size={140} color={p > 0.5 ? "#fff" : INK} underline={false} />
      {f >= S(tDay) && <Slam text="하루" at={S(tDay)} x={980} y={360} size={260} color={OR} center={false} />}
    </AbsoluteFill>
  );
};

const Main: React.FC = () => {
  const o = OFF;
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      <Fonts />
      {/* ─ s02 몇 시간 */}
      {sq(o[0], o[0] + 2.55, <Ink n="m_phone_show" side="right"><Hand text={"다들\n쉽다고 하잖아요"} x={150} y={200} size={160} /></Ink>)}
      {sq(o[0] + 2.55, o[0] + 5.74, <Ink n="m_laptop_blank" side="left"><Hand text="막상 앉으면…" x={1060} y={300} size={170} /></Ink>)}
      {sq(o[0] + 5.74, o[0] + 12.96, <Todo base={5.74} />)}
      {sq(o[0] + 12.96, o[0] + 15.27, <AbsoluteFill style={{ background: PAPER }}><Slam text="5~6시간" at={S(0.72)} y={260} size={300} color={OR} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 640, textAlign: "center", fontFamily: "Pen", fontSize: 90, color: INK }}>쇼츠 한 편에</div></AbsoluteFill>)}
      {sq(o[0] + 15.27, o[0] + 18.8, <Ink n="f_tired" side="right">
        <Slam text="빠른 분 2~3시간" at={S(0.77)} x={130} y={240} size={110} center={false} />
        <Slam text="끝내 못 만드는 분도" at={S(2.67)} x={130} y={420} size={100} color={OR} center={false} /></Ink>)}
      {sq(o[0] + 18.8, o[0] + 21.98, <Ink n="f_laptop_hope" side="left"><Hand text={"손이 가면\n욕심이 생긴다"} x={1040} y={240} size={160} /></Ink>)}
      {sq(o[0] + 21.98, o[0] + 25.0, <More />)}
      {sq(o[0] + 25.0, o[1], <AbsoluteFill style={{ background: PAPER }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 200, textAlign: "center", fontFamily: "Pen", fontSize: 110, color: "#9a958d" }}>쉽다고 했는데</div>
        <Slam text="결국 몇 시간" at={S(1.29)} y={380} size={240} color={INK} /></AbsoluteFill>)}
      {/* ─ s03 천 회 벽 (문장마다) */}
      {sq(o[1], o[1] + 2.89, <Ink n="m_phone_cu" side="right"><Hand text={"힘들게 올렸는데\n어떻던가요?"} x={130} y={230} size={150} /></Ink>)}
      {sq(o[1] + 2.89, o[1] + 8.44, <Dm text={"열심히 올렸는데,\n천 회를 벗어나지 못합니다"} />)}
      {sq(o[1] + 8.44, o[1] + 11.25, <Stuck />)}
      {sq(o[1] + 11.25, o[2], <Ink n="m_frustr_head" side="center" draw={false}><Hand text={"길었던 밤\n그 절망"} x={1300} y={240} size={170} color={OR} /></Ink>)}
      {/* ─ s04 수익 없는 시간 */}
      {sq(o[2], o[2] + 3.42, <Months t2={1.85 - 0} t3={2.45} />)}
      {sq(o[2] + 3.42, o[2] + 6.56, <Ink n="f_frustr_head" side="right"><Hand text={"언제까지\n수익 없이?"} x={150} y={230} size={170} /></Ink>)}
      {sq(o[2] + 6.56, o[3], <Ink n="m_tired" side="left"><Hand text={"그만두지도\n못하는 시간"} x={1060} y={260} size={160} color={OR} /></Ink>)}
      {/* ─ s05 강의 */}
      {sq(o[3], o[3] + 7.21, <Courses tLeft={4.21} />)}
      {sq(o[3] + 7.21, o[3] + 8.84, <AbsoluteFill style={{ background: PAPER }}><Slam text="강의 탓이 아니에요" at={S(0.19)} y={360} size={150} /></AbsoluteFill>)}
      {sq(o[3] + 8.84, o[4], <Ink n="f_hope" side="right"><Hand text={"실행할 시간이\n없었던 것"} x={140} y={240} size={160} color={OR} /></Ink>)}
      {/* ─ s06 원본 찾기 */}
      {sq(o[4], o[4] + 1.64, <Ink n="m_point_hope" side="left"><Hand text="이상한 게 하나" x={1080} y={300} size={160} /></Ink>)}
      {sq(o[4] + 1.64, o[4] + 5.96, <Day tDay={4.87 - 1.64} />)}
      {sq(o[4] + 5.96, o[4] + 8.55, <Hop />)}
      {sq(o[4] + 8.55, o[4] + 10.78, <Covered />)}
      {sq(o[4] + 10.78, o[4] + 12.85, <Ink n="m_phone_meh" side="left"><Hand text={"여기서 막힌 분\n진짜 많다"} x={1050} y={260} size={150} /></Ink>)}
      {sq(o[4] + 12.85, END, <Ink n="f_point_hope" side="right"><Hand text={"다들\n어떻게 풀고 있을까?"} x={130} y={220} size={150} color={OR} /></Ink>)}
      {[2, 3, 4, 5, 6].map((i, k) => <Sequence key={i} from={S(o[k])}><Audio src={staticFile(`full/s0${i}.mp3`)} /></Sequence>)}
      <Caption caps={CAPS} />
    </AbsoluteFill>
  );
};
registerRoot(() => <Composition id="P03" component={Main} durationInFrames={S(END)} fps={30} width={1920} height={1080} />);
