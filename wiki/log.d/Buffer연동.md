- 2026-08-30: Buffer 거절 뿌리 = async 핸들러의 blocking 호출로 이벤트루프 정지(검증 HEAD가 10초 블록). run_in_threadpool로 수정·배포. 시험 예약 전부 삭제.

- 2026-09-02 버퍼 3플랫폼 점검. 유튜브 실패 뿌리=YoutubePostMetadataInput에 없는 `type` 필드 전송(로그 6회 동일). type 제거·title+categoryId+privacy로 교체. 틱톡은 metadata 입력형 자체가 없어 현행 유지가 정답, 인스타는 개인 프로필 계정 거절을 한국어 안내로 변환.
