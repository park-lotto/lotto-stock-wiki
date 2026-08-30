# Buffer연동

## 2026-08-30 (Fable) — "Video could not be read from its URL" 진짜 원인 확정·수정
- **원인**: `api_buffer_schedule`(app.py, async 핸들러)이 blocking urllib 기반
  `buffer_api.schedule_video`를 이벤트루프에서 직접 호출 → createPost가 도는 10~20초 동안
  **서버 전체가 멈춰** Buffer 검증기의 HEAD/GET(`/api/share/v/...`)에 응답 못 함 → 거절.
- **증거(실측)**:
  - 같은 파일·같은 캡션을 앱 밖(서버 스크립트)에서 호출 → 전부 성공 (파일·캡션·규격 무관 확정)
  - 실패 때 apache 로그 HEAD 도착 16:30:33 / uvicorn 완료 16:30:43 = **HEAD가 10초 멈춤**,
    createPost 응답과 동시에 풀림. 성공 때는 HEAD+GET(ffprobe)이 1초 안에 완료.
  - faststart·Range/206·.mp4 확장자·비트레이트·캡션 가설은 전부 기각(앞선 3오진 포함).
- **수정**: `run_in_threadpool`로 감쌈(app.py ~6020) + import 추가. finish로 main 병합·배포.
- **시험 예약은 전부 deletePost로 삭제**(4건: A/B 2 + 캡션재현 1 + 라이브검증 1).
- ⏭ 없음 (라이브 검증까지 완료 시)
