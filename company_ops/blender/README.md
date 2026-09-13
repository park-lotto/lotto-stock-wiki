# Blender 제작 환경 — 설치 및 실제 검증

## 확인한 사용 문서

- [Blender MCP 설치·사용법](https://github.com/ahujasid/blender-mcp#usage): 장면 조회, 코드 실행, 자산 연결, 단일 MCP 실행.
- [Codex MCP 설정](https://learn.chatgpt.com/docs/extend/mcp): stdio 명령·환경변수 등록.
- [Blender 명령행 렌더](https://docs.blender.org/manual/en/4.0/advanced/command_line/arguments.html): 파일 로드 → 장면·출력 경로 → 프레임 렌더 순서. 설치한4.5.9의 `--help`로 옵션 재확인.
- [glTF 설명](https://docs.blender.org/manual/en/4.0/addons/import_export/scene_gltf2.html): 웹 전달 형식과 재질. 설치한4.5의 `scripts/addons_core/io_scene_gltf2/__init__.py`에서 `use_active_scene`, `export_apply`, `export_format` 직접 확인. 4.5 온라인 문서는 조회 오류가 있어 구버전 설명만 최신 사실로 간주하지 않았다.

## 이 PC 설치 상태 (2026-09-13)

- 프로그램: `%LOCALAPPDATA%/Programs/MakersLab-Blender/blender-4.5.9-windows-x64/blender.exe`.
- 공식 ZIP SHA256: `41da973b9bf95bb312cbeff4d1982feb13259b43c821686b9bafea4dfe5477cf` 검증.
- MCP: 동일 상위 폴더 `blender-mcp/.venv/Scripts/blender-mcp.exe`, PyPI wheel **1.9.1**, 배포 메타데이터 SHA256 대조 후 설치.
- 조사한 GitHub 소스: `5f8ddaf6e987c4aa0c3467fcc548838b28f64477`. 소스 체크아웃은 `config.py`가 gitignore되어 telemetry 초기화 때 import 오류. 소스 `uv sync`로 덮어쓰지 말고 PyPI 배포본을 유지한다.
- 별도 프로필: `profile/config`, `profile/scripts/addons/blender_mcp.py`. 기존 Blender 사용자 설정은 건드리지 않는다.
- Codex 전역 `blender` 항목 등록. 기존 `config.toml`은 같은 디렉터리에 `config.toml.before-blender-*.bak`으로 백업했다. 다른 MCP 항목은 보존.
- `DISABLE_TELEMETRY=true`, `BLENDER_MCP_SAFE_MODE=1`, `BLENDER_HOST=127.0.0.1`, `BLENDER_PORT=9876`, `BLENDERMCP_ADDONS_DIR`를 지정. Blender 애드온 동의도 false.
- 안전 모드는 완전한 샌드박스가 아니다. 로컬 소켓은 강한 실행 권한을 갖는다. 외부 공개 금지, 외부 스크립트 무검토 실행 금지. 유료/API 서비스는 활성화하지 않았다.

## 재실행

트랙 루트에서 `powershell -NoProfile -File company_ops/blender/start.ps1`.
이미 포트9876을 사용 중이면 두 번째 Blender를 시작하지 않고 멈춘다. 기존 작업을 임의 종료하지 않는다.

MCP가 실제 Blender에 연결됐는지 확인:

```powershell
& "$env:LOCALAPPDATA/Programs/MakersLab-Blender/blender-mcp/.venv/Scripts/python.exe" company_ops/blender/mcp_check.py
```

이 검증기는 Python MCP SDK로 initialize → list_tools → get_addon_status → get_scene_info를 호출한다. 단순 소켓 우회가 아니다. Codex 도구 목록 갱신 전에도 이 경로로 실제 MCP 작업을 진행할 수 있다. 앱 자체 도구 목록의 핫 리로드는 확인하지 않았다.

## 창면 검증물 재생성

빈 전용 세션에서 `mcp_check.py --script company_ops/blender/facade_proof.py`. 동일 이름의 장면이 이미 있으면 덮어쓰지 않고 거절한다.
`mcp_check.py --script company_ops/blender/export_proof.py`로 GLB 저장.
렌더는 Blender의 `--background <절대 blend 경로> --scene ML_Connection_Proof --render-output <절대 출력 경로> --render-frame 1 -- --cycles-device OPTIX`.
**출력은 절대경로 필수**. 일반 상대경로가 C: 기준으로 해석되는 현상을 실제 확인했다.

산출물은 `company_ops/.artifacts/blender-facade-proof.blend`, `.glb`, `blender-facade-proof-0001.png`. GPU RTX3080Ti / OptiX 렌더 결과 직접 확인. 장면27객체(카메라·조명 포함). GLB는 내보내기까지 확인, 웹 재현은 아직 미검증.

이것은 연결·재질 검증용 창면 한 구간이지 본사나 캠퍼스 완성 디자인이 아니다. 현재 `/campus/`는 보존했다. 다음은 A 본사 실루엣·층별 테라스·입구를 실제 모델로 설계하고 같은 각도로 비교한다.
