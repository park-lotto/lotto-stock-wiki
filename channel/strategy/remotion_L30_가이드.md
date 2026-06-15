# 리모션 AI최신 가이드 — L30 (LIFE 3.0 Pictures 벤치마크)

> 기준 영상: https://youtu.be/kI1soqlxwl8  
> 파일 위치: `remotion-stock/src/life30/`  
> 작성일: 2026-06-15

---

## 디자인 원칙

| 원칙 | 내용 |
|------|------|
| **배경** | 순수 블랙 `#000000` — 어떤 데이터도 빛난다 |
| **액센트** | 라임 그린 `#AAFF00` 하나만 — 분산 금지 |
| **PiP 테두리** | 골드/앰버 `#C8921A` — AI 아나운서 고급감 |
| **HUD** | 항상 좌상단 챕터 + 우상단 타임코드 |
| **자막** | 하단 그라데이션 바, 흰색 굵은 글씨 |
| **카드 테두리** | `rgba(170,255,0,0.65)` 라임 1.5px |

---

## 컬러 팔레트

```
배경        #000000
라임 액센트  #AAFF00   ← 텍스트, 수치, 테두리, HUD 레이블
골드 PiP    #C8921A   ← 아바타 PiP 테두리만
흰색 텍스트  #FFFFFF
흐린 텍스트  rgba(255,255,255,0.55)
카드 배경   rgba(0,0,0,0.88)
바 차트     #1C1C1C
```

---

## 타이포그래피

| 용도 | 폰트 | 크기 | 굵기 | 간격 |
|------|------|------|------|------|
| HUD 레이블 | Courier New | 11px | 400 | 3px |
| 카드 상단 레이블 | Courier New | 10px | 400 | 3px |
| 대형 수치 ($420B) | Noto Sans KR | 48px | 900 | -1px |
| 날짜 (2022.11.30) | Courier New | 38px | 700 | 2px |
| 선언문 (대형) | Noto Sans KR | 72px | 900 | — |
| 서브텍스트 | Noto Sans KR | 22px | 400 | — |
| 자막 | Noto Sans KR | 36px | 700 | — |
| 국가명 | Noto Sans KR | 16px | 500 | — |

---

## 컴포넌트 목록

### 1. L30_Layout (마스터 레이아웃)
```tsx
<L30_Layout
  avatarFile="avatar_s01.mp4"
  mode="fullscreen"          // "fullscreen" | "pip"
  chapter="01"
  chapterTitle="HOOK"
  timeStart="00:00"
  timeEnd="00:40"
  subtitles={[...]}
>
  {/* 데이터 오버레이 */}
</L30_Layout>
```

### 2. L30_HUD (챕터 + 타임코드)
```tsx
<L30_HUD chapter="01" title="HOOK" timeStart="00:00" timeEnd="00:08" />
```
→ L30_Layout 사용 시 자동 포함. 직접 사용 불필요.

### 3. L30_PipAvatar (골드 PiP)
```tsx
<L30_PipAvatar avatarFile="avatar_s01.mp4" showAt={0} />
```
→ L30_Layout mode="pip" 사용 시 자동 포함.

### 4. L30_MetricCard (대형 수치 카드)
```tsx
<L30_MetricCard
  showAt={20}
  topLabel="MARKET CAP · 2022.11"
  value="$420B"
  valueLime={true}
  subLabel="RANK · OUT OF TOP 10"
  width={290}
  slideFrom="left"
/>
```

### 5. L30_TimestampCard (날짜 카드)
```tsx
<L30_TimestampCard
  showAt={0}
  date="2022.11.30"
  subLabel="DAY ZERO"
/>
```

### 6. L30_LogoCard (로고 카드)
```tsx
<L30_LogoCard
  showAt={10}
  emoji="🤖"
  name="ChatGPT"
  subLabel="PUBLIC RELEASE"
  slideFrom="right"
/>
```

### 7. L30_ArrowBadge (화살표 배지)
```tsx
<L30_ArrowBadge showAt={30} text="→ 2024년 6월" />
```

