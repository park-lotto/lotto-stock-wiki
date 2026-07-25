# 해외HOT 발굴 — 핸드오프

- 갱신: 2026-07-25 (회사PC) / 트랙: 해외HOT (병합 후 폴더 유지)

## 현재 상태 — 라이브 완결 ✅
해외HOT "완료 0건" 근본해결 후 **라이브 피드에 꿀템 영상 80건 실제 수집** 확인.

- **429 근본원인** = AWS 데이터센터 IP를 Reddit이 익명 RSS에서 막음(계정나이 아님, about.json으로 확정).
- **해결1: 주거용 프록시** — Webshare 로테이팅. `REDDIT_PROXY` env로 RSS(urllib)·OAuth(requests) 둘 다 경유.
  서버 실측: 4연속 200(429 소멸). **서버 .env에 이미 설정됨**(REDDIT_PROXY=...@p.webshare.io:80).
- **해결2: 시드 교체** — 기존 시드(gadgets/GifRecipes/cooking/SkincareAddiction)는 사진 중심이라 영상0.
  영상 실측으로 재선정: 주방=Kitchenhacks, 살림꿀템=INEEEEDIT, 인테리어/DIY=ArtisanVideos,
  가전/도구=SpecializedTools+GadgetGifs, 만족감/제품=oddlysatisfying+SatisfyingAsFuck,
  신기템/바이럴=BeAmazed+nextfuckinglevel.
- **안전망: 429 백오프** — 프록시 실패 대비 RateLimited 재시도(env REDDIT_RL_RETRIES/BACKOFF).

## 실측 근거
- 서버 실서비스 _run(): proxy_on=True, **count=80**, 86초. (원본 186 → 중복제거·영상필터·_CAP 로테이션 후 80)
- 커밋: e068cff18(프록시) + 4fc51a174(시드) → origin/main 9a5bd670c 병합·배포 완료.
- 테스트 25/25 통과. 서버 HEAD 9a5bd670c, 새 시드·프록시 env 반영 확인.

## 수집 내용 / 한계
- 수집 = 메타데이터(제목·영상URL(v.redd.it)·썸네일·순위점수). **영상 파일 다운로드는 [재편집] 단계 별도.**
- 영상 플랫폼 = 전부 v.redd.it(틱톡 바이럴의 레딧 재업로드본). tiktok.com 원본 링크는 아님.

## ⏭ 집에서 이어서 (다음 작업)
1. **육안 확인**: shoppingshorts.duckdns.org 해외HOT 탭 → "지금 업데이트" → 80건·카테고리 필터 확인.
2. **가전/도구 카테고리 영상 보강** — SpecializedTools(2)·GadgetGifs(0)로 약함. 대체 서브 발굴 필요.
3. **[재편집]→제작소 연결(Phase 3)** — v.redd.it mp4 다운로드 → mix 파이프라인 투입.
4. (선택) tiktok.com 원본 링크가 필요하면 별도 소스(틱톡 해시태그) 검토. overseas_seeds.json seed_accounts 비어있음.

설계 docs/superpowers/specs/2026-07-24-해외HOT발굴-design.md
메모리 reference_reddit_anon_rss_datacenter_429
