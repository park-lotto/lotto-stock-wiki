---
name: sector-dashboard
description: "섹터별 HTML 대시보드 + 브리핑 카드 개발 현황 — 반도체·조선 완성, 나머지 미착수"
metadata: 
  node_type: memory
  type: project
  originSessionId: a04ff25f-9e80-47fd-8bd9-8334dda16b53
---

## 현재 상태 (2026-05-24 기준)

### 완성된 파일

| 파일 | 용도 | 상태 |
|------|------|------|
| `out/sector_dashboard_반도체.html` | 반도체 풀 대시보드 (풀스크린) | ✅ 완성 |
| `out/sector_dashboard_조선.html` | 조선 풀 대시보드 | ✅ 완성 |
| `out/briefing_반도체.html` | 반도체 배포용 브리핑 카드 (800px) | ✅ 완성 |

### 미착수

- `out/sector_dashboard_전력기기.html`
- `out/sector_dashboard_2차전지ESS.html`
- `out/sector_dashboard_방산.html`
- `out/briefing_조선.html` (+ 전력기기, 2차전지ESS, 방산)

---

## 대시보드 레이아웃 (확정)

```
[sticky header] STOCK BRAIN | {섹터명} | 날짜 | 무드칩
[Market Summary] 4열: 핵심신호 / 오늘기회 / 체크포인트 / 결론
[상단 4분할 tbox] 국내커플링 / 뉴스매칭 / 당일리포트탑픽 / 수급빈집탑픽
[크로스체크 4열] L1~L4
[서브섹터 레이더] ss-a(민트) / ss-w(레드) / ss-q(회색)
[메인 grid: 1fr 300px]
  좌: 미국커플링전광판 → 테마 → 수출+컨센서스(2열) → 수급오실레이터 → 뉴스피드 → 지속이벤트 → 캘린더 → 밸류체인
  우(sticky): 이벤트 타임라인
```

## 브리핑 카드 레이아웃 (확정)

```
[헤더 50px] 브랜드 도트 + STOCK BRAIN | 섹터명 | 날짜 | 무드뱃지
[시그널스트립 40px] SIGNALS │ hot │ hot │ mid │ off │ bad
[① 인사이트 130px] 민트 라벨 + 좌3px 액센트 블록
[② 뉴스 150px] 3줄 아이템 (시간/태그/헤드라인/종목칩)
[③ 2열 190px] 리포트탑픽(순위원+18px점수) | 수급빈집
[수출바 42px] 발표일만 표시 — 슬롯형 4개 수치
[④ 테마 3열 150px] 강세카드 2개 + 약세카드 1개
[푸터 38px]
총 ~900px — 한 화면 캡처
```

**배포**: PNG (브라우저 "전체 페이지 캡처") → 텔레/카톡

---

## 디자인 토큰 (공통)

```css
/* 대시보드 */
--bg: #080808, --card: #111111, --main: #00FFD0, --red: #FF4B4B
accent: mint=긍정/강세 | red=위험/약세 | yellow=#FFD600 점수2위

/* 브리핑카드 */
body bg: #03030c + 그리드패턴(mint 022%, 48px)
card: linear-gradient(162deg, #0d0d1c → #070710)
card border: rgba(0,255,208,0.16) + 60px glow
text: t0=#fff / t1=#ccc / t2=#888 / t3=#444 / t4=#252535
```

---

## 섹터별 wiki 파일 구조 (L5_섹터/)

```
L5_섹터/
  index.md                  ← 섹터 온도 인덱스 (매 ingest 업데이트)
  반도체/
    index.md                ← 섹터 일일 상태 (반도체+장비+기판소재 통합)
    테이블.md               ← 18개 서브섹터 × 종목 매핑 (고정 참조)
  조선/
    index.md
    테이블.md               ← 10개 서브섹터 × 종목 매핑
  전력기기/ (index.md + 테이블.md)
  2차전지ESS/ (index.md + 테이블.md)
  방산/ (index.md + 테이블.md)
```

**중요**: 반도체장비, PCB기판소재는 별도 섹터 폴더 없음 → 반도체/ 안에서 서브섹터로 관리

---

## 스펙 문서 위치

- 브리핑카드: `channel/strategy/briefing_카드_디자인스펙.md`
- 대시보드 디자인시스템: `channel/strategy/dashboard_디자인시스템.md`

**Why:** 유튜브 채널 "로또의 주식" 텔레/카톡 단톡방 배포용 인사이트 카드. 매일 섹터 브리핑을 PNG 한 장으로 공유.

**How to apply:** 새 세션에서 "브리핑" 또는 "대시보드" 요청 오면 이 파일 + 스펙 문서 먼저 확인 후 기존 디자인 언어로 이어서 제작.
