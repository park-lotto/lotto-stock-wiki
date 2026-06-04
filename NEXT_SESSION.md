# NEXT SESSION
> 2026-06-04 | 집PC

## 세션 요약
텔레그램 인제스트 파이프라인 완성 + 채널 인사이트 시스템(Pass 2) 설계·구현

---

## ✅ 완료

- `scripts/ingest_crawl.py` 커플링(coupling) 타입 추가 — 해외기업 → 연관 섹터에 [커플링: ...] 자동 분류
- `scripts/ingest_crawl.py` Pass 2 인사이트 추출 로직 추가 — `pass2: true` 채널 → `wiki/insights/{채널}.md` 별도 저장
- `pipeline/channel_registry.json` 생성 — 채널별 타입/처리규칙 등록 구조
- `wiki/insights/` 폴더 + `_consensus.md` 생성
- 2026-06-04 텔레그램 6채널 실제 인제스트 완료 (sector 16 / stock 21 / coupling 16)
- 반도체 오늘 핵심 인사이트 정리: 낸야테크 +730%, 젠슨황 HBM4E 증산요청, 브로드컴 가이던스 미달, TEL +13%→장비주 상한가

---

## ⏳ 미완료 — 다음 세션 최우선

### 채널 레지스트리 등록 대기
사용자가 크롤링 폴더에 채널 전부 넣으면 → 채널별 문항지(3문항) 작성 → `channel_registry.json` 등록

등록 항목:
- `type`: A(증권사공식) / B(큐레이션) / C(섹터전문) / D(인사이트흐름)
- `pass1`: 섹터/종목 wiki 뿌리기 (기본 true)
- `pass2`: 인사이트 별도 저장 (배우고 싶은 채널만 true)
- `specialty`: 전문 섹터
- `trust`: high / medium

### Pass 2 실제 동작 테스트 미완
registry에 `pass2: true` 채널 없어서 아직 실행 안 됨
채널 등록 후 테스트 필요 → `wiki/insights/{채널}.md` 생성 확인

### _consensus.md 자동 집계 로직 미구현
지금은 수동. 추후: 날짜별로 채널별 언급 섹터 집계 → 3개↑ 자동 🔴 플래그

---

## 관련 파일
- `scripts/ingest_crawl.py` — Pass 2 포함 전체 파이프라인
- `pipeline/channel_registry.json` — 채널 등록소
- `wiki/insights/` — 인사이트 누적 폴더 (현재 비어있음)
- `wiki/insights/_consensus.md` — 교집합 신호 집계 (수동)
- `wiki/L5_섹터/반도체/sector_반도체.md` — 오늘 커플링 포함 26개 코멘트 추가

---

## yt-gemini-pipeline 대기
주제: **"반도체만 올랐다, 이제 이 업종이 달린다 — 6월 순환매 핵심 3종목"**
Gemini 브리프 완성. 다음: yt-gemini-pipeline 스킬 실행