### 8. L30_CountryRankCard (국가 랭킹 카드)
```tsx
<L30_CountryRankCard
  showAt={20}
  rank="01"
  flag="🇺🇸"
  country="USA"
  tag="EXCLUDED"
  market="MARKET > 5.5T"
  delay={0}    // stagger: 0 / 8 / 16
/>
```

### 9. L30_BarChart (국가 막대차트)
```tsx
<L30_BarChart
  chartTitle="MARKET CAP · LISTED EQUITIES"
  bars={[
    { flag: '🇰🇷', country: '한국', value: '$4.5T', pct: 82 },
    { flag: '🇬🇧', country: '영국', value: '$4.0T', pct: 73 },
    { flag: '🇫🇷', country: '프랑스', value: '$3.5T', pct: 64 },
  ]}
  referenceLabel="NVIDIA · $5.5T"
  refSubLabel="REFERENCE CEILING"
  maxBarH={540}
/>
```

### 10. L30_TextReveal (선언문 텍스트)
```tsx
<L30_TextReveal
  topLabel="THE VERDICT"
  lines={[
    { text: 'AI가 바꾼 것은', color: 'white' },
    { text: '기술만이 아닙니다', color: 'lime' },
  ]}
  subLines={[
    { text: '숫자  —  시장  —  현실', color: 'white', size: 24 },
    { text: '데이터는 거짓말하지 않습니다.', color: 'dim', size: 18 },
  ]}
/>
```

### 11. L30_LargeLogoBlast (대형 로고 폭발)
```tsx
<L30_LargeLogoBlast
  showAt={10}
  hideAt={50}
  emoji="🟩"
  color="#AAFF00"
  opacity={0.22}
  size={400}
/>
```

---

## 씬 타입별 레시피

### A. 아바타 + 좌측 카드 (스크린샷2·4 스타일)
```
mode="fullscreen" 아바타 전체화면
→ 좌측: 카드들 세로 스택 (position: absolute, left: 80)
→ 우측: 차트 또는 로고 (position: absolute, right: 80)
```

### B. 풀스크린 데이터 + 우하단 PiP (스크린샷1·5 스타일)
```
mode="pip" 블랙 배경
→ children: BarChart 또는 Globe 전체화면
→ PiP: 자동으로 우하단 골드 테두리로 등장
```

### C. 순수 텍스트 + 우하단 PiP (스크린샷6 스타일)
```
mode="pip" 블랙 배경
→ children: L30_TextReveal
→ PiP: 자동으로 우하단 등장
```

### D. 아바타 + 로고 폭발 (스크린샷3 스타일)
```
mode="fullscreen" 아바타 전체화면
→ children: L30_LargeLogoBlast (반투명 대형)
```

---

## 카카오클로드 영상 적용 매핑

| 씬 | 타입 | 핵심 컴포넌트 |
|----|------|-------------|
| S0 인트로 | D | LargeLogoBlast (카카오 노란색) |
| S1 훅 | A | TimestampCard (오늘 아침), LogoCard (Claude) |
| S2 페인포인트 | A | MetricCard (30분 낭비), ArrowBadge |
| S3 철학선언 | C | TextReveal ("치트키는 없다") |
| S4 로드맵 | B | BarChart 대신 커스텀 스텝 인포그래픽 |
| S5~S10 | KakaoLayout PiP | 기존 화면녹화 방식 유지 |
| S11 응용 | A | CountryRankCard 형식으로 4가지 응용 |
| S12 수미상관 | C | TextReveal + 카톡 화면 재등장 |
| S13 CTA | D | 채널 로고 폭발 |

---

## 애니메이션 파라미터

```
카드 등장: spring(damping:22, stiffness:140) + 18f 페이드
바 차트: spring(damping:24, stiffness:90, mass:1.3) + stagger 10f
텍스트 라인: spring(damping:28, stiffness:130) + stagger 7f
PiP 슬라이드인: spring(damping:22, stiffness:160)
HUD 페이드: 12f linear
```
