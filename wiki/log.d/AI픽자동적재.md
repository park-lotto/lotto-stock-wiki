
## 2026-07-28
- 인스타 수집 Playwright 전환: 설계→계획 9태스크→SDD로 코드 7태스크 구현·리뷰 완료, main 병합(548cf96a7). 플래그 기본 apify라 라이브 무변경.
- 최종 리뷰(Opus)가 Critical 2건 포착: stale 임계값이 apify 경로 회귀 / 진행률이 배너 DOM 파괴. 수정 후 재리뷰 ADDRESSED.
- 서버 playwright+크로미움 설치 완료·구동 확인. 그러나 인스타 접근 실패: 직결=login_wall(4.5s), Webshare DE 프록시=타임아웃(20s·60s). 게이트 불통과로 전환 보류.
- 그 외 라이브: ✕ 실제삭제, 새로고침 단계유지, 자막꾸미기 점선박스 제거, AI PICK pick_text.

## 2026-07-29 — 인스타 세션로그인(B안) 프로덕션 전환 완료 ✅
- 샤오홍슈 성공패턴("막힌 건 IP가 아니라 로그인 여부") 이식 시도. Playwright 직접 로그인은
  Meta의 CDP 자동화 감지로 캡차벽 — stealth·AutomationControlled 껐어도 안 뚫려 폐기.
- 완전히 다른 방식으로 전환: Firefox에 정상 로그인 → browser_cookie3로 로컬 쿠키 직접 추출
  → storage_state 변환. 로그인 자동화 흔적 자체가 없어 캡차 회피 성공.
  (Chrome/Edge는 앱 바운드 암호화로 막힘 — Firefox만 됨)
- 별개 발견: 인스타 웹이 REST→GraphQL 통합돼 파서가 0건 반환하던 버그 수정
  (`extract_reel_nodes` 신 응답모양 지원 + pk로 `/api/v1/media/{pk}/info/` 직접호출해
  taken_at·video_versions·caption 보충).
- **서버 실제 192채널 전수 수집 게이트 통과**: ok 187 · not_found 5 · login_wall 0 · error 0,
  19.1분 소요(Apify 28분보다 빠르고 403 위험 0). `INSTAGRAM_SCRAPER=playwright` 프로덕션
  전환 완료(라이브 서버 `/etc/shopping-shorts.env` 반영, 재시작 확인).
- 트랙 병합 중 `test_mix_naturalize.py::test_beat_tts_applies_naturalize_and_continuity`
  flaky 실패로 finish 게이트 2회 튕김(인스타 코드와 무관, 재현 시 있다 없다 함) — 3번째 재시도로 통과.
