# 타입캐스트 TTS 조사 (일레븐랩스 대안 검토)

**날짜**: 2026-08-06 · **PC**: 회사 · **상태**: 조사 완료, 코드 미변경

---

## 왜 봤나

일레븐랩스(현행 `eleven_multilingual_v2` / 프리셋은 `eleven_v3`)의 대안으로 타입캐스트를
검토. 사장님 질문: ①API 있나 ②성우 섞는 기능이 있다던데 ③기존 걸 감정 업그레이드 가능한가.

## 결론 3줄

- **API 있다. 무료 티어 30k 크레딧/월, 카드 불필요** — 웹 에디터 구독(프로 39,000원)과 별개.
- **"성우 섞기"는 없다.** 사장님이 본 건 감정·피치·템포 조합이거나 다중화자 대본일 것.
  다만 비공개 `emotion_vector`(1024/1280차원)가 존재 — 이게 진짜 믹스일 수 있다(아래 미완).
- **이미 뽑은 음성에 감정만 얹기는 불가능.** 재합성만이 방법.

---

## 실측으로 확인한 것 (문서와 다름 — 중요)

문서엔 감정 7종이라 적혀 있는데 **실제 20종**이다. 잘못된 값을 던지면 서버가 전체 목록을 뱉는다.

```
POST /v1/text-to-speech   "emotion_preset": "ZZZ"
→ 422 "Input should be 'normal','sad','happy','angry','regret','urgent','whisper',
   'scream','shout','trustful','soft','cold','sarcasm','inspire','cute','cheer',
   'casual','tonemid','toneup' or 'tonedown'"
```

### ★함정1: 감정은 성우마다 다르다

전체 1,125명 전수조사 결과. 지원 안 하는 감정을 걸면 `EMOTION_NOT_SUPPORTED` 422.
**감정을 먼저 정하고 성우를 고르는 순서**가 맞다.

| 감정 | 지원 성우 수 |
|---|---|
| normal·sad·happy·angry | 1,125 (전원) |
| toneup / tonedown / whisper | 712 / 655 / 600 |
| tonemid | 103 |
| cheer·soft | 12 |
| cute·shout | 7 |
| urgent | 5 |
| casual·sarcasm·trustful·cold·scream | 3~4 |
| inspire·regret | 1 |

### ★함정2: 희귀 감정은 전부 구버전(ssfm-v21) 전용

v30에는 희귀 감정이 **하나도 없다**. 트레이드오프:
- **v30** = `smart`(문맥 자동감정) + 37개 언어 + 최신 품질
- **v21** = 감정 종류 많음(urgent·trustful·cold 등)

### ★함정3: 모르는 필드도 200을 준다 — "성공"이 아니다

`zzz_unknown: 1` 같은 엉터리 필드를 넣어도 200이 떨어진다. 즉 **200 = 적용됨이 아니다.**
- `last_pitch`, `duration`, `max_length`, `style` → 전부 200이지만 **조용히 무시된다**
- 문서 목차의 "문장 끝 피치·고정 길이"는 구버전 `/api/text-to-speech` 얘기. `/v1/`엔 없음.

---

## 실제 튜닝 축 (검증된 것만)

| 필드 | 범위 | 비고 |
|---|---|---|
| `prompt.emotion_preset` | 20종 | 성우가 지원해야 함 |
| `prompt.emotion_intensity` | 0.0 ~ 2.0 | 초과 시 422 |
| `output.audio_pitch` | -12 ~ +12 반음 | **일레븐랩스엔 없는 축** |
| `output.audio_tempo` | 0.5 ~ 2.0 | 일레븐랩스는 0.7~1.2 clamp |
| `output.volume` | 0 ~ 200 | `target_lufs`와 동시 사용 불가 |
| `output.target_lufs` | -70 ~ 0 | |
| `seed` | 0 ~ 4294967295 | 재현성 |
| `prompt.emotion_type` | `preset` / `smart` / `embedding` | |

### emotion_type 3종

