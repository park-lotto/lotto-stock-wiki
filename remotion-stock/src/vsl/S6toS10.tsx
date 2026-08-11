/**
 * S6~S10 — 후반부 5씬. 촬영본이 하나도 없는 구간이라 화면을 전부 만든다.
 *
 * ★가장 중요한 발견(2026-08-11): **TTS 실제 발화가 대본과 다르다.**
 *   - S8 가격: 대본 "평생 소장 99만 원 / 다음 기수 200만 원"
 *              → 실제 녹음 "1기에서만 **1년에 77만 원**에 시작합니다 / 다음 기수부터는 이 가격 못 드립니다"
 *     대본을 믿고 99만 원을 화면에 박았으면 **음성과 가격이 다른 영상**이 나갈 뻔했다.
 *   - S8의 외주비 계산(3만원×30일=90만원) 구간은 녹음에 아예 없다 → 그 그래픽도 안 쓴다.
 *   - S10은 대본이 길지만 녹음은 6.19초 3문장뿐이다.
 *   자막·그래픽은 **whisper로 뜬 실제 발화**를 기준으로 짰다. 대본은 참고만 한다.
 *
 * 타이밍: s6 21.63s / s7 39.39s / s8 97.49s / s9 14.45s / s10 6.19s (전부 whisper 실측)
 */

import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';
import {
  BlackCard, Flash, ProgressBar, KineticWord, useKick, MINT, BG,
} from './motion';
import { RED } from './motion2';
import { BUILD } from './motion3';
import {
  Aura, DailyStream, Roadmap, WhoList, PriceReveal, PriceVersus,
  CtaCards, PointDown, PriceBadge, SeatsShrink, RichBed,
} from './motion4';

export const VSL_FPS_2 = 30;

type Body =
  | { m: 'black' }
  | { m: 'aura'; tone?: string }
  | { m: 'daily' }
  | { m: 'road'; appearAt: number[] }
  | { m: 'who'; lines: string[]; appearAt: number[] }
  | { m: 'price'; price: string; label: string; after?: string }
  | { m: 'versus' }
  | { m: 'cta'; appearAt: number[] }
  | { m: 'point'; label?: string }
  | { m: 'seats' }
  | { m: 'stat'; big: string; label: string; sub?: string };

type Sfx = { n: string; at: number; v?: number };
export type Cut2 = {
  text: string; d: number; big?: boolean; center?: boolean; sfx?: Sfx[]; badge?: boolean;
  /** 이 컷의 배경 정책. rich=완성 쇼츠가 흐르는 배경(S7·S8), 미지정=씬 기본값 */
  bed?: 'rich' | 'aura' | 'insta' | 'none';
} & Body;

const S = {
  whoosh: (at = 0, v = 0.30): Sfx => ({ n: 'whoosh.mp3', at, v }),
  boom: (at = 0, v = 0.30): Sfx => ({ n: 'boom.mp3', at, v }),
  punch: (at = 0, v = 0.38): Sfx => ({ n: 'punch.mp3', at, v }),
  click: (at = 0, v = 0.28): Sfx => ({ n: 'click.mp3', at, v }),
  ding: (at = 0, v = 0.32): Sfx => ({ n: 'ding.wav', at, v }),
  ding2: (at = 0, v = 0.22): Sfx => ({ n: 'ding2.mp3', at, v }),
  sub: (at = 0, v = 0.22): Sfx => ({ n: 'subpoint.mp3', at, v }),
  pop: (at = 0, v = 0.24): Sfx => ({ n: 'pop.wav', at, v }),
};

/* ══════════ S6 — 증거 + 실행은 본인 몫 (21.63s / 7세그먼트) ══════════
   밀어내는 화법이라 화면도 밀어낸다: 장식 최소, 암전 위주.
   마지막 두 컷만 '매일 갱신되는 제품'의 증거(실제 커밋 날짜)로 연다. */
