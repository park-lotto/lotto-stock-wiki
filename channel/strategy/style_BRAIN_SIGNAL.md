# BRAIN SIGNAL 스타일 레퍼런스

> 에이전트 직원 영상(AG 시리즈)에서 확립된 Remotion 영상 스타일.
> "데이터가 살아서 흐르는" 느낌 — Phase마다 완전히 다른 비주얼 + 민트 다크.

---

## 스타일 정의

| 항목 | 값 |
|------|----|
| 이름 | BRAIN SIGNAL |
| 배경 | `#080c14` (딥 네이비 블랙) |
| 포인트 컬러 | `#00FFD0` (민트) |
| 보조 컬러 | `#FFA502` (앰버), `#FF4757` (레드), `#9ca3af` (그레이) |
| 폰트 | Noto Sans KR / 숫자·코드: Consolas Menlo monospace |
| 자막 | 하단 16% 영역, 흰색 40px bold, Whisper 싱크 |
| FPS / 해상도 | 30fps / 1920×1080 |

---

## 핵심 원칙

### 1. Phase 전환 — 씬 내에서 비주얼이 바뀐다
- 1개 씬(50~60초)을 4~8개 Phase로 분할
- 각 Phase마다 완전히 다른 시각 언어 사용
- Phase 전환: `ip(f, outA, outB)` opacity fade (약 20프레임)
- **금지**: 한 가지 이미지/아이콘으로 씬 전체 끌고 가기

### 2. Phase 유형 라이브러리
| Phase 유형 | 사용 상황 | 핵심 구현 |
|-----------|----------|---------|
| **레이더 Sweep** | 대기·스캔 표현 | SVG sectorPath 회전 + trail |
| **카드 낙하** | 데이터 수집·보고서 | translateY + Easing.back |
| **텔레그램 버블** | 메시지·채널 표현 | 채팅창 UI 모방, 오른→왼 슬라이드 |
| **뉴스 Ticker** | 뉴스·헤드라인 흐름 | translateX linear 무한 스크롤 |
| **UI 모방** | 유튜브·앱 화면 | 실제 인터페이스 다크 버전 재현 |
| **SVG 차트 Draw-on** | 데이터·주가·통계 | strokeDashoffset or path slice |
| **폴더 트리 누적** | 파일 쌓임·기록 | 아이콘 카드 elastic 등장 순차 |
| **24시간 원형 클락** | 타임스탬프·24H | SVG circle + hourToDeg |
| **이모지 원형 배치** | 팀·집합 표현 | trigonometry 원형 포지션 |
| **클라이맥스 텍스트** | 씬 마무리 | elastic scale + dynGlow |

### 3. 애니메이션 패턴
```ts
// 기본 ip() 헬퍼 — 모든 씬 공통
function ip(f, a, b, from=0, to=1, ease=Easing.out(Easing.cubic)) {
  return interpolate(f, [a,b], [from,to], { extrapolateLeft:'clamp', extrapolateRight:'clamp', easing:ease })
}

// Phase fadeInOut
const fadeInOut = (inA, inB, outA, outB) =>
  ip(f, inA, inB) * (1 - ip(f, outA, outB))

// 동적 글로우 (pulse 기반)
const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5
const gSz     = interpolate(pulse, [0,1], [10,28])
const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`

// Elastic scale 등장
const scale = interpolate(f, [startF, startF+35], [0.2, 1], {
  extrapolateLeft:'clamp', extrapolateRight:'clamp',
  easing: Easing.out(Easing.elastic(0.8)),
})

// 스캔라인 (씬 전환 시그니처)
const scanY  = interpolate(f, [s, s+40], [-2, 104], { extrapolateLeft:'clamp', extrapolateRight:'clamp' })
const scanOp = interpolate(f, [s, s+5, s+35, s+40], [0,1,1,0], ...)
```

### 4. 자막바 — 전 씬 공통
```tsx
<div style={{
  position:'absolute', bottom:0, left:0, right:0, height:'16%',
  display:'flex', alignItems:'center', justifyContent:'center',
  paddingInline:80,
  background:'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)',
}}>
  {sub && <div style={{ color:'#FFF', fontSize:40, fontWeight:700,
    textAlign:'center', opacity:sub.op, textShadow:'0 2px 8px rgba(0,0,0,0.9)',
  }}>{sub.text}</div>}
