/**
 * KK_S1_Hooking — S1 훅 씬 (후킹 채널 벤치마킹 스타일)
 *
 * ▶ 배경: s1scene.mp4  →  public/kakao/s1scene.mp4 에 복사 필요
 *   (원본: C:\Users\TheRose\Desktop\클로드 카톡방\s1씬.mp4)
 *
 * ▶ 스타일 참조: raw/리모션/레퍼런스/image 1~39.png (후킹 채널)
 *   - 순수 검정 배경 (#000000)
 *   - 라임 그린 포인트 (#39FF14)
 *   - 4포인트 별 파티클
 *   - 씬당 대표 이모지 (130px)
 *   - 영어 소문자 라벨 + 한국어 대형 볼드 타이틀
 *   - 하단 자막 바 (그라디언트)
 *
 * ▶ 대본 기준: yt_카카오클로드_대본_v6.md S1
 *
 * 씬 구조 (1800f = 60초 @ 30fps):
 *   CH1  f0~180   : 🤖 "클로드로 갈아탔어요"
 *   CH2  f270~450 : 🇺🇸 "GPT는 옛날 / 클로드가 지금"
 *   CH3  f540~720 : 😅 "그냥 AI 아니냐?"  (지인 반응)
 *   CH4  f810~990 : ☀️ "자는 동안 / 클로드가 했어요"
 *   CH5  f1080~1260: ⏱️ "딱 10분"
 *   CH6  f1350~1530: 📌 "프롬프트 전부 드려요"
 *   VIDEO f1530~1800: 비디오 클리어 (자막만)
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
import { FONT } from '../constants';

export const KK_S1_HOOKING_FRAMES = 1800;

// ── 컬러 팔레트 (후킹 채널 기준) ─────────────────────────────
const LIME   = '#39FF14';
const LIMESF = '#C8FF00';   // 소프트 라임 (대형 타이틀 강조)
const WHITE  = '#FFFFFF';
const GRAY   = '#888888';
const KAKAO  = '#FAE100';
const KAKAO_D = '#3A2F00';

// ── 유틸 ─────────────────────────────────────────────────────
const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

const sp = (
  f: number,
  from: number,
  damping = 14,
  stiffness = 220,
  mass = 0.75,
) => spring({ frame: Math.max(0, f - from), fps: 30, config: { damping, stiffness, mass } });

// ── 별 파티클 위치 정의 ────────────────────────────────────────
const STARS: [number, number, number][] = [
  [110,  78,  1.00], [1812, 62,  0.75], [235, 975, 0.90],
  [1690, 912, 0.80], [958, 118,  0.65], [382, 550, 0.55],
  [1535, 398, 0.72], [672, 212,  0.62], [1215, 858, 0.88],
  [74,  402,  0.52], [1848, 698, 0.63], [572, 758, 0.70],
  [782, 352,  0.48], [1142, 492, 0.58], [1418, 222, 0.66],
  [440, 155,  0.55], [1280, 750, 0.60], [820,  60, 0.45],
];

const StarParticles: React.FC<{ f: number }> = ({ f }) => (
  <svg
    viewBox="0 0 1920 1080"
    style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
  >
    {STARS.map(([x, y, s], i) => {
      const pulse = Math.sin(f * 0.038 + i * 1.27) * 0.35 + 0.65;
      const sz = 7 * s;
      return (
        <g key={i} transform={`translate(${x},${y})`} opacity={s * pulse * 0.88}>
          <line x1={0} y1={-sz} x2={0} y2={sz} stroke={LIME} strokeWidth={1.4} />
          <line x1={-sz} y1={0} x2={sz} y2={0} stroke={LIME} strokeWidth={1.4} />
          <line x1={-sz * 0.52} y1={-sz * 0.52} x2={sz * 0.52} y2={sz * 0.52} stroke={LIME} strokeWidth={0.8} />
          <line x1={sz * 0.52} y1={-sz * 0.52} x2={-sz * 0.52} y2={sz * 0.52} stroke={LIME} strokeWidth={0.8} />
        </g>
      );
    })}
  </svg>
);

// ── 챕터 카드 ─────────────────────────────────────────────────
interface ChapterCardProps {
  f:       number;
  showAt:  number;
  hideAt:  number;
  emoji:   string;
  label:   string;        // 영어 소문자 서브라벨
  line1:   string;        // 타이틀 1행
  line2:   string;        // 타이틀 2행 (강조색)
  sub?:    string;        // 서브텍스트
  accentLine?: 1 | 2;    // 어느 행을 라임으로 강조할지
}

const ChapterCard: React.FC<ChapterCardProps> = ({
  f, showAt, hideAt, emoji, label, line1, line2, sub, accentLine = 2,
}) => {
  // 범위 밖이면 렌더링 skip
  if (f < showAt - 8 || f > hideAt + 8) return null;

  const fadeIn  = ci(f, showAt, showAt + 22);
  const fadeOut = ci(f, hideAt - 22, hideAt, 1, 0);
  const op      = Math.min(fadeIn, fadeOut);

  const prog  = sp(f, showAt, 14, 220, 0.75);
  const scale = interpolate(prog, [0, 1], [0.86, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const emojiY = interpolate(prog, [0, 1], [18, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  const subOp = ci(f, showAt + 28, showAt + 48);

  const textColor1 = accentLine === 1 ? LIMESF : WHITE;
  const textColor2 = accentLine === 2 ? LIMESF : WHITE;
  const textShadow1 = accentLine === 1 ? `0 0 28px ${LIME}66` : undefined;
  const textShadow2 = accentLine === 2 ? `0 0 28px ${LIME}66` : undefined;

  return (
    <div style={{
      position: 'absolute', inset: 0,
      bottom: '18%',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      opacity: op, pointerEvents: 'none',
    }}>
      {/* 이모지 */}
      <div style={{
        fontSize: 130, lineHeight: 1,
        transform: `scale(${scale}) translateY(${emojiY}px)`,
        marginBottom: 26,
        filter: `drop-shadow(0 0 28px ${LIME}66)`,
      }}>
        {emoji}
      </div>

      {/* 영어 라벨 */}
      <div style={{
        fontFamily: '"Courier New", monospace',
        fontSize: 14, fontWeight: 400,
        letterSpacing: '4.5px',
        textTransform: 'uppercase',
        color: LIME,
        marginBottom: 18,
        opacity: 0.90,
      }}>
        {label}
      </div>

      {/* 타이틀 2행 */}
      <div style={{
        transform: `scale(${scale})`,
        textAlign: 'center',
      }}>
        <div style={{
          fontFamily: FONT,
          fontSize: 82,
          fontWeight: 900,
          lineHeight: 1.10,
          color: textColor1,
          textShadow: textShadow1,
          letterSpacing: '-1px',
        }}>
          {line1}
        </div>
        <div style={{
          fontFamily: FONT,
          fontSize: 82,
          fontWeight: 900,
          lineHeight: 1.10,
          color: textColor2,
          textShadow: textShadow2,
          letterSpacing: '-1px',
        }}>
          {line2}
        </div>
      </div>

      {/* 서브텍스트 */}
      {sub && (
        <div style={{
          fontFamily: FONT,
          fontSize: 30,
          fontWeight: 500,
          color: GRAY,
          marginTop: 20,
          opacity: subOp,
          letterSpacing: '0.3px',
        }}>
          {sub}
        </div>
      )}
    </div>
  );
};

