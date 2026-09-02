# 미디어gzip — 미리보기가 검게 죽던 진짜 뿌리

## 2026-09-02 고객(이유준) 제보
- "분명 영상인데 사진처럼 멈춰서 확인이 불가" / "돌아가다 다음 클립에서 멈추고 또 돌아가다 멈추고"
- "전체 재생하는데 미리보기에 검정으로 아예 안 보일 때도 가끔"
- "어제는 안 그랬는데 지금은 매번"

## 브라우저로 직접 재현 (사장님 "너가 눈으로 해")

라이브 `scene_lab.html?job=353493f20d31`을 열어 전체 재생 → **미리보기 완전 검정, "컷 1/4"에서 정지.**
페이지의 `<video>` 8개가 전부 `readyState 0` / `networkState 2`.

갈라서 확인한 것:
| 확인 | 결과 |
|---|---|
| 서버 Range | ✅ 정상 — `0-1023`·`-1024`·끝부분 전부 206, 45~68ms |
| moov 위치 | ✅ 파일 앞(faststart 됨) |
| 코덱 | ✅ avc1(h264)+mp4a, 이 크롬이 `probably` 재생 가능 |
| 동시 연결 고갈 | ✅ 아님 — 다른 video를 다 끊어도 여전히 못 읽음 |
| **Range 없는 통짜 GET** | ❌ **200 + `content-encoding: gzip` + `transfer-encoding: chunked`** |

`<video>`는 Range 없는 GET으로 시작한다. 그 응답이 gzip이고 **Content-Length가 없으면**
메타데이터를 못 읽고 시크도 못 한다 → readyState 0 → 검은 화면·정지 그림.
fetch로 Range를 직접 주면 206이라 gzip이 안 붙어 **혼자 시험하면 멀쩡해 보인다** —
이 어긋남이 "됐다 안 됐다"의 정체다.

## 뿌리

`app.add_middleware(GZipMiddleware, minimum_size=1024)` (2026-07-30, 유튜브 랭킹 3.34MB 응답
때문에 넣은 것). **타입을 안 가리고 모든 응답을 압축한다** — mp4·mp3·이미지까지.

## 고친 것

`_NoCompressMedia` 미들웨어를 GZip **안쪽**에 둔다. 응답 content-type이 video/·audio/·
image/·octet-stream·zip·font면 `Content-Encoding: identity`를 심고, 바깥 GZip이 그걸 보고
비켜간다(Starlette 0.36.3 실측: `content_encoding_set`이면 압축 안 함).

★판단은 여기 한 곳뿐이다 — 미디어 라우트마다 헤더를 붙이면 새 라우트에서 또 빠뜨린다.
★JSON 압축은 그대로 살아 있다(랭킹이 느려진 원래 문제를 되돌리지 않는다).

## 검증
- 새 테스트 4건: 영상 비압축 / **Content-Length 유지** / 소리 비압축 / JSON은 여전히 압축
- 배포 후 라이브에서 같은 페이지를 다시 열어 눈으로 확인할 것 ⏭

## 곁가지로 확인된 것
`/api/mix/src/...`는 **HEAD가 404**다(`@app.get`만 있다). `/api/share/v/{sid}`는
`methods=["GET","HEAD"]`로 이미 고쳐져 있다(2026-08-30 버퍼 사고). 지금 증상의 직접
원인은 아니었지만 같은 함정이라 언젠가 문다 — 별도로 맞춰두는 게 좋다.
