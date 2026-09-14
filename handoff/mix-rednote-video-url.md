# mix-rednote-video-url

- 2026-09-14 김성현(cid 352) job `843305244fd6`: 입력 7개 중 샤오홍슈 6개가 제작 다운로드에서 yt-dlp `No video formats found`로 스킵되어 유튜브 1개만 3단계에 전달됐다.
- 담기 예열은 `mix_basket.video_url`의 `rednotecdn.com` 직접 MP4로 성공했지만, `run_mix_job`은 `mix_jobs.urls_json`의 페이지 URL만 다시 사용한 것이 원인이다.
- `mix_pipeline._basket_download_urls`에서 고객별 장바구니의 같은 원본 URL을 찾아 검증된 직접 영상 URL로 치환한 뒤 `_prepare_sources`에 전달한다.
- 다른 고객의 주소와 직접 영상이 아닌 값은 사용하지 않는 회귀 테스트를 추가했다.