```jsonc
// ① 프리셋 — 수동 지정
{"emotion_type":"preset", "emotion_preset":"toneup", "emotion_intensity":1.3}

// ② 스마트 — 문맥 읽고 자동 (ssfm-v30 전용)
{"emotion_type":"smart", "previous_text":"앞 대사", "next_text":"뒤 대사"}

// ③ 임베딩 — 비공개. 1024 또는 1280개 실수 배열
{"emotion_type":"embedding", "emotion_vector":[...]}
```

**②가 우리 파이프라인에 중요**: `tts.py:81-85`가 이미 `previous_text`/`next_text`를 넘기는데
일레븐랩스 v3에서는 400으로 막혀 버려지고 있다(코드 주석에 기록됨). 타입캐스트 smart는 그 값을 받는다.

---

## 일레븐랩스 대비

| | 일레븐랩스 (현행) | 타입캐스트 |
|---|---|---|
| 모델 | eleven_v3 (미나·유니 프리셋) | ssfm-v30 / v21 |
| 속도 | **0.7~1.2 clamp** → 초과분 후처리 atempo (`tts.py:44`) | **0.5~2.0** API 직접 |
| 피치 | **없음** | **-12~+12 반음** |
| 감정 | voice_settings.style (수치) | 프리셋 20종 + 강도 |
| 문맥 자동감정 | 없음 | `smart` |
| 앞뒤 문맥 | v3에서 400 에러 | 지원 |
| 보이스 | 라이브러리 | 1,125명 (v30 590) |
| 텍스트 상한 | - | 2,000자 |
| 요금 | $0.0484/1k자 | Free 30k/월 · Lite $15 · Plus $280 |

---

## ✅ 타임스탬프(자막 싱크) 실측 완료 — 2026-08-19

**결론: 붙일 수 있다. 자막 싱크는 안 밀린다.** 배선 최대 걸림돌이었던 항목이 해소됐다.

`POST /v1/text-to-speech/with-timestamps` (200). ElevenLabs와 **같은 경로 이름**이다.
`/v1/text-to-speech/{voice_id}/with-timestamps`는 404 — voice_id를 경로에 넣지 않는다(요청 본문으로).
`with_timestamps: true` 같은 **요청 필드로는 안 된다** — 200이 오지만 그냥 wav다(0순위 함정3 재현).

### 응답 구조 (실측)

```jsonc
{"audio": "<base64>", "audio_format": "mp3", "audio_duration": 3.683,
 "words":      [{"text":"이거","start":0.261,"end":0.401}, ...],   // 6개
 "characters": [{"text":"이","start":0.261,"end":0.321}, ...]}     // 23개
```

**원문 23자 = characters 23개 정확히 일치**(공백 포함). 우리처럼 보낸 문자열 자체의 정렬이라
맞출 대상이 없다 = 어긋날 수가 없다. ElevenLabs와 같은 성질.

### 우리 형식으로 변환 — 실제로 통과시킴

`tts_timestamps.words_from_alignment`에 먹여 **단어 6개 정상 추출 확인**:
`이거 / 수리 / 맡기면 / 30만원은 / 그냥 / 깨지죠.`

필드명만 바꾸면 된다(리스트→평행배열):

| 우리(ElevenLabs) | 타입캐스트 |
|---|---|
| `characters[]` | `characters[].text` |
| `character_start_times_seconds[]` | `characters[].start` |
| `character_end_times_seconds[]` | `characters[].end` |

⚠️ **`end`까지 반드시 실어야 한다** — `words_from_alignment:117`이 셋 중 하나라도 없으면
`None`을 반환하고 조용히 ASR 폴백으로 강등된다(비용·오차 부활). 실제로 이 실측 중에 밟았다.

### 같이 확인한 것

- **mp3 직접 지원**: `output.audio_format:"mp3"` → 200, 실제 mp3. 현행 mp3 사이드카 전제 그대로.
- **audio_tempo 1.6 실동작**: 3.683초 → 2.406초. 프리셋 `default_speed`가 1.6인데 ElevenLabs는
  1.2 clamp라 `audio_post` atempo로 되돌리던 것을 **API가 직접 처리**. 2.0도 200.
