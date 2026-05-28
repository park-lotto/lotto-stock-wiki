// Sample B — UI 화면 콜라주
// 사람 안 보이고 UI 카드들만 시간순으로 등장 → 마지막에 대시보드로 통합
// "내 어깨너머에서 본 화면"이 영상 그 자체
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 240;

type Card = {
  title: string;
  subtitle: string;
  body: string[];
  x: number; y: number; w: number; h: number;
  onAt: number;   // progress 등장
  offAt?: number; // progress 사라짐
  accent?: boolean;
};

const CARDS: Card[] = [
  // 04:00 — 터미널 (크롤러 로그)
  { title: '04:00 · CRAWLER', subtitle: 'telegram·news·blog', body: ['> fetched 247 messages', '> fetched 89 posts', '> deduped → 312'],
    x: 80,  y: 120, w: 560, h: 280, onAt: 0.05, offAt: 0.55 },
  // 05:00 — Claude 분류
  { title: '05:00 · CLAUDE', subtitle: 'classifying...', body: ['반도체 · HBM ─ 18건', '조선 · MASGA ─ 12건', '방산 · KAI ─ 7건'],
    x: 700, y: 120, w: 560, h: 280, onAt: 0.18, offAt: 0.55 },
  // 06:00 — 위키 저장
  { title: '06:00 · WIKI', subtitle: 'stock_SK하이닉스.md', body: ['+ 컨센서스 TP 갱신', '+ 어닝서프 ✅', '+ 수급빈집 A등급'],
    x: 1320, y: 120, w: 540, h: 280, onAt: 0.30, offAt: 0.55 },
  // 07:30 — 인사이트 푸시
  { title: '07:30 · INSIGHT', subtitle: 'today picks ready', body: ['SK하이닉스 · 8/9pt', '한화에어로스페이스 · 6/9pt', '대한조선 · 6/9pt'],
    x: 380, y: 440, w: 600, h: 260, onAt: 0.40, offAt: 0.55 },
];

// 08:00 클라이맥스 — 대시보드가 풀스크린으로 통합
const HERO_AT = 0.55;
const CLICK_AT = 0.60;

