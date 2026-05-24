# 로또의 주식 — Remotion 영상 제작 가이드

> 작성일: 2026-05-22 | 최종 수정: 2026-05-23 | 이 파일이 유일한 최신 가이드. AIStockVideo Scene01~10 실측 기반으로 전면 재정의.

---

## 1. 프로젝트 구조

```
remotion-stock/
├── src/
│   ├── Root.tsx              ← Composition 등록 (여기에 새 영상 추가)
│   ├── load-font.ts          ← Noto Sans KR 비동기 로딩 (한 번만 실행)
│   ├── constants.ts          ← 색상·글로우·그라데이션·폰트 상수
│   ├── components/
│   │   └── Arrow.tsx         ← SVG 화살표 컴포넌트
│   └── scenes/
│       └── Scene01~10.tsx    ← 장면 파일들
├── package.json
└── remotion.config.ts
```

---

## 2. constants.ts — 디자인 토큰

```ts
// 색상
C.bg          = '#000000'        // 배경 (순수 블랙)
C.cardBg      = '#111111'        // 카드 기본 배경
C.cardBgActive= '#0A1F1A'        // 민트 계열 카드 배경
C.main        = '#00FFD0'        // 메인 민트 네온 ← 주 강조색
C.mainMid     = '#00BF9A'        // 중간 민트
C.mainDark    = '#003D31'        // 어두운 민트
C.mainLight   = '#80FFE8'        // 밝은 민트
C.textPrimary = '#FFFFFF'        // 주 텍스트 ← 흰색
C.textSub     = '#888888'        // 보조 텍스트
C.borderActive= '#00FFD0'        // 활성 테두리
C.borderSub   = '#1A3D35'        // 비활성 테두리
C.dataUp      = '#FF4336'        // 빨강 ← 절대 사용 금지 (채널 방침)
C.dataDown    = '#2196F3'        // 파랑

// 글로우 (N1~N3)
GLOW.weak    → textShadow / boxShadow / filter (약한 글로우)
GLOW.mid     → 중간 글로우 (일반 강조)
GLOW.strong  → 강한 글로우 (클라이맥스 전용)

// 그라데이션 (배경 사용 금지 — 민트 텍스트에만 사용)
GRAD.premium    → 135deg, 4색 민트 그라데이션
GRAD.vertical   → 세로 민트 페이드
GRAD.horizontal → 가로 민트 그라데이션

// 폰트
FONT = '"Noto Sans KR", sans-serif'  ← fontFamily에 항상 사용
```

---

## 3. 타이포그래피 시스템 — 씬 유형별 정확한 치수

### 3-1. 씬 유형별 타이틀 fontSize (AIStockVideo 실측)

| 씬 유형 | Line 1 fontSize | Line 2 fontSize | 진입 방향 |
|--------|----------------|----------------|---------|
| **임팩트형** (S01) | **148px** | **148px** | 좌←→우 교차 X슬라이드 |
| **카운트업형** (S02) | **200px** (숫자) | — | elastic scale |
| **바차트형** (S03) | **100px** | — | 아래 Y슬라이드 |
| **아젠다형** (S04) | **140px** | **150px** (강조어) | 아래 Y슬라이드 + elastic |
| **리스트형** (S05) | **100px** | — | 아래 Y슬라이드 |
| **비교형** (S06) | **100px** | — | 아래 Y슬라이드 |
| **클라이맥스형** (S07) | **150px** | **150px** | 위↕아래 Y슬라이드 |
| **플로우형** (S08) | **100px** | — | 아래 Y슬라이드 |
| **결론형** (S09) | **140px** | **110px** | 좌←→우 교차 X슬라이드 |
| **클로징형** (S10) | **160px** (채널명) | — | 아래 Y슬라이드 |

### 3-2. 공통 고정 치수 (전 씬 동일)

| 레벨 | fontSize | fontWeight | 색상 | 기타 |
|------|---------|-----------|------|------|
| **라벨** (카테고리 태그) | **28px** | 500 | C.textSub | letterSpacing: **5** |
| **서브 설명** (한줄 보조) | **32~36px** | 500 | C.textSub | lineHeight: 1.6 |
| **하단 자막 바** | **40px** | 700 | C.textPrimary | height: 16%, paddingInline: 80 |
| **카드 제목** | **42px** | 700 | C.textPrimary (활성: C.main) | — |
| **카드 설명** | **26px** | 500 | C.textSub | — |
| **번호 배지 숫자** | **30px** | 900 | #000000 | 배지: 64×64px, borderRadius: 14 |
| **카드 아이콘** | **68px** | — | — | filter: GLOW.weak.filter |
| **메인 아이콘** | **150px** | — | — | elastic scale 등장 |
| **클로징 구독 버튼** | **46px** | 900 | #000000 | — |

