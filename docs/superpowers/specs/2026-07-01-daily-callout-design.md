# 오늘의 빈집 포착 + 성과 추적 — 설계 (2026-07-01)

## 목표
유튜브 영상에서 보여주고, 멤버십 회원이 매일 쓰는 히어로 기능.
**찍고(A) → 증명(B)** 루프 = 영상→멤버십 전환 엔진.

## A. 오늘의 빈집 포착
- 로직: `/api/sector_vacuum`(이미 존재: 강한ETF섹터 → 편입종목 → 빈집 percentile 정렬) 재사용
- 전 섹터 통합 랭킹 → **Top3 선정**
  - 점수 = 빈집깊이(낮은 pct↑) + 섹터강도(등락률) + 아직-안-오름(당일 급등 감점)
- **그날 1회 동결** → `pipeline/callouts/YYYY-MM-DD.json` (기준가 KIS 기록)
- 최초 요청 시 자동 생성(스케줄 불필요, 추후 고정시각 가능)
- 화면: /market 최상단 히어로 카드 (종목·섹터·빈집%·오늘등락·한줄근거)

## B. 성과 추적
- 저장분(entry) 대비 현재가로 수익률 재계산 (KIS)
- 성과 로그: 최근 콜아웃 + 적중률 + 평균수익
- 화면: "성과" 탭/모달

## 아키텍처
- 서버 네이티브(빈집 json·KIS·네이버 다 서버 OK) → 키움/릴레이 불필요, 토큰 0
- server.py: `_compute_sector_vacuum(top)` 추출 → sector_vacuum·callout 공용
  - `_generate_callout()` 동결, `/api/callout`, `/api/callout_history`
- 프론트: 히어로 카드 + 성과 뷰

## 프레이밍(안전)
- "매수추천" ❌ → "시스템 포착 후보" ⭕ (면책 1줄)
- 성과는 실제 수치만 (지어내지 않음) = 차별화

## 스키마
```
callouts/2026-07-01.json
{ date, generated_ts, picks:[{code,name,sector,sector_rate,pct,group,entry,change_at_gen,reason}] }
```

## 미정(보면서 수정)
- 동결 시각(최초요청 vs 장마감 고정), Top3 vs Top5, 점수 가중치, 성과 기간(+1/3/5d)
