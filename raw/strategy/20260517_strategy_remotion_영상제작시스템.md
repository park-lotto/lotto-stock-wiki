# Remotion 최종 통합 마스터 가이드

**원본 파일**: 리모션 최종.md | **날짜**: 2026-05-17 | **유형**: strategy

---

## 포맷 결정

```
□ A. 롱폼 (유튜브) — 16:9 / 5~15분 / 상세 분석
□ B. 숏폼 (쇼츠)  — 9:16 / 15~90초 / 핵심만
□ C. 둘 다        — 각각 다르게 제작
```

---

## 컬러 시스템

### 메인톤 (70%) — UI/텍스트 전용

| 색상 | HEX | 용도 |
|------|-----|------|
| 화이트 | #FFFFFF | 본문 텍스트, 라벨 |
| 형광민트 | #00FFD4 | 제목, 강조, 화살표, 테두리 |
| 황금주황 | #FFC000 | CTA, 부강조, 경고 |
| 배경 | #0F112A | 전체 배경 |

### 데이터톤 (30%) — 그래프/차트 전용

| 색상 | HEX | 용도 |
|------|-----|------|
| 상승(빨강) | #FF4336 | 양봉, 상승 추세선, 상승 숫자 |
| 하락(파랑) | #2196F3 | 음봉, 하락 추세선, 하락 숫자 |

### 컬러 규칙 (절대 준수)

```
✅ UI 요소 (제목/본문/테두리/화살표/카드/버튼) → 메인톤만
❌ UI에 파랑(#2196F3)/빨강(#FF4336) 사용 금지
✅ 그래프/차트 데이터 → 데이터톤만
```

---

## 렌더링 최적화

### 글자 크기 계층

```
제목   56px  weight 700
부제   40px  weight 600
본문   24px  weight 500
라벨   16px  weight 500
캡션   12px  weight 400
```

### 레이아웃 원칙

- 모든 페이지 중앙 정렬 (alignItems/justifyContent: center)
- lineHeight: 1.5~1.6
- letterSpacing: 0.3~0.5px
- 화살표: SVG 전용 (텍스트 → 금지)

---

## 완전한 컴포넌트 코드

### 색상 상수

```typescript
const C = {
  bg:'#0F112A', white:'#FFFFFF', mint:'#00FFD4', orange:'#FFC000',
  bull:'#FF4336', dim:'rgba(255,255,255,0.45)', card:'rgba(255,255,255,0.07)',
  news:'rgba(255,255,255,0.72)',
};
```

### 애니메이션 헬퍼

```typescript
// 기본 페이드인
const fi = (f, s, d=20) =>
  interpolate(f,[s,s+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});

// 슬라이드업
const su = (f, s, d=20, dist=30) =>
  interpolate(f,[s,s+d],[dist,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});

// 스프링 바운스 (탄성 입장)
const spr = (f, s, d=24) => {
  const t=interpolate(f,[s,s+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return t>=1?1:1-Math.pow(2,-9*t)*Math.cos(t*Math.PI*2.4);
};

// 스프링 Y 이동
const spry = (f, s, d=24, dist=40) => dist*(1-spr(f,s,d));

// 지속 맥동 (breathing)
const osc = (f, sp=.05, base=.7, amp=.2) => base+Math.sin(f*sp)*amp;
```

### SVG 화살표

