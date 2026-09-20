---
name: project_telegram_ingest
description: 텔레그램 인제스트 시스템 완성 — 17채널 타입별 질문지→2층 원자. 외국주 comment 드롭 후속 결정 필요
metadata: 
  node_type: memory
  type: project
  originSessionId: de7ca053-7eff-4b16-b7a7-1a8982360976
---

텔레그램 17개 채널을 타입별 질문지(Gemini flash-lite)로 추출 → 2층 원자로 atoms DB 누적. 리포트 인제스트([[project_crawling_pipeline]]) 패턴 차용. **9 Task SDD 완료, main 병합·push 완료 (2026-06-21).**

- 설계: `docs/superpowers/specs/2026-06-21-텔레그램-인제스트-design.md`
- 계획: `docs/superpowers/plans/2026-06-21-텔레그램-인제스트.md`
- 핵심 모듈: `pipeline/atoms/telegram_ingest.py`(오케스트레이터, `--all/--date/--dry-run`), `telegram_questionnaire.py`(질문지5종+fan-out), `telegram_registry.py`(채널맵+별칭), `stock_resolve.py`(정규화+미매칭로그), `telegram_stance.py`(스탠스만료), `verify_telegram.py`(quote대조)
- 채널맵: `telegram_channels.json` (sector/market/stock_tips/insight/report_relay × 신뢰등급 B/C). 제외: 리포트요약·투경현황
- **2층 모델**: FACT(append)/STANCE(stance_key 갱신, 과거 is_active=0 보존)/METHOD(매매방법론). 의견 만료로 위키 부패 방지가 핵심
- 일일 파이프라인 `scripts/atom_pipeline.py` STEP3.5로 자동 실행(7AM 스케줄러)
- 별칭사전 `stock_aliases.json`, 미매칭 종목명은 `raw/telegram_unmatched.log`에 쌓임 → 주기적으로 별칭 보강(🔧 튜닝)

**해결됨:**
- ✅ **news_relay 타입 0원자 버그(2026-07-05)**: `telegram_channels.json`에 4채널(주식픽·실시간속보단독뉴스·실시간주식뉴스·그로쓰리서치특징주)이 `news_relay` 타입으로 등록만 되고 `telegram_questionnaire.py`엔 그 타입 구현이 아예 없어서(QUESTIONNAIRES.get(ctype)→None) 매일 조용히 0원자였음. 질문지+`questionnaire_to_atoms_tg` 분기 추가로 해결(뉴스 stock 있으면 종목원자, 없으면 시장원자). 겸 Gemini가 JSON 뒤 여분문자 붙여 반환할 때 `json.loads` 전체실패하던 것도 `raw_decode()` 폴백으로 복구.
- ⚠️ **미해결(코드 아님, 플랫폼 이슈)**: `실시간주식뉴스`·`그로쓰리서치특징주` 두 채널은 원격 크롤봇(Lightsail 3.39.179.148) 계정이 2026-07-03 이후 새 메시지를 전혀 못 받음. 채널 자체는 활발(공개 프리뷰 확인), 계정도 정상멤버(밴/추방 아님), Telethon raw GetHistory로도 07-03 데이터만 반환 — 재시도로 안 풀림. 07-03에 이 4채널 크롤주기를 15분마다로 올린 시점과 일치, 텔레그램 리드제한(shadow limit) 추정. 다음 조치: 계정으로 두 채널 나갔다 재입장 검토.
- ✅ 외국주→섹터 매핑(2026-06-21): `foreign_sector_map.json`. 미매핑은 `raw/telegram_foreign_unmapped.log` 큐레이션.
- ✅ **report_relay 외국주 드롭 버그(2026-07-01)**: `report_relay` 핸들러가 KRX 미매칭 종목을 else분기 없이 전량 폐기 → 한투글로벌(글로벌IT 리포트채널) 전 파일 0원자. `add_stocks` 패턴(`_foreign_sector_atom`)을 report_relay에도 이식해 복구. 겸 **요약하는고잉 report_relay→insight 오분류 교정**(시황·코멘트 채널). 6월 백로그 재처리(telegram_ingest --all, 0원자=done아님이라 자동 재선택).
- ✅ 종목 섹터 자동분류 sector_hint(2026-06-21): `sectors.json`(18섹터 config, 확장가능) + `sector_classify.resolve_sector`. Gemini가 추출 시 모든 종목에 섹터 태깅 → 한국주·외국주 "기타" 고정 해결(삼성전자→반도체 등). 우선순위: 외국map → hint정확 → hint부분 → 기타. foreign_sector_map은 오버라이드 강등. 라이브 확인(삼성전자·SK하이닉스→반도체). 81 tests pass.

