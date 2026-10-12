import React from 'react';
import { Scene, Para, sceneFrames } from './V2_Engine';

/* S2 · 당신은 어디쯤 계십니까 — 문제 구간이라 흑백 톤. 문단 길이 = 필재 TTS 실측 */
const A = (n: string) => 'shottem2/v2s2/' + n;
const RANK = 'shottem2/bg/bg_랭킹스크롤.mp4';
const CODE = 'shottem2/bg/bg_코드터미널.mp4';
const CAPCUT = 'shottem2/bg/bg_캡컷타임라인.mp4';

const P: Para[] = [
  { dur: 3.955, back: 'hero', bg: A('search.mp4'), tint: 'mono', hits: [{ t: '지금 부업,\n찾고 계시죠?', style: 'mega', accent: '부업' }] },
  { dur: 13.637, bg: A('search.mp4'), frame: 'screen', tint: 'mono', hits: [
    { t: '직장인 · 퇴근하고', style: 'tag' }, { t: '주부 · 아이 재우고', style: 'tag' },
    { t: '시니어 · 은퇴하고', style: 'tag' }, { t: '"쉽다.\n누구나 한다."', style: 'quote' } ] },
  { dur: 14.727, bg: A('senior.mp4'), frame: 'screen', tint: 'mono', hits: [
    { t: '시니어 롱폼', style: 'tag' }, { t: '야담 롱폼', style: 'tag' },
    { t: '시간은 엄청 걸리고', style: 'kinetic', accent: '엄청' }, { t: '채널 정지 · 규제', style: 'neon' } ] },
  { dur: 18.364, back: 'split', seed: 11, tint: 'mono', hits: [
    { t: '그럼 쇼츠?', style: 'slam' }, { t: '쇼츠는\n마라톤', style: 'mega' },
    { t: '매일 해야 하는데\n그게 지옥', style: 'kinetic', accent: '지옥' },
    { t: '매일 이걸 반복', style: 'flow', steps: ['기획', '영상 찾기', '대본', '편집'] }, { t: '하루 종일 붙잡아도\n한 개', style: 'slam' } ] },
  { dur: 6.727, back: 'wall', seed: 2, tint: 'monoWarm', hits: [
    { t: '그래서 결국\n쇼핑쇼츠', style: 'mega' }, { t: '얼굴 X · 링크만', style: 'tag' } ] },
  { dur: 12.682, bg: A('yadam.mp4'), frame: 'screen', tint: 'mono', hits: [
    { t: '"복붙만\n하면 된다"', style: 'quote' }, { t: '"자세한 건\n유료 강의에서"', style: 'quote' },
    { t: '제일 비싼 강의까지\n제 돈 내고', style: 'kinetic', accent: '제 돈' } ] },
  { dur: 18.273, back: 'mosaic', seed: 6, tint: 'mono', hits: [
    { t: '열어 보면?', style: 'slam' }, { t: '뻔한 얘기\n그리고 노가다', style: 'stack' },
    { t: '"결국은\n본인 역량"', style: 'quote' }, { t: '비밀은\n없었다', style: 'mega' },
    { t: '찾고 · 쓰고 · 지우고 · 입히고\n전부 내 몫', style: 'kinetic', accent: '전부' } ] },
  { dur: 26.545, back: 'ring', seed: 4, tint: 'mono', hits: [
    { t: '5 · 60대 분들', style: 'mega' }, { t: '멈추고 · 돌려 보고\n또 멈추고', style: 'kinetic', accent: '또' },
    { t: '프롬프트\n렌더링\n키프레임\n템플릿', style: 'stack' }, { t: '"엄마, 아까\n알려 줬잖아"', style: 'quote' },
    { t: '그래서 더는\n안 묻게 되죠', style: 'slam' }, { t: '"내 나이에\n욕심이었나"', style: 'quote' } ] },
  { dur: 34.727, back: 'hero', seed: 13, tint: 'monoWarm', hits: [
    { t: '아닙니다', style: 'mega' }, { t: '나이 탓이\n아닙니다', style: 'slam' },
    { t: '도구가\n젊은 사람 기준', style: 'kinetic', accent: '젊은' }, { t: '따라갈 수 없게\n만든 것', style: 'mega' },
    { t: '"딸깍 한 번이면 끝"', style: 'quote' }, { t: '퀄리티\n나오던가요?', style: 'slam' },
    { t: '같은 틀 · 같은 목소리\n같은 자막', style: 'stack' }, { t: '양산형', style: 'neon' } ] },
  { dur: 17.227, back: 'split', seed: 8, tint: 'mono', hits: [
    { t: '개발자 입장에서', style: 'tag' }, { t: '직접 결제해서\n뜯어봤습니다', style: 'kinetic', accent: '뜯어봤습니다' },
    { t: '전부\n구멍', style: 'mega' }, { t: '퀄리티 나오는 건\n손에 꼽습니다', style: 'slam' } ] },
  { dur: 7.864, back: 'mosaic', seed: 9, tint: 'mono', hits: [
    { t: 'AI는\n마법봉이 아닙니다', style: 'mega', accent: '마법봉' } ] },
  { dur: 5.545, back: 'aurora', seed: 3, tint: 'none', hits: [
    { t: '뭘 만들지 모르고', style: 'slam' }, { t: '너무 오래 걸리고', style: 'slam' }, { t: '남들과 똑같다', style: 'mega' } ] },
  { dur: 3.864, back: 'ring', seed: 7, tint: 'amber', hits: [{ t: '이제\n답을 보실 차례', style: 'mega', accent: '답' }] },
];

export const V2_S2_FRAMES = sceneFrames(P);
export const V2_S2: React.FC = () => <Scene voice={A('voice.mp3')} paras={P} cap="01" />;
