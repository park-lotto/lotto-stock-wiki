---
name: remotion-effects-library
description: T3CHFEED 스타일 Remotion 효과 라이브러리. 완성된 컴포넌트 목록과 미구현 효과 스펙.
metadata: 
  node_type: memory
  type: project
  originSessionId: 4102237c-381a-443b-bacd-10b591c78630
---

# Remotion 효과 라이브러리 (T3CHFEED 스타일)

**상세 파일**: `channel/strategy/remotion_효과_레퍼런스.md`
**가이드 파일**: `channel/strategy/strategy_remotion_가이드.md` (세션 시작 시 읽는 파일)

## 완성된 효과 (✅ 즉시 사용 가능)

| 효과 | 파일 | 핵심 파라미터 |
|------|------|-------------|
| DocHighlight | `scenes/DocumentHighlightScene.tsx` | 형광펜 #FFE500 opacity 0.52 |
| FocusZoom | `scenes/FocusZoomDemo.tsx` | blur(9px) + 중앙이동 + scale 1.22× |
| TechFeed | `scenes/TechFeedScene.tsx` | brightness(0.35) + stagger 22f 간격 |

## 미구현 효과 (🔧 필요 시 구현)

| 효과 | 용도 | 비고 |
|------|------|------|
| ImpactText | 큰 숫자·임팩트 문장 | 인라인으로도 가능 |
| HubDiagram | MCP 개념 설명 | SVG stroke-dashoffset |
| SplitScreen | 좌우 동시 비교 | CSS flexbox |
| LogoIntro | 채널 인트로 | 로고 파일 필요 |

**Why:** 카카오×Claude 영상(2026-06-14) 기획 중 T3CHFEED 레퍼런스 분석으로 수집·구현
**How to apply:** 새 씬 제작 시 이 라이브러리에서 먼저 골라서 적용. 없으면 스펙 작성 후 구현.
