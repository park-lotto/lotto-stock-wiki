# 릴레이VMake (관제 315) — 2026-11-03 TheRose PC

## 무엇·왜
사장님 제보: 관리자 마지막 작업 VMake 실패 + 렌즈 검색 안 됨.
뿌리(실측):
1. 관리자 f9d97335bda1 고급 지우기 — VMake 서버에서 progress 0.99 로 50분 정지(예상 787초). 우리 폴링은 367회(1시간) 다 채우고 poll_timeout. 21:07 재실행은 4분 40초에 정상 완료.
2. 렌즈 틱톡 0건 — 쿠팡도우미(PC 릴레이)가 서버 재시작(03:05) 뒤 한 번도 안 붙음(자동 시작 없음).
3. 도우미 붙은 뒤에도 0건·136초 — 릴레이 줄이 FIFO 라 백그라운드 상품재료 19건(건당 30~60초, 쿠팡 403) 뒤에서 틱톡 요청이 75초 제한 초과.
4. 도우미 없을 때 63~72초 — 서버 틱톡 브라우저 경로(늘 0건)가 60+9초 대기.

## 고친 곳
- shopping_shorts/vmake_sdk/core/api.py status: 진행률 5분 그대로 + 예상×2(최소 10분) 넘으면 poll_stalled (MT_AI_POLL_STALL_MIN_S=0 이면 끔)
- shopping_shorts/vmake_client.py remove_subtitles: poll_stalled → 장부 비우고 1회만 재제출
- shopping_shorts/coupang_relay.py take: background(submit_async) 일감은 뒤로
- shopping_shorts/kw_backends.py pw_tiktok: 릴레이 없으면 서버 브라우저 생략(KW_TIKTOK_SERVER_PW=1 로 되살림)
- tools/coupang_relay_start.bat(재시작 루프, 로그 %TEMP%\coupang_relay.log) + tools/coupang_relay_install_startup.ps1
- 시험 shopping_shorts/tests/test_relay_vmake_315.py (고치기 전 코드에서 실패 확인함)

## ⏭ 남은 것
- 쿠팡 403: 이 PC(KT 서울)에서도 막힘. .coupang_profile → .coupang_profile_blocked_20261103 로 백업. 새 프로필 1회 3건, 재시험 0건 — 원인 미확정
- VMake SDK 'Skill version is outdated' 경고(미조치)
- 회원 c9d6dd692fc9: 새 VMake 키 넣어도 재지우기 안 하고 흐림 완성(미조사)
- 서버 failed 유닛: instagram-collect / instagram-discover / video-audit (미조사)
