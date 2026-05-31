# Remotion 스타일 레퍼런스 — 국민성장펀드

> 저장일: 2026-05-31
> 파일 위치: `remotion-stock/src/buildup/GB01~GB06, GB03_5`
> 이 레퍼런스는 새 영상 제작 시 "국민성장펀드 스타일로"라고 하면 이 규격을 따른다

---

## 핵심 스타일 특징

### 색상 팔레트 (`constants.ts` 기반)
```
배경:     #000000 (순수 검정)
메인:     #00FFD0 (네온 틸)
서브텍스트: #888888
카드배경:  #111111
위험색:   #FF4336 (상승/경고)
안전색:   #2196F3 (하락/중립)
amber:   #FFB800 (조건/주의)
```

### 이모지 · 텍스트 규격
| 요소 | 크기 |
|------|------|
| 씬 대표 이모지 | 100~140px |
| 메인 타이틀 | 90~160px · fontWeight 900 |
| 서브 타이틀 | 36~52px · fontWeight 600~800 |
| 카드 내 이모지 | 52~72px |
| 카드 내 제목 | 24~36px |
| 자막 바 | 36~40px |

### 레이아웃
- 콘텐츠 영역: 상단 0 ~ 하단 16% (자막 바 제외)
- 자막 바: 하단 16% 고정
- 패딩: 좌우 80~120px

### 진입 효과
| 효과 | 용도 |
|------|------|
| 수평 스캔라인 (위→아래) | Phase 전환 시 |
| 수직 스캔라인 (좌→우) | 리스트형 씬 |
| 크로스 스캔 (가로+세로) | 클라이맥스 전환 |
| 대각선 스윕 30° | CTA 씬 |
| 글로우 버스트 (radial expand) | 임팩트 순간 |

### 텍스트 애니메이션
| 패턴 | 설명 |
|------|------|
| X슬라이드 ±200px | 좌우 교차 등장 |
| Y슬라이드 +30~60px | 위에서 내려오기 |
| letterSpacing 18→0 | 자간 압축 |
| elastic(1.2) scale | 수치·뱃지 팝 |
| breathe (sin 0.08) | 완전 등장 후 미세 호흡 |

### 이모지 동적 효과
- 등장: `elastic(1.2)` scale 0.3→1
- 유지: `sin * 0.015 + 1` breathe
- 순환 글로우: 60~72프레임 주기로 카드 순환 하이라이트
- GLOW.strong.filter: `drop-shadow(0 0 12px #00FFD0)`

### 자막 바 패턴
```tsx
// 하단 16% 고정. 여러 자막 position:absolute로 겹치고 opacity로 전환
<div style={{ position:'absolute', bottom:0, left:0, right:0, height:'16%', ... }}>
  <div style={{ position:'absolute', opacity: cap1, fontSize:36~40, fontWeight:700 }}>
    일반 텍스트 <span style={{ color: C.main }}>강조 텍스트</span>
  </div>
</div>
```

### Phase 전환 공식
```ts
const fi = (fa, fb) => (f) => interpolate(f, [fa, fb], [0,1], { clamp })
const fo = (fa, fb) => (f) => interpolate(f, [fa, fb], [1,0], { clamp })

// 예: ph1 = 0~390 들어오고, 390~450 나감
const ph1 = f < 390 ? fi(0, 20)(f) : fo(390, 450)(f)
const ph2 = f < 450 ? 0 : f < 840 ? fi(450, 490)(f) : fo(840, 900)(f)
```

---

## 씬 구성 템플릿

### 임팩트형 (훅·클라이맥스)
```
이모지 140px → X슬라이드 Line1 → X슬라이드 Line2 (민트색) → 글로우버스트 → 서브텍스트
```
예시: GB01 Phase1, GB04 Phase3

### 리스트형 (카드 stagger)
```
라벨 → 타이틀 → 카드 N개 (24~40프레임 stagger, 좌에서 X슬라이드) → 판결박스
카드 내: 카드 내부 스캔라인 + elastic 체크마크 + 순환 글로우
```
예시: GB02 Phase3, GB04 Phase2, GB06 Phase1

### 수치형 (카운트업)
```
정적 출발점 → 카운트업 elastic 등장 → 비교 bar → 차이 강조
```
예시: GB03

### CTA형 (구독 클로징)
```
대각선 스윕 → 아이콘 elastic → 채널명 Y슬라이드 → 슬로건 → 구독버튼 elastic + 파티클
```
예시: GB06 Phase2

---

## 파일 목록 (2026-05-31 기준)

| 파일 | 씬 | 상태 |
|------|-----|------|
| GB01_Hook.tsx | 훅 (완판됐습니다) | pending |
| GB02_Checklist.tsx | 12개 섹터 + 혜택 | pending |
| GB03_Compare.tsx | 수익률 비교 | pending |
| GB03_5_RealBenefit.tsx | 진짜 수혜주 | pending |
| GB04_Telegram.tsx | 전환 (어떻게 알았냐) | pending |
| GB05_StockBrain.tsx | AI 직원들 | pending |
| GB06_CTA.tsx | 구독 클로징 | pending |