```jsx
const Arrow = ({color='#00FFD4', w=70, h=44, t=5}) => {
  const mid=`am${w}${h}${color.replace('#','')}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}
      style={{display:'block',flexShrink:0,margin:'0 10px'}}>
      <defs><marker id={mid} markerWidth="12" markerHeight="12"
        refX="11" refY={h/2} orient="auto">
        <polygon points={`0 0,12 ${h/2},0 ${h}`} fill={color}/>
      </marker></defs>
      <line x1="6" y1={h/2} x2={w-12} y2={h/2}
        stroke={color} strokeWidth={t} markerEnd={`url(#${mid})`}/>
    </svg>
  );
};
```

### 텍스트 컴포넌트

```jsx
const Title = (txt, color='#FFFFFF', ex) => (
  <div style={{color,fontSize:56,fontWeight:700,lineHeight:1.2,
    letterSpacing:'-0.5px',marginBottom:16,...ex}}>{txt}</div>
);
const Sub = (txt, color='#00FFD4', ex) => (
  <div style={{color,fontSize:40,fontWeight:600,lineHeight:1.3,
    marginBottom:12,...ex}}>{txt}</div>
);
const Body = (txt, color='#FFFFFF', ex) => (
  <div style={{color,fontSize:24,fontWeight:500,lineHeight:1.6,
    letterSpacing:'0.3px',...ex}}>{txt}</div>
);
const Lbl = (txt, color='rgba(255,255,255,0.45)') => (
  <div style={{color,fontSize:16,fontWeight:500,
    letterSpacing:2,marginBottom:10}}>{txt}</div>
);
```

### 장면 래퍼 (Wrap)

```jsx
// accent 색상 = 장면 테마 색상 (민트/주황/bull)
// label = 장면 카테고리 텍스트
const Wrap = ({children, no, accent='#00FFD4', label}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor:'#0F112A', opacity:fi(f,0,8)}}>
      <div style={{position:'absolute',top:0,left:0,right:0,height:5,backgroundColor:accent}}/>
      {label && <div style={{position:'absolute',top:26,left:56,
        color:accent,fontSize:16,letterSpacing:3,opacity:fi(f,3)}}>{label}</div>}
      <div style={{position:'absolute',top:26,right:56,
        color:accent,fontSize:16,opacity:0.5}}>{String(no).padStart(2,'0')} / 전체</div>
      <div style={{position:'absolute',bottom:22,left:0,right:0,
        textAlign:'center',color:'rgba(255,255,255,0.45)',fontSize:15,opacity:.6}}>
        로또의 주식
      </div>
      {children}
    </AbsoluteFill>
  );
};
```

### 중앙 레이아웃 (Ctr)

```jsx
const Ctr = ({children, gap=24}) => (
  <AbsoluteFill style={{display:'flex',flexDirection:'column',
    justifyContent:'center',alignItems:'center',
    textAlign:'center',padding:'80px 140px',gap}}>
    <div style={{maxWidth:900,width:'100%'}}>{children}</div>
  </AbsoluteFill>
);
```

---

## Claude Code 프롬프트 (복사용)

```
내 Remotion 시스템 최종 설정:

포맷: [롱폼 16:9 / 숏폼 9:16]

색상:
- 배경: #0F112A
- 민트: #00FFD4 (제목, 강조, 화살표)
- 주황: #FFC000 (CTA, 부강조)
- 흰색: #FFFFFF (본문)
- 빨강: #FF4336 (상승 데이터만)
- 파랑: #2196F3 (하락 데이터만)
규칙: UI는 민트/주황/흰색만. 빨강/파랑은 차트 데이터에만.

렌더링:
- 화살표: SVG (thickness 4-6)
- 글자: 제목 56px/700, 부제 40px/600, 본문 24px/500
- 레이아웃: 모든 페이지 중앙 정렬

스크립트:
[여기에 스크립트 붙여넣기]

위 설정으로 Remotion 영상 생성!
```

---

## 최종 체크리스트

```
색상:
□ UI 요소에 민트/주황/흰색만 사용
□ 파랑/빨강은 차트 데이터에만

렌더링:
□ SVG 화살표 (텍스트 → 금지)
□ 글자 크기 계층 (56/40/24/16px)
□ 중앙 레이아웃 확인

코드:
□ CSS transition 금지 (interpolate만)
□ TypeScript 오류 없음 (npx tsc --noEmit)
□ 렌더링 전 미리보기 확인
```
