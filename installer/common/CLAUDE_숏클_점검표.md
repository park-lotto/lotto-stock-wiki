# 회원 지침(CLAUDE_숏클.md) 점검표 — 2026-10-30 (지침 문장 ↔ 회원 쪽 코드 대조)

**10-30 오전 수리 뒤(관제 290)**: ×11·△5 → 전부 ○(16번은 결정 — opus 그대로). ★전부 트랙에만 있다 — 라이브·설치본·꾸러미 반영은 사장님 승인 뒤. 커밋 eb4cc182e·f30aa04e5·7cef549ce·82c888dd8.

판정: ○ 지금 됨 · △ 일부 · × 안 됨(엔진 할 일). 근거 = 파일:줄 또는 함수.

| # | 지침 문장(장) | 판정 | 근거 | 할 일 |
|---|---|---|---|---|
| 1 | "○○ 회원님" 인사(2) | ○ | 라이선스 응답 member_name(가입 이름, 없으면 아이디 — claude_portal._member_name) → shortem_setup info.license.member_name | 시험 test_라이선스_회원이름_인사 |
| 2 | 지시함 확인 `shortem_inbox`(3-2) | ○ | make 스킬 allowed-tools 에 inbox·job·presets·profile 추가 | 시험 member_guide(지침 속 도구 ⊆ 허용 목록) |
| 3 | 채널 여러 개·새 프리셋 `shortem_presets`(3-2) | ○ | 같음(make·setup 스킬) | — |
| 4 | 새 프리셋 알림(3-2) | ○ | presets 응답 new=true(이 PC ~/.shortem/본프리셋.json, 처음 설치는 조용히) — index.newPresets | 시험 member_guide |
| 5 | 만들던 편 찾기·멈추기 `shortem_job`(3-2·4⑥) | ○ | 허용 목록 추가 | — |
| 6 | 1~2분 뒤 다시(4①) · 1분씩 10분 기다리기(5) | ○ | shortem_make(step="pause", seconds≤60) — 셸 없이 기다리기. 지침 5장 Start-Sleep 문장을 pause 로 | 시험 member_guide |
| 7 | 재료 모자라면 다른 검색어·후보로(4②) | ○ | 장면 검수 답 "재료_더찾기" → 그 자리에서 검색·고르기·받기·새 시트 → 장면 검수로 복귀(flow._more_material, 편당 2번, 대본·앞 단계 그대로) | 시험 test_flow_plan_ways · 저장된 hs_ep3 상태 재현 |
| 8 | 장면에 맞게 그 줄 문장 바꾸기(4②) | ○ | 장면 검수·완성본 고치기 답 "대본줄" → flow._apply_lines(줄 고치기·회원 고치기 공용 한 곳) → 계획부터, 재료 그대로 | 같음 |
| 9 | 목소리·길이 그 줄만(4②) | ○ | flow._line_fix(e635fe342) — 걸린 줄만 묻고 재료 그대로 → 계획부터 | 시험 test_flow_line_fix |
| 10 | 대본 먼저 보고 그 줄만 고치기(3-1) | ○ | 서버 응답마다 script(줄 id 포함, flow.script_view) · shortem_make step="script"(보기)·"revise"(그 줄 — flow.ph_member_revise, 어느 단계든) | 시험 test_flow_line_fix · member_guide |
| 11 | 디스크 모자라면 지울 후보 보여 주기(4③) | ○ | shortem_setup: 여유 10GB 아래면 cleanup(완성본·끝난/멈춘 편 작업 폴더, 경로 없이) · remove=[id] 로 고른 것만(disk.js) | 시험 member_guide |
| 12 | 완성 전 1초 시트 직접 보기(4-0 15-0) | ○ | 자동 검사 통과여도 1초 시트·훅 3초·끝 2초를 판정 요청으로(flow.FINAL_SHEET_LOOK·ph_final_sheet) · 걸리면 시트 붙여 완성본 고치기 | 시험 test_flow_plan_ways · hs_ep3 재현 |
| 13 | 완성본 받기 연결 안 됐으면 안내(8) | ○ | done 응답 deliver.to + 안내 한 줄(make_flow.deliverSay) | 시험 member_guide |
| 14 | 버텍스 키 숏템메이커에서 가져오기(2-1) | ○ | ★처음 판정 틀림 — 가져오기는 관제 266 에 이미 있었다(설정 화면 버튼 /bridge/import-keys, 서버 claude_studio.PC_KEY_SERVICES 에 vertex_sa). 회원 Claude 길만 없었다 → web_bridge.importMakerKeys 한 곳 + shortem_settings(action="import_keys"). 회원 엔진에서 버텍스를 부르는 단계는 지금 없음(받으면 keyEnv 가 GOOGLE_APPLICATION_CREDENTIALS 로 넘긴다) | 시험 member_guide |
| 15 | 판독 요청 여러 개 Agent 병렬(2-1) | ○ | make 스킬 Agent 허용 | — |
| 16 | 권장 모델 opus(2-1·3) | ○(결정) | 모든 요청 opus 그대로 = 사장님 PC 제작과 같다(사장님 10-30 "모델·도구 똑같이"). 나누기는 기록 대조 근거가 생기면 flow._rv 한 곳에서 | — |
| 17 | 숏템메이커·드라이브·텔레그램 보내기(8) | ○ | deliver.js | — |
| 18 | 설정 바꾸기·restyle(6) | ○ | shortem_settings set·make restyle · 칸 = preview_request default_pack 실측 | — |
| 19 | 라이선스 키 `/plugin configure`(2) | ○ | setup 스킬과 같음 | — |
| 20 | 기기 1대·작업 1개(2·3) | ○ | DEVICES_MAX=1 · lease | — |
| 21 | 다시 시도·이어 가기(4①⑥) | ○ | make retry·status | — |
| 22 | 로그인 창(4③) | ○ | shortem_login | — |
| 23 | 다른 소재 웹 검색 제안(4④) | ○ | WebSearch 허용 | — |
| 24 | 숏클 고장 알리기(4⑤) | ○ | shortem_feedback 허용 | — |
| 25 | 업데이트 다음 켤 때(3-2) | ○ | updater.js(바로 적용·지침 전문 응답은 카드 할 일) | — |

지침만 고친 것(1f7e333bd): 사용 한도 땐 Claude 가 말할 수 없음 → 미리 알림 · 우회는 검사 통과 범위에서만 · 요청 글은 Agent 에게 맡기는 건 됨.
