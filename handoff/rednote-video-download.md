# rednote-video-download

## 2026-09-14

- 고객 352의 샤오홍슈 즐겨찾기 11건이 `분석 중`에 머문 원인을 라이브 DB와 실제 RedNote 화면에서 확인했다. 저장된 `video_url`은 전부 비어 있었고, RedNote는 `<video src>`를 `blob:`으로 감춘 채 실제 MP4를 새 CDN `sns-v*.rednotecdn.com`에서 재생한다.
- 담기 스크립트가 렌더된 DOM에서 현재 RedNote MP4를 찾아 보내고, 서버가 새 CDN을 허용해 직접 다운로드하도록 수정했다.
- `video_url`이 바구니에는 저장되지만 prewarm 큐에서 빠지던 배선도 연결했다. 다시 분석할 때도 저장된 직접 URL을 넘긴다.
- 배포 뒤 기존 실패 영상은 RedNote 원본을 열고 우측 하단 `📥 담기`를 한 번 더 누르면 빈 `video_url`이 채워지고 재분석된다.

검증: 관련 pytest 34개 통과, 실제 실패 영상 화면에서 새 정규식으로 MP4 검출, AWS 서버에서 해당 MP4 Range 요청 `206 video/mp4` 확인.

