# 인기상품 랭킹 (관제 240) — 시안 단계 도구

모든 명령은 `tools/hot_products/work` 폴더에서 실행한다(스크립트가 상대경로로 읽고 쓴다).

| 순서 | 명령 | 하는 일 | 필요한 것 |
|---|---|---|---|
| 1 | `py -I ../snap.py` | 스냅샷 1장 → `snaps/YYYYMMDD_HHMM.json` (네이버 6분야·1688 14카테고리×인기/급상승·테무 베스트·알리·아마존 6분야) | 파이어폭스 Playwright, **테무 로그인 프로필 `~/.claude/temu_ff_profile`**(PC마다 한 번 로그인) |
| 2 | (분류) | 상품명 → cat·wow(0~3)·kw. 지금은 서브에이전트가 판정해 `cls2_*.json` 으로 저장 | Claude |
| 3 | `py -I ../enrich.py` | `kws.json` 키워드마다 월 검색수·4주 추세·유튜브 조회 → `enrich.json`(이어하기 됨) | `.env` 의 `NAVER_SEARCHAD_*`·`NAVER_CLIENT_*`, yt-dlp |
| 4 | `py -I ../build3.py` | 스냅샷 2장 비교(시간당 판매) + 분류 + 지표 → 점수 → `v3_data.json` | 스냅샷 파일명 2개가 코드에 박혀 있음 |
| 5 | `py -I ../build_html.py` | `v3_data.json` + `template.html` + `view.js` → `out/인기상품랭킹_시안.html` | |
| 검사 | `py -I ../check3.py` | 크롬으로 사이트·정렬 눌러 카드 수·첫 상품·이미지·JS 오류 확인 | 경로가 main 폴더 out 으로 박혀 있음 |

쿠팡은 서버 파트너스 API(사장님 키 cid 0)로만 된다 — `work/cp_dump.json` 이 그 결과(13카테고리×20 + 골드박스).

조사 보고서: `research/kr_report.md`(아이템스카우트·판다랭크·셀러라이프 해부) · `global_report.md`(테무·알리·1688·틱톡샵) · `amz_report.md`(아마존).
