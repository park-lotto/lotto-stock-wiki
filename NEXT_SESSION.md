# NEXT_SESSION — 원자추출 프로파일 재설계 + 태린이아빠 채널 온보딩

**날짜**: 2026-07-02 · **PC**: DESKTOP-T8CB1GG(회사) · **주제**: 원자추출 프로파일 재설계(10태스크 완료) + 텔레그램 2채널 온보딩(진행중)

## 이번 세션 요약

### ✅ 완료: 원자추출 프로파일 재설계 (10태스크, subagent-driven-development)
크롤봇이 Gemini로 원자 뽑을 때 질문지 슬롯이 조용히 유실되던 문제를 구조적으로 해결.

- Task1: `structured_fields` JSON 컬럼 신설(`pipeline/atoms/db.py`)
- Task2~5: 유튜브 채널 프로필 레지스트리(`pipeline/atoms/profiles.py`) + 데이트레이딩 프로필 신설
  + `post_ingest.py` 하이브리드 폴백 분기 + `youtube_registry.json` profile 필드(전부 null, 동작불변)
- Task6: 리포트 stock/sector/market 구조화슬롯을 structured_fields로 보존(`questionnaire.py`)
- Task7: 텔레/유튭/블로그/뉴스 공유 insight타입 유실(leading_sectors/noise_ratio/quote) 복구
- Task8: 슬롯 유실 방지 정적 체크(`test_slot_coverage.py`)
- Task9: 채널 온보딩 스킬 문서(`.agents/skills/channel-onboard/SKILL.md`) — 신규 채널 추가시
  반드시 거쳐야 하는 7단계(샘플수집→성격분석→질문지설계→1차검수→Gemini시험→2차검수→등록) 루프
- **사고 발견·복구**: Task6 완료 직후 동시 세션이 같은 워킹트리에서 `feat/goal-loop-morning-brief`
  브랜치를 만들어 체크아웃했는데 못 알아채서 Task6~9+최종수정 커밋 5개가 main이 아니라 그
  브랜치에 쌓였음. 최종 검증 중 발견→전부 main으로 cherry-pick 복구, 153개 테스트 통과 확인
  후 push 완료. **교훈: 공유 워킹트리에서 커밋 전 `git branch --show-current` 항상 확인.**

계획: `docs/superpowers/plans/2026-07-02-원자추출-프로파일-재설계.md` (10태스크 전부 완료 마킹)
스펙: `docs/superpowers/specs/2026-07-02-원자추출-프로파일-재설계-design.md`

### 🔄 진행중: 텔레그램 채널 온보딩 (태린이아빠 주식투자 / 요약하는 고잉)

Task10(위 계획의 마지막 태스크)으로 시작 — 두 채널 다 현재 `insight` 프로필로는 부적합하다는
결론까지는 났으나, 실제 질문지 설계·등록은 **미완료**(온보딩 스킬 STEP4/6 사용자 확인 대기).

#### 요약하는 고잉 — 작은 변경만 필요 (미착수)
insight 프로필에 근접하지만 날짜 붙은 이벤트 캘린더(예: "미고용지표 7/2, 삼전실적 7/7")를
저장할 슬롯이 없어서 샘. 제안: `telegram_questionnaire.py`의 `QUESTIONNAIRES["insight"]`에
`event_calendar: [{date, event}]` 슬롯 1개만 추가(신규 프로필 아님, insight 태그 붙은 다른
채널도 같이 혜택). STEP5(Gemini시험) 아직 안 돌려봄.

#### 태린이아빠 주식투자 — 신규 프로필 필요, v2까지 시험함 (STEP4 확인 대기)

**채널 성격** (7일치 샘플: 06-19/06-25/06-28~07-02): 실시간 포지션 추적 일지 + 증권사
리포트 릴레이 + 매크로 뉴스가 섞임. **고정 시각 루틴은 없고**("미국장마감→국내장개장"
이벤트 기준으로 블록이 흔들림), 대신 **매일 있는 고정 콘텐츠 1개**: 미국장 마감 직후
(대략 06:00~06:10대) 번호매긴(1~7번) "오늘 시장 대응 어떻게 할지" 정리하는 개인 판단글.
이게 채널의 핵심 콘텐츠.

**질문지 v2 (Gemini로 07-02 실제 시험 완료, 결과 양호)**:
```
너는 텔레그램 주식 포지션 추적 채널의 하루치 메시지를 '정해진 칸'에 옮겨 적는 사람이다.
판단하지 말고 칸을 채워라. 잡담·인사는 버려라.
철칙: 없으면 null(지어내지 마라) / 비중(%)은 원문 숫자 그대로 / quote는 원문 문장 그대로.
종목 하나당 레코드 하나 — 여러 종목을 합쳐서 하나로 기록하지 마라.

## 칸
daily_prep_note: {
  time(시각), points([str] — 번호매긴 항목 그대로 각각 하나씩),
  stance(당일 종합 스탠스 한 줄 — 예: "반도체 비중 축소, 은행 편입 관찰")
}  (미국장 마감 직후 올라오는 번호매긴 대응준비 글 — 채널의 핵심 판단. 하루에 보통 1개)
position_changes: [{
  name(종목/ETF명 — 여러 종목이면 각각 별도 항목으로), from_weight(변경전 비중, 알수있으면),
  to_weight(변경후 비중), reason(매도매수 사유 원문 — 예: "10주이평선 이탈"), time(시각), sector
}]
relayed_reports: [{
  broker(증권사), analyst(애널리스트), target(종목/섹터), rating(투자의견),
  tp(목표가), summary(1~2문장 요약)
}]
macro_notes: [str]  (환율/금리/외신 코멘트 — daily_prep_note에 안 들어간 것만)
leading_sectors: [str]  (당일 언급된 주도섹터)
quote: str  (가장 통찰력 있는 한 문장)
```

