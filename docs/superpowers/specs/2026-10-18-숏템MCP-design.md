# 숏템 MCP — 설계 (2026-10-18, 조사·설계 전용 세션, 코드 수정 없음) — **개정 4**

> **개정 4(2026-10-18)** 사장님 결정: A 고객 API 키 = `~/.shortem/keys` 0600 **확정** / B 설치팩·자산 = 객체 저장소+서명 URL **확정**, 단 "다 주는 거 아니다 — 공개는 해서 옵션은 주지만 고객 PC로 다 다운받지 못하게" → 페이지는 **팩 전체를 미리보기로 공개**(저해상도·짧은 견본·워터마크 스트리밍, 원본 다운로드 링크 없음), 옵션 선택은 전부 가능, 원본은 `assets_for`가 이번 편 참조분만(§8-1 미리보기 규격·탐지) / C 캐시 30일·2GB **확정** / D 탐지 임계값 초기안 **확정**(베타 1주 뒤 조정) / E 다른 기기 시작 = 거절 **확정** / F 맥 ffmpeg = **libass 포함 정적 빌드를 우리가 빌드·서명·공증해 설치팩에 동봉** **확정**(볼케이노 setup 실측: 볼케이노는 ffmpeg를 동봉·설치하지 않고 `shutil.which('ffmpeg')`로 찾아 `-filters`의 ` ass ` 유무만 잰다 — §3-4) / 원격 MCP "두지 않음" 유지.

> **개정 3(2026-10-18)** 사장님 결정 반영: ① 원격 MCP 두지 않음(비개발자용 설명 §12-1) ② 설치팩 = 설치 exe/pkg + 얇은 연결 파일(.mcpb)/플러그인 **확정** ③ 노하우 "최소한으로 노출 제한" **확정** → 체크리스트 §7-4 ④ 품질검사 결과 서버 보고 **없음**, 대신 **이상 행동 모니터링 필수** §7-9 ⑤ 기기 2대 등록·각 기기 MCP 설치·**동시 실행 1개**(임대·하트비트) §7-10 ⑥ **맥도 1차부터** §3-4 ⑦ 진행 상세 보기 기능 **없음**(`shortem_job open` 제거).
> 개정 3 추가: §3-5 "비교: 쇼츠AI 스타터킷"(경쟁 킷 실물 비교 → 그림 안내 HTML·드래그 1회 온보딩·자가점검 3종 채택, 평문 동봉·winget 의존·라이선스 없음은 반대로).
> 개정 2: 실행도구 전부 설치 때 / 자산은 필요한 것만 / 진행은 순서만. 개정 1: 렌더=고객 PC 확정(카드 079·213 그대로). 1판의 서버 렌더·원격 MCP(OAuth)·서버 품질 관문은 삭제.

사장님 요청(원문): "칼카피 숏템엔진에 올라가는것들 이제 mcp로 만들어서 고객이 바로 쓸수있게 설치팩부터 명령어팩등 보안부터 다 신경써서 설계할꺼야. 볼케이노mcp한번 어떻게 하는지 확인해보고 우리꺼로 할방법알려줘." / "고객들이 클로드코드를 안쓰고 데스크탑을써도 되게 / 우리 프리셋을 볼수있게 숏템메이커에 페이지 하나 / 프리셋 이름 보고 자기만의 옵션 설정 → 채널 통일성 / 우리가 더 고퀄로." / "랜더는 다 본인 pc에서 한다. 우리는 그냥 프리셋보여주고 옵션을 설정하는 페이지만 … 서버는 전혀안쓰는거야." / "설치팩에 모든 실행도구들 다 받게 하고 / 우리 자산팩들은 다 넘겨주지말고 필요한것만 / 볼케이노처럼 자세하게 보여주지말고 실행순서 어떤게 되는지만."

근거 규칙: 주장마다 `파일:줄` 또는 명령 출력. 못 본 것은 **미확인**. 토큰·키 값은 어디에도 옮기지 않았다(`.volcano_runner_key.json`·`~/.volcano/keys/` 열지 않음).

---

## 0. 한 줄 결론

**설치팩(윈도 exe·맥 pkg, 코드서명·공증) 하나가 실행도구 전부(Node·로컬 MCP 서버·Chromium headless-shell·ffmpeg·Python 런타임)를 고객 PC에 깔고, 얇은 연결 파일(.mcpb)과 Claude Code 플러그인이 그 로컬 MCP 서버를 등록한다. 자산(프리셋 규격·글꼴·효과음·BGM·짤)은 설치 때 없고, 영상 한 편마다 "이번 작업에 필요한 것"만 라이선스 키로 서명 URL을 받아 내려와 짧게 캐시된다. 우리 서버는 보여주기(페이지)·설정(채널 옵션)·내려주기(필요 자산)·**라이선스 확인(임대·하트비트)**·**이상 행동 탐지**만 하고 제작 호출은 0건. 고객 화면엔 "9단계 중 4번째 — 장면 계획"만 보이고 지시·규격·payload는 로컬 job 파일 밖으로 안 나온다.** 그 편에 쓰인 규격이 그 PC에 남는 것은 못 막는다 — "최소한으로 노출 제한"(§7-4 체크리스트)으로 줄인다.

---

## 1. 볼케이노 MCP는 어떻게 도나 (실측 요약)

### 1-1. 흐름도
```
[고객 PC]                                   [볼케이노 서버 = Cloudflare Workers]
 ~/.claude.json: {"type":"http","url":"https://volcano-mcp.groove1027.workers.dev"}   ← 설정 한 줄(실측: 이 PC .claude.json /mcpServers/volcano)
   │ ① claude mcp login volcano ──► 브라우저 OAuth
   │      AS 메타데이터(실측 fetch /.well-known/oauth-authorization-server): authorize·token·register(DCR) · PKCE S256 ·
   │      token_endpoint_auth none · scopes volcano, volcano:ta-publish · resource_indicators_supported true
   │      PRM(/.well-known/oauth-protected-resource): resource=서버 URL, bearer_methods ["header"]
   │ ② tools/call volcano_video {step, preset, payload, source}   ← 도구 2개(volcano_video·volcano_cardnews)
   │ ◄── {next_step, do[], measure[], then_call_with[], carry[], next_payload(그대로 되돌릴 것)} "한 글자라도 다르면 반려"
   │ ③ step=assets: 팩 5종(sfx·pepe·fonts·runner·framevision) 서명 URL(?k=, 6h) + runner_key(출입증)
   │      실행기가 .volcano-asset-receipts/<pack_sha>.json(파일별 sha256·size)로 재사용 판정(volcano_drive.py:427-520)
   │ ④ env 이후 실행 단계는 실행기(volcano_drive.py)만 서버를 부름. 출입증 {token,url,expires,preset} 0600·이틀(:2975-3019)
   │      JSON-RPC tools/call + Bearer + MCP-Protocol-Version 2025-11-25(volcano_run.py:469-476) · _meta.runner_update로 실행기 자동 갱신(sha256, :478-500)
   │ ⑤ do[] 종류: transcribe·ask_video·fetch_images·image_qc·synthesize·generate_images·argv(volcano_drive.py:1681-1803)
   │      argv는 "한 글자도 안 고치고" subprocess.run(volcano_run.py:925-937) ★argv[0] 허용 목록 없음(:860-905, grep ALLOWED 0건)
   │ ⑥ 사람 자리 3곳(script·prompts·memes)에서 멈추고 next_payload.json 저장 → --step <단계>로 재개
   ▼ out/<편>.mp4
```
API 키: 고객 키를 `~/.volcano/keys/<서비스>`에 값만, 서버는 키를 안 가짐, 어느 헤더에 실을지는 서버가 `env`에서 지정, 로그엔 sha256 앞 12자(volcano_drive.py:1036-1047, runner README:61-62). payload가 크면 `fold_payload` 3.4MB→92KB(volcano_run.py:350-363).

### 1-2. 장점(가져올 것) / 1-3. 약점(실사고)

| 장점 | 근거 | | 약점 | 실사고 근거 |
|---|---|---|---|---|
| 노하우는 서버에만, 실행기는 껍데기 | runner/README.md:3-4 | | 고객 PC 셋업 무거움(venv 2개·onnxruntime·팩 80MB), CH PC 재셋업 | handoff/볼케이노MCP.md:27-37, :74, :140 |
| 규칙은 판정(반려 사유)으로만 | handoff:45-54 | | Claude Code auto 분류기가 실행기·팩 다운로드 차단 → 사장님 `!` 수동 | :83, :119, :130 |
| 돈 나가기 전 env 실측 | 원리 문서 §1 3행 | | `.vscode/tasks.json`이 `--dangerously-skip-permissions` 자동 실행 | :12 |
| 팩·실행기 sha256 대조·영수증 재사용 | volcano_drive.py:427-520 | | 실행기 버전마다 처방이 달라짐(밈 글자 보존 3가지) | :87, :121, :133 |
| 출입증 무상태 서명 토큰(이틀) | handoff 요약 | | argv 허용 목록 없음 → 서버가 고객 PC에서 임의 명령 가능한 구조 | volcano_run.py:860-937 |
| 피드백 통로 내장 | 원리 §1 11행 | | 키 파일을 한 기계 모든 세션이 공유 → 남의 크레딧 소진 | volcano_drive.py:1036-1040 |
| 설치 = 설정 한 줄 | .claude.json | | 채널 고정·조정 불가 / 왕복 길이(실행기 26~46초 vs Claude 개입 124~275초) | 원리 §6, README:75-76 |

