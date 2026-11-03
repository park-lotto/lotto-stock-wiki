import json
from pathlib import Path

D = Path('C:/t/jev')
Q = {
 "01_font": {
  "problem": "회원이 설정 화면 글꼴 'PretendardXBold' 를 고르면 다시 만들기가 'StyleError: 회원 제목 글꼴 파일이 없다'로 멈춤(한정수)",
  "facts": ["설정 화면 글꼴 목록은 out/scene-style-ui-showcase.html 의 @font-face font-family 이름 88개를 뽑았다",
            "렌더(styles.member_font_file)는 static/fonts/{이름}.ttf|otf 를 찾았다 — 88개 중 70개가 파일 이름과 달라 실패(실측)",
            "같은 html @font-face src 에 실제 파일 경로가 있다(예 w2/Pretendard-ExtraBold.woff2), 같은 이름 otf 가 fonts 폴더에 있다",
            "PIL ImageFont.truetype 은 woff2 를 읽는다(실측 1042_Tenada.woff2 getlength 105)"],
  "causes": ["화면 이름→파일 판단이 두 곳(목록=family 이름, 렌더=파일 이름 짐작)에 따로 있어 어긋났다",
             "회원이 잘못된 글꼴을 골랐다", "글꼴 파일이 설치본에 빠졌다"],
  "fixes": ["@font-face src 를 읽는 함수 하나(preview_request.font_files)를 만들어 목록·렌더 둘 다 그것을 부르게 한다(87개 전부 렌더 확인)",
            "member_font_file 에 이름 바꾸기 표(XBold→-ExtraBold 등)를 덧붙인다", "목록에서 파일이 없는 이름을 손으로 지운다"]},
 "02_autoblur_stale": {
  "problem": "회원이 새 VMake 키를 넣었는데 다시 돌려도 VMake 를 부르지 않고 흐림으로 완성(한정수)",
  "facts": ["옛 키 실패 때 관문④ autoblur 가 박힌 글자 자리에 흐림 칸을 재료.json blur 에 넣었다",
            "관문④는 흐림에 덮인 글자를 남의 글자로 세지 않는다(blur_cover>TEXT_BLUR_MAX → foreign_text False)",
            "그래서 새 키로 지우는 판이 되어도 '지울 컷'이 0개였다"],
  "causes": ["코드가 넣은 흐림 칸이 표시 없이 재료에 남아, 지우기가 가능해진 뒤에도 글자를 가려 지울 컷이 0이 됐다",
             "새 키가 틀렸다", "VMake 서버 장애"],
  "fixes": ["코드가 넣은 흐림은 blur_auto 로 표시하고, 지울 수 있으면(그리고 매 바퀴) 그 칸만 걷고 다시 잰다(손 흐림은 그대로)",
            "새 키를 넣으면 재료.json blur 를 통째로 지운다", "회원에게 흐림 칸을 손으로 지우라고 안내만 한다"]},
 "03_blur_area": {
  "problem": "렌더가 '흐림이 화면의 41~75%(상한 15%)'로 같은 원인 3번 멈춤(강태경)",
  "facts": ["관문④ autoblur 가 바퀴마다 흐림 칸을 재료.blur 에 더하고 지우지 않았다(쌓임)",
            "blur_cut_gate 는 흐림 칸 넓이를 단순 합으로 셌다 — 같은 자리 칸 두 개를 두 배로 셈"],
  "causes": ["흐림 칸이 바퀴마다 쌓이고 면적을 겹침 없이 더해 실제보다 크게 셌다", "원본 영상에 글자가 정말 화면 75%를 덮었다", "상한 15%가 너무 낮다"],
  "fixes": ["코드 흐림은 바퀴마다 걷고 다시 정하고, 면적은 겹친 칸을 한 번만 세는 합집합 넓이로", "상한을 50%로 올린다", "흐림 면적 관문을 경고로 내린다"]},
 "04_lines_dropped": {
  "problem": "장면 검수에서 보낸 대본줄(L2) 바꿈이 반영 안 돼 화면은 새 컷·자막과 목소리는 옛 문장(강태경·이용재)",
  "facts": ["flow._apply_lines 는 대본 검사 미달이면 로그만 남기고 None 을 돌려준다",
            "ph_plan_look 은 None 이면 아무 말 없이 재료 답만 받고 진행했다"],
  "causes": ["반영 못 한 대본줄을 조용히 버려 회원 Claude 가 몰랐다", "회원 Claude 가 줄 id 를 잘못 적었다", "대본 검사가 너무 엄하다"],
  "fixes": ["버리지 않고 검사 미달 이유와 함께 되묻는다(편당 2번, 장면 검수·완성본 고치기 같은 함수 _lines_reask)", "대본 검사를 건너뛰고 그대로 넣는다", "재료 답이 오면 대본줄을 무시한다고 안내한다"]},
 "05_eleven_free": {
  "problem": "일레븐랩스 키 회원이 장면 맞추기에서 402 payment_required 'Free users cannot use library voices via the API' 로 멈춤, 시작 점검은 통과했었다(윤상길)",
  "facts": ["점검(selftest.testVoice)은 일레븐이면 키 유무만 봤다", "회원 키 GET /v1/user/subscription tier=free(회원 PC 실측)", "기본 성우 미나 = 공유 라이브러리 목소리"],
  "causes": ["점검이 요금제·목소리 종류를 안 봐서 무료 키+공유 목소리를 제작 중에야 알았다", "일레븐 서버 장애", "크레딧 부족"],
  "fixes": ["점검이 요금제와 고른 목소리 종류를 조회(돈 0)해 무료+공유 목소리면 시작 전에 알리고, 오류 문구를 '무료 요금제'로", "목소리를 자동으로 다른 회사로 바꾼다", "점검에서 실제 합성을 한 번 해 본다"]},
 "06_flowbusy": {
  "problem": "벤치마킹이 '지금 만드는 편이 있습니다'로 3번 막힘, 목록엔 진행 중 0(강태경)",
  "facts": ["cancelFlow 는 f.cancelled=true 만 두고 status 는 그대로(review 등)", "anyFlowBusy 는 status execute/review 만 봤다"],
  "causes": ["멈춘 편의 남은 status 를 바쁜 편으로 셌다", "다른 창 프로그램이 정말 돌고 있었다", "프리셋 빌림이 안 돌아왔다"],
  "fixes": ["flowBusy 한 함수: 멈춘 편은 실행기가 끝나는 중(busy)일 때만 센다", "벤치마킹에서 바쁨 검사를 뺀다", "회원에게 창을 다시 열라고 안내만"]},
 "07_ocr_twice": {
  "problem": "느린 PC 에서 렌더 전 관문④ 글자 검사가 1시간 40분(이용재)",
  "facts": ["cut_content_feats 는 흐림을 입힌 프레임으로 OCR 했고 OCR 캐시 열쇠에 흐림 칸이 들어 있었다",
            "흐림 칸이 하나 늘면 같은 원본의 모든 컷 프레임을 다시 OCR 했다(cut_ocr.json 이 계속 늘어남)",
            "흐림 덮임은 이미 상자 좌표(blur_cover)로 따로 판정한다 · 흐린 글도 검출기는 글로 본다(표본 08)"],
  "causes": ["흐림이 바뀔 때마다 같은 프레임을 다시 OCR 하는 중복 계산", "PC 가 느려서", "OCR 모델이 무겁다"],
  "fixes": ["프레임·OCR 은 흐림 없이 한 번만, 흐림은 좌표로만 판정", "OCR 모델을 가벼운 것으로 바꾼다", "느린 PC 는 글자 검사를 건너뛴다"]},
 "08_reloc_reuse": {
  "problem": "회원이 고른 팥 장면 컷이 다시 만들기에서 다른 샷의 크림 장면으로 바뀜(김형관·김만기)",
  "facts": ["B13(같은 장면 재사용)은 경고(ADVISORY_GATES)로 내려져 있다",
            "material_fit.relocate_cuts 는 reuse_unfixed 컷을 같은 원본의 다른 샷으로 옮겼다(옮긴 곳 내용 확인 없음)"],
  "causes": ["경고일 뿐인 재사용을 피하려고 코드가 장면 내용을 모른 채 다른 샷으로 옮겼다", "회원 Claude 가 재료를 잘못 적었다"],
  "fixes": ["재사용만 걸린 컷은 다른 샷으로 옮기지 않는다(같은 줄 다른 컷이 이어받는 빼기는 남김)", "옮긴 뒤 AI 로 장면을 다시 확인한다", "B13 을 다시 막는 관문으로 올린다"]},
 "09_update_mid": {
  "problem": "제작 중 '판 잇템로그판_v2 이 없다 — 있는 판: (빈 목록)' 3번(김효준), engine/tools/calcopy/hybrid/styles 폴더가 디스크에 없음",
  "facts": ["회원 Claude 실측: _update 에 1.0.61~1.0.88 이 10~15분 간격으로 들어왔고 제작 중 교체됐다",
            "업데이트 미루기는 그 프로그램의 activeRuns·anyFlowBusy 만 봤다(다른 Claude 창 프로그램의 빌림은 안 봄)",
            "빌림 잠금 rent.lock 은 PC 전체(모든 창)가 같이 본다"],
  "causes": ["다른 창이 빌려 만드는 중인데 이 창 프로그램이 엔진을 교체해 빌린 styles 가 사라졌다", "프리셋 서버가 판을 안 줬다", "디스크 부족"],
  "fixes": ["엔진 즉시 교체·연결기 교체 둘 다 rent.lock(어느 창이든 빌림 중)이면 미룬다", "업데이트를 하루 한 번만 낸다", "styles 를 빌리지 않고 설치본에 넣는다"]},
 "10_stale": {
  "problem": "다시 시도할 때마다 서버가 'stale 옛 진행 상태'로 거절해 편이 영영 막힘(김유선)",
  "facts": ["회원 PC send() 는 network/502~504 면 5초 뒤 같은 payload 로 한 번 더 보낸다",
            "서버는 처리 뒤 seq 를 올리고 next_payload 를 응답에만 담는다 — 응답이 PC 에 못 오면 PC 는 옛 payload 만 가진다",
            "서버는 seq 가 다르면 stale 로 거절한다"],
  "causes": ["처리된 요청의 응답을 못 받은 PC 가 같은 요청을 다시 보내자 서버가 stale 로 거절, 새 payload 를 다시 받을 길이 없었다", "두 창이 같은 편을 돌렸다", "서버 seq 계산 오류"],
  "fixes": ["서버가 편마다 직전 응답을 저장하고 같은 요청(해시)이 다시 오면 그 응답을 그대로 돌려준다", "stale 검사를 없앤다", "회원 PC 재시도를 없앤다"]},
 "11_sent_check": {
  "problem": "'자막 지우기에 쓰지 않는 구간까지 보낸 게 보여 멈췄어요'로 편이 닫힘, 실제로 더 보낸 것 없음(정민혜·차순엽)",
  "facts": ["c_clean_take 는 장부를 지금-30분부터 셌다", "다시 만들기 전 호출 13.2초와 뒤 호출 0.97초가 합쳐져 이번 쓰는 구간과 비교됐다(회원 Claude 실측)",
            "job.json 에 이번 뒤 작업 시작 시각 at 이 있다"],
  "causes": ["보낸 초를 세는 시작 시각이 이번 작업이 아니라 30분 창이라 앞 호출까지 셌다", "VMake 가 정말 더 보냈다", "계획이 보낸 뒤 바뀌었다"],
  "fixes": ["이번 뒤 작업 시작 시각(job.json at)부터의 장부만 센다", "보낸 초 검사를 없앤다", "30분 창을 5분으로 줄인다"]},
 "12_restyle_unchanged": {
  "problem": "다시 만들기가 '다시 만들지 못했습니다(실행기 ok · 완성본 안 바뀜)'로 실패 보고, render ok(강태경·김형관·김준용)",
  "facts": ["restyleFlow 는 final.mp4 수정 시각이 안 바뀌면 실패로 봤다", "렌더는 입력 지문이 같으면 완성본을 다시 쓰지 않는다(바뀐 것 없음)", "김준용 편은 강조 설정이 거절돼 실제로 바뀐 설정이 없었다"],
  "causes": ["바뀐 것이 없어 렌더가 완성본을 그대로 둔 것을 실패로 셌다", "렌더가 다른 경로에 썼다", "렌더가 죽었다"],
  "fixes": ["실행기 ok·완성본 있음·안 바뀜이면 '바뀐 설정이 영상에 닿지 않아 그대로'라는 안내와 함께 완성", "완성본을 항상 지우고 다시 굽는다", "실패 문구만 바꾼다"]},
 "13_vmake_tier": {
  "problem": "기본형(옛 방식·Pro 아님) VMake 키 회원은 편마다 고급을 먼저 보내 거절받고 기본으로 다시 보냄",
  "facts": ["member_clean 은 고급이 new_api/not_pro 로 거절되면 그 조각을 기본으로 한 번 더 보낸다(f189b7639)", "거절된 고급은 과금 전에 막힌다(다른 창 실측)", "키 확인용 무료 API 를 찾지 못했다"],
  "causes": ["키 등급을 기억하지 않아 편마다 고급 시도를 반복한다", "VMake 가 고급을 막았다"],
  "fixes": ["키 지문별로 등급을 기억해 기본형 키는 다음부터 처음부터 기본으로", "점검에서 실제 영상을 보내 등급을 미리 확인한다(돈 듦)", "항상 기본으로만 보낸다"]},
 "14_erase_blur": {
  "problem": "렌더 전 관문이 박힌 글자 컷을 찾았는데 clean_text 가 '자막 컷 0초 → VMake 0회'(김준용)",
  "facts": ["회원 PC 계획_시간표.json vmake_cuts = []", "회원이 재료.json blur 칸을 손으로 고쳐 넣어 둔 상태",
            "관문④는 흐림에 덮인 글자를 세지 않는다 · vmake_clean.gate_text_cuts 는 '흐림 칸은 빼지 않고 잰다(지우면 흐림이 필요 없어지니까)'"],
  "causes": ["지우는 판에서도 관문④가 흐림 칸을 빼고 재서 손 흐림이 덮은 글자를 지울 컷에서 뺐다(gate_text_cuts 와 판단이 다름)", "VMake 키가 없었다", "done 이 그 구간을 뺐다"],
  "fixes": ["지우는 판(erase)이면 관문④가 흐림 칸을 빼지 않고 잰다", "손 흐림 칸을 무조건 지운다", "회원에게 흐림을 넣지 말라고 안내만"]},
}
for k, v in Q.items():
    (D / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
print(len(Q))
