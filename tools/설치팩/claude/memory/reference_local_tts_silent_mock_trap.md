---
name: reference_local_tts_silent_mock_trap
description: 로컬엔 ElevenLabs 키가 없어 TTS가 무음 mock으로 나온다 — 무음 길이로 재면 거짓 결론. 실TTS는 5.92자/초로 상수 5.7과 일치
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0120789f-ab04-47db-9779-e09084f300ad
  modified: 2026-07-20T02:54:55.163Z
---

쇼핑쇼츠 TTS(`shopping_shorts/tts.py`)는 `config.ELEVENLABS_API_KEY`가 비면 조용히
**무음 mp3**를 만든다(`_write_silent_mp3`, 길이는 `_CHARS_PER_SEC=5.0`으로 추정, mean_volume≈-91dB).
키는 **서버 systemd `/etc/shopping-shorts.env`에만** 있고 로컬 `.env`(루트·shopping_shorts/ 둘 다)엔 없다.
`config`는 `shopping_shorts/.env`만 dotenv 로드한다(루트 .env는 `pipeline.atoms.key_vault`만 읽음 → Gemini는 되고 TTS만 무음).

**함정(2026-07-20 실제로 빠질 뻔함):** 콤포루프 검증 때 무음 mock 길이로 재서
"conform이 gap 못 닫음 · `_SYLLABLES_PER_SEC=5.7`이 2배 어긋남"이라는 **거짓 결론**을 냈다.
서버 키를 트랙 `shopping_shorts/.env`로 내려받아 실 TTS로 재니: 실측 **5.92자/초**로 상수 5.7과 거의 일치,
conform이 sync_gap을 **5.03s→0.0s**로 완전히 닫았다(재TTS ≤ 예산 → freeze 불필요).

**앞으로 TTS/음성 검증 시 필수 선행 체크:**
1. `config.ELEVENLABS_API_KEY` 로드됐나(길이 확인)
2. 만든 mp3 `mean_volume`이 -91dB(=무음)인지 volumedetect로 확인 — 무음이면 mock, 결론 금지
3. 필요하면 서버에서 키를 당겨 트랙 `shopping_shorts/.env`에 넣고 실 TTS로 잰다
   (`ssh ubuntu@3.39.179.148 "sudo grep ^ELEVENLABS_API_KEY= /etc/shopping-shorts.env"`).

[[project_제작소_어긋남구제]] [[feedback_verify_with_real_data]] — 검증환경≠실행환경(무음 mock은 실TTS가 아니다).
보이스 트랙 핸드오프에도 같은 사실이 이미 기록돼 있었다(로컬 ElevenLabs 키 0개 → tts.py 무음).