export const S6_CUTS: Cut2[] = [
  { text: '여기까지, 제가 하나도 감추지 않고 |다 보여드렸습니다.|', d: 3.50, m: 'black', center: true, big: true,
    sfx: [S.boom(0, 0.26)] },
  { text: '이제는 본인이 실행하느냐, 마느냐… |딱 거기서 갈립니다.|', d: 3.74, m: 'aura',
    sfx: [S.whoosh(0)] },
  { text: '솔직히 말씀드리겠습니다.', d: 1.56, m: 'aura', center: true },
  { text: '이렇게까지 |밥상 다 차려드렸는데도| 안 하신다면…', d: 3.32, m: 'aura', center: true,
    sfx: [S.boom(0, 0.24)] },
  { text: 'SNS로 돈 버는 일은, 그냥 |안 하시는 걸 추천드립니다.|', d: 3.66, m: 'black', center: true, big: true,
    sfx: [S.boom(0, 0.36)] },
  { text: '그리고 아까 말씀드렸죠. 이 프로그램, |매일 업그레이드됩니다.|', d: 3.74, m: 'daily',
    sfx: [S.whoosh(0), S.pop(0.5, 0.2), S.pop(0.8, 0.18), S.pop(1.1, 0.16)] },
  { text: '|어제 없던 기능이, 오늘 생깁니다.|', d: 2.11, m: 'daily', big: true,
    sfx: [S.ding(0, 0.3)] },
];

/* ══════════ S7 — 확장 (39.39s / 13세그먼트) ══════════
   유일하게 '넓게' 가는 구간. 로드맵이 가로로 길게 뻗는다. */
const ROAD = [
  { label: '쇼핑쇼츠', when: '지금' },
  { label: '짤 쇼핑', when: '확장' },
  { label: '연예인 쇼핑', when: '확장' },
  { label: '네이버 클립', when: '곧', soon: true },
  { label: '쓰레드', when: '곧', soon: true },
];

export const S7_CUTS: Cut2[] = [
  { text: '지금은 |쇼핑쇼츠 시대|입니다.', d: 2.60, m: 'road', appearAt: [0.2, 99, 99, 99, 99],
    sfx: [S.ding2(0.1)] },
  { text: '이제 여기서, |절대 안 멈춥니다.|', d: 2.00, m: 'road', appearAt: [-1, 99, 99, 99, 99], big: true,
    sfx: [S.boom(0, 0.28)] },
  { text: '짤 쇼핑, 연예인 쇼핑. |계속 확장됩니다.|', d: 3.10, m: 'road', appearAt: [-1, 0.3, 1.2, 99, 99],
    sfx: [S.click(0.3), S.click(1.2)] },
  { text: '그리고 곧, |네이버 클립, 쓰레드.| 제일 핫한 플랫폼도 다 최적화해서 붙입니다.', d: 5.22, m: 'road',
    appearAt: [-1, -1, -1, 0.4, 1.5],
    sfx: [S.click(0.4), S.click(1.5), S.sub(3.0)] },
  { text: '저랑 같이, |사업을 계속 확장|하시는 겁니다.', d: 2.84, m: 'road', appearAt: [-1, -1, -1, -1, -1],
    sfx: [S.whoosh(0)] },
  { text: '지금 들어오신 분들껜, 새 프로그램이 나올 때마다 |큰 할인 혜택|을 드립니다.', d: 4.46, m: 'aura',
    sfx: [S.ding(0, 0.28)] },
  { text: '이 영상, 누군가에겐 |엄청난 기회|입니다.', d: 2.82, m: 'aura',
    sfx: [S.ding2(0.2)] },
  { text: '또 누군가에겐, 그냥 |흘려보낼 스팸|이고요.', d: 2.86, m: 'black', center: true,
    sfx: [S.boom(0, 0.22)] },
  { text: '이젠 |여러분의 선택|입니다.', d: 2.24, m: 'black', center: true, big: true,
    sfx: [S.boom(0, 0.30)] },
  { text: '근데 하나는 |약속드립니다.|', d: 1.58, m: 'aura', center: true, big: true,
    sfx: [S.ding(0, 0.30)] },
  { text: '저를 알게 된 이상, SNS에서 돈 되는 방법, 돈 되는 프로그램.', d: 4.28, m: 'aura' },
  { text: '|누구보다 빠르게, 누구보다 좋은 퀄리티로| 만나실 겁니다.', d: 3.30, m: 'aura', big: true,
    sfx: [S.sub(0.3)] },
  { text: '그게, 제가 드릴 수 있는 |기회이자 선물|입니다.', d: 2.59, m: 'aura', center: true,
    sfx: [S.ding(0, 0.34)] },
];

/* ══════════ S8 — 누가 쓰면 좋은가 + 오퍼 (97.49s / 25세그먼트) ══════════
   ★가격은 실제 녹음대로 "1년에 77만 원"이다(대본의 99만 원 평생 아님).
   가격 컷은 장식 금지 — 배경 거의 검정, 숫자만. */
