---
name: reference_scene_dup_by_desc_not_phash
description: "쇼핑쇼츠에서 '같은 그림' 판정은 phash 문턱으로 못 한다 — 설명 겹침(자카드 0.6)으로 통일. 문턱을 올리려는 시도를 막는 실측 근거."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 44ef7732-82ce-47c7-a6b9-70bda6010ebb
  modified: 2026-08-16T13:34:27.540Z
---

장면 중복("왜 같은데 2장이 붙지")을 **phash 해밍거리 문턱(`DUP_MAX = 8`)을 올려서** 잡으려
하지 마라. 그 소재군에서는 안 갈린다.

실측 (job `8873eeb48a08`, 커피 추출기, 31장면 465쌍, 2026-08-16 브라우저 계측):

| 거리 | 쌍 | 실제 |
|---|---|---|
| 11 | `s1-8`(에스프레소가 노즐로 솟구침) ↔ `Db_2V-mzT44-8`(크레마가 표면을 덮음) | **진짜 같은 장면** |
| 13 | `s1-5`(가스버너 위 메이커) ↔ `s1-2`(원목 스쿱 거치대) | **전혀 다른 장면** |

최소 11 / 하위 10%가 21 / 중앙 31. 커피·금속처럼 톤이 균일한 소재는 8×8 흑백 해시로
안 갈린다 — **12로만 올려도 멀쩡한 장면이 묶여 사라진다.**

**그래서 판정을 설명 겹침으로 통일했다**: `label + scene_desc + change`의 자카드 ≥ 0.6.
세 곳이 같은 원리를 쓴다 — AI 채우기 프롬프트(`fill_beat_scenes`) · AI 결과 거르기 ·
최초 배치 자동보충(`_fill_beat_screen_time`의 `_same_look`).

**소스를 여러 개 올리면 `sid in used` 검사로는 못 막는다** — 같은 장면이 소스마다 있고
`seg_id`가 다르다. 이게 이 문제의 뿌리다.

**★같아 보이는 후보를 하드 차단하지 마라.** `_fill_beat_screen_time`에서 막으면 붙일 게
동나 아래쪽 **재사용 폴백(똑같은 컷을 그대로 또 씀)**으로 떨어져 더 나빠진다.
정렬 키 맨 앞에 두어 **뒤로만 밀어라** — 다른 화면이 있을 때만 그게 먼저 쓰이고, 없으면
종전과 같다(회귀 0).

관련: [[reference_shopping_shorts_scene_lab_verify]] · [[project_scene_spine_first]]
