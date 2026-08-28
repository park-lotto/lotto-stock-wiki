// produce.html의 5단계 대본수정 로직을 파일에서 떼어 실제 응답 모양으로 검증
const fs=require('fs');
const h=fs.readFileSync('shopping_shorts/static/produce.html','utf8');

let fail=0;
const t=(label,cond,extra)=>{ if(!cond) fail++;
  console.log((cond?'  OK  ':'  FAIL')+' '+label+(extra?('  → '+extra):'')); };

// ① 3단계와 같은 저장구멍을 쓰는가 (0순위-B: 새 API를 만들면 규칙이 두 벌이 된다)
const api = /\/api\/mix\/scene_lab\/'\+MIX_JOB\+'\/narration\/'\+b\.beat_idx/.test(h);
t('3단계와 같은 API를 쓴다', api);

// ② 자막을 JS에서 다시 나누지 않는가 (2026-08-20 초 두 벌 사고 방지)
const seg = /vpSaveNarr[\s\S]{0,2600}?cap_durs\s*=/.test(h);
t('자막 타이밍을 화면에서 계산하지 않는다', !seg);

// ③ 편집 중 목록 재그리기를 막는가 (입력 날아감 방지)
t('편집 중엔 renderTtsBeats가 멈춘다',
  /async function renderTtsBeats\(\)\{\s*\n\s*if\(vpIsEditing\(\)\) return;/.test(h));

// ④ 409(생성 중) 처리
t('생성 중 409를 안내한다', /r\.status===409[\s\S]{0,120}생성 중엔 못 바꿔요/.test(h));

// ⑤ unchanged 응답 처리 (서버가 "바뀐 글자 없음"을 줄 때)
t('unchanged 응답을 헛되이 기다리지 않는다', /j\.unchanged\s*&&\s*!j\.regen/.test(h));

// ⑥ 완료 감지를 tts_ver로 하는가 (mp3 경로가 같아 겉으론 구분 불가)
t('tts_ver 폴링으로 완료를 안다', /vpSaveNarr[\s\S]{0,2600}?tts_ver\|\|0\)>prevVer/.test(h));

// ⑦ 타임아웃이 있는가 (영원히 도는 폴러 금지)
t('60초 타임아웃이 있다', /vpSaveNarr[\s\S]{0,2600}?started>60000/.test(h));

// ⑧ 빈 대본 방어
t('빈 대본은 저장하지 않는다', /if\(!text\)\{[^}]*비었어요/.test(h));

// ⑨ 값을 innerHTML이 아니라 value로 넣는가 (따옴표·꺾쇠 든 대본이 깨지지 않게)
t('대본을 value로 주입한다(이스케이프 사고 방지)', /ed\.value=cur;/.test(h));

// ⑩ 버튼이 실제로 화면에 붙었는가
t('✏ 대본수정 버튼이 목록에 있다', /onclick="vpEditNarr\(\$\{i\}\)"/.test(h));

console.log(fail? ('\n★ 실패 '+fail+'건') : '\n전부 통과');
process.exit(fail?1:0);
