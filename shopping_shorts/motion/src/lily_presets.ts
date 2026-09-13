// 릴리리아(by. Lily) 자막 스타일 프리셋. deco_frame.PRESETS 처럼 한 곳에서 관리한다.
// 새 스타일을 추가할 때 여기 항목만 늘리면 된다(컴포넌트는 그대로).
export type LilyPreset = {
  id: string;
  name: string;        // 사람이 고르는 이름
  fontFamily: string;  // @font-face 로 등록된 이름
  italic: number;      // 기울임(deg). 0이면 없음
  fillColor: string;   // 글자색
  hlColor: string;     // 강조 단어색
  hlStroke?: string;   // 강조어 외곽선(대비 반전용, 기본 흰색)
  strokeColor: string; // 외곽선색
  strokeW: number;     // 외곽선 두께(px)
  glow: string;        // 글로우 색(rgba)
  sparkle: boolean;    // 양옆 반짝이 별
  anim: 'fade' | 'pop' | 'bounce';
  fontSize: number;
};

export const LILY_PRESETS: Record<string, LilyPreset> = {
  // #8 희로애락 — 핑크 네온: 흰 글자 아닌 진분홍 글자 + 두꺼운 흰 외곽선 + 핑크 글로우 + 반짝이
  hee_pink: {
    id: 'hee_pink',
    name: '릴리 · 핑크 네온(희로애락)',
    fontFamily: 'TmonMonsori',
    italic: 8,
    fillColor: '#ffffff',
    hlColor: '#ff2e8f',
    hlStroke: '#ffffff',
    strokeColor: '#ff2e8f',
    strokeW: 7,
    glow: 'rgba(255,90,175,0.55)',
    sparkle: true,
    anim: 'pop',
    fontSize: 96,
  },
  // #1 핫한 핑크 — 더 진한 핑크 톤
  hot_pink: {
    id: 'hot_pink',
    name: '릴리 · 핫핑크',
    fontFamily: 'TmonMonsori',
    italic: 8,
    fillColor: '#ffffff',
    hlColor: '#ff0d6e',
    hlStroke: '#ffffff',
    strokeColor: '#ff0d6e',
    strokeW: 7,
    glow: 'rgba(255,20,110,0.6)',
    sparkle: true,
    anim: 'pop',
    fontSize: 96,
  },
  // #9 화려한 모션 — 보라 네온
  purple_neon: {
    id: 'purple_neon',
    name: '릴리 · 보라 네온',
    fontFamily: 'TmonMonsori',
    italic: 8,
    fillColor: '#ffffff',
    hlColor: '#b06bff',
    hlStroke: '#ffffff',
    strokeColor: '#8a3dff',
    strokeW: 7,
    glow: 'rgba(150,80,255,0.6)',
    sparkle: true,
    anim: 'pop',
    fontSize: 96,
  },
};

export const resolveLilyPreset = (p?: string | LilyPreset): LilyPreset => {
  if (p && typeof p === 'object') return p;
  return LILY_PRESETS[(p as string) || 'hee_pink'] || LILY_PRESETS.hee_pink;
};
