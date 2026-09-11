---
name: project-wiki-synth-engine
description: 위키 종합엔진 — 원자를 종목 페이지에 자동 녹이는 엔진. 반도체 프로토타입 미완(수율14%·claude -p파괴). 단순화 재설계 필요
metadata: 
  node_type: memory
  type: project
  originSessionId: c778810e-4955-43d4-8a00-cffbe0bc5a5d
---

원자(news·텔레·리포트·youtube·blog 추출본)를 종목 페이지 골드 포맷(SK하이닉스 기준)에 자동으로 녹이는 종합엔진. 2026-06-22 brainstorming→spec→plan→구현(서브에이전트 TDD)까지 진행, 반도체로 실증했으나 미완.

**작동 원칙(확정)**: 저신뢰(텔레·뉴스)도 위키에 반영하되 `⚠️미검증`/`(설)` 태그. staging은 고위험 주장(파트너십·납품·M&A)만. 출처는 실존 raw 파일만(날조 금지). 모르면 "위키에 없음".

**미완 3구멍 + 재설계** (수율 14%):
1. 날짜 윈도우가 *내용 날짜*로 잘라 백로그 67% 제외 → `created_at` 기준으로.
2. 섹터 페이지(1007줄) 통째 재작성 실패 → 섹션타겟 갱신.
3. 시장레벨 반도체 내용이 sector='기타' 오분류 → 분류 보강.
4. **claude -p 종합 폐기** — 에이전트라 stdout에 잡담/요약 섞여 페이지 파괴(삼성전자). → 서브에이전트가 Write로 직접 쓰기(무료·안전).

**[2026-06-23 결정적 원인 규명]** 수율14%의 핵심 원인 발견: `atomizer.py` 프롬프트가 `content` 필드를 안 시킴 → Gemini가 본문을 안 주고 → 후처리 `if not content: continue`로 **content 없는 원자 전량 폐기(0개)** → 긴 텔레/뉴스가 통째 유실. 종목매칭·claude -p 이전에 **입력 자체가 안 들어가고 있었음**. content 필드 추가로 수정(그로스리서치 24K: 0→15개, 대신시황: 0→8개 확인). 종목명 정규화는 기우(hot 6/6 매칭). 등급=atoms 원자수 자동산정(gen_tiers.py).

**핵심 교훈**: "제대로 만들었나"만 검증하지 말고 "쓸모있나(수율)"를 먼저 검증. 복잡 엔진 전에 단순버전("바뀐 종목마다 서브에이전트 1개가 페이지 갱신")으로 값어치 확인. 14일 윈도우·복잡 라우팅은 과설계.

코드: `pipeline/atoms/synth_*.py` / 설계: `docs/superpowers/specs/2026-06-22-위키-종합엔진-design.md` / 브랜치 `feat/synth-engine`→main. 관련: [[project_atom_db_gaps]]