**완료 추가(2026-06-21 자동진행):**
- ✅ **뉴스 인제스트**: post 소스 추가(`post_sources` news, header_label=["출처","키워드"] 폴백). 라이브: 아시아경제→방산, 호르무즈묶음→조선. atom_pipeline STEP3.8. → **5소스 완성**(리포트·텔레·블로그·유튜브·뉴스).
- ✅ **daily_health MVP**: `daily_health.py`(compare_to_baseline·render_card·collect_signals·main). 기존신호만(원자수·개선큐로그·pytest)→어제대비→정상=1줄/이상=상세 텔레카드(send_telegram 재사용). atom_pipeline STEP6. 라이브: ✅카드 텔레 실발송 확인. 설계=docs .../daily-health-검증시스템-design.md. **후속**: run-log·flag율 훅(MVP 제외).
- ✅ **리포트 섹터 통일**: questionnaire.py가 `_guess_sector_from_stock`("기타" 고정) 제거→`resolve_sector`(sector_hint). `_SECTOR_LIST`→sectors_list(). 리포트 종목도 섹터 분류됨. **후속**: sectors.json에 옛목록 우주·LNG·AI소프트웨어 없음(사용자 큐레이션) — 필요시 추가.

- ✅ **채널간 이벤트 병합**(A 비파괴 선택, 2026-06-21): `event_merge.py` — event/macro 원자를 `_event_key`로 그룹핑, 다른 source_name 2개↑면 mention_count/mention_channels UPDATE(삭제 없음). atom_pipeline STEP3.9. 멱등. **한계(실측)**: exact-fact 매칭이라 채널들이 같은사건 다른표현시 안 묶임(06-19 라이브 0건). verbatim 복붙만 잡힘. **후속**: 의미기반 매칭(임베딩 유사도)으로 업그레이드.
2. 골든셋 픽스처 `fixtures/tg_spike.json`의 insight stance/methods는 손보강분(실 Gemini 출력 아님) → 라이브 재생성 권장
3. foreign_sector_map 커버리지 — `telegram_foreign_unmapped.log` 주기적으로 보고 매핑 보강(별칭사전과 같은 운영)
4. 섹터 택소노미 통일 — 다른 파이프라인 5곳에 하드코딩 섹터리스트 잔존(questionnaire.py:97·taxonomy.py:56·atomizer.py:31·pdf_ingest.py:67·sector_signal/prompt_v_final.py:5) → sectors.json으로 통일 후보
5. **daily_health 검증시스템** — ✅ 설계문서 완성·커밋(`docs/superpowers/specs/2026-06-21-daily-health-검증시스템-design.md`), **구현 보류**. atom_pipeline STEP6, 신호6종→어제대비→정상=한줄/이상=상세 텔레카드. 결정론적(무료). 선행훅: run-log+ingest flag집계. 구현은 blog/youtube 후.
6. **소스 확장(C안)** — 텔레그램 패턴을 blog→youtube→뉴스로 확장.
   - ✅ **블로그→유튜브 겸용화**(2026-06-21): blog_ingest/blog_questionnaire를 **범용 `post_ingest`/`post_questionnaire`로 편입**(삭제). 소스 차이(폴더·헤더라벨 출처/채널·레지스트리·source_type)는 `post_sources.py` config. `python -m pipeline.atoms.post_ingest --source blog|youtube`. atom_pipeline STEP3.6=blog/STEP3.7=youtube. 텔레 2층 fan-out·sector_classify 재사용. 라이브: blog/pokara61 sector=바이오, youtube/한균수 market+stock(바이오·조선). 97 tests. 레지스트리: blog_registry.json·youtube_registry.json(채널→trust, 기본C).
   - **뉴스 추가 = post_sources에 한 줄 + news_registry**. (다음)
   - 후속: raw/yt 스크립트노이즈는 _FNAME 강제로 해결됨 / --source 잘못입력 KeyError(daily는 무관).
