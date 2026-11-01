# 숏템 설치팩(installer/)

고객 PC 에 숏템을 까는 묶음. 설계: `docs/superpowers/specs/2026-10-18-숏템MCP-design.md` §2-2·§3·§4-3·§7-5.

| 산출물 | 무엇 | 만드는 곳 |
|---|---|---|
| `shortem-setup-win-x64-<버전>.exe` | 윈도 설치팩(실행도구 전부 + 로컬 MCP 서버 + 연결 파일 + 플러그인 + 안내) | `win/build_win.py` + `win/shortem.nsi` |
| `shortem.mcpb` | Claude Desktop 연결 파일(얇음 — 설치 폴더의 서버를 부르기만) | `mcpb/` (빌드 때 `mcpb pack`) |
| `claude-plugin/` (설치 폴더 안) | Claude Code 플러그인 `shortem` + 로컬 마켓플레이스 | `plugin/` |
| `시작.md` | Claude Code 입력창에 끌어다 놓는 입구(플러그인 등록 2줄 + `/shortem:setup`) | `시작.md`(설치 때 실제 경로로 채움) |
| `설치안내.html` | 그림 안내 11장(화면 모형) | `guide/설치안내.html` |
| `shortem-setup-mac-<arm64\|x64>-<버전>.pkg` | 맥 설치팩 | `mac/build_mac.sh` (**맥에서 실측 전**) |

## 빌드 — 윈도(이 PC 에서 실측)

```
py installer/win/build_win.py --out <빌드 폴더>
py installer/win/test_install.py --exe <빌드 폴더>/dist/shortem-setup-win-x64-1.0.0.exe --dir <없는 임시 폴더>
```

- 필요: 파이썬 3.10+, Node/npm(서버 의존성·`npx @anthropic-ai/mcpb@2.1.2`), 인터넷. NSIS 는 빌드가 직접 받는다(설치 불필요).
- `--client` 기본값 `installer/../shortem_client` — `server/index.js` 가 없으면 **자리표시 서버**로 빌드하고 그렇다고 출력한다.
- 내려받은 압축·풀린 폴더·설치될 폴더·결과물은 전부 `--out` 아래(git 밖). 받아 둔 파일은 해시가 맞으면 재사용.
- 빌드 폴더 경로가 길면(NSIS 260자 한계) `%TEMP%\shb<pid>` 정션을 잠깐 만들어 거쳐 읽는다.

### 설치 exe 동작
- 설치 경로 `%LOCALAPPDATA%\Shortem`(관리자 권한 없음, `RequestExecutionLevel user`). `/D=` 로 바꿀 수 있다.
- 끝: Claude Desktop 이 `.mcpb` 를 열 수 있으면 `shortem.mcpb` 를 연다(마침 화면 체크박스, 기본 켜짐) · 바탕화면 `숏템작업\시작.md`·`설치안내.html` · 제거 프로그램 등록(HKCU) · 사용자 환경변수 `SHORTEM_INSTALL`·`SHORTEM_NODE`(Claude Code 플러그인이 동봉 node 를 찾는 데 쓴다).
- 무인: `exe /S [/OPENMCPB] [/D=경로]`. 시험: `/SANDBOX`(등록 키·환경변수 이름에 `_SANDBOXTEST`, 바탕화면 대신 설치 폴더 안 `_sandbox_desktop`).
- 제거: 설정 ▸ 앱, 또는 `uninstall.exe /S`. `숏템작업`(내 영상)·`~/.shortem`(키·캐시)은 남긴다.

### 왜 NSIS 인가
이 PC 에 Inno Setup·NSIS 둘 다 없었다. NSIS 3.11 은 **포터블 zip(2.4MB) 하나로 설치 없이** `makensis` 가 돌고, 무인 설치(`/S`)·설치 폴더 지정(`/D=`)·사용자 단위 설치·LZMA solid 압축·서명 훅(`!finalize`/`!uninstfinalize`)이 기본 기능이라 빌드 서버에 아무것도 깔 필요가 없다. Inno Setup 은 컴파일러를 먼저 설치(또는 설치본에서 뽑기)해야 한다.

## 코드서명 자리(지금 미서명)

| 대상 | 환경변수 | 하는 일 |
|---|---|---|
| 윈도 exe·uninstall.exe | `SHORTEM_SIGN_PFX`(+`SHORTEM_SIGN_PASSWORD`, `SHORTEM_SIGNTOOL`, `SHORTEM_SIGN_TIMESTAMP`) | makensis `!finalize`·`!uninstfinalize` 로 `signtool sign /fd SHA256 /tr <ts> /td SHA256` |
| 맥 실행 파일 전부 | `SHORTEM_APP_ID`="Developer ID Application: …" | inside-out `codesign --options=runtime --timestamp --entitlements …` |
| 맥 pkg | `SHORTEM_INSTALLER_ID`="Developer ID Installer: …" | `productbuild --sign` |
| 맥 공증 | `SHORTEM_NOTARY_PROFILE` | `notarytool submit --wait` → `stapler staple` → `spctl -a -t install` |
| .mcpb | (선택) `npx @anthropic-ai/mcpb@2.1.2 sign shortem.mcpb --cert … --key …` | Desktop 이 이 서명을 신뢰 판단에 쓰는지 **미확인**(설계 §13-1) |

