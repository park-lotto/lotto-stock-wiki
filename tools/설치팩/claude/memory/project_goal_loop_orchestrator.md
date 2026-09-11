---
name: project_goal_loop_orchestrator
description: "골-루프 오케스트레이션 v1(아침브리핑) 빌드 상태·재개법. Task1-2 완료, 3-7 남음"
metadata: 
  node_type: memory
  type: project
  originSessionId: 174439c8-05f0-4472-9abf-783a04b1935b
---

# 골-루프 오케스트레이션 v1 — 아침 시장 브리핑 (2026-07-02)

**무엇**: "목표 주면 스스로 루프 돌며 오케스트레이션"하는 상위 시스템. 첫 골=아침 브리핑.
서버 파이썬 데몬(08:00 평일 자율) + Gemini 품질루프 + 하이브리드 게이트(이상징후만 사장님 확인).

**설계 결정**: ①아침브리핑 ②하이브리드 게이트 ③품질루프+복원력 ④런타임=서버 파이썬 데몬(Claude Workflow 아님 — 무인 8시엔 Claude 세션 못 켜져 있음. Lightsail 24h + 기존 `_summary_prewarm` 데몬패턴 재사용). 브리핑 생성기 이미 3개 존재(`studio_pipeline.generate_briefing`=카드+텔레 / `morning_briefing.py` / `daily_scenario.py`) → v1은 "생성"이 아니라 오케스트레이션 껍데기만.

- 스펙: `docs/superpowers/specs/2026-07-02-goal-loop-orchestrator-design.md`
- 계획(7태스크 TDD 실제코드): `docs/superpowers/plans/2026-07-02-goal-loop-morning-brief.md`
- 진행원장: `.superpowers/sdd/progress.md`

## 실전 배포·검증 완료 (2026-07-03 오후)
- **OWNER_CHAT_ID = @parklotto13bot**(=기존 CHAT_ID/OPS_CHAT_ID, 사장님 개인 업무보고봇). 로컬+서버 반영.
- ⚠️**서버에 프로젝트 .env 자체가 없던 것 발견**(BOT_TOKEN/CHAT_ID/GEMINI_API_KEY 등 전부 못읽던 상태) → 6개 GEMINI키+텔레키 전부 서버 .env로 반영. 이게 없었으면 골루프뿐 아니라 기존 studio_pipeline 브리핑카드도 서버에서 텔레발송 불가였을 것.
- **daily_scenario.py 단일키→로테이션 개선**: `get_gemini()`가 GEMINI_API_KEY 1개만 쓰다 429 나면 그냥 실패하던 걸, 6키(GEMINI_API_KEY·_2, GEMINI_INGEST_KEY·_2~_4)+모델폴백(gemini-3-flash-preview→2.5-flash) `generate_with_rotation()`으로 교체. 커밋 fdd54bf0.
- ⚠️**서버에 playwright 자체가 없어서 카드 PNG가 한번도 안 만들어지고 있었음**(기존 기능도 영향받았을 가능성) → `playwright install --with-deps chromium` 설치(반드시 서비스 실행유저=ubuntu로, sudo로 하면 root캐시에 잘못 들어감). Pillow도 설치(히어로이미지 폴백용).
- **실전 스모크 테스트 성공**: 2026-07-03 실제로 코스닥 -3.9%~-4.8% 급락한 날 → 이상징후 정확히 감지→에스컬레이션(자동채널발행 안함)→카드PNG 렌더→OWNER 텔레 실제전송 확인("✅텔레그램 전송완료"). C1(빈데이터 헛소리방지)도 이전 라운드에서 실전 검증됨.
- ⚠️**서버 git push 안 됨**(자격증명 없음, pull만 가능) — 서버 로컬에 병합커밋들(edcfc153 등 타 세션 핫픽스) 존재, origin과 완전동기화는 아직. 매번 pull시 `git merge origin/main`으로 수동 병합 필요(충돌은 지금까진 없었음).
- **아직 GOAL_LOOP_ENABLED 안 켬**(사장님 최종 GO 대기). 켜는 법: 서버 /etc/stockbrain.env에 GOAL_LOOP_ENABLED=1 추가 + 재시작.

