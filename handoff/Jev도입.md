# Jev도입 — 핸드오프

## 2026-10-21 (CH PC)
**무엇**: TypeSafe AI의 판단전용 모델 Jev(Choice/Score/Noul/Box 확률 반환, 글 생성 X) 조사·설치.

**완료**
- 조사: 공식 문서(docs.typesafe.ai, `.md` 붙여 curl) · 공식 GitHub · awesome-jev · 유튜브 7편 자막
- 설치(프로젝트 밖 `C:\Users\CH\jev-lab`):
  - Python SDK `typesafe-sdk` 0.7.5 (`.venv`) + `jev_test.py` (TYPESAFE_API_KEY)
  - JS AI SDK `ai` 7.0.146 + `jev_test_vercel.js` (Vercel AI Gateway, `experimental_decide`, 모델 `typesafe-ai/jev`)
  - Claude Code 플러그인 `typesafe@typesafe-ai` 0.5.7 (user 범위, enabled)
- 가이드: `out/Jev_활용가이드.html` (원본 `C:\Users\CH\jev-lab\Jev_활용가이드.html`)

**막힌 곳 (실측)**
- TypeSafe 콘솔: 크레딧 0이라 키 생성 불가("Add credits in Billing"). 무료 크레딧은 현재 없음(공식 문서 언급 없음, 계정 잔액 0)
- Vercel AI Gateway: 키는 `jev-lab\.env`에 저장·인증 통과. 요청 시 `customer_verification_required` — **카드 등록해야 월 5달러 무료 크레딧 열림**
- ⚠️ 게이트웨이 키를 사장님이 채팅에 붙임 → 시험 후 Vercel에서 재발급 권장

## ⏭ 다음
1. 사장님 카드 등록(Vercel) 또는 TypeSafe 충전 → `node --env-file=.env jev_test_vercel.js`
2. 한국어 정확도 측정: 텔레그램 뉴스 50건 정답셋, 영어 지시문 vs 한국어 지시문 A/B (공식: 한국어 약함)
3. 붙일 곳 1개 선정(뉴스 1차 선별 / 레퍼런스 영상 선별 / 훅 점수 후보)
