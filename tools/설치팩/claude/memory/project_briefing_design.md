---
name: project-briefing-design
description: "아침 브리핑 HTML 디자인 시스템 — 레이아웃 철학, 파일 위치, 미결 작업"
metadata: 
  node_type: memory
  type: project
  originSessionId: e3e6a8d2-ff6a-4705-b33c-793f4b8edde7
---

## 섹터 브리핑 카드 v2 현황 (2026-06-05)

### v2 구조 (out/sector_v2_반도체.html)
- **판단 배지**: 관망/매수준비/주의 — 헤더 우측 크게 표시
- **SIGNAL BAR**: 오실레이터 수치 + 빈집강도(별점) + 외인/기관 방향 + 보조지표 한 줄
- **이슈카드**: 기존 + 주가반응 칩 추가 (이 뉴스 나왔을 때 실제 주가 반응)
- **종목카드**: 수급 4종 신호 + 0~10점 게이지 + 진입조건/탈출기준 박스

### v2 피드백: "와닿지 않는다"
구조는 맞는 방향이나 내용이 아직 공허함. 미결 방향:
- A. 디자인 심플화 / B. 실제 데이터 연결 / C. 포맷 변경 / D. 트레이더 말투
→ 다음 세션에서 방향 확인 후 재시도

### 생성된 카드 파일
- `out/sector_briefing_로봇.html` / `반도체.html` / `우주.html` (v1)
- `out/sector_v2_반도체.html` (v2 시안)

---

## 아침 브리핑 HTML 디자인 현황 (2026-06-03)

### 확정된 디자인 토큰
- 배경(다크): #080808 / 배경(베이지): #F7F2EA
- 강조: #e8b84b (골드), 베이지에선 #A87020
- 폰트(현재): Black Han Sans (헤드라인) + Noto Sans KR (본문) + Geist Mono (수치)
- 너비: 800px 고정 (Telegram/Kakao 공유용)

### 파일 위치
- `out/morning_v2.html` — 최신 버전 (다크/베이지 토글 포함)
- `out/font_sample.html` — 폰트 샘플 20종 (내일 선정 예정)
- `out/morning_dark_v2.png` / `out/morning_beige_v2.png` — 캡처본

### 현재 레이아웃 구조 (v2)
1. STOCK BRAIN 헤더 (로고 + 브랜드명 + 날짜/시간)
2. 오늘의 판단 (Black Han Sans 34px 헤드라인)
3. 탑픽 3종 카드 (3컬럼 그리드)
4. 수급방향 + 섹터온도 (2컬럼)
5. 글로벌 컨텍스트 바 (6개 지표 한 줄)
6. 리스크 경고
7. 푸터

### 테마 토글 구현
- `data-theme="dark"` / `data-theme="beige"` 속성으로 CSS 변수 전환
- 버튼: `.theme-toggle` (캡처 시 `display:none` 처리)

### 미결 작업 (내일 이어서)
1. **폰트 선정** — font_sample.html 20종 중 1개 선택 → morning_v2.html 적용
   - 현재 후보: Black Han Sans(굵은 고딕), Noto Serif KR(명조계), 콘트라스트 믹스(19번) 유력
2. **디자인 확정** — 선정 폰트로 다크/베이지 최종 PNG 재캡처 + 텔레그램 재발송
3. **DESIGN.md** 작성
4. **자동 생성 파이프라인** 연결 (wiki 데이터 → HTML 자동 채우기)

### 스킬 파이프라인 (확인됨)
`design-consultation` → `design-html` → `design-review`
= 레이아웃 → 디자인 → 마감 (3단계)

### PNG 캡처 방법 (검증됨)
```python
# html_to_png.py --file 은 firstElementChild만 잡혀서 부정확
# 아래 방식 사용:
page.evaluate('document.body.scrollHeight')  # 전체 높이 측정
```

### 텔레그램 전송 방법 (검증됨)
```python
requests.post(f'https://api.telegram.org/bot{token}/sendPhoto', ...)
# sys.stdout.reconfigure(encoding='utf-8') 필수 (Windows cp949 오류 방지)
```
