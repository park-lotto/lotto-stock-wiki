---
name: project
description: 빼쓰기(생성) 순응 검열 라이브 — 은행이 실제로 대본을 형성했나 매 job 관측
metadata: 
  node_type: memory
  type: project
  originSessionId: 37220a0d-1206-4f7f-b38c-d107b92f10f9
  modified: 2026-07-23T02:43:34.239Z
---

쇼핑쇼츠 검열의 "빼서 쓰는 쪽" 확장(2026-07-23 라이브, origin/main b0f9128c9). 넣기 검열([[project_부품은행]]의 gemini_audit)에 이어, **은행에서 부품·스파인 빼서 대본 만들 때 제미니가 진짜 은행을 따랐나**를 매 영상 job 관측.

**구조**: 결정적 3층 + 샘플 LLM. `bank_assemble.bank_usage_snapshot`(주입내역·empty) + `bank_usage_audit.py`(structural_conformance 강오프너/CTA/비트/표절, judge_snapshot, compute_usage_audit, usage_health 신호등) + `bank_compliance.judge_compliance`(은행 주입 job **N=10에 1편**만 아크/부품 순응 LLM 채점 — 병목 제미니 최소부하) + `store.append_bank_usage`(bank_usage_recent 링버퍼 K=50) → mix_pipeline 배선(bank_usage_audit_last 저장) → /api/bank/ingest_report usage_audit → index.html _renderBankPanel "🎬 생성 순응" 섹션.

**핵심 원칙**: 회귀 0 = `bank_enabled != "1"`이면 완전 no-op(모든 관측이 try/except 삼킴). 순응 감지를 LLM 매번 안 돌리고 결정적 신호(구조·표절 재사용) 위주 + 샘플만 LLM = 넣기 29% 성공률 병목을 안 건드림.

**SDD 8태스크 전부 opus 리뷰+최종 whole-branch 리뷰 통과**(seam=생산키↔소비키 일치 확인, 무단 블랭크 없음). 로컬 42 passed.

**후속**: 흡수 성공률 개선(top_n 상향, 키실패 vs 빈추출 metric 분리) = 넣기 쪽 별개. 한계: usage_audit 패널이 수집 done 폴링에 얹혀 렌더(수집 안 하면 생성순응 따로 안 보임).
