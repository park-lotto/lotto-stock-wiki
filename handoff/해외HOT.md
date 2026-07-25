# 해외HOT 발굴 — 핸드오프

- 갱신: 2026-07-25 (집PC) / 트랙: 해외HOT (병합 후에도 폴더 유지)

## 현재 상태
- **Phase 1 (Reddit 발굴→랭킹→탭)** · **Phase 2 (선점뱃지 gap_check)** · **Phase 2.5 (OAuth+UI토글 수정)** 전부 코드 완료·라이브 배포.
- 숏템박스 랭킹화면 → **🌍 해외HOT** 진입탭 → 카테고리 필터 큐. `/api/overseas/{update,status,feed}`.

## ⚠️ 회사에서 이어서 할 일 (코드 아님 — 서버 설정 1가지)
**완료 0건의 근본원인 = 익명 Reddit RSS의 rate-limit(429).** 라이브 SSH 진단으로 확정:
서버IP·시드·코드는 정상(BeAmazed는 200·영상 17건 확인됨). 익명 한도가 낮아 배치 36요청이
대부분 429로 빈손 → 0건. **해결책 = Reddit OAuth**(코드는 이미 붙임 — 크레덴셜만 넣으면 자동 전환).

### Reddit 앱 등록 → 서버 .env (⏭ 남은 유일 작업)
```
1. https://www.reddit.com/prefs/apps 접속 → "create another app…"
2. type= "script" 선택 / name=아무거나(예: stocklab-overseas) / redirect uri= http://localhost:8080
3. 생성 후:
   - client_id = 앱 이름 바로 아래(제목 밑) 짧은 문자열
   - secret    = "secret" 항목
4. 서버 .env에 추가 (ssh ubuntu@3.39.179.148):
     REDDIT_CLIENT_ID=<client_id>
     REDDIT_CLIENT_SECRET=<secret>
   그리고: sudo systemctl restart shopping-shorts
5. 확인: 해외HOT 탭 → "지금 업데이트" → 이제 100req/분이라 429 없이 수집됨(업보트 실값·속도/가속).
```
크레덴셜이 없으면 코드는 RSS 폴백으로 계속 돌지만(rate-limit에 취약) 크레덴셜 넣으면
`reddit_source._has_oauth()` True → oauth.reddit.com JSON 경로로 자동 전환.

## 검증 상태
- 신규 테스트 29/29 통과(reddit_source OAuth+RSS·ranking·store·jobs·api·gap_check·tab smoke).
- RSS 폴백 로컬 실측 13건(oddlysatisfying/top). OAuth 경로는 **유닛테스트만** — 크레덴셜
  넣고 라이브 1회 확인 필요(⏭ 회사에서).
- gap_check(선점뱃지)는 서버 YouTube 키로 실판정, 로컬 무키는 '미확인' degrade.

## Phase 3 (나중)
yt-dlp 원본 다운로드·[재편집]→mix 연결 / TikTok 시드계정(overseas_seeds.json seed_accounts) /
Apify 해시태그 검색 선택토글 / niche 카테고리는 TikTok이 더 적합(Reddit은 general 바이럴 위주).

설계 `docs/superpowers/specs/2026-07-24-해외HOT발굴-design.md` · 계획 `.../plans/2026-07-25-해외HOT발굴-phase1.md`
