# Comment Card Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 장면꾸미기에서 다크 소셜과 프리미엄 팝 댓글 카드를 편집·저장·복원하고 최종 세로 영상에 애니메이션으로 합성한다.

**Architecture:** Pillow 기반의 `comment_card.py`가 두 스타일의 투명 PNG를 단일 정본으로 렌더한다. 브라우저 미리보기와 최종 렌더가 이 이미지를 공유하며, FFmpeg 모션 레이어가 등장 타이밍을 담당한다.

**Tech Stack:** FastAPI, Pillow, vanilla HTML/CSS/JavaScript, FFmpeg, pytest

---

### Task 1: 댓글 카드 정규화와 PNG 렌더러

**Files:**
- Create: `shopping_shorts/comment_card.py`
- Create: `shopping_shorts/tests/test_comment_card.py`

- [ ] 정규화, 스타일 목록, 투명 PNG 출력, 프로필 폴백을 요구하는 테스트를 먼저 작성한다.
- [ ] `pytest -q shopping_shorts/tests/test_comment_card.py`를 실행해 모듈 부재로 실패하는지 확인한다.
- [ ] `normalize`, `cache_key`, `render_to`, `styles` API를 구현하고 다크·프리미엄 두 PNG를 그린다.
- [ ] 단위 테스트를 다시 실행해 통과를 확인한다.

### Task 2: 미리보기와 프로필 업로드 API

**Files:**
- Modify: `shopping_shorts/app.py`
- Create: `shopping_shorts/tests/test_comment_card_api.py`

- [ ] 스타일 목록, PNG 미리보기, 작업별 프로필 업로드의 정상·잘못된 입력 테스트를 먼저 작성한다.
- [ ] 라우트 부재 실패를 확인한다.
- [ ] `/api/produce/comment-card/styles`, `/api/produce/comment-card.png`, `/api/produce/mix/comment-avatar`를 구현한다.
- [ ] API 테스트를 통과시킨다.

### Task 3: 저장된 스펙을 최종 렌더 레이어로 해석

**Files:**
- Modify: `shopping_shorts/mix_pipeline.py`
- Modify: `shopping_shorts/video_assemble.py`
- Create: `shopping_shorts/tests/test_comment_card_render_pipeline.py`

- [ ] `deco.comment_card`가 PNG 경로와 범위가 정규화된 모션 레이어로 변환되는 테스트를 먼저 작성한다.
- [ ] 현재는 레이어가 생성되지 않아 실패함을 확인한다.
- [ ] `resolve_deco_media()`에서 동적 PNG를 생성하고 `_burn_captions()`에서 기존 motion layer 목록에 한 번만 합친다.
- [ ] `_motion_layer_filters()`에 `slide_up`과 페이드 입·출력을 추가하고 필터 문자열을 테스트한다.
- [ ] 렌더 파이프라인 테스트를 통과시킨다.

### Task 4: 장면꾸미기 댓글 카드 UI

**Files:**
- Modify: `shopping_shorts/static/produce.html`
- Create: `shopping_shorts/tests/test_comment_card_ui.py`
- Modify: `shopping_shorts/tests/test_deco_handlers_save.py`

- [ ] 효과 탭의 스타일 2종, 편집 필드, 범위 제어, 삭제·저장 호출을 검사하는 UI 테스트를 먼저 작성한다.
- [ ] UI 요소와 함수가 없어 실패하는지 확인한다.
- [ ] 카드 선택, 편집, 업로드, 드래그, 미리보기, 삭제, 저장, 복원 코드를 구현한다.
- [ ] UI 및 저장 회귀 테스트를 통과시킨다.

### Task 5: 실제 화면과 최종 영상 검증

**Files:**
- Create: `handoff/댓글효과.md`
- Create: `wiki/log.d/댓글효과.md`

- [ ] 관련 테스트 전체와 모듈 import 검사를 실행한다.
- [ ] 로컬 서버에서 스타일 2종을 직접 누르고 한글 댓글·드래그·저장·복원을 확인한다.
- [ ] 1080×1920 샘플 영상을 실제 렌더하고 등장 전·중·후 프레임을 이미지로 추출해 육안 검수한다.
- [ ] ffprobe로 출력 규격과 오디오 존재를 확인한다.
- [ ] 핸드오프와 로그에 결과·미확인 사항을 남긴다.
