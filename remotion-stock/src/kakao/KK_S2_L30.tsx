/**
 * KK_S2_L30 — S2 페인포인트 (LIFE 3.0 오버레이)
 * 실제 대본 (Whisper 추출, 2026-06-15):
 *   f0~106   주식을 하는 분들이라면 제 이야기에 공감하실 거예요.
 *   f106~241 눈 뜨자마자 무엇부터 확인해야 할지 모르고 매일 시간에 쫓기죠.
 *   f241~371 네이버 뉴스 들어가서 최신 기사 찾아보고 텔레그램 카톡방 채널 돌아다니면서
 *   f371~452 내가 산 종목 얘기 없나 아침마다 찾아 봅니다.
 *   f452~535 그러면 어느덧 장 시작 시간이 훅 넘어버리네요.
 *   f535~656 앞으로 이제는 매일 반복하는 정보수집일은 AI에게 맡기면 되는 겁니다.
 */

import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
} from 'remotion';

export const KK_S2_L30_FRAMES = 656;

const LIME   = '#AAFF00';
const LIME50 = 'rgba(170,255,0,0.5)';
const LIME20 = 'rgba(170,255,0,0.2)';
const CARD   = 'rgba(0,0,0,0.84)';
const BORDER = 'rgba(170,255,0,0.45)';

const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (f: number, from: number, damping = 9, stiffness = 270, mass = 0.7) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping, stiffness, mass } });

// ── 실제 대본 자막 (Whisper segments × 30fps) ──
const SUBS = [
  { from: 0,   to: 106, text: '주식을 하는 분들이라면 제 이야기에 공감하실 거예요.',            accent: '공감' },
  { from: 106, to: 241, text: '눈 뜨자마자 무엇부터 확인해야 할지 모르고 매일 시간에 쫓기죠.', accent: '시간에 쫓기죠' },
  { from: 241, to: 371, text: '네이버 뉴스 최신 기사 찾아보고 텔레그램 카톡방 채널 돌아다니면서', accent: '텔레그램 카톡방' },
  { from: 371, to: 452, text: '내가 산 종목 얘기 없나 아침마다 찾아 봅니다.',                    accent: '아침마다' },
  { from: 452, to: 535, text: '그러면 어느덧 장 시작 시간이 훅 넘어버리네요.',                  accent: '훅 넘어버리네요' },
  { from: 535, to: 656, text: '매일 반복하는 정보수집일은 AI에게 맡기면 되는 겁니다.',           accent: 'AI' },
];

// ── 아침 루틴 앱 목록 (실제 언급 플랫폼만) ──
const APPS = [
  { icon: '📰', label: '네이버 뉴스',  sub: '최신 기사 검색',  delay: 135, pct: 82 },
  { icon: '✈️', label: '텔레그램',     sub: '채널·그룹 체크',  delay: 158, pct: 68 },
  { icon: '💬', label: '카톡방',       sub: '찌라시 확인',     delay: 181, pct: 74 },
  { icon: '📊', label: '내 종목 얘기', sub: '종목별 검색',     delay: 204, pct: 55 },
];

// ── 솔루션 기능 목록 ──
const FEATS = [
  { num: '01', label: '뉴스 자동 요약',         delay: 548 },
  { num: '02', label: '텔레·카톡 모니터링',     delay: 562 },
  { num: '03', label: '관심 종목 얘기만 추출',  delay: 576 },
  { num: '04', label: '장 전 브리핑 자동 수신', delay: 590 },
];

const ClaudeLogo: React.FC<{ size?: number }> = ({ size = 46 }) => (
  <svg width={size} height={size} viewBox="0 0 46 46">
    <rect width="46" height="46" rx="10" fill="#D97757" />
    <rect x="10" y="10" width="7" height="26" rx="3.5" fill="white" />
    <rect x="19.5" y="10" width="7" height="26" rx="3.5" fill="white" />
    <rect x="29" y="10" width="7" height="26" rx="3.5" fill="white" />
  </svg>
);

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  position: 'absolute',
  background: CARD,
  border: `1.5px solid ${BORDER}`,
  borderRadius: 6,
  overflow: 'hidden',
  ...extra,
});

const kicker: React.CSSProperties = {
  fontFamily: "'Courier New', monospace",
  fontSize: 10,
  color: LIME,
  letterSpacing: 3,
  textTransform: 'uppercase',
  padding: '12px 18px 10px',
  borderBottom: `1px solid ${LIME20}`,
};

