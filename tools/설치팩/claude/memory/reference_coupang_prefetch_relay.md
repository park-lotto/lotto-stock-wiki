---
name: reference_coupang_prefetch_relay
description: 쿠팡 상품 재료는 서버가 못 긁는다(한국 IP여도 403) — 사장님 PC 릴레이가 긁고 서버가 분석. 1단계에서 선수집
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7b8e13c8-73d2-4c35-baf7-b442f0a94a2f
  modified: 2026-08-16T13:52:22.665Z
---

쿠팡 상세·리뷰 수집은 **서버가 원리상 못 한다**. 2026-08-17 실측: AWS 서울(=한국 IP,
`ipinfo.io/country` → KR)에서도 **403**. IP가 아니라 브라우저 지문을 본다.
`product_facts.collect_raw`가 Playwright로 실제 Chrome을 띄우는 이유.

**구조**: 1단계 담기 → 영상 분석 끝 → (홈템·기타만) 큐잉 → **사장님 PC 릴레이**가
롱폴링으로 물어가 Playwright로 긁음 → 이미지 1400px 축소 base64 전송 →
**서버가 제미니 분석**(분석 키 `SHORTS_GEMINI_KEY`는 서버에만 있음) → 캐시 저장 →
2단계 대본 프롬프트에 실림.

- 릴레이 실행: `py scripts/coupang_relay_client.py` (토큰 `.env`의 `COUPANG_RELAY_TOKEN`,
  git에 없으므로 PC마다 서버 `/etc/shopping-shorts.env`에서 꺼내 넣어야 한다)
- 상태: `GET /api/coupang/relay/status` → `online`
- 재시도: `POST /api/coupang/relay/prefetch_retry {shortcode, token}`
  (선수집은 중복 방지로 한 번만 걸린다 — 실패 건은 이걸로 되살린다)
- 캐시 키: `product_prefetch_<code>`(queued|lens|done|empty) · `product_facts_<code>`

⚠️ **배포해도 릴레이는 안 바뀐다** — 따로 도는 프로세스라 **재시작해야** 새 코드로 돈다.
   이걸 놓쳐 "고쳤는데 그대로"가 한 번 났다.
⚠️ 검색어는 1단계 태깅의 `source_brief.product`(3단계 `affiliate_target`을 안 기다린다).
   무자막 해외영상도 화면만 보고 브랜드·모델까지 잡힌다(실측: 고독스 C100).
   못 잡거나 검색이 빈손일 때만 렌즈 승격(SerpApi 유료, 한 번만).

관련: [[reference_deploy_truth_branch_ssh]] · [[project_쇼핑쇼츠_자동화]]
