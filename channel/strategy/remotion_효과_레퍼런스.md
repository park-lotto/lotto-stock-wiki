# Remotion 효과 레퍼런스 — T3CHFEED 스타일

> 2026-06-14 정리 | 카카오×Claude 영상 기획 중 수집·구현

---

## 1. DocHighlightScene — 크롭+줌+형광펜
**상태: ✅ 구현 완료** (`src/scenes/DocumentHighlightScene.tsx`)

```
용도: 문서·스크린샷에서 특정 줄/영역 형광펜 강조 후 줌인
레이어: 이미지 → 크롭+줌(transform scale+translate) → 형광펜 bar
```

| 속성 | 값 |
|------|-----|
| 형광펜 색 | `#FFE500`, opacity 0.52 |
| 등장 | `spring()` elastic |
| 줌 방식 | `scale(S) translate(tx%, ty%)` — clip-path 아님 |
| 컴포넌트 | `DocumentHighlightScene` (단일) / `DocPanScene` (멀티 팬) |

**쓰는 씬**: S5(Claude 설치) / S7(PlayMCP 스위치) / S8(브리핑 결과) / S10(플러그인)

---

## 2. FocusZoom — 블러 배경 + 카드 중앙 이동 + 살짝 확대
**상태: ✅ 구현 완료** (`src/scenes/FocusZoomDemo.tsx`)

```
용도: 화면의 핵심 문장/영역만 선명하게 부각, 나머지 흐리게
레이어: 블러 배경 전체 | 선명 카드(overflow hidden으로 클립) | 테두리
```

| 속성 | 값 |
|------|-----|
| 배경 블러 | `filter: blur(9px) brightness(0.42)` |
| 카드 이동 | box 중심 → 캔버스 중심 (translateY: -189px 예시) |
| 확대 배율 | **1.22×** (너무 크면 안 됨) |
| 이동 애니 | `spring({ damping: 18, stiffness: 160 })` |
| 테두리 | `2px solid rgba(255,255,255,0.88)` + boxShadow |

**핵심 공식**:
```
translateY = 캔버스중심Y(540) - 박스중심Y
cardTransform = `translate(0, ${translateY}px) scale(1.22)`
```

**쓰는 씬**: S3(철학 선언) / S8(프롬프트 ③번) / S11(응용 카드 강조)

---

## 3. TechFeedScene — 실화면 배경 + 한국어 오버레이
**상태: ✅ 구현 완료** (`src/scenes/TechFeedScene.tsx`)

```
용도: 실제 웹/앱 화면을 배경에 깔고 한국어 설명 텍스트를 stagger로 올림
레이어: 스크린샷(brightness 0.35) | 한국어 텍스트 stagger | 하단 자막바
```

| 속성 | 값 |
|------|-----|
| 배경 밝기 | `brightness(0.35)` |
| 텍스트 간격 | 22프레임 간격 stagger |
| 텍스트 등장 | `translateY(14→0) + opacity(0→1)` 14프레임 |
| 자막바 | 하단 고정, `rgba(0,0,0,0.82)` |
| 레이아웃 | 좌=레이블 / 우=설명 (분류 | 내용 형식) |

**쓰는 씬**: S5(Claude 설치) / S6(PlayMCP) / S7(연결 실연) / S8(프롬프트) / S10(플러그인)

---

## 4. ImpactText — 어두운 배경 + 큰 임팩트 숫자/텍스트
**상태: 🔧 미구현 (씬 내 인라인으로 사용)**

```
용도: 숫자·통계·핵심 한 줄을 화면 꽉 채워 임팩트 있게 표시
레이어: 어두운 배경(영상 or 검정) | 큰 텍스트(자간 넓게) | 선택적 글로우
```

| 속성 | 값 |
|------|-----|
| 배경 | Pexels 영상 or `#000` |
| 글자 크기 | 120~160px |
| 자간 | `letterSpacing: 12~20px` |
| 색상 | 흰색 or 민트(`#00FFB0`) 글로우 |
| 등장 | opacity + scale `0.9 → 1.0` spring |