// ── 자막 데이터 ───────────────────────────────────────────────
const CAPS: { from: number; to: number; text: string; accent?: string }[] = [
  { from: 0,    to: 150,  text: '주식판 고수들은 이미 다릅니다',          accent: '이미' },
  { from: 150,  to: 270,  text: '클로드로 갈아탔어요',                    accent: '클로드' },
  { from: 270,  to: 420,  text: '미국 앱스토어에서도 난리가 났죠',        accent: '난리' },
  { from: 420,  to: 540,  text: '자동화 기능까지 특화되어서 그렇더라고요' },
  { from: 540,  to: 690,  text: '"그거 그냥 대화하는 AI 아니냐?"',        accent: 'AI 아니냐' },
  { from: 690,  to: 810,  text: '주위 40-50대 지인들 반응이 이래요' },
  { from: 810,  to: 960,  text: '오늘 아침 카톡 — 어젯밤 설정만 해둔 거예요', accent: '어젯밤 설정' },
  { from: 960,  to: 1080, text: '자는 동안 클로드가 알아서 한 겁니다',    accent: '클로드' },
  { from: 1080, to: 1230, text: '딱 10분만 투자하면 됩니다',              accent: '10분' },
  { from: 1230, to: 1350, text: '복잡한 코딩 전혀 없어요',                accent: '코딩 없어요' },
  { from: 1350, to: 1530, text: '프롬프트 고정 댓글로 다 드릴게요 👇',    accent: '고정 댓글' },
  { from: 1530, to: 1800, text: '지금 영상 끝까지 집중해주세요!',          accent: '집중' },
];

// ── 챕터별 어두운 오버레이 계산 ───────────────────────────────
const CARD_WINDOWS: [number, number][] = [
  [0, 180], [270, 450], [540, 720], [810, 990], [1080, 1260], [1350, 1530],
];
const TRANS = 22;
const BASE_DIM = 0.30;
const CARD_DIM = 0.80;