export const S8_CUTS: Cut2[] = [
  { text: '이 말씀은 꼭 드리고 싶었습니다. 그동안 쇼핑쇼츠 만드느라 |고생하신 분들.|', d: 4.70, m: 'aura',
    sfx: [S.whoosh(0)] },
  { text: '', d: 4.36, m: 'who',
    lines: ['밤새 컷 붙이고', '자막 하나하나 지우고', '그러다 지쳐서 놓아버린 분들'],
    appearAt: [0.1, 1.5, 2.9],
    sfx: [S.click(0.1), S.click(1.5), S.click(2.9)] },
  { text: '저는 그분들이 이걸 쓰셨으면 합니다. 그 고생을 직접 해보신 분이, |이 가치를 제일 정확하게| 아실 테니까요.', d: 7.00, m: 'aura',
    sfx: [S.sub(2.6)] },
  { text: '그리고 아까 말씀드린 것… |왜 하필 육십 대 어머니| 기준이었냐.', d: 3.64, m: 'black', center: true, big: true,
    sfx: [S.boom(0, 0.28)] },
  { text: '컴퓨터 앞에서 |제일 먼저 포기하는 분|이, 우리 어머니였습니다.', d: 3.68, m: 'black', center: true },
  { text: '그분이 할 수 있으면, |누구나 할 수 있습니다.| 이미 첫 번째 테스터로 쉽게 하고 계시고요.', d: 5.14, m: 'aura',
    sfx: [S.ding(0, 0.28)] },
  { text: '그 기준으로 만들었기 때문에, 이 프로그램에는 |배워야 할 게 없습니다.|', d: 4.00, m: 'aura', big: true,
    sfx: [S.sub(1.4)] },
  { text: '프로그램 소문나기 전에, 초기에 빠르게 선점해서 |먼저 버셔야 합니다.|', d: 4.58, m: 'black', center: true,
    sfx: [S.boom(0, 0.22)] },
  { text: '그래서 며칠간… |1기, 딱 한정 인원만| 받습니다.', d: 3.36, m: 'seats',
    sfx: [S.punch(0.4, 0.34)] },
  { text: '저는, 실제로 실행하실 수 있는 |프로그램 키를 손에 쥐어드립니다.|', d: 4.00, m: 'aura',
    sfx: [S.ding(0, 0.3)] },
  { text: '그 많은 영상이랑 강의, 무료 유료 다 보면서 "이건 진짜 알짜다" 싶었던 것만, |이 안에 담았습니다.|', d: 6.64, m: 'aura',
    sfx: [S.sub(2.4)] },
  { text: '이제 유료 강의, |볼 필요 없습니다.|', d: 2.06, m: 'black', center: true, big: true,
    sfx: [S.boom(0, 0.3)] },
  { text: '1기로 들어오시면, 숏템메이커가 계속 만드는 |노하우 영상들도 계속| 드릴 예정입니다.', d: 5.76, m: 'aura',
    sfx: [S.ding2(0.3)] },
  { text: '그리고 하나, 부탁이 아니라 |말씀을 드리겠습니다.|', d: 2.86, m: 'black', center: true,
    sfx: [S.boom(0, 0.24)] },
  { text: '시중에 나온 프로그램들과 |굳이 비교하지 마십시오.|', d: 3.18, m: 'black', center: true, big: true },
  { text: '그 비교는, 제가 |이미 지겹도록 다 했습니다.|', d: 2.86, m: 'aura' },
  { text: '내 돈 주고 전부 사서 뜯어봤고, 구멍이 뻔히 보여서 |결국 제가 만든 겁니다.|', d: 5.16, m: 'aura',
    sfx: [S.sub(2.0)] },
  // ★가격 — 여기만 장식 금지
  { text: '', d: 3.08, m: 'price', price: '1년 77만 원', label: '1기에서만',
    sfx: [S.boom(0, 0.34)] },
  { text: '다음 기수부터는 |이 가격 못 드립니다.|', d: 2.28, m: 'price', price: '1년 77만 원', label: '1기에서만',
    after: '다음 기수부터는 이 가격 없음' },
  { text: '프로그램은 매일 좋아지는데, |가격이 그대로일 이유가 없습니다.|', d: 3.78, m: 'daily',
    sfx: [S.whoosh(0)] },
  { text: '그리고 1기 회원분들께는, 따로 준비하고 있는 |혜택이 있습니다.|', d: 3.86, m: 'aura',
    sfx: [S.ding(0, 0.28)] },
  { text: '그건 |방에서 직접| 말씀드리겠습니다.', d: 2.56, m: 'black', center: true },
  { text: '결제와 환불 규정은, 결제 페이지에 그대로 안내해 두었습니다.', d: 3.76, m: 'aura' },
  { text: '읽어보시고 |결정하십시오.|', d: 2.00, m: 'black', center: true, big: true },
  { text: '이번 모집 닫히면, |다음 기수까지 기다리셔야| 합니다.', d: 3.06, m: 'seats',
    sfx: [S.boom(0, 0.32)] },
];

