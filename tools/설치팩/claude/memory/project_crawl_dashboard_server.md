---
name: project_crawl_dashboard_server
description: 크롤봇 서버구조(Lightsail)+소스관리 대시보드 서버자동연동+유튜브 Gemini 타임스탬프 자막
metadata: 
  node_type: memory
  type: project
  originSessionId: ed142f9e-b952-4137-96b7-ec4226e9c36a
---

크롤링 실체와 대시보드 연동 구조 (2026-06-28 구축).

**서버(실제 크롤)**: Lightsail `ubuntu@3.39.179.148:/home/ubuntu/kmong/crawling_bot/`. `main.py`(APScheduler)가 config.yaml cron대로 크롤. 스케줄: 뉴스 매시 / 텔레 30분(증분=output/seen_urls.json 영구중복체크) / 유튜브·블로그 9·12·15·18·21시. 로컬 `client.py`(C:\Users\TheRose\crawling_bot_client\)가 5분마다 새 파일만 다운로드→`crawling_bot_data`. SSH키: `crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem`.

**소스관리 대시보드**: `dashboard/server.py`(8090)/`sources.html`, 바탕화면 `크롤링소스관리.bat`. 추가/삭제(링크or이름)→로컬 레지스트리(`pipeline/atoms/*_registry.json`, 텔레=telegram_channels.json) **+ 서버 config.yaml 자동연동**(SSH로 서버 `add_source.py`/`del_source.py` 호출). 버튼: 받아오기(전체 다운로드)·소스동기화(폴더스캔 자동등록)·전체크롤/채널별크롤(`crawl_run.py` 백그라운드). 서버 config 섹션: 텔레/유튜브=channels, 블로그=sites, 뉴스=keywords.

**유튜브 자막 교훈**: yt-dlp 자막 다운로드는 **서버(데이터센터 IP)에서 YouTube 봇차단**("Sign in to confirm")으로 불가. → **Gemini가 영상 URL 직접 시청**(`processors/gemini_summarizer.py`, gemini-2.5-flash, file_uri)해서 `- [mm:ss] 화자: 발언원문` 타임스탬프 발언 추출. 노이즈 없는 핵심 인용이라 원자·발언카드에 더 적합.

미완: B(자막→원자, atomizer 보강) · C(발언카드+/영상기획) = 집PC 작업. 상세 [[project_youtube_insight_pipeline]] 없으면 NEXT_SESSION.md + spec 2026-06-28-유튜브-자막-원자-파이프라인.

## 서버반영 실패 버그 해결 (2026-07-02)
증상: /sources에서 유튜브·뉴스키워드 추가 시 "저장됨✓·⚠️서버반영 실패" 매번.
원인: `server_register/unregister/crawl`이 **Windows 키경로**(`C:\Users\...pem`)로 SSH하는데 대시보드는 **리눅스 서버에서** 실행됨→키경로 없어 무조건 실패. 게다가 크롤봇이 **같은 서버**(/home/ubuntu/kmong/crawling_bot/)라 SSH 자체가 불필요.
조치: `_crawlbot_cmd(local_script,remote)` 추가 — 로컬스크립트(add/del_source.py·crawl_run.py) 존재시 `python3` 직접실행, 없으면 SSH폴백. add_source.py=stdin JSON→config.yaml upsert(멱등). 기존 미반영분은 레지스트리(pipeline/atoms/*_registry.json)→add_source.py 루프로 일괄 reconcile(유튜브6·블로그4·뉴스키워드21). ⚠️`scan_actual_sources` CRAWL_DIR도 Windows경로라 서버선 빈값(표시용이라 부차적).