### 3-3. letterSpacing 진입 애니메이션 (씬 유형별)

| 씬 유형 | 시작값 | 끝값 | 프레임 |
|--------|--------|------|--------|
| 임팩트형 (S01, 임팩트 타이틀) | **22** | **0** | f38-68 |
| 클라이맥스형 (S07 Line1) | **20** | **0** | f40-68 |
| 아젠다형 (S04 메인) | **18** | **0** | f40-68 |
| 결론형 (S09 Line1) | **16** | **0** | f40-68 |
| 클로징형 (S10 채널명) | **12** | **-2** | f38-68 |
| 바차트/리스트/비교/플로우형 | letterSpacing 없음 | — | — |

### 3-4. ⚠️ 금지 사항

```
❌ WebkitBackgroundClip: 'text' + 애니메이션 backgroundPosition 동시 사용
   → Remotion 렌더러에서 텍스트 대신 민트 사각형 박스가 렌더링됨

❌ 텍스트 노드가 섞인 <div> 내부 <span>에 WebkitBackgroundClip: 'text'
   예) <div>AI는 <span style={{WebkitBackgroundClip:'text'}}>도구</span>다</div>
   → 반드시 solid color + textShadow 로 대체

❌ C.dataUp (#FF4336 빨강) 사용
   → 채널 방침: 네온민트(C.main) + 흰색(C.textPrimary) 두 색만 사용

✅ 올바른 민트 키워드 강조 방법:
   <span style={{ color: C.main, textShadow: GLOW.mid.text }}>도구</span>

✅ 그라데이션 텍스트가 필요하면: 단독 div에 독립적으로 적용 (다른 텍스트 노드 없이)
   그리고 backgroundPosition 애니메이션 없이 고정값으로만 사용
```

---

## 4. 레이아웃 구조

```tsx
<AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

  {/* [필수] 배경 중앙 글로우 */}
  <div style={{
    position: 'absolute', inset: 0,
    background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
    opacity: bgGlow,   // ← Math.sin 펄스 (아래 5-2 참조)
    pointerEvents: 'none',
  }} />

  {/* [씬마다 선택] 스캔 라인 — 씬 시작 시 위→아래 1회 스윕 */}
  ...

  {/* 콘텐츠 영역 — 상단 82% */}
  <div style={{
    position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    paddingInline: 120,  // 기본. 리스트형: 160, 보조설명: 180
  }}>
    ...
  </div>

  {/* 하단 자막 바 — 하단 16% */}
  <div style={{
    position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    opacity: captionOp,
  }}>
    <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700,
      textAlign: 'center', paddingInline: 80 }}>
      자막 텍스트
    </div>
  </div>

</AbsoluteFill>
```

**paddingInline 씬별 기준:**
- 기본 (임팩트/클라이맥스/아젠다/결론/클로징): **없음** (텍스트 자체가 center align)
- 리스트형 카드 컨테이너: **paddingInline: 160**
- 보조 서브텍스트 div: **paddingInline: 180**

---

## 5. 애니메이션 패턴 사전

### 5-1. 씬 유형별 진입 패턴 (정확한 프레임)

#### 임팩트형 — 좌↔우 교차 X슬라이드 (S01 기준)
```ts
// 아이콘 (f5-28)
const iconScale = interpolate(f, [5, 28], [0.4, 1], {
  extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1))
});
// 라벨 (f22-42)
const labelOp = interpolate(f, [22, 42], [0, 1], { extrapolateRight: 'clamp' });

// Line1 — 좌에서 슬라이드 + 자간 22→0 (f38-68)
const t1X  = interpolate(f, [38, 68], [-180, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
const t1Op = interpolate(f, [38, 68], [0, 1],    { extrapolateRight: 'clamp' });
const t1Ls = interpolate(f, [38, 68], [22, 0],   { extrapolateRight: 'clamp' });

// Line2 — 우에서 슬라이드 + 브리드 (f55-88)
const t2X  = interpolate(f, [55, 88], [180, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
const t2Op = interpolate(f, [55, 88], [0, 1],    { extrapolateRight: 'clamp' });
// 사용: opacity: t1Op, transform: `translateX(${t1X}px)`, letterSpacing: t1Ls
// 사용: opacity: t2Op, transform: `translateX(${t2X}px) scale(${breathe})`
```

#### 결론형 — 좌↔우 교차 X슬라이드 (S09 기준, 임팩트형보다 좁음)
```ts
// 아이콘 (f8-28)
// 라벨 (f25-45)

// Line1 — 좌에서 슬라이드 + 자간 16→0 (f40-68)
const t1X  = interpolate(f, [40, 68], [-120, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
const t1Ls = interpolate(f, [40, 68], [16, 0],   { extrapolateRight: 'clamp' });

// Line2 — 우에서 슬라이드 (f60-92)
const t2X  = interpolate(f, [60, 92], [120, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
// Line1: fontSize 140, Line2: fontSize 110
```