**우리와 결정적 차이**: 볼케이노는 "노하우 서버 + 실행기 고객 PC", 응답에 지시·payload·반려 규칙 원문이 전부 실린다(그래서 우리가 30건 반려로 역분석했다, handoff:45). 우리는 "노하우도 고객 PC(필요한 만큼만), 응답은 순서만, 서버는 보여주기·설정·내려주기·라이선스·탐지". 가져올 것은 ③영수증·④출입증 모양·⑥재개 파일·껍데기 README 규율.

---

## 2. 우리 구조 — 무엇이 어디서 도나

```
[우리 서버 shoppingshorts.duckdns.org]                       [고객 PC — 기기 1 / 기기 2 (각각 설치 필수, 동시 실행 1)]
 '클로드형' 페이지(§8): 프리셋·팩·통과작 보기 / 내 채널 옵션 저장 /     Claude Desktop ──stdio──┐
   라이선스 발급·기기 2대·회수 / 설치팩 내려받기                           Claude Code  ──stdio──┤ 로컬 MCP 서버(Node, 설치팩이 깐 것)
 REST 5개(§5) — 제작 호출 아님                                                                     │  ├ tools 6개(§4) 전부 로컬 실행
   GET  /api/claude/license        키·기기·회수 확인                                                 │  ├ engine/ 상태기계·대본 판정·plan·render·check·응답 가르기
   POST /api/claude/lease          임대 취득·하트비트·반납(동시 실행 1, §7-10)                       │  ├ tools/  node·chromium-headless-shell·ffmpeg·python (설치 때 전부)
   GET  /api/claude/assets         이번 작업 자산 목록(assets_for) + 서명 URL(§2-3)                   │  ├ ~/.shortem/cache/<sha>  이번 편 자산(30일·2GB LRU)
   GET  /api/claude/pack/<id>      목록 안 자산만 서명 URL 재발급                                     │  └ ~/.shortem/keys/<서비스> 고객 API 키(값만, 0600) — 서버는 안 가짐
   POST /api/claude/feedback       요청·버그                                                        ▼
 탐지(§7-9): license·lease·assets 로그에서 이상 신호 → 경고/속도 제한/정지/관리자 경보          <작업폴더>/jobs/<id>/ (state·규격) → out/<편>.mp4 + verdict.json
```
- 제작 호출 0건: 대본 생성·TTS·렌더·검사 어느 것도 서버에서 안 돈다(카드 079 '됐다의 기준'). `lease`·`license`는 **권한 확인**이지 제작이 아니다(§7-10).
- 대본·판단 = 고객 본인 Claude 구독. 외부 API(TTS·이미지·Gemini) = 고객 본인 키. 유튜브 재료도 고객 PC(서버 IP 봇차단 app.py:810-811이 문제가 안 됨).

### 2-1. "숏템엔진에 올라가는 것" 실측 목록 → 고객 PC로 어떻게 가나

| 자산 | 지금 어디(실측) | 수·크기 | 고객 PC로 |
|---|---|---|---|
| 브랜드 장부 | `channel/브랜드.json` | brands 8 | 페이지에 **이름만**. PC로는 고른 프리셋의 brand 1개 |
| 스타일 장부 | `channel/스타일.json` | styles 4 + options 12 | 페이지 desc·example만. PC로는 고른 스타일의 규칙 |
| 결과물 장부 | `channel/결과물.json` | 26(통과 15) | 페이지 미리보기만. PC로 안 감 |
| 채널 프리셋(틀) | `channel/<slug>/preset/<갈래>/<틀>/{frame.json,manifest.json,sources/}` | frame.json 7(sseolpulda 4·banggu·yummyknow·hottemreport) | **고른 틀의 frame.json 축약 + rules만**. sources/·variable_stats·bench 원값은 안 감 |
| 내 팩(채널 키트) | `calcopy_frame/my_packs.json` | brand·text·tts·meme_pool·sfx_pool·bgm | 프로필(§9)의 원형 → 합본에 포함 |
| 단계(상태기계) | `calcopy_topics.py`·`calcopy_make.py`(트랙) | found→…→passed, 사람 자리 2 | **로컬 엔진으로 이식**. 서버 상태기계는 안 씀 |
| 렌더러 | `tools/render_scene_style.js` puppeteer+Chromium, 호출 `scene_style.py:549,574` | — | 설치팩: chromium-headless-shell |
| ffmpeg | 설치본 | 이 PC full 217MB(실측) | 설치팩: essentials |
| 파이썬 엔진 부분(판정·compare·bench) | `shopping_shorts/*`, `tools/calcopy/engine/*`, `channelkit/*` | Pillow 15·numpy 31MB(실측) | 설치팩: Python 런타임(python-build-standalone) + 두 모듈 |
| 꾸미기 템플릿 | `deco_templates.py` 3×4=12, PNG 12 | 1MB | 자산(고른 1) |
| 효과음 팩 | `assets/sfx_packs` 팩01~20 × 7 | 5MB | 자산(프로필 팩 1) |
| BGM | `assets/bgm_lib` 24곡 | 20MB | 자산(고른 곡 1) |
| 글꼴 | `static/fonts` 파일 60 | 235MB | 자산(참조 2~4종) |
| 목소리 프리셋 | `voice_presets.json` 79 | 작음 | 합본(목록) — 합성은 고객 키 |
| 자막 효과 | 등장 14·CAPTION_PACKS 6·MOTION_PACKS 20 | `static/caption-motions.js` | 렌더러 HTML/JS에 포함 |
| 장면 효과 | 확대 3·흑백 충격·자동 배치 | scene_style | 렌더러에 포함 |
| 짤 | 서버 등록 1,283 | 크기 미확인 | 자산(대본 신호어가 고른 몇 장) |
| 에펙 견본 | 30 + 글자 프리셋 300 | D:\숏템\30_재료 | 1차 범위 밖 |

### 2-2. 설치팩 용량 — 실행도구 전부(윈도·맥 실측)

| 실행도구 | 윈도 x64 | 맥 arm64 | 맥 x64 | 근거(2026-10-18 HEAD/실측) |
|---|---|---|---|---|
| chrome-headless-shell 131.0.6778.204 zip | **105.8MB**(풀면 235MB 실측) | **87.8MB** | **91.5MB** | storage.googleapis.com/chrome-for-testing-public Content-Length / `~/.cache/puppeteer` |
| Node v24.15.0 | **36.5MB**(zip) | **51.5MB**(tar.gz) | 미실측 | nodejs.org/dist Content-Length. Desktop에 Node 내장이지만 Claude Code 경로 공유를 위해 포함 |
| ffmpeg+ffprobe | gyan essentials zip **114.8MB**(full 217MB 실측) | **미실측**(evermeet 410·martin-riedl 404) — 정적 빌드 둘 ≈80~120MB 추정 | 미실측 | gyan.dev Content-Length |
| Python 3.12.15 install_only(python-build-standalone 20261013) | **44.2MB** | **24.0MB** | **23.7MB** | GitHub API asset size |
| Pillow 15 + numpy 31 | 46MB | ≈46MB | ≈46MB | 실측 site-packages(윈도) |
| 로컬 MCP 서버 코드 + node_modules(puppeteer-core 8MB) | ≈10~15MB | 같음 | 같음 | `du` |
| (2차) onnxruntime 43MB + 얼굴·OCR 모델 | +≈120MB | +≈120MB | — | 실측·볼케이노 framevision 80MB |
| **설치팩 합계(1차, 압축 기준)** | **≈360~370MB** | **≈300~340MB** | **≈310~350MB** | 풀면 윈도 ≈600MB |

### 2-3. "이번 작업에 필요한 자산 목록" — 판단 주인 함수 하나

- **주인**: `shopping_shorts/claude_portal.py:assets_for(customer_id, profile_id, job_request) -> AssetPlan` — 라이선스·entitlement 확인 → `channel_profile.merge(preset, pack_defaults, options)` 합본 → 합본이 **실제로 참조하는** 글꼴 id·효과음 팩·곡·템플릿·짤 kinds·frame/rules 축약만 `{assets:[{id, kind, sha256, size, url(서명 6h)}], bundle:{…}, expires}`. 개별 `pack/<id>`도 **이 목록에 있어야** 서명 URL을 준다 → "통째로 안 준다"가 코드로 강제. script 단계 뒤 대본이 오면 신호어가 고른 **구체 짤·효과음 파일만** 추가 발급.
- 한 편 수신량: 첫 편 ≈15~35MB(글꼴 2~4종 10~30 + 효과음 <1 + 곡 1 + 짤 수 장 + 규격 수십 KB), 같은 프로필 다음 편 0~1MB.
- 로컬 캐시 `~/.shortem/cache/<sha256>`(내용주소) · 영수증 `~/.shortem/receipts/<sha>.json` · **30일 미사용 삭제·총량 2GB LRU(개정 4 C 확정)** · 라이선스 거절(해지·회수)이면 **다음 실행 때 캐시 삭제**.
- 저장소(개정 4 B 확정): 설치팩·원본 자산 = 객체 저장소(S3/R2) `assets/` 접두사 + 서명 URL 6h / 미리보기 견본 = `preview/` 접두사(§8-1, 서명 URL 아님). 우리 FastAPI는 발급만 하고 파일을 흘리지 않는다.
- 서버 검사: `assets_for` 응답의 자산 수 = 참조 수(참조 안 하는 글꼴·곡이 섞이면 테스트 실패).

---

## 3. 설치팩 — 설치 exe/pkg(실행도구 전부) + 얇은 연결 파일(.mcpb)/플러그인 (확정)

### 3-1. 규격 실측(2026-10-18 fetch)

