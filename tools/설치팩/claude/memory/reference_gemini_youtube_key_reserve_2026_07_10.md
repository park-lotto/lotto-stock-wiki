---
name: reference_gemini_youtube_key_reserve_2026_07_10
description: "2026-07-10 제공 키 13쌍 — ★2026-08-04 실측: 전부 이미 배치됨, 예비 아님. 원본 메모=Downloads/52926371_secretkey.txt, 정리본=바탕화면 제미니키_보관메모장.md"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 2fa09dbe-56ae-4b88-a327-fabde1ac5dcf
  modified: 2026-08-04T02:57:20.488Z
---

2026-07-10, 쇼핑쇼츠 Gemini 키 소진 대응 중 사용자가 대량의 신규 키를
제공(계정10~계정20). 그중 **쇼핑쇼츠용으로 명시된 3개(계정20, 아이디
3000~3002)**는 그 자리에서 `SHORTS_GEMINI_KEY_14~16`로 서버
`/etc/shopping-shorts.env`에 추가·배포 완료.

**나머지 10쌍(계정10~계정19, 아이디2000~2009)**은 사용자가 "앞에 10개는
주식쪽일꺼고 비상용으로 꺼내쓰면되"라고 명시 — **주식위키 본체
(`pipeline.atoms.key_vault`) 쪽 비상 예비 키**. 아직 아무 곳에도 배치
안 됨(이 세션은 쇼핑쇼츠 작업이라 범위 밖으로 판단해 보류). key_vault는
프로젝트 루트 `.env` 파일에서 `GEMINI_API_KEY_N`(general 그룹) 등 넘버링
패턴으로 동적 스캔한다([[project_쇼핑쇼츠_자동화]]와 무관, 별도 시스템).

각 쌍은 "AQ.Ab8RN6..." 형식(Gemini, [[reference_...]] 필요시 재확인)과
"AIzaSy..." 형식(YouTube Data API)으로 구성. 실제 키 값은 사용자와의
대화 기록에 있음 — 이 메모리는 존재·용도·미배치 상태만 기록. 다음에
주식위키 쪽 Gemini/YouTube 키 소진이 발생하면 이 예비분을 먼저 확인할 것.

**★2026-08-04 실측 정정**: "미배치 예비"는 틀렸다. 13쌍 전부 이미 배치돼
있었다 — 아이디3000~3002=서버 SHORTS_GEMINI_KEY 1~3, 아이디2000~2009=서버
KEY 4~13 **이면서 동시에** 주식위키 로컬 `.env`(EMBED/API/BRIEFING/INGEST
그룹)와 같은 키 공유(쿼터 공유 → 한쪽 소진=양쪽 막힘). 서버는 이날 중복
3개(KEY14~16=KEY1~3 재입력) 제거+신규4개로 유니크 17개로 정리됨.
키 원본: `Downloads/52926371_secretkey.txt`, 정리본: 바탕화면
`제미니키_보관메모장.md`(사장님이 계속 추가 중, 다음 슬롯 KEY_18).
