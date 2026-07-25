# 해외HOT 발굴 — 핸드오프

- 갱신: 2026-07-26 (집PC) / 트랙: 해외HOT (병합 후 폴더 유지)

## 현재 상태 — Apify 발굴전환 라이브 완결 ✅
레딧 발굴을 **틱톡 + CN(샤오홍슈·도우인) Apify 발굴**로 전면 전환. main 병합·서버 배포 완료.

- **왜 전환**: 레딧 틈새 서브의 hot은 "틱톡 바이럴 원본/선점"과 불일치 → 잡탕(80건 중 76건 일반바이럴,
  꿀템 카테고리 0). 무료 발굴경로(틱톡 tiktok:tag broken·Creative Center gated·CN 검색추출기 없음)는
  전부 벽 확인 → Apify 유료로 결정(사장님 승인).
- **재활용**: `apify_client`(토큰17개 `/etc/shopping-shorts.env`) · `tiktok_search.search_full` ·
  `gap_check` · store/job/폴링/🌍탭. 신규: CN `search_full`2개 · `build_overseas_items`(참여속도 랭킹) ·
  `overseas_funnel`(형식·관련성·안터진상한) · job 재작성 · 카드 UI.
- **랭킹 = 참여속도**: CN은 조회수를 안 줌(실측: 도우인 playCount=0, 샤오홍슈 view필드 없음) →
  랭킹 기준을 **(좋아요+댓글+수집+공유)/경과h** 로 통일(세 플랫폼 좋아요 자릿수 유사). 조회수는 표시용.
- **깔때기**: STAGE0 쿼리(유료 40/카테고리/플랫폼) → 형식·관련성·안터진상한(무료) → 참여속도 랭킹 →
  dedup → 생존자만 gap_check(쿼터보호). 폐기 카테고리(옛 레딧) 자동퇴출 가드 있음(셀프힐링).
- **실측 라이브(2026-07-26)**: 39건, 6카테고리 골고루(가전14·인테리어6·뷰티6·정리5·주방4·살림4),
  전부 tiktok/douyin/xiaohongshu. 옛 레딧 잡탕 퇴출 완료.

## 검증 상태
- 신규 유닛테스트 전부 통과(seeds3·build_overseas3·douyin2·xhs2·funnel4·gap2·job4). 전체게이트 통과(기준선 11건 무관).
- 라이브 실수집 1회 성공(949초/39건). **주의**: `/api/*`·`/`는 로그인 게이트라 익명 curl은 401/랜딩(정상).
- 서버 Apify 토큰 17개 `/etc/shopping-shorts.env`(systemd EnvironmentFile). 앱 config는 여기서 env 로드.

## ⏭ 다음 (Phase 2 — 남은 것)
1. **CN 선점뱃지 = 현재 "미확인"** — `gap_check` 번역이 CN 중국어제목→한국어가 안 돼(translate_keyword
   방향이 KO→ZH로 추정) 안전하게 미확인 처리 중. ZH→KO 번역경로 붙이면 CN도 🔥선점 판정 가능.
   (거짓 선점 방지 위해 번역결과에 한글 없으면 미확인 반환하도록 구현돼 있음 — Task7)
2. **관련성/생존율 튜닝** — 시드 키워드(overseas_seeds.json)·차단어(overseas_funnel.BLOCK_WORDS)·
   조회수상한(DEFAULT_VIEW_CEILING=300만) 라이브 며칠 보고 조정.
3. **가속(accel) 정착** — 참여 Δ의 Δ는 2회+ 스냅샷부터 성립. 매일 수집 누적되면 급상승 신호 강화.
4. **Phase 3** — 생존자 yt-dlp 다운로드 → [재편집] → mix 파이프라인 연결.

## 파일
설계 `docs/superpowers/specs/2026-07-26-해외HOT-Apify발굴전환-design.md`
계획 `docs/superpowers/plans/2026-07-26-해외HOT-Apify발굴전환.md`
핵심코드 `overseas_hot_jobs.py`·`overseas_funnel.py`·`ranking.build_overseas_items`·
`douyin_search.search_full`·`xiaohongshu_search.search_full`·`gap_check.gap_badge(translate=)`·
`static/index.html`(renderOverseas 카드)·`overseas_seeds.json`
