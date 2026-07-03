# 골-루프 카드 — NotebookLM 인포그래픽 추가 · 그라데이션 히어로 제거

- 작성일: 2026-07-03
- 상위 스펙: `docs/superpowers/specs/2026-07-03-goal-loop-notebooklm-stage0-design.md` (Stage0 NotebookLM 텍스트 교체, 완성·병합됨)
- 상태: 설계 확정 (구현계획 대기)

---

## 1. 배경 · 문제

Stage0을 NotebookLM 텍스트 기반으로 교체한 뒤 실전 스모크 테스트에서 카드 이미지를 확인한 사장님이
지적: 카드 상단의 골드→검정 그라데이션 이미지가 여전히 "클로드식(전형적 AI생성)" 느낌이다.
원인 확인 — 이 히어로 이미지는 `gemini_image.py`(모델 `gemini-2.5-flash-image`, 일명 나노바나나)가
생성하는데, **등록된 Gemini 키 8개 전부에서 동일하게 429(쿼터 0)** 로 실패해 항상 그라데이션 폴백만
나오고 있었다. 실측 결과 이는 "오늘 소진"이 아니라 **무료 티어 자체가 이 이미지 모델에 쿼터를 0으로
막아놓은 구조적 제한**이라 키를 아무리 늘려도 해결되지 않음을 확인함(8키 전량 재현).

사용자 결정: 이 히어로 이미지 슬롯을 없애고, 대신 **NotebookLM 자체 스튜디오 기능(인포그래픽)**으로
카드 이미지를 대체한다. NotebookLM은 별도 접근 경로라 위 Gemini 이미지 쿼터 제약과 무관하며,
이미 Stage0에서 `notebook_query`/`create_report`가 정상 작동함을 확인함.

---

## 2. 확정된 핵심 결정

| 항목 | 결정 |
|------|------|
| 텍스트 카드 히어로 슬롯 | **제거**(텍스트만, 헤드라인부터 시작). Gemini 이미지 호출 자체를 안 함 |
| 인포그래픽 관계 | **텍스트 카드 + 인포그래픽 둘 다 발송**(병행, 대체 아님) — 별도 사진 메시지로 추가 전송 |
| 인포그래픽 실패 시 | **이상징후로 처리**(에스컬레이션) — 텍스트카드도 발행 보류. 즉 인포그래픽 생성 성공이
  "정상 발행"의 필수 조건이 됨(기존 C1/I1/I2 안전장치 패턴 재사용, 신규 코드 최소화) |
| 생성 엔진 | `nlm_bridge.py`에 동기식 `create_infographic()` 신규 추가. 기존 대시보드 인터랙티브
  UI 엔드포인트(`/api/insights/notebook_studio`, 비동기 폴링)는 **무수정**, 완전 별개 경로 |
| 디자인 톤 | 기존 `_BRAND_DESIGN`(검정+라임그린 HUD 금융 대시보드) 상수를 그대로 재사용해 일관성 유지 |

---

## 3. 아키텍처

```
[변경 A] scripts/card_render.py
  render_briefing_card(data, hero=None)에서 히어로 <img> 슬롯 제거(또는 hero 인자 자체 미사용).
  텍스트(헤드라인·강세·리스크·시나리오 등) 섹션은 무수정 — 헤드라인부터 바로 시작.

[변경 B] scripts/nlm_bridge.py — 신규 함수
  _BRAND_DESIGN 상수 이전(dashboard/server.py와 값 동일, 공유 소스로)
  create_infographic(nb_id: str, out_dir: str = None, focus: str = "") -> dict
     -> {"ok": bool, "path": str, "error": str}
     내부: nlm CLI "infographic create --style professional --focus {BRAND_DESIGN+focus}
           --language ko --confirm" → "studio status" 최대 150초 폴링(5초×30회, create_report와
           동일 패턴) → 완료되면 "download infographic" → out_dir/infographic_{nb_id}.png 저장

[변경 C] scripts/goal_loop/notebook_stage0.py — 신규 함수
  generate_infographic(notebook_id: str, date: str) -> str|None
     nlm_bridge.create_infographic 호출 → 성공 시 저장경로, 실패 시 None(예외 흡수, 상위가 판단)

[변경 D] scripts/goal_loop/morning_brief.py — run_morning_brief 흐름 수정
  _render_card(data, date)에서 gemini_image.generate_hero 호출 제거(히어로 없이 렌더)
  품질루프 통과 + 이상징후 없음 확인된 "정상 발행" 직전 단계에서:
    infographic_path = notebook_stage0.generate_infographic(links로부터 얻은 notebook_id, date)
    infographic_path 없음 → flags에 "인포그래픽 생성 실패" 추가 → 기존 게이트로 에스컬레이션
    infographic_path 있음 → 텍스트카드 PNG 전송 → 인포그래픽 PNG 추가 전송(caption 없이 또는 짧게)
  ⚠️ notebook_id를 run_morning_brief 스코프까지 전달해야 함(현재 links dict는 url만 가짐) —
     _ensure_scenario가 반환하는 links dict에 "notebook_id" 필드 추가.
```

**재사용(무수정)**: `quality.critique/revise`, `verify.detect_anomalies`, `pending.*`,
`viz_card.send_telegram_photo/message`, 08:00 데몬 게이트, `nlm_bridge.create_notebook/
add_source_file/notebook_query/create_report`, `notebook_stage0.build_notebook/
query_card_content/generate_deep_report`.

---

## 4. 에러 처리 (기존 안전장치 확장)

| 실패 지점 | 처리 |
|---|---|
| 인포그래픽 생성/폴링/다운로드 실패 | `flags.append("인포그래픽 생성 실패")` → 기존 게이트가 에스컬레이션 처리(신규 게이트 로직 불필요) |
| 인포그래픽 타임아웃(60초 내 미완료) | 위와 동일 취급 (ready=False → 실패로 간주) |
| 텍스트 카드는 정상, 인포그래픽만 실패 | **발행 보류**(사용자 결정) — 텍스트카드 단독 발행 안 함, 둘 다 준비돼야 발행 |

---

## 5. 범위 (YAGNI)

### 이번 범위
- 히어로 이미지 슬롯 제거(card_render.py, morning_brief._render_card)
- `nlm_bridge.create_infographic` 신규(동기, create_report와 동일 폴링 패턴 재사용)
- `notebook_stage0.generate_infographic` 신규
- `morning_brief.py`: notebook_id 전달 경로 추가 + 정상발행 조건에 인포그래픽 성공 포함 + 2번째 사진 전송

### 이번 범위 아님
- 대시보드 인터랙티브 UI(`/api/insights/notebook_studio` 등) 변경 — 완전 별개, 무수정
- 슬라이드·오디오·비디오 등 다른 스튜디오 타입 연동
- 인포그래픽 실패 시 재시도 로직(1회만 시도, 실패=에스컬레이션)

---

## 6. 열린 항목 (구현 중 확정)
- 인포그래픽 전송 시 캡션 유무(짧은 캡션 vs 무캡션) 구현 중 결정