## 인포그래픽 추가 완성·병합 (2026-07-03 저녁, 세번째 라운드)
사용자 피드백("내용 안중요, 클로드식 그라데이션 이미지 안받으려고 노트북 연동한건데 안됨") →
확인해보니 텍스트만 NotebookLM으로 바꿨을뿐 히어로이미지는 옛날 Gemini(나노바나나,
gemini-2.5-flash-image) 그대로였음. **나노바나나 실측**: 등록된 Gemini 키 8개(API_KEY·_2,
INGEST_KEY·_2~_4, BRIEFING_KEY·_2) 전부 429 동일 실패 — "오늘 소진"이 아니라 무료티어
자체가 이 이미지모델 쿼터 0으로 막아놓은 구조적 제한(키 늘려도 무의미, 실측 확인됨).
→ 브레인스토밍→스펙→계획(5태스크)→서브에이전트구현→개별리뷰(전부 1발통과)→
최종검수(opus, MERGE)→**origin/main 병합 완료**(5aa88d8e, 56테스트).
**설계**: 히어로슬롯 완전제거(텍스트만) + NotebookLM 인포그래픽(nlm_bridge.create_infographic,
create_report와 동일 동기폴링패턴) 병행발송. **인포그래픽 생성 성공이 "정상발행" 필수조건**
— 실패하면 텍스트카드도 보류하고 기존 에스컬레이션(C1/I1/I2)으로 흡수(신규 게이트 안 만들고
기존 flags 리스트에 얹음 — 안전성 재사용). 기존 studio_pipeline.py(대시보드 인터랙티브 UI)는
render_briefing_card(data, hero_path=None) 기본값만 추가해 완전 하위호환.

✅**서버 코드 배포 완료**(같은 저녁): dashboard/server.py 등 5개 파일 origin/main에서 checkout,
stockbrain.service 재시작, 56테스트 서버에서도 통과. atoms.db ingest 밀림은 자연 해소됨(571건).

🚨**신규 발견 — nlm CLI가 서버(Lightsail AWS)에서 인증 자체가 안 됨 (미해결, 중요)**:
`uv tool install notebooklm-mcp-cli`로 nlm 설치는 됐지만, `nlm login`이 "성공" 메시지(쿠키
40+개 추출)를 내고도 바로 이어지는 `nlm login --check`(실제 API 검증)에서 즉시
"Credentials have expired"로 실패. **7번 이상 반복 재현**(snap chromium, 정식
google-chrome-stable 둘 다, 로컬에서 복사한 유효 쿠키까지) — 전부 동일 패턴.
**결론: 브라우저/설정 문제가 아니라 구글이 이 서버 IP를 자동화 트래픽으로 판단해
API 검증 단계에서 거부하는 것으로 추정**(로그인 UI는 통과, 후속 API 호출만 거부됨 —
전형적인 데이터센터 IP 평판 차단 패턴). 로컬(Windows PC)은 정상 작동.
Xvfb+x11vnc+websockify(noVNC)로 원격 로그인 인프라는 구축·검증됨(재사용 가능,
`nlm login --force` 실행 후 `http://localhost:6080/vnc.html?password=lotto2026vnc`로
접속하는 방식 — VNC/websockify 프로세스는 작업 종료 시 정리함, 재개 시 재구성 필요).

**다음 세션 검토할 옵션**:
1. Lightsail 고정IP 재할당 후 재시도(IP 평판이 인스턴스별로 다를 수 있어 저렴한 실험)
2. 골루프 오케스트레이터(run_morning_brief) 자체를 서버가 아닌 로컬PC에서 스케줄 실행
   (Windows 작업 스케줄러) — "무인 서버 데몬" 설계 원칙과 충돌, 재설계 필요
3. 로컬PC에 상시 relay API 두고 서버가 nlm 호출을 그쪽으로 위임 — PC 상시 켜짐 전제 필요
4. 프록시/VPN으로 서버 발신 IP를 신뢰 IP로 변경

⚠️ **이 문제 때문에 GOAL_LOOP_ENABLED는 계속 OFF 상태 유지해야 함** — Stage0/인포그래픽
전부 nlm 인증에 의존하므로 지금 켜면 매일 에스컬레이션만 발생(안전하게 막혀있는 상태,
급하지 않음).

⚠️**"둘 다 준비돼야 발행" 트레이드오프**: 인포그래픽까지 1분 가까이 걸릴 수 있어 매일 아침
발행이 예전보다 늦어질 수 있음. 또한 같은 날 수동 재실행 시 scenario.md 캐시로 인해
notebook_id 없어 인포그래픽 스킵→에스컬레이션(의도된 동작, 08시 데몬 1일1회 경로엔 무관).

## Stage0 NotebookLM 교체 완성·병합 (2026-07-03 오후, 두번째 라운드)
사용자 피드백("카드퀄리티 안좋아서 노트북lm으로") → 브레인스토밍→스펙→계획(4태스크)→서브에이전트 구현→
개별리뷰(1회 수정루프: add_source_urls 테스트누락)→최종검수(opus, MERGE승인)→**origin/main 병합 완료**
(커밋 945d40c0~3cf7c41d, 41테스트). daily_scenario.py 대신 인사이트허브 NotebookLM 파이프라인
재사용(nlm_bridge.py로 추출, notebook_stage0.py가 A=구조화카드+B=심층리포트 매일 생성).
안전장치(C1빈데이터가드·I1fail-closed·I2침묵금지) 전부 재검증·무회귀 확인.

