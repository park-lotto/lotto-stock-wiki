---
name: feedback-deliver-outputs-to-desktop
description: 완성 결과물(영상·이미지 등)은 out/ 뿐 아니라 바탕화면(C:\Users\TheRose\Desktop)에도 복사해 전달할 것
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fab1bd3-9436-44e4-87d9-a14e338313b2
  modified: 2026-07-25T08:54:38.688Z
---

사장님에게 보여줄 **완성 결과물 파일은 `C:\Users\TheRose\Desktop`(바탕화면)에도 복사**한다.
2026-07-25 지시: "바탕화면에 앞으로 파일을 보내".

**Why:** `out/`는 프로젝트 폴더 깊숙이 있어 사장님이 직접 찾아 열기 번거롭다.
바탕화면에 있으면 바로 눈에 띄고 폰 전송·카톡 첨부도 쉽다.

**How to apply:**
- 정본은 그대로 `out/`에 저장(git·핸드오프 경로 유지) → **추가로** 바탕화면에 `cp`.
- 대상 = 사장님이 볼 최종 산출물(mp4·png·pdf 등). 중간 프레임·스크립트·로그는 제외.
- 복사 후 경로를 답변에 명시하고, 필요하면 `Start-Process`로 열어준다.
- 프로젝트 폴더 자체가 `Desktop\로또의 주식`이므로 **바탕화면 루트**(`Desktop\`)에 둔다.

관련: [[feedback_obsidian_open]]