#### 클라이맥스형 — 위↕아래 Y슬라이드 (S07 기준)
```ts
// 아이콘 (f8-28), 라벨 (f25-45)

// Line1 — 위에서 내려옴 + 자간 20→0 (f40-68)
const t1Y  = interpolate(f, [40, 68], [-60, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
const t1Ls = interpolate(f, [40, 68], [20, 0],  { extrapolateRight: 'clamp' });

// Line2 — 아래서 올라옴 (f58-90)
const t2Y  = interpolate(f, [58, 90], [60, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
// 씬 전체 줌인 필수
const sceneZoom = interpolate(f, [0, 180], [1, 1.04], { extrapolateRight: 'clamp' });
// fontSize 150 / 150
```

#### 아젠다형 — Y슬라이드 + 강조어 elastic (S04 기준)
```ts
// 아이콘 (f8-28), 라벨 (f25-45)

// 메인 타이틀 — 아래서 슬라이드 + 자간 18→0 (f40-68)
const t1Y  = interpolate(f, [40, 68], [60, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
const t1Ls = interpolate(f, [40, 68], [18, 0],  { extrapolateRight: 'clamp' });

// 강조어 — elastic + Y슬라이드 (f62-92)
const t2Scale = interpolate(f, [62, 92], [0.5, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
const t2Y     = interpolate(f, [62, 92], [50, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
// 메인: fontSize 140 / 강조어: fontSize 150
```

#### 서브타이틀형 — 아래 Y슬라이드 (바차트/리스트/비교/플로우/클로징 공통)
```ts
// 아이콘 (f5-28 or f8-28 or f8-30), 라벨 (f10-30 or f25-45)

// 타이틀 (f22-48)
const titleY  = interpolate(f, [22, 48], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
const titleOp = interpolate(f, [22, 48], [0, 1],  { extrapolateRight: 'clamp' });
// fontSize 100, letterSpacing 없음

// 클로징형만 다름 (f38-68, 채널명 160px, letterSpacing 12→-2)
const t1Y  = interpolate(f, [38, 68], [70, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
const t1Ls = interpolate(f, [38, 68], [12, -2], { extrapolateRight: 'clamp' });
```

### 5-2. 지속 애니메이션 (Hold)

```ts
// 브리드 (미세 스케일 숨쉬기) — 완전히 등장 후에만
const breathe = t2Op > 0.9 ? Math.sin(f * 0.07) * 0.018 + 1 : 1;  // 임팩트형
const breathe = t2Op > 0.9 ? Math.sin(f * 0.08) * 0.025 + 1 : 1;  // 아젠다/클라이맥스형
const breathe = iconOp > 0.9 ? Math.sin(f * 0.06) * 0.015 + 1 : 1; // 결론형 (아이콘)
// 사용: transform: `scale(${breathe})`

// 동적 N3 글로우 펄스 (Line2 민트 텍스트)
const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
const gSz     = interpolate(pulse, [0, 1], [10, 34]);
const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.3)`;
// 클라이맥스형 (더 강하게):
const glowSize = interpolate(pulse, [0, 1], [14, 40]);  // f * 0.08

// 배경 글로우 펄스 — 씬별 기준값
const bgGlow = Math.sin(f * 0.04) * 0.035 + 0.05;  // 임팩트형 (S01) — 범위 0.015~0.085
const bgGlow = Math.sin(f * 0.04) * 0.03  + 0.05;  // 아젠다형 (S04) — 범위 0.02~0.08
const bgGlow = Math.sin(f * 0.04) * 0.03  + 0.04;  // 리스트형 (S05) — 범위 0.01~0.07
const bgGlow = Math.sin(f * 0.05) * 0.04  + 0.06;  // 클라이맥스형 (S07) — 범위 0.02~0.10
const bgGlow = Math.sin(f * 0.04) * 0.03  + 0.045; // 결론형 (S09)
// 기본값 (불명확한 씬): Math.sin(f * 0.04) * 0.03 + 0.05
```

### 5-3. 효과 (Effect)

```ts
// 스캔 라인 — 씬 시작 시 위→아래 1회 (f0-38, 임팩트/클라이맥스/아젠다/결론형 필수)
const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
// JSX:
<div style={{
  position: 'absolute', left: 0, right: 0,
  top: `${scanY}%`, height: 2,
  background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
  boxShadow: '0 0 10px rgba(0,255,208,0.9)',
  opacity: scanOp, zIndex: 10, pointerEvents: 'none',
}} />