/* ══════════ S9 — 챌린지 예고 (14.45s / 4세그먼트) ══════════ */
export const S9_CUTS: Cut2[] = [
  { text: '마지막으로, |챌린지 이벤트|를 진행할 예정입니다.', d: 3.14, m: 'aura', big: true,
    sfx: [S.ding(0, 0.34)] },
  { text: '1기 멤버 중 챌린지에 참여하시는 분들껜, |소정의 상금|을 지급해 드립니다.', d: 4.64, m: 'aura',
    sfx: [S.punch(0.5, 0.3)] },
  { text: '', d: 4.14, m: 'who',
    lines: ['인스타 · 유튜브에 매일', '백 일간 영상 올리고', '보상받는 겁니다'],
    appearAt: [0.1, 1.3, 2.6],
    sfx: [S.click(0.1), S.click(1.3), S.click(2.6)] },
  { text: '자세한 건 |단톡방에서 전부| 풀겠습니다.', d: 2.53, m: 'black', center: true,
    sfx: [S.boom(0, 0.26)] },
];

/* ══════════ S10 — CTA (6.19s / 3세그먼트) ══════════
   녹음이 6초뿐이라 화면도 군더더기 없이: 카드 두 장 → 화살표 → 끝. */
export const S10_CUTS: Cut2[] = [
  { text: '단톡방 주소는 |이 영상 고정 댓글|에 있습니다.', d: 3.08, m: 'cta', appearAt: [0.1, 1.4], badge: true,
    sfx: [S.ding(0, 0.32), S.click(1.4)] },
  { text: '|1기 모집|은 그 방에서만 진행합니다.', d: 2.56, m: 'point', label: '고정 댓글 확인', badge: true,
    sfx: [S.punch(0.2, 0.34)] },
  { text: '', d: 0.55, m: 'black', center: true },
];


/* ★'매일 업그레이드' 목록 — 내부 커밋 메시지를 그대로 띄우면 고객은 못 알아본다
   ("제작소 EDL빔 복구"가 무슨 말인가). 사장님이 준 기능 문구로 바꿨다.
   날짜는 실제 빌드가 있었던 날(buildStats 최근 커밋일)을 쓴다. */
const UPGRADES = [
  { d: '8월 11일', s: '샤오홍슈 바로 가져오기' },
  { d: '8월 11일', s: '레퍼런스 랭킹 대규모 업데이트' },
  { d: '8월 10일', s: '영상 길이 · 썸네일 자동 업데이트' },
  { d: '8월 10일', s: '대본 — 최상위 채널 흡수' },
  { d: '8월 9일', s: '역대 히트작 크롤링 시작' },
  { d: '8월 9일', s: '틱톡 랭킹 추가' },
  { d: '8월 7일', s: '발음 교정 사전 적용' },
];

/* ── 배경 선택기 ────────────────────────────────────────
   cut.bed가 'rich'면 완성 쇼츠가 흐르는 배경, 아니면 종전 오라.
   배경을 씬 파일 한 곳에서 정하게 해 두면 "이 컷만 왜 다르지"가 안 생긴다. */
const Bed: React.FC<{ cut: Cut2; def?: 'rich' | 'aura' | 'insta'; graphic?: boolean }> = ({
  cut, def = 'aura', graphic,
}) => {
  const use = cut.bed ?? def;
  if (use === 'insta') return <RichBed kind={graphic ? 'deep' : 'insta'} />;
  if (use !== 'rich') return <Aura strength={0.08} />;
  // 기획서 배정: 그래픽이 주인공인 컷은 BG3 딥필드(색만 남긴 바닥),
  // 말만 있는 컷은 BG1 워크벤치(우리 페이지) ↔ BG2 결과물 벽
  return <RichBed kind={graphic ? 'deep' : 'work'} />;
};

