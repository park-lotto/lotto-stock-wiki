# Blender 연결 및 본사 제작 검증 계획

> 실행: superpowers:executing-plans. 기존 회사운영플랫폼 트랙 안에서 진행한다.

**목표:** Blender와 커뮤니티 MCP를 로컬에 설치하고 실제 장면 생성·저장·렌더로 연결을 검증한다.
**구조:** 공식 ZIP 배포를 별도 사용자 프로그램 폴더에 설치. GitHub 소스 버전 고정. 기존 Codex 설정 백업 후 blender 항목만 추가. 텔레메트리 비활성화, localhost 바인딩, 별도 테스트 장면.
**기술:** Blender 4.5 LTS, ahujasid/blender-mcp, uv, Python MCP SDK.

- [ ] 공식 배포 SHA256 검증, Blender 버전 실행 확인.
- [ ] MCP 저장소 소스/라이선스/실행 경로 검토. 임의 Python 실행 및 텔레메트리 경로 확인.
- [ ] 기존 설정 백업. 환경변수 DISABLE_TELEMETRY=true와 localhost 설정으로 MCP 등록.
- [ ] 별도 Blender 프로세스에 addon 등록. MCP initialize/list_tools/get_scene_info 실제 호출.
- [ ] 테스트 장면에 식별 가능한 물체 생성 후 조회·blend 저장·이미지 렌더 확인. 기존 장면 삭제 금지.
- [ ] 본사 정밀 제작은 승인 A의 외형 기준을 유지. 연결 검증 후 별도 파일에서 착수하며 현재 웹 캠퍼스는 교체하지 않는다.
- [ ] 설치 경로·커밋·재시작 필요 여부·검증 결과를 handoff 및 wiki/log.d 기록. 트랙만 커밋/푸시, main 미배포.
