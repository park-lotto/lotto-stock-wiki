# 코덱스 git차단 — 로그

- 2026-09-11 · 코덱스 샌드박스가 `.git`에 유령 Deny ACE 4개를 박아 아스트라 트랙 생성 실패. 원인 진단(코덱스 버그, 사장님 설정 무죄)·`tools/fix_git_acl.ps1` 제작·제거 성공했으나 명령마다 재적용 확인 → **코덱스=파일, 클로드=git** 역할 분담으로 확정. 트랙 2개(회사운영플랫폼·effect-mining-workers) 대신 커밋·푸시·finish. `codex mcp add claude -- claude mcp serve` 등록(코덱스 창에서 클로드 호출, 샌드박스 우회 여부 미검증). gstack 1.55→1.84 갱신. 메모리 `reference_코덱스_git차단_유령ACE`.
