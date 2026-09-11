---
name: reference_extract_cache_key_lens_prefix
description: "태깅 캐시 조회 키에 lens_ 접두사가 빠져 틱톡 소스가 통째로 불발 — \"재태깅했는데 대본이 그대로\"의 진짜 원인"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 053a5ce9-6039-4b81-9dd4-3eb72b569b08
  modified: 2026-08-16T08:19:46.024Z
---

같은 영상이 **경로에 따라 다른 키**로 `script_extracts`에 저장된다:

```
담기 경로 → 7458060642738605355
렌즈 경로 → lens_tiktok_7458060642738605355
렌즈(짧은해시) → lens_tiktok_1jw6i6i        ← URL에서 만들 수 없다
```

`mix_pipeline._cache_key_for_url()`은 **앞 형태 하나만** 반환해서, 틱톡 소스는
캐시에 재태깅본이 있는데도 한 번도 안 맞았다. 실측(job `8873eeb48a08`, 2026-08-17):
고치기 전 인스타 1건 적중 / 틱톡 2건 불발 → 고친 뒤 **3/3 적중**
(label 17/10/10, use_point 17/10/10, source_brief 3개 다).

**증상은 "재태깅했는데 대본이 안 좋아진다"로 보인다.** 태깅은 멀쩡하고 조회만 빗나간 것.
덤으로 매번 Gemini 재추출이 돌아 비용도 이중이었다.

**Why:** 저장하는 곳과 찾는 곳이 키 규칙을 따로 정했다(0순위-B의 전형 — 같은 판단이 두 군데).

**How to apply:**
- "재태깅/재분석했는데 하류가 그대로"면 **코드를 고치기 전에 캐시가 실제로 적중하는지 먼저 재라.**
  DB에 있느냐가 아니라 **그 코드가 쓰는 키로 찾아지느냐**를 확인한다.
- 캐시 키는 후보 목록(`_cache_keys_for_url`)으로 만들고 호출부는 순회한다.
- 서버 DB는 `shopping_shorts/data/reference.db`다(`config.DB_PATH`). `app.db`에도
  같은 테이블이 있지만 0건 — 여기서 헛짚기 쉽다.
- 라이브 API를 SSH curl로 찌르면 유료게이트라 **401**이다. DB를 직접 읽어라.
- `/tmp/*.json`에 다른 세션이 남긴 옛 파일이 있다 — 날짜·소유자를 보고 써라.

관련: [[project_scene_spine_first]] · [[feedback_verify_with_real_data]] · [[project_gemini_key_ops_2026_08_04]]
