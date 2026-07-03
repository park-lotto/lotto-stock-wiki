# Claude Design System (출처: getdesign.md/claude/design-md)

> 인포그래픽 생성 시 대안 스타일 참고용. 채널 기본 스타일(라임그린/블랙 HUD, `nlm_bridge._BRAND_DESIGN`)과는
> 별개로 보관 — 기본값을 바꾼 게 아니라 실험/비교용 레퍼런스.

## 브랜드 요약
따뜻한 크림 캔버스 위 세리프 디스플레이 헤드라인 + 코랄(산호색) CTA + 다크 네이비 프로덕트 표면(코드 에디터 목업).
쿨톤 블루/슬레이트를 쓰는 다른 AI 브랜드와 달리 크림/코랄 조합으로 따뜻하고 인간적인 톤. h1/h2는 슬랩세리프
디스플레이 폰트(Copernicus / Tiempos Headline), 본문은 휴머니스트 산세리프(StyreneB/Inter).

## 컬러 팔레트 (hex)
- Primary(코랄): `#cc785c` / Primary-active: `#a9583e` / Primary-disabled: `#e6dfd8`
- Ink: `#141413` / Body: `#3d3d3a` / Body-strong: `#252523` / Muted: `#6c6a64` / Muted-soft: `#8e8b82`
- Hairline: `#e6dfd8` / Hairline-soft: `#ebe6df`
- Canvas(크림 배경): `#faf9f5` / Surface-soft: `#f5f0e8` / Surface-card: `#efe9de` / Surface-cream-strong: `#e8e0d2`
- Surface-dark(네이비 계열): `#181715` / Surface-dark-elevated: `#252320` / Surface-dark-soft: `#1f1e1b`
- On-primary: `#ffffff` / On-dark: `#faf9f5` / On-dark-soft: `#a09d96`
- Accent-teal: `#5db8a6` / Accent-amber: `#e8a55a` / Success: `#5db872` / Warning: `#d4a017` / Error: `#c64545`

## 타이포그래피
| 토큰 | 폰트 | 크기 | 굵기 | 행간 | 자간 |
|---|---|---|---|---|---|
| display-xl | Copernicus/Tiempos Headline, serif | 64px | 400 | 1.05 | -1.5px |
| display-lg | 〃 | 48px | 400 | 1.1 | -1px |
| display-md | 〃 | 36px | 400 | 1.15 | -0.5px |
| display-sm | 〃 | 28px | 400 | 1.2 | -0.3px |
| title-lg/md/sm | StyreneB/Inter | 22/18/16px | 500 | 1.3~1.4 | 0 |
| body-md/sm | StyreneB/Inter | 16/14px | 400 | 1.55 | 0 |
| caption | StyreneB/Inter | 13px | 500 | 1.4 | 0 |
| caption-uppercase | StyreneB/Inter | 12px | 500 | 1.4 | 1.5px |
| code | JetBrains Mono | 14px | 400 | 1.6 | 0 |

## 레이아웃/스페이싱
- 기본 단위 4px. 토큰: xxs4·xs8·sm12·md16·lg24·xl32·xxl48·section96
- 섹션 간 여백 96px(에디토리얼 리듬), 카드 내부 여백 24~32px
- 최대 콘텐츠 폭 ~1200px, 12컬럼 그리드, 히어로는 6/6 분할 흔함
- 여백 철학: 크림 캔버스+세리프 디스플레이+넉넉한 내부 패딩 = 매거진 칼럼처럼 읽히는 에디토리얼 페이싱

## Shape / Elevation
- Border radius: xs4·sm6·md8·lg12·xl16·pill/full 9999px
- 그림자는 거의 안 씀 — "color-block first, shadow rare". 깊이는 크림 vs 다크 표면 대비로 표현
- 안트로픽 4방향 스파이크(별표) 마크가 워드마크에 붙음. 다크배경에서 마크 반전 금지

## Do / Don't
**Do**: 크림 캔버스 고정(순백 금지, 크림이 브랜드 차별점) · 디스플레이는 항상 세리프+음수 자간 · 코랄은 CTA/콜아웃에만 희소하게 · 크림카드↔다크목업 밴드를 번갈아 배치 · 섹션 간 96px 유지
**Don't**: 쿨그레이/순백 배경 금지 · 세리프 디스플레이를 bold(700)로 쓰지 않음(400 유지) · 코랄 남용 금지 · 헤드라인에 Inter류 산세리프 금지 · 같은 표면모드를 연속 배치 금지(크림→크림카드→다크목업→크림→코랄콜아웃→다크풋터 순환)
