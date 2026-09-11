---
name: project_gemini_key_ops_2026_08_04
description: "쇼핑쇼츠 제미니 키 운영 체제(2026-08-04 확립) — 25키+제작소 예약2키, 사장님이 키 계속 추가 중(메모장→KEY_26+), 태거가 대량소비 주범"
metadata: 
  node_type: memory
  type: project
  originSessionId: a50f90e1-4297-4d1c-8775-a4c2fb913cd9
  modified: 2026-08-04T06:24:57.777Z
---

2026-08-04 확립된 키 운영 체제:
- 서버 `/etc/shopping-shorts.env`에 SHORTS_GEMINI_KEY 1~25 (유니크 25개).
- **제작소 비상 예약 2키**: 태거·백필은 `SHORTS_BULK_MODE=1`로 떠서 마지막 2키를
  못 본다(`config.py`). `run_tagger.sh`(서버 크론 00:12 UTC)에 export 반영됨.
- **사장님이 키를 계속 추가 중** — 바탕화면 `제미니키_보관메모장.md` ① 섹션에
  SHORTS_GEMINI_KEY_NN= 형식으로 붙여넣음. 다음 슬롯 **KEY_26**, config 상한 30
  (`_SHORTS_GEMINI_MAX`) — 넘으면 상한부터 올려라. 반영 절차: 중복검사 →
  서버 env 교체 → `systemctl restart shopping-shorts` → 상태파일에서 새 idx 소진해제.
- 무료키 = 하루 500건. 구글 리셋 한국 16시경, 상태파일(`shorts_gemini_state.json`)은
  UTC 자정(한국 9시) 리셋 — 리셋 시점 어긋남 주의([[reference_mix_stage_staleness_gap]]와
  별개, handoff/1소스믹스.md '상태파일 UTC 함정' 참조).
- 대량 소비 주범 = archive_tagger(태깅 1건=1호출, 백로그 수만 건). 근본 해법으로
  **유료 Tier1 1키(태거 전용)** 제안됨 — 백로그 2.7만 건 ≈ 8천 원. 사장님 결정 대기.
- 키 원본 메모: `Downloads/52926371_secretkey.txt`(계정10~20). [[reference_gemini_youtube_key_reserve_2026_07_10]]
