# NEXT SESSION

> 날짜: 2026-06-07 | PC: 집PC

## 세션 요약

경쟁 채널 "로보, AI 활용해서 살아남기" 전수 분석 (17개 VTT 자막).
수익 모델 역설계 → 17편 영상제작 플랜 → 고객 전달 모델 전략 수립.

---

## 완료 항목

- [x] 경쟁채널 분석 리포트 작성 — `channel/yt/competitor_analysis_로보.md`
- [x] 상세 분석 (Hook 9패턴, 수익모델, 퍼널) — `channel/yt/competitor_analysis_로보_상세.md`
- [x] 17편 영상제작 플랜 (레퍼런스→우리버전 1:1 매핑) — `channel/yt/영상제작_플랜_로보벤치마킹.md`
- [x] 경쟁사 수익모델 확정: 4가지 자동화 강의 + 1:1 코칭 + 카카오 단톡방 DB 수집
- [x] 영상 제작 방식 결정: Type A(실사화면녹화) / B(Remotion) / C(혼합)
- [x] 고객 전달 3단계 모델 설계: 텔레채널 → 캐시봇 → 개인화
- [x] Perplexity Pro vs Claude WebSearch 비교: Pro UI = 한국 실시간 뉴스, Claude = 파이프라인

---

## 미완료 / 다음 할 것

### 우선순위 1 — 첫 영상 제작 (EP15)
- [ ] **OBS Studio 설치** — 화면 녹화 환경 세팅 (마우스 하이라이트 플러그인 포함)
- [ ] **EP15 촬영** — daily_scenario.py 실행 → 오늘 아침 시스템 결과물 화면 녹화
  - 시스템 장면: Claude Code 터미널 → 브리핑 카드 생성 → 텔레그램 전송
  - 파일: `channel/yt/영상제작_플랜_로보벤치마킹.md` EP15 항목 참조
- [ ] **핵심 대사**: "로보는 ChatGPT한테 이렇게 물어보세요를 알려줍니다. 저는 ChatGPT한테 물어볼 필요 없는 시스템을 보여드립니다"

### 우선순위 2 — 텔레그램 채널 오픈 (고객 전달 1단계)
- [ ] **텔레그램 채널 개설** — 구독자 0명부터 시작, 첫 브리핑 발송
- [ ] **채널봇 연결** — 기존 assistant_bot을 채널 발송용으로 연동
- [ ] **첫 콘텐츠**: 오늘 daily_scenario.py 결과 → 채널 발송

### 우선순위 3 — Gemini API 키 수정
- [ ] **Gemini MCP API 키 무효** — `400 INVALID_ARGUMENT` 오류 발생
  - `.mcp.json` 또는 환경변수에서 GEMINI_API_KEY 재설정 필요

### 우선순위 4 — 기존 미완
- [ ] assistant_bot 상시실행 Task Scheduler 등록
- [ ] 첫 브리핑 풀플로우 검증 (6/9 화요일, 6/9 월 휴장)
- [ ] Perplexity Pro 구독 결정 ($18/월, UI 전용 한국 실시간 뉴스)

---

## 핵심 결정 사항

1. **경쟁 우위 핵심 대사**: "로보는 방법을 판다. 우리는 결과(수급 신호)를 팔 수 있다"
2. **영상 우선순위**: EP15(아침시스템) > EP08(빈집탐색) > EP03(오실레이터) > EP07(대장주) > EP10(텔레봇)
3. **고객 전달 모델**: Pre-compute → cache → bot 전달 (Claude API 쿼리당 비용 없음)
4. **도구 역할 분담**: Perplexity Pro = 한국 실시간 뉴스 UI / Claude Code = 파이프라인 허브
5. **제작 스타일 확정**: 실사 시스템 화면(OBS) + 보이스오버. Remotion은 데이터 시각화 특별편만

---

## 관련 파일

| 파일 | 경로 |
|------|------|
| 경쟁채널 분석 | `channel/yt/competitor_analysis_로보.md` |
| 상세 분석 | `channel/yt/competitor_analysis_로보_상세.md` |
| 17편 영상제작 플랜 | `channel/yt/영상제작_플랜_로보벤치마킹.md` |
| 채널 전략 | `channel/yt/yt_전략_채널방향.md` |
