# 트랙: AI픽자동적재 — 핸드오프

최종 갱신: 2026-07-28 (사무실 PC) · 브랜치 `track/AI픽자동적재`

## 오늘 라이브로 나간 것 (전부 `origin/main` 반영 완료)

| # | 내용 | 커밋 |
|---|---|---|
| 1 | 담긴 영상 자동 대본적재 — 고객도 관리자와 같은 AI PICK 화면 | `78a577a65` |
| 2 | ✕가 영상을 실제로 삭제(카드 제거 + 서버 담김 멱등 remove) | `1dbaca268` |
| 3 | 새로고침해도 매칭 단계 유지 — 게이트 판정을 `stepLocked()` 하나로 단일화 | `867ebef62` |
| 4 | 자막꾸미기 "원본 자막이 있던 자리" 점선 박스 제거 | `e6183e2b3` |
| 5 | AI PICK "대본을 확보하지 못했습니다" 해소 — `pick_text`를 응답에 실어 보냄 | `eed0cf6f7` |
| 6 | **인스타 수집 Playwright 전환(코드 전체, 8커밋)** | `4a7f322d5`..`43c2109a2` |

⚠️ 6번은 **코드만 배포됐고 아직 안 쓰인다.** `INSTAGRAM_SCRAPER` 기본값이 `apify`라
라이브 수집 경로는 예전 그대로다. 켜는 건 아래 게이트를 통과한 뒤다.

## ⏭ 지금 막힌 곳 — 여기서 이어서 시작하면 된다

**2026-07-29 갱신 — B안(세션 로그인) 로컬 검증 성공. 서버 배포·진짜 10채널 게이트만 남았다.**

`scripts/instagram_setup_session.py`(Playwright 직접 로그인)는 **폐기** — 사람이 직접 타이핑해도
로그인 제출 시점에 Meta가 CDP(자동화) 자체를 감지해 캡차로 막았다(stealth·
AutomationControlled 껐어도 안 뚫림). 대신 `scripts/instagram_cookies_from_browser.py`
(Firefox에 정상 로그인 → `browser_cookie3`로 로컬 쿠키 직접 추출)로 전환해 **성공**.
Chrome/Edge는 앱 바운드 암호화로 막힘 — Firefox만 됨. 상세: 위 설계문서 "실측 결과" 섹션.

로컬에서 실제로 검증 완료:
- 세션 로그인 상태 확인(로그인전용 데이터 응답에 포함됨, `login_wall` 없음)
- 인스타 웹의 GraphQL 통합으로 파서가 깨져있던 것 별도로 발견·수정
  (`extract_reel_nodes` 신 응답 모양 지원 + `pk`로 `/api/v1/media/{pk}/info/` 직접 호출해
  taken_at·video_versions 보충)
- 5채널 스파이크: nike·gymshark·zara·starbucks `ok`(top3 전부 정확), homeinon·salimhome
  `not_found`(릴스 없는 계정으로 보임). **채널당 평균 5초**(Apify 8.4초보다 빠름)

**다음 할 일**:
1. `scripts/instagram_session.json`(로컬, git비추적)을 서버로 옮기기
   (`scp ... ubuntu@3.39.179.148:/home/ubuntu/instagram_session.json`, 600권한)
2. 서버에 `playwright-stealth` 설치 필요(로컬 `.venv`엔 있음, 서버엔 아직 — playwright 자체와
   동일하게 requirements.txt엔 안 넣고 수동 `pip install`)
3. 서버에서 `INSTAGRAM_SESSION_PATH=/home/ubuntu/instagram_session.json`으로
   **실제 등록된 레퍼런스 채널 목록**(브랜드 테스트계정 아님)으로 10채널 게이트
   (10채널 실측 문서의 재시도 명령 패턴과 동일하게 `_scrape_one_playwright` 직접 호출)