// 글로우 버스트 — 임팩트형 (f85-118)
const burstOp    = interpolate(f, [85, 92, 118], [0, 0.55, 0], { extrapolateRight: 'clamp' });
const burstScale = interpolate(f, [85, 118], [0.2, 2.8], { extrapolateRight: 'clamp' });
// 클라이맥스형 (f88-125, 더 강하게)
const burstOp    = interpolate(f, [88, 95, 125], [0, 0.6, 0], { extrapolateRight: 'clamp' });
const burstScale = interpolate(f, [88, 125], [0.2, 3.0], { extrapolateRight: 'clamp' });
// JSX: width/height 560(임팩트) or 600(클라이맥스), top: '45%' or '48%'
<div style={{
  position: 'absolute', top: '45%', left: '50%',
  width: 560, height: 560, marginLeft: -280, marginTop: -280,
  borderRadius: '50%',
  background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
  opacity: burstOp, transform: `scale(${burstScale})`, pointerEvents: 'none',
}} />

// 파티클 — 클로징형 (위로 떠오르는 점들)
const progress = (age % 90) / 90;  // cycleLen = 90
const y = startY - progress * 50;
const op = progress < 0.2 ? progress / 0.2 : progress > 0.7 ? (1 - progress) / 0.3 : 1;
// opacity: op * 0.55, 크기: 4~8px