- **크레딧 헤더 없음** → 타임스탬프 추가과금 여부는 헤더로 확인 불가. 대시보드에서 봐야 한다.

### 하네스

`docs/typecast/probe_ts.py`(엔드포인트 탐색) · `probe_ts2.py`(구조 해부 + 우리 함수 통과 검증).
⚠️ `probe_ts`를 import하면 그쪽 본문이 다시 실행된다(실측: stdout 재래핑 충돌) — 복사해 쓸 것.

---

## ⏭ 미완료

### 0. 결제 전 확인 (사장님 손 필요)
웹 에디터 구독(프로 39,000원)과 **API는 별개**다. 결제 전 API 크레딧 포함 여부를 확인할 것.
지금은 무료 티어 키로 위 실측을 다 했다(30k 크레딧/월).

### 1. emotion_vector 정체 (막힘 — 사장님 손 필요)
`emotion_type:"embedding"` + `emotion_vector`(1024/1280 실수)로 **합성 성공은 확인**.
근데 벡터를 어디서 얻는지 불명:
- `/v1/emotions`, `/v1/emotion/extract` 등 전부 404
- 공개 문서에 `embedding` 언급 자체가 없음
- 스튜디오(웹 에디터)는 로그인 벽 → Claude가 대신 로그인 불가

**재개 방법**: 사장님이 studio.typecast.ai 로그인한 창을 열어주면
네트워크 요청을 까서 벡터 획득 경로를 잡을 수 있다.

### 2. 일레븐랩스 나란히 A/B (미완)
로컬 `.env`에 `ELEVENLABS_API_KEY`가 **없다**(서버 `/etc/shopping-shorts.env`에만 있음).
같은 대사로 뽑으면 무음 mock(37KB)이 나온다. 진짜 A/B를 하려면 키를 로컬로 가져와야 함.
→ 지금까지의 일레븐랩스 수치는 **코드·문서 기준**이지 청취 확인이 아니다.

### 3. 홈테리어픽 재해석 (사장님 지적)
`homterior_pick` 272만뷰 릴스를 9개 비트로 쪼개 감정을 각각 배정했는데,
**사장님 지적: "하나로 셋팅해둔 걸텐데"** — 채널 톤이 일관되므로 비트별 교체가 아니라
단일 세팅일 가능성이 높다. 재현 방향을 단일 프리셋 + smart로 다시 잡아야 함.

---

## 관련 파일

- 키: `.env`의 `TYPECAST_API_KEY` (gitignore — 서버 배포 시 `/etc/shopping-shorts.env`에도 필요)
- 현행 프리셋: `shopping_shorts/assets/voice_presets.json` (kr-mina-*, kr-yooni-*)
- TTS 호출: `shopping_shorts/tts.py` (speed clamp는 44행, v3 문맥 가드는 77~85행)
- 샘플 대사: `shopping_shorts/scripts/build_voice_samples.py` `DEMO_TEXT`
- 조사 스크립트: `docs/typecast/` (probe.py·probe2.py = 파라미터 실측 하네스)

## 배선한다면

`tts.py`에 백엔드 분기를 넣는 방식. 매핑:

| 현행 인자 | 타입캐스트 |
|---|---|
| `speed` | `output.audio_tempo` (clamp 불필요) |
| `voice_settings.style` | `prompt.emotion_preset` + `emotion_intensity` |
| `previous_text`/`next_text` | `prompt.emotion_type:"smart"` (v3에서 막힌 게 여기선 살아난다) |
| `seed` | `seed` (동일) |
| — | `output.audio_pitch` (신규 축) |

⚠️ 타임스탬프: 일레븐랩스는 `/with-timestamps`로 자막 싱크를 받는데(`tts_timestamps`),
타입캐스트도 타임스탬프 TTS 엔드포인트가 별도로 있다. 배선 시 그 경로도 맞춰야 자막이 안 밀린다.
