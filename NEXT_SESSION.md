# NEXT_SESSION — 골루프 인포그래픽 카드 + 서버 인프라 정비

**날짜**: 2026-07-03 · **주제**: 골루프 아침브리핑 카드에서 클로드식 그라데이션 이미지 제거 +
NotebookLM 인포그래픽 병행발송 기능 완성. 서버 인프라 문제 다수 발견·해결.

## 이번 세션 요약

### ✅ 완료: 인포그래픽 카드 기능 (설계→구현→테스트56개→리뷰→병합→서버배포)

사용자 피드백("클로드식 그라데이션 이미지 안받으려고 노트북 연동한건데 안됨") → 실제로는
텍스트만 NotebookLM으로 바꿨을 뿐 히어로이미지는 Gemini 나노바나나 그대로였음이 원인.

- **나노바나나 실측**: 등록된 Gemini 키 8개 전부 429(쿼터0, 무료티어 구조적 제한) 확인
- **결정**: 히어로 이미지 슬롯 완전 제거(텍스트만) + NotebookLM 인포그래픽 병행발송(별도 사진)
- **필수조건 변경**: 인포그래픽 생성 성공이 "정상 발행" 조건에 포함 — 실패시 텍스트카드도
  보류하고 기존 안전장치(C1/I1/I2)로 에스컬레이션
- 스펙: `docs/superpowers/specs/2026-07-03-goal-loop-infographic-design.md`
- 계획: `docs/superpowers/plans/2026-07-03-goal-loop-infographic.md` (5태스크 전부 완료)
- 5개 파일 수정(card_render.py/nlm_bridge.py/server.py/notebook_stage0.py/morning_brief.py)
  → **main 병합 완료**(5aa88d8e) → 서버 배포 완료 → **실전 검증 성공**(라임그린 HUD 스타일
  인포그래픽 실제 생성+텔레그램 전송 확인됨, 151초 소요)

### 🚨 발견·해결: 서버 인프라 문제 (오늘 처음 실측으로 드러남)

1. **`nlm` CLI가 서버에 아예 설치돼 있지 않았음** — `uv tool install notebooklm-mcp-cli`로 설치
2. **`nlm login --check` 명령어 자체가 버그** — 로그인 성공해도 항상 "만료"로 오답. 실제
   검증은 `nlm notebook list`(진짜 API 호출)로 해야 함. (다른 세션이 발견)
3. **서버 스왑(가상메모리) 0바이트**였음 — 무거운 작업(Chrome+nlm) 시 서버가 멎는 원인.
   **2GB 스왑 추가 완료**(재부팅해도 유지, `/etc/fstab` 등록됨). 오늘 밤 이 문제로 서버
   2번 다운 → 사용자가 Lightsail 콘솔에서 Stop→Start로 복구
4. **`nlm` 실행파일이 재부팅시 PATH에서 사라짐** — `/usr/local/bin/nlm`, `/usr/local/bin/
   notebooklm-mcp` 심볼릭 링크로 영구 해결
5. **NotebookLM "인포그래픽 생성"(Studio 기능)만 이 서버에서 rate limit 걸린 것으로 추정**
   — 노트북 4개·스타일 2종·계정 2개(parklotto12/parklotto20) 전부 시도했지만 전부 7분+
   "in_progress"에서 멈춤. 일반 기능(노트북생성/질문)은 정상. 시간 지나면 풀릴 가능성 높음.
6. **다른 세션이 `stockbrain1.duckdns.org/vnc-login/`이라는 영구 VNC로그인 페이지를
   이미 만들어둔 것 발견** — 오늘 밤 두 세션이 같은 nlm 인증 문제를 동시에 풀고 있었을
   가능성 높음(서버 다운 원인 중 하나였을 수도). **다음 세션: 이 중복 작업 정리/조율 필요**

## 미완료 / 다음 할 것

- [ ] **인포그래픽 rate limit 풀렸는지 재확인** — `PATH=$HOME/.local/bin:$PATH nlm notebook list`로
      인증 확인 → `notebook_stage0.build_notebook`+`generate_infographic`로 실전 테스트
- [ ] `stockbrain1.duckdns.org/vnc-login/` 페이지(다른 세션 작업)와 오늘 만든 임시 VNC
      인프라 정리·통합 — 중복 작업 여부 확인
- [ ] `GOAL_LOOP_ENABLED`는 여전히 OFF — 위 rate limit 문제 해소 확인 후 사용자 최종 GO 대기
- [ ] 클로드/테라코타 스타일(에디토리얼) 인포그래픽 실험은 미완료 — rate limit 풀리면 재시도
- [ ] 오늘 만든 테스트 노트북들은 전부 삭제 완료(정리됨)

## 관련 파일

- 인포그래픽 스펙/계획: `docs/superpowers/specs/2026-07-03-goal-loop-infographic-design.md`,
  `docs/superpowers/plans/2026-07-03-goal-loop-infographic.md`
- 오케스트레이터: `scripts/goal_loop/morning_brief.py`, `notebook_stage0.py`, `scripts/nlm_bridge.py`
- 메모리: `project_goal_loop_orchestrator.md`(전체 히스토리), `feedback_simple_before_complex.md`
