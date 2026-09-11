---
name: reference_인스타세션_전멸과_복구
description: 인스타 수집 0건의 원인은 프록시가 아니라 계정 세션 전멸. 판정은 반드시 실제 수집 코드로 하고, 복구는 파이어폭스 프로필별 재로그인+이메일 인증
metadata:
  type: reference
---

2026-08-31. 인스타 수집이 하루아침에 0건(08-30 145건 → 08-31 0건).

## 오진 두 번 — 판정 도구를 잘못 골랐다

1. **"서버 IP가 429"** — 서버에서 `api/v1/users/web_profile_info`를 치니 429,
   집 IP는 200이라 IP 차단으로 단정했다. **틀렸다.** 그 API는 실제 수집 경로가 아니다.
   프록시를 태워 **HTML 페이지를 받아보면 200**(619KB)이 나온다.
2. **"프록시가 아예 없다"** — `INSTAGRAM_PROXY`가 비어 있길래 그렇게 말했다. **틀렸다.**
   인스타 프록시는 `WEBSHARE_USER/PASS`로 `channel_archive.slot_proxy(i, pool)`가
   슬롯마다 조립한다(계정↔IP 1:1). 실측: 슬롯별로 219.248 / 58.225 / 182.208 한국 주거용.

**교훈: 판정은 실제 수집 코드로 한다.**
```
_scrape_one_playwright('아무채널', session_path=슬롯파일, proxy=slot_proxy(i, POOL_REFERENCE))
→ (reels, 최종URL, err)
   릴>0                      : 살아있음
   URL이 instagram.com/      : 로그아웃(세션 죽음)
   URL에 update_risky_...    : 본인확인 잠김
```
API 응답코드·쿠키 존재 여부로 판정하면 전부 헛다리다. `sessionid`가 파일에 **있어도**
인스타가 서버 측에서 죽인 상태일 수 있다.

## 진짜 원인과 복구

계정 세션 10개 **전멸**. 복구는 사장님 PC에서:
1. 파이어폭스 **프로필별로** 인스타 재로그인 (한 프로필=한 계정. 갈아타면 직전 세션이 죽는다)
2. 잠김(`update_risky_contactpoint`)은 **이메일 인증하면 풀린다**(실측)
3. `py scripts/ig_session_capture.py` → `scripts/ig_sessions/*.json`
4. 서버 `/home/ubuntu/ig_sessions/reference/` 로 복사 (`z1_`·`z2_`·`z3_` 접두사 유지, 계정ID로 매칭)

⚠️ **적립 전에 파이어폭스를 완전히 닫아라.** 실행 중이면 쿠키가 메모리에 있어
디스크(cookies.sqlite)에 없다 → 옛 쿠키를 뽑는다.
⚠️ **적립 도구의 `[OK]`는 "쿠키가 있다"는 뜻이지 "살아있다"가 아니다.**
⚠️ **화면이 자동 로그인된 것처럼 보여도 세션은 안 줄 수 있다**(실측 2건).
⚠️ 로그인한 프로필 확인은 `cookies.sqlite` mtime으로. 사장님이 내가 지정한 프로필이
   아닌 다른 걸 고르실 수 있다(실제로 그랬다).

## 동시 실행 금지

강제 수집(`service.collect`)을 돌리는 중에 타이머 서비스가 렌더 대기를 풀고 같이 떴다.
같은 세션을 둘이 쓰면서 **그쪽은 127채널 실패**, 그리고 그때 쓰던 두 계정이 다시 죽었다.
게이트를 우회해 강제 실행할 땐 타이머 서비스 상태를 먼저 확인하라.

## 저장 위치 (다른 플랫폼과 다르다)

인스타만 `snapshots` 테이블 + `store.save_run()`.
유튜브·틱톡·쓰레드는 `platform_snapshots` + `save_run_platform`/`save_last_run_platform`.
`last_run::instagram` 키는 **없다** — 인스타를 platform_snapshots에서 찾으면 "0건"으로 오독한다.

관련: [[reference_계정프록시_덮어쓰기함정]] · [[reference_하루1회_스킵은_그날0건]]