</div>
```

### 5. 레이더 Sweep SVG — 재사용 패턴
```tsx
function sectorPath(cx, cy, r, startDeg, endDeg) {
  const s = (startDeg * Math.PI) / 180
  const e = (endDeg   * Math.PI) / 180
  return `M${cx},${cy} L${cx+r*Math.cos(s)},${cy+r*Math.sin(s)}
    A${r},${r},0,${endDeg-startDeg>180?1:0},1,${cx+r*Math.cos(e)},${cy+r*Math.sin(e)} Z`
}
// sweepDeg = (f * 2.4) % 360  → 초당 72도 = 약 5초 1회전
// trail: sweepDeg-40 ~ sweepDeg, opacity 0.04씩 4단계
```

---

## 이모지 사용 원칙
- 이모지 40% + 텍스트 60% 혼합
- 이모지는 시각 포인트, 텍스트가 정보 전달
- 이모지 크기: 72~130px (메인), 22~44px (카드 내)
- `filter: drop-shadow(0 2px 14px col55)` 글로우 필수

---

## 색상 시그널 체계
| 컬러 | 의미 | 사용 |
|------|------|------|
| `#00FFD0` 민트 | AI·성공·핵심 | 탑픽, 완료, 메인 강조 |
| `#FFA502` 앰버 | 주의·미국·야간 | 미국장, 밤 시간대, 경고 |
| `#FF4757` 레드 | 긴급·핫·상승 | 속보, 탑픽 🔴, LIVE |
| `#9ca3af` 그레이 | 보조·과거·낮 | 리포트, 낮 시간대 |
| `#6b7280` 다크그레이 | 설명·서브 | 설명 텍스트, 부제 |

---

## 구현 파일 위치

| 파일 | 내용 | Phase 유형 |
|------|------|-----------|
| `src/agents/AG_S04_2_Collect_v2.tsx` | 수집 직원 (v3) | 레이더→카드→ticker→유튜브→차트→폴더→클락 |
| `src/agents/AG_S02_Empathy.tsx` | 공감 씬 | 이모지+텍스트 혼합, 자막바 |
| `src/agents/AG_S03_Declaration.tsx` | 선언 씬 | Org chart, elastic scale, 스캔라인 |
| `src/agents/AG_S04_1_Boss.tsx` | 총괄 씬 | 부채꼴 구조 |
| `src/agents/AG_S05_Climax.tsx` | 클라이맥스 | 타임라인 재등장 → 팀 선언 |
| `src/agents/AG_S06_Awareness.tsx` | 자각 씬 | Before/After + 브리핑 카드 |
| `src/agents/AG_S07_Tease.tsx` | 여운 씬 | 블러 다이어그램 + 다음 편 티저 |
| `src/agents/AG_S08_CTA.tsx` | CTA | 댓글 타이핑 + STOCK BRAIN 로고 |
| `src/dakkak/B4_Dashboard.tsx` | 대시보드 | 대시보드 UI 레이아웃 참고 |

---

## 씬 구성 템플릿 (BRAIN SIGNAL 영상 기준)

```
씬1 훅     20~30초  레이더 or 타임라인 (임팩트 첫 인상)
씬2 공감   40~50초  이모지+텍스트 혼합 (시청자 감정 연결)
씬3 선언   20~30초  Org chart or 숫자 클라이맥스
씬4 데모   4~5분    Phase 전환 × 6~8 (실제 시스템 보여주기)
씬5 클라이맥스 40~60초  오프닝 회상 + 개념 전환 문장
씬6 자각   35~45초  Before/After 비교
씬7 여운   25~35초  다음 편 티저 (흐릿 다이어그램)
씬8 CTA    25~35초  댓글 키워드 + 서비스 티저
```

---

*확립일: 2026-05-30 | AG 직원 10명 영상에서 추출*
*다음 적용 예정: STOCK BRAIN 서비스 소개 영상*
