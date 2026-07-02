---
name: channel-onboard
description: 새 크롤링 채널을 추가하거나 기존 채널의 원자추출 질문지를 재검토할 때
  사용. 샘플 콘텐츠를 직접 분석해 채널 성격에 맞는 질문지를 설계하고, Gemini로
  시험 추출한 뒤 검수까지 마치고서야 프로덕션에 등록한다.
---

# 채널 온보딩 — 성격 분석 → 질문지 설계 → 검수 → 시험 → 재검수 → 등록

## 언제 쓰나

- 새 텔레그램/유튜브 채널을 크롤 대상에 추가할 때
- 기존 채널의 원자추출 품질이 의심될 때(정보가 새고 있다고 판단될 때)

절대 이 루프를 건너뛰고 채널을 registry.json에 등록하지 않는다.

## STEP 1 — 샘플 수집

- 유튜브: `/watch` 스킬로 그 채널의 최근 영상 3~5개를 확인(프레임+자막)
- 텔레그램: `raw/telegram/{채널명}/` 최근 메시지 파일 중 최근 20개 정도를 직접 Read

## STEP 2 — 채널 성격 분석

샘플을 보고 다음을 판단해 사용자에게 요약 보고:
- 이 채널이 전형적으로 어떤 정보를 담는가(시황요약형/종목추천형/데이트레이딩형/
  리서치형/잡담형 등)
- `pipeline/atoms/profiles.py`(유튜브) 또는 `pipeline/atoms/telegram_questionnaire.py`의
  `QUESTIONNAIRES`(텔레그램)에 이미 맞는 프로필이 있는지, 없으면 신규가 필요한지

## STEP 3 — 질문지 설계

기존 프로필을 재사용하거나, 신규 프로필을 설계한다. 신규 프로필은 반드시 다음
두 가지를 산출물로 만든다:
1. Gemini 프롬프트(질문 슬롯 목록) — Task3의 `_DAYTRADING_PROMPT` 형식을 참고
2. 슬롯 → 저장 위치 매핑표: 각 슬롯이 `atoms` 컬럼인지 `structured_fields` 키인지
   명시. **모든 슬롯이 매핑돼야 한다** — 매핑 안 되는 슬롯은 프롬프트에서 아예 뺀다.

## STEP 4 — 1차 검수

STEP3 산출물(질문지 + 매핑표)을 사용자에게 보여주고 확인받는다(`AskUserQuestion`
또는 평문으로 물어보기). 확인 전에는 다음 단계로 넘어가지 않는다.

## STEP 5 — Gemini 시험 실행

STEP1 샘플 중 3~5개에 실제로 그 질문지로 Gemini를 돌려본다(기존
`extract_telegram`/`extract_post`/`_extract_daytrading` 패턴을 참고해 임시 스크립트로
실행하거나 파이썬 인터랙티브로 직접 호출).

## STEP 6 — 2차 검수

Gemini 결과를 원문과 대조:
- 슬롯이 실제로 채워지는가(빈 값만 나오면 프롬프트가 안 맞는 것)
- `quote` 필드가 원문에 실제로 존재하는 문장인가(지어내지 않았는가)
- `pipeline/atoms/verify_questionnaire.py`의 인용대조 패턴을 참고해 직접 대조

결과를 사용자에게 보여주고 확인받는다. 실패하면 STEP3로 돌아가 질문지를 수정한다.

## STEP 7 — 등록

통과하면 registry.json(텔레그램: `telegram_channels.json`의 `type` 필드 / 유튜브:
`youtube_registry.json`의 `profile` 필드)에 프로필명을 등록한다. 신규 프로필을
만들었다면 `pipeline/atoms/profiles.py`(유튜브) 또는
`pipeline/atoms/telegram_questionnaire.py`의 `QUESTIONNAIRES`(텔레그램)에 코드로
반영하고 `pipeline/atoms/test_slot_coverage.py`에 슬롯 커버리지 체크를 추가한다.
