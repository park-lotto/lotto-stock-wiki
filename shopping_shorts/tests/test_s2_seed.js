// 2단계 씨앗 오염 회귀 테스트 (2026-08-18)
//   사고: 담긴 영상은 카메라 5편인데 대본이 통째로 다이소 주방청소로 나왔다.
//   원인: _s2Hydrate가 drafts만 지우고 seed를 남겨(0순위-B 짝 어긋남),
//         s2RenderSeeds의 `!S2.seed` 가드에 걸려 새 AI PICK이 씨앗을 못 바꿨다.
//   실행: node shopping_shorts/tests/test_s2_seed.js   (PASS 12 / FAIL 0)
//   ⚠️ 수정 전 코드로 돌리면 [1][2]가 FAIL 해야 한다 — 그래야 이 테스트가 의미 있다.
const fs=require('fs');
const src=fs.readFileSync('shopping_shorts/static/produce.html','utf8');

// 두 함수 본문만 뽑아 실제로 실행한다(문자열 검사 아님 — 진짜 동작을 본다).
function grab(name, start){
  const i=src.indexOf(start); if(i<0) throw new Error('not found: '+name);
  let d=0,j=src.indexOf('{',i);
  for(let k=j;k<src.length;k++){
    if(src[k]==='{')d++; else if(src[k]==='}'){d--; if(d===0) return src.slice(i,k+1);}
  }
}
const fnHydrate=grab('_s2Hydrate','function _s2Hydrate(w){');
// s2RenderSeeds는 DOM을 쓰므로 씨앗 결정 부분만 재현
const seedLogic=(()=>{
  const a=src.indexOf('const _manualSeed');
  const b=src.indexOf('const cards=S2.seeds.map');
  return src.slice(a,b);
})();

let S2={seed:null,seeds:[],drafts:[],curDraft:0,picked:[],materials:null};
function _s2Reset(){ S2.drafts=[]; S2.curDraft=0; S2.picked=[]; S2.materials=null; S2.seed=null; }
eval(fnHydrate);

function renderSeedsCore(aiPick){
  S2.seeds=[];
  if(aiPick && aiPick.pick_id){
    const pm=aiPick.pick_meta||{};
    S2.seeds.push({shortcode:aiPick.pick_id,title:pm.title||'선택 영상',text:aiPick.pick_text||'',structure:{},tiles:{},pick:true});
  }
  eval(seedLogic);
}

let pass=0,fail=0;
const t=(name,cond)=>{ if(cond){pass++;console.log('  PASS',name);} else {fail++;console.log('  FAIL',name);} };

console.log('\n[1] 실제 사고 재현 — 옛 홈데코랩 씨앗 + 새 카메라 작업');
S2={seed:null,seeds:[],drafts:[],curDraft:0,picked:[],materials:null};
// 옛 작업 복원(다이소 대본 + 홈데코랩 씨앗)
_s2Hydrate({s2:{drafts:[{style_name:'물건 발견형'}],curDraft:0,picked:[54,53],
  materials:{}, seed:{shortcode:'DbmCnyTTobw',title:'홈데코랩'}}});
t('옛 작업에서 씨앗 복원됨', S2.seed && S2.seed.shortcode==='DbmCnyTTobw');
// 새 작업으로 갈아탐 — drafts 없음
_s2Hydrate({s2:null});
t('★새 작업 진입 시 씨앗이 지워진다', S2.seed===null);
t('  drafts도 비었다', S2.drafts.length===0);
// 새 AI PICK(카메라)이 들어옴
renderSeedsCore({pick_id:'grab_instagram_ecf1cf902047',pick_meta:{title:'Video by eoseo_shop'},pick_text:'고독스 투명 필름 카메라'});
t('★씨앗이 카메라로 정해진다', S2.seed.shortcode==='grab_instagram_ecf1cf902047');
t('  홈데코랩이 아니다', S2.seed.shortcode!=='DbmCnyTTobw');

console.log('\n[2] 같은 작업에서 1단계 영상을 바꾼 경우');
renderSeedsCore({pick_id:'DcFIDH9pURp',pick_meta:{title:'유어테리어'},pick_text:'카메라2'});
t('★새 AI PICK을 따라간다', S2.seed.shortcode==='DcFIDH9pURp');

console.log('\n[3] 회귀 — 직접 쓴 대본은 지켜져야 한다');
S2.seed={shortcode:'',title:'직접 쓴 대본',text:'내가 쓴 것'};
renderSeedsCore({pick_id:'grab_instagram_498df25fb6c6',pick_meta:{title:'today.s_page'},pick_text:'x'});
t('★직접 쓴 대본을 AI PICK이 안 덮는다', S2.seed.title==='직접 쓴 대본');

console.log('\n[4] 회귀 — 작업을 이어서 열면 대본·씨앗이 살아난다');
S2={seed:null,seeds:[],drafts:[],curDraft:0,picked:[],materials:null};
_s2Hydrate({s2:{drafts:[{style_name:'A'},{style_name:'B'}],curDraft:1,picked:[54],
  materials:{sources:[]}, seed:{shortcode:'cam1',title:'카메라'}}});
t('대본 2안 복원', S2.drafts.length===2);
t('보던 탭 복원', S2.curDraft===1);
t('★씨앗도 복원', S2.seed && S2.seed.shortcode==='cam1');
// 같은 씨앗의 AI PICK이 다시 와도 그대로
renderSeedsCore({pick_id:'cam1',pick_meta:{title:'카메라'},pick_text:'y'});
t('같은 영상이면 씨앗 유지', S2.seed.shortcode==='cam1');

console.log('\n[5] 회귀 — AI PICK이 아직 없을 때(분석 중)');
S2={seed:null,seeds:[],drafts:[],curDraft:0,picked:[],materials:null};
renderSeedsCore(null);
t('빈 AI PICK에 안 터진다', S2.seed===null && S2.seeds.length===0);

console.log('\n결과: PASS '+pass+' / FAIL '+fail);
process.exit(fail?1:0);