/* ── 렌더러 ─────────────────────────────────────────────── */
const CutView: React.FC<{ cut: Cut2; def?: 'rich' | 'aura' | 'insta'; centerAll?: boolean }> = ({
  cut, def, centerAll,
}) => {
  const { scale, flash } = useKick();
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // 가운데에 그래픽이 있는 컷 — 여기에 가운데 자막을 얹으면 겹친다(S7 12초 실측)
  const graphic = ['daily', 'road', 'who', 'cta', 'point', 'seats', 'versus', 'stat'].includes(cut.m);

  let body: React.ReactNode = null;
  switch (cut.m) {
    case 'black': body = <BlackCard />; break;
    case 'aura': body = <Bed cut={cut} def={def} graphic={graphic} />; break;
    case 'daily': body = <><Bed cut={cut} def={def} graphic={graphic} /><DailyStream items={UPGRADES} /></>; break;
    case 'road': body = <><Bed cut={cut} def={def} graphic={graphic} /><Roadmap items={ROAD} appearAt={cut.appearAt} /></>; break;
    case 'who': body = <><Bed cut={cut} def={def} graphic={graphic} /><WhoList lines={cut.lines} appearAt={cut.appearAt} /></>; break;
    case 'price': body = <PriceReveal price={cut.price} label={cut.label} after={cut.after} />; break;
    case 'versus': body = <><Aura strength={0.06} /><PriceVersus /></>; break;
    case 'cta': body = <><Bed cut={cut} def={def} graphic={graphic} /><CtaCards appearAt={cut.appearAt} /></>; break;
    case 'point': body = <><Bed cut={cut} def={def} graphic={graphic} /><PointDown label={cut.label} /></>; break;
    case 'seats': body = <><Bed cut={cut} def={def} graphic={graphic} /><SeatsShrink /></>; break;
  }

  // centerAll: 씬 전체를 가운데 자막으로 (S7·S8). 배경이 화면녹화라
  // 아래에 붙은 자막이 UI 위에 얹혀 읽기 나빴다 → 가운데가 항상 비어 있게 만든다.
  const centered = cut.center ?? (centerAll && !graphic);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>{body}</AbsoluteFill>
      {centered && cut.m !== 'price' && cut.text ? (
        // 가운데 자막용 보호막 — 글자 뒤만 눌러 배경은 살리고 가독성은 지킨다
        <AbsoluteFill style={{
          background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0.66) 0%, rgba(0,0,0,0.22) 46%, rgba(0,0,0,0) 68%)',
          pointerEvents: 'none',
        }} />
      ) : null}
      {!centered && cut.m !== 'price' && (
        <AbsoluteFill style={{
          background: 'linear-gradient(to top, rgba(0,0,0,0.82) 0%, rgba(0,0,0,0) 30%)',
          pointerEvents: 'none',
        }} />
      )}
      {cut.text ? <KineticWord text={cut.text} center={centered} size={cut.big ? 88 : 64} /> : null}
      {cut.badge ? <PriceBadge /> : null}
      <Flash v={flash * 0.7} />
      <ProgressBar p={frame / durationInFrames} />
      {(cut.sfx ?? []).map((s, i) => (
        <Sequence key={i} from={Math.round(s.at * VSL_FPS_2)} layout="none">
          <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.3} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

const makeScene = (
  cuts: Cut2[], audio: string, def?: 'rich' | 'aura' | 'insta', centerAll?: boolean,
): React.FC => () => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Audio src={staticFile(audio)} />
      {cuts.map((cut, i) => {
        const from = Math.round(at * VSL_FPS_2);
        at += cut.d;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.round(cut.d * VSL_FPS_2)}>
            <CutView cut={cut} def={def} centerAll={centerAll} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const frames = (cuts: Cut2[]) => Math.round(cuts.reduce((a, c) => a + c.d, 0) * VSL_FPS_2);

// S6도 가운데 자막 + 우리 페이지 배경. 'black' 컷만 예외로 검정을 지킨다(밀어내는 화법)
export const S6Proof = makeScene(S6_CUTS, 'vsl/s6.mp3', 'insta', true);
// S7·S8은 말이 무거운 구간이라 배경이 비면 슬라이드처럼 보인다 → 완성 쇼츠를 깔아 둔다.
export const S7Expand = makeScene(S7_CUTS, 'vsl/s7.mp3', 'rich', true);
export const S8Offer = makeScene(S8_CUTS, 'vsl/s8.mp3', 'insta', true);
// S9는 '영상 올리고 보상받는' 챌린지 — 결과물 벽이 그대로 증거다
export const S9Challenge = makeScene(S9_CUTS, 'vsl/s9.mp3', 'insta', true);
export const S10Cta = makeScene(S10_CUTS, 'vsl/s10.mp3');

export const S6_FRAMES = frames(S6_CUTS);
export const S7_FRAMES = frames(S7_CUTS);
export const S8_FRAMES = frames(S8_CUTS);
export const S9_FRAMES = frames(S9_CUTS);
export const S10_FRAMES = frames(S10_CUTS);
