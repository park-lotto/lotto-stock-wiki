# 메이커스랩 유니버스 진입 검토본

> **For agentic workers:** superpowers:executing-plans로 순서대로 실행한다.

**Goal:** 외부 캠퍼스 → 숏템메이커 → 직급별 자리와 인접 3구역 → 외부 복귀를 실제 브라우저에서 검토한다.

**Architecture:** 기존 atlas/studio를 보존하고 `/universe/`를 추가한다. 공용 studio-art의 가구·로봇을 재사용한다. 예시 워커는 atlas-data에서 가져오고 실운영 연결은 하지 않는다.

**Tech Stack:** 기존 Three.js 0.180.0 / esbuild / Chromium + Puppeteer.

## 승인 범위

메이커스랩 단일 회사, 숏템메이커·스탁브레인 프로그램 건물. 숏템메이커만 입장 가능하며 다른 건물은 미구현 안내. 1층 기획 8석, 개발 4석, 독립 검수 4석. 팀장을 구역 뒤쪽 별도 자리로 분리한다. 복도와 추가 구역 부지를 표시하고 기존 방 좌표를 고정한다. 2층·지하는 설계 예정이며 작동하는 척하지 않는다.

## 실행 체크리스트

- [ ] `company_ops/tests/universe.cjs`: 실제 페이지 제목, 입장, 3구역, 팀장 선택, 복귀, 주야간, 모바일, 비쓰기 검증을 먼저 작성하고 `node company_ops/tests/universe.cjs`에서 새 페이지 부재 실패를 확인한다.
- [ ] `scene/studio-art.js`: 기존 기본값 유지하며 `{workers,title,leaderSeat}` 옵션과 공용 조형 함수 export. 새 방의 worker point는 world 좌표로 변환한다.
- [ ] `scene/universe-art.js`: 원형 캠퍼스, 2개 프로그램 건물, 입장 hit target; 연결 복도와 3방을 만든다.
- [ ] `scene/universe.js`: 외부/입구/내부의 명시적 상태, 카메라 이동, 워커 선택, 검색, 주야간, 회전/팬/줌, 드래그 오선택 방지.
- [ ] `static/universe/index.html`, `universe.css`: 지도 중심 화면, 경로, 구역 목록, 상세, 미연결 표시. 좁은 화면은 패널 크기 제한.
- [ ] scene에서 `npm run build:universe`, 트랙에서 `node company_ops/tests/universe.cjs`, `node company_ops/tests/studio.cjs`, `node --test company_ops/tests/atlas-data.test.mjs` 실행. `.artifacts/universe-*.png` 직접 확인.
- [ ] 읽기 전용 리뷰 후 수정·재검증. handoff/회사운영플랫폼.md 및 루트 wiki/log.d/회사운영플랫폼.md 기록. 트랙만 커밋/푸시, main 미병합.

## 검증 기준

실행 결과: 위 구현 및 검증 수행. 신규 페이지 부재 실패 확인 후 구현했고 Chromium 건물·워커 레이캐스트/16개 고유 워커/팀장/3방/교차 방 목록 갱신/회전/모바일/복귀 검사 통과. studio 회귀 및 atlas-data 2테스트 통과. 캡처 직접 확인. 일반 코드 리뷰의 roster 누락 수정. 트랙 보존, 사용자 시각 검토 대기.

`assert.equal(diag.view,'outside')` → 건물 클릭 시 `entrance` → 입장 시 `inside`. 기획/개발/검수 버튼이 서로 다른 고정 공간으로 이동. W-001 상세의 팀장/보고 대상 표시. 내부 전체에 16개 고유 예시 워커. `outside` 복귀시 내부 상세·검색 선택 해제. 실제 API 변경 요청 0건. 브라우저 오류 0건. 기존 studio의 8석 기본 렌더·조작 회귀 없음.
