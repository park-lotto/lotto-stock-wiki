# 로또의 주식 — 대시보드 디자인 시스템

> Remotion constants.ts 기반 | 웹 대시보드 전용 확장판

---

## 색상 토큰

```css
/* 배경 */
--bg:          #000000   /* 순수 블랙 — 전체 배경 */
--bg-card:     #111111   /* 카드 기본 배경 */
--bg-active:   #0A1F1A   /* 민트 계열 카드 (강조 카드) */
--bg-hover:    #0D2620   /* 호버 상태 */

/* 메인 민트 (주 강조색) */
--mint:        #00FFD0   /* 네온 민트 — 핵심 수치, 강조, 테두리 */
--mint-mid:    #00BF9A   /* 중간 민트 — 서브 강조 */
--mint-dark:   #003D31   /* 어두운 민트 — 배경 섞을 때 */
--mint-light:  #80FFE8   /* 밝은 민트 — 글로우 하이라이트 */

/* 텍스트 */
--text:        #FFFFFF   /* 주 텍스트 */
--text-sub:    #888888   /* 보조 텍스트 */
--text-dim:    #444444   /* 비활성 텍스트 */

/* 테두리 */
--border-on:   #00FFD0   /* 활성 테두리 */
--border-off:  #1A3D35   /* 비활성 테두리 */
--border-dim:  #222222   /* 기본 구분선 */

/* 신호색 (대시보드 전용 — 유튜브 영상에는 사용 안 함) */
--sig-up:      #FF4336   /* 상승·위험·매파 신호 */
--sig-mid:     #F0883E   /* 중립·주의 신호 */
--sig-warn:    #E3B341   /* 경고·관찰 신호 */
--sig-down:    #2196F3   /* 하락·채널 정책 파랑 */
```

---

## 폰트

```css
font-family: 'Noto Sans KR', 'Segoe UI', -apple-system, sans-serif;
```

### 크기 체계

| 용도 | 크기 | 굵기 | 색상 |
|------|------|------|------|
| 헤더 타이틀 | 20px | 800 | --mint |
| 섹션 레이블 | 11px | 700 | --text-sub / uppercase |
| 카드 타이틀 | 15px | 700 | --text |
| 핵심 수치 | 28~36px | 800 | --mint |
| 보조 수치 | 18px | 700 | --text |
| 본문 | 13px | 400 | --text |
| 설명 | 12px | 400 | --text-sub |
| 라벨 | 11px | 600 | --text-sub |

---

## 글로우 (Glow)

```css
/* 약한 글로우 — 일반 민트 수치 */
--glow-weak:  0 0 8px rgba(0,255,208,0.4);

/* 중간 글로우 — 강조 수치, 활성 테두리 */
--glow-mid:   0 0 12px rgba(0,255,208,0.6), 0 0 24px rgba(0,255,208,0.3);

/* 강한 글로우 — 핵심 인사이트, 오늘의 결론 */
--glow-strong: 0 0 16px rgba(0,255,208,0.8), 0 0 32px rgba(0,255,208,0.5), 0 0 64px rgba(0,191,154,0.3);

/* 배경 방사형 글로우 — 카드 중앙 */
radial-gradient(ellipse at 50% 50%, rgba(0,255,208,0.06) 0%, transparent 70%)
```

---

## 애니메이션

### CSS 키프레임

