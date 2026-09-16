---
name: feedback_simple_before_complex
description: 원격 인증/설정 문제는 로컬에 이미 있는 토큰 파일부터 찾아본 뒤 복잡한 인프라(VNC 등)로 넘어갈 것
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 174439c8-05f0-4472-9abf-783a04b1935b
---

원격 서버에서 로그인/인증이 막히면, 곧바로 Xvfb+VNC 같은 무거운 원격 브라우저 인프라를
구축하기 전에 **로컬 PC에 이미 저장된 인증 토큰/쿠키 파일을 먼저 찾아서 복사할 수 있는지
확인**한다.

**Why**: nlm(NotebookLM CLI) 서버 인증 작업 중, 처음부터 Xvfb+x11vnc+websockify(noVNC)
원격 브라우저 인프라를 구축해 사용자에게 로그인을 요청했다. 사용자가 "이거 뭐라고 이렇게
힘들고 못하는거야, 오푸스도 설계 안 되는거야?"라고 명확히 불만을 표함. 실제로는
`~/.notebooklm-mcp-cli/profiles/default/cookies.json`처럼 로컬에 이미 인증 토큰 파일이
존재했고, 그걸 서버로 scp 복사하는 게 훨씬 간단한 첫 시도였다(결과적으로 이 경우는 구글의
IP 기반 세션 차단 때문에 안 됐지만, 그건 시도해보고 나서야 알 수 있는 것 — 순서상 먼저
시도했어야 함).

**How to apply**: 새 기기/서버에서 어떤 CLI 도구의 인증이 필요할 때, (1) 먼저 로컬에서 그
도구가 토큰을 어디에 저장하는지 찾는다(`find ~ -iname "*<toolname>*"`, uv/pipx 설치 경로
등) (2) 작은 설정/토큰 파일이면 그대로 복사해서 되는지 시도 (3) 안 될 때만(예: IP 기반
세션 차단처럼 파일 복사로는 못 넘는 진짜 이유가 확인된 뒤에) VNC 같은 무거운 인프라로 확장.
"어려운 길이 필요해 보인다"는 가정보다 "쉬운 길을 먼저 실측"이 항상 우선이다.
