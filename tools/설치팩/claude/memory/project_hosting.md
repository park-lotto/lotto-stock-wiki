---
name: project-hosting
description: GitHub Pages 호스팅 설정 완료. 섹터 마스터 페이지 URL 구조.
metadata: 
  node_type: memory
  type: project
  originSessionId: 5523b3f4-95a5-468f-8912-79dc9112c3c7
---

GitHub Pages 활성화 완료 (2026-06-08).

**Why:** 섹터 마스터 페이지를 URL 하나로 고객에게 전달하기 위해.

**설정:**
- `.github/workflows/pages.yml` — GitHub Actions 자동 배포
- `.nojekyll` — Jekyll 처리 우회
- 레포: `park-lotto/lotto-stock-wiki`
- 베이스 URL: `https://park-lotto.github.io/lotto-stock-wiki/`

**현재 라이브 파일:**
- `out/semi-master.html` → 반도체 마스터 (A안 탭네비, 모바일 최적화)

**URL 구조 계획:**
- `out/semi-master.html` → 반도체
- `out/ship-master.html` → 조선 (미완성)
- `out/robot-master.html` → 로봇 (미완성)
- 도메인 구매 후 `stockbrain.kr/out/semi-master.html` 식으로 연결 예정

**도메인:** 미구매. 가비아(.kr) or Namecheap(.com) 구매 후 나한테 알려주면 10분 연결.

**How to apply:** 새 섹터 페이지 만들면 `out/` 에 저장 후 push만 하면 자동 배포됨.