**쓰는 씬**: S1 훅 "제가 한 건 없습니다" / S2 "매일 20분" / S12 "어제 30분 → 매일"

---

## 5. HubDiagram — 중앙 허브 + 서비스 아이콘 + 화살표 드로잉
**상태: 🔧 미구현**

```
용도: MCP 개념 설명 — Claude가 여러 서비스에 연결되는 구조 시각화
레이어: 어두운 배경 | 중앙 허브 아이콘(펄스) | 방사형 화살표 드로잉 | 서비스 아이콘
```

| 속성 | 값 |
|------|-----|
| 화살표 | SVG `stroke-dashoffset` 드로잉 애니메이션 |
| 허브 | `scale + glow pulse` 반복 |
| 등장 순서 | 허브 먼저 → 화살표 순차 → 아이콘 순차 |
| 참고 | T3CHFEED 스타링크 위성 다이어그램 씬 |

**쓰는 씬**: S6 MCP 개념 인서트

---

## 6. SplitScreen — 좌우 분할 동시 비교
**상태: 🔧 미구현 (CSS flexbox로 즉시 구현 가능)**

```
용도: 두 화면(Claude 좌 / 카카오톡 우)을 동시에 보여줌
레이어: 좌 패널(width 50%) | 구분선 | 우 패널(width 50%)
```

| 속성 | 값 |
|------|-----|
| 구분선 | `1px solid rgba(255,255,255,0.2)` |
| 레이블 | 각 패널 상단 작은 텍스트 |
| 등장 | 좌 패널 먼저 → 우 패널 slide-in |

**쓰는 씬**: S7 PlayMCP 연결 실연 / S8 프롬프트 실행 결과

---

## 7. LogoIntro — 채널 로고 인트로
**상태: 🔧 미구현 (로고 파일 필요)**

```
용도: T3CHFEED 스타일 채널 인트로 (영상 시작 3~4초)
레이어: 검정 배경 | 로고 elastic 등장 | 채널명 fade in | 효과음
```

| 속성 | 값 |
|------|-----|
| 로고 등장 | `spring({ damping: 10, stiffness: 200 })` scale 0→1 |
| 채널명 | fade in, `letterSpacing: 4px` |
| 배경 | `#000` or 어두운 테크 영상 |
| 효과음 | Remotion `<Audio>` 컴포넌트로 정확한 프레임 트리거 |
| 참고 | T3CHFEED: 음파 웨이브 로고 + 흰 텍스트 |

**쓰는 씬**: S0-B 채널 인트로

---

## 제작 공통 원칙

```
배경 영상: Pexels 무료 (검색어: "dark tech", "stock market", "smartphone dark")
배경 어둡기: brightness(0.3~0.45) — 너무 어두우면 맥락 잃음
텍스트 그림자: textShadow: '0 2px 12px rgba(0,0,0,0.85)' — 가독성 확보
Spring 기본값: damping 14~18, stiffness 160~200, mass 0.7~0.9
자막바: 항상 하단 고정, height 74px, rgba(0,0,0,0.82)
해상도: 1920×1080, 30fps
```

---

## 씬별 효과 매핑 (카카오×Claude 영상)

| 씬 | 효과 |
|----|------|
| S0-B 로고 인트로 | LogoIntro |
| S1 훅 | DocHighlight + ImpactText |
| S2 페인포인트 | ImpactText + stagger |
| S3 철학 선언 | FocusZoom (비교형) |
| S4 로드맵 | 순수 Remotion 플로우 그래픽 |
| S5 Claude 설치 | TechFeed + DocHighlight |
| S6 MCP 개념 | ImpactText + HubDiagram |
| S7 PlayMCP | TechFeed + SplitScreen + DocHighlight |
| S8 프롬프트 | TechFeed + FocusZoom + SplitScreen + DocHighlight |
| S9 스케줄 | DocHighlight |
| S10 플러그인 | TechFeed + DocHighlight |
| S11 응용 아이디어 | stagger 카드 + FocusZoom |
| S12 수미상관 | DocHighlight + ImpactText |
| S13 CTA | 순수 Remotion 클로징 |
