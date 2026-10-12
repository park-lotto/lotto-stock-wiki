import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { Scene, Para, sceneFrames } from './V2_Engine';
import { V2_S47_Proof } from './V2_S47_Proof';
import { V2_Compare } from './V2_S41';
import { BackKind } from './V2_Bg';

/* 숏템메이커 V2 광고 — S3 · S4-7 · S5 · S6 · S7 · S8 (데이터만. 연출은 V2_Engine 한 곳)
   문단 길이 = 필재 TTS 문단 파일 실측(초) */
const RANK = 'shottem2/bg/bg_랭킹스크롤.mp4';
const SSUL = 'shottem2/bg/bg_랭킹썰쇼핑.mp4';
const INSTA = 'shottem2/bg/bg_랭킹인스타.mp4';
const CAT = 'shottem2/bg/bg_랭킹카테고리.mp4';
const CODE = 'shottem2/bg/bg_코드터미널.mp4';
const CAPCUT = 'shottem2/bg/bg_캡컷타임라인.mp4';
const MOM = 'shottem2/v2s1/mom1.mp4';
const MOM2 = 'shottem2/v2s1/mom2.mp4';
const RV = (n: number) => 'shottem2/s47/rvc' + n + '.jpg';  // 날짜 자르고 이름 가운데 가림


// 배경을 문단마다 6종으로 돌린다(같은 배경 연속 금지). 어머니 영상이 배경이면 히어로로 그 영상을 쓴다.
const KINDS: BackKind[] = ['ring', 'mosaic', 'split', 'aurora', 'hero', 'wall'];
const vary = (P: Para[], seed: number): Para[] => P.map((p, i) => {
  if (p.back || p.img || p.frame) return p;
  if (p.bg === MOM || p.bg === MOM2) return { ...p, back: 'hero', seed: seed + i };
  return { ...p, back: KINDS[(i + seed) % KINDS.length], seed: seed * 3 + i, bg: undefined };
});

// ── S3 방구석에서 V2가 나오기까지 ──
const S3: Para[] = [
  { dur: 21.409, bg: CODE, tint: 'cyan', hits: [
    { t: '방구석에서\n직접 만들었다', style: 'mega', accent: '직접' }, { t: '진짜 이야기는\n1편 다음부터', style: 'slam' },
    { t: '회사라면?\n회의 · 결재 · 다음 분기', style: 'stack' }, { t: '오늘 들은 불편\n오늘 밤 고칩니다', style: 'mega', accent: '오늘 밤' } ] },
  { dur: 25.091, bg: CODE, tint: 'amber', hits: [
    { t: '"몇 장면만\n지우면 안 돼요?"', style: 'quote' }, { t: '✓ 그날 밤 고쳤습니다', style: 'tag' },
    { t: '"짤·효과음\n찾기 힘들어요"', style: 'quote' }, { t: '✓ 대본 줄마다 자동으로', style: 'tag' },
    { t: '"롱폼은 또\n따로 만들어요?"', style: 'quote' }, { t: '✓ 쇼츠 하나로 롱폼까지', style: 'tag' } ] },
  { dur: 10.727, bg: CODE, tint: 'amber', hits: [
    { t: '59일 동안 고친 횟수', style: 'count', num: 2478, unit: '번', sub: 'UPDATE' }, { t: '막힌 자리를\n하나씩 뚫었다', style: 'kinetic', accent: '뚫었다' } ] },
  { dur: 9.182, bg: MOM, tint: 'monoWarm', hits: [
    { t: '"이 화면, 우리 엄마가\n혼자 넘어갈 수 있나"', style: 'quote' }, { t: '막히면\n제 프로그램 잘못', style: 'slam' } ] },
  { dur: 9.045, bg: RANK, tint: 'amber', hits: [
    { t: '외울 것 없이\n고르고 · 누르면 끝', style: 'kinetic', accent: '누르면' }, { t: '숏템메이커\nV2', style: 'mega' } ] },
  { dur: 16.136, bg: SSUL, tint: 'amber', hits: [
    { t: '찾고 → 쓰고 → 맞춘다', style: 'tag' }, { t: '원리는 그대로', style: 'slam' },
    { t: '모든 단계가\n미친 듯이 좋아졌다', style: 'mega', accent: '미친 듯이' }, { t: '지금부터\n비교해 보십시오', style: 'kinetic', accent: '비교' } ] },
];
export const V2_S3_FRAMES = sceneFrames(S3);
export const V2_S3: React.FC = () => <Scene voice="shottem2/v2s3/voice.mp3" paras={vary(S3, 2)} cap="02" />;

