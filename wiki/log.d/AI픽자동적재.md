
## 2026-07-28
- 인스타 수집 Playwright 전환: 설계→계획 9태스크→SDD로 코드 7태스크 구현·리뷰 완료, main 병합(548cf96a7). 플래그 기본 apify라 라이브 무변경.
- 최종 리뷰(Opus)가 Critical 2건 포착: stale 임계값이 apify 경로 회귀 / 진행률이 배너 DOM 파괴. 수정 후 재리뷰 ADDRESSED.
- 서버 playwright+크로미움 설치 완료·구동 확인. 그러나 인스타 접근 실패: 직결=login_wall(4.5s), Webshare DE 프록시=타임아웃(20s·60s). 게이트 불통과로 전환 보류.
- 그 외 라이브: ✕ 실제삭제, 새로고침 단계유지, 자막꾸미기 점선박스 제거, AI PICK pick_text.