4. 성공률 8/10 이상이면 `INSTAGRAM_SCRAPER=playwright` 전환
5. Firefox 세션은 언젠가 만료된다 — 만료 시 `instagram_cookies_from_browser.py` 재실행
   (Firefox에서 재로그인 필요할 수 있음)

**구 A안(프록시) 기록은 아래 유지 — 참고용, 지금은 안 쓴다.**

서버 준비는 전부 끝났다:
- playwright 1.61.0 + 크로미움 설치 완료, `example.com` 접속으로 구동 확인 ✅
- 코드 8커밋 서버 반영 완료 ✅

그런데 인스타에 못 닿는다:
- **프록시 없이**: 4.5초 만에 `/accounts/login/`으로 튕김 (= 서버 데이터센터 IP 차단)
- **기존 Webshare 프록시**(`YTDLP_PROXY`, DE 출구) 경유: 20초·60초 **둘 다 타임아웃**

상세·재시도 명령: `docs/superpowers/plans/2026-07-28-인스타-playwright-10채널-실측.md`

### 다음 순서

1. **Webshare에서 다른 출구(가급적 KR) 엔드포인트를 받아** `INSTAGRAM_PROXY`로 넣고 1채널 테스트
   (명령은 위 실측 문서에 그대로 복사해 쓸 수 있게 적어뒀다)
2. `ok`가 나오면 → 10채널 실측 → 성공률 8/10 이상이면 `/etc/shopping-shorts.env`에
   `INSTAGRAM_SCRAPER=playwright` 추가 + `sudo systemctl restart shopping-shorts`
3. 프록시를 바꿔도 계속 `login_wall`이면 → **A안 포기, B안(부계정 세션 쿠키) 설계**로 전환

### 되돌리는 법 (문제 생기면)

`/etc/shopping-shorts.env`에서 `INSTAGRAM_SCRAPER=apify`로 바꾸고 재시작하면 즉시 원복.
코드 revert 필요 없다.

## 설계·계획 문서

- 설계: `docs/superpowers/specs/2026-07-28-인스타수집-playwright-전환-design.md`
- 구현계획(9태스크): `docs/superpowers/plans/2026-07-28-인스타수집-playwright-전환.md`
- 실측결과: `docs/superpowers/plans/2026-07-28-인스타-playwright-10채널-실측.md`
- SDD 원장(태스크별 리뷰·이월항목): `.superpowers/sdd/2026-07-28-인스타수집-playwright-전환/progress.md` (git 추적 안 됨)

## 알아둘 것 (다음 사람이 헛디디지 않게)

- **서버 메모리가 빠듯하다** — 총 1907MB에 가용 993MB. 크로미움을 여러 개 동시에 띄우면 위험하다.
- **`sudo python3 -m playwright install`은 실패한다.** root가 ubuntu의 `~/.local` 패키지를 못 본다.
  브라우저는 ubuntu 사용자로, 시스템 의존성만 `sudo PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages ...`.
- **동시성이 구현돼 있지 않다.** `_scrape_one_playwright`가 채널마다 크로미움을 새로 띄운다.
  설계서의 "브라우저 1개 + 컨텍스트 5개"는 미구현이고 `INSTAGRAM_PW_CONTEXTS`는 죽은 설정이다.
  "200채널 10분"은 현 구조로 안 나온다(15~20분 예상). 프록시가 뚫린 뒤에 손대면 된다.
- **stale 임계값이 경로별로 다르다** — apify 60분 / playwright 15분(`app.py`).
  apify는 진행률을 안 보내 `updated_at`이 안 바뀌는데 실제 28분이 걸린다.
  **하나로 합치면 정상 수집이 15분마다 "중단됨"으로 뜬다** — 최종 리뷰가 잡은 회귀다.
- **`LAST_TALLY`는 모듈 전역이다.** 수집이 동시에 두 개 돌면 집계 숫자가 섞인다.
  지금은 관리자 수동 트리거뿐이라 괜찮지만, 자동 스케줄 수집을 붙이면 그때 반드시 옮겨야 한다.