export const KK_S2_L30: React.FC = () => {
  const f = useCurrentFrame();

  const activeSub = SUBS.find(s => f >= s.from && f < s.to);

  const panelOp = (start: number, end: number) =>
    ci(f, start, start + 20) * ci(f, end - 16, end, 1, 0);
  const slideX = (start: number, dir: 1 | -1) =>
    dir * (1 - sp(f, start)) * 40;

  /* ── Phase 1: 공감 훅 카드 (f8~100) ── */
  const hookOp    = panelOp(8, 100);
  const hookScale = 0.82 + sp(f, 8, 8, 280, 0.6) * 0.18;

  /* ── Phase 2: 루틴 패널 + 압박 RIGHT (f110~440) ── */
  const leftOp  = panelOp(110, 440);
  const rightOp = panelOp(140, 440);

  /* ── Phase 3: 임팩트 (f455~535) ── */
  const impactOp    = panelOp(455, 535);
  const impactScale = 0.70 + sp(f, 455, 7, 290, 0.5) * 0.30;

  /* ── Phase 4: 솔루션 (f538~645) ── */
  const solOp  = panelOp(538, 645);
  const solROp = panelOp(568, 645);

  return (
    <AbsoluteFill style={{ fontFamily: "'Inter', sans-serif", overflow: 'hidden', background: '#000' }}>

      <OffthreadVideo
        src={staticFile('kakao/ep1/s02_face.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.2) 0%, transparent 28%, transparent 60%, rgba(0,0,0,0.55) 100%)',
      }} />

      {/* ══ Phase 1: 공감 훅 (f8~100) ══ */}
      <div style={{
        position: 'absolute', top: 80, left: '50%',
        transform: `translateX(-50%) scale(${hookScale})`,
        transformOrigin: 'center top',
        ...panel({ position: 'relative', width: 680, padding: '18px 30px', textAlign: 'center' }),
        opacity: hookOp,
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 10, color: LIME50,
          letterSpacing: 3, textTransform: 'uppercase', marginBottom: 10 }}>
          STOCK TRADER · 공감 체크
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 26, fontWeight: 800,
          color: '#fff', textShadow: '0 2px 12px rgba(0,0,0,0.9)', lineHeight: 1.45 }}>
          주식 하는 분들이라면<br />
          <span style={{ color: LIME, textShadow: `0 0 18px rgba(170,255,0,0.7)` }}>무조건 공감</span>하실 거예요 👇
        </div>
      </div>

      {/* ══ Phase 2 LEFT: 아침 루틴 패닉 (f110~440) ══ */}
      <div style={{
        ...panel({ left: 36, top: 80, width: 420, height: 320 }),
        opacity: leftOp,
        transform: `translateX(${slideX(110, -1)}px)`,
      }}>
        <div style={kicker}>MORNING PANIC · 아침 루틴</div>

        <div style={{ padding: '9px 18px 4px',
          fontFamily: "'Inter',sans-serif", fontSize: 13, fontWeight: 700,
          color: 'rgba(255,255,255,0.4)', opacity: ci(f, 115, 130) }}>
          눈 뜨자마자 → 뭐부터?
        </div>

        {APPS.map((app, i) => {
          const rowOp    = ci(f, app.delay, app.delay + 18);
          const barWidth = ci(f, app.delay + 6, app.delay + 28, 0, app.pct);
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 18px',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              opacity: rowOp,
            }}>
              <span style={{ fontSize: 17, width: 22, textAlign: 'center' }}>{app.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 13, fontWeight: 700,
                  color: '#fff', textShadow: '0 1px 8px rgba(0,0,0,0.9)' }}>{app.label}</div>
                <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                  color: 'rgba(255,255,255,0.35)', letterSpacing: 1.5 }}>{app.sub}</div>
              </div>
              <div style={{ width: 88, height: 3, background: 'rgba(255,255,255,0.08)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 2, width: `${barWidth}%`,
                  background: `linear-gradient(to right, rgba(170,255,0,0.4), ${LIME})`,
                  boxShadow: `0 0 6px ${LIME50}`,
                }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* ══ Phase 2 RIGHT: 장 시작 압박 (f140~440) ══ */}
      <div style={{
        ...panel({ right: 36, top: 80, width: 350, height: 260 }),
        opacity: rightOp,
        transform: `translateX(${slideX(140, 1)}px)`,
        padding: '20px 24px',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
          color: LIME50, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 14 }}>
          MARKET OPEN · 코스피
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 8 }}>
          <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 68, fontWeight: 900, lineHeight: 1,
            color: LIME, letterSpacing: -2,
            textShadow: `0 0 30px rgba(170,255,0,0.65), 0 4px 18px rgba(0,0,0,0.9)` }}>
            9:00
          </span>
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 12, fontWeight: 600,
          color: 'rgba(255,255,255,0.45)', marginBottom: 14 }}>
          장 시작 시간
        </div>
        <div style={{
          background: 'rgba(255,80,80,0.12)', border: '1px solid rgba(255,80,80,0.35)',
          borderRadius: 4, padding: '8px 12px',
          fontFamily: "'Inter',sans-serif", fontSize: 12, fontWeight: 700,
          color: 'rgba(255,120,120,0.9)',
          opacity: ci(f, 230, 248),
        }}>
          ⚠️ 아직 정보 수집 중...
        </div>
      </div>

      {/* ══ Phase 3: "장 시작 시간 훅 넘어버림" 임팩트 (f455~535) ══ */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        opacity: impactOp, pointerEvents: 'none',
        paddingBottom: '12%',
        transform: `scale(${impactScale})`,
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 12, color: LIME50,
          letterSpacing: 4, textTransform: 'uppercase', marginBottom: 12 }}>
          MARKET OPEN 9:00 AM
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 78, fontWeight: 900, lineHeight: 1,
          color: '#fff', letterSpacing: -3, textAlign: 'center',
          textShadow: '0 0 40px rgba(255,255,255,0.12), 0 6px 28px rgba(0,0,0,0.95)' }}>
          장 시작 시간이
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 78, fontWeight: 900, lineHeight: 1.1,
          color: LIME, letterSpacing: -3,
          textShadow: `0 0 40px rgba(170,255,0,0.6)` }}>
          훅 넘어버림
        </div>
      </div>

      {/* ══ Phase 4 LEFT: AI 솔루션 (f538~645) ══ */}
      <div style={{
        ...panel({ left: 36, top: 80, width: 440, height: 330 }),
        opacity: solOp,
        transform: `translateX(${slideX(538, -1)}px)`,
      }}>
        <div style={{ ...kicker, display: 'flex', alignItems: 'center', gap: 12 }}>
          <ClaudeLogo size={32} />
          <span>CLAUDE AI · 자동화 솔루션</span>
        </div>

        <div style={{ padding: '9px 18px 6px',
          fontFamily: "'Inter',sans-serif", fontSize: 12, fontWeight: 600,
          color: 'rgba(255,255,255,0.38)', opacity: ci(f, 542, 558) }}>
          정보수집 노가다 → AI에게 위임
        </div>

        {FEATS.map((ft, i) => {
          const rowOp   = ci(f, ft.delay, ft.delay + 16);
          const checkOp = ci(f, ft.delay + 14, ft.delay + 26);
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '11px 18px',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              opacity: rowOp,
            }}>
              <span style={{ fontFamily: "'Courier New',monospace", fontSize: 10,
                color: LIME50, width: 20 }}>{ft.num}</span>
              <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 14, fontWeight: 700,
                color: '#fff', flex: 1, textShadow: '0 1px 8px rgba(0,0,0,0.9)' }}>
                {ft.label}
              </span>
              <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                color: LIME, letterSpacing: 1.5, opacity: checkOp,
                textShadow: `0 0 8px ${LIME50}` }}>✓ AUTO</span>
            </div>
          );
        })}
      </div>

      {/* ══ Phase 4 RIGHT: 결과 (f568~645) ══ */}
      <div style={{
        ...panel({ right: 36, top: 80, width: 350, height: 230 }),
        opacity: solROp,
        transform: `translateX(${slideX(568, 1)}px)`,
        padding: '22px 26px',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
          color: LIME50, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 14 }}>
          RESULT · 이제부터는
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 22, fontWeight: 800,
          color: '#fff', lineHeight: 1.5, marginBottom: 14 }}>
          아침 정보수집<br />
          <span style={{ color: LIME, textShadow: `0 0 14px rgba(170,255,0,0.7)` }}>
            AI가 대신합니다
          </span>
        </div>
        <div style={{
          height: 2, background: LIME, borderRadius: 1,
          width: `${ci(f, 585, 618, 0, 100)}%`,
          boxShadow: `0 0 10px ${LIME50}`,
        }} />
      </div>

      {/* ══ 자막 바 ══ */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '17%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, transparent 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {activeSub && (
          <div style={{
            fontFamily: "'Inter',sans-serif",
            fontSize: 38, fontWeight: 700, color: '#fff',
            textAlign: 'center', paddingInline: 80,
            textShadow: '0 2px 16px rgba(0,0,0,0.95)',
            lineHeight: 1.4,
          }}>
            {activeSub.text.split(activeSub.accent).map((part, i, arr) => (
              <React.Fragment key={i}>
                {part}
                {i < arr.length - 1 && (
                  <span style={{ color: LIME, textShadow: `0 0 12px rgba(170,255,0,0.85)` }}>
                    {activeSub.accent}
                  </span>
                )}
              </React.Fragment>
            ))}
          </div>
        )}
      </div>

    </AbsoluteFill>
  );
};
