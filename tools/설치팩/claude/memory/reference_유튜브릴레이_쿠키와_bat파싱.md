---
name: reference_유튜브릴레이_쿠키와_bat파싱
description: 유튜브 릴레이 다운로드 실패의 뿌리는 쿠키 미설정. 크롬은 ABE로 못 뽑고 파이어폭스로만 됨. bat REM 안의 <> 는 cmd가 리다이렉션으로 파싱해 set 줄을 죽인다
metadata:
  type: reference
---

2026-08-31. "유튜브가 계속 다운이 안 된다" 제보의 실제 원인 3가지.

**1) 쿠키 미설정 (뿌리)**
`yt_relay` 테이블에 같은 URL이 성공1/실패1로 갈렸고 실패 사유는 전부
`from-browser or --cookies for the authentication`. 릴레이 배치가
`YTDLP_COOKIES_YOUTUBE`를 안 걸어서 `_cookies_arg()`(media_download.py:47)가
쿠키 파일을 못 찾고 무쿠키로 나갔다. 주거용 IP라 예전엔 됐지만 유튜브가
간헐적 봇확인을 걸기 시작해 절반쯤 실패. **성공/실패가 섞이면 IP가 아니라
인증을 의심하라** — 완전 차단이면 전부 실패한다.

**2) 크롬 쿠키는 못 뽑는다 — 크롬을 닫아도 안 된다**
- 크롬 켜짐 → `Could not copy Chrome cookie database` (잠금)
- 크롬 닫음 → `Failed to decrypt with DPAPI` (App-Bound Encryption, 크롬 127+)
  yt-dlp 최신(2026.08.19)도 미해결(yt-dlp#10927). 엣지도 동일.
- **되는 길 = 파이어폭스**(ABE 없음). 유튜브 로그인 한 번 하면 끝:
  `py -m yt_dlp --cookies-from-browser firefox --cookies C:\Users\TheRose\yt_cookies.txt --skip-download URL`
  ★그러나 **파일로 뽑아둔 스냅샷은 조용히 죽는다** — 09:32 추출본이 09:50까진 되다가
  10:15에 같은 URL이 다시 봇확인. 그 순간 브라우저에서 새로 읽으면 즉시 성공했다
  (파일 자체는 멀쩡: 같은 파일 3회 연속 사용에 크기·성공 불변). 유튜브가 세션을
  회전시켜 옛 스냅샷을 무효화한 것. **처방 = 매번 브라우저 직독**:
  `YTDLP_COOKIES_BROWSER_YOUTUBE=firefox` 를 두면 `_cookies_arg()`가
  `--cookies-from-browser firefox` 를 쓴다(값 없으면 종전 파일 경로라 서버 회귀 0).
  쿠키 없이 되는 길은 없다 — player_client 5종(tv_simply/web_safari/tv/mweb/android_vr)
  전부 봇확인으로 기각.

**3) bat REM 주석 안의 `<URL>` 이 배치를 통째로 죽인다**
주석이어도 cmd는 줄의 `<` `>` 를 리다이렉션으로 먼저 파싱하고 `%VAR%`도 확장한다.
`REM ... --skip-download <URL>` 한 줄 때문에 아래 `set "YT_RELAY_KEY=..."`가
안 먹어 릴레이가 `YT_RELAY_KEY 환경변수가 없습니다`로 즉사 반복했다.
**bat 주석엔 `<` `>` `%` `&` `|` 쓰지 마라.** 고친 뒤 set 구간만 떼어 실행해 검증했다.

또 하나: **쿠키를 고쳐도 화면은 계속 빨갛다.** `produce_autoload`가 attempts=3으로
차면 자동 재시도를 멈춘다. 원인을 고친 뒤엔 그 행을 지워 래치를 풀어야 다시 탄다.
"고쳤는데 화면 그대로"면 릴레이 기록에 **새 요청이 있었는지**부터 봐라 — 없으면
코드가 아니라 래치다.

검증: 실패하던 `youtube.com/shorts/q7S9sW_pVgc`를 서버 큐에 넣어 릴레이가
6,428,159바이트 mp4를 서버에 올림(로컬 다운로드 크기와 일치).

⚠️ 릴레이 PC가 2대다(`tools/yt_relay_start.bat` = TheRose PC,
`deploy/yt_relay_agent.bat` = CH PC). **CH PC엔 쿠키 파일이 아직 없다** —
경로만 박아뒀고(없으면 무쿠키 폴백이라 회귀 없음) 그 PC에서도 파이어폭스
로그인 후 위 명령으로 뽑아야 완전히 해소된다.

⚠️ 서버 IP가 3.35.251.172로 바뀌었다 — [[reference_server_ip_changed_2026_08_05]]의
43.200.48.69는 낡았다. 이번에 그 낡은 IP를 보고 "서비스가 죽었다"고 오진했다.
**SSH 붙기 전에 `nslookup shoppingshorts.duckdns.org` 부터 하라.**
