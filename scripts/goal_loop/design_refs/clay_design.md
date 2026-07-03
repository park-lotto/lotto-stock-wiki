# Clay.com Design System (출처: getdesign.md/clay/design-md → GitHub raw + clay.com 실사이트 확인)

> 인포그래픽 브랜드 스타일 실험 3번째 결과물. `brand="clay"` 프리셋으로 등록됨(nlm_bridge.py
> BRAND_STYLE_PRESETS). 이미지 레퍼런스 3장(clay_ref1_sculptor.png, clay_ref2_audiences.jpg,
> clay_ref3_ads.png — clay.com CDN에서 직접 다운로드한 실제 브랜드 3D 클레이 일러스트) 사용,
> 텍스트 지침만으로도 잘 재현됨. 결과: 3D 클레이메이션 일러스트 + 채도색 카드 순환 + 크림 배경이
> 그대로 나옴(2026-07-03 secondary 계정으로 성공 확인, 텔레 전송 완료).

## 브랜드 요약
크림빛 화이트 캔버스 + 다크네이비 프라이머리 CTA + 커스텀 둥근 디스플레이 타이포 + 채도 높은
단색 피처카드(핑크/틸/라벤더/피치/오커 6색). 3D 렌더링 클레이메이션 일러스트(산·캐릭터·마스코트)가
풀블리드 히어로로 쓰여서 경쟁사들의 쿨그레이 데이터플랫폼 미학과 확실히 차별화됨.

## 컬러 팔레트 (hex)
- Primary: `#0a0a0a` / Primary-active: `#1f1f1f` / Primary-disabled: `#e5e5e5`
- Brand: pink `#ff4d8b` · teal `#1a3a3a` · lavender `#b8a4ed` · peach `#ffb084` · ochre `#e8b94a` · mint `#a4d4c5` · coral `#ff6b5a`
- Canvas(크림배경): `#fffaf0` / Surface-soft: `#faf5e8` / Surface-card: `#f5f0e0` / Surface-strong: `#ebe6d6`
- Surface-dark: `#0a1a1a`(드묾) / Hairline: `#e5e5e5`
- Ink: `#0a0a0a` / Body: `#3a3a3a` / Muted: `#6a6a6a`

## 타이포그래피
- 디스플레이: Plain Black(커스텀 둥근 폰트) 굵기 500, 절대 700(bold) 금지 — 음수 자간
- 본문/UI: Inter. Plain Black 없으면 Inter 500 + 음수자간(-0.05em)으로 대체
- display-xl 72px/500/-2.5px ~ display-sm 32px/500/-0.5px, body-md 16px/400

## 레이아웃/스페이싱
- 기본단위 4px, 섹션간 96px 리듬. 최대폭 ~1280px, 12컬럼(히어로는 7:5 분할)
- 피처카드 3-up 데스크탑, 카드내부패딩 32px

## Shape/Elevation
- Radius: 카드 24px(피처카드), 16px(콘텐츠카드), pill 9999px
- 그림자 거의 없음 — 깊이는 크림배경 vs 채도색카드의 색 대비로만. 3D 클레이 일러스트가 signature 깊이 요소

## Do/Don't
**Do**: 크림 캔버스 고정 · 피처카드는 핑크→틸→라벤더→피치→오커 순환(연속 반복 금지) · 3D 클레이메이션을 히어로/마스코트로 · 풋터도 크림(다크풋터 금지, Clay는 끝까지 따뜻하게 마무리)
**Don't**: 쿨그레이 배경 금지 · 7번째 브랜드컬러 추가 금지(6색으로 충분) · 디스플레이 bold(700) 금지 · 평면 벡터로 클레이일러스트 대체 금지(손빚은 3D여야 함)

## 참고 이미지 (clay.com CDN, 로컬 저장)
- `clay_ref1_sculptor.png` — 3D 클레이 구체 아이콘(블루/핑크/옐로우)
- `clay_ref2_audiences.jpg` — 오렌지 배경 위 제품 UI 목업 카드
- `clay_ref3_ads.png` — 3D 클레이 아이콘(블루/오렌지)
