---
name: reference_douyin_download_headless
description: 도우인 영상은 yt-dlp로 절대 못 받는다 — 헤드리스 크롬 SSR에서 서명 CDN 주소를 뽑는 것이 유일한 길. hevc 정규화·동시 2개 상한 필수
metadata: 
  node_type: memory
  type: reference
  originSessionId: 053a5ce9-6039-4b81-9dd4-3eb72b569b08
  modified: 2026-08-16T13:38:51.616Z
---

**도우인(douyin.com) 영상 수신은 2026-08-16에 처음 성사됐다.** 그전엔 담기·검색·렌즈만
됐고 영상 분석은 **한 번도 성공한 적이 없다**(`script_extracts` 도우인 0건으로 확인).
사장님은 "원래 잘 됐다"고 기억하시지만 그건 메타·썸네일까지였다 — 담아서 제작까지 간 적이 없었다.

## 이미 해봤고 안 되는 것 (다시 하지 마라, 전부 실측)

```
서버 yt-dlp                      ❌ ERROR: [Douyin] Fresh cookies ... are needed
사장님 PC(가정용 IP) yt-dlp       ❌ 동일  → ★IP 차단 문제가 아니다
헤드리스로 쿠키 20~33개 얻어 전달  ❌ 동일
yt-dlp 최신(PyPI)·git master     ❌ 동일
헤드리스에서 재생시켜 네트워크 가로채기 ❌ 미디어 요청 0건(재생 자체가 안 됨)
plain curl로 SSR                 ❌ douyin.com은 2.4KB 챌린지 셸만 옴
/video/{id} 로 playwright 직행    ❌ 로드 중 재네비게이션돼 캡처 불가
```

## 되는 길

**headless chromium으로 `douyin.com/discover?modal_id={id}`를 열면** 챌린지 통과 후
SSR HTML에 **전 화질 playAddr(서명된 zjcdn URL)가 URL인코딩으로 내장**돼 있다.
그걸 뽑아 `Referer: https://www.douyin.com/` + UA로 GET하면 서버(AWS IP)에서도 200.
→ `shopping_shorts/douyin_fetch.py`, `media_download.download_any`의 도우인 분기.

## 반드시 함께 지킬 것

- **hevc 정규화**: 도우인 최고화질은 `hevc(H.265) 2160x2880`이다. 그대로 두면 크롬 재생이
  고객 PC마다 갈리고(3단계가 검은 화면) 편집이 무겁다 → `_normalize()`가 h264·높이 1920으로
  맞춘다. 결과물이 1080x1920이라 화질 손해 0.
- **제한 시간**: 길이에 비례한다. 20초 영상=35초, **45초 영상=108초**. 180초로 잡으면
  긴 영상만 조용히 죽는다 → 600초.
- **동시 2개 상한**: 도우인만 영상당 크롬+ffmpeg를 돌린다. 서버 4코어인데 자동적재는
  고객마다 3개씩 던진다 → 고객 5명이면 크롬 15개, 다 같이 기어가다 전부 시간 초과.
  `_DOUYIN_SLOTS`(서버 전역 2개, `DOUYIN_MAX_CONCURRENT`).
- **`DouyinBusy`는 실패가 아니다**: `RuntimeError` 하위라 `except Exception: pass`에
  삼켜지기 쉽다 — 실제로 그래서 대기 기능 전체가 죽어 있었다(도달 불가 코드).
  반드시 `except DouyinBusy: raise`로 통과시키고, 상류는 래치를 되돌려야 한다.

## 함정

- 도우인 페이지는 무거워 **Claude in Chrome이 3회 연속 렌더러 프리즈**했다. 브라우저 검증을
  기대하지 말고 서버에서 `python3 -m shopping_shorts.douyin_fetch <url> /tmp/out`으로 확인하라.
- 서버 DB는 `shopping_shorts/data/reference.db`다(`config.DB_PATH`). `app.db`에도 같은
  테이블이 있지만 0건 — 여기서 헛짚기 쉽다. 라이브 API는 유료게이트라 SSH curl은 401.

관련: [[reference_youtube_shorts_datacenter_block]] · [[reference_extract_cache_key_lens_prefix]] ·
[[feedback_extension_needs_reinstall]]
