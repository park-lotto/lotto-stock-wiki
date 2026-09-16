---
name: project-naver-board-sentiment
description: 네이버 종토방 크롤링→개미 여론·상승이유 댓글분석 기능. 워크스페이스 🗣️종토방 여론 버튼
metadata: 
  node_type: memory
  type: project
  originSessionId: afbd0124-37e9-45d2-bcda-59a773462789
---

인사이트 허브 워크스페이스에 **네이버 종목토론방 여론분석** 추가(2026-07-01). NotebookLM이 못 찾는 실시간 개미 여론·상승이유를 보완.

- 버튼: 워크스페이스 좌측 '자료 보강'에 **🗣️ 종토방 여론** (질문칸에 종목명 입력 후 클릭, 없으면 ws.label 사용)
- 엔드포인트: `POST /api/insights/naver_board {stock}` → `codemap.code_for(종목명)`으로 코드 조회 → `finance.naver.com/item/board.naver?code=&page=1~2` 크롤(**UTF-8 디코드**, `<td class="title"><a title="...">` 정규식) → Gemini(gemini-3-flash-preview, 그라운딩 없음, `_gemini_interactive_keys`)로 분위기/상승·하락이유/키워드/대표목소리 분석. 과열·작전 신호 표시.
- 검증: 대우건설(047040) 39글 → "부정적 혼조·소외감(불장인데 대우만 못 감)" 정확.
업그레이드(2026-07-01): 전용 좌측섹션(종목명 input+기간select), bs4 파싱으로 **제목·날짜·조회수·추천** 전량 추출→조회수순 가중 분석("많이 읽힌 글 위주"). 멀티페이지+기간(dN)필터. Gemini 503 재시도(같은키 2회 백오프).

✅ 본문 크롤 성공(Playwright): 네이버가 본문을 read페이지 iframe→`m.stock.naver.com`(Next.js SPA)→`apis.naver.com/mobilestock` 인증API로 가려 **단순 HTTP는 불가**(파트너키 필요, error_code 052). BUT **claude-in-chrome MCP만 naver 차단**이고 **Playwright 파이썬 라이브러리(직접)는 제약없음** → 헤드리스로 SPA 렌더링해 본문 추출됨.
- `_naver_post_bodies`(async): URL `m.stock.naver.com/pc/domestic/stock/{code}/discussion/{nid}`, 셀렉터 `[class*="content"]` 중 최단 유효텍스트. 조회수 상위 6글 **병렬**(asyncio.gather)+이미지/CSS/폰트 route.abort → 27초. **엔드포인트 이벤트루프서 직접 await**(run_in_threadpool+asyncio.run은 hang됨). Gemini 프롬프트에 본문 포함.
- 주의: 네이버 finance는 UTF-8. code_for 실패 시 토큰별 재시도. 목록행: td[0]날짜 td.title제목 td[3]조회 td[4]추천. [[project_insights_notebooklm_bridge]]

📰 종목뉴스(상승원인) 추가·완성(2026-07-01): 종토방 옆에 **📰 종목 뉴스** 버튼. `POST /api/insights/naver_news {stock}` → `m.stock.naver.com/domestic/stock/{code}/news` 크롤→광고성(`_NEWS_AD_KW`: 추천주·급등주·리딩·무료 등) 제외→Gemini(gemini-3-flash-preview)로 ①주가 상승/하락 원인 ②핵심뉴스3~5 ③리스크 정리. 검증 대우건설 23초·25건 고품질(수주2.9조·SMR·건설채리스크).
⚙️ **subprocess 격리(핵심 교훈)**: Playwright를 uvicorn 이벤트루프서 반복 launch하면 불안정(90초 hang→서버死→이후 즉시 FAIL). → `scripts/naver_crawl.py` 별도 프로세스로 분리, 서버는 `subprocess.run([sys.executable, script, json페이로드], timeout=)`로 호출(`_naver_crawl`→`_naver_news`/`_naver_post_bodies`). standalone 1초 안정. cp949 UnicodeEncodeError(⋯)는 `sys.stdout.reconfigure(encoding="utf-8")`로 해결. **"2초 FAIL"의 진범은 죽은 서버**(재시작이 해법).
🔤 **뉴스 구조화·Gemini폴백·자동완성(2026-07-01)**: 뉴스=구조화객체{title,summary,press,date,url}(NewsList_title/text/cite/time 셀렉터, n.news.naver.com 원문). `_gemini_text()` 공용헬퍼=모델폴백(gemini-3-flash-preview 503과부하→gemini-2.5-flash 자동전환)+키로테이션(503은 모델전체과부하라 첫503에 다음모델로 점프). 종목명 자동완성 `/api/insights/stock_suggest`(krx_codes.json 2605종). **KRX가 회사마다 등록명 제각각**(SK하이닉스=영문 / 엘에스일렉트릭=한글음역)→ `_BRAND_ALIASES`(ls↔엘에스…) 양방향 매칭 + `_DISPLAY_ALIAS`(검증10종 브랜드표시). 선택 시 **코드기반 조회**(`_resolve_stock`, body에 code동봉)라 표시명이 브랜드여도 code_for 안 깨짐.
