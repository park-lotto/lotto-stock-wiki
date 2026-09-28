# Pinterest PC 릴레이

## 완료

- 브라우저 담기 로직이 `pinimg.com` 직접 MP4 주소를 감지해 `video_url`로 함께 전송한다.
- 서버에서 Pinterest JSON-LD가 없거나 HTTP 차단이 나면 기존 `yt_relay` 큐로 PC에 위임한다.
- PC 릴레이 에이전트가 Pinterest는 `pin_video_info` + 직접 MP4 다운로드로 처리하고, 재큐잉은 금지한다.
- YouTube 기존 `_download_ytdlp` 경로는 유지했다.
- 관련 테스트 38개, JavaScript 문법 검사, Python 컴파일 통과.

## 운영 반영 후 확인

- 실행 중인 PC `youtube_relay_agent`는 새 코드를 읽도록 한 번 재시작해야 한다.
- 실제 영상 핀 하나를 담아 서버 큐가 `done`이 되는지 확인한다.