// ── S4-7 완성·증거 — 첫 문단(완성본 비교)은 녹화 대기, 나머지는 증거 장면(V2_S47_Proof) ──
const S47_HEAD: Para[] = [
  { dur: 16.682, bg: RANK, tint: 'amber', hitAt: [0, 0.45, 0.72], hits: [
    { t: '', node: <V2_Compare /> },   // 터진 썰쇼핑 원본 vs 숏템메이커 완성본 나란히(소재: public/shottem2/v2s47h/)
    { t: '머리 쥐어짠 순간\n0번', style: 'mega', accent: '0번' }, { t: '눈앞에서\n직접 만들어 보였습니다', style: 'kinetic', accent: '직접' } ] },
];
const S47_TAIL: Para[] = [
  { dur: 10.545, bg: SSUL, tint: 'amber', hits: [
    { t: '매일 올리는 게\n제일 힘들었다', style: 'slam' }, { t: '이제 매일은\n문제가 아니다', style: 'mega', accent: '문제가 아니다' }, { t: '양산형과의 차이', style: 'tag' } ] },
];
const HEAD = Math.round(16.682 * 30);
const PROOF = Math.round((4.5 + 1.864 + 16.682) * 30);
export const V2_S47F_FRAMES = HEAD + PROOF + sceneFrames(S47_TAIL);
export const V2_S47F: React.FC = () => (
  <AbsoluteFill>
    <Scene voice="shottem2/v2s47/voice.mp3" paras={S47_HEAD} />
    <Sequence from={HEAD} durationInFrames={PROOF}><V2_S47_Proof /></Sequence>
    {/* "회원분들 반응도 보시죠" — 후기 5장을 빠르게 넘긴다(3번·7번은 같은 글이라 7번 제외) */}
    <Sequence from={HEAD + Math.round(4.5 * 30)} durationInFrames={Math.round(1.864 * 30) + 45}>
      <Scene paras={[{ dur: 1.864 + 1.5, img: RV(1), hits: [
        { t: '', img: RV(1) }, { t: '', img: RV(2) }, { t: '', img: RV(4) }, { t: '', img: RV(5) }, { t: '회원분들 반응', style: 'tag', img: RV(6) } ] }]} />
    </Sequence>
    <Sequence from={HEAD + PROOF}><Scene paras={S47_TAIL} /></Sequence>
  </AbsoluteFill>
);