export const DakkakB_UICollage = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const prog = interpolate(f, [10, DUR - 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const labelOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;

  // 마우스 커서 (08:00 클릭 모션)
  const cursorMoveProg = interpolate(prog, [0.45, CLICK_AT], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const cursorX = interpolate(cursorMoveProg, [0, 1], [1700, 960], { easing: Easing.out(Easing.cubic) });
  const cursorY = interpolate(cursorMoveProg, [0, 1], [900, 540], { easing: Easing.out(Easing.cubic) });
  const cursorOp = interpolate(prog, [0.42, 0.46, CLICK_AT + 0.03, CLICK_AT + 0.08], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 클릭 임팩트
  const clickPulse = interpolate(prog, [CLICK_AT, CLICK_AT + 0.06, CLICK_AT + 0.12], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 히어로 대시보드 등장
  const heroOp = interpolate(prog, [HERO_AT, 0.70], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const heroScale = interpolate(prog, [HERO_AT, 0.70], [0.85, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 딸깍 자막
  const ddakOp = interpolate(prog, [0.78, 0.88], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 카드 진입 애니메이션 헬퍼
  const cardAnim = (c: Card) => {
    const inAt = c.onAt;
    const outAt = c.offAt ?? 1.1;
    const inOp = interpolate(prog, [inAt, inAt + 0.05], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
    const outOp = interpolate(prog, [outAt - 0.04, outAt], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
    const opacity = inOp * outOp;
    const ty = interpolate(prog, [inAt, inAt + 0.05], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
    return { opacity, ty };
  };

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 우상단 샘플 라벨 */}
      <div style={{
        position: 'absolute', top: 40, right: 60,
        color: C.textSub, fontSize: 22, fontWeight: 600, letterSpacing: 4,
        opacity: labelOp, zIndex: 50,
      }}>SAMPLE B · UI COLLAGE</div>

      {/* 카드 콜라주 */}
      {CARDS.map((c, i) => {
        const a = cardAnim(c);
        if (a.opacity < 0.01) return null;
        return (
          <div key={i} style={{
            position: 'absolute',
            left: c.x, top: c.y, width: c.w, height: c.h,
            background: C.cardBg,
            border: `1px solid ${C.borderSub}`,
            borderRadius: 14,
            padding: '22px 28px',
            opacity: a.opacity,
            transform: `translateY(${a.ty}px)`,
            boxShadow: '0 12px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,255,208,0.08) inset',
            display: 'flex', flexDirection: 'column', gap: 10,
          }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <div style={{ color: C.main, fontSize: 22, fontWeight: 800, letterSpacing: 2 }}>{c.title}</div>
              <div style={{ color: C.textSub, fontSize: 18, fontWeight: 500 }}>{c.subtitle}</div>
            </div>
            <div style={{
              flex: 1, marginTop: 6,
              display: 'flex', flexDirection: 'column', gap: 8,
              fontFamily: '"Consolas", "Menlo", monospace',
            }}>
              {c.body.map((b, j) => (
                <div key={j} style={{
                  color: C.textPrimary, fontSize: 24, fontWeight: 500,
                  opacity: 0.9,
                }}>{b}</div>
              ))}
            </div>
          </div>
        );
      })}

      {/* 마우스 커서 */}
      {cursorOp > 0.01 && (
        <div style={{
          position: 'absolute', left: cursorX, top: cursorY,
          width: 36, height: 36, opacity: cursorOp,
          pointerEvents: 'none', zIndex: 60,
        }}>
          <svg width={36} height={36} viewBox="0 0 24 24">
            <path d="M2 2 L2 18 L7 14 L10 22 L13 21 L10 13 L17 13 Z"
              fill="#FFFFFF" stroke="#000000" strokeWidth={1.2} />
          </svg>
        </div>
      )}

      {/* 클릭 임팩트 링 */}
      {clickPulse > 0.01 && (
        <div style={{
          position: 'absolute', left: 940, top: 520,
          width: 40, height: 40, borderRadius: '50%',
          border: `3px solid ${C.main}`,
          transform: `scale(${1 + clickPulse * 4})`,
          opacity: 1 - clickPulse,
          boxShadow: GLOW.strong.box,
          pointerEvents: 'none', zIndex: 55,
        }} />
      )}

      {/* 히어로 대시보드 (08:00 통합 화면) */}
      {heroOp > 0.01 && (
        <div style={{
          position: 'absolute',
          left: 160, top: 140, width: 1600, height: 700,
          background: C.cardBgActive,
          border: `2px solid ${C.main}`,
          borderRadius: 22,
          padding: 40,
          opacity: heroOp,
          transform: `scale(${heroScale})`,
          transformOrigin: 'center center',
          boxShadow: GLOW.strong.box,
          zIndex: 40,
          display: 'flex', flexDirection: 'column', gap: 24,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={{ color: C.main, fontSize: 44, fontWeight: 900, textShadow: GLOW.mid.text }}>
              STOCK BRAIN · 08:00
            </div>
            <div style={{ color: C.textSub, fontSize: 24, fontWeight: 500, letterSpacing: 3 }}>
              오늘의 탑픽 · 섹터 · 수급
            </div>
          </div>
          <div style={{ display: 'flex', gap: 20, flex: 1 }}>
            {[
              { rank: '#1', name: 'SK하이닉스', score: '8 / 9', tag: '수급빈집 A · 수출🔴' },
              { rank: '#2', name: '한화에어로스페이스', score: '6 / 9', tag: '리포트 TP↑ · 일정 D-12' },
              { rank: '#3', name: '대한조선', score: '6 / 9', tag: 'PER 9.8 · 수주 역대최고' },
            ].map((t, i) => (
              <div key={i} style={{
                flex: 1, background: C.bg, border: `1px solid ${C.borderActive}`, borderRadius: 14,
                padding: '24px 26px', display: 'flex', flexDirection: 'column', gap: 12,
              }}>
                <div style={{ color: C.textSub, fontSize: 22, fontWeight: 700, letterSpacing: 3 }}>{t.rank}</div>
                <div style={{ color: C.textPrimary, fontSize: 38, fontWeight: 800 }}>{t.name}</div>
                <div style={{ color: C.main, fontSize: 56, fontWeight: 900, textShadow: GLOW.mid.text }}>{t.score}</div>
                <div style={{ color: C.textSub, fontSize: 20, fontWeight: 500 }}>{t.tag}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 딸깍 자막 (히어로 위 오버레이) */}
      <div style={{
        position: 'absolute', bottom: 110, left: 0, right: 0,
        textAlign: 'center',
        color: C.main, fontSize: 96, fontWeight: 900, letterSpacing: 8,
        textShadow: GLOW.strong.text,
        opacity: ddakOp,
        transform: `scale(${0.85 + ddakOp * 0.15})`,
        zIndex: 70,
      }}>딸깍</div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '12%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: labelOp, zIndex: 70,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 34, fontWeight: 700, opacity: 0.85 }}>
          내가 본 화면이 곧 영상이 된다
        </div>
      </div>
    </AbsoluteFill>
  );
};
