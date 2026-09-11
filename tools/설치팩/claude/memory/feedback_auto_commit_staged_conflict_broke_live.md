---
name: feedback_auto_commit_staged_conflict_broke_live
description: "\"auto: session changes\" 커밋이 미해결 병합충돌을 그대로 add→라이브 HTML/JS가 SyntaxError로 죽음. 게이트는 non-Python 못잡고, 깨진 baseline이 게이트 오탐까지 유발"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a9a4f2b3-fa1a-459d-8c68-570986667a04
  modified: 2026-07-19T03:14:12.891Z
---

2026-07-19 실사고: `shopping_shorts/static/produce.html`과 `tests/test_style_use_js.py`에
**커밋된 git 충돌마커(`<<<<<<< HEAD`/`=======`/`>>>>>>>`)**가 origin/main에 올라가 있었다.
`de1aa5ecd`·`a48dd25b7` **"auto: session changes"** 커밋이 미해결 병합(`f04aec0de` merge)을
`git add`로 통째로 담아 발생. produce.html `<script>` 전체가 SyntaxError → **영상 제작소 페이지가
안 열림**(사장님 제보로 확인). 서버 auto_deploy는 정상이라 깨진 커밋을 그대로 라이브에 배포했다.

**Why:** 병합게이트는 문법검사=Python compileall + `import shopping_shorts.app` + pytest만 본다.
**HTML/JS 충돌마커는 아무도 안 잡는다.** 그리고 더 나쁜 건 게이트 **오탐**: 충돌마커가
`test_style_use_js.py`도 깨서 origin/main의 pytest가 **rc=2(수집 불가)** → baseline 실패목록이
**빈 집합**. 내 수정이 수집을 복구하니 그제야 보이는 **기존 8건(apify·edit_plan·mix, 손 안 댐)**이
`new_failed = 8 - 0`으로 계산돼 "신규 8건 깨짐"으로 `finish`가 거부. 즉 **수집을 고치는 수정은
게이트를 못 통과한다**(고치는 행위가 기존실패를 드러내므로). 데드락.

**How to apply:**
- 새 세션 시작 시 `git grep -nE '^(<<<<<<< |=======$|>>>>>>> )' origin/main` 로 커밋된 충돌마커
  1회 스캔. 특히 `*.html *.js`(게이트 사각지대).
- "auto: session changes" 커밋을 신뢰하지 말 것 — 미해결 병합을 담았을 수 있다.
- 게이트 오탐: origin/main pytest가 rc=2(insane baseline)면 `finish`가 정상 수정을 거부한다.
  이땐 **수동 병합**(트랙에서 `git merge origin/main`→해소·검증→`git push origin HEAD:main`)+
  서버 강제 `git pull --ff-only && sudo systemctl restart shopping-shorts`로 복구.
- 근본대책 후속: `tools/merge_gate.py compare()`가 baseline이 insane(rc∉{0,1})이면 `new_failed`
  비교를 스킵하도록 패치해야 이 데드락 재발 안 함. [[reference_deploy_truth_branch_ssh]]
