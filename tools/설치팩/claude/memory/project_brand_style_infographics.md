---
name: project-brand-style-infographics
description: NotebookLM 인포그래픽에 실제 브랜드(클로드/클레이 등) CI/BI 스타일 입히는 실험 진행상황
metadata: 
  node_type: memory
  type: project
  originSessionId: 1e215eb0-3ee6-4c66-8b01-6ddf65a7d711
---

골루프 인포그래픽(`scripts/goal_loop/notebook_stage0.py` → `nlm_bridge.create_infographic`)의
기본 스타일은 라임그린+블랙 HUD(`_BRAND_DESIGN`). 여기에 실제 유명 브랜드 CI/BI를 입히는 실험을
2026-07-03에 진행, `BRAND_STYLE_PRESETS` dict(`scripts/nlm_bridge.py`)에 프리셋으로 등록.

**등록된 프리셋**
- `claude`: 크림(#faf9f5)+코랄(#cc785c) 에디토리얼, 세리프 헤드라인. getdesign.md/claude 참고.
- `claude_terminal`: 다크 차콜 배경+코랄 아웃라인 픽셀폰트+터미널창(점3개) — Claude Code CLI 스크린샷 참고, 텍스트 지침만으로도 재현 확인.
- `clay`: 3D 클레이메이션 일러스트+채도색 카드 순환(핑크/틸/라벤더/피치/오커)+크림배경. clay.com 실사이트+getdesign.md/clay 참고, 이미지 레퍼런스 3장을 노트북 소스로 추가해서 성공.

**핵심 교훈**
- `create_infographic()`은 원래 커스텀 focus를 줘도 항상 `_BRAND_DESIGN`(라임그린)이 같이 붙어서 스타일이 섞이는 버그가 있었음 → `brand=` 파라미터 추가로 완전 대체 가능하게 고침.
- 실제 브랜드 이미지를 노트북 소스로 추가하면(`nlm source add --file`) 텍스트 지침만보다 재현도가 눈에 띄게 올라감 — 앞으로 새 스타일은 이미지 레퍼런스 필수로 챙길 것. [[feedback_brand_style_workflow]]
- `studio status` 폴링 버그(최신순 응답인데 `arts[-1]`로 예전항목 오판) 발견·수정함.
- `nlm download infographic` CLI가 `--profile` 옵션 자체를 지원 안 함(create/status는 지원) — 다른 계정 노트북 다운로드 시 `nlm login switch <profile>`로 기본프로필 임시전환 후 다운로드, 즉시 원복하는 우회 필요.
- 계정 2개(parklotto12=default, parklotto20=secondary) 운용 중 — 하나가 rate limit(RESOURCE_EXHAUSTED) 걸리면 다른 계정으로 즉시 전환 가능.

**참고 파일**: `scripts/goal_loop/design_refs/{claude,clay}_design.md`(스펙 요약), `scripts/goal_loop/design_refs/clay_images/`(clay.com CDN 원본 이미지 3장)

**다음 단계**: 애플/구글 등 추가 스타일은 [[feedback_brand_style_workflow]] 절차(질문지 먼저) 따라 진행.
