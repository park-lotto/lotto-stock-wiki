# 회원 지침(CLAUDE_숏클.md) 점검표 — 2026-10-30 (지침 문장 ↔ 회원 쪽 코드 대조)

판정: ○ 지금 됨 · △ 일부 · × 안 됨(엔진 할 일). 근거 = 파일:줄 또는 함수.

| # | 지침 문장(장) | 판정 | 근거 | 할 일 |
|---|---|---|---|---|
| 1 | "○○ 회원님" 인사(2) | × | 라이선스 응답에 회원 이름 칸 없음(claude_portal 라이선스 응답 cid 만) | 서버 응답에 이름 칸 |
| 2 | 지시함 확인 `shortem_inbox`(3-2) | △ | make 스킬 allowed-tools 에 없음(make·ai·settings·login·setup·feedback·Agent·WebSearch·WebFetch 만) | 스킬 허용 목록에 inbox·job·presets·profile 추가 |
| 3 | 채널 여러 개·새 프리셋 `shortem_presets`(3-2) | △ | 같은 허용 목록 문제 | 같음 |
| 4 | 새 프리셋 알림(3-2) | × | Claude 는 대화 사이 기억이 없어 "처음 보는" 것을 모름 · presets 응답에 새것 표시 없음 | 서버가 회원이 아직 안 쓴 새 프리셋 표시 |
| 5 | 만들던 편 찾기·멈추기 `shortem_job`(3-2·4⑥) | △ | 허용 목록에 없음 | 2번과 같음 |
| 6 | 1~2분 뒤 다시(4①) · 1분씩 10분 기다리기(5) | × | `wait` 은 돌고 있는 작업이 없으면 바로 끝남(make_flow.js wait "기다릴 작업이 없습니다") · make 스킬이 PowerShell 막음 | 숏클 도구에 "N초 기다리기(회원 답 오면 바로 끝)" 추가 |
| 7 | 재료 모자라면 다른 검색어·후보로(4②) | × | 지시서에 재료 찾기로 돌아가는 길 0곳 | 지시서에 재료 다시 찾기 길 |
| 8 | 장면에 맞게 그 줄 문장 바꾸기(4②) | × | 장면 맞추기 중 회원 Claude 가 대본 줄을 바꿀 길 없음(재료 답만) | 장면 검수 답에 줄 고치기 칸(line_fix 재사용) |
| 9 | 목소리·길이 그 줄만(4②) | △ | flow._line_fix 트랙에만(e635fe342) | 라이브 반영 |
| 10 | 대본 먼저 보고 그 줄만 고치기(3-1) | × | MCP 에 대본 보기·고치기 단계 없음(start·choose·approve·wait·status·retry·restyle 만) | shortem_make 에 script(보기)·revise(줄) |
| 11 | 디스크 모자라면 지울 후보 보여 주기(4③) | × | 회원 Claude 가 폴더 목록을 볼 도구 없음(Read·Glob 막힘, job 허용 밖) | setup 결과에 지울 후보 목록 |
| 12 | 완성 전 1초 시트 직접 보기(4-0 15-0) | × | 완성본 1초 시트를 회원 Claude 에게 보내는 곳 없음(flow_driver 에 없음) | 검사 단계에서 시트를 판정 요청으로 반드시 |
| 13 | 완성본 받기 연결 안 됐으면 안내(8) | × | 보내기는 뒤에서 돌고(deliverInBackground) 결과가 응답에 없음 | done 응답에 보내기 상태 |
| 14 | 버텍스 키 숏템메이커에서 가져오기(2-1) | × | 안내 글(voice.js need)만 있고 가져오기 동작 못 찾음 · 회원 묶음에 vertex_route 없음(HAND_SERVER_ONLY) | 가져오기 + 버텍스 경로 |
| 15 | 판독 요청 여러 개 Agent 병렬(2-1) | ○ | make 스킬 Agent 허용 | — |
| 16 | 권장 모델 opus(2-1·3) | △ | 모든 요청이 opus(flow._rv 기본) — 나눠 쓰지 않음 | 요청별 모델(기록 대조 뒤) |
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
