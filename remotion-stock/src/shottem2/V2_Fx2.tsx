import React from 'react';
import {
  AbsoluteFill, OffthreadVideo, Loop, Img, Audio, Sequence, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, spring, random,
} from 'remotion';
import { C, F } from './theme2';
import { CAP } from './V2_Captions';
import { IconBadge, ICON_RULES } from './V2_Bg';

/* V2 광고 2차 부품 (2026-10-12 사장님 "영상이 심심해 / 회원 영상 페이지 / 카톡 후기 각색 / 30일 챌린지 극적으로")
   - ShortsWall    : 회원 완성 쇼츠가 폰 화면 여러 줄로 흘러가는 배경(서버 회원 완성본에서 8초씩 잘라 온 60개)
   - MemberGallery : "실제 회원님들이 만든 영상입니다" — 폰 그리드가 펼쳐지는 장면
   - KakaoChat     : 카톡 후기를 대화창으로 재현(글은 원문 그대로, 이름 가운데는 ○)
   - Challenge30   : 실전 한 달 — 날짜 칸이 하루씩 도장 찍히며 조회수가 쌓인다(실전30일 캡처 숫자 그대로)
   - WordCaption   : 필재 TTS 단어 시각에 맞춰 지금 말하는 단어가 튀는 자막 */

const FPS = 30;
const WALL = (i: number) => 'shottem2/v2wall/w' + String(((i % 60) + 60) % 60).padStart(2, '0') + '.mp4';
const STROKE: React.CSSProperties = { WebkitTextStroke: '3px rgba(0,0,0,0.9)', paintOrder: 'stroke fill', textShadow: '0 8px 30px rgba(0,0,0,1)' };

const Phone: React.FC<{ i: number; w: number; style?: React.CSSProperties; glow?: boolean }> = ({ i, w, style, glow }) => (
  <div style={{
    width: w, height: (w * 16) / 9, borderRadius: w * 0.08, overflow: 'hidden', flexShrink: 0,
    border: Math.max(3, w * 0.018) + 'px solid #0d0d0f',
    boxShadow: glow ? '0 0 40px rgba(250,204,21,0.55), 0 20px 50px rgba(0,0,0,0.8)' : '0 20px 50px rgba(0,0,0,0.8)', ...style,
  }}>
    <Loop durationInFrames={240}><OffthreadVideo src={staticFile(WALL(i))} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} /></Loop>
  </div>
);

/** 회원 쇼츠 벽 — 기울어진 3D 면 위로 기둥 다섯 줄이 엇갈려 흐른다 */
export const ShortsWall: React.FC<{ seed?: number; dim?: number; tint?: string }> = ({ seed = 0, dim = 0.45, tint }) => {
  const f = useCurrentFrame();
  const cols = 7;
  const w = 250;
  const gap = 24;
  return (
    <AbsoluteFill style={{ background: '#050507', overflow: 'hidden', perspective: 1600 }}>
      <div style={{
        position: 'absolute', left: '50%', top: '50%', width: cols * (w + gap), height: 2600,
        transform: 'translate(-50%,-50%) rotateX(22deg) rotateZ(-10deg) scale(1.15)',
        display: 'flex', gap,
      }}>
        {Array.from({ length: cols }, (_, c) => {
          const dir = c % 2 ? 1 : -1;
          const y = ((f * (1.4 + (c % 3) * 0.35) * dir) % 900) - 450;
          return (
            <div key={c} style={{ display: 'flex', flexDirection: 'column', gap, transform: 'translateY(' + y + 'px)' }}>
              {Array.from({ length: 6 }, (_, r) => <Phone key={r} i={seed * 7 + c * 6 + r} w={w} />)}
            </div>
          );
        })}
      </div>
      <AbsoluteFill style={{ background: 'rgba(0,0,0,' + dim + ')' }} />
      {tint === 'mono' ? <AbsoluteFill style={{ backdropFilter: 'grayscale(1)', WebkitBackdropFilter: 'grayscale(1)' }} /> : null}
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.85) 100%)' }} />
    </AbsoluteFill>
  );
};

