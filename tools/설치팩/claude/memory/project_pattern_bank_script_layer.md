---
name: project_pattern_bank_script_layer
description: 부품은행(대본 학습층) — Phase0(스키마·8버킷·큐레이션)+Phase1(자동크롤결합·perf·스파인클러스터·F1행위사전) 라이브. 스파인 승격게이트·R4필터·주입점 핵심
metadata: 
  node_type: memory
  type: project
  originSessionId: e26b6f80-358b-46da-bd39-3cd7903d10a0
  modified: 2026-07-21T05:58:54.719Z
---

부품은행 = 대본 학습층. 스파인 기계(build_scene_first_plan)는 이미 돌고, 고정 손잡이 2개(_STORY_RULES_CORE 등)를 학습 데이터로 교체하는 설계. [[project_scene_spine_2track]]의 대본쪽 확장.

**설계/검토**: `docs/superpowers/specs/2026-07-21-대본학습층-부품은행-스파인라이브러리-design.md`(코어) / `...-응용-백본인터리브-팩토리-design.md`(응용, A7 행위태깅 커버율 스파이크가 게이트) / `docs/superpowers/reviews/2026-07-21-대본학습층-페이블검토.md`.

**Phase0 라이브**(3014d01a2): pattern_bank 스키마(pattern_source·pattern_item·spine)·8버킷 추출·큐레이션 API/페이지(pattern_bank.html)·F5 네거티브뱅크.

**Phase1 라이브**(2026-07-21, 1f4689be2, 10태스크 TDD): 트랙 `부품은행`.
- ④ **F1 행위 액션 사전**(`action_dict.py`): categorize.KEYWORDS 패턴 복제. script_extract._RESPONSE_SCHEMA에 action enum(무과금)+`_assign_seg_ids` 결정적 폴백(tag_action). edit_plan._build_inventory에 `행위:` 노출.
- ① **perf 저장배관**(`perf_score.perf_from_item`): 필드별 nullable 매트릭스 — **saves=전무·followers=인스타전용(별도 profile콜)·댓글=도우인/샤오홍슈 없음, views/likes/comments가 신뢰삼종**. 0 지어내지 말 것. store setters(list_pattern_sources·set_pattern_source_perf/spine·pattern_source_url_exists). 야간 `ingest_crawl_winners`=우승작(grade)×대본(wiki_list, 조인키 shortcode) opportunistic 흡수, url dedup.
- ② **perf_score**(A2): 플랫폼내 로그백분위(log1p)×최근성감쇠(반감기30일)+views/followers 보정. 상수 모듈상단. 야간 `recompute_perf_scores`=부품 perf_score를 인용소스 최댓값으로.
- ③ **스파인 클러스터링**(`spine_cluster.py`, A1): enum힌트(기존 스파인명+`__NEW__` 센티넬)로 신규 남발 억제. 야간 `cluster_and_gate_spines`. **승격게이트=source_count>=3 AND status='approved'(사람). 배치는 절대 자동승인 안 함(pending만). 부품 MIN_SAMPLES=1과 분리.**

**핵심 규칙**(재작업 시 반드시): **[R4]** 통계·perf·fit_categories는 `category_source IN ('user','gemini')`만(keyword 추측 54%정확, 오염). 모든 Gemini콜 `call=`/`ingest_fn=` 주입점(테스트가 실 API 안 침, `pattern_bank._default_call` 기본). 새 야간스텝은 daily_batch.run() 순차호출(크론=서버 crontab `python -m shopping_shorts.daily_batch`, repo엔 스케줄러 없음). 기준선 실패 8건.

**★2026-07-21 저녁 대전환(믹스+대본 실사용 디버깅)**: 사장님이 실렌더로 문제 지적하며 방향 확정. 핵심교훈=[[feedback_anchor_to_real_goal_backbone_interleave]]. 실사고·수정 다수:
- **은행이 텅 비어 있던 게 대본 허접의 뿌리**(pattern_item/source/spine=0). '위키에 담기(학습반영)'가 은행에 안 넣고 있었음 → api_wiki_save에 `_ingest_pattern_bank` 배선(훅·어미·부사·CTA 자동적재+스타일 자동승인 auto_approve_style_buckets)+생성 자동주입(마스터스위치 ping_pong_enabled 켜지면 assemble_bank_context 주입). 레시피39개 백필=380부품(227승인).
- **서버 SHORTS_GEMINI_KEYS=0** → pattern_bank 추출 0부품이던 근본버그. `_default_call`이 빈 SHORTS면 key_vault 예비풀(general)로 폴백(`_vault_fallback`). ⚠️ad-hoc python은 서비스 env(/etc/shopping-shorts.env) 안 실려 SHORTS 0 → 검증 시 `set -a; . /etc/shopping-shorts.env` 로드 필수.
- **AI 검수** `curate.py`: 밋밋한 '여러분~이렇게 드세요' 설명체 훅을 Gemini 배치판정 기각(훅39→14기각). rubric=궁금증·긴장·반전·강한주장·인물상황=keep.
- **짤드라마 강제**(script_generate._STORY_RULES_CORE 최상단): '여러분/이렇게하세요' 설명체 금지, 구체 인물·상황·갈등·반전 미니드라마. 재미강도 tone_score.fun_intensity(D14).
- **최상위 조합 4개**(스파인 시드, perf1.0·레시피): 역발상경고·인물드라마·충격결과·비밀궁금증형, [대괄호] 슬롯 갈아끼우기.
- **검증완료**: 실 생성대본이 '남편이 야식 찾길래…투덜대더라고요…웬걸…댓글 감자'(짤드라마·은행어미·비법CTA). 옛 설명체→드라마 전환 확인.
- **믹스쪽**: ping_pong(행위매칭 fit거짓말잡기)·백본순서·길이양방향(fill+trim)·dedup_and_balance(반복·s1편중 해소, 단 s2=0=Gemini선택편중은 서브의무삽입 필요·미구현)·백본선정(인스타/유튜브만·댓글수·platform_of·backbone_forced통로, UI토글 미완). 백본-베이스(generate_backbone_script 흐름따라 우리대본·있는장면만) 커밋했으나 미배선.
- ⚠️기존 요소장치(generate_variations elem_modes+element_category_stats)와 은행 목적겹침 → 은행이 같은 generate_variations에 주입되므로 사실상 통합됨(별 시스템 아님).

**다음**: ①큐레이션UI(스파인 승인버튼·perf배지를 pattern_bank.html에 — 현재 데이터만 쌓이고 화면 없음) ②Phase2(생성이 은행에서 조립+대화체 스코어러, F4 골든셋 회귀평가 선구축) ③서버 야간배치 1회 실행 로그로 실 Gemini경로 관측(mock테스트라 실동작 미관측).
