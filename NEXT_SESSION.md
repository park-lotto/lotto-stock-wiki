# NEXT SESSION — 2026-06-10 아침 시작

**세션 요약 (2026-06-09 집PC)**
조선 섹터 마스터 페이지 완성 + GitHub Pages 배포. Gemini vs Claude 비교 아이디어 논의.

**세션 요약 (2026-06-08 사무PC — 2차)**
반도체 섹터 마스터 완성 + GitHub Pages 호스팅 + 서비스 방향 확정.

**세션 요약 (2026-06-08 사무PC — 1차)**
수급오실레이터700 엑셀 파일 22개 시트 전체 구조 완전 해독.

---

## ✅ 완료된 것 (2026-06-09 세션)

### 조선 섹터 마스터 (ship_master.html)
- `out/ship_master.html` 완성 — 반도체 마스터와 **완전히 동일한 UI**
- 사이드바(PC) + 하단 탭바(모바일) + 7탭 구조
- 7탭: 오늘핵심 / 종목워치 / 이벤트캘린더 / 밸류체인 / 미반영 / 리스크역발상 / 로그
- 종목 클릭 상세 패널 (이평선·수급·키워드 3패널)
- D-155 카운트다운 칩, 5프레임 분석 카드
- **GitHub Pages URL**: `https://park-lotto.github.io/lotto-stock-wiki/out/ship_master.html`
- 커밋: `eb69285`

---

## ✅ 완료된 것 (2026-06-08 세션)

### 반도체 섹터 마스터 + GitHub Pages
- `out/sector_반도체_v2.html` — 8카테고리·미반영인사이트5개·밸류체인·이벤트캘린더·리스크역발상·종목포지셔닝
- 레이아웃 A/B/C 3안 비교 → **A안(탭네비) 확정**
- GitHub Pages 활성화 (`.github/workflows/pages.yml` + `.nojekyll`)
- 모바일 최적화 완료 (터치·탭스크롤·OG메타·반응형)
- **URL**: `https://park-lotto.github.io/lotto-stock-wiki/out/semi-master.html`

### 서비스 방향 확정
- 핵심 차별점: **정보의 정리 + 수급빈집 + 주도섹터 강도**
- 구조: 채널(유튜브) = 개념 교육 / 서비스 = 매일 결과물
- 섹터별 파일 하나씩 → 도메인 하나에 경로로 (`stockbrain.kr/semi` 등)

---

## ⚡ 다음 세션 할 것 (우선순위 순)

### 0. 도메인 구매 + 연결
- 가비아(한국) or Namecheap에서 `.kr` or `.com` 구매
- 구매 후 도메인 이름 알려주면 10분 안에 GitHub Pages 연결

### 1. 조선 딥리서치 3라운드 → ship_master.html placeholder 채우기

```
1라운드 (3개 동시):
  - FLNG 시장 전체: 삼성중공업 독점 근거·시장규모·모잠비크 입찰
  - 캐나다 함대 현대화: 잠수함·해군 발주 한국 조선소 참여 현황
  - 핵잠수함 / AUKUS: 한국 방산 조선 연계 기회

2라운드 (3개 동시):
  - FLNG MRO: 10~20년 장기 정비 계약 시장 규모·수익성
  - 부유식 데이터센터: 실제 발주 현황·조선소 경쟁력·시장 규모
  - 조선엔진 AI: HD현대 엔진 AI 기술 현황·수주 영향

3라운드 (2개):
  - 리스크 검증: Section 301 유예 연장 가능성·시나리오
  - 미해군 MRO: 한국 조선소 미군함 정비 수주 현황
```

### 2. 반도체 브리핑 인사이트 — Claude vs Gemini 비교
- 위키 + WebSearch로 인사이트 뽑기
- Gemini CLI 설치 여부 확인 (`gemini --version`)
- 동일 프롬프트 → Claude / Gemini 동시 호출 → 나란히 비교
- 목적: 어느 쪽이 투자 인사이트 퀄리티가 더 나은지 확인

### 3. sector-v5.html 검색 기능 제거
- searchInput, search-wrap, 관련 CSS/JS 전부 삭제

### 4. 종목 워치 태린이 파일 실데이터 연동
- ship_master.html 종목 패널의 이평선·수급빈집 수동 입력 → 자동화 검토

---

## 📁 관련 파일

- `ship_master.html` → `out/ship_master.html`
- `semi-master.html` → `out/semiconductor_master.html`
- `sector-v5.html` → `.superpowers/brainstorm/34-1780845638/content/sector-v5.html`
- `analysis_rules.md` → `wiki/rules/analysis_rules.md` (§-1 추가됨)
- 딥리서치 결과물 → `out/딥리서치/` 저장 예정

---

## 💡 나중에 (지금 아님)

- 멀티섹터 포털 페이지에 크로스 검색 달기
- 키워드 세트 JSON 만들어 크롤링봇 연동
- 반도체·방산·원전 섹터 동일 구조 복제
- AI Q&A 박스 (딥리서치 데이터 기반 자연어 질의)
