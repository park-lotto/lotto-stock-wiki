---
name: project_ttalkkak_studio
description: 딸깍 스튜디오 — 버튼 하나로 브리핑 카드 자동생성+텔레전송하는 내부도구(녹화용 연출 겸용)
metadata: 
  node_type: memory
  type: project
  originSessionId: fa1ce68d-7d2c-4780-baa8-9d050f0f3a63
---

딸깍 스튜디오: `/studio` 페이지(FastAPI:8090, `dashboard/server.py`)에서 버튼 하나로 아침 브리핑 카드를 생성. 흐름 = 데이터수집(`scripts/studio_data.py`)→Gemini 히로이미지(`scripts/gemini_image.py`, 실패 시 골드 그라데이션 폴백)→카드 HTML 렌더(`scripts/card_render.py`, `.card` 420px 다크+골드 Instrument Serif)→PNG(viz_card.save_png)→텔레전송(viz_card.send_telegram_photo). 오케스트레이션+SSE 5단계 이벤트는 `scripts/studio_pipeline.py`, 트렌디 UI(macOS프레임+갤러리+미리보기+단계 애니메이션)는 `dashboard/studio.html`.

레퍼런스: Threads @devdesign.kr (좌측 작업목록 갤러리 + 우측 미리보기). 목적 = 진짜 도구 + 녹화하면 콘텐츠 되는 화면 둘 다.

**상태(2026-06-28)**: 서브에이전트 TDD 완성·main 머지·push 완료(18 tests). 실데이터(06-05) 진짜 테스트 성공 → 풍부한 카드 생성+텔레전송 확인.
**바탕화면 바로가기**: `딸깍 스튜디오.lnk`(Desktop) → `dashboard/launch_studio.ps1`(서버 8090 자동기동+/studio 브라우저 오픈). 서버는 python.exe 콘솔 최소화로 띄움(pythonw는 server.py의 sys.stdout.reconfigure 때문에 죽음 — 쓰지 말것).
**★ 차별화 핵심(2026-06-28 피벗)**: 일반 브리핑은 가치 없음 → **수급빈집 탑픽**으로 전환. `signal_snapshot.json`(stage3: 498종목 vacancy A/B·rs·score·flags[빈집/수출/컨센신고가/어닝서프/판가/미국커플링/정책/D30], stage2.sortino={섹터:점수} dict, stage1 verdict/vix/us_strong_sectors)에서 **주도섹터(소르티노상위) ∩ 빈집A ∩ score≥3 → score·RS 랭킹**으로 탑픽 산출. 각 픽에 atoms.db 근거(content+source+date) 부착. signal_snapshot 기반이라 daily_scenario 없이 매일 작동. `scripts/studio_picks.py`(get_picks)+`scripts/card_picks.py`(통합카드: 시황+점검+주도섹터+탑픽4). 딸깍 버튼 기본 모드=picks(generate_picks), briefing은 mode=briefing. 06-27 실증: SK하이닉스4점RS58·브이엠·테스·원익IPS, 텔레전송 성공.

**중요 주의/후속**:
- daily_scenario 실제 출력은 **이모지 섹션 형식**(`📌 오늘 핵심`/`🔴 강세 종목`/`💡 시나리오`/`🎯 오늘 한 줄`), `## 헤더` 아님. studio_data가 이 형식을 파싱(headline=🎯한줄, lead_sectors=🔴강세 종목명, lines=📌핵심불릿).
- Gemini 이미지: **무료 티어는 image 모델 limit:0**(아예 생성 불가)→항상 폴백 그라데이션. 진짜 AI 히로 보려면 **빌링(결제) 활성화** 필요. 예비키 `GEMINI_API_KEY_2` 자동전환은 미구현(어차피 무료면 둘다 0).
- `out/scenario_{날짜}.md` 없으면 카드 빈약 → `python daily_scenario.py` 선행. 산출물 `out/studio/`는 gitignore.
- 확장: 콘텐츠 타입(종목요약·숏폼)은 card_render 템플릿 추가로.

설계/계획: `docs/superpowers/specs/2026-06-28-딸깍-스튜디오-design.md`, `docs/superpowers/plans/2026-06-28-딸깍-스튜디오.md`. 관련 [[project_ttalkkak_dashboard]] [[project_daily_scenario]] [[project_briefing_design]].
