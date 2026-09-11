---
name: youtube-shorts-datacenter-block
description: 유튜브 쇼츠 다운로드 차단 = 서버 데이터센터 IP만 문제. 주거용 IP(사장님 PC)는 쿠키 없이도 됨. 해법=프록시 or 로컬릴레이
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7ce7ffe1-2a07-4052-a7e6-9e49296ff07c
  modified: 2026-07-24T11:55:23.563Z
---

유튜브 "Sign in to confirm you're not a bot" 차단의 실체(2026-07-24 가설 4개 실측):

- **서버(AWS Lightsail 데이터센터 IP)**: yt-dlp 최신(2026.07.04)·유효 로그인 쿠키(세션 5개)·player_client 우회(mweb/tv/web_embedded) **전부 실패**. 쇼츠는 하드 차단(일반 watch 영상은 쿠키로 제목까지는 됨).
- **주거용 IP(사장님 PC)**: 같은 쇼츠 URL을 **쿠키 없이 1초 만에 실다운로드 성공**(2.4MB mp4).
- 즉 쿠키 갱신·클라이언트 우회로는 못 풀고, **IP 종류가 결정**한다. 쿠키 파일은 yt-dlp가 매 요청 덮어써 실패 응답이 로그인 쿠키를 로그아웃으로 갈아엎는 부차 문제도 있음(--cookies는 복사본으로 쓸 것).

**해법 A(로컬PC 릴레이) = 2026-07-24 구축·라이브·E2E검증 완료.**
- 서버는 유튜브 URL을 `yt_relay` 큐에 넣고 폴링(`config.YT_RELAY_ENABLED=1`, `download_any`→`_download_via_relay`).
  PC 에이전트 `python -m shopping_shorts.youtube_relay_agent`(env `YT_RELAY_KEY`, 서버와 동일)가 큐를
  폴링→주거용 IP로 yt-dlp 다운로드→`POST /api/yt_relay/deliver`로 업로드. 서버는 CPU/디스크 부하 0(전부 PC).
- 엔드포인트 `/api/yt_relay/*`는 로그인 가드(_auth_guard) 예외 + 자체 키(YT_RELAY_KEY) 인증.
- 서버 env: `/etc/shopping-shorts.env`에 `YT_RELAY_ENABLED=1`+`YT_RELAY_KEY=…`. **PC에선 ENABLED 끄기**(안 그러면 무한루프).
- ⚠️ 에이전트 print는 utf-8 강제(cp949 콘솔이 '—'·이모지에서 UnicodeEncodeError로 죽음).
- E2E 실측: 서버 enqueue→에이전트 픽업→PC다운로드→업로드→서버에 629KB mp4 저장 성공.
- **PC 에이전트가 꺼지면 유튜브 소스가 큐에서 타임아웃(180s)**난다 — 상시 켜둘 것(항상성 원하면 B 프록시).

**해법 B(주거용 프록시) = 2026-07-24 라이브·서버 실검증 완료 → 이게 서비스용 정답.**
- 서버 `/etc/shopping-shorts.env`에 `YTDLP_PROXY=http://user:pass@host:port` 한 줄. 코드가 유튜브 yt-dlp
  호출에 `--proxy`를 붙인다(`media_download._proxy_arg`, 유튜브만·틱톡 등 제외). **우선순위 프록시>릴레이(A)>직접.**
- 업체=**Webshare Rotating Residential**(1GB $3.50, 쇼츠 ~400편). 프록시 형식 `p.webshare.io:80` user/pass.
- 실검증: 서버(데이터센터 IP)가 프록시로 유튜브 629KB 다운로드 성공(직접 yt-dlp·download_any 앱경로 둘 다).
- **B가 켜지면 A(PC 릴레이)는 안 씀**(코드가 프록시 우선) → 사장님 PC 불필요, 고객 전원 사용 가능. A는 백업.
- ⚠️ 프록시 비번은 **서버 env에만**(git 금지). env 파일 CRLF는 `sed -i 's/\r$//'`로 정리(bash source 시 $'\r' 에러).
- ⚠️ **회전 프록시 엔드포인트 품질이 국가별로 천차만별**(2026-07-24 실사고): Webshare GB(`bhkvcxfo-gb-1`)는
  502 Tunnel failed 남발+2~6KB 깨진 파일(2/5) → 사장님 믹스서 유튜브 소스 통째 스킵됐다. **DE/CA/FR은 3/3
  정상 2.5MB**. 교체=env `bhkvcxfo-gb-1`→`bhkvcxfo-de-3`. 새 프록시는 **반드시 실다운로드+파일크기(>100KB)로
  검증**하라(연결만 되고 깨진 조각 주는 함정). 코드도 유튜브 프록시 경로에 `--extractor-retries/--retries 10`
  넣어 드문 502에 소스가 안 빠지게 함(`media_download._proxy_arg`).

**How to apply**:
- "유튜브 다운 안 됨" 제보 → 쿠키부터 만지지 말고 **로컬 PC에서 같은 URL 실측**으로 IP 문제인지 즉시 판별.
- 프록시 소진 시 Webshare 대시보드서 충전. 다른 업체도 `http://user:pass@host:port`면 그대로 동작.
- 쇼츠 1편 ≈ 2.4MB(0.6MB인 것도) → residential proxy 1GB로 수백 편.
