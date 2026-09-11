---
name: reference_chrome_extension_automation_blocked
description: "chrome://, chrome-extension://, 크롬 웹스토어 페이지는 브라우저 자동화 도구가 전혀 접근 못 함(플랫폼 차단)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 181348e5-5c18-4092-a67b-255c27e98cf2
---

`chrome://*`(예: `chrome://extensions`)와 `chrome-extension://*`(예: 설치된 확장의
옵션/대시보드 페이지) URL은 claude-in-chrome 자동화 도구로 navigate 자체가
불가능("Can't interact with browser-internal or unparseable URLs" 에러). 크롬
웹스토어(`chromewebstore.google.com`) 상세 페이지는 navigate는 되지만 스크린샷·
스크립팅이 전부 막힘("The extensions gallery cannot be scripted").

**Why:** Chrome이 확장 설치/관리 UI를 자동화로부터 원천 차단하는 보안 정책 — 특정
도구나 권한 설정의 문제가 아니라 크롬 자체의 하드 블록. 재시도·워크어라운드로
뚫을 수 없음(2026-07-13, Tampermonkey 유저스크립트 설치를 대신해주려다 여러
방법 다 시도 후 확인).

**How to apply:** 사용자가 브라우저 확장 설치/설정(Tampermonkey 등)을 도와달라고
하면, 웹스토어 페이지를 열어주는 것까지만 하고 "Chrome에 추가"/"사용자 스크립트
허용" 토글/유저스크립트 임포트 클릭은 전부 사용자가 직접 해야 한다고 처음부터
명확히 안내할 것 — 자동화로 시도하다 실패하는 시행착오를 반복하지 말 것. 대신
사용자가 캡처해서 보내주는 스크린샷을 보고 다음 클릭을 정확히 안내하는 방식이
효과적이었음(단계별로: 웹스토어→설치→chrome://extensions에서 "사용자 스크립트
허용" 토글→대시보드 "스크립트 가져오기"로 로컬 파일 임포트).
