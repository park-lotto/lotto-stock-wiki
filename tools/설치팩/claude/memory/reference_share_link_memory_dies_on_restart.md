---
name: reference-share-link-memory-dies-on-restart
description: QR 폰으로 보내기 링크가 죽던 진짜 원인 — 단축 sid가 프로세스 메모리라 자동배포 재시작마다 전멸. 라이브 실측으로만 잡힌다
metadata:
  type: reference
---

숏템메이커 9단계 「QR로 폰에 보내기」가 "안 살아있다"던 진짜 원인(2026-08-19).

`_SHARE_STORE`가 **프로세스 메모리 dict**였다. 서버 자동배포 크론(3분)이 새 커밋마다
`systemctl restart` 하므로, 발급된 QR이 폰으로 스캔되기 전에 죽어 403 '만료'가 떴다.
→ `share_links` 테이블(sid·job_id·expires_at)로 이관. 라이브 실측:
고치기 전 `/s/{sid}`·`/api/share/v`·`/api/share/t` **전부 403** → 고친 뒤 **전부 200**
(영상 36.6MB, 썸네일 1.1MB). 별개 프로세스에서 발급한 sid를 라이브가 인식 = 재시작 내성.

**교훈: 배포가 잦은 서비스에서 "만료됐다/링크가 죽는다"는 제보를 받으면, TTL·시간 계산을
의심하기 전에 그 저장소가 프로세스 메모리인지부터 봐라.** 로컬에서는 재시작이 없어 항상
통과한다 — 재현은 라이브에서, 또는 "새 인스턴스로 조회"하는 테스트로만 된다.

곁가지(같은 화면에서 함께 나온 오진 2건):
- 렌더 전엔 버튼을 아예 안 그려서 "기능이 사라졌다"로 보였다 → 흐리게라도 항상 보인다.
- 그래도 "활성 안 된다" → 라이브 DB 실측 결과 그날 job 6개가 전부 ready_for_review(렌더 0회).
  이제 버튼이 최종 렌더까지 대신 하고 끝나면 QR을 자동으로 띄운다.

관련: [[reference_deploy_truth_branch_ssh]] · [[feedback_verify_before_claim_and_act]]
