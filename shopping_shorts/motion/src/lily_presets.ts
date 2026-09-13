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
  label?: {bg: string; color: string};  // 위 작은 라벨 박스(첨자용). props.label 텍스트와 함께 씀
  emoji?: string;      // 글자 양옆 이모지(화날때 🔥 등)
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
  // #2 첨자 — 핑크 글자+노란 외곽선, 위에 핑크 라벨 박스
  cheomja: {
    id: 'cheomja', name: '릴리 · 첨자(라벨)',
    fontFamily: 'TmonMonsori', italic: 6,
    fillColor: '#ff5fb0', hlColor: '#ffe14d', hlStroke: '#ff2e8f',
    strokeColor: '#ffe14d', strokeW: 6,
    glow: 'rgba(255,120,190,0.5)', sparkle: false, anim: 'pop', fontSize: 84,
    label: {bg: '#ff7ab8', color: '#ffffff'},
  },
  // #11 첨자 자막 — 흰 글자 + 핑크 외곽선 + 위 핑크 라벨(강조어만 핑크)
  cheomja_white: {
    id: 'cheomja_white', name: '릴리 · 첨자(흰글자)',
    fontFamily: 'TmonMonsori', italic: 6,
    fillColor: '#ffffff', hlColor: '#ff5fb0', hlStroke: '#ffffff',
    strokeColor: '#ff7ab8', strokeW: 7,
    glow: 'rgba(255,120,190,0.45)', sparkle: false, anim: 'pop', fontSize: 84,
    label: {bg: '#ff7ab8', color: '#ffffff'},
  },
  // #11 첨자 — 파랑 라벨 변형
  cheomja_blue: {
    id: 'cheomja_blue', name: '릴리 · 첨자(파랑)',
    fontFamily: 'TmonMonsori', italic: 6,
    fillColor: '#ffffff', hlColor: '#4db6ff', hlStroke: '#ffffff',
    strokeColor: '#5a9bd8', strokeW: 7,
    glow: 'rgba(90,155,216,0.45)', sparkle: false, anim: 'pop', fontSize: 84,
    label: {bg: '#5a9bd8', color: '#ffffff'},
  },
  // #12 화날때 — 흰 글자 차분 버전(불편함을 감출 수 없구나)
  angry_calm: {
    id: 'angry_calm', name: '릴리 · 화날때(차분)',
    fontFamily: 'TmonMonsori', italic: 4,
    fillColor: '#f2f2f2', hlColor: '#ff6a3d', hlStroke: '#1a1a1a',
    strokeColor: '#1a1a1a', strokeW: 5,
    glow: 'rgba(0,0,0,0.4)', sparkle: false, anim: 'fade', fontSize: 80,
  },
  // #13 휘뚤마뚤 — 레트로 컬러(노랑 글자+주황 외곽선, 첨자 라벨)
  retro_yellow: {
    id: 'retro_yellow', name: '릴리 · 레트로 컬러',
    fontFamily: 'TmonMonsori', italic: 4,
    fillColor: '#ffd23d', hlColor: '#ff8a3d', hlStroke: '#7a3a00',
    strokeColor: '#7a3a00', strokeW: 6,
    glow: 'rgba(255,160,60,0.4)', sparkle: false, anim: 'pop', fontSize: 84,
    label: {bg: '#ffb000', color: '#5a2a00'},
  },
  // #13 휘뚤마뚤 — 네온 초록
  neon_green: {
    id: 'neon_green', name: '릴리 · 네온 초록',
    fontFamily: 'TmonMonsori', italic: 6,
    fillColor: '#ffffff', hlColor: '#7dff8a', hlStroke: '#ffffff',
    strokeColor: '#3ad14a', strokeW: 7,
    glow: 'rgba(80,230,110,0.6)', sparkle: true, anim: 'pop', fontSize: 90,
  },
  // #23 모션 — 무지개(강조어만 다른 색; 본문 흰 글자)
  rainbow: {
    id: 'rainbow', name: '릴리 · 무지개',
    fontFamily: 'TmonMonsori', italic: 6,
    fillColor: '#ffffff', hlColor: '#ff5fb0', hlStroke: '#ffffff',
    strokeColor: '#9b6bff', strokeW: 7,
    glow: 'rgba(150,90,255,0.5)', sparkle: true, anim: 'bounce', fontSize: 88,
  },
  // #23 모션 — 하늘 파랑
  sky_blue: {
    id: 'sky_blue', name: '릴리 · 하늘 파랑',
    fontFamily: 'TmonMonsori', italic: 6,
    fillColor: '#ffffff', hlColor: '#4db6ff', hlStroke: '#ffffff',
    strokeColor: '#2f8fd8', strokeW: 7,
    glow: 'rgba(80,170,240,0.55)', sparkle: true, anim: 'pop', fontSize: 88,
  },
  // #12 화날 때 — 빨간 글자+흰 외곽선, 양옆 불꽃
  angry: {
    id: 'angry', name: '릴리 · 화날때(불꽃)',
    fontFamily: 'TmonMonsori', italic: 6,
    fillColor: '#ff2b2b', hlColor: '#ffd23d', hlStroke: '#8a0000',
    strokeColor: '#ffffff', strokeW: 7,
    glow: 'rgba(255,60,0,0.55)', sparkle: false, anim: 'bounce', fontSize: 90,
    emoji: '🔥',
  },
  // ── 채널 톤별 기본 컬러 (P1 보강) ──
  mint: {
    id: 'mint', name: '릴리 · 민트',
    fontFamily: 'TmonMonsori', italic: 6, fillColor: '#ffffff', hlColor: '#3fe0c0', hlStroke: '#ffffff',
    strokeColor: '#1fb89c', strokeW: 7, glow: 'rgba(60,220,190,0.5)', sparkle: true, anim: 'pop', fontSize: 88,
  },
  coral: {
    id: 'coral', name: '릴리 · 코랄',
    fontFamily: 'TmonMonsori', italic: 6, fillColor: '#ffffff', hlColor: '#ff7a6b', hlStroke: '#ffffff',
    strokeColor: '#e85c4a', strokeW: 7, glow: 'rgba(255,110,90,0.5)', sparkle: true, anim: 'pop', fontSize: 88,
  },
  gold: {
    id: 'gold', name: '릴리 · 골드',
    fontFamily: 'TmonMonsori', italic: 4, fillColor: '#fff4d6', hlColor: '#ffcf3d', hlStroke: '#7a5a00',
    strokeColor: '#b8901f', strokeW: 6, glow: 'rgba(255,200,60,0.45)', sparkle: true, anim: 'pop', fontSize: 88,
  },
  lavender: {
    id: 'lavender', name: '릴리 · 라벤더',
    fontFamily: 'TmonMonsori', italic: 6, fillColor: '#ffffff', hlColor: '#c59bff', hlStroke: '#ffffff',
    strokeColor: '#9a6bff', strokeW: 7, glow: 'rgba(170,120,255,0.5)', sparkle: true, anim: 'pop', fontSize: 88,
  },
  red_punch: {
    id: 'red_punch', name: '릴리 · 레드 펀치',
    fontFamily: 'TmonMonsori', italic: 4, fillColor: '#ff3b3b', hlColor: '#ffd23d', hlStroke: '#600',
    strokeColor: '#ffffff', strokeW: 8, glow: 'rgba(255,40,40,0.5)', sparkle: false, anim: 'bounce', fontSize: 96,
  },
  clean_white: {
    id: 'clean_white', name: '릴리 · 클린 화이트',
    fontFamily: 'TmonMonsori', italic: 0, fillColor: '#ffffff', hlColor: '#ffe14d', hlStroke: '#333',
    strokeColor: '#1a1a1a', strokeW: 6, glow: 'rgba(0,0,0,0.4)', sparkle: false, anim: 'fade', fontSize: 88,
  },
};

export const resolveLilyPreset = (p?: string | LilyPreset): LilyPreset => {
  if (p && typeof p === 'object') return p;
  return LILY_PRESETS[(p as string) || 'hee_pink'] || LILY_PRESETS.hee_pink;
};