**v2 시험 결과 (2026-07-02 실데이터)**: position_changes는 하이닉스(24%→20%,20일선이탈)/
삼성전자(20%→15%,10주이평선이탈)로 정확히 분리됨(v1의 "닉전"으로 합치던 버그 해결).
**남은 흠**: `daily_prep_note`가 06:07의 번호매긴(1~7) 글이 아니라 05:45의 짧은 불릿목록을
잘못 골랐음 — 프롬프트에 "숫자+괄호 형식(1) 2) 3)...)인 것만"으로 더 명확히 못박아야 함.
relayed_reports도 실행마다 1~2개씩 랜덤으로 누락됨(변동성 있음, 재시험 필요).

**⚠️⚠️ 중대 발견 — 사람 브레인 프로젝트와 정확히 겹침**: 사용자가 "이 사고과정 계속
추적하면 태린이 사고를 가져올 수 있는거 아니냐"고 질문 → 확인해보니 `pipeline/people/`
("사람 브레인" 프로젝트, 오늘 오전 별도 세션에서 이미 **핵심 비전 전부 달성** 완료됨,
자세한 내용은 `project_person_brain` 메모리 + 이 파일 git 히스토리의 이전 버전 참고)이
이미 이 정확한 개념을 구현해놨음:
- `pipeline/people/routines/태린이아빠.json` — 4단계(전날밤/새벽/장전/장중) 정적 루틴
  템플릿. 내가 07-02에서 수동 추적한 반도체 사고체인과 **이미 스텝별로 일치**함
  (예: "종합판단(1~7 정리)" 스텝 = 내가 찾은 06:07 글, "이평선 이탈 종목 비중축소 계획:
  기계적 5% 축소(삼전·하이닉스)" 룰 = 내가 추적한 트리거 그대로)
- `pipeline/people/persona.py` — 이 룰을 오늘 실데이터에 적용해서 종목/시장 판정까지 내는
  질의엔진(`stock_verdict`/`market_verdict`) 이미 완성, 대시보드 :8090/brain에서 라이브
- **진짜 갭**: routine.json은 07-01/07-02 딱 이틀 수동분석으로 만든 정적 템플릿이고,
  funnel/persona는 osc·RS·소라티노 등 숫자데이터로만 오늘을 채움. 지금 설계중인
  `daily_prep_note`/`position_changes`(텔레그램 원문 자동추출)가 있으면 "오늘 그가 실제로
  뭐라고 판단했는지" 원문 근거가 매일 atoms.db에 자동으로 쌓여서 persona.py가 매일 손으로
  raw파일 다시 안 읽어도 더 풍부하게 답할 수 있게 됨.

**사용자에게 물어봤던 질문(응답 전 세션 종료)**: 지금 설계한 질문지를 (a) 사람브레인
데이터 소스로 연결(atoms.db에 매일 쌓이게 하고 persona.py가 읽도록) vs (b) 온보딩만
먼저 마무리(사람브레인 연결은 나중) — **다음 세션에서 이 결정부터 확인 필요.**

## 미완료 / 다음 할 것
- [ ] **최우선**: 태린이아빠 질문지를 사람브레인과 어떻게 연결할지 결정 (위 질문)
- [ ] daily_prep_note 인식조건 좁혀서(숫자형식 명시) v3 재시험
- [ ] relayed_reports 누락 변동성 원인 확인(温度/재시도 필요할수도)
- [ ] STEP4(1차검수, 사용자 확인) → STEP5(정식 Gemini시험, 3~5일) → STEP6(원문대조 검수)
      → STEP7(telegram_channels.json 등록) — 태린이아빠·요약하는고잉 둘 다
- [ ] 요약하는고잉은 event_calendar 슬롯 추가만 하면 됨(변경 작음, 아직 시험 안 함)
- [ ] (사람브레인 자체 잔여작업, 오늘 오전 세션 기록): 비중산출·매도규칙감시·채널더추가

## 관련 파일
- 원자추출 재설계: `docs/superpowers/plans/2026-07-02-원자추출-프로파일-재설계.md`(완료),
  `docs/superpowers/specs/2026-07-02-원자추출-프로파일-재설계-design.md`
- 채널 온보딩 스킬: `.agents/skills/channel-onboard/SKILL.md`
- 사람 브레인: `pipeline/people/`, `project_person_brain` 메모리
- 이번 세션 시험 스크립트(임시, 미커밋): 세션 종료시 삭제됨 — 필요하면 위 v2 프롬프트로 재작성
