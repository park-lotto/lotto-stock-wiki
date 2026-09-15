---
name: 자동저장이-오려낸조각을-지운다
description: "완성본 만들어도 자막제거·꾸미기 반영 안 됨"의 뿌리 — scene_lab 자동저장이 film_ 조각을 지워 편성 서명이 바뀌고 청소본이 즉시 무효가 된다
metadata:
  type: reference
---

제보 "자막제거 후 3단계에서 장면 수정 → 완성본 만들기 → 다시 가도 적용 안 됨"(2026-09-05,
사장님·박세현 등)의 뿌리는 **자막제거가 아니라 편성 서명**이다.

- 청소본은 `final_clean_{편성서명}.mp4`로 캐시된다. 서명이 다르면 화면은 stale(AFTER 검은 칸).
- scene_lab은 편집이 멈추면 1.2초 뒤 **자동으로 apply**를 보낸다(사람이 안 눌러도 로그에 찍힌다).
- 그 payload가 EXTRA(`extra_segs`)를 못 채우면 `film_*` 조각이 seg_map에 없어 걸러지고
  scene_override에서 **영구 소멸** → 서명이 바뀌어 **방금 만든 청소본이 그 자리에서 무효**.

★판정법: 렌더 직후 `final_clean_{sig}.plan.json`(스냅샷)과 현재 edit_plan의 비트 재료를
대조하라. 조각 하나가 줄어 있으면 이것이다. 서버 로그의 `scene_lab/*/apply` POST 시각이
`edit_plan` updated_at과 일치하는지도 함께 본다.

수정(main `786c39bb1`): `edit_plan.apply_scene_lab`이 저장된
`plan["scene_lab"]["extra_segs"]`를 먼저 깔고 클라 payload를 얹는다(같은 id는 클라 우선).
09-05 낮 수정(`b35b85b45`)은 저장만 하고 **다시 읽지 않아** 반쪽이었다 —
"저장했다"와 "다시 읽는다"는 짝이다([[reference_목록에만_적힌_예외는_아무것도_안막는다]]).

곁: `clean_video_path`는 재청소해도 첫 청소본에서 갱신되지 않는다(미수정). 썸네일 배경 등
이 값을 쓰는 화면은 옛 청소본을 본다.

배포 함정: `DEPLOY_NOW` 플래그는 `/home/ubuntu/DEPLOY_NOW`(repo 안 아님)이고 **pull 시간창**용이라
"웹 재시작 연기(고객 접속 중)"는 못 푼다 → `sudo systemctl restart shopping-shorts`
([[reference_자동배포_시간창_2시6시]]).
