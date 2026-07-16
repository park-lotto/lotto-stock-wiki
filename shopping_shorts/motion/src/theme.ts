// 스타일 테마: 콘텐츠 장르별로 팔레트·모서리·폰트·글로우를 교체한다.
// 컴포넌트는 그대로 두고 이 토큰만 바꿔 주식(테크)·레시피(따뜻함) 등 다른 톤을 낸다.
export type Theme = {
  accent: string;      // 주 강조색
  accentSoft: string;  // 보조 강조(숫자 단위 등)
  cardBg: string;      // 카드 배경
  ink: string;         // 카드 위 본문 텍스트
  label: string;       // 라벨 색
  border: string;      // 카드 테두리
  radius: number;      // 모서리 둥글기
  brackets: boolean;   // 테크 코너 브래킷 사용 여부
  labelMono: boolean;  // 라벨을 모노스페이스 대문자로
  heading: string;     // 제목 폰트
  glow: string;        // 그림자/글로우 색
  impactTop: string;   // 임팩트 텍스트 그라데이션 상단
  impactStroke: string;// 임팩트 텍스트 외곽선
};

const SANS = '"Malgun Gothic","맑은 고딕",system-ui,sans-serif';
const ROUND = '"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif';

// 주식·데이터: LIFE 3.0 네온 라임, 모노, 날카로운 브래킷.
export const TECH: Theme = {
  accent: '#c6f04a', accentSoft: '#c6f04a',
  cardBg: 'rgba(6,10,4,0.84)', ink: '#ffffff', label: '#c6f04a',
  border: 'rgba(198,240,74,0.28)', radius: 0, brackets: true, labelMono: true,
  heading: SANS, glow: 'rgba(198,240,74,0.4)',
  impactTop: '#eaffb0', impactStroke: '#22330a',
};

// 레시피·라이프스타일: 따뜻한 크림 카드, 코랄, 둥근 모서리, 친근함.
export const WARM: Theme = {
  accent: '#ff6f61', accentSoft: '#ff9e7d',
  cardBg: 'rgba(255,249,242,0.94)', ink: '#4a2f28', label: '#e8615a',
  border: 'rgba(255,111,97,0.35)', radius: 22, brackets: false, labelMono: false,
  heading: ROUND, glow: 'rgba(255,158,125,0.5)',
  impactTop: '#fff0ea', impactStroke: '#7a2c22',
};

export const THEMES: Record<string, Theme> = {tech: TECH, warm: WARM};
export const resolveTheme = (t?: string | Theme): Theme =>
  typeof t === 'string' ? (THEMES[t] || TECH) : (t || TECH);