/** 회원 작품 갤러리 — 제목이 박히고 폰 12개가 차례로 튀어 오른 뒤 카메라가 훑는다 */
export const MemberGallery: React.FC<{ title?: string; sub?: string; seed?: number }> = ({
  title = '실제 회원님들이 만든 영상입니다', sub = '숏템메이커 회원 완성 쇼츠', seed = 3,
}) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const pan = interpolate(f, [0, durationInFrames], [120, -220]);
  const zoom = interpolate(f, [0, durationInFrames], [1.0, 1.12]);
  const t = spring({ frame: f - 4, fps, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ background: 'radial-gradient(circle at 50% 40%, #2a2208, #050507 70%)', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 0, right: 0, top: 210, display: 'flex', flexDirection: 'column', gap: 26, alignItems: 'center', transform: 'translateX(' + pan + 'px) scale(' + zoom + ')' }}>
        {[0, 1].map((row) => (
          <div key={row} style={{ display: 'flex', gap: 26 }}>
            {Array.from({ length: 8 }, (_, k) => {
              const i = row * 8 + k;
              const p = spring({ frame: f - 10 - i * 2.2, fps, config: { damping: 11, mass: 0.6 } });
              return (
                <div key={k} style={{ transform: 'translateY(' + (1 - p) * 300 + 'px) scale(' + (0.6 + p * 0.4) + ')', opacity: p }}>
                  <Phone i={seed * 11 + i} w={230} glow={(i + Math.floor(f / 20)) % 5 === 0} />
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(0,0,0,0.85) 0%, transparent 22%, transparent 75%, rgba(0,0,0,0.85) 100%)' }} />
      <div style={{ position: 'absolute', top: 40, left: 0, right: 0, textAlign: 'center', transform: 'scale(' + (0.7 + t * 0.3) + ')', opacity: t }}>
        <div style={{ font: '800 34px ' + F.sans, color: C.gold, letterSpacing: 10 }}>{sub}</div>
        <div style={{ font: '900 92px ' + F.sans, color: C.paper, ...STROKE }}>{title}</div>
      </div>
    </AbsoluteFill>
  );
};

/** 카톡 후기 — 원문 그대로(이름 가운데 ○). hl = 형광펜 칠할 구절 */
export const REVIEWS: { who: string; text: string; hl: string; color: string }[] = [
  { who: '김○○ 50대 회원님', color: '#7dd3c0', hl: '치킨값 벌었네요', text: '60대 나이에 새로운 것에 도전한다는 게 두려웠는데, 숏템메이커 덕분에 용기를 냈습니다. 컴맹인 저도 쉽게 따라 할 수 있었고, 이번 달 처음으로 치킨값 벌었네요. 작은 수익이지만 제겐 너무나 큰 성취감입니다. 정말 감사합니다!' },
  { who: '김○○ 60대 회원님', color: '#93c5fd', hl: '손주들 용돈 쥐여줬을 때의 기쁨', text: '은퇴 후 무료한 일상을 보내다가 숏템메이커를 만나 삶의 활력을 찾았습니다. 나이 든 사람도 집에서 무언가를 해내고 돈을 벌 수 있다는 게 믿기지 않네요. 첫 달 수익으로 손주들 용돈 쥐여줬을 때의 기쁨, 정말 고맙습니다.' },
  { who: '김○○ 30대 회원님', color: '#a5b4fc', hl: '기저귀값, 분유값', text: '육아하면서 집에서 할 수 있는 부업을 찾다가 숏템메이커를 알게 되었습니다. 하루 1~2시간 투자로 기저귀값, 분유값 벌 수 있어서 정말 만족하며 쓰고 있어요. 초보자도 쉽게 접근할 수 있어서 너무 좋습니다.' },
  { who: '김○○ 50대 회원님', color: '#c4b5fd', hl: '매일 커피값, 밥값', text: '강의도 많이 전전하고 처음엔 반신반의하며 시작했는데 숏템메이커 쓰면서 확실히 달라졌어요. 아직 엄청나게 큰돈은 아니지만 매일 커피값, 밥값 정도는 꾸준히 벌리고 있어서 너무 신기하고 감사합니다.' },
  { who: '박○○ 40대 회원님', color: '#86efac', hl: '첫 수익이 났습니다!', text: '혼자 맨땅에 헤딩할 때는 너무 막막하고 포기하고 싶었는데, 숏템메이커 도입하고 나서 첫 수익이 났습니다! 비록 아직은 귀여운 수준의 수익이지만, 저도 할 수 있다는 자신감을 얻었어요.' },
  { who: '강○○ 40대 회원님', color: '#fda4af', hl: '수익이 늘어나고 있어서', text: '여러 가지 프로그램 써봤지만 숏템메이커만큼 안정적이고 직관적인 게 없네요. 소소하게 용돈벌이 느낌으로 시작했는데, 갈수록 요령이 생기고 수익이 늘어나고 있어서 기대가 큽니다.' },
];

const Bubble: React.FC<{ r: typeof REVIEWS[number]; at: number; big: boolean }> = ({ r, at, big }) => {
  const f = useCurrentFrame() - at;
  const { fps } = useVideoConfig();
  if (f < 0) return null;
  const typing = f < 14;
  const p = spring({ frame: f, fps, config: { damping: 13, mass: 0.6 } });
  const hlp = interpolate(f, [22, 40], [0, 100], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const [a, b] = r.text.split(r.hl);
  return (
    <div style={{ display: 'flex', gap: 18, alignItems: 'flex-start', opacity: p, transform: 'translateY(' + (1 - p) * 60 + 'px)', marginBottom: 26 }}>
      <div style={{ width: 78, height: 78, borderRadius: 28, background: r.color, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', font: '900 40px ' + F.sans, color: '#1f2937' }}>
        {r.who[0]}
      </div>
      <div>
        <div style={{ font: '600 28px ' + F.sans, color: '#cbd5e1', marginBottom: 8 }}>{r.who}</div>
        <div style={{
          maxWidth: 980, padding: '22px 28px', borderRadius: '6px 26px 26px 26px', background: '#2b2b30',
          font: '500 ' + (big ? 40 : 34) + 'px/1.5 ' + F.sans, color: '#f1f5f9',
        }}>
          {typing ? <span style={{ letterSpacing: 8 }}>{'●'.repeat(1 + (Math.floor(f / 4) % 3))}</span> : (
            <>{a}<span style={{ fontWeight: 900, borderRadius: 6, padding: '0 4px', backgroundImage: 'linear-gradient(' + C.gold + ',' + C.gold + ')', backgroundRepeat: 'no-repeat', backgroundSize: hlp + '% 100%', WebkitBoxDecorationBreak: 'clone', boxDecorationBreak: 'clone', color: hlp >= 100 ? '#111' : '#f1f5f9' }}>{r.hl}</span>{b}</>
          )}
        </div>
      </div>
    </div>
  );
};

/** 카톡방 — 메시지가 차례로 올라오고 화면이 위로 밀린다. 하트가 떠오른다 */
export const KakaoChat: React.FC<{ every?: number }> = ({ every = 62 }) => {
  const f = useCurrentFrame();
  const n = REVIEWS.length;
  const shown = Math.min(n, Math.floor(f / every) + 1);
  const scroll = interpolate(f, [every * 1.6, every * n], [0, -(n - 2) * 260], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill>
      <ShortsWall seed={5} dim={0.72} />
      <div style={{ position: 'absolute', left: 260, top: 40, width: 1400, height: 1000, borderRadius: 36, overflow: 'hidden', background: '#17171b', boxShadow: '0 40px 140px rgba(0,0,0,0.9), 0 0 0 2px rgba(250,204,21,0.4)' }}>
        <div style={{ height: 110, background: '#1f1f24', display: 'flex', alignItems: 'center', padding: '0 40px', gap: 20, borderBottom: '1px solid #333' }}>
          <div style={{ width: 64, height: 64, borderRadius: 22, background: C.gold, display: 'flex', alignItems: 'center', justifyContent: 'center', font: '900 30px ' + F.sans, color: '#111' }}>SM</div>
          <div style={{ font: '800 40px ' + F.sans, color: '#fff' }}>숏템메이커 1기 회원님들</div>
          <div style={{ marginLeft: 'auto', font: '700 30px ' + F.sans, color: C.gold }}>💬 실제 후기</div>
        </div>
        <div style={{ padding: '36px 46px', transform: 'translateY(' + scroll + 'px)' }}>
          {REVIEWS.slice(0, shown).map((r, i) => <Bubble key={i} r={r} at={i * every} big={false} />)}
        </div>
      </div>
      {REVIEWS.map((_, i) => (
        <Sequence key={i} from={i * every + 14} durationInFrames={10} layout="none">
          <Audio src={staticFile('sfx/kakao_ding.mp3')} volume={0.7} />
        </Sequence>
      ))}
      {Array.from({ length: 14 }, (_, i) => {
        const st = (i * 23) % (every * n);
        const g = f - st;
        if (g < 0 || g > 60) return null;
        return (
          <div key={i} style={{ position: 'absolute', right: 120 + random('hx' + i) * 140, bottom: 80 + g * 9, font: '60px sans-serif', opacity: interpolate(g, [0, 10, 60], [0, 1, 0]), transform: 'scale(' + (0.7 + random('hs' + i) * 0.8) + ')' }}>
            {['❤️', '👍', '🔥', '😭'][i % 4]}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/** 실전 한 달 — 실전30일 캡처의 날짜·조회수 그대로(8/28~9/20, 하루 1~3편) */
export const DAYS: [string, number[]][] = [
  ['8/28', [5325, 1354]], ['8/29', [2040, 5469]], ['8/30', [3271, 2596]], ['8/31', [1579, 1877]],
  ['9/1', [3667, 1240]], ['9/2', [2635, 4789]], ['9/3', [513, 1777]], ['9/4', [1772]], ['9/5', [1709, 1301]],
  ['9/6', [3424, 2354]], ['9/7', [24, 1051, 0]], ['9/8', [1815, 1289]], ['9/9', [1181]], ['9/10', [1340, 25, 1032]],
  ['9/11', [1250, 1123]], ['9/12', [1547, 1653]], ['9/13', [1281, 2261]], ['9/14', [1450]], ['9/15', [1375, 1070]],
  ['9/16', [1175, 2755]], ['9/17', [1086, 21]], ['9/18', [1694, 1347]], ['9/19', [1150, 1114]], ['9/20', [1210, 1096]],
];
export const Challenge30: React.FC<{ per?: number }> = ({ per = 9 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lit = Math.min(DAYS.length, Math.floor(f / per) + 1);
  let views = 0;
  let posts = 0;
  DAYS.slice(0, lit).forEach(([, v]) => { views += v.reduce((a, b) => a + b, 0); posts += v.length; });
  const head = spring({ frame: f, fps, config: { damping: 12 } });
  const done = f > per * DAYS.length + 6;
  const fin = spring({ frame: f - per * DAYS.length - 6, fps, config: { damping: 9 } });
  return (
    <AbsoluteFill>
      <ShortsWall seed={9} dim={0.78} />
      <div style={{ position: 'absolute', top: 36, left: 0, right: 0, textAlign: 'center', transform: 'scale(' + (0.7 + head * 0.3) + ')', opacity: head }}>
        <div style={{ font: '800 34px ' + F.sans, color: C.gold, letterSpacing: 10 }}>1기 회원님의 실전 기록</div>
        <div style={{ font: '900 88px ' + F.sans, color: C.paper, ...STROKE }}>하루도 안 빼고 올렸다</div>
      </div>
      <div style={{ position: 'absolute', left: 120, top: 250, display: 'grid', gridTemplateColumns: 'repeat(6, 170px)', gap: 16 }}>
        {DAYS.map(([d, v], i) => {
          const on = i < lit;
          const g = f - i * per;
          const st = spring({ frame: g, fps, config: { damping: 9, mass: 0.5 } });
          return (
            <div key={d} style={{
              height: 150, borderRadius: 18, position: 'relative', overflow: 'hidden',
              background: on ? 'linear-gradient(160deg, rgba(250,204,21,0.28), rgba(20,20,24,0.9))' : 'rgba(255,255,255,0.05)',
              border: '2px solid ' + (on ? C.gold : 'rgba(255,255,255,0.12)'),
              boxShadow: on && g < 12 ? '0 0 40px rgba(250,204,21,0.9)' : 'none',
            }}>
              <div style={{ position: 'absolute', left: 14, top: 10, font: '800 30px ' + F.sans, color: on ? C.paper : '#555' }}>{d}</div>
              {on ? (
                <>
                  <div style={{ position: 'absolute', right: 10, top: 6, font: '900 26px ' + F.sans, color: C.gold }}>{'▶'.repeat(v.length)}</div>
                  <div style={{ position: 'absolute', left: 0, right: 0, bottom: 14, textAlign: 'center', font: '900 34px ' + F.sans, color: '#fff', transform: 'scale(' + (1.8 - st * 0.8) + ')', opacity: Math.min(1, st * 2) }}>
                    {v.reduce((a, b) => a + b, 0).toLocaleString()}
                  </div>
                  <div style={{ position: 'absolute', left: 40, top: 30, font: '900 70px ' + F.sans, color: 'rgba(248,113,113,0.95)', transform: 'scale(' + (2.4 - st * 1.4) + ') rotate(-14deg)', opacity: st }}>✓</div>
                </>
              ) : null}
            </div>
          );
        })}
      </div>
      <div style={{ position: 'absolute', right: 110, top: 300, width: 560, textAlign: 'center' }}>
        <div style={{ font: '700 36px ' + F.sans, color: C.dim }}>연속 업로드</div>
        <div style={{ font: '900 150px/1 ' + F.sans, color: C.gold, textShadow: '0 0 50px rgba(250,204,21,0.6)' }}>{lit}<span style={{ fontSize: 60 }}>일</span></div>
        <div style={{ font: '700 36px ' + F.sans, color: C.dim, marginTop: 30 }}>올린 쇼츠</div>
        <div style={{ font: '900 96px/1 ' + F.sans, color: C.paper }}>{posts}<span style={{ fontSize: 44 }}>편</span></div>
        <div style={{ font: '700 36px ' + F.sans, color: C.dim, marginTop: 30 }}>누적 조회수</div>
        <div style={{ font: '900 96px/1 ' + F.sans, color: C.paper, transform: 'scale(' + (done ? 1 + (1 - fin) * 0.3 : 1) + ')' }}>{views.toLocaleString()}</div>
      </div>
      {DAYS.map((_, i) => (
        <Sequence key={i} from={i * per} durationInFrames={6} layout="none"><Audio src={staticFile('sfx/tick.mp3')} volume={0.8} /></Sequence>
      ))}
      <Sequence from={per * DAYS.length + 6} durationInFrames={20} layout="none"><Audio src={staticFile('sfx/impact.mp3')} volume={0.9} /></Sequence>
    </AbsoluteFill>
  );
};

/** 단어 자막 — 4~5단어씩 한 줄, 지금 말하는 단어만 금색으로 튄다. 줄마다 등장 방식이 7가지로 바뀐다.
    관련 단어가 있으면 왼쪽에 금속 아이콘 배지가 붙는다. 시간 기준 = 이 컴포넌트가 놓인 Sequence의 0프레임 = 음성 0초 */
type Variant = 'pop' | 'rise' | 'blur' | 'type' | 'swing' | 'drop' | 'wipe';
const VARIANTS: Variant[] = ['rise', 'pop', 'blur', 'swing', 'type', 'drop', 'wipe'];
export const WordCaption: React.FC<{ k: string; offset?: number }> = ({ k, offset = 0 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / FPS + offset;
  const W = CAP[k] || [];
  const lines: [number, number][] = [];
  let st = 0;
  for (let i = 1; i <= W.length; i++) {
    const brk = i === W.length || i - st >= 5 || W[i][1] - W[i - 1][2] > 0.35 || /[.?!]$/.test(W[i - 1][0]);
    if (brk) { lines.push([st, i]); st = i; }
  }
  const li = lines.findIndex(([a, b]) => t >= W[a][1] - 0.05 && t <= W[b - 1][2] + 0.25);
  if (li < 0) return null;
  const [a, b] = lines[li];
  const words = W.slice(a, b);
  const v = VARIANTS[li % VARIANTS.length];
  const lineF = Math.round((t - W[a][1] + 0.05) * fps);
  const lp = spring({ frame: lineF, fps, config: { damping: 14, mass: 0.5 } });
  const rule = ICON_RULES.find(([re]) => words.some((w) => re.test(w[0])));
  const box: React.CSSProperties = v === 'wipe'
    ? { clipPath: 'inset(0 ' + (1 - lp) * 100 + '% 0 0)' }
    : { transform: 'translateY(' + (v === 'drop' ? -(1 - lp) * 60 : (1 - lp) * 30) + 'px)', opacity: Math.min(1, lp * 1.4) };
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 50, pointerEvents: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 22, ...box }}>
        {rule ? <IconBadge name={rule[1]} size={118} /> : null}
        <div style={{ padding: '8px 30px', borderRadius: 16, background: 'linear-gradient(90deg, rgba(0,0,0,0.0), rgba(0,0,0,0.6) 12%, rgba(0,0,0,0.6) 88%, rgba(0,0,0,0))', perspective: 600 }}>
          {words.map(([w, s, e], i) => {
            const on = t >= s && t <= e + 0.05;
            const past = t > e;
            const wf = Math.round((t - s) * fps);
            const q = spring({ frame: wf, fps, config: { damping: 9, mass: 0.4 } });
            const appear = spring({ frame: lineF - i * 2, fps, config: { damping: 12, mass: 0.5 } });
            let tr = '';
            let op = 1;
            let fl = 'none';
            if (v === 'pop') tr = 'scale(' + (0.3 + appear * 0.7) + ')';
            if (v === 'rise') { tr = 'translateY(' + (1 - appear) * 70 + 'px)'; op = appear; }
            if (v === 'blur') { fl = 'blur(' + (1 - appear) * 14 + 'px)'; op = appear; }
            if (v === 'swing') tr = 'rotateX(' + (1 - appear) * 90 + 'deg)';
            if (v === 'drop') { tr = 'translateY(' + -(1 - appear) * 80 + 'px)'; op = appear; }
            if (v === 'type') op = t >= s - 0.02 ? 1 : 0;
            const boost = on ? ' scale(' + (1.06 + (1 - Math.min(1, q)) * 0.18) + ') translateY(-4px)' : '';
            return (
              <span key={i} style={{
                display: 'inline-block', margin: '0 12px', font: '900 62px ' + F.sans, opacity: op, filter: fl,
                color: on ? C.gold : past || v === 'type' ? '#fff' : 'rgba(255,255,255,0.6)',
                transform: tr + boost, ...STROKE,
                textShadow: on ? '0 0 26px rgba(250,204,21,0.8), 0 8px 30px #000' : STROKE.textShadow,
              }}>{w}</span>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
