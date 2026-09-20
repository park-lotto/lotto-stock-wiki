---
name: project-insights-notebooklm-bridge
description: 인사이트 허브 가로검색 → NotebookLM 노트북+리서치+카드 자동 다리. nlm CLI subprocess. 완성·검증
metadata: 
  node_type: memory
  type: project
  originSessionId: afbd0124-37e9-45d2-bcda-59a773462789
---

인사이트 허브(:8090/insights)에서 종목/키워드 **가로검색 한 번 → 전 소스 발언이 NotebookLM 노트북으로 자동 투입**하는 다리. 2026-06-30 집PC 완성·라이브 검증.

**운영 팁(2026-07-03, 사용자 경험)**: 인포그래픽(스튜디오) 생성이 **같은 노트북 페이지에서 계속 실패**하는
경우가 많음 — 그 노트북을 계속 재시도하지 말고 **다른(새) 노트북 페이지에서 다시 시도**하면 되는 경우가
많다고 함. 골루프의 `generate_infographic`도 실패 시 같은 notebook_id로 재시도하는 로직은 없음(1회
시도 후 실패=에스컬레이션) — 향후 재시도 로직 추가 시 "새 노트북으로 재시도"를 우선 고려할 것.

확정 설계: **①+㉢** — 묶음단위=가로검색 q / 넣을자료=추출발언(검증사실).md + 원본 URL·유튜브 둘 다.
아키텍처: 서버(dashboard/server.py)가 `nlm` CLI를 subprocess 호출 → 브라우저 버튼 하나로 완전 자동(MCP 경유 아님).

엔드포인트:
- `POST /api/insights/to_notebook {q}` → atoms 토큰매칭 수집(LIMIT200) → 카테고리/소스별 .md + distinct URL → `nlm notebook create`+`source add --file/--youtube/--url`
- `POST /api/insights/notebook_research {notebook_id,q,mode}` → `nlm research start -n -m fast --auto-import`
- `POST /api/insights/notebook_card {notebook_id,format}` → `nlm report create --confirm` → 폴링 → `nlm download report`(md) 인라인 반환 (인포그래픽 이미지는 CLI 없음→리포트로)
- `POST /api/insights/notebook_query {notebook_id,question,conversation_id}` → `nlm notebook query --json` → 인용 달린 answer 반환

v2 핵심(2026-06-30): **허브 모달 안에서 이탈 없이** 💬질문(Q&A 인라인)+🎴리포트 인라인+🔬리서치. 검색/번들에 `_tokenize_query`(자연어 문장→키워드, 불용어·조사 제거). 노트북 제목=키워드 label.
검증(API): 반도체(질문 답변 인용포함·리서치+10·리포트), HBM, 조선 정상. 브라우저 스크린샷은 CDP 불안정(기능정상).

nlm 인증(2026-07-01 self-heal 완성): `nlm login`은 전용 Chrome 프로필(parklotto12)로 **비대화식 자동완료**(쿠키 재추출, 무비번). `nlm login --check`는 만료여도 exit0이라 출력의 "valid" 문자열로 판정. `_run_nlm`이 인증만료 신호 감지 시 그 자리서 재로그인+1회 재시도(락으로 직렬화). keepalive 15분 선제. 옛 25분 반응형은 만료구간에 사용자 걸림 → 폐기.
주의: 검색창은 키워드용(문장 질문은 노트북 안에서). PS 본문은 UTF-8바이트로 보내야 한글 안깨짐. [[project_telegram_ingest]] [[project_stockbrain_dashboard]]
