# 해외HOT 작업 로그

- 2026-07-26 (집PC): 해외HOT 발굴 소스를 **레딧 → 틱톡+CN(샤오·도우) Apify**로 전면 전환·라이브 배포.
  무료 probe로 발굴벽 확인 → Apify 결정. 참여속도 랭킹(build_overseas_items, CN 조회수부재 대응) +
  깔때기(overseas_funnel) + CN search_full 2개 + gap_check 번역 + 카드 UI. 라이브 39건·6카테고리 골고루.
- 2026-07-26 (집PC, 이어서): 튜닝 — 숏폼필터·가전키워드 정밀화·관련성 74%복구(허용어폐기 차단어만)·
  도우인썸네일 프록시허용. **🖐픽업**(무료크롤로 고른 틱톡 URL만 Apify postURLs 픽업) + **🔎같은영상**(렌즈 trace_url) 라이브.
- 2026-07-26 (집→사무실): **무료 Playwright 검색크롤 실측 성공** — 틱톡·인스타(조회수까지!)·샤오홍슈 로그인없이 긁힘,
  도우인만 로그인. PoC(무료크롤36→판단5→Apify픽업5) 성공. **다음: 무료크롤 전환**(2모드=해시태그발굴+소스채널마이닝,
  매일 headless, 토큰0·Apify0). Phase0 서버 데이터센터IP 스파이크부터. 설계 `docs/superpowers/specs/2026-07-26-해외HOT-무료Playwright크롤전환-design.md`.