// ── S5 왜 지금 ──
const S5: Para[] = [
  { dur: 10.5, bg: RANK, tint: 'mono', hits: [
    { t: '"좋긴 한데…\n나도 될까?"', style: 'quote' }, { t: '"또 결제만 하고\n안 쓰는 거 아닐까?"', style: 'quote' }, { t: '"다음에 할까?"', style: 'quote' } ] },
  { dur: 11.045, bg: RANK, tint: 'mono', hits: [
    { t: '그 \'다음에\'가\n제자리에 두었다', style: 'mega', accent: '제자리' }, { t: '강의 하나 더\n후기 하나 더', style: 'stack' }, { t: '그사이 누군가는\n오늘도 올렸다', style: 'slam' } ] },
  { dur: 11.091, bg: SSUL, tint: 'amber', hits: [
    { t: '정보 싸움 ✕', style: 'slam' }, { t: '속도와\n꾸준함 싸움', style: 'mega', accent: '꾸준함' }, { t: '먼저 · 더 많이 올리는 사람이\n가져간다', style: 'kinetic', accent: '가져간다' } ] },
  { dur: 20.273, bg: CAPCUT, tint: 'red', hits: [
    { t: '계산해 보면', style: 'tag' }, { t: '손으로 영상 하나', style: 'count', num: 3, unit: '시간' }, { t: '하루 하나씩 한 달이면', style: 'count', num: 90, unit: '시간' },
    { t: '다들 2주 만에\n멈춥니다', style: 'slam' }, { t: '편집자?\n편집비가 먼저 나간다', style: 'kinetic', accent: '편집비' },
    { t: '시간을 사고\n기회로 바꾼다', style: 'mega', accent: '기회' } ] },
  { dur: 13.545, bg: RANK, tint: 'amber', hits: [
    { t: '숏템메이커가 하는 일', style: 'flow', steps: ['랭킹\n뭘 만들지', '파워검색\n제품', '대본은행\n말맛', '장면·효과\n자동'] },
    { t: '장면·효과음·짤·템플릿\n알아서', style: 'stack' }, { t: '고르고 · 확인하고 · 올린다', style: 'mega', accent: '올린다' } ] },
  { dur: 16.318, bg: MOM2, tint: 'monoWarm', hits: [
    { t: '"이 나이에\n늦지 않았나…"', style: 'quote' }, { t: '거꾸로입니다', style: 'mega' },
    { t: '', style: 'vs', vs: ['젊은 사람\n퇴근 후 1~2시간', '은퇴·육아 끝\n하루가 통째로'] }, { t: '시간 있는 사람이\n이긴다', style: 'mega', accent: '이긴다' } ] },
  { dur: 13.182, bg: CAT, tint: 'amber', hits: [
    { t: '쇼핑쇼츠 =\n물건 파는 일', style: 'slam' }, { t: '주방 · 청소 · 생활용품', style: 'tag' },
    { t: '살림 이삼십 년의 눈', style: 'mega', accent: '눈' } ] },
  { dur: 4.591, bg: CAT, tint: 'amber', hits: [{ t: '그 눈이\n그대로 실력', style: 'mega', accent: '실력' }] },
  { dur: 15.455, bg: CODE, tint: 'cyan', hits: [
    { t: '못 한 이유\n편집 · 컴퓨터', style: 'slam' }, { t: '숏템메이커가\n대신 합니다', style: 'mega', accent: '대신' },
    { t: '혼자 두지 않습니다', style: 'kinetic', accent: '혼자' }, { t: '막히면 1:1로 바로', style: 'tag' } ] },
  { dur: 9.092, bg: RANK, tint: 'amber', hits: [
    { t: '몇 번을 물어봐도\n눈치 볼 사람 없다', style: 'kinetic', accent: '눈치' }, { t: '그냥\n물어보세요', style: 'mega' } ] },
  { dur: 10.955, bg: SSUL, tint: 'amber', hits: [
    { t: '2기 정규 단톡방', style: 'mega' }, { t: '영상 · 노하우 · 새 기능 먼저', style: 'tag' }, { t: '혼자면 멈추고\n같이면 계속 간다', style: 'slam' } ] },
  { dur: 6.045, img: RV(1), hits: [
    { t: '1기도 똑같이\n"나도 될까?"', style: 'quote' }, { t: '지금은 직접\n만들고 올린다', style: 'tag', img: RV(5) } ] },
  { dur: 22.818, bg: RANK, tint: 'red', hits: [
    { t: '밥상은\n차려 놨습니다', style: 'mega', accent: '차려' }, { t: '실행하느냐\n마느냐', style: 'mega' },
    { t: '움직이지 않는다면?', style: 'slam' }, { t: '프로그램 문제가\n아닙니다', style: 'kinetic', accent: '아닙니다' },
    { t: '강의 ✕\n손에 쥐고 돌리는 도구', style: 'mega', accent: '도구' } ] },
];
export const V2_S5_FRAMES = sceneFrames(S5);
export const V2_S5: React.FC = () => <Scene voice="shottem2/v2s5/voice.mp3" paras={vary(S5, 15)} cap="15" />;

// ── S6 계속 진화 ──
const S6: Para[] = [
  { dur: 17.182, bg: CODE, tint: 'cyan', hits: [
    { t: '매일 진화하겠다', style: 'quote' }, { t: '약속 지킨 업데이트', style: 'count', num: 2478, unit: '번', sub: '59일' },
    { t: '계속 진화', style: 'flow', steps: ['V1', 'V2', 'V3'] }, { t: '방구석 불은\n오늘 밤에도 켜져 있다', style: 'kinetic', accent: '오늘 밤' } ] },
  { dur: 9.182, bg: CODE, tint: 'amber', hits: [
    { t: '오늘 기준\n내일 또 바뀐다', style: 'slam' }, { t: '바뀌는 모든 걸\n그대로', style: 'mega', accent: '그대로' } ] },
  { dur: 7.545, bg: RANK, tint: 'amber', hits: [
    { t: 'V3', style: 'mega', sub: 'NEXT' }, { t: '다음 자동화 프로그램\n제작 중', style: 'kinetic', accent: '제작 중' } ] },
];
export const V2_S6_FRAMES = sceneFrames(S6);
export const V2_S6: React.FC = () => <Scene voice="shottem2/v2s6/voice.mp3" paras={vary(S6, 16)} cap="16" />;

