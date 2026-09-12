# Company HQ Preview Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. 디자인은 주 에이전트 아스트라 전담, 페이블은 기술 조사만 담당한다.

**Goal:** 사옥→부서→로봇→저장 업무→사옥의 실제 조작 가능한 첫 3D 검토본.
**Architecture:** 독립 Three.js 번들 장면과 DOM 실무 패널. 기존 읽기 API를 그대로 소비한다.
**Tech Stack:** Three.js 0.180.0, esbuild 0.25.10, 기존 FastAPI/SQLite, Puppeteer.

## 실행 결과 2026-09-13
T1~T5 구현 및 실제 브라우저 통과. T6 기록 완료, 사용자 디자인 검토 대기. 대표 진입 URL `/hq/` (기존 StaticFiles 루트의 html=True 제공 경로). 자동 브라우저 열기는 정책 거절로 링크 전달. 페이블 새 Agent 타입 미지원, 로컬 Claude 세션에 기술 검토 요청 전달 후 응답 대기. 세부 증거와 미구현 경계는 최신 트랙 핸드오프 참조.

- [ ] T1 company_ops/scene/package.json 의존성 설치와 잠금. `npm install --ignore-scripts` 후 `npm run build`로 번들 생성.
- [ ] T2 scene/architecture.js에 공유 지오메트리·재질, 석재 기단·다섯 부서·개방형 사옥·유리·조명·화분·책상·로봇 구현. 부서 좌표와 pick 대상은 장면 메타데이터로 반환.
- [ ] T3 scene/main.js에서 renderer/camera/OrbitControls, 부서 및 워커 선택, 카메라 전환·오선택 방지·resize·reduced-motion 구현. static/hq/index.html 및 hq.css로 부서 탐색·워커 목록·연결 상태·읽기 전용 업무 패널 제공.
- [ ] T4 GET /api/state와 프로젝트 사건 읽기를 연결. DOM textContent 사용, 빈 상태와 조회 실패 명시. 등록된 역할과 실제 모델 세션 구분.
- [ ] T5 tests/hq.cjs로 실제 전용 서버에서 마우스·터치·모바일·API 상태·브라우저 오류 검사, .artifacts/hq-*.png 촬영 및 주 에이전트 직접 검토. 미흡한 외관은 한 번 더 보정.
- [ ] T6 README 및 트랙 handoff 갱신, 루트 wiki/log.d/회사운영플랫폼.md에 이번 기록 추가. 작업 파일만 확인하고 트랙에 보존. 서버 화면 열고 사용자 중간 피드백 대기. finish/외부 배포는 하지 않는다.