// 씬 전체 미세 줌인 — 클라이맥스형 전용
const sceneZoom = interpolate(f, [0, 180], [1, 1.04], { extrapolateRight: 'clamp' });
// 사용: <div style={{ transform: `scale(${sceneZoom})` }}>콘텐츠 영역</div>
```

### 5-4. 카드·리스트 공통 패턴

```ts
// 카드 순차 등장 (stagger) — 24프레임 간격 (CARD_START = [48, 72, 96])
const cardAnim = (i) => {
  const s = CARD_START[i];
  return {
    opacity: interpolate(f, [s, s + 22], [0, 1], { extrapolateRight: 'clamp' }),
    tx:      interpolate(f, [s, s + 22], [-80, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    scale:   interpolate(f, [s, s + 22], [0.92, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    // 카드 내부 스캔 라인
    scanY:  interpolate(f, [s + 10, s + 28], [0, 110], { extrapolateRight: 'clamp' }),
    scanOp: interpolate(f, [s + 10, s + 15, s + 24, s + 28], [0, 0.9, 0.9, 0], { extrapolateRight: 'clamp' }),
  };
};
// 카드에 position:'relative', overflow:'hidden' 필수

// 카드 순환 글로우 (f >= 125 이후, 60프레임 주기)
const allVisible = f >= 125;
const ringPhase  = allVisible ? ((f - 125) % 60) / 60 : 0;
const cardCenter = i / totalCards + 1 / (totalCards * 2);
const dist = Math.min(Math.abs(ringPhase - cardCenter), 1 - Math.abs(ringPhase - cardCenter));
const ringOp = allVisible ? Math.max(0, 1 - dist * totalCards * 1.8) : 0;
// border: ringOp > 0.3 ? C.main : C.borderSub
// boxShadow: ringOp > 0.2 ? `0 0 ${16 * ringOp}px rgba(0,255,208,${0.6 * ringOp})` : undefined
```

### 5-5. 비교형 패턴 (좌=회색, 우=민트)

```ts
// 양쪽 등장 후 — 왼쪽 점점 어두워지고 오른쪽 글로우 강해짐 (f100-140)
const aiReveal = interpolate(f, [100, 140], [0, 1], { extrapolateRight: 'clamp' });
const humanDim = interpolate(f, [100, 140], [1, 0.38], { extrapolateRight: 'clamp' });
// 왼쪽: opacity: leftOp * humanDim
// 오른쪽: boxShadow 강도에 aiReveal 반영
```

### 5-6. 파이프라인 흐름 패턴

```ts
// 화살표 드로잉 — scaleX 0→1
const arrowScaleX = interpolate(f, [start, start + 16], [0, 1], {
  extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
});
// JSX: <div style={{ transform: `scaleX(${arrowScaleX})`, transformOrigin: 'left center' }}>

// 파이프라인 순환 하이라이트 (완전 등장 후, 44프레임 주기)
const CYCLE_LEN = 44;
const cycleF = f >= CYCLE_START ? (f - CYCLE_START) % CYCLE_LEN : -1;
const stepGlow = (i) => cycleF >= 0 ? Math.max(0, 1 - Math.abs(cycleF - i * 11) / 8) : 0;
```

### 5-7. ⚠️ extrapolateLeft: 'clamp' 필수 규칙

배열 인덱스 계산에 `prog` (interpolate 결과)를 쓰는 경우 반드시 양쪽 clamp:

```ts
// 위험 패턴 — f=0일 때 prog가 음수 → raw[-1] = undefined → TypeError
const prog = interpolate(f, [30, 200], [0, 1], { extrapolateRight: 'clamp' }); // ❌

// 올바른 패턴
const prog = interpolate(f, [30, 200], [0, 1], {
  extrapolateLeft: 'clamp', extrapolateRight: 'clamp',  // ✅
  easing: Easing.out(Easing.cubic),
});
```

### 5-8. 씬 시작 스윕 효과 변형 7가지

모두 **f0-38 구간 1회성 스윕** 구조로 동일. 영상별로 교체해 지루함 방지.

#### ① 수평 스캔 (기본 — AIStockVideo)
```tsx
const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

<div style={{
  position: 'absolute', left: 0, right: 0,
  top: `${scanY}%`, height: 2,
  background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
  boxShadow: '0 0 10px rgba(0,255,208,0.9)',
  opacity: scanOp, zIndex: 10, pointerEvents: 'none',
}} />
```

#### ② 수직 스캔 (좌→우 — 데이터 로딩 느낌)
```tsx
const scanX  = interpolate(f, [0, 38], [-2, 104], { extrapolateRight: 'clamp' });
const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

<div style={{
  position: 'absolute', top: 0, bottom: 0,
  left: `${scanX}%`, width: 2,
  background: 'linear-gradient(180deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
  boxShadow: '0 0 10px rgba(0,255,208,0.9)',
  opacity: scanOp, zIndex: 10, pointerEvents: 'none',
}} />
```
→ 추천: DataDetective, 분석형 씬

#### ③ 크로스 스캔 (수평+수직 동시 — KosdaqPolicy)
```tsx
// 수평선 + 수직선 동시 렌더 — 중앙에서 교차하는 순간이 클라이맥스
// ①의 scanY div + ②의 scanX div 동시 사용
```
→ 추천: 정책·구조 발표형 씬

#### ④ 원형 충격파 (중앙에서 border 확산 — LoseReason)
```tsx
const shockScale = interpolate(f, [0, 35], [0, 2.5], { extrapolateRight: 'clamp', easing: Easing.out(Easing.quad) });
const shockOp    = interpolate(f, [0, 5, 28, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

<div style={{
  position: 'absolute', top: '50%', left: '50%',
  width: 800, height: 800, marginLeft: -400, marginTop: -400,
  borderRadius: '50%',
  border: '2px solid #00FFD0',
  boxShadow: '0 0 12px rgba(0,255,208,0.8), inset 0 0 12px rgba(0,255,208,0.4)',
  opacity: shockOp,
  transform: `scale(${shockScale})`,
  pointerEvents: 'none', zIndex: 10,
}} />
```
→ 추천: LoseReason, 숫자 임팩트, 카운트업형

#### ⑤ 대각선 스윕 (30도 빛줄기 — LeadingStock)
```tsx
const diagX  = interpolate(f, [0, 40], [-120, 120], { extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad) });
const diagOp = interpolate(f, [0, 5, 32, 40], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

<div style={{
  position: 'absolute', top: '-20%', bottom: '-20%',
  left: `${diagX}%`, width: 60,
  background: 'linear-gradient(90deg, transparent 0%, rgba(0,255,208,0.6) 40%, rgba(128,255,232,0.9) 50%, rgba(0,255,208,0.6) 60%, transparent 100%)',
  transform: 'rotate(30deg)',
  transformOrigin: 'center center',
  opacity: diagOp,
  pointerEvents: 'none', zIndex: 10,
}} />
```
→ 추천: LeadingStock, 결론형, 클로징형

#### ⑥ 글리치 슬라이스 (화면 분할 뒤틀림 — BuyHigh)
```tsx
const SLICES = [0, 20, 40, 60, 80]; // top %
const glitchAmp = interpolate(f, [0, 8, 22, 30], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

{SLICES.map((top, i) => {
  const dir = i % 2 === 0 ? 1 : -1;
  const tx  = Math.sin(f * 0.8 + i) * 18 * dir * glitchAmp;
  return (
    <div key={i} style={{
      position: 'absolute', left: 0, right: 0,
      top: `${top}%`, height: '20%',
      background: `rgba(0,255,208,${0.04 * glitchAmp})`,
      transform: `translateX(${tx}px)`,
      borderTop: glitchAmp > 0.3 ? `1px solid rgba(0,255,208,${0.3 * glitchAmp})` : 'none',
      pointerEvents: 'none', zIndex: 10,
    }} />
  );
})}
```
→ 추천: BuyHigh, 손실·충격 강조 씬

#### ⑦ 코드 레인 (세로 문자 스트림 — DataDetective)
```tsx
const STREAMS = [{ x: 15, delay: 0 }, { x: 42, delay: 8 }, { x: 68, delay: 4 }, { x: 88, delay: 12 }];
const DIGITS  = ['0', '1', '%', '↑', '↓', '$', '₩'];

{STREAMS.map((s, si) =>
  Array.from({ length: 8 }).map((_, ri) => {
    const streamOp = interpolate(f, [s.delay, s.delay + 8, 32, 40], [0, 0.7, 0.7, 0], { extrapolateRight: 'clamp' });
    const digit = DIGITS[(f + si * 3 + ri * 2) % DIGITS.length];
    const ty = interpolate(f - s.delay - ri * 5, [0, 40], [-5, 110], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
    return (
      <div key={`${si}-${ri}`} style={{
        position: 'absolute', left: `${s.x}%`, top: `${ty}%`,
        color: '#00FFD0', fontSize: 22, fontFamily: 'monospace',
        opacity: streamOp * (1 - ri * 0.1),
        textShadow: '0 0 6px #00FFD0',
        pointerEvents: 'none', zIndex: 10,
      }}>{digit}</div>
    );
  })
)}
```
→ 추천: DataDetective, 통계·데이터 기반 씬

#### 영상별 기본 매핑

| 영상 | 스윕 효과 | 이유 |
|------|---------|------|
| AIStockVideo | ① 수평 스캔 | 기준 영상 |
| BuyHighVideo | ⑥ 글리치 | 고점 매수 = 충격·뒤틀림 |
| LeadingStockVideo | ⑤ 대각선 스윕 | 선두 = 속도감 |
| DataDetectiveVideo | ⑦ 코드 레인 | 데이터 탐정 = 분석 |
| KosdaqPolicyVideo | ③ 크로스 스캔 | 정책 = 구조적 교차 |
| LoseReasonVideo | ④ 원형 충격파 | 손실 = 폭발적 충격 |

---

## 6. 씬 유형별 스펙 시트

### 6-1. 임팩트형 (S01 기준)

```
아이콘: fontSize 150, elastic scale f5-28
라벨:   fontSize 28, letterSpacing 5, f22-42
Line1:  fontSize 148, C.textPrimary, translateX(-180→0) f38-68, letterSpacing 22→0
Line2:  fontSize 148, C.main + dynGlow, translateX(180→0) f55-88, scale(breathe)
자막:   fontSize 40, f80-105

스캔라인: f0-38 ✅
글로우버스트: f85-118 ✅
배경글로우: Math.sin(f*0.04)*0.035+0.05
```

### 6-2. 카운트업형 (S02 기준)

```
아이콘: fontSize 150, elastic scale
라벨:   fontSize 28, letterSpacing 5
숫자:   fontSize 200, C.main + GLOW.strong.text
        표시: Math.round(목표값 * progress).toLocaleString()
        ⚠️ 숫자에 WebkitBackgroundClip 금지 → color: C.main, textShadow 사용
보조설명: fontSize 36, C.textSub
자막:   fontSize 40
```

### 6-3. 바차트형 (S03 기준)

```
라벨:   fontSize 28, letterSpacing 5
타이틀: fontSize 100, C.textPrimary, translateY(40→0) f22-48
바:     사람=회색, 비교=C.main
배지:   elastic 스케일 + 회전 등장
자막:   fontSize 40
```

### 6-4. 아젠다형 (S04 기준)

```
아이콘: fontSize 150, elastic scale f8-28
라벨:   fontSize 28, letterSpacing 5, f25-45
메인:   fontSize 140, C.textPrimary, translateY(60→0) f40-68, letterSpacing 18→0
강조어: fontSize 150, C.main + dynGlow, elastic scale(0.5→1)+translateY(50→0) f62-92
        breathe: Math.sin(f*0.08)*0.025+1 (t2Op > 0.9 조건)
자막:   fontSize 40, f95-118

스캔라인: f0-38 ✅
배경글로우: Math.sin(f*0.04)*0.03+0.05
```

### 6-5. 리스트형 (S05 기준)

```
라벨:   fontSize 28, letterSpacing 5, f10-30
타이틀: fontSize 100, C.textPrimary, translateY(40→0) f22-48
카드:   CARD_START = [48, 72, 96], 24프레임 간격
        background: C.cardBg, borderRadius: 16, padding: 26px 32px
        카드 내부 스캔라인 ✅
배지:   64×64px, borderRadius 14, background C.main, fontSize 30
아이콘: fontSize 68
제목:   fontSize 42, fontWeight 700 (활성 시 C.main)
설명:   fontSize 26, fontWeight 500, C.textSub
순환글로우: f >= 125, 60프레임 주기 ✅
paddingInline 160 (콘텐츠 컨테이너)
자막:   fontSize 40, f120-142

배경글로우: Math.sin(f*0.04)*0.03+0.04
```

### 6-6. 비교형 (S06 기준)

```
라벨:   fontSize 28, letterSpacing 5
타이틀: fontSize 100, translateY(40→0) f22-48
좌카드: 먼저 등장 (회색 계열)
우카드: 나중 등장 (민트 계열)
딤/글로우: f100-140 (humanDim 0.38, aiReveal 1.0)
자막:   fontSize 40
```

### 6-7. 클라이맥스형 (S07 기준)

```
아이콘: fontSize 150, elastic scale f8-28, GLOW.strong.filter
라벨:   fontSize 28, letterSpacing 5, f25-45
Line1:  fontSize 150, C.textPrimary, translateY(-60→0) f40-68, letterSpacing 20→0
Line2:  fontSize 150, C.main + dynGlow(강), translateY(60→0) f58-90, scale(breathe)
        breathe: Math.sin(f*0.08)*0.025+1 (t2Op > 0.9)
자막:   fontSize 40, f98-120

씬 전체 줌인: sceneZoom 1.0→1.04 (f0-180) ✅
스캔라인: f0-38 ✅
글로우버스트: f88-125 (더 강하게, burstOp 0.6) ✅
배경글로우: Math.sin(f*0.05)*0.04+0.06 (다른 씬보다 강함)
```

### 6-8. 플로우형 (S08 기준)

```
라벨:   fontSize 28, letterSpacing 5
타이틀: fontSize 100, translateY(40→0) f22-48
박스:   4개 + 화살표 3개, Arrow 컴포넌트 scaleX 드로잉
        박스 아이콘: fontSize 72
순환하이라이트: 44프레임 주기 ✅
자막:   fontSize 40
```

### 6-9. 결론형 (S09 기준)

```
아이콘: fontSize 150, elastic scale f8-28, GLOW.mid.filter + breathe (iconOp > 0.9)
라벨:   fontSize 28, letterSpacing 5, f25-45
Line1:  fontSize 140, translateX(-120→0) f40-68, letterSpacing 16→0
        (혼합색: C.textPrimary + C.main span)
Line2:  fontSize 110, C.textPrimary, translateX(120→0) f60-92
        (C.main span 강조 포함)
서브설명: fontSize 34, C.textSub, translateY(30→0) f88-115
          paddingInline: 180
자막:   fontSize 40, f110-132

스캔라인: f0-38 ✅
배경글로우: Math.sin(f*0.04)*0.03+0.045
```

### 6-10. 클로징형 (S10 기준)

```
아이콘: fontSize 150, elastic scale f8-30, iconPulse (버튼과 연동)
채널명: fontSize 160, C.main + GLOW.strong.text, translateY(70→0) f38-68, letterSpacing 12→-2
슬로건: fontSize 38, C.textSub, translateY(30→0) f62-90
구독버튼: elastic scale f88-115, background C.main, fontSize 46, borderRadius 16, padding 22px 72px
          pulseGlow: 강도가 시간에 따라 증가 (pulseMag = Math.min(1, (f-88)/40))
배경파티클: 6개, 위로 이동, opacity * 0.55, cycleLen 90 ✅
자막:   fontSize 40, f118-140

배경글로우: Math.sin(f*0.05)*0.04+0.06 + bgGlowAmp (f88-170, 0→0.06 증가)
```

---

## 7. Composition 등록 (Root.tsx)

```tsx
// Root.tsx에 새 영상 추가 방법
import { AIStockVideo } from './AIStockVideo';

<Composition
  id="AIStockVideo"
  component={AIStockVideo}
  durationInFrames={1800}   // 60초 × 30fps
  fps={30}
  width={1920}
  height={1080}
/>
```

각 씬을 묶는 컴포넌트:
```tsx
// AIStockVideo.tsx
import { Series } from 'remotion';
import { SDUR } from './constants';  // SDUR = 180 (6초)

export const AIStockVideo = () => (
  <Series>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene01 /></FadeWrapper></Series.Sequence>
    {/* ... 씬 추가 */}
  </Series>
);
```

`Series.Sequence`는 내부 `useCurrentFrame()`을 0부터 리셋 → 각 씬은 독립적으로 작성.

---

## 8. 실행 & 렌더링

```bash
# 개발 서버 (http://localhost:3000)
npm run dev

# 렌더링 (out/ 폴더에 mp4 생성)
npx remotion render AIStockVideo out/영상이름.mp4

# 특정 씬만 스틸 확인
npx remotion still AIStockVideo --frame=360 out/scene03.png
```

---

## 9. 자주 쓰는 수식

```ts
// 반복 사이클 (0→1→0→1→...)
const cycle = ((f - startFrame) % cycleLen) / cycleLen;

// Sin 기반 펄스 (0~1)
const pulse = Math.sin(f * speed) * 0.5 + 0.5;

// 조건부 글로우 (등장 완료 후에만)
const glow = opacity > 0.9 ? dynGlow : undefined;

// 파티클 수명 (나타났다 사라짐, cycleLen=90)
const age = (f - delay) % cycleLen;
const particleOp = age < 0.2 * cycleLen ? age / (0.2 * cycleLen)
                 : age > 0.7 * cycleLen ? (1 - age / cycleLen) / 0.3
                 : 1;
```

---

## 10. 장면 전환 — 페이드인 / 페이드아웃 필수

**모든 씬은 페이드인(시작) + 페이드아웃(끝)을 반드시 적용한다.**

### 10-1. 씬 내부 fadeIn

```ts
const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
// → <AbsoluteFill style={{ opacity: fadeIn, ... }}>
```

### 10-2. FadeWrapper — 장면 전환 전담 컴포넌트

```tsx
// src/components/FadeWrapper.tsx
// dur 기본값 = SDUR(180). 12초 씬은 dur={360} 전달.
export const FadeWrapper: React.FC<{ children: React.ReactNode; dur?: number }> = ({ children, dur = SDUR }) => {
  const f = useCurrentFrame();
  const endOp = interpolate(f, [dur - 50, dur - 30], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{ background: '#000000' }}>
      {children}
      <div style={{
        position: 'absolute', inset: 0,
        background: '#000000', opacity: endOp, pointerEvents: 'none',
      }} />
    </AbsoluteFill>
  );
};
```

### ⚠️ 체커보드(바둑판) 방지 규칙

```
❌ FadeWrapper AbsoluteFill에 background 없이 opacity만 조작
   → 씬 root opacity=0일 때 Remotion이 체커보드 표시

✅ 올바른 방법: FadeWrapper AbsoluteFill에 background: '#000000' 지정
   → 씬이 투명해도 FadeWrapper 배경이 항상 검정 → 체커보드 없음
   → fadeOut은 자식 위에 검은 오버레이 div를 올려서 처리
```

---

## 11. 창의성 원칙

가이드는 기술 제약만 제공한다. 씬의 구성·레이아웃·연출은 매번 내용에서 발명한다.

```
씬을 만들 때 물어야 할 질문:
  "이 씬의 핵심 감정이 무엇인가?"
  "그 감정을 가장 강하게 전달하는 시각 언어는?"

답이 나오면 그것을 구현한다. 기존 형식에서 고르지 않는다.
```

- 색상·폰트·기술 제약 (위 섹션들) 은 지킨다
- 레이아웃·구성·요소 배치는 매 씬 새로 설계한다
- 이전 영상에서 쓴 형식이면 다른 방법을 찾는다

---

## 12. 체크리스트 (새 씬 작성 시)

```
□ fontFamily: FONT 적용
□ 배경 C.bg + 배경 중앙 글로우 (Math.sin 펄스)
□ fadeIn = interpolate(f, [0, 15], [0, 1]) — AbsoluteFill opacity
□ 씬은 FadeWrapper로 감싸기 (fadeOut 자동 적용)
□ 하단 자막 바: height 16%, fontSize 40px, fontWeight 700, paddingInline 80
□ 콘텐츠 영역: bottom '18%'
□ C.dataUp(빨강) 사용하지 않음 — 민트+흰색만
□ WebkitBackgroundClip:text 사용하지 않음
□ 민트 키워드 강조 = color:C.main + textShadow
□ 메인 아이콘: fontSize 150px, elastic scale Easing.out(Easing.elastic(1))
□ 라벨: fontSize 28px, fontWeight 500, letterSpacing 5
□ 임팩트/결론형 타이틀: 교차 X슬라이드 (translateX), letterSpacing 애니
□ 클라이맥스형 타이틀: Y슬라이드(위↕아래), 씬줌인 1.0→1.04
□ 아젠다형: 140+150px, 강조어 elastic(1.2)
□ 서브타이틀형: 100px, translateY(40→0) f22-48
□ 배열 인덱스에 prog 쓰는 경우: extrapolateLeft:'clamp' 필수
□ 브리드: opacity > 0.9 조건 확인 후 적용
□ tsc --noEmit 에러 0개 확인
```

---

## 수정 히스토리

| 날짜 | 내용 |
|------|------|
| 2026-05-22 | 최초 작성 — 기본 구조·색상·레이아웃·애니메이션 패턴 정의 |
| 2026-05-23 | Section 3 타이포그래피 전면 재정의 — AIStockVideo Scene01~10 실측으로 씬 유형별 정확한 fontSize·letterSpacing·프레임 번호 확정 |
| 2026-05-23 | Section 5-8 추가 — 씬 시작 스윕 효과 변형 7가지 (수평/수직/크로스/원형충격파/대각선/글리치/코드레인) + 영상별 매핑 표 |
