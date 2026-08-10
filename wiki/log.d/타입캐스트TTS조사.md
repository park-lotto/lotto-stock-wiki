# 타입캐스트 TTS 조사 로그

## 2026-08-06 (회사PC)

- 타입캐스트 API 실측 조사. 무료 티어(30k/월, 카드 불필요)로 검증 — 웹 에디터 구독과 별개.
- **문서가 틀렸다**: 감정 프리셋이 7종이 아니라 20종. 잘못된 값을 던져 422 에러에서 전체 목록 획득.
  숨어 있던 13종: regret·urgent·scream·shout·trustful·soft·cold·sarcasm·inspire·cute·cheer·casual·tonemid.
- **함정 3개 기록**: ①감정은 성우마다 지원 여부가 다름(1,125명 전수조사, urgent는 5명뿐)
  ②희귀 감정은 전부 구버전 ssfm-v21 전용(v30엔 없음) ③모르는 필드도 200을 주므로
  `last_pitch`·`duration`은 "성공"처럼 보이지만 조용히 무시됨.
- `emotion_type:"embedding"` + `emotion_vector`(1024/1280 실수) 발견 — 합성은 되나
  벡터 획득 경로 불명(엔드포인트 전부 404, 스튜디오는 로그인 벽). **미완**.
- 코드 변경 없음(조사만). 하네스는 `docs/typecast/probe*.py`, 정리는 `handoff/타입캐스트TTS조사.md`.
- ⚠️ 일레븐랩스 A/B는 못 함 — 로컬 .env에 ELEVENLABS_API_KEY 없음(서버 /etc/shopping-shorts.env 전용).
  비교표의 일레븐랩스 수치는 코드·문서 기준이지 청취 확인이 아니다.