// ── S7 2기 모집 ──
const S7: Para[] = [
  { dur: 5.182, bg: SSUL, tint: 'amber', hits: [{ t: '숏템메이커 V2\n2기 모집', style: 'mega', accent: '2기 모집' }, { t: '참가비 88만 원', style: 'tag' }] },
  { dur: 15.182, bg: RANK, tint: 'amber', hits: [
    { t: '1기 중엔\n고액 강의 수강생도', style: 'slam' }, { t: '다른 프로그램\n쓰던 분도', style: 'slam' }, { t: '왜일까요?', style: 'mega' } ] },
  { dur: 17.727, bg: RANK, tint: 'red', hits: [
    { t: '3기부터\n가격 인상', style: 'mega', accent: '가격 인상' }, { t: '기능이 매일 늘어난다', style: 'tag' },
    { t: '가장 낮은 가격은\n지금', style: 'mega', accent: '지금' } ] },
  { dur: 2.0, bg: SSUL, tint: 'amber', hits: [{ t: '2기 분들께만', style: 'mega' }] },
  { dur: 6.227, bg: CODE, tint: 'amber', hits: [{ t: '1:1 채팅 지원', style: 'mega', sub: '첫째' }] },
  { dur: 7.045, bg: SSUL, tint: 'amber', hits: [{ t: '2기 정규 단톡방', style: 'mega', sub: '둘째' }] },
  { dur: 11.864, bg: CODE, tint: 'cyan', hits: [{ t: '다음 자동화\n체험단', style: 'mega', sub: '셋째' }, { t: '먼저 쓰고\n먼저 번다', style: 'slam' }] },
  { dur: 9.5, bg: INSTA, tint: 'amber', hits: [{ t: '챌린지 이벤트', style: 'mega', sub: '넷째' }, { t: '꾸준함을\n같이 지킨다', style: 'slam' }] },
  { dur: 6.0, bg: CODE, tint: 'amber', hits: [{ t: '매일 업데이트\n그대로', style: 'mega', sub: '다섯째' }] },
  { dur: 4.818, bg: RANK, tint: 'red', hits: [{ t: '닫히면 3기\n3기는 더 비쌉니다', style: 'mega', accent: '더 비쌉니다' }] },
];
export const V2_S7_FRAMES = sceneFrames(S7);
export const V2_S7: React.FC = () => <Scene voice="shottem2/v2s7/voice.mp3" paras={vary(S7, 17)} cap="17" />;

// ── S8 마지막 한마디 ──
const S8: Para[] = [
  { dur: 5.227, bg: RANK, tint: 'amber', hits: [{ t: '누군가에겐 기회', style: 'mega', accent: '기회' }, { t: '누군가에겐 광고', style: 'slam' }] },
  { dur: 15.091, bg: SSUL, tint: 'amber', hits: [
    { t: '한 달 뒤', style: 'mega' }, { t: '', style: 'vs', vs: ['미룬 사람\n"조금 더…"', '시작한 사람\n매일 쌓인 영상'] },
    { t: '하나가 터지면\n이야기가 달라진다', style: 'mega', accent: '달라진다' }, { t: '미룬 사람은\n여전히 "조금 더…"', style: 'slam' } ] },
  { dur: 23.5, bg: MOM, tint: 'monoWarm', hits: [
    { t: '5 · 60대 분들께', style: 'tag' }, { t: '자식 먼저\n가족 먼저\n회사 먼저', style: 'stack' },
    { t: '이제 한 번쯤은\n내 이름으로 된 일', style: 'mega', accent: '내 이름' },
    { t: '늦은 나이는 없다\n어려운 도구가 있었을 뿐', style: 'kinetic', accent: '도구' }, { t: '그래서\n쉽게 만들었습니다', style: 'mega', accent: '쉽게' } ] },
  { dur: 24.455, bg: MOM2, tint: 'amber', hits: [
    { t: '자녀분이라면', style: 'tag' }, { t: '부모님께\n이 영상 보내 드리세요', style: 'mega', accent: '보내' },
    { t: '"엄마도\n할 수 있대"', style: 'quote' }, { t: '돈 되는 방법과 도구\n누구보다 빨리', style: 'kinetic', accent: '빨리' },
    { t: '제가 드릴 수 있는\n선물', style: 'mega', accent: '선물' } ] },
  { dur: 6.545, bg: RANK, tint: 'amber', hits: [
    { t: '레퍼런스 하나만\n담아 보세요', style: 'mega', accent: '하나만' }, { t: '참여 방법 · 고정 댓글', style: 'tag' } ] },
];
export const V2_S8_FRAMES = sceneFrames(S8);
export const V2_S8: React.FC = () => <Scene voice="shottem2/v2s8/voice.mp3" paras={vary(S8, 18)} cap="18" />;
