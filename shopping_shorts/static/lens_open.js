// 나라별 검색어로 6곳(샤오홍슈·도우인·틱톡·인스타·핀터레스트·유튜브)을 여는 판단의 주인(2026-10-15 관제 209).
// 숏템파워(index.html)와 3단계 장면 찾기(scene_find.js)가 **같이 부른다** — 종전엔 index.html 안에만 있어
// 3단계가 쓰려면 베껴야 했다(같은 판단 두 벌 금지, 0순위-B). 시험: tests/test_lens_cn_js.py 가 이 파일을 통째로 돌린다.
const _LENS_AUTO_LANG = {xiaohongshu:'zh', douyin:'zh', pinterest:'en', tiktok:'en', instagram:'en', youtube:'en'};

function _lensKwFor(c, platform, lang){
  // 고른 언어의 검색어. 없으면 ''을 돌려 **버튼을 아예 안 그린다** —
  // 빈 검색어로 사이트를 열면 엉뚱한 홈으로 떨어진다(기존 규약과 같다).
  const L = (lang && lang !== 'auto') ? lang : (_LENS_AUTO_LANG[platform] || 'ko');
  // ★인스타는 러시아어 검색어에 결과를 안 준다(2026-09-14 실측: 'чехол Марио' 2단어도 0건).
  //   러시아어를 골랐어도 인스타 버튼만은 영어 검색어로 연다.
  if (platform === 'instagram' && L === 'ru' && c && (c.en || '').trim()) return c.en.trim();
  // ★핀터레스트는 영어가 아니면 사실상 안 나온다(2026-09-26 앱 크롤러로 실측, 영상탭 건수):
  //   'オープンイヤーイヤホン' 0 · 'ランニング用イヤホン' 0 · '倍思耳机' 0 · '베이스어스 이어폰' 0
  //   vs 'open ear earbuds' 25 · 'running earbuds' 25 · 'Baseus earbuds' 22.
  //   그래서 어느 언어를 골라도 핀터레스트만은 영어 검색어로 연다(영어가 없으면 고른 언어 그대로).
  if (platform === 'pinterest' && c && (c.en || '').trim()) return c.en.trim();
  return ((c && c[L]) || '').trim();
}
const _LENS_OPEN_ALL = ['xiaohongshu', 'douyin', 'tiktok', 'instagram', 'pinterest', 'youtube'];

