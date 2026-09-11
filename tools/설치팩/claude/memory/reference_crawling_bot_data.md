---
name: reference-crawling-bot-data
description: 크롤링봇이 자동 저장하는 폴더 경로 — ingest 시 항상 확인
metadata: 
  node_type: memory
  type: reference
  originSessionId: 47e5854a-1d93-4781-b320-45a710a68289
---

## 크롤링봇 수신 폴더

**경로:** `C:\Users\TheRose\crawling_bot_data\`

텔레그램봇·뉴스봇·리포트봇 등 자동 크롤링 결과가 저장되는 위치. 프로젝트 폴더(`로또의 주식\raw\`) 외부에 있음.

**How to apply:** ingest 요청 시 `raw/` 폴더와 함께 이 폴더도 항상 확인. 새 파일이 있으면 ingest 대상에 포함.
