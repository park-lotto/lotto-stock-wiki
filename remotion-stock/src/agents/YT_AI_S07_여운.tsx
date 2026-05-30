// YT_AI_S07_여운 — 씬 7 여운 (780프레임 / 25초)

import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

function ip(
  f: number, a: number, b: number,
  from = 0, to = 1,
  ease: (t: number) => number = Easing.out(Easing.cubic),
) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease,
  });
}

// ── 자막 세그먼트 ─────────────────────────────────────────────────
const SUBS = [
  { s: 0,   e: 240, text: '다음 편에서는 STOCK BRAIN이 어떻게 수많은 뉴스 속에서' },
  { s: 241, e: 299, text: '숨겨진 대박 키워드를 찾아내고, 그것이 곧 수급 빈집으로 이어지는지,' },
  { s: 300, e: 450, text: '뉴스 크롤링 기능의 심층 분석을 보여드리겠습니다.' },
  { s: 451, e: 780, text: '놓치지 마시고, 다음 영상도 꼭 시청해주세요!' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

export const YT_AI_S07_여운: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  const bgGlow = Math.sin(f * 0.04) * 0.028 + 0.05;
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // Phase 1: Thumbnail appears from right, positioned to the right of an implied presenter
  const thumbnailX_P1 = ip(f, 0, 30, 1920, 1920 - 600 - 80); // 600px width, 80px padding from right
  const thumbnailY_P1 = 1080 / 2 - 360 / 2; // Centered vertically
  const thumbnailScale_P1 = ip(f, 0, 30, 0.8, 1); // Slight scale in
  const thumbnailOpacity_P1 = ip(f, 0, 30);

  // Phase 2: Thumbnail zooms to center
  const thumbnailScale_P2 = ip(f, 450, 600, 1, 1.5, Easing.out(Easing.cubic));
  const thumbnailX_P2 = ip(f, 450, 600, 1920 - 600 - 80, (1920 - 600 * 1.5) / 2, Easing.out(Easing.cubic));
  const thumbnailY_P2 = ip(f, 450, 600, thumbnailY_P1, (1080 - 360 * 1.5) / 2, Easing.out(Easing.cubic));
  const thumbnailOpacity_P2 = ip(f, 450, 480); // Maintain opacity or fade in if it was fading out

  const currentThumbnailScale = f < 450 ? thumbnailScale_P1 : thumbnailScale_P2;
  const currentThumbnailX = f < 450 ? thumbnailX_P1 : thumbnailX_P2;
  const currentThumbnailY = f < 450 ? thumbnailY_P1 : thumbnailY_P2;
  const currentThumbnailOpacity = f < 450 ? thumbnailOpacity_P1 : thumbnailOpacity_P2;

  // Keyword highlighting logic based on dialogue
  const highlightHiddenKeyword = f >= 0 && f <= 299;
  const highlightSupplyEmptyHouse = f >= 0 && f <= 299;
  const highlightNewsCrawling = f >= 300 && f <= 450;
  const getKeywordStyle = (highlight: boolean) => ({
    color: highlight ? C.main : '#FFF',
    textShadow: highlight ? dynGlow : 'none',
    transition: 'all 0.2s ease-out', // Smooth transition for glow
  });

  return (
    <AbsoluteFill style={{ backgroundColor: '#080c14', overflow: 'hidden' }}>
      <Html5Audio src={staticFile('voice/yt_ai_s07_tease.m4a')} />

      {/* Background glow effect */}
      <div style={{
        position: 'absolute',
        inset: -100, // Make it larger than screen to cover edges
        background: `radial-gradient(circle at center, rgba(0,255,208,${bgGlow}) 0%, transparent 70%)`,
        opacity: ip(f, 0, 30),
      }} />

      {/* Thumbnail for next video */}
      <div style={{
        position: 'absolute',
        width: 600,
        height: 360,
        backgroundColor: 'rgba(14,20,32,0.8)',
        borderRadius: 20,
        border: `2px solid ${C.main}`,
        boxShadow: dynGlow,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 40,
        textAlign: 'center',
        fontFamily: FONT,
        left: currentThumbnailX,
        top: currentThumbnailY,
        opacity: currentThumbnailOpacity,
        transform: `scale(${currentThumbnailScale})`,
        transition: 'transform 0.5s ease-out, left 0.5s ease-out, top 0.5s ease-out, opacity 0.3s ease-out',
      }}>
        <div style={{ fontSize: 48, fontWeight: 800, color: '#FFF', marginBottom: 20 }}>
          다음 영상 미리보기
        </div>
        <div style={{ fontSize: 36, fontWeight: 700, lineHeight: 1.4 }}>
          <span style={getKeywordStyle(highlightNewsCrawling)}>뉴스 크롤링</span>으로
          <br />
          <span style={getKeywordStyle(highlightHiddenKeyword)}>숨겨진 대박 키워드</span>를 찾아
          <br />
          <span style={getKeywordStyle(highlightSupplyEmptyHouse)}>수급 빈집</span>을 공략!
        </div>
        <div style={{
          position: 'absolute',
          bottom: 20,
          right: 20,
          fontSize: 24,
          fontWeight: 600,
          color: C.main,
          opacity: ip(f, 450, 480, 0, 1),
          textShadow: dynGlow,
        }}>
          #STOCKBRAIN #AI투자
        </div>
      </div>

      {/* 자막바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80,
        background: 'linear-gradient(to top,rgba(8,12,20,0.88) 0%,transparent 100%)',
      }}>
        {sub && <div style={{
          color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center',
          opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)',
        }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};