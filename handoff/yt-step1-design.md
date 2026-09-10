# yt-step1-design

## 결정

- `/yt` 1단계를 `기본 설정`이 아니라 `주제 찾기·레퍼런스 영상 분석`으로 구체화했다.
- Astra는 원본 수집기가 아니라 여러 영상의 분석 결과를 비교해 최종 적용 설계를 내리는 편집장 역할이다.
- 분석 산출물은 요약이 아니라 `채택·변형·버림`, 실제 사용 위치, 조사 과제, 필요 파일을 포함하는 주제 확정 카드다.
- 사용자가 주제를 확정해야만 2단계 심층조사로 넘어간다.

## 구현

- `scripts/yt_agents/clip_teardown.py`
  - YouTube URL/영상 ID 정규화
  - yt-dlp 메타데이터 수집
  - Gemini 영상 직접 분석(클릭 장치, 첫 30초 타임코드, 이야기 구조, 화면 문법, 장점, 위험)
  - Astra 종합 판단(주제, 약속, 차별점, 채택·변형·버림, 제목, 훅, 조사 과제, 필요 파일)
- `dashboard/server.py`
  - 프로젝트에 `topic_discovery`, `video_analyses` 영속화
  - 영상별 분석 캐시
  - SSE `POST /yt/projects/{project_id}/topic/analyze`
- `dashboard/yt.html`
  - `주제로 찾기`와 `URL 직접 분석` 모드
  - 성과 영상 후보 선택, 실시간 진행 표시, 영상 분석 카드, Astra 주제 확정 카드
  - 확정 결과와 조사 과제를 2단계로 전달

## 검증

- `py -m pytest tests/test_yt_dashboard.py tests/test_yt_clip_teardown.py -q` → 9 passed
- `py -m py_compile dashboard/server.py scripts/yt_agents/clip_teardown.py` → 통과
- `git diff --check` → 통과
- Chrome에서 `http://127.0.0.1:8096/yt` 실사용 검증
  - 프로젝트 생성
  - 실제 YouTube 영상 `tclPelYumZ8` 분석
  - 영상 카드와 Astra 주제 확정 카드 생성
  - 주제 확정 후 조사 과제 3개가 2단계에 전달되는 것까지 확인

## 다음 작업

- 2단계 `AI 심층 기획서 만들기`를 현재 단일 호출에서 근거 수집→교차검증→기획서 생성 파이프라인으로 강화한다.
- 무주제 사용자를 위한 당일 급상승 자동 스캔 모드를 1단계에 추가한다.
- 분석 점수의 합산 근거를 UI에서 항목별로 보여준다.