| 항목 | 실측 | 출처 |
|---|---|---|
| .mcpb = zip(로컬 MCP 서버+manifest.json), stdio, "No OAuth required" | claude.com/docs/connectors/building/mcpb |
| Claude Desktop **Node 내장**("built-in Node.js environment") | support 10949351 |
| manifest_version 0.3 · server.type node/python/binary/uv · `mcp_config{command,args,env}` + `${__dirname}`·`${user_config.KEY}` · `user_config` sensitive "mask input and store securely"(키체인인지 **미확인**) · `compatibility.platforms` darwin/win32/linux | mcpb MANIFEST.md |
| 설치: 더블클릭 / 드래그 / Settings ▸ Extensions ▸ Advanced ▸ Install Extension… | claude.com/docs mcpb, support 10949351 |
| 서명 `mcpb sign --cert --key --intermediate`(PKCS#7 DER, zip 뒤 `MCPB_SIG_V1…END`), `mcpb verify`. Desktop이 신뢰에 쓰는지 **미확인** | mcpb CLI.md |
| 사설 배포는 **자동 갱신 없음**(디렉터리 등재분만 자동), 디렉터리 등재는 폐기 | support 10949351, claude.com/docs mcpb |
| 용량 한계 명시 없음 | CLI.md, MANIFEST.md |
| Claude Code 플러그인 `mcpServers`는 `.mcpb` 경로/URL도 받음 | code.claude.com/docs/en/plugins-reference |

### 3-2. 윈도 설치팩

```
shortem-setup-win-x64.exe (코드서명 — 구매 인증서, SmartScreen 평판)   ≈360~370MB
  %LOCALAPPDATA%\Shortem\tools\   node\ · chrome-headless-shell\ · ffmpeg\ · python\(+Pillow·numpy) · (2차) models\
  %LOCALAPPDATA%\Shortem\server\  index.js(MCP stdio) · engine\ · assets.js(서명 URL·영수증·캐시) · lease.js(§7-10)
  %LOCALAPPDATA%\Shortem\tools\tools.manifest.json   (구현 2026-10-18: tools\ 아래) 바이너리마다 sha256·버전 — 시작 때 대조, 틀리면 "설치팩 다시"
  끝: shortem.mcpb 실행(Claude Desktop 설치 UI) · Claude Code 있으면 플러그인 안내
shortem.mcpb (≈1MB, 등록·설정만)
  manifest.json  server.type "node" · entry_point launcher.js · mcp_config {command:"node", args:["${__dirname}/launcher.js"],
                 env:{SHORTEM_LICENSE:"${user_config.license_key}", SHORTEM_WORK:"${user_config.work_dir}"}}
                 user_config: license_key(sensitive, required) · work_dir(directory, default "${DESKTOP}/숏템작업")
                 compatibility {platforms:["win32","darwin"], runtimes:{node:">=20"}} · tools 6개 · icon.png
  launcher.js    설치 폴더의 server\index.js 실행(없으면 "설치팩을 먼저 까세요" 도구 1개만)
```
- 왜 fat .mcpb가 아닌가(확정 근거): MCPB 용량 한계 미확인·Claude Code엔 .mcpb 설치 UI 없음·바이너리 갱신을 .mcpb 재설치 없이. 볼케이노도 exe(코드서명, handoff:11).
- Claude Code: 플러그인 `shortem` plugin.json `"mcpServers": {"shortem": {"command": "node", "args": ["<설치 폴더>/server/index.js"]}}` + skills(§4-3). 또는 `claude mcp add shortem -s user -- node <경로>/server/index.js`. 서버 코드는 하나.
- 업데이트: 엔진(server\engine\)만 서명(ed25519)+sha256 둘 다 맞을 때 자가 갱신(실패 시 교체 안 함 — volcano_run.py:655-680 규율). 실행도구·.mcpb는 새 설치팩(시작 때 `min_installer` 비교해 안내). `shortem_setup`은 다운로드 없음 — **있는지·sha가 맞는지 확인만**.

### 3-3. 고객이 하는 일

| 환경 | 단계 |
|---|---|
| Claude Desktop(윈도·맥) | ① 숏템메이커 로그인 → '클로드형' 페이지에서 프리셋 고르고 **내 채널 옵션 저장** → 라이선스 키 복사 → 설치팩 내려받기(OS 자동 선택) ② 설치팩 실행(실행도구 전부, 끝에 Claude Desktop 설치 UI) → 라이선스 키 붙여넣기 → **이 기기 등록**(2대 중 1) ③ 채팅 "숏템 준비 점검해줘"(`shortem_setup`: 도구 sha·라이선스·키 파일 안내) ④ "내 채널(프로필)로 이 영상 만들어줘" → 이번 편 자산 자동 수신 → 소재·대본·최종 확인 3번 |
| Claude Code | ① 같은 페이지(그림 안내 HTML 11장 안팎 — §3-5에서 배움) ② 같은 설치팩 ③ 설치 폴더의 `시작.md`(내용: "/shortem:setup 을 실행하세요" 한 줄 — 입구일 뿐 지시문 아님)를 Claude Code 입력창에 **드래그+엔터 1회** → 플러그인 등록(`/plugin install shortem` 또는 `claude mcp add`) → `/shortem:setup`이 키를 물어 `~/.shortem/`에 저장·기기 등록·자가점검 3종 ④ `/shortem:make <프로필> <소재>` |
| 두 번째 기기 | 같은 설치팩을 **그 기기에도** 깔고 같은 라이선스 키로 등록(2대째). 3대째는 거절(마이페이지에서 기기 교체) |

### 3-4. 맥 1차 지원(확정)

| 항목 | 설계 | 근거·미확인 |
|---|---|---|
| 아키텍처 | **arm64·x64 두 pkg**(universal은 Chromium·ffmpeg가 각각 바이너리라 합치면 ≈2배 → 분리) — 페이지가 `navigator`/다운로드 안내로 고르게 하고, launcher가 `process.arch`로 재확인 | 크기 §2-2 |
| 패키지 | `shortem-setup-mac-arm64.pkg`(Developer ID **Installer** 인증서로 pkg 서명) 안의 모든 실행 파일(node·chrome-headless-shell·ffmpeg·ffprobe·python·.dylib·server)은 Developer ID **Application** 인증서 + **hardened runtime**(`--options=runtime`) + 타임스탬프로 **inside-out 개별 서명** 후 `notarytool`로 **공증**(notarization) → 스테이플 | developer.apple.com "Notarizing macOS software before distribution"·"Resolving common notarization issues"(hardened runtime 없으면 실패) · 2026 GitHub PR 사례: 중첩 바이너리 하나라도 빠지면 거절 |
| Gatekeeper | 공증 안 되면 "확인되지 않은 개발자" 차단. Chromium은 자체 서명본이라 **재서명 때 entitlements**(`com.apple.security.cs.allow-jit`, `allow-unsigned-executable-memory`, `disable-library-validation`) 필요 — Electron/puppeteer 배포 선례. 정확한 entitlement 집합은 **미확인**(1호 맥 빌드에서 실측) | — |
| 설치 경로 | 실행도구·서버 = `~/Library/Application Support/Shortem/`(사용자 단위, 관리자 암호 불필요·샌드박스 밖) · 사용자 데이터(캐시·키·영수증·작업) = `~/.shortem/`(윈도와 **같은 이름** → 서버 코드 경로 분기 1곳) · 작업 폴더 기본 `~/Desktop/숏템작업` | 숏템 코드 한 벌 |
| Node | Desktop 내장이지만 Claude Code 경로 공유를 위해 pkg에 포함(51.5MB) | nodejs.org |
| Python | python-build-standalone darwin install_only 24.0MB | GitHub API |
| ffmpeg 맥 빌드(F **확정**) | **libass 포함 정적 ffmpeg·ffprobe를 우리가 직접 빌드**(arm64·x64 각각) → Developer ID 서명·hardened runtime·공증 → 설치팩 동봉. 외부 미러(evermeet.cx 410 Gone·martin-riedl 404 실측) 의존 0, Homebrew 의존 0. 자가점검(§4-2)에 **`ffmpeg -version` 첫 줄 + `ffmpeg -filters`에 ` ass ` 필터 유무** 확인을 넣는다(없으면 자막 굽기 단계에서 멈추므로 설치 직후에 잡는다) | 근거 = 볼케이노 setup 응답 실측(조율자, 이번 세션, env_probe 코드는 실행 안 함): 볼케이노는 ffmpeg를 **동봉·설치하지 않는다** — env_probe가 `shutil.which('ffmpeg')`로 찾고 `-version` 첫 줄과 `-filters`의 ` ass `(libass) 유무만 잰다. 파이썬은 `~/.volcano/venv`(맥 externally-managed라 venv 강제), 키는 `~/.volcano/keys/<이름>` 또는 환경변수를 14종 키표로 file/env/short/invalid만 보고, 채널 34개(프반 전용 10). 즉 볼케이노 맥 고객은 ffmpeg를 **스스로 설치**해야 한다(Homebrew) — 우리가 동봉으로 이기는 지점. 빌드 크기는 1호 빌드에서 실측(미확인) |
| 로드맵 | 맥 테스트 기기 **2대**(Apple Silicon 1·Intel 1) 확보 + Apple Developer Program(연 99달러) + 공증 API 키 → 단계 0 포함 | — |

금지(공통): `--dangerously-skip-permissions`·tasks.json 자동 실행·플러그인 `bin/`(claude.ai·Cowork 설치 거부).

### 3-5. 비교: 쇼츠AI 스타터킷(경쟁 킷, 조율자가 이번 세션에 실물을 읽음 — 실행 안 함)

`쇼츠AI_스타터킷_v1_Windows.zip`(48MB, 맥판 별도)은 **프로그램이 아니라 "Claude Code에게 주는 지침+재료" 폴더**다. 고객이 하는 일 = `①_먼저_보세요.html`(11장 그림 안내) 읽기 → `②_이_파일을_Claude_Code에_끌어다_놓고_엔터.md`를 Claude Code 입력창에 드래그+엔터. 그 md가 Claude에게 시키는 것: 킷 찾기→바탕화면 이동→`.claude/CLAUDE.md`(22KB, 사용조건·온보딩 1~7·진행 리드 대본·절대 규칙) 읽기→`엔진/설치.bat`(winget으로 Python 3.12·Gyan.FFmpeg·yt-dlp 무음 설치→.venv→pip numpy·pillow·scipy·faster-whisper·av, 선택 demucs+torch 2GB; 맥은 설치.sh+Homebrew, 터미널 비번)→`set_key.py --open`(메모장으로 키 파일, `~/.config/typecast/api_key` 0600, `--check`로 값 비출력 확인)→`paths.py`→`selftest.py`(시험_렌더.mp4·시험_목소리.wav·시험_다운로드.mp4·자가점검_결과.md)→예시 3문장.

| 항목 | 쇼츠AI 스타터킷 | 우리(개정 3) | 판정 |
|---|---|---|---|
| 설치 방식 | winget/Homebrew로 런타임을 **그 자리에서 내려받음**, 고객이 "명령 실행 허용·작업 공간 신뢰·UAC 예"를 손으로 클릭, 첫 설치 10~30분·수 GB·디스크 10GB | 서명된 exe/pkg에 실행도구 **전부 포함**(≈360MB), 클릭 1~2회, winget·Homebrew·pip 의존 0 | **우리가 이김** — 볼케이노 사고(분류기 차단·셋업 재작업)와 같은 종류의 실패를 그들은 고객 손에 맡겼다 |
| 권한 | settings.json·훅·skip-permissions 없음(좋음) — 대신 Claude가 bat·pip를 돌리는 것을 고객이 매번 허용 | 같음(금지) + 실행은 **MCP 서버 프로세스 안**이라 Bash 허용 프롬프트가 설치 뒤엔 없음 | 동급 이상 |
| 온보딩 UX | **그림 안내 HTML 11장 + "md 한 장 드래그" 한 번** | 1~2판엔 없었음 → **채택**: 페이지에 그림 안내(설치→키→첫 편 11장 안팎) + Claude Code용 `시작.md` 1장(내용은 "/shortem:setup 실행" 뿐 — 지시문이 아니라 입구) | **배운다** |
| 자가점검 산출물 | `selftest.py` → 시험_렌더.mp4·시험_목소리.wav·시험_다운로드.mp4·자가점검_결과.md | `shortem_setup`에 **같은 3종 추가**: 시험 렌더(프리셋 없는 기본 틀 3초)·시험 목소리(고객 키로 1문장, 비용 최소)·시험 다운로드(공개 영상 5초) + 결과 md. 돈 나가기 전 실측(볼케이노 원리 3행과 같다) | **배운다** |
| 자산·노하우 | **전부 평문 동봉**: 스타일 카드 3종(대본_프롬프트.md 18KB·스타일.json·레퍼런스_정량분석.md)·엔진 파이썬 소스 전부·효과음 ~60·Pretendard 6종·템플릿 PNG 5·예시 영상 3편 | 필요분만 서명 URL·원값 제외·고객 지문·작업 후 삭제(§7-4) | **반대로 간다** — 그들 킷은 복사 한 번이면 끝. 우리가 라이선스·동시 1·탐지를 두는 근거 |
| 라이선스·서버·업데이트·기기 제한·모니터링 | **전부 없음**(zip 한 번 팔면 끝) | 라이선스 키·기기 2·lease·엔진 자가 갱신·탐지 A1~A9 | 우리가 운영 가능한 상품, 그들은 1회 판매물 |
| 키 저장 | 홈 파일 0600(`~/.config/typecast/api_key`), 값 비출력 `--check` | `~/.shortem/keys/<서비스>` 0600 + 지문 12자 — **같은 수준**. 우리는 MCPB `user_config sensitive`가 OS 키체인인지 추가 확인(미확인 1번) | 동급, 확인 뒤 상향 가능 |
| 지원 환경 | Claude Code 탭/CLI 필수·유료 플랜 필수, **Claude Desktop(채팅) 미지원** | Desktop(.mcpb)·Code 둘 다 | **우리가 이김** |
| 다운로드 정당화 | CLAUDE.md 사용조건에 문구를 넣어 Claude가 yt-dlp를 되묻지 않게 함 | 다운로드는 MCP 서버 프로세스가 하므로 모델이 되물을 일이 없다. 도구 description에 "본인 채널 제작용 재료 수집" 한 줄만 | 구조로 해결 |
| 진행 표시 | CLAUDE.md "진행 리드 대본"으로 Claude가 단계를 말로 안내 | `progress`+`steps` 고정 9단계(§4-4) | 동급(우리는 규격 비노출까지) |

반영한 것(이 개정에서 추가): ① §3-3 고객 단계에 **그림 안내 HTML + 시작.md 드래그 1회**를 넣는다(Code 경로) ② `shortem_setup`이 **시험 렌더·시험 목소리·시험 다운로드 + 자가점검_결과.md**를 만든다(§4-2 도구 표에 추가, 실패 문구는 `{where,why,fix,retry_ok}`) ③ 로드맵 0 '됐다'에 "자가점검 3종 전부 생성" 추가. 바꾸지 않은 것: 평문 동봉·winget 의존·라이선스 없음은 따라가지 않는다.

---

## 4. MCP 도구(명령어팩) — 전부 로컬 실행, 범위 고정

### 4-1. 도구 수 근거
볼케이노 2개(+step)로 12단계. 도구가 적을수록 순서를 엔진이 강제. Desktop은 도구마다 승인 프롬프트(support 11175166) → 세분화 반대. 상태는 `job_id` handle(MCP 2026-07-28 Tools "Stateful Tools"). 쓰기는 작업 폴더·`~/.shortem/` 안만. 셸 실행 도구 없음.

### 4-2. 도구 표

| 도구 | 인자 | 하는 일(로컬) | annotations | 사람 자리 |
|---|---|---|---|---|
| `shortem_setup` | `{selftest?: true}` | 라이선스·기기 등록 확인 · 실행도구 sha 대조(다운로드 없음) · 키 파일 유무(지문만) · 디스크 여유 · 프로필 목록 캐시 · **자가점검 3종**(§3-5에서 배움): `시험_렌더.mp4`(기본 틀 3초)·`시험_목소리.wav`(고객 키 1문장)·`시험_다운로드.mp4`(공개 영상 5초) + `자가점검_결과.md` · **ffmpeg 점검**: 동봉 ffmpeg의 `-version` 첫 줄 기록 + `-filters`에 ` ass `(libass) 필터 있음 확인(볼케이노 env_probe와 같은 자, 없으면 `fail{where:"ffmpeg", fix:"설치팩 다시"}`) — 실패는 `{where,why,fix,retry_ok}` | readOnlyHint=false(캐시·시험 파일), destructive=false, idempotent=true, openWorld=true | 없음 |
| `shortem_presets` | `{refresh?}` | 캐시된 프리셋·프로필 카드(이름·설명·예시 URL) | readOnly=true | 없음 |
| `shortem_profile` | `{profile_id}` | 프로필 **조회만**(저장·수정은 웹 페이지 §9) | readOnly=true | 없음 |
| **`shortem_make`** | `{step, job_id?, profile_id?, source?, payload?}` | 로컬 상태기계 `setup→source_pick(○)→analyze→script(○, 방향 힌트 반려 루프)→plan(선검수 승인)→voice→render→check→review(○)→done`. 시작 때 **임대 취득**, 끝·실패 때 반납(§7-10) | readOnly=false, destructive=false, idempotent=true(job_id+step), openWorld=true | **3곳** |
| `shortem_job` | `{action: status\|list\|cancel, job_id?}` | 진행(단계 이름·순번)·완성본 **로컬 경로**·검사 통과/미달. **상세 열기 기능 없음**(개정 3 ⑦) | status/list readOnly; cancel destructive=true | 없음 |
| `shortem_feedback` | `{kind: request\|bug, text, job_id?}` | `/api/claude/feedback` POST | readOnly=false, destructive=false | 없음 |

`shortem_make` 반환: `{job_id, progress:{no:4, total:9, name:"장면 계획", status: working|need_input|done|failed}, steps:["소재","분석","대본","장면 계획","음성","렌더","검사","확인","완료"], need?, hints?, fail?}`. 상태·payload·규격은 `<작업폴더>/jobs/<job_id>/state.json`에만 — 모델엔 handle만(볼케이노의 `next_payload` 되돌리기·"한 글자 다르면 반려"·`fold_payload`가 필요 없어진다). `check` 미달이면 final 안 만들고 `out/FAILED.json`(`review.content_gate` 규율, handoff/칼카피숏템엔진.md:75).

### 4-3. 슬래시 명령·스킬 팩(Claude Code 플러그인 `shortem`)
```
shortem/.claude-plugin/plugin.json  {"name":"shortem","version":"1.0.0","mcpServers":{"shortem":{"command":"node","args":["<설치 폴더>/server/index.js"]}}}
shortem/skills/make/SKILL.md        /shortem:make <프로필> <소재> — step 순서·사람 자리 3곳. allowed-tools: 우리 도구 6개만
shortem/skills/setup/SKILL.md       /shortem:setup — 라이선스·기기·도구·키 점검
shortem/skills/script/SKILL.md      대본 쓰기 지침(숫자 없는 문장만)
```
도구 이름은 플러그인 번들이면 `mcp__plugin_shortem_shortem__shortem_make`(code.claude.com/docs/en/mcp). Desktop엔 스킬이 없으니 도구 description + `hints[]`가 절차를 안내.

### 4-4. 진행 표시 — "실행 순서만", 응답 두 겹, 상세 보기 없음

| 겹 | 누가 보나 | 들어가는 것 | 안 들어가는 것 |
|---|---|---|---|
| `progress`+`steps` | 고객·모델 | 단계 이름 9개 고정, 지금 몇 번째, 상태, 걸린 시간 | 단계 안에서 무엇을 어떻게(컷 수·좌표·공식·명령) |
| `need` | 사람 자리 3곳 | ① 소재 후보 5개(제목·링크·한 줄) ② 대본: 칸 수·칸 역할 이름("상황/반전/감동/반응/덤")·길이 등급("짧게/보통") ③ 확인: 완성본 경로·통과/미달 | 규칙표·글자수 공식·노출 초 공식·frame 값·verdict 수치 |
| `hints`(반려) | 모델 | **고칠 방향만**: "3번 줄 더 짧게"·"존댓말을 반말로"·"마지막 줄 단정문으로"·"숫자에 근거가 없다 — 빼거나 출처" | 규칙 원문·임계값·규칙 id |
| `fail` | 모델·고객 | where(단계명)·why 한 문장·fix·retry_ok | 스택·명령줄·작업 폴더 밖 경로 |
| job 파일(로컬) | 엔진만 | 전부 | — |

- 수렴 근거: 볼케이노 2편째 반려 0·3편째 1(handoff:76, :105). 5회 안 수렴하면 `fail{fix:"칸 N을 직접 써 주세요"}`.
- **상세 보기 기능은 없다**(개정 3 ⑦): 2판의 `shortem_job open`(시트·계획.md 열기) 제거. 고객이 볼 수 있는 산출물은 완성본 mp4와 "통과/미달" 한 줄뿐. 계획 시트·verdict 숫자·state.json은 작업 폴더 `jobs/`에 남지만 도구가 열어주지 않는다(파일 탐색기로 직접 여는 것까지는 못 막는다 — §7-4).
- 노하우 보호 기여: 규격·임계값이 모델 컨텍스트·채팅 로그에 **한 번도 안 나타남**(볼케이노식 역분석 통로 차단) · payload가 모델을 안 거침 · 모델 왕복 짧음(볼케이노 124~275초 중 상당수가 JSON 읽기).

---

## 5. 서버 REST 5개 — 원격 MCP 없음

| 라우트 | 하는 일 | 제작 호출? |
|---|---|---|
| `GET /api/claude/license` | 라이선스 키 검증·기기 지문 등록/확인·회수 여부·entitlement | 아니오(권한 확인) |
| `POST /api/claude/lease` | `{action: acquire\|heartbeat\|release, device, job_id}` — 한 라이선스 **동시 실행 1**(§7-10) | 아니오(권한 확인) |
| `GET /api/claude/assets?profile=&job=` | `assets_for` 결과 + 서명 URL 6h | 아니오(내려주기) |
| `GET /api/claude/pack/<id>` | 목록 안 자산만 서명 URL 재발급 | 아니오 |
| `POST /api/claude/feedback` | 요청·버그 | 아니오 |
구현: 기존 FastAPI `_AUTH_ALLOW`(app.py:13624)에 공개 경로 추가 + 라우트가 라이선스 키 직접 검사(`/api/kakao/ask`의 `X-Bot-Secret` 선례 :13660-13663). 요청은 **고객 PC에서** 오므로 IP·기기 지문 기반 탐지(§7-9)가 된다(원격 커넥터였다면 Anthropic 클라우드에서 와서 불가능).

---

## 6. 품질(고퀄) — 고객 PC에서 도는 결과물 검사(서버 보고 없음)

| 관문(기존 자산) | 지금 어디 | 고객 PC 판 |
|---|---|---|
| 선검수(렌더·TTS 전 계획) — "반려·TTS 비용을 줄였다" | handoff/칼카피숏템엔진.md:261 | `plan` 단계: 고객이 승인해야 TTS(고객 키 비용 보호). 시트는 안 보여주고 "장면 N개 계획됨 — 진행할까요"만 |
| 대본 규칙표 판정 | `script_engine`·`style_writer.copied_from`(:311) | `script` 로컬 린터 → 방향 힌트만 |
| 내용 하드 게이트(얼굴 ≥55%·자막꼴 ≤1·장면 틀림 ≤30%) | `review.content_gate`(:71-75) | 2차(onnxruntime). 1차: 줄↔장면 표 일치·자막 안 컷·컷 수≤자막 수(:59) |
| 규칙표 compare(LUFS·말속도·컷 중앙·자막 자수) | `engine/compare.py`(:210) | `check`: ffmpeg ebur128·ffprobe·자수·컷 중앙 → `verdict.json`(기준 밖 FAILED) — **서버로 안 보냄**(개정 3 ④) |
| 세 길 대조(편집기·렌더·캡컷) | `editor_vs_final_video.py`(:294) | 개발 때 내부 1호 채널에서(라이브 제작소 mp4와 프레임 대조) |
| 원음 깔기+덕킹 | `video_assemble.source_audio_bed`(:202-205) | 렌더 경로에 포함 |
| 사실 검증 | 담당_공통규칙.md:22 | 린터 "근거 없는 숫자" + 지시 블록 |
볼케이노에 없는 것 = 선검수·내용 관문·compare·원음 덕킹·사실 검증 → 전부 로컬 엔진.

---

## 7. 보안

### 7-1. 서버 기존 자산 중 쓰는 것/안 쓰는 것
쓴다: 회원 `customers`(store.py:1013-1023)·구글 로그인(app.py:15853) → 페이지 로그인 / 기기 2칸 `customer_devices`(store.py:1852-1864, :7192-7200) 규율 → 라이선스 기기 2 / `_setting_gate`(app.py:16896) → 킬스위치.
안 쓴다: `customer_keys`·`keyroute`·Fernet(고객 키 서버 미보관) / `pull_pool_keys.py`(회원 풀 키를 PC로 — 고객 경로 금지) / `live_admin.admin_cookie`(운영 전용).

### 7-2. 라이선스 키
`SHORTEM-L1.<cid>.<만료>.<HMAC(cid|exp|kv)>` 무상태 + 회수 목록. 재발급 = kv+1(옛 키 즉시 무효). 서버는 해시만 저장. entitlement = 구매한 프리셋 목록 → `assets_for`는 목록 안만. 만료·해지 → `license` 거절 → 로컬은 새 자산·엔진 갱신 중단 + 다음 실행 때 캐시 삭제.

### 7-3. 고객 API 키(개정 4 A **확정**)
`~/.shortem/keys/<서비스>` 값만·0600(볼케이노 방식, 쇼츠AI 킷과 동급) — Desktop·Code 두 경로가 같은 파일. 로그 지문 12자만(volcano_drive.py:1044), 셸 인자 금지(handoff:140), 작업 폴더에 복사 금지(볼케이노 08-16 공유 사고). 우리 서버는 **받지도 저장하지도 않는다**(카드 213 "고객 키 서버 보관"은 웹형만).

### 7-4. 노하우 — "최소한으로 노출 제한"(확정) 체크리스트

**사실**: 고객 PC에서 렌더하려면 그 편의 frame·rules가 그 PC에 있어야 하고, 암호화해도 복호 키가 같은 PC에 있어 **완전 방지 불가**. 아래는 "최소한"의 정의.

| 자리 | 체크 | 검사 |
|---|---|---|
| **응답(모델·채팅)** | □ `shortem_make`·`shortem_job` 응답에 frame·rules·payload·임계값 숫자·규칙 id·공식 0개 □ 반려는 방향 문장만 □ `need`는 사람 자리 최소 정보(§4-4) □ 상세 보기 도구 없음 □ 도구 description 고정 문자열(규격 미포함) | 응답 스키마 테스트(금지 키·숫자 패턴 grep) + 1호 채널 채팅 로그 전수 grep 0건 |
| **자산 전송** | □ `assets_for`가 이번 편 참조분만 □ sources/·variable_stats·bench 원값·분석 .md 안 보냄 □ 서명 URL 6h·1 URL 1 파일 □ 목록 밖 `pack/<id>` 거절 | 자산 수 = 참조 수 테스트 |
| **캐시(`~/.shortem/cache`)** | □ 내용주소 저장(파일명에 프리셋 이름 없음) □ 30일 미사용 삭제·2GB LRU □ 해지·회수 시 다음 실행 때 삭제 □ 캐시 안 frame 축약본에 **고객 지문**(cid·발급시각: manifest `license` 필드 + 렌더 차이 없는 ±1px 지터) | 캐시 디렉터리 검사 도구 |
| **작업 파일(`jobs/<id>/state.json`)** | □ 작업 끝나면 규격 부분(frame·rules)은 **삭제**하고 결과 요약(단계·통과·경로)만 남김 □ 완성본 메타데이터 comment에 묶음 id(유출본 식별) □ 작업 폴더에 키 복사 0 | 완료 후 state.json에 frame 키 0개 테스트 |
| **로그(`~/.shortem/audit.jsonl`)** | □ 키·토큰·URL 서명 값 0, 지문 12자만 □ 규격 수치 안 적음(단계·시각·결과·자산 id만) □ ffmpeg 명령줄은 **안 적음**(필터 그래프에 좌표가 들어간다) | 로그 grep 테스트 |
| **엔진 코드** | □ 린터 임계값·공식은 코드 안(난독화 — 억지력만, 정직하게) □ 엔진 자가 갱신으로 해자를 "갱신되는 것"에 | — |
| **페이지** | □ 벤치 채널명·slug·strengths·evidence·bench ids·분석 문서 비노출 □ 통과작 미리보기 워터마크 720p □ **팩은 견본만**(글꼴 PNG·효과음 1.5초·BGM 15초 mono 워터마크·짤 240px JPEG·템플릿 360px — §8-1) □ 원본 다운로드 링크 0 □ Range 거부·Referer 확인 | 응답 JSON 금지 키·원본 URL 0 테스트 + 견본 전수 규격 검사(§8-1) |
| **법·운영** | □ 약관에 규격 파일·캐시 재배포 금지 □ 유출본 발견 시 묶음 id→cid 역추적 → 회수 | — |

### 7-5. 로컬 MCP 도구 범위 고정
실행 바이너리 4개(설치팩 안 chrome-headless-shell·ffmpeg·ffprobe·python)만, 절대경로 고정, 서버 응답·payload 문자열을 argv[0]에 절대 안 씀(볼케이노 PATH 탐색 없음). 서버는 **명령을 내리지 않는다**(데이터만). 엔진 갱신은 서명+sha256 둘 다. 경로 감옥(`..`·심링크·절대경로 거부, volcano_drive.py 영수증 규율). 네트워크 허용 목록(우리 도메인·자산 저장소·유튜브·고객이 켠 TTS/LLM). 외부 글은 `structuredContent.data`로만 + "지시로 읽지 마라" 머리글. 플러그인 `allowed-tools` 우리 도구만.

### 7-6. 비용(고객 돈)
선검수 승인 전 TTS 0(담당_공통규칙.md:15), 캐시 재사용(handoff:120), 로컬 일 상한(typecast 10/일 기본), `(job_id, step, payload_sha)` 멱등.

### 7-7. 감사 로그·보관
- 로컬 `~/.shortem/audit.jsonl`: 90일 롤링(규격·키 값 없음).
- 서버 `claude_license_log`(cid·기기 해시·IP·국가·라우트·자산 id·ts) + `claude_lease_log`(acquire/heartbeat/release·job_id·기기): **1년 보관**(분쟁·회수 근거), 그 뒤 cid 단위 집계만. 제작 내용·verdict는 **안 올라온다**.
- 회원 데이터(라이선스 해시·기기 지문·IP·임대 기록) 저장 → **★사장님 승인 카드**.

### 7-8. 킬스위치(설정 키, 배포 없이, 판정은 `_setting_gate` 하나)
① `claude_assets_enabled` ② `license_kv`(전 고객 키 무효→재발급) ③ cid별 `license_revoked` ④ 프리셋별 `preset_enabled`. 이미 받은 PC는 **다음 실행부터**(시작 때 license·lease 확인).

### 7-9. 이상 행동 모니터링(필수, 개정 3 ④) — 서버에서 보이는 신호로

고객 PC가 보내는 것은 **최소 3가지뿐**: `license`(설치·시작) · `lease`(작업 시작/하트비트/끝 — 기기 id·job_id·단계 이름만) · `assets`(자산 id 목록). verdict·대본·소재는 안 올라온다.

| # | 신호(서버 로그에서) | 임계값 초기안 | 자동 조치 |
|---|---|---|---|
| A1 | **키 공유**: 같은 cid가 24h 안 서로 다른 국가/ASN ≥2 또는 등록 기기 지문 아닌 기기에서 `license` | 국가 2↑ 또는 미등록 지문 1회 | 경고(마이페이지·텔레그램) → 2회째 **일시 정지**(lease 거절) + 관리자 경보 |
| A2 | **동시 실행 시도**: lease 보유 중 다른 기기 acquire | 1회 | 거절(§7-10) + 24h 안 5회면 경고, 10회면 정지 |
| A3 | **긁어가기**: `assets` 요청 자산 수 / 완료된 job 수(release) 비율 | 7일 비율 > 3 또는 하루 자산 요청 > 200 | 속도 제한(분당 10) → 하루 지속 시 정지 + 경보 |
| A4 | **짧은 시간 대량 요청**: 어느 라우트든 cid당(미리보기 `preview` 포함) | 분당 60 / 시간당 600 | 429 속도 제한, 3회 반복 시 1h 정지 |
| A5 | **고른 프리셋 밖 자산 요청**: `pack/<id>`가 `assets_for` 목록·entitlement 밖 | 1회 | 거절+기록, 10회/일이면 정지 + 경보(정상 클라이언트는 0회여야 한다) |
| A6 | **회수된 키 사용**: `license_revoked`·옛 kv 키로 요청 | 1회 | 거절, 24h 안 3회면 경보(유출 키 추적) |
| A7 | **하트비트 없는 긴 lease**·비정상 종료 반복 | 하루 3회 만료 | 경고(설치 문제 안내), 7일 지속 경보 |
| A8 | **엔진 버전 위조**: `min_engine` 미만·알 수 없는 서명 버전 헤더 | 1회 | 자산 거절 + "갱신하세요" |
| A9 | **계정당 기기 교체 빈도**: 마이페이지 기기 교체 | 30일 3회↑ | 경고, 5회↑ 관리자 경보(승인 뒤 교체) |
| A10 | **미리보기 긁어가기**(§8-1): 24h 견본 요청 수 / 짤·BGM·효과음 전수 순차 요청 / Range·Referer 밖 요청 | 500개↑ 또는 전수 순차 1회 / Range·Referer 밖 10회/일 | 속도 제한 → 지속 시 정지 + 경보 |

- 판정 주인: `shopping_shorts/claude_portal.py:anomaly_check(cid, event)` 하나 — 라우트 5개 + 미리보기 라우트가 이벤트를 넣고 결과(allow·throttle·deny·alert)를 받는다. 임계값은 **설정 키**(배포 없이 조정).
- 관리자 화면: 기존 관제 보드 `관제/BOARD.md`·`/admin` '결정할 것' 옆에 **"클로드형 경보"** 칸(cid·신호·횟수·마지막 시각·조치·해제 버튼) + 텔레그램(`notify.send_telegram` 선례 app.py:15757). 매시간 `live_check.py --all`에 "경보 미처리 수"를 지표로 추가.
- 거짓 양성 대비: VPN 사용자(A1)·노트북 들고 다니는 고객(국가 2↑)은 **경고 먼저, 정지는 2회째** — 정지는 사람이 풀 수 있게.
- 임계값 초기안 **확정**(개정 4 D) — 베타 1주 로그로 거짓 양성률을 재서 조정. 값은 설정 키라 배포 없이 바꾼다.

### 7-10. 기기 2대·각 기기 설치·동시 실행 1 — 임대(lease)·하트비트

| 항목 | 설계 |
|---|---|
| 기기 등록 | 라이선스 1 = 기기 지문 2(해시). 지문 = OS machine id(`MachineGuid`/`IOPlatformUUID`)+사용자명 sha256. 3대째는 거절 → 마이페이지에서 교체(자동 교체 금지, store.py 2026-08-31 규율). **각 기기에 설치팩+MCP가 있어야** 한다(지문은 그 기기의 로컬 서버가 만든다) |
| 임대 | `shortem_make` 시작(step=setup)에서 `POST /api/claude/lease {acquire, device, job_id}` → 서버가 cid당 **활성 lease 1개**만 발급(`lease_id`, TTL **3분**) |
| 하트비트 | 로컬 서버가 **60초마다** `{heartbeat, lease_id, step_name}` — 단계 이름만(규격·대본 없음) |
| 다른 기기에서 시작 | **거절**(앞 기기 안 끊음 — 개정 4 E 확정): "다른 기기(이름)에서 작업 중 — 끝나거나 3분 뒤 다시". 이유: 렌더 도중 끊으면 그 기기 작업이 깨진다. 사용자가 원하면 마이페이지 "강제 해제"(앞 기기는 다음 하트비트에서 `lease_lost` → 그 단계에서 멈추고 state 저장 → 재개 가능) |
| 오프라인·크래시 | 하트비트가 끊기면 **3분(TTL) 뒤 자동 만료** → 다른 기기 가능. 로컬은 state.json이 남아 같은 기기에서 `{step, job_id}`로 재개(재개 때 lease 다시 취득) |
| 렌더 도중 네트워크 끊김 | 렌더 자체는 로컬이라 **계속 돈다**(제작은 서버 무관). 하트비트 실패 3회(3분)면 로컬도 lease 만료로 보고 **현재 단계까지만** 끝내고 멈춤(다음 단계 진입 때 acquire 재시도). 완성 직전 끊김이면 render는 끝내고 check·done은 재취득 뒤 |
| 제작 호출 0건과의 관계 | lease는 "지금 이 라이선스로 돌려도 되나"의 **권한 확인**이다. 서버는 대본·재료·렌더 어느 것도 받지도 돌리지도 않는다 → 카드 079 "숏템 서버 제작 호출 0건" 유지. 로그에도 단계 이름·시각만 |
| 판정 주인 | `claude_portal.py:lease(cid, device, action, job_id)` 하나(TTL·동시 1·강제 해제). 로컬 `lease.js`는 부르기만 |
| 검사 | 두 기기에서 동시에 시작 → 두 번째 거절 1건 / 하트비트 끊고 3분 뒤 두 번째 성공 / 강제 해제 뒤 첫 기기 `lease_lost`로 멈춤·재개 성공 — 전부 라이브 실측 |

### 7-11. 위협 모델 표(개정 3)

| 위협 | 영향 | 막는 법 | 한계 |
|---|---|---|---|
| 프리셋 규격 유출(frame·rules) | 채널 복제 | 필요분만·원값 제외·고객 지문·작업 후 삭제·캐시 수명·해지 시 삭제·응답 0·해자를 갱신에 | **완전 방지 불가** |
| 라이선스 키 공유 | 무단 사용 | 기기 2·지문·동시 1(lease)·A1/A2 탐지·kv 재발급 | VM 지문 위조 |
| 자산 긁어가기(원본) | 자산 유출 | assets_for 참조분만·목록 밖 거절·A3/A5 탐지·속도 제한 | 정상 사용 범위 안 누적 |
| 미리보기 긁어가기(견본) | 견본 수집 | 견본 규격(저해상도·mono·워터마크·짧음)·Range 거부·세션 토큰 10분·A4/A10 | 화면 캡처·녹음은 못 막음(견본은 제작에 못 씀) |
| 회수된 키 재사용 | 해지 뒤 사용 | 회수 목록·A6·다음 실행 캐시 삭제 | 오프라인 PC |
| 엔진 갱신 팩 위조 | 고객 PC 임의 코드 | 서명+sha256·실패 시 교체 안 함·A8 | 서명 키 관리 |
| 서버 응답으로 임의 명령 | PC 침해 | 명령 채널 없음·바이너리 4개 고정·경로 감옥 | — |
| 간접 인젝션(유튜브·댓글·기사) | 대본 오염 | data 분리·머리글·베낌 검사·사람 자리 3 | 모델 판단 |
| 고객 API 키 유출 | 고객 돈 | PC 홈 0600·지문만·셸 인자 금지 | PC 침해 |
| TTS 비용 폭주 | 고객 돈 | 선검수 승인 뒤 1회·일 상한·캐시 | — |
| 설치팩 위변조(중간자·미러) | 악성 설치 | 코드서명(윈도)·Developer ID+공증(맥)·페이지에 sha256 표시 | — |
| 트래픽 폭증 | 송신 비용 | 객체 저장소+서명 URL·A4 | 월 한도 미확인 |
| auto 분류기 차단(볼케이노 사고) | 설치 실패 | 다운로드·실행을 MCP 서버 프로세스 안에서 | 미실측 |
| 운영 도구 오용 | 전권 | 클로드형 라우트에서 import 금지 | — |
| 사고 시 중단 | 확산 | 스위치 4개 + lease 거절 | 받은 PC는 다음 실행부터 |

---

## 8. '클로드형 가입자' 페이지(`/claude`)

| 항목 | 관리자 `/shortem_preset`(`calcopy_board.preset_home`:312) | 고객 `/claude` |
|---|---|---|
| 판단 주인 | `preset_home` | 같은 함수 + `for_customer=True` |
| 브랜드 | slug·bench·old_names | **우리 브랜드 이름만**(관제 066 선례) |
| 스타일 | desc·why·strengths·bench·judge | desc·example·audio_kinds |
| 결과물 | 26건+path·commit·rules | 통과 15건 미리보기(워터마크 720p)·길이·스타일 |
| 팩 | — | 실측 표(템플릿 12·효과음 20팩×7·BGM 24·글꼴 60파일·목소리 79·자막 효과 14/팩 6/모션 20·장면 효과·짤 1,283·에펙 30+300) + 시연 1개씩 |
| 내 채널 옵션 | — | §9 프로필 편집·저장(여기만) |
| 라이선스·기기 | — | 키 발급·재발급 / 기기 2대 목록·교체·강제 해제 / 지금 작업 중인 기기 |
| 설치 | — | 설치팩(윈도 x64·맥 arm64·맥 x64) + sha256 표시 · Claude Code 명령 |
| 팩 미리보기(개정 4) | 원본 파일 | **전부 공개하되 견본만**(§8-1): 글꼴 60·효과음 20팩·BGM 24·짤 1,283·템플릿 12·목소리 79·자막 효과를 **보고 듣고 고를 수 있다**. 원본 파일 다운로드 링크 **없음** |
접근: `claude_plan`(`_FEATURE_KEYS` 패턴 app.py:16950). 됐다: 비관리자 베타 계정에서 표 숫자 = 서버 실물, 응답 JSON에 `bench`·`strengths`·`frame`·`path`·`commit` 키 0개, 폰 390px 넘침 0(handoff/숏템프리셋.md:17), **페이지 전체 응답에 원본 자산 URL 0개**(§8-1 검사).

### 8-1. 팩 미리보기 규격 — "공개는 하되 원본 대체가 안 되게"(사장님 개정 4)

원칙: 고객은 **모든 팩을 보고 골라** 채널 옵션(§9)에 넣을 수 있다. 그러나 페이지가 내주는 것은 **견본**이고, 원본은 `assets_for`가 **이번 편이 참조하는 것만** 서명 URL로 준다. 견본은 아래 규격으로 원본을 대체할 수 없게 만든다.

| 자산 | 견본 규격(서버가 미리 구워 둠, 요청 때 원본을 안 건드림) | 원본 대체 불가 근거 |
|---|---|---|
| 글꼴(60파일) | 글꼴 파일 **안 보냄**. 서버가 고정 문구("숏템메이커 1234 가나다")를 **PNG 1장(720px 폭)**으로 렌더해 보여줌 + 옵션 선택 시 고객 채널명을 같은 방식으로 PNG | 글꼴 파일 자체가 전송되지 않음 |
| 효과음(20팩×7) | 팩당 **1.5초 미리듣기 1개**(7개 중 대표 1, 나머지는 이름·길이만), **64kbps mono mp3**, 끝 0.3초 페이드아웃, 가청 워터마크(끝 0.1초 서버 톤) | 원본은 7개·고음질; 견본은 1개·끊김·저음질 |
| BGM(24곡) | 곡당 **15초**(서버가 고른 구간 1곳), **64kbps mono**, 5초마다 **TTS 보이스 워터마크**("숏템 미리듣기") 겹침, 페이드 인/아웃 | 15초·워터마크·mono → 영상에 깔 수 없음 |
| 짤(1,283) | 썸네일 **240px 긴 변**, **JPEG q50**, 대각선 반투명 공용 워터마크("SHORTEM PREVIEW"), **스프라이트 시트**(한 장에 수십 개) | 원본은 투명 PNG/영상 1080p; 견본은 240px·불투명 JPEG·워터마크 |
| 템플릿(12) | **360px 폭 축소판 + 워터마크** | 원본 1080×1920 |
| 목소리(79) | 목소리당 **고정 문장 1개 3초**, 64kbps mono, 서버가 미리 구움(고객 키 사용 0) | 합성은 고객 키로 — 견본으로 충분 |
| 자막 효과(14종·팩 6·모션 20) | 효과당 **2초 WebM/GIF 360px**, 글자는 고정 문구 | 렌더러 코드는 설치팩에 있으니 보여주는 것만 |
| 통과작(15) | **720p·공용 워터마크·스트리밍만**(Range 거부), 다운로드 링크 없음 | 1판부터 유지 |
| 프리셋 틀(7) | 통과작 미리보기 + 틀 **설명 문장**만("흰 바탕·검정 제목·자막 창 아래"). frame 수치·좌표 **없음** | 규격 비노출(§7-4) |

- **전송 방식**: 견본은 `GET /api/claude/preview/<kind>/<id>` — 서명 URL **아님**(페이지 세션 안 10분 토큰), `Content-Disposition: inline`, `Cache-Control: private`, HTTP Range **거부**, `Referer`·세션 쿠키 확인. 원본 저장소와 **다른 접두사**(`preview/` vs `assets/`)에 두어 URL 추측으로 원본에 못 닿게.
- **견본은 배치로 미리 굽는다**(`tools/claude_portal/build_previews.py`, 자산 추가 때 1회) — 요청 때 원본을 읽지 않으니 원본 경로가 응답 코드에 없다. 견본마다 `made_by: preview v1` 표식(0순위-C "만든 파일에 표식").
- **탐지(§7-9 규칙을 미리보기 API에도)**: A4 속도 제한(분당 60·시간당 600) 적용 · **A10 미리보기 긁어가기**: 한 cid가 24h에 견본 **500개↑** 또는 짤 스프라이트 전부·BGM 24곡 전부·효과음 20팩 전부 순차 요청 → 속도 제한 → 지속 시 정지+경보 · 세션 쿠키 없음·Referer 밖·Range 요청 → 403+기록(10회/일이면 A5와 같이) · 견본 URL이 외부 도메인에서 열림 → 기록·경보.
- **판단 주인**: 견본 규격·토큰·거절 = `claude_portal.py:preview(cid, kind, id)` 하나. 원본 발급은 여전히 `assets_for`만 — 두 함수가 **다른 저장소 접두사**를 읽는다.
- **검사**: ① 견본 전수 규격 검사 도구(길이·비트레이트·해상도·워터마크 — ffprobe/PIL, 기준 밖 1개라도 있으면 실패) ② 페이지 응답 전수에 원본 경로·서명 URL 0개 ③ Range 요청 403 ④ 견본 500개 긁기 시뮬레이션 → 속도 제한 발동 1건.
- 한계(정직하게): 견본은 보여주기용 자료로는 수집될 수 있다(240px 짤·15초 곡). 그래서 제작에 쓸 수 없는 품질(저해상도·mono·워터마크·짧은 길이)을 강제하는 것이고, 화면 캡처·녹음까지는 막지 못한다.

---

## 9. 채널 프로필 — 프리셋 상수 + 고객 옵션

```json
channel_profiles(id, customer_id, name, preset_id, options_json, version, created, updated)
{ "profile_id": "cp_7f3a…", "preset_id": "sseolpulda/A_흰바탕창/창아래_검정", "name": "내 채널 · 썰",
  "options": { "brand": {"channel_name": "…", "colors": {"accent": "#…"}, "logo_asset": "ast_…"},
    "text": {"title_font": "JalnanGothic", "caption_font": "CcPretendard-Bold", "caption": {"mode": "accumulate", "enter": "popBounce", "emphasis": "none", "outline_px": 0}},
    "tts": {"provider": "typecast", "voice_id": "tc_…", "name": "필재", "tempo": 1.36},
    "sfx_pack": "팩07", "bgm": {"track": "qiuqiu", "gain_db": -18}, "meme_pool": {"kinds": ["연예인","해외밈"]}, "caption_pack": "story", "scene_fx": {"auto": true} } }
```
프리셋=구조, 프로필=겉모습(calcopy_make.py 머리말). 옵션 값은 서버 자산 id만. 합치기 주인 `shopping_shorts/channel_profile.py:merge(preset, pack_defaults, options)`(= `calcopy_make.merge_preset_pack`:114 이전) — `assets_for`가 서버에서 합쳐 내려주고 PC는 그대로 씀. job에 `profile_version` 고정. 회원 데이터 → **★승인 카드**.

---

## 10. 0순위-C 두 줄

- **주인 함수**: (서버) `claude_portal.py:assets_for`(필요 자산 원본) · `claude_portal.py:preview`(견본 규격·토큰, §8-1) · `claude_portal.py:lease`(동시 1) · `claude_portal.py:anomaly_check`(탐지) — 각 하나. 원본과 견본은 저장소 접두사가 다르고 함수도 다르다. (고객 PC) `server/engine/next_step.js:nextStep(job, step, payload)` 하나(전이·판정·검사·응답 가르기). 서버에 전이 판단, PC에 자산 선택·임대 판단을 두지 않는다.
- **결과물 검사**: ① PC `check` → `verdict.json`(미달이면 final 안 만듦) ② 내부 1호 채널에서 라이브 제작소 mp4와 프레임 대조 차 0(`tools/editor_vs_final_video.py`) ③ 노출 테스트 — `shortem_make`·`/claude` 응답 금지 키 0개, `assets_for` 자산 수 = 참조 수, 완료 후 state.json에 frame 키 0개, audit 로그에 키·좌표 0, **페이지 응답에 원본 URL 0개** ④ lease 실측 3건(§7-10) ⑤ **견본 전수 규격 검사**(길이·비트레이트·해상도·워터마크, §8-1). 전부 기능과 같은 커밋.

---

## 11. 로드맵

| # | 단계 | 됐다의 기준(실측) | 승인 |
|---|---|---|---|
| 0 | 설치팩(윈도 exe·맥 arm64/x64 pkg, 서명·공증, **libass 포함 ffmpeg 직접 빌드 동봉**) + 얇은 .mcpb + 플러그인 + 그림 안내 HTML·시작.md + REST 5개 + 캐시·영수증 · **맥 테스트 기기 2대·Apple Developer 가입** | 윈도 1·맥 2 기기에서 설치팩→Claude Desktop 설치 UI→`shortem_setup` 도구 sha 전부 OK(다운로드 0)·**자가점검 3종(시험 렌더·목소리·다운로드) 전부 생성·ffmpeg ` ass ` 필터 확인 OK** · Claude Code `시작.md` 드래그 1회로 같은 도구 6개 · Gatekeeper 경고 0 · `assets_for` 자산 수 = 참조 수 · 설치 소요 ≤5분(쇼츠AI 킷 10~30분 대비) | 관제 자동 |
| 1 | 내부 1호(썰풀다 A_흰바탕창) 로컬 엔진 + 응답 가르기 + lease | 사장님 PC에서 3번 눌러 mp4 1편, 첫 편 자산 ≤35MB·다음 편 ≤1MB, verdict 기준 안, 라이브 제작소 mp4와 프레임 차 0, 서버 로그 제작 호출 0(license·lease·assets만), 채팅 로그 규격 숫자·규칙 원문 0, 두 기기 동시 시작 → 거절 1 | — |
| 2 | `/claude` 페이지 + **팩 전체 견본 미리보기(§8-1, 배치로 굽기)** + 프로필 + 라이선스·기기·강제 해제 + 탐지 A1~A10 + 관리자 경보 칸 | 베타 계정 페이지 숫자 일치·견본 전수 규격 검사 통과·페이지 응답 원본 URL 0·Range 요청 403·견본 500개 긁기 시뮬레이션에 속도 제한 1건·프로필→자산→렌더 글꼴 실측 일치·키 공유 시나리오에서 경고 1건→정지 1건·경보 칸 표시 | **★승인**(회원 데이터: 프로필·라이선스·기기·IP·임대 로그) |
| 3 | 베타 5명(윈도 3·맥 2) | 각 1편, 반려 ≤3, TTS 편당 1회, 3대째 거절, auto 분류기 차단 0, 거짓 양성 경보 0 | **★승인**(상품 정책) |
| 4 | 판매(카드 079 50만/88만) + 엔진 자가 갱신 | 결제→키→설치→첫 편 고객 손만, 1주 제작 호출 0 | **★승인**(돈) |
| 5 | 2차: 내용 하드 게이트 모델 팩·짤 팩 확대 | — | — |

---

## 12. 사장님 결정 — 상태

### 12-1. 원격 MCP가 무엇이고 왜 안 두나(비개발자용 3줄)
1. 원격 MCP = 고객의 Claude가 **우리 서버에 있는 도구**를 인터넷으로 직접 부르는 방식. 볼케이노가 이것이다(고객 PC엔 주소 한 줄, 로그인은 브라우저 OAuth, 지시는 서버가 한 걸음씩).
2. 우리는 제작을 전부 고객 PC에서 하기로 했으니 Claude가 부를 도구가 **고객 PC 안**(로컬 MCP)에 있다. 서버가 할 일(자산 내려주기·라이선스 확인)은 로컬 MCP가 **일반 웹 요청(REST)**으로 하면 된다.
3. 원격 MCP를 두면 OAuth 로그인 서버·토큰 관리·규격 MUST 8개를 더 만들어야 하고, 고객 요청이 Anthropic 클라우드를 거쳐 와서 **어느 PC에서 왔는지(기기·IP) 못 본다** → 이상 행동 탐지가 약해진다. 그래서 두지 않는다. 나중에 "웹형(서버 렌더)"을 할 때만 다시 검토.

### 12-2. 결정 목록

| # | 항목 | 상태 |
|---|---|---|
| 1 | 렌더 위치 = 고객 PC | **결정됨** |
| 1-b | 실행도구 전부 설치 / 자산 필요분만 / 진행 순서만 | **결정됨** |
| 2 | 원격 MCP 두지 않음, REST+라이선스 키 | **결정됨**(§12-1) |
| 3 | 설치팩 = exe/pkg + 얇은 .mcpb/플러그인 | **결정됨** |
| 4 | 노하우 "최소한으로 노출 제한" → §7-4 체크리스트 | **결정됨** |
| 5 | 검사 결과 서버 보고 없음 / 이상 행동 모니터링 필수(§7-9) | **결정됨** |
| 6 | 기기 2대·각 기기 설치·동시 실행 1(lease, §7-10) | **결정됨** |
| 7 | 맥 1차 포함(§3-4) | **결정됨** |
| 8 | 진행 상세 보기 없음 | **결정됨** |
| A | 고객 API 키 = `~/.shortem/keys` 0600(라이선스 키만 MCPB user_config sensitive) | **결정됨**(개정 4) |
| B | 설치팩·원본 자산 = 객체 저장소+서명 URL · 페이지는 **팩 전체를 견본으로 공개**(§8-1 규격), 원본 다운로드 링크 없음, 원본은 `assets_for` 참조분만 | **결정됨**(개정 4, 사장님 "다 주는 거 아니다 — 공개는 해서 옵션은 주지만 고객 PC로 다 다운받지 못하게") |
| C | 캐시 30일·2GB | **결정됨** |
| D | 탐지 임계값 초기안(§7-9 A1~A10) — 베타 1주 뒤 조정 | **결정됨** |
| E | 다른 기기에서 시작 = 거절(마이페이지 강제 해제만) | **결정됨** |
| F | 맥 ffmpeg = libass 포함 정적 빌드 **직접 빌드·서명·공증·동봉** + 자가점검에 ` ass ` 필터 확인 | **결정됨**(개정 4 — 볼케이노 setup 실측: 그들은 ffmpeg 미동봉, which+`-filters` ass 검사만) |
| — | 원격 MCP | "두지 않음" 유지 |

---

## 13. 확인 못 한 것(미확인)

1. MCPB `user_config sensitive` 저장 위치(키체인?) · Desktop이 PKCS#7 서명을 신뢰 판단에 쓰는지 · .mcpb 용량 한계.
2. 우리가 직접 빌드할 libass 포함 정적 ffmpeg의 크기(윈도·맥 arm64·x64 — 1호 빌드에서 실측; 참고로 gyan essentials zip 114.8MB) · 맥 x64 Node 크기 · Chromium 재서명에 필요한 entitlement 정확한 집합(1호 맥 빌드에서 실측). 볼케이노 setup 응답은 조율자 실측이며 이 세션은 env_probe 코드를 실행하지 않았다.
3. 짤 1,283개 용량 · `static/fonts` 60파일의 글꼴 종 수.
4. 방향 힌트만으로 대본 반려 루프 수렴 횟수(볼케이노 0~1건은 규칙을 이미 아는 모델 결과 — 1호 채널에서 실측).
5. Lightsail 월 송신 한도(app.py:18510 지표만) · 설치팩 100명×0.35GB 전송.
6. Claude Code auto 분류기가 MCP 서버 프로세스 안의 다운로드·실행도 막는지.
7. 고객 PC 1편 렌더 시간(서버 225초/편은 서버 기준) · 맥 Apple Silicon/Intel 렌더 시간.
8. 탐지 임계값(§7-9)은 **초기안** — 베타 5명 1주 로그로 거짓 양성률을 재서 조정.
9. 이 PC `.tracks/칼카피숏템엔진`(1625a9c0d)이 origin(54d652638)보다 뒤처짐 — 엔진 코드 인용은 옛 커밋 기준, 착수 전 `git pull --ff-only`.
10. 관제 ownership.json에 calcopy·MCP 주인 0건 → 착수 때 카드+소유권 등록.
