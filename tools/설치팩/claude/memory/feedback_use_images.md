---
name: feedback-use-images
description: 모든 보고서·브리핑 카드·템플릿에 이미지를 적극 활용해야 함
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cd1c7c0b-b4de-43f0-85f1-86b4c78a7ffc
---

모든 HTML 보고서, 브리핑 카드, 섹터 대시보드 생성 시 관련 이미지(인물 사진, 로고, 제품 이미지)를 적극 포함할 것.

**Why:** report_nvidia_sample.html에서 젠슨황 히어로 이미지 + 원형 프로필 + NVIDIA 로고를 넣었더니 "완전 멋있다"는 반응. 텍스트만인 기존 보고서 대비 시각적 완성도가 크게 올라감.

**How to apply:**
- 고정 섹터→이미지 매핑 금지. 보고서 핵심 내용(핵심 인물·기업·이벤트·제품)을 분석해 그에 맞는 검색 쿼리를 생성할 것.
- 예: HBM4 리포트 → "SK Hynix HBM4 memory" / 테슬라 Dojo → "Tesla Dojo supercomputer" / 조선 수주 → "HD Hyundai shipyard"
- `scripts/download_images.py --query "..."` 로 동적 검색 후 가장 관련성 높은 이미지 선택
- 인물 → 원형 프로필, 기업 로고 → 배너, 이벤트·제품 사진 → 히어로 이미지
- 출처_attribution.txt를 HTML 풋터에 반드시 명시
- Wikimedia Commons(CC 라이선스) 우선 사용