⚠️**4개 동시 Claude세션 환경 교훈**: main 워크트리(공유폴더)는 사용자가 여러 창을 동시에 써서
거의 항상 미커밋 변경 있음 → "깨끗해지길 기다리기"는 비현실적. **해법**: 별도 임시 워크트리를
`origin/main`에서 새로 만들어 거기서 병합·테스트하고, `git push origin <머지커밋SHA>:main`으로
로컬 main 브랜치 건드리지 않고 원격에 직접 push(로컬 main은 다른 워크트리가 물고 있어 강제이동 불가하나
SHA push는 우회 가능). 공유 main 폴더의 미커밋 파일 절대 건드리지 않음 — 나중에 그쪽이 pull하면 합류.
이 프로젝트엔 post-commit 훅(단순 git push)이 있어 커밋마다 자동 push됨.

⚠️**미해결**: GOAL_LOOP_ENABLED 아직 OFF(사용자 최종 GO 대기). 서버 배포(git pull+restart)도
아직 안 함 — main엔 반영됐지만 라이브 서버는 이전 daily_scenario 버전 그대로. 다음 세션: 배포+
실전 스모크테스트(어제처럼) 먼저 하고 GO 여부 확인.

## 최종 상태 (2026-07-03 완성·main 병합)
- **7태스크 전부 완성 + 최종검수(opus) + 수정 → main 58787b05 병합·push.** 18테스트 통과.
- 검수가 잡은 중대문제 수정: **C1**(Stage0 누락→빈데이터서 헛소리 발행 위험) = `_ensure_scenario`(daily_scenario 실행)+빈데이터 가드(revise 안 하고 즉시 에스컬레이션) / **I1** OWNER_CHAT_ID 없으면 채널로 ⚠️ 안 보냄(fail-closed) / **I2** 실패도 침묵 안 하고 대기+알림, `send_telegram_message` 추가, gemini 폴백.
- ⚠️**데몬 기본 OFF**: `GOAL_LOOP_ENABLED=1`일 때만 가동. **가동 절차**: 서버 배포(git pull;restart) → `/etc/stockbrain.env`에 `OWNER_CHAT_ID`(사장님 개인 텔레) + `GOAL_LOOP_ENABLED=1` → 스모크 1회(`run_morning_brief` 수동실행) → 정상 확인 후 다음날 08시 자동.
- ⚠️**미해결(v1 한계, 문서화됨)**: I3 이상징후가 08시 장전이라 지수 ±3%·staleness 신호 사실상 죽음(품질루프+빈데이터가드가 안전망). 향후 개선: 콘텐츠기반 폭락키워드 검사 or 미국증시 오버나이트 활용. M3 goals/*.yaml 템플릿 미구현(상수 하드코딩).
- 브랜치 feat/goal-loop-v2(origin), 진행원장 `.superpowers/sdd/progress.md`.

## (구) 상태 — 서브에이전트 실행 이력
- ✅ Task 1: `viz_card.send_telegram_photo(chat_id=None)` — commit **142bb50c**, 리뷰통과
- ✅ Task 2: `scripts/goal_loop/verify.py` 이상징후 — commit **027af395**, 3테스트
- ⬜ Task 3: `pending.py`(대기 상태) / 4: `quality.py`(Gemini 비평·개선, data dict 대상) / 5: `morning_brief.py`(오케스트레이터) / 6: 대시보드 발행엔드포인트+버튼 / 7: 08시 데몬+배포+`OWNER_CHAT_ID`

**보존**: 브랜치 `feat/goal-loop-morning-brief` **origin에 push됨**(Task1-2 안전). 핵심 fn 계약은 계획서 안에.

## ⚠️ 재개법 (git 충돌 주의)
2026-07-02 다른 세션(atoms structured_fields·채널온보딩·[[project 사람브레인]])이 **같은 저장소에서 동시에 커밋·브랜치전환·cherry-pick** → feat/goal-loop 히스토리에 타 워크스트림 혼입, 워킹트리 main 이동. NEXT_SESSION.md도 그쪽이 점유.
재개: ①동시 세션 끝났는지 확인 ②main에서 새 브랜치 ③`git cherry-pick 142bb50c 027af395` ④계획서 Task3부터 subagent-driven 이어서 ⑤끝나면 main병합→서버배포+OWNER_CHAT_ID.

## 곁다리 이슈 해결(같은날)
- 히트맵 큐레이션(숨김29·이름변경7) 초기화돼 보임 → 원인=`_heatmap_merge_keep`이 숨긴 섹터까지 이전캐시에서 되살림. **서버 직접 핫픽스**(숨긴 섹터·hidden_sectors 제외). ⚠️**git엔 미반영 — 내일 dashboard/server.py `_heatmap_merge_keep`에 `_hidden` 제외 로직 커밋 필요**(안 하면 다음 배포 pull때 핫픽스 날아감). 데이터는 안전(파일+스냅샷 무사).

[[project_dashboard_deploy]] [[feedback_break_long_tasks]]
