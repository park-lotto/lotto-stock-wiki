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

## 2026-08-19 — 타임스탬프 실측 (배선 최대 걸림돌 해소)
- `POST /v1/text-to-speech/with-timestamps` 200 확인. words 6개 + characters 23개(원문 23자와 정확히 일치).
- 우리 `tts_timestamps.words_from_alignment`에 먹여 단어 추출 통과 — **자막 싱크 안 밀린다**.
  단 `end`(character_end_times_seconds)까지 실어야 함, 빠지면 None→ASR 폴백 강등.
- mp3 직접 지원 확인. audio_tempo 1.6 실동작(3.683→2.406초) → ElevenLabs 1.2 clamp 후처리 제거 가능.
- 하네스: docs/typecast/probe_ts.py, probe_ts2.py
- 청취샘플 20개 생성(성우 4 x 감정·속도 5) + 일레븐랩스 기존 20개 나란히 비교 페이지:
  `out/typecast_vs_eleven.html` (mp3를 data URI로 박아 파일 하나로 재생). 하네스 docs/typecast/make_samples.py, build_compare.py
- 음량 대조 -21.0dB(TC) vs -20.6dB(EL)로 동등 — 무음 mock 아님을 ffmpeg volumedetect로 확인.
- 사장님 확정 세팅: **Seohyeon(tc_69f2e455ea79fd197aa0476f) · ssfm-v30 · toneup 강도1.3 · tempo 1.2**.
  청취 페이지 out/typecast_확정_Seohyeon.html (실제 대본 훅/본문/마무리 + 1.2·1.3·1.4 속도 대조).
  ⚠️ tempo 1.2는 ElevenLabs API 상한과 같은 값 — 타입캐스트로 가는 근거에서 "속도 clamp 해소"는 빠진다.