function calcOverlay(f: number): number {
  let maxCard = 0;
  for (const [start, end] of CARD_WINDOWS) {
    const fadeIn  = ci(f, start, start + TRANS);
    const fadeOut = ci(f, end - TRANS, end, 1, 0);
    const active  = Math.min(fadeIn, fadeOut);
    if (active > maxCard) maxCard = active;
  }
  return BASE_DIM + maxCard * (CARD_DIM - BASE_DIM);
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────
export const KK_S1_Hooking: React.FC = () => {
  const f   = useCurrentFrame();

  const overlayOp = calcOverlay(f);
  const activeCap = CAPS.find(c => f >= c.from && f < c.to);

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: FONT, overflow: 'hidden' }}>

      {/* ── 배경 영상 ──────────────────────────────────────────── */}
      <OffthreadVideo
        src={staticFile('kakao/s1scene.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* ── 어두운 오버레이 (챕터 카드 등장 시 짙어짐) ─────────── */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `rgba(0,0,0,${overlayOp})`,
      }} />

      {/* ── 별 파티클 ─────────────────────────────────────────── */}
      <StarParticles f={f} />

      {/* ── 챕터 카드 1: 클로드로 갈아탔어요 ─────────────────────── */}
      <ChapterCard
        f={f} showAt={0} hideAt={180}
        emoji="🤖"
        label="S1 · Claude 혁명"
        line1="클로드로"
        line2="갈아탔어요"
        accentLine={2}
        sub="주식판 고수들이 선택한 이유"
      />

      {/* ── 챕터 카드 2: GPT는 옛날 / 클로드가 지금 ─────────────── */}
      <ChapterCard
        f={f} showAt={270} hideAt={450}
        emoji="📱"
        label="미국 앱스토어 트렌드"
        line1="GPT는 옛날"
        line2="클로드가 지금"
        accentLine={2}
        sub="자동화 + 리서치 특화"
      />

      {/* ── 챕터 카드 3: 지인 반응 ───────────────────────────────── */}
      <ChapterCard
        f={f} showAt={540} hideAt={720}
        emoji="😅"
        label="주위 반응"
        line1='"그냥 대화하는'
        line2='AI 아니냐?"'
        accentLine={1}
        sub="40-50대 지인들 이야기"
      />

      {/* ── 챕터 카드 4: 아침 카톡 브리핑 ───────────────────────── */}
      <ChapterCard
        f={f} showAt={810} hideAt={990}
        emoji="☀️"
        label="아침 자동 브리핑"
        line1="자는 동안"
        line2="클로드가 했어요"
        accentLine={2}
        sub="어젯밤 설정 → 아침 카톡 도착"
      />

      {/* ── 챕터 카드 5: 10분 약속 ───────────────────────────────── */}
      <ChapterCard
        f={f} showAt={1080} hideAt={1260}
        emoji="⏱️"
        label="지금 바로 따라하기"
        line1="딱"
        line2="10분"
        accentLine={2}
        sub="코딩 없음 · 프롬프트 전부 공유"
      />

      {/* ── 챕터 카드 6: 프롬프트 공유 ──────────────────────────── */}
      <ChapterCard
        f={f} showAt={1350} hideAt={1530}
        emoji="📌"
        label="고정 댓글 확인"
        line1="프롬프트"
        line2="전부 드려요"
        accentLine={2}
        sub="구독 + 고정댓글 저장하세요 👇"
      />

      {/* ── 채널 배지 (좌상단) ────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 40, left: 52,
        opacity: ci(f, 18, 42),
        display: 'flex', flexDirection: 'column', gap: 5,
        zIndex: 30,
      }}>
        <div style={{
          background: KAKAO,
          color: KAKAO_D,
          fontSize: 12,
          fontWeight: 900,
          letterSpacing: '0.5px',
          padding: '3px 12px',
          borderRadius: 6,
          display: 'inline-flex',
          alignSelf: 'flex-start',
        }}>
          카카오 × 클로드
        </div>
        <div style={{
          color: 'rgba(255,255,255,0.55)',
          fontSize: 11,
          fontWeight: 500,
        }}>
          STOCKBRAIN
        </div>
      </div>

      {/* ── 하단 자막 바 ─────────────────────────────────────────── */}
      <div style={{
        position: 'absolute',
        bottom: 0, left: 0, right: 0,
        height: '18%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.94) 0%, rgba(0,0,0,0.60) 55%, transparent 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 20,
      }}>
        {activeCap && (
          <div
            key={activeCap.from}
            style={{
              fontSize: 42,
              fontWeight: 700,
              color: WHITE,
              textAlign: 'center',
              paddingInline: 80,
              lineHeight: 1.35,
              textShadow: '0 2px 16px rgba(0,0,0,1)',
            }}
          >
            {activeCap.accent
              ? (() => {
                  const parts = activeCap.text.split(activeCap.accent!);
                  return parts.map((part, i, arr) => (
                    <React.Fragment key={i}>
                      {part}
                      {i < arr.length - 1 && (
                        <span style={{ color: LIMESF, textShadow: `0 0 16px ${LIME}88` }}>
                          {activeCap.accent}
                        </span>
                      )}
                    </React.Fragment>
                  ));
                })()
              : activeCap.text
            }
          </div>
        )}
      </div>

    </AbsoluteFill>
  );
};
