---
name: project-image-system
description: 보고서·Remotion 영상용 이미지 자동 다운로드 시스템 완성 현황
metadata: 
  node_type: memory
  type: project
  originSessionId: cd1c7c0b-b4de-43f0-85f1-86b4c78a7ffc
---

## 완성된 것 (2026-05-28)

### scripts/download_images.py
- Wikimedia Commons API 기반 이미지 검색·다운로드
- `--query "..."` : 직접 검색어
- `--from-html out/파일.html` : HTML 내용 분석 → 쿼리 자동 생성
- `--from-text "텍스트"` : 텍스트 → 쿼리 자동 생성
- `--dry-run` : 다운로드 없이 목록만 확인
- KR_TO_EN 사전: 한국어 키워드 → Wikimedia 영문 쿼리 자동 변환
- CC 라이선스 확인 + 출처_attribution.txt 자동 생성
- 저장 경로: `raw/images/{slug}/`

### remotion-stock/public/images/ (현재 파일)
- ship_hero.jpg — Maersk 컨테이너선 파노라마 (CC BY 3.0)
- lng_tanker.jpg — CATALUNYA SPIRIT LNG 탱커 (CC BY-SA 4.0)
- jensen_keynote.jpg — Jensen Huang CES 2025 키노트 (CC BY-SA 4.0)
- jensen_profile.jpg — Jensen Huang EU 회의 (CC BY 4.0)
- chart_조선etf.png — KODEX 친환경조선해운액티브 차트 (1151×414)

### Remotion 이미지 씬 컴포넌트 (ImgScene.tsx)
- `ImgHeroScene` : 전체 배경 이미지 + 켄번스 줌인 + 텍스트 오버레이
- `ImgSplitScene` : 좌이미지↔우불릿 순차 등장

### Remotion 차트 씬 (ChartScene.tsx)
- 실제 차트 이미지 위에 오버레이 애니메이션
- ① 스캔 라인 (왼→오 스윕)
- ② 현재위치 서클 (3중 펄스 링)
- ③ 추세 화살표 SVG 드로잉 애니메이션
- ④ 텍스트 레이블 + 자막
- 위치 조정: `DOT_PCT_X`, `DOT_PCT_Y` 두 값만 변경 (0~1 범위)

## 핵심 운영 원칙

**고정 섹터→이미지 매핑 금지.** 보고서 핵심 내용(인물·기업·이벤트·제품)을 분석해 그에 맞는 검색 쿼리 동적 생성.

새 차트 씬 만들 때:
1. 차트 이미지 → `raw/export/` 저장
2. `Copy-Item`으로 `remotion-stock/public/images/` 복사
3. `ChartScene.tsx` 복사 후 `DOT_PCT_X`, `DOT_PCT_Y` 조정

**Why:** NVIDIA 보고서에 젠슨황+로고 넣었을 때 "완전 멋있다" → 모든 보고서/영상에 이미지 적극 활용 확정.
**How to apply:** 보고서/영상 생성 요청 시 → 먼저 download_images.py로 관련 이미지 확보 → HTML/Remotion에 삽입.