function _lensSearchUrl(platform, kw){
  if(platform==='instagram') kw=_igKw(kw);
  if(platform==='pinterest') kw=_pinKw(kw);
  const q=encodeURIComponent(kw||'');
  const B={
    tiktok:`https://www.tiktok.com/search?q=${q}`,
    instagram:`https://www.instagram.com/explore/search/keyword/?q=${q}`,
    xiaohongshu:`https://www.xiaohongshu.com/search_result?keyword=${q}`,
    douyin:`https://www.douyin.com/search/${q}`,
    // 유튜브(2026-09-08) — 영어·일본어 검색어로 해외 원본을 찾을 때 쓴다.
    // &sp=EgIQCQ%253D%253D = Shorts 전용(관제 156 — 4분 미만 필터 EgIYAQ는 일반 영상이 섞였다: 실측 Shorts 31·일반 14 → 31·0).
    youtube:`https://www.youtube.com/results?search_query=${q}&sp=EgIQCQ%253D%253D`,
    // 핀터레스트 영상탭(2026-09-08) — 언어 격자에서 빠져 있었다.
    pinterest:`https://www.pinterest.com/search/videos/?q=${q}`,
  };
  return B[platform]||'#';
}
function _igKw(kw){
  // 인스타 검색어 다듬기(2026-08-03). 인스타 키워드 검색은 '만들기·하는 법' 같은
  // 동사꼬리가 붙은 긴 구문에 극단적으로 약하다(사장님 실측: '한국식 김밥 만들기' 0건,
  // '김밥'류는 왕창). 꼬리(만들기/싸는 법/방법/레시피/꿀팁…)와 부사(맛있게/쉽게…)를
  // 떼어 명사 중심으로 줄인다. 틱톡·중국앱은 구문 검색이 되므로 그대로 둔다.
  // ⚠️ 위치: test_lens_cn_js가 _lensSearchUrl~renderLens 구간을 잘라 node로 돌리므로
  // 이 함수는 그 구간 안에 있어야 한다(호이스팅으로 호출 순서는 무관).
  let s=String(kw||'').trim();
  const tails=/(만들기|만드는\s*법|싸는\s*법|하는\s*법|먹는\s*법|방법|레시피|꿀팁|비법|조합|추천|사용법|사용기|후기|리뷰|언박싱|개봉기|체험|비교|정리|모음)$/;
  const advs=/(맛있게|쉽게|간단하게|예쁘게|빠르게|완벽하게|감성)$/;
  for(let i=0;i<3;i++){ s=s.replace(tails,'').trim(); s=s.replace(advs,'').trim(); }
  // ★3어절 이상이면 '첫 어절 + 마지막 어절'만 남긴다 (2026-08-16 실측).
  //   인스타 검색은 **사람들이 실제로 쓰는 말**에만 반응한다 — 길이 문제가 아니라
  //   '지어낸 조합'이 문제다. 라이브 인스타에서 직접 세어본 결과:
  //     고독스 아동용 카메라 0 → 고독스 카메라 18 / 고독스 토이 카메라 0 → 고독스 카메라 18
  //     아이 장난감 카메라 0 → 아이 카메라 15 / 어린이 사진 촬영은 원래 18
  //   (가운데 수식어가 '지어낸' 부분이라 그걸 떨어뜨리는 게 가장 잘 맞았다: 4/5)
  // ★한글이 없는 검색어(영어·일본어 띄어쓰기 등)는 규칙이 다르다(2026-09-14 라이브 인스타 실측).
  //   'Mario phone case'(3)·'Super Mario phone case'(4) 결과 있음 / 5단어부터 전부 0건
  //   ('Mario phone case with stand'·'cute character phone case aesthetic'·
  //    'Super Mario 3D stand phone case'). 영어는 핵심 명사가 **뒤**에 오므로
  //   위 한국어식 '첫+끝'을 쓰면 잘 나오던 'Mario phone case'가 'Mario case'로 망가졌다.
  //   → 연결어(with/for…)만 빼고, 그래도 5단어 이상이면 **뒤 4단어**만 남긴다.
  if(!/[가-힣]/.test(s)){
    let w=s.split(/\s+/).filter(Boolean);
    if(w.length>=5) w=w.filter(x=>!/^(with|for|and|the|a|an|of|to|in|on|at|by|from)$/i.test(x));
    if(w.length>=5) w=w.slice(-4);
    return w.join(' ')||String(kw||'').trim();
  }
  const t=s.split(/\s+/).filter(Boolean);
  if(t.length>=3) s=t[0]+' '+t[t.length-1];
  return s||String(kw||'').trim();
}
// 핀터레스트 검색어 줄이기(2026-09-26 사장님 "길어서 그런지 안 나온다"). 앱 크롤러로 센 영상탭 건수:
//   'Baseus open ear headphones' 3 → 'Baseus headphones' 22 · 'Baseus open ear' 9
//   'earbuds that don't fall out while running' 1 → 'earbuds' 25
//   'comfortable open ear headphones for running' 0 → 'comfortable headphones' 25
//   'affordable sports earbuds review' 4 → 'affordable sports earbuds'(3단어는 흔한 말이면 25)
// 규칙: 연결어(that/for/while…)부터 뒤를 자르고, 꼬리(review…)를 떼고, 4단어 이상이면 아래처럼 줄인다.
//   3단어 이하는 그대로 둔다(흔한 말이면 25건).
function _pinKw(kw){
  const raw=String(kw||'').trim();
  if(/[가-힣぀-ヿ一-鿿]/.test(raw)) return raw;   // 영어 아닌 건 손대지 않는다
  let w=raw.split(/\s+/).filter(Boolean);
  const cut=w.findIndex((x,i)=>i>0 && /^(that|which|for|with|while|when|to|without|in|on)$/i.test(x));
  if(cut>0) w=w.slice(0,cut);
  while(w.length>1 && /^(review|reviews|unboxing|haul|recommendation|recommended|test|comparison|tips|hack|hacks)$/i.test(w[w.length-1])) w.pop();
  if(w.length>=4){
    // 대문자로 시작하는 앞 단어 = 브랜드(최대 2개: 'Super Mario'). 브랜드+끝 명사만 남긴다.
    //   실측: Godox kids digital camera 0 → Godox camera 25 / Xiaomi portable electric fan 1 → Xiaomi fan 25
    //         Dyson cordless hair dryer 7 → Dyson dryer 25
    // 브랜드가 없으면 뒤 3단어(영어는 핵심 명사가 뒤에 온다): comfortable open ear headphones → open ear headphones 25
    // ★브랜드 없는 말을 첫+끝으로 자르면 'super mario phone case'가 'super case'가 된다 — 건수(22)는 나와도 엉뚱한 영상이다.
    let n=0; while(n<2 && n<w.length-1 && /^[A-Z]/.test(w[n])) n++;
    w = n ? w.slice(0,n).concat(w[w.length-1]) : w.slice(-3);
  }
  return w.join(' ')||raw;
}
// 그래도 0건인 2어절(브랜드+합성어)을 위한 마지막 안전망 — 핵심 명사 한 단어.
// 실측: '고독스 픽스플레이' 0 → 픽스플레이 13 / '고독스 뷰파인더' 0 → 뷰파인더 15
//       '감성 키즈카메라' 0 → 키즈카메라 15. 3전 3승이라 버튼 하나를 더 둔다.
function _igShortKw(kw){
  const t=_igKw(kw).split(/\s+/).filter(Boolean);
  return t.length>=2 ? t[t.length-1] : '';
}
// 인스타 결과가 '0건이거나 왕창이거나'로 튀는 이유를 화면에서 갈라 보여준다(2026-08-14).
// 서버 diag가 세어준다: 렌즈 원본에 인스타 링크가 몇 개였나(ig_raw), 그중 개별 게시물이
// 아니라 프로필·검색페이지라 입구에서 잘린 게 몇 개(ig_dropped_not_post), 카드뉴스(/p/)가
// 몇 개(ig_photo). 0건일 때 "렌즈가 안 물어왔다" vs "우리가 걸렀다"가 구분된다.
// ⚠️ 위치: test_lens_cn_js가 _lensSearchUrl~renderLens 구간만 잘라 node로 돌리므로
// renderLens가 부르는 이 함수는 그 구간 안에 있어야 한다.
function _openUrl(u){ return String(u||'').replace(/:\/\/(www\.)?xiaohongshu\.com/i,'://www.rednote.com'); }

// 검색어 후보 하나(c = {ko, zh, en, ja, ru})·언어(auto|ko|zh|en|ja|ru) → 새 탭으로 열 [{k, url}] (샤오홍슈는 rednote 주소).
function lensOpenTargets(c, lang){
  const L = lang || 'auto';
  return _LENS_OPEN_ALL
    .map(k => { const q = _lensKwFor(c, k, L); if (!q) return null;
      const u = _lensSearchUrl(k, q); return {k, url: k === 'xiaohongshu' ? _openUrl(u) : u}; })
    .filter(Boolean);
}
