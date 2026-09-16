---
name: feedback_mockup_is_source_of_truth
description: 사장님이 손수 만든 목업이 있으면 그게 정본 — 설계텍스트/보조목업 말고 그 목업을 실렌더 대조하며 구현할 것
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e85fd9ee-43ef-4c1b-8180-990cc6b0ddc7
  modified: 2026-07-23T05:25:30.913Z
---

숏템메이커 UI 리뉴얼에서 오브 단계바를 `layout.html`(라벨 없는 점 버전)과 설계문서 텍스트 기준으로 만들었더니, 사장님이 렌더를 보고 "이게 아니었는데"라 함. 진짜 정본은 사장님이 집에서 6번 다듬은 `final-mock-v6.html`이었고, 거기엔 **오브 아래 이름 라벨 + 금색→민트 진행 채움선**이 있는데 내 구현은 숫자만 나왔다.

**Why:** 설계문서에 목업이 여러 개 참조돼 있어도(layout·visual-style·final-mock-v6·analysis-show) **"final-mock"이 최종 정본**이다. 보조 목업이나 텍스트 요약만 보고 만들면 사장님이 실제로 원한 디테일(라벨·진행선)을 빠뜨린다. 사장님은 시각 결과로 판단한다.

**How to apply:** UI 작업 착수 시 ①`assets-*목업/`에서 `final-mock-*` 최신 버전을 찾아 **정본으로 지정** ②그 목업을 실제 브라우저로 띄워 눈으로 확인 ③구현 후 **produce.html을 실렌더해 목업과 나란히 대조**(정적 grep은 관측이 아님) ④사장님께 렌더를 보여주고 OK 받은 뒤 finish. 서브에이전트는 navigate 권한이 막히는 경우가 많으니 그라운딩은 컨트롤러가 직접 한다. [[feedback_verify_with_real_data]]

관련: 숏템메이커 오브바 = 라벨+진행선 8단계(영상/대본·화면붙이기·자막제거·음성·꾸미기·썸네일·SEO·완성), "모든 페이지 이 v6 틀로" 확산이 사장님 방향(2026-07-23).