인증서가 없으면 빌드는 "미서명" 이라고 출력한다. 미서명 exe 는 SmartScreen 경고("추가 정보 ▸ 실행")가 뜬다 — 안내 HTML 4단계에 적어 두었다.

## 실행도구(버전·출처·해시 고정 = `common/tools.lock.json` 한 곳)

| 도구 | 윈도 x64 | 맥 |
|---|---|---|
| Node | 24.15.0 (`node.exe` 만, sha256 = nodejs SHASUMS256) | 24.15.0 `bin/node` |
| chrome-headless-shell | 131.0.6778.204 (GCS md5·크기 대조) | 같음(mac-arm64·mac-x64) |
| ffmpeg·ffprobe | gyan 9.0.2 essentials (libass 포함, GitHub digest) | **소스 직접 정적 빌드** 9.0.2 + libass 0.17.3·freetype 2.13.3·fribidi 1.0.16·harfbuzz 10.1.0·x264(stable 커밋 고정) |
| Python | 3.12.15 standalone 20261013 + Pillow 13.0.0·numpy 2.5.4(`--require-hashes`) | 같음(+ yt-dlp 를 파이썬 패키지로) |
| yt-dlp | 2026.08.19 `yt-dlp.exe` | 2026.8.19 wheel + `tools/yt-dlp/yt-dlp` 얇은 실행 스크립트 |

`tools/tools.manifest.json`(서버 계약 `shortem_client/server/tools_paths.js`): `tools.{node,ffmpeg,ffprobe,chrome,python,ytdlp}.{path,sha256,version}` + `files[]`(실행 파일·라이브러리 전부 sha256). 쓰는 곳은 `common/write_manifest.js` 하나(윈도·맥 공용).

## 경로·환경변수 약속

| 이름 | 뜻 | 누가 정하나 |
|---|---|---|
| 설치 폴더 | 윈도 `%LOCALAPPDATA%\Shortem` · 맥 `~/Library/Application Support/Shortem` | 설치 프로그램 |
| `SHORTEM_INSTALL` | 설치 폴더(다른 곳에 깔았을 때 연결기가 찾는 길) | 설치 프로그램(윈도 사용자 환경변수 · 맥 `~/.zshenv` 블록) |
| `SHORTEM_NODE` | 동봉 node 절대경로 — 플러그인 `"command": "${SHORTEM_NODE:-node}"` | 같음 |
| `SHORTEM_TOOLS` | `<설치>/tools` — 서버가 manifest 를 읽는 곳 | 연결기(launcher.js)가 서버를 띄울 때 넣음 |
| `SHORTEM_HOME` | **서버의 사용자 자료 폴더(~/.shortem)** — 설치 폴더 아님 | 서버(paths.js) |
| `SHORTEM_LICENSE`·`SHORTEM_WORK` | 라이선스 키·작업 폴더 | Desktop `.mcpb` user_config / Code 플러그인 userConfig |

## 맥 — `mac/build_mac.sh` (★맥에서 실측 필요)

`ARCH=arm64 installer/mac/build_mac.sh --out <폴더>` / `ARCH=x64 …`. 이 PC 는 윈도라 **`bash -n` 문법 검사만** 했다. 처음 맥에서 돌릴 때 확인할 것: ffmpeg configure 통과·`otool -L` 외부 dylib 0·`-filters` 에 ` ass `, Chromium 재서명 entitlement 최소 집합, 홈 도메인 pkg 의 `--install-location` 해석(~/Library/… 로 깔리는지), postinstall 이 root 로 도는지 사용자로 도는지, 공증 통과.

## 용량
(빌드 결과 숫자는 `dist/build_report.json` 이 정본 — 아래는 2026-10-18 이 PC 실측)

| 항목 | 값 |
|---|---|
| 설치 exe | **203.5MB** (`shortem-setup-win-x64-1.0.0.exe`, LZMA solid, 빌드 약 8~9분) |
| 설치 뒤 폴더 | 765.3MB — chrome-headless-shell 235 · ffmpeg+ffprobe 201 · python(+Pillow·numpy, 시험 묶음·pip 제거) 174 · node 88 · yt-dlp 18 · server(+node_modules) 29 (MB) |
| shortem.mcpb | 22.7KB (manifest.json · launcher.js · icon.png) |
| 무인 설치 시간 | 118~126초(이 PC) |
| 설치 폴더 안 가장 긴 상대 경로 | 122자 → 설치 폴더 경로는 120자 이하만 받는다(넘으면 설치 거절, 종료 코드 4) |

## 설치 검사(`win/test_install.py`)가 재는 것
manifest sha256 전부(files·tools) · ffmpeg `-filters` 의 ` ass ` · chrome `--version` · node `-v` · python `import PIL, numpy` · yt-dlp `--version` · launcher.js 로 MCP initialize→tools/list→tools/call(shortem_setup) 왕복 · 제거 프로그램 키·환경변수 등록 → 제거 뒤 파일·키·환경변수 0.
설치 직후 postinstall.js 도 manifest sha 를 다시 대조한다(어긋나면 설치 실패 코드 3).

## 서버를 다시 넣어 빌드하기
`shortem_client/server` 가 바뀌면 같은 명령을 다시 돌리면 된다(내려받은 파일은 해시가 맞으면 재사용):
```
py installer/win/build_win.py --out <빌드 폴더>
```
