---
name: reference_capcut_draft_format
description: CapCut draft(draft_content.json) 포맷 역공학 실측 + 웹앱이 File System Access API로 캡컷폴더 직접쓰기 가능(레퍼런스 방식)
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0120789f-ab04-47db-9779-e09084f300ad
  modified: 2026-07-20T10:15:50.926Z
---

쇼핑쇼츠 "캡컷으로 내보내기"([[project_쇼핑쇼츠_자동화]], 내보내기캡컷 트랙)의 T2 근거.

**전제 정정**: 레퍼런스(쇼핑팩토리)는 데스크톱 앱이 아니라 **웹앱 + 브라우저 File System Access API**
(`showDirectoryPicker`, Chrome/Edge 전용, Safari/FF 불가)로 캡컷 draft 폴더에 직접 쓴다.
→ **우리 웹앱도 캡컷 폴더에 프로젝트 직접 생성 가능.** "웹앱은 로컬폴더 못 쓴다"는 틀림. .bat 우회 불필요.
폴더 핸들을 IndexedDB에 저장하면 2회차부터 폴더선택 없이 원클릭.

**CapCut draft 포맷** (실측 2026-07-20, 설치버전 8.9.1.3802, Windows):
- draft 1개 = 폴더 1개(폴더명=프로젝트명), 기본경로 `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\`
  (사용자가 설정에서 옮길 수 있음 — 이 PC는 `C:\capcutproject\CapCut Drafts`).
- 핵심파일 `draft_content.json`: `version:360000`, `new_version:"171.0.0"`, fps 30, **시간 단위=마이크로초(초×1e6)**.
- `canvas_config`(세로숏폼=1080×1920) + `materials{videos,audios,texts,speeds,beats,sound_channel_mappings,
  vocal_separations,placeholder_infos,material_animations,canvases}` + `tracks[{type:video|audio|text, segments}]`.
- 세그먼트: `material_id`참조 + `source_timerange`/`target_timerange`{start,duration μs} + `extra_material_refs`(동반 material id).
- **동반 refs**: 오디오=speed·placeholder·beat·sound_channel_mapping·vocal_separation(5) / 텍스트=material_animation(1) /
  비디오=speed·canvas·sound_channel_mapping·placeholder·vocal_separation. 전부 단순객체라 새 UUID로 생성.
- 자막 텍스트: material.`content`가 JSON**문자열** `{"styles":[{fill.color[r,g,b],font.path,range:[0,len],size}],"text":"..."}`, 세그먼트 render_index 14000+.

**상세 스키마·구현계획**: `docs/superpowers/specs/2026-07-20-내보내기캡컷-design.md` 부록A.
**T1(ZIP 다운로드)·T2(원클릭 캡컷 보내기) 둘 다 라이브**(origin/main e81678b1b·e1a97062b).
구현: `capcut_draft.py`(draft 생성+assemble_draft_folder), `/api/mix/capcut/{job}?base=`(매니페스트)+`/api/mix/capcut_asset`,
produce.html `sendToCapCut()`(showDirectoryPicker+IndexedDB 핸들). 검증됨: 실캡컷(8.9.1.3802) 홈에 뜨고 영상+자막 렌더(육안).
샘플 draft엔 device_id/mac_address 있어 **repo 커밋 금지**(생성기는 새 UUID+사용자 경로 사용, platform ID는 빈값으로 열림).
실 E2E 성공(원클릭→실 32초 프로젝트 캡컷 생성, 사장님 라이브 확인). 제스처버그=showDirectoryPicker는 클릭 제스처 안에서 **맨 처음**(앞에 await/prompt/alert 금지) 호출해야 함 — 핸들은 페이지 로드 때 IndexedDB에서 미리 읽어둔다.

**상대경로 실패**: 캡컷은 `##_draftpath_placeholder##`·파일명만 둘 다 Media Not Found → **에셋은 절대경로 필수**. 브라우저는 고른 폴더 절대경로를 안 알려줘서, 경로를 표준화(`C:\capcutproject\CapCut Drafts`)해야 함.
**최초설정 자동화(수동 폴더생성+캡컷 저장위치변경 제거)**: 캡컷 저장위치 = `%LOCALAPPDATA%\CapCut\User Data\Config\globalSetting`(평범 INI)의 `currentCustomDraftPath=C:\\capcutproject\\CapCut Drafts`(**더블백슬래시**=Qt 이스케이프). 브라우저는 못 바꾸지만 `.bat`(`static/capcut_setup.bat`)이 폴더생성+이 키 세팅(`[char]92`로 더블백슬래시 생성·.bak 백업·다른줄 온전). CapCut 실행 중이면 종료 시 덮어쓰므로 **캡컷 꺼둔 채** 실행. base 기본값 `C:\capcutproject\CapCut Drafts`.
