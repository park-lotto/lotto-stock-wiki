# Higgsfield API 파일럿

- 2026-09-29: 지아지조 공식 메인 사진의 실제 자매 모델로 키즈라이드 캐리어 Product Hit 4초 영상을 Open Higgsfield API에서 1건 생성했다($0.39, 당시 cashback 적용). 9:16 후처리본을 바탕화면 `kids-ride-sisters-product-hit-higgsfield-4s.mp4`에 저장하고 접촉시트로 육안 확인했다.
- 2026-09-29: 제출 성공 응답의 상태 URL 호스트가 기존 허용 검사와 달라 요청 ID 저장 전 예외가 발생했다. 대시보드에서 기존 작업을 복구했으며, 파서와 `aspect_ratio` payload 보강이 후속 과제다.

- 2026-09-29: 작업 `4bd606509402`용 Seedance 2.0 4초 훅 영상을 공식 Higgsfield API로 1건 생성하고 바탕화면에 저장했다. 실측 결과는 handoff 참고.
- MCP는 Basic 플랜 제한으로 생성 불가였고, Vertex/Veo는 기존 `ai_scene.py` 경로와 로컬 설정만 확인해 추가 비용을 막았다.
- 2026-09-29: 같은 제품 시작 이미지와 동일 프롬프트로 Vertex Veo 4초 A/B 영상 1건을 생성했다. 720×1280, 24fps이며 바탕화면에 저장했다.
- 2026-09-29: MCP Viral Hub 후킹 예시 87개를 검색·분류하고 카드 클릭 시 공식 영상을 재생하는 관리자 라이브러리 화면을 구현해 브라우저 실사까지 마쳤다.
- 2026-09-29: 사용자 제공 영상과 MCP Marketing Studio UGC를 대조해 찾던 연출이 `Product Hit`임을 확인했다. 공식 UGC 첫 화면 12개와 Product Hit 미리보기를 페이지 상단에 추가하고 Viral Hub 87개와 분리했다.