```css
/* 페이드인 + 위로 슬라이드 (카드 등장) */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 민트 글로우 펄스 (핵심 수치 호흡) */
@keyframes mintPulse {
  0%, 100% { text-shadow: 0 0 8px rgba(0,255,208,0.4); }
  50%       { text-shadow: 0 0 20px rgba(0,255,208,0.9), 0 0 40px rgba(0,255,208,0.5); }
}

/* 테두리 글로우 펄스 (활성 카드) */
@keyframes borderPulse {
  0%, 100% { box-shadow: 0 0 8px rgba(0,255,208,0.2); }
  50%       { box-shadow: 0 0 20px rgba(0,255,208,0.5), 0 0 40px rgba(0,255,208,0.2); }
}

/* 스캔라인 (페이지 로딩 시 1회) */
@keyframes scanDown {
  from { top: -2%; opacity: 0; }
  5%   { opacity: 1; }
  95%  { opacity: 1; }
  to   { top: 102%; opacity: 0; }
}

/* 수치 카운트업 효과 */
@keyframes countUp {
  from { opacity: 0; transform: scale(0.8); }
  to   { opacity: 1; transform: scale(1); }
}

/* 신호 깜빡임 (위험 상태) */
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}

/* 좌에서 슬라이드 */
@keyframes slideLeft {
  from { opacity: 0; transform: translateX(-24px); }
  to   { opacity: 1; transform: translateX(0); }
}

/* 카드 순차 등장 (stagger) */
.card:nth-child(1) { animation-delay: 0.0s; }
.card:nth-child(2) { animation-delay: 0.1s; }
.card:nth-child(3) { animation-delay: 0.2s; }
.card:nth-child(4) { animation-delay: 0.3s; }
```

### 적용 기준

| 요소 | 애니메이션 | 지속 시간 |
|------|---------|---------|
| 카드 등장 | fadeUp | 0.5s ease-out |
| 핵심 수치 | mintPulse | 3s infinite |
| 활성 카드 테두리 | borderPulse | 2.5s infinite |
| 페이지 로딩 스캔 | scanDown | 1.2s 1회 |
| 섹션 타이틀 | slideLeft | 0.4s ease-out |
| 위험 신호 | blink | 1.5s infinite |

---

## 카드 유형

### 기본 카드
```css
background: #111111;
border: 1px solid #1A3D35;
border-radius: 12px;
padding: 18px 20px;
```

### 민트 강조 카드 (오늘의 결론 등)
```css
background: #0A1F1A;
border: 1px solid #00FFD0;
border-radius: 12px;
box-shadow: 0 0 20px rgba(0,255,208,0.15);
animation: borderPulse 2.5s infinite;
```

### 게이지 바
```css
/* 트랙 */
background: #1A1A1A;
border-radius: 10px;
height: 10px;

/* 민트 필 */
background: linear-gradient(90deg, #003D31, #00BF9A, #00FFD0);
border-radius: 10px;
box-shadow: 0 0 8px rgba(0,255,208,0.5);

/* 바늘 */
background: #FFFFFF;
box-shadow: 0 0 6px rgba(255,255,255,0.8);
```

### 신호 태그 (Pill)
```css
/* 민트 — 긍정/강세 */
background: rgba(0,255,208,0.12);
border: 1px solid rgba(0,255,208,0.3);
color: #00FFD0;

/* 경고 — 중립/주의 */
background: rgba(240,136,62,0.12);
border: 1px solid rgba(240,136,62,0.3);
color: #F0883E;

/* 위험 — 매파/리스크 */
background: rgba(255,67,54,0.12);
border: 1px solid rgba(255,67,54,0.3);
color: #FF4336;
```

---

## 레이아웃 원칙

```
헤더: 48px 고정 / 블랙 배경 / 하단 민트 1px 라인
컨테이너: max-width 960px / padding 24px
카드 gap: 14px
섹션 간격: 28px
```

### 섹션 레이블
```css
font-size: 11px;
font-weight: 700;
text-transform: uppercase;
letter-spacing: 1.2px;
color: #888888;
/* 오른쪽으로 민트 라인 연장 */
::after { content:''; flex:1; height:1px; background: linear-gradient(90deg, #1A3D35, transparent); }
```

---

## 수치 표시 원칙

| 상태 | 색상 | 효과 |
|------|------|------|
| 핵심 포지티브 수치 | `#00FFD0` (mint) | mintPulse 애니 |
| 일반 수치 | `#FFFFFF` | 없음 |
| 보조 수치 | `#888888` | 없음 |
| 수집 대기 | `#333333` | 없음 |
| 위험/경고 수치 | `#FF4336` | blink (급변 시) |
| 상승 방향 | `#00FFD0` ↑ | 없음 |
| 하락 방향 | `#2196F3` ↓ | 없음 |

---

## 참조
- Remotion 원본: `channel/strategy/strategy_remotion_가이드.md`
- 적용 파일: `out/L1_글로벌유동성.html`, `out/dashboard.html`
