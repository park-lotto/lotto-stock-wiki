# 볼케이노(volcano MCP) 기록 정리 — 사실만 (2026-10-31 조사, 읽기 전용, volcano 도구 호출 0회)

## 0. 경로 약어·근거 등급

| 약어 | 실제 경로 |
|---|---|
| T | `C:\Users\CH\Desktop\로또의 주식\.tracks\칼카피숏템엔진` |
| M | `C:\Users\CH\.claude\projects\C--Users-CH-Desktop-------\memory` |
| K | `C:\Users\CH\Desktop\볼케이노작업\카피` |
| R | `T\out\썰쇼핑_국립중앙박물관굿즈\runner` — 저장소에 들어온 실행기 사본 125파일(커밋 `e4398cc6b`, 2026-10-24). **우리가 가진 가장 새 판** |
| H | `T\handoff\볼케이노MCP.md` |

근거 등급을 항목마다 갈랐다.
- **[우리 실측]**: 우리가 직접 돌리고 적은 기록.
- **[볼케이노 코드]**: 실행기 사본의 코드를 내가 이번에 직접 읽은 것.
- **[볼케이노 주석]**: 실행기 주석에 볼케이노 개발 측이 적은 숫자. **우리가 검증한 숫자가 아니다.**

조사 한계(이 범위 밖은 모른다).
- 서버 코드는 아무도 못 봤다. 서버 쪽 동작은 응답·주석으로만 안다.
- D: 드라이브가 이 PC에 안 붙어 있어 `D:/volcano_jobs/`를 못 봤다(`ls /d` 실패). `~/.volcano/jobs/`도 지금 없다.
- `C:\Users\CH\.volcano`에 runner 폴더·코드가 없다. 그래서 실행기는 R과 `K\runner\v1~v4`로 확인했다. `keys` 폴더는 열지 않았다.
- `.volcano_runner_key.json`은 값을 읽지 않았다.
- 실행기 주석은 전수 정독이 아니라 정규식 추출이다(§부록). `K\jobs\*\drive_log*.txt`는 읽지 않았다.
- `MEMORY_archive.md`에는 "볼케이노·volcano" 언급이 0건이다(`grep` 실측).

---

## 1. 구조

### 1-1. 서버에 있는 것

| 사실 | 근거 |
|---|---|
| 본체는 Cloudflare Workers `volcano-mcp.groove1027.workers.dev` | H:10 |
| 채널 규격·대본 검증·줄나눔·타이밍·효과음 순환·밈 매핑 판정은 서버에만 있다 | K\README.md:22-23 · H:64 · R\README.md:3-4 |
| 서버는 대본 단계에서 유료 모델을 부르지 않고 규격만 검사한다 | T\handoff\뇌전구벤치.md:214-215 · T\shopping_shorts\channelkit\providers.py:125-127 |
| 서버는 API 키를 갖지 않는다. 키는 회원 본인 것이고, 어디서 읽을지는 서버가 env 단계에서 알려 준다 | R\README.md:68-69 |
| 팩은 서명 URL로 내려간다(6시간). 자산 URL 안에 열쇠(`?k=`)가 있다 | H:19 · R\README.md:27 |
| 채널 프리셋은 09-11에 10개, 09-24에 12개. 이 세션의 MCP 도구 설명에는 39개가 적혀 있다(실제 제공 여부는 미확인) | H:18 · H:152 |

### 1-2. 회원 PC에 있는 것

| 사실 | 근거 |
|---|---|
| Claude 설정에 연결 한 줄과 OAuth 토큰 | H:10 |
| **실행기 코드와 팩은 회원 PC 작업 폴더로 내려받아 돈다**: sfx·pepe·fonts·runner·framevision | H:19-20 |
| 실행기 파일 수: v1 12 → v2·v3 14 → v4(09-25) 32 → 09-30 51 → 10-24 사본 125 | K\README.md:8-10 · `K\runner\v4_0925_39ea06b4` 실측 · M\reference_볼케이노_실행기차단_OCR보존두곳.md:56 · R 실측 |
| 회원 PC에서 도는 것: 다운로드·ffmpeg·이미지·TTS 호출·측정(HTTP·ffmpeg·PIL·측정) | R\README.md:46-47 |
| 전용 venv, 키 파일 `~/.volcano/keys/<서비스>`(값만) | H:31-33 · R\README.md:16-18 |
| 출입증 `.volcano_runner_key.json`: `assets` 응답으로 받고, 이틀 뒤 만료 | H:24 · R\README.md:80-81, :92-93 |
| 서버는 `env`부터 실행 단계를 **실행기가 부른 것만** 받는다(2026-09-02). 왕복은 실행기 26~46초, Claude 개입 124~275초 | R\README.md:89-90 |
| 재개 파일: 사람 자리에서 멈추고 `next_payload.json`·`input_brief.json`을 남긴다 | R\README.md:91, :116-118 |
| 긴 실행은 `--background`, `progress.log`·`process.json`으로 본다 | R\README.md:136-139 |
| 오래 가는 자리 `~/.volcano/runner`에도 설치하는 코드가 있다. 단 이 PC에는 그 폴더가 없다 | R\volcano_drive.py:808-818 · `ls` 실측 |

회원 PC에서 서버로 나가는 것(`setup`의 env_probe): home, 파이썬 경로·버전, 설치 모듈, ffmpeg, CPU, 보유 키 목록(값 아님), `os.getcwd()`(M\reference_볼케이노_개발폴더에서_호출금지.md:20-25).

### 1-3. 실행기 갱신 — 언제, 무엇을 덮어쓰나 [볼케이노 코드]

**언제**
1. 첫 편의 `assets`에서 runner 팩을 받는다(H:19).
2. **서버 응답마다** 갱신 지시가 올 수 있다. 응답의 `_meta.runner_update`를 받으면 그 자리에서 `self_update`가 돈다(R\volcano_run.py:2240-2256). 2026-09-02 도입.
3. 서버가 `status="runner_update"`로 답하면 FP2 경로가 돈다. 저장 → 설치 → 같은 인자로 자기 재시작(R\volcano_drive.py:6077-6090, :5835-5855). 2026-10-05 도입.
4. 옛 FP1 경로: 서버가 내린 설치기가 설치하고, 이제 실행기가 그 뒤 스스로 다시 뜬다(R\volcano_drive.py:5789-5795).
5. `runner_pin` 작업은 갱신에서 빠진다. 설치된 코드를 유지한다(R\volcano_run.py:2244-2246).

**무엇을 덮어쓰나**
- 설치 자리는 `<작업 폴더>/runner`다. 작업 폴더 밖 공용 사본은 바꾸지 않는다(R\volcano_run.py:2774-2790).
- 팩에 든 파일만 파일 단위로 원자 교체한다. 바뀌기 전 원본은 `<작업 폴더>/.volcano-runner-update/replaced/<식별값>/`에 보관한다(R\volcano_drive.py:571-580, :778).
- 안전장치: sha256·파일 수 대조, 설치 전후 runner_id 대조, 다르면 바꾸지 않음(R\volcano_drive.py:743-748, :5893-5907 · R\volcano_run.py:2862-2870).
- 한 프로세스에서 한 번만 갱신. 재시작한 판에 같은 갱신이 또 오면 멈추고 "관리자에게 알리라"고 한다(R\volcano_run.py:2836-2839 · R\volcano_drive.py:5861-5866).
- 새 필수 모듈이 없으면 갱신을 멈춘다(R\volcano_run.py:2840-2851).

**회원 패치는 살아남지 못한다**
- [우리 실측] 09-14 fsync 패치가 서버의 재배포로 덮였다. 그래서 실행 직전마다 다시 적용하는 `drive_patched.py`를 썼다(M\reference_볼케이노_실행기차단_OCR보존두곳.md:31-33).
- [볼케이노 코드] 실행기 식별값은 배급 파일 **전부의 해시**다(R\runner_files.py:125-131). 식별값은 UA에 실려 서버로 간다(R\volcano_drive.py:542). 그러니 파일을 고치면 판이 달라진다.
- 서버가 그 값을 어떻게 비교하는지는 **미확인**이다. "고친 파일이 그래서 덮인다"는 위 두 사실을 이은 추정이다.
- 우리 문서도 같은 사실을 적어 뒀다: "볼케이노도 회원 수정 덮어씀"(T\channel\칼카피_제작순서\99_회원PC_MCP.md:80).

### 1-4. 검수기 [볼케이노 코드]

- 기본 검수 제공자는 `client`, 즉 연결된 AI다. 유료 `evolink`는 `max_requests`를 함께 줄 때만 쓴다(R\volcano_run.py:5462-5468 · R\README.md:144-145).
- 검수자는 `claude`·`codex`·`agy`·`host` 네 가지다(R\volcano_run.py:5498-5503).
- `claude`·`codex`면 실행기가 그 CLI를 직접 띄운다. `host`면 멈추고 현재 대화의 AI에게 넘긴다(R\volcano_run.py:5609-5616). docstring: "CLI for actual images; host model handoff for video/audio or unavailable CLI"(R\volcano_run.py:6125).
- 멈출 때 실행기는 `need_input`과 `review_requests`를 남기고, 현재 AI가 답을 넣어 같은 단계를 재개한다. 문구는 "유료 검수를 자동 호출하지 않았습니다"(R\volcano_drive.py:6168-6181).
- 처리 순서: 완료 영수증이 있으면 그 답을 돌려주고, 그 뒤에야 `replies`를 읽는다(R\volcano_run.py:6210, :6213). **09-14 기록 "내가 쓴 검수 답은 안 쓰인다"의 코드 근거가 지금도 같다.**
- 답은 요청 SHA·이미지 ID·영상 SHA가 맞아야 받는다. 틀리면 거절하고 지문을 영수증에 남긴다(R\volcano_run.py:6214, :6248).
- 호스트 자료 지시: "읽지 못한 자료가 있으면 통과 답을 만들지 말고 미완료로 유지"(R\volcano_run.py:6184-6186).
- 인물형 롱폼의 영상 피사체 판독은 구독 AGY가 한다. AGY가 결과 없이 끝나면 사람 답으로 풀지 않는다(R\volcano_run.py:6313-6318 · 이 세션 MCP 도구 설명).
- 09-25 쇼핑 실측: 컷 검수는 영상·음성이 필요해 Claude 검수로 못 넘어가고, 유료 EvoLink를 지정해야 했다(K\docs\쇼핑_역분석_2026-09-25.md:19).

### 1-5. 회원 Claude가 하는 일

- 사람 자리 3곳을 채운다: script·prompts·memes. 나머지 12단계는 실행기가 서버와 직접 주고받는다(T\channel\volcano\볼케이노_원클릭원리_숏템메이커적용_2026-09-12.md:18, :34).
- 실행기 첫 호출과 재개 명령을 돌린다(H:22 · R\README.md:83-92). 대본 작성 안내는 `input_brief.json`의 `caption_budget`·`script_rules`·`tone`·`then_call_with`로 받는다(R\README.md:116-117).
- 검수 대기 시 실제 자료를 보고 `review_replies`를 쓴다(§1-4).
- 금지: 규격 조회 목적으로 지난 단계를 다시 부르는 것, 임의로 대본을 자르는 것, 회원에게 토큰을 묻는 것(R\README.md:28, :36, :119).
- 실패 보고는 실행기가 서버 `feedback`으로 자동 전송한다. 성공 보고도 2026-08-22 이후 보낸다(R\volcano_drive.py:4347-4353, :4424-4431, :4481-4482). `step=feedback`은 "관리자가 매일 아침 읽는다"(T\channel\volcano\볼케이노_원클릭원리_숏템메이커적용_2026-09-12.md:39).

---

## 2. 멈춤·오류 사례

### 2-A. 우리가 직접 겪은 것 [우리 실측]

"주체" 칸: **서버** = 볼케이노 쪽이 고침, **우리 우회** = 우리가 입력·소재·파일로 피함, **미해결** = 안 풀린 채 끝남.

| 날짜 | 채널·단계 | 증상 | 원인 | 풀린 방법 | 주체 | 근거 |
|---|---|---|---|---|---|---|
| 09-11 | 뇌전구 script | 대본 반려 30건 | 서버 규격 위반 | 규칙을 익혀 재작성. 다음날 0건 | 우리 우회 | H:45-54, :76 |
| 09-11 | 전 단계 | 가짜 소재로 팩만 받기 차단 | Claude Code auto 모드 안전장치 | 우회 안 함 | 해당 없음 | H:60 |
| 09-11 | 뇌전구 voice | Typecast 401 | 64자 hex 키 | `__plt` 키로 교체 | 우리 우회 | H:37 |
| 09-11~12 | 뇌전구 render_plan | 밈 내장 글자 OCR로 같은 자리 정지 | 팩의 밈 자체에 글자 있음. **처방이 실행기 판마다 3번 바뀜** | ①두 구조 동시 수정 ②`images[경로].preserve_text` ③밈을 025.png로 교체 | 우리 우회 | H:53, :87, :121, :133, :142 · M\reference_볼케이노_실행기차단_OCR보존두곳.md:14, :22, :54 |
| 09-12 | 실행기 실행 | "Code from External" 차단(첫 1회 통과, 2회째부터) | **우리 쪽 Claude Code auto 분류기**(볼케이노 결함 아님) | 사장님이 `!`로 1회 실행 | 우리 우회 | H:83, :119, :141 |
| 09-12 | 팩 다운로드 | 같은 분류기 차단 | 위와 같음 | 완성 폴더의 팩 복사. sha 대조로 재사용 통과 | 우리 우회 | H:130 |
| 09-12 | env | "실행기를 찾지 못했다" 경고 | setup 때 잰 옛 env 재전송 | 작업 폴더에서 다시 재서 env 재실행 | 우리 우회 | H:85 |
| 09-12 | render_plan | images 반려, user_slots 반려 | list·`{}` 모양 틀림 | dict, `[]` | 우리 우회 | H:86, :142 |
| 09-12 | probed | "비디오 스트림이 없다" | news 소재에 probe 전송 | source_chars만 | 우리 우회 | H:107 |
| 09-12 | images | EvoLink 실패 3장·1장·1장(사유 없음, state=failed뿐) | 무기·미성년자 묘사로 보이는 프롬프트(우리 판단) | 프롬프트 수정. 성공분은 캐시 재사용 | 우리 우회 | H:120, :132, :142 |
| 09-12 | keys | 키 파일이 지워졌다 다시 써짐 | 동시 세션 | 저장 직후 `ls` 재확인 | 우리 우회 | H:118 |
| 09-14 | 뇌전구 voice | **윈도우에서 100% 사망** `OSError [Errno 9]` | `_tts_fsync`가 읽기 핸들로 fsync | 우리 `drive_patched.py`로 매 실행 재패치, 서버에 신고 | **서버**(현재 코드 `r+b` + 주석 "Windows CRT _commit requires a writable descriptor", 09-30 51파일판에서 재현 안 됨) | M\reference_볼케이노_실행기차단_OCR보존두곳.md:27-33, :56 · R\volcano_run.py:13644-13647 |
| 09-14 | voice | 크래시 뒤 재요청 영구 차단 | TTS 영수증 `intent` 잔존 | 캐시 파일 삭제(재과금 위험) | 당시 우리 우회. **이후 서버**: 주석에 수리, 기록 삭제 금지 안내 | M\…:34-36 · R\README.md:156-158 · R\volcano_run.py:13862, :12324 |
| 09-14 | render_plan | 검수 답을 써도 같은 retry | 실행기 자체 검수기와 영수증 우선 | 그림을 바꿈 | 우리 우회 | M\…:37-39 · R\volcano_run.py:6210-6213 |
| 09-14 | render_plan | 엉뚱한 그림 수정 | `group:N`은 슬롯 번호가 아님 | 슬롯 역산 | 우리 우회 | M\…:40-41 |
| 09-14 | render_plan | 글자 얹힌 밈이 주피사체 검사 실패 | 상자가 팔·글자를 자름 | 밈 자리를 실사로 | 우리 우회 | M\…:42-43 |
| 09-14 | assets | `next_payload.json` 덮여 진행 상태 날아감 | assets 재호출 | 백업 | 우리 우회 | M\…:47 |
| 09-16 | setup | 멈춤은 아니나 개발 폴더에서 호출해 폴더명·키 목록 전송 | 전역 등록 + env_probe | 개발 폴더 호출 금지 | 우리 규칙 | M\reference_볼케이노_개발폴더에서_호출금지.md:11-29 |
| 09-25 | **쇼핑 shop_cuts** | **같은 컷 8개가 1시간 넘게 매번 WinError 10054·HTTP 524. 완성본 없음** | EvoLink가 특정 컷 요청을 거부하는 것으로 **판단**(원인 미확정) | 유료 낭비 막으려 중단 | **미해결** | K\docs\쇼핑_역분석_2026-09-25.md:6 · K\벤치_대기열.md:8 |
| 09-25 | 어랍숏 | 말 0초 소재 진행 거부 | 전사 단어 0 | 말 있는 UGC로 교체 | 우리 우회 | K\docs\어랍숏_역분석_2026-09-25.md:57, :163 · K\벤치_대기열.md:12 |
| 09-25 | 어랍숏 assets | 토큰 직접 파일 쓰기 차단 | 안전장치 | `--step assets`로 실행기가 저장 | 우리 우회 | K\docs\어랍숏_역분석_2026-09-25.md:168 |
| 09-30 | 웃긴버거 camera | 유료 TTS 전 "글꼴 없음" 정지 | assets를 MCP 손수 호출, fetch_font 누락 | 받아 넣고 rinbox_retry | 우리 우회 | K\docs\웃긴버거_역분석_2026-09-30.md:43, :134 |
| 09-30 | 웃긴버거 다운로드 | yt-dlp 일부 "not available" | JS 런타임 | `--js-runtimes node` | 우리 우회 | K\docs\웃긴버거_역분석_2026-09-30.md:135 |
| 09-30 | 군림보 render_plan | group:10 피사체 미확정, 간판 깨진 한글 반려, 헛과금 3장 | 그림 가장자리 붙음, 생성 글자, 우리가 0부터 셈 | 재생성·번호 교체 | 우리 우회 | K\docs\군림보_역분석_2026-09-30.md:111-115 · M\…:50-52 |
| 09-30 | 강석주 images | `StepError: 슬롯 2의 색인 후보를 받지 못했습니다` 크래시, 15슬롯 중 7슬롯 QC 탈락 | 썸네일 URL 탈락, 일본어 글자 | 검색어 교체, 6장 반복 재배치 | 우리 우회 | K\docs\강석주_역분석_2026-09-30.md:50-56 |
| 09-30 | 3D쇼츠 | `PREFLIGHT_FAILED`, 유료 전 멈춤 | Gemini 키 또는 agy 없음 | 사장님 결정 대기 | **미해결** | K\docs\3D쇼츠_역분석_2026-09-30.md:6 · K\벤치_대기열.md:17 |
| 09-30 | 카드뉴스 | 사진 조달 0, 구글 캡차 4회 | 구글 차단 | 색면 8장으로 완료 | 우리 우회 | K\docs\카드뉴스_역분석_2026-09-30.md:56, :63 · K\벤치_대기열.md:18 |
| 시점 미기록 | 전 채널 | 한글 작업 폴더에서 drawtext 크래시 | 경로 | 영문 폴더만 | 우리 우회 | K\벤치_대기열.md:22 · T\channel\칼카피_제작순서\00_공통.md:13 |
| 09-30 | setup | 개발 창 호출이 자동 권한 검사에 차단 | "데이터 유출" 판정 | 볼케이노작업 폴더 새 창 | 우리 규칙 | M\feedback_볼케이노셋업창_켜기.md:19-21 |
| 10-24 | 썰쇼핑 sseol_make | 실행기가 `sseol_make` 호출 실패로 66.7초에 멈추고 상태가 `active`로 남음. handoff·log.d에 이 작업 기록 없음 | **미상** | 기록 없음 | **미상** | `T\out\썰쇼핑_국립중앙박물관굿즈\runtime-report.json:84-90, :155-160` |

### 2-B. 볼케이노가 회원에게서 겪은 것 [볼케이노 주석 — 숫자는 저쪽 주장, 우리 미검증]

아래는 실행기에 적힌 대표 사건이다. 나머지는 §부록. 전부 볼케이노가 실행기·서버를 고쳐 푼 것으로 적혀 있다. 회원이 패치한 기록은 주석에 없다.

| 날짜 | 규모 | 증상·원인 | 수리 | 근거(R) |
|---|---|---|---|---|
| 08-16 | 7명 | 서버 응답 모양이 아닌 입력에 죽음 | 모양 아니면 아무것도 안 함 | volcano_run.py:9697 |
| 08-17 | "여러 명" | 예제가 TOKEN을 보여 줘 회원이 없는 토큰을 찾다 멈춤 | 문서·정상 경로 수정 | README.md:29-30 · volcano_drive.py:32-37 |
| ~08-16(나흘간) | 92건·48명 | 측정 후 다음 줄에서 죽음(`measure_sfx`·`cut_sigs`·`factcheck`) | 규칙·실행기 양쪽 | volcano_drive.py:1395-1400 |
| 08-22 | 304건·66명 | 산문 지시를 모델이 못 지켜 값 누락 | 데이터 규칙화 | volcano_drive.py:1423-1430 |
| 08-26 | 69건·35명 | 헤더가 아닌 값을 헤더로 보내 죽음 | 헤더 필터 | volcano_drive.py:1664-1669 |
| 09-02 | 93명 중 89명 | 실행기 사용자 대부분이 옛 팩 | **자동 갱신 도입** | volcano_run.py:2265, :2820-2822 |
| 09-02 | 162건·9명 | 윈도우 ffmpeg 한글 파일명 | 수리 | volcano_run.py:3009 |
| 09-04~05 | 159명 수신·94명 자동 해제 | `ref_*` 계측기 22개가 회원 팩에 유출 | 팩 분리 | volcano_drive.py:1329-1334 |
| 09-12 | 227회·78명(배포 전 24시간) | 접힌 측정값 어긋남 반려 | 읽을 때 복원 | volcano_run.py:1320-1325 |
| 09-27 | 7,558건·471명 | 응답 풀기 결함으로 정지 | 수리 | volcano_run.py:980-985 |
| 10-02~04 | 1,419건·217명, 배포 뒤 31건·23명 | 재시도를 단발로 바꾼 뒤 caps 500 한 번에 정지 | 재시도 복구 | volcano_run.py:1612-1617 |
| 10-03 | 646명이 2,804번 | 판 갈아타기마다 사람이 같은 명령 재실행 | FP2 자동 재시작 | volcano_drive.py:5839 |
| 10-04 | 8건·7명 | TTS 완료 불명으로 영구 정지 | 수리 | volcano_run.py:13862 |
| 10-14~23 | 신고 4일분 | 새 판이 옛 폴더 모듈을 읽어 같은 갱신 무한 요구 | 곁 모듈은 같은 폴더 것만 | volcano_drive.py:88-92 |
| 10-16~17 | 2명 | 외부 글꼴 배포처 503 한 번에 seed 정지 | 대체 글꼴 | volcano_run.py:2698, :2718 |
| 10-17 | 26건·2명 | **배포 창(팩 R2 업로드~Worker 전파)에 sha 어긋남** | 15·30·45초 자동 재시도 | volcano_drive.py:5824-5831 |
| 10-17 | 20건·10명 | 유튜브 403 | yt-dlp 판 처리 | volcano_run.py:3147 |
| 10-17~18 | 7명(#311) | 팩 sha 어긋남 되풀이, 신고에 사실 부족 | 진단 사실 추가 | volcano_drive.py:5895-5896 |
| 10-20 | 290건(뇌전구) | images 제공자 거절로 멈춤 | 빠진 칸 길 | volcano_run.py:8010 |
| 10-11~22 | 15건 | 새 판 주소에 앞 판 바이트가 옴 | 응답 머리 기록 | volcano_drive.py:1107 |
| 10-22 | 107번(한 사람·작업 폴더 33곳) | 공용 사본이 영영 옛 판이라 단계마다 갱신 | 작업 폴더 runner로 넘김 | volcano_drive.py:5959-5967 |
| 10-23 | 26건·16명(1주) | 윈도우 자식 프로세스 0xC0000142 | CREATE_NO_WINDOW | volcano_run.py:3284-3285 |
| 10-23 | 69건·17명(1주) | 설치기 뒤 사람이 재실행 | 자기 재시작 | volcano_drive.py:5791-5795 |

**읽을 때 주의**: 건수는 사건마다 잰 기간·단위가 다르다. 합산하면 안 된다.

---

## 3. 회원에게 내보내기 전 시험 절차·회원 수·멈춤 건수

### 내보내기 전 시험 절차

**명문화된 절차 기록 없음.** 우리 기록 어디에도 없다. 서버·개발 저장소를 못 봤기 때문에 "없다"가 아니라 "우리가 모른다"이다.

간접 흔적만 있다 [볼케이노 주석].
- 저장소에 시험이 있다: `tests/test_runner_update_cwd`, `tests/test_runner_win.py`, `tests/test_blob_protocol.py`, `tests/test_ref_runner_tool.py`, `tools/check_names.py`(R\volcano_drive.py:658, :1341, :6013 · R\volcano_run.py:817, :1561).
- 사람 또는 에이전트 검토 회차 표기가 있다: "Z 검토 2회차·3회차", "B 최종 검토 3회차", 원장 번호 `W2-xx`(R\volcano_drive.py:758, :775 · R\volcano_run.py:2775, :2268).
- 실기 PC 이름이 나온다: `win-01`, `win-main`, 맥(R\volcano_run.py:3283 · R\runner_caller.py:22 · R\file_witness.py:8).
- 배포 방식: "서버 코드는 배포하면 그 순간 전원에게 적용"(R\volcano_run.py:2820). 단계적 배포·카나리 언급은 내가 찾은 범위에서 없다.
- 배포 창이 있다: "팩 올림→배포 창 약 45초"(R\volcano_drive.py:5830).
- 시험을 지나 회원에게 먼저 터진 사례가 주석에 적혀 있다: 10-02 변경이 10-04에 1,419건·217명으로 드러남(R\volcano_run.py:1616), 팩 유출(R\volcano_drive.py:1329-1334).
- 찾아내는 수단은 시험이 아니라 자동 신고다. 내가 본 가장 큰 번호는 #318이다(R\response_receipts.py:115).

### 회원 수 [볼케이노 주석]

| 표현 | 시점 | 근거 |
|---|---|---|
| 수강생 480명 | 09-05 주석 | R\volcano_drive.py:1331, :6281 · R\volcano_run.py:1559 |
| 48시간 실행기 사용자 93명 | 09-02 | R\volcano_run.py:2265 |
| 3일 `render_mix` 성공 175명, `stitch_master` 129명 | 08-22 | R\volcano_drive.py:4352-4353 |
| 하루 646명이 실행기 갱신 | 10-03 | R\volcano_drive.py:5839 |

총 회원 수를 직접 적은 공식 기록은 없다. 위 480은 코드 주석의 표현이고, 646은 그날 갱신한 사람 수다.

### 멈춤 건수

- 사건별 숫자는 있다(§2-B·부록). **전체 멈춤률·완주율 기록은 없다.**
- 08-22까지는 볼케이노 자신도 완주를 몰랐다: "완주 기록은 0건"(R\volcano_drive.py:4352-4353). 그 뒤 성공 보고를 넣었지만 결과 숫자는 우리 기록에 없다.
- 요금 체계: 기록 없음. `C:\Users\CH\Desktop\볼케이노작업\숏템엔진_진행상황.md:20`의 "요금 방식" 칸이 빈 채로 있다.

---

## 4. 숏클(숏템MCP·칼카피 엔진)이 볼케이노에서 가져오거나 비교한 설계 결정

### 가져온 것

| 결정 | 근거 |
|---|---|
| 공통 엔진 하나 + 채널마다 설정표 한 장 | T\docs\superpowers\specs\2026-09-25-숏템엔진-design.md:5, :11 · T\docs\superpowers\specs\2026-10-15-칼카피엔진-design.md:11, :25 |
| 단계 배열 구조(`next_step` 상태기계), 규칙은 판정으로만 | T\docs\superpowers\specs\2026-09-12-brainbulb-design.md:20 · T\channel\volcano\볼케이노_원클릭원리_숏템메이커적용_2026-09-12.md:29-39 |
| **응답 규약**: `status/message/do/measure/review/traps/next_step/then_call_with/next_payload` | T\docs\superpowers\specs\2026-10-21-숏템MCP-볼케이노형-design.md:43-49, :53-75 |
| 노하우는 서버 지시서 한 곳, 회원 PC는 손(실행기), 눈은 회원 Claude | 같은 문서:1, :10 · T\handoff\숏템MCP.md:4, :212-213 · T\tools\calcopy\hybrid\flow.py:2 · T\tools\calcopy\hybrid\runner_ops.py:2 |
| 진행 안내는 지금 단계 한 줄만 | T\handoff\숏템MCP.md:161 |
| 회원 키는 PC 파일에 값만, 서버 미보관, 로그는 지문 12자 | T\docs\superpowers\specs\2026-10-18-숏템MCP-design.md:282 |
| 팩·서명 URL, 영수증 재사용, 출입증 모양, 재개 파일, 껍데기 README 규율 | 같은 문서:3, :48-56 |
| 돈 나가기 전 자가점검 | 같은 문서:189 · 원리 문서:31 |
| 엔진 자가 갱신은 서명+sha256 둘 다, 실패 시 교체 안 함 | 같은 문서:155 |
| 측정 규율(LUFS·모노·프레임 수÷fps·못 잰 값 None) | T\docs\superpowers\specs\2026-09-28-channelkit-bench-design.md:15-22 · T\docs\칼카피\측정코드_세벌_함수지도_2026-09-28.md:239 |
| 키 경로 `~/.volcano/keys` 재사용(칼카피·측정 도구) | T\tools\calcopy\hybrid\runner_ops.py:291 · T\tools\calcopy\pc_check.py:61-63 · T\channel\칼카피_시작.md:24 |
| `customize` 단계 개념 참고("개념 참고만, 코드 아님") | T\tools\calcopy\표준작업지시\12_회원맞춤_패치.md:9 |
| 숏템엔진 설계에서 "볼케이노 실행기 코드 사용"은 범위 밖(라이선스·서버 종속) | T\docs\superpowers\specs\2026-09-25-숏템엔진-design.md:88 |

### 일부러 다르게 간 것

| 볼케이노 | 숏클 | 근거 |
|---|---|---|
| `do`에 코드·argv가 통째로 실림. argv 허용 목록 없음 | **허용 목록 안의 명령 종류와 인자만** | 10-21 설계:45, :49, :75 · 10-18 설계:38, :300 |
| 응답에 지시·반려 규칙 원문이 실려 역분석됨(우리가 30건으로 역분석) | 규칙 원문·임계값을 질문에 안 싣고, `do`·`measure`는 모델에 안 보임 | 10-18 설계:56, :240 · 10-21 설계:79 |
| 설치 때 winget·Homebrew로 내려받고 첫 설치가 무거움 | 서명된 설치본에 실행 도구 동봉 | 10-18 설계:186 |
| Claude Code auto 분류기가 실행기·팩 다운로드를 차단 | 다운로드·실행을 MCP 서버 프로세스 안에서(그 표는 "미실측") | 10-18 설계:365 |
| ffmpeg 미동봉 | libass 포함 정적 빌드 동봉 결정 | 10-18 설계:470 |
| 없음(우리 문서의 비교) | 선검수·내용 관문·compare·원음 덕킹·사실 검증을 로컬 엔진에 | 10-18 설계:268 |
| 우리 문서의 평가: 한 채널 꼴을 손으로 옮긴 템플릿 | 구조 다섯 가지로 경쟁 | T\tools\calcopy\칼카피_공통규칙표준.md:27-33 |
| 엔진 수정 덮어씀(같은 점) | 엔진 못 고침, 중앙 수리 → 시작 때 자동 업데이트 | T\channel\칼카피_제작순서\99_회원PC_MCP.md:80, :83 · T\handoff\숏템MCP.md:109, :152 |

### 비교에서 나온 볼케이노 약점 기록

- 실행기 판마다 처방이 달라짐(밈 글자 보존 3가지), 키 파일을 한 기계 세션이 공유, 왕복 길이(10-18 설계:48-53).
- `.vscode/tasks.json`이 `--dangerously-skip-permissions`를 자동 실행(H:12).
- 모방은 약관 문제가 될 수 있음, 사장님 판단 몫(H:65 · T\channel\volcano\뇌전구_자체제작_분석_2026-09-11.md:222). 이 판단이 내려졌다는 기록은 찾지 못했다.

---

## 5. 기록끼리 어긋나거나 낡은 것

| 낡은 기록 | 지금 사실 | 근거 |
|---|---|---|
| "채널 10개 고정, 스타일 못 바꿈"(원리 문서 §6, 09-12) | 프리셋이 늘었고 `customization`·`customize` 단계가 있다 | 원리 문서:156 · 12_회원맞춤_패치.md:9 · K\docs\군림보_역분석_2026-09-30.md:118, :127 |
| 09-14 "서버가 단계마다 volcano_run.py를 새로 내려보내 덮어쓴다" | 10-24 코드는 판이 다를 때만 갱신. 단 식별값이 전 파일 해시라 고치면 판이 달라진다(§1-3) | M\…:31 · R\runner_files.py:125-131 |
| 09-14 "fsync로 voice 100% 사망" | 서버가 고침 | R\volcano_run.py:13644-13647 |
| `K\README.md` "실행기 3버전, v3 최신" | 폴더에 v4 있음, 저장소에 10-24 판 있음 | `K\runner` 목록 |
| H:10 "이 PC엔 연결 설정 + 토큰뿐" | 같은 문서 §2대로 실행기·팩이 작업 폴더에 내려온다. **이 문장만 읽으면 오해한다** | H:10 · H:19-20 |
| 09-30 강석주 "≥400px" | 메모리에서 ≤387로 정정됨 | M\…:53 |

## 6. 곁에서 발견한 위험

`.volcano_runner_key.json`이 **저장소에 추적되고 있다.** `out/썰쇼핑_국립중앙박물관굿즈/`가 커밋 `e4398cc6b`(10-24)로 들어갔고, `origin/main`에도 있다(`git ls-tree` 1건). H:69의 gitignore는 `out/volcano*`만 막아서 이 폴더는 빠졌다. 값은 읽지 않았다. 출입증은 이틀 만료라고 기록돼 있다(H:24). 그 폴더에는 실행기 전체도 함께 들어 있다.

---

## 부록 — 실행기 사고 주석 기계 추출 [볼케이노 주석]

R 전체 `*.py`에서 `N명`·`N건`·`신고 #N`·`실행기 중단 보고`가 든 줄을 뽑았다. 총 211줄. 파일:줄 형식이며 경로는 R 기준. 정독이 아니라 추출이라 맥락이 잘릴 수 있고, 회원 사고가 아닌 숫자도 섞여 있다.

```
agy_google.py:17: 따라가지 않고 **이동할 곳(Location)만** 본다 — 동시 2 · 요청 시작 사이 0.5초 = **초당 2건 이하**
agy_google.py:19: Gemini API 약관 · vertexaisearch robots.txt 확인. 초당 2건 266회 거부 0 실측).
agy_google.py:21: 사이트마다 동시 1 · 초당 1건 이하(보수값 · 공식 숫자 없음), 서로 다른 사이트는 동시에.
agy_google.py:135: 시작하고 **60초를 기다린 뒤** 끝났다(win-01 cli.log 12건) — 수강생 화면엔 그동안 아무 안내가 없고,
agy_google.py:243:# ── 받기(사이트마다 동시 1 · 초당 1건 이하, 구글 중계 주소는 동시 2 · 초당 2건 이하) ─────────
agy_google.py:253:_RD_SEM = threading.Semaphore(2) # 사장님 확정: 초당 2건 = 동시 2 · 시작 간격 0.5초
agy_review_bridge.py:196: # ★'per_request_evidence'(2026-10-21 쇼핑 신고 510306 · 쇼핑 한 패스 10-17·인물형 롱폼 피사체 10-06 과 같은 판정): /usage 를
agy_review_bridge.py:198: # 회차 전체(7건)가 멈췄다. 속도·한도 낱말이나 /usage 가 한도 소진·로그인 풀림을 말하면 그대로 전부 멈춘다(6-2).
agy_transport_client.py:32:#: 결과 사건(result) 한 줄이 stdout 에 줄바꿈까지 다 쓰인 뒤 agy 가 스스로 끝나기를 기다리는 상한(★10-19 서버 신고 #305 · 13명).
agy_transport_pc_env.py:77: 창(클로드 코드)의 PATH 는 낡아 있다(진단 본문: 4명이 회차마다 찾음/못찾음)."""
cardnews_agyimage.py:53:#: IMAGE_PATH 줄의 경로 — 한 줄 안에서 확장자로 끝나는 가장 짧은 글자(2026-10-17 신고 #122: 예전 `\S+` 는 «C:\Users\Windows 10\…» 처럼
cardnews_agyimage.py:56:#: agy 가 답을 끝낸 뒤에야 하위 에이전트가 그림을 저장하는 일이 있다(신고 #122 · «몇 초 뒤 파일이 생김»). 답 뒤 이 시간 안에서만
cardnews_agyimage.py:259: # ★ImageName 은 영문·숫자·밑줄만(신고 #122: agy 는 하이픈을 밑줄로 바꿔 저장해 «이 이름으로 찾기» 가 빗나갔다). 찾는 열쇠는 이
cardnews_design.py:70: ★서버에 두면 480명분 설정을 우리가 들고 있게 된다(§2 와 같은 판단).
cardnews_images.py:259: **이미 과금된 작업 8건이 버려질 뻔한 사고**가 있었다(앱, 2026-08-11).
cardnews_publish.py:23: 480명 키를 우리가 들고 있으면 그게 사고의 근원이다(§2 와 같은 판단).
cardnews_render.py:442: 정본 주석: 고정 검정이던 시절 사용자가 '고장난 화면' 으로 읽었다(피드백 3건).
film_continuity.py:312: 으로 돌려보냈다. 호스트는 초 단위 편집으로 프레임 틈을 맞히지 못해 실물 1명이 5시간 1,417회를 돌았다.
film_editor.py:113: 적었더니 verify 쪽에만 빠져, AGY 카메라 작업의 최종 확인이 원리적으로 늘 실패했다(10-07~10-17 · 14명).
film_editor.py:896: # (2026-10-22 일본어 신고 514415 · 10~104ms 물림). 자기 줄의 소리는 자르지 않는다.
film_editor.py:987: # 자막이 걸렸다(10-21 웃긴버거 신고 510295). 같은 원본의 표본 프레임마다 가장자리 «단색 띠»를 재고, 모든 표본에
film_editor.py:2624:#: 위에 앞 회차의 reason='source_cut_boundaries' 와 앞 보고서 경로가 남아 서버가 «원본 컷 경계» 대기를 되풀이했다(두 보고서 모두 문제 0건).
film_word_audio.py:88: 규칙으로 다시 매핑해 같은 실패를 되풀이했다(빠져나갈 수 없는 고리 · 3명). 결정적 규칙이라 같은 결과는 같은 표가 된다.
focus_kernel.py:37:exec(compile('FPS = 30\n\ndef qf(d, fps=FPS):\n """프레임 격자에 맞춘 길이. 정본 `stitch.qf`."""\n return round(round(d * fps) / fps, 4)\n\ndef window_of(S):\n """(창 상단 y, 창 하단 y, 창 높이). 3층 캔버스가 아닌 채널이면 None.\n\n ■ 왜 있나 (
local_focus.py:439: # (10-21 뇌전구 render_plan 신고 · 한 주 9건·4명 · 사장님 «반려가 아니라 정상 실행»).
local_render_plan.py:158: # 보고 · 뇌전구 render_plan img43 11건·3명). 그림 칸은 images 단계가 만든 자리다 — images 를 다시 부르면 이미 있는 칸은
local_render_plan.py:424: # ★두 사실을 가른다(2026-10-23 뇌전구 신고 · 5명 · 맥·윈도우): 예전 한 문구는 «무엇이·어느 쪽이» 를 안 말해 원인을 못 가렸다.
local_render_plan.py:455: ★왜 (2026-10-22 뇌전구 신고 2건 · 한 사람): 영상을 끝낸 뒤 같은 작업 폴더에서 편집을 다시 돌리자 서버가 이전 판의
local_render_plan.py:475: ★왜 (2026-10-20~22 뇌전구 render_mix 신고 · 윈도우 3명): 윈도우 env 단계가 onnxruntime 을 onnxruntime-directml 로 바꿔 깐 뒤
longform_agyimage.py:13: (cardnews_agyimage.generate — 지문 캐시·이 PC 공용 agy 그림 줄·거부 판정)으로 바꿔 끼운다. 플로우 간격은 vkclient 공용 줄(5초×5건→20초).
longform_agyimage.py:361: # 윈도우 백신·색인기가 막 쓴 파일을 잠깐 쥐면 os.replace 가 WinError 5 로 실행 전체를 멈췄다(2026-10-17 신고 #131) —
longform_audio.py:268: # 2026-10-17 신고 #128(2명): one block at a time, every run stopped here and asked the author for a «reviewed» tail
longform_contract.py:240: """Caption highlight terms in the form the screen shows (2026-10-17 신고 #119): the same caption_display rule the
longform_contract.py:254: """Narration character range of every authored caption card, computed by code (2026-10-17 신고 #118).
longform_contract.py:688: """One ProductionError carrying every distinct violation found by one validate() pass (2026-10-17 신고 #117 · 23명).
longform_contract.py:709: 2026-10-17 신고 #117: every independent part (each reference, media, sound, block identity / picture / voice /
longform_cutout.py:2:"""인물형 롱폼 누끼 — 서버 일감 `prepare_cutouts` 를 실행기 공용 모듈 nukki.py 로 오린다 (2026-10-17 · 신고 #121).
longform_cutout.py:92: # 윈도우 백신·색인기가 막 쓴 파일을 잠깐 쥐면 os.replace 가 WinError 5 로 실행 전체를 멈춘다(신고 #131 과 같은 부류) —
longform_engine.py:823: # → 사전 점검 결과가 전송 상한 2MiB 를 넘어 «증거 인라인 … 나누지 못했습니다» 로 longform_seed·run 이 멈췄다(2026-10-22 신고 4건).
longform_engine.py:1015: # 2026-10-17 신고 #132: the engine ended with a non-zero code and an empty stderr (5 students · Windows) — a death outside
longform_fonts.py:44: # member_sha256: zip 안 글꼴을 이름이 아니라 내용 지문으로 고른다(2026-10-17 신고 #123 — 공군체 zip 은 안 이름이 CP949 라
longform_state.py:46:# (2026-10-14 운영: runtime_failed «[Errno 13] Permission denied: …status.json» 5건 · 전부 윈도우).
longform_video_treatment.py:36:# ■ 2026-10-22 (신고 #81 · 사장님 «바로 고쳐라») — 화면 처리를 컷마다 필요한 만큼만(서버 video_treatment.look·strength).
nukki.py:3:"""nukki.py — 사람 사진 누끼(배경 지우기)의 **한 자리** — 실행기 공용 모듈 (2026-10-17 · 신고 #121 3명).
nukki.py:25: Cloudflare — 공식(https://developers.cloudflare.com/workers/platform/limits/ · 2026-10-13 확인): Workers 무료 하루 요청 100,000건 ·
nukki.py:29: Replicate — 공식(https://replicate.com/docs/topics/predictions/rate-limits «Rate limits», 2026-10-12 확인): 예측 만들기 분당 600건 ·
nukki.py:30: 그 밖의 API 분당 3000건. 단 «잔액이 바닥에 가까우면 더 센 한도», «크레딧을 받았고 결제 수단이 없으면 초당 1건 · 분당 최대 6건».
nukki.py:31: 수강생 잔액을 알 수 없으므로 **가장 좁은 숫자(분당 6건)** 에 맞춘다 — API 요청(만들기·상태 묻기·판 확인)은 전부 한 줄로 세어
nukki.py:91:REP_GAP_S = 10.0 # 공식 «분당 최대 6건»(머리말) — 60 ÷ 6
politics_legacy_upgrade.py:3:■ 무슨 일이 있었나 (2026-10-04 12:43 배포 · 10-04 하루 148건·23명)
redub_kernel.py:37:exec(compile('FPS = 30\n\ndef qf(d, fps=FPS):\n pass\n return round(round(d * fps) / fps, 4)\n\ndef zoom_vf(i, dur, W, H, Z, subject=None):\n pass\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n if not Z or dur < float(Z["min_sec"]):\n return ""\n rate = float(Z["rate"])\n if rate <
render_kernel.py:8: ■ 왜 있나 (2026-09-05 · `subtitle` `[미분류]` 182건·3명 = 7일 미분류의 72%)
render_kernel.py:17: 수강생에게는 `[미분류] (ValueError)` 만 갔다. 182건이 그렇게 났다.
response_receipts.py:13: 회수 GET 으로 넘어간다(★2026-10-19 신고 #318: 헤더 전 시간 초과는 «못 닿음» 이라 같은 신원 재전송 쪽 — `_post`) — 서버는 응답을 보내기 전에 완료 영수증을 저장하므로 대개 그 자리에서 받는다.
response_receipts.py:115: 신고 #318(2026-10-19): «받지 못했음» 112건 중 15건이 0~43ms 만에 실패했는데 진단에 예외 종류가 없어
response_receipts.py:369: # ★헤더를 못 받은 채 시간이 다 된 것도 같은 신원으로 다시 보낸다(2026-10-19 · 신고 #318).
response_receipts.py:373: # «받지 못했음» 112건 전부 HTTP 응답이 없었고(cf-ray 0 — 1101·1102·5xx 아님) 그중 120초 시간 초과 78건의
runner_caller.py:4: 요청을 보낸 실행기 프로세스는 다른 코드입니다» 로 멈췄다(10-05 24시간 38건·15명 · 사람마다 건수 = 작업 폴더 수). 설치는 작업
runner_caller.py:35: `lsof +D <그 폴더>` 0건(파이썬은 import 한 소스 파일을 열어 두지 않고, 현재 폴더는 그 폴더의 부모다).
runner_caller.py:319: # 사이에 런처가 아닌 프로세스가 끼었거나 명령줄을 못 읽으면 (None, 이유) (Z 검토 2회차 major ①: 윈도우 21명 중 대부분이
runner_caller.py:332: # 예전에는 절대경로만 인정해 공용 폴더가 영영 안 바뀌고 새 작업 폴더마다 같은 멈춤이 되풀이됐다(신고 #53).
runner_files.py:120: "longform_cutout.py", # 인물형 롱폼 누끼 일감 prepare_cutouts(10-17 · 신고 #121) — nukki.py 를 쓴다
subject_agy.py:896:# 학생은 고칠 것이 없어 «다시» 를 눌러도 같은 막힘이었다(최근 24시간 막힌 48명 중 증명 실패 12 · 답 형식 8 · 주인공 못 정함 6 ·
subject_agy.py:897:# 2일 동안 longform_seed 20번 넘게 오간 사람 95명). AGY 에 다시 묻지 않는다(전역 규칙 6-2) — 영수증이 남아 이어 할 때도 그대로 쓴다.
subject_agy_run.py:12: 있으면 AGY 가 영상을 본 뒤 그 파일을 열려다 자동 거부당하고 답이 빈다(저장소 아래 자리 40건 중 9건).
subject_agy_run.py:13: 상위에 규칙 파일이 없는 폴더에서는 35건 중 0건이었고, 작업 폴더 안 읽기는 설정 파일을 고치지 않아도 허용됐다.
subject_agy_run.py:14: · 질문 첫머리에 «이 파일 하나만 봐라 · 다른 파일은 열지 마라» 를 둔다(저장소 아래 자리에서도 12건 중 0건).
subject_agy_run.py:223: 권한 거부된 시도 하나로 멀쩡한 답을 버렸다 · 학생 실측 agy_view_unproven 12명). 10-20 agy 1.4.3 자동 갱신 뒤에는 이 자리가
subject_agy_run.py:920: # 그대로 붙인다(신고 #174 — 예전에는 코드 표 글로 덮어 원인이 지워졌다). 한도처럼 판정 글이 이미 코드 표 글로 시작하면 두 번 적지 않는다.
subject_focus.py:820:#: 구독 AGY 에 이 스키마로 답을 받는다(글자로 감싼 JSON 의 이스케이프 실수 · 2026-10-21 신고 510306). 판정은 여전히 `_decisions`.
subject_focus.py:1151: ★10-23 회원 신고 516558: 실행기가 갱신되어 질문 글(답 스키마)이 바뀌자 지문이 달라져 «반으로 줄인 크기» 를 잃고 같은 컷의
subject_focus.py:1233: # ★1초보다 짧은 컷은 영상 파일을 붙이지 않는다(2026-10-21 쇼핑 신고 510306). Gemini 는 영상을 초당 1장으로 뽑아 보므로
vision.py:20: 정본은 컷튐 위반 77건을 영상으로 판정해 **진짜는 11건(14%)뿐**임을 확인하고
volcano_drive.py:55: 틀린 쪽이 모델이 import 하는 모듈 안에 있었다. `start` 반려 9건/5명 중
volcano_drive.py:56: 실행기 3건이 이 경로였다.
volcano_drive.py:91:# 읽어, 새 판으로 다시 뜬 실행기가 옛 폴더의 식별값을 알리고 서버가 같은 갱신을 또 요구해 멈췄다(신고 10-14·10-18·10-20·10-23:
volcano_drive.py:321: 5일 13건이 멈췄다 — 긴 경로(WinError 206) · 병렬로 받는 다른 팩이 쓰는 중인 파일(WinError 3) ·
volcano_drive.py:382: # 예능 assets 1건) 이미 설치한 팩을 실패로 돌리지 않는다 — 남은 임시 폴더는 무해하다(3.10+ 의 공식 인자 · 3.9 는 그대로).
volcano_drive.py:461: # «Local computation implementation mismatch» 2명(W2-09). 설치한 .py 의 옛 캐시를 지운다.
volcano_drive.py:780: # 경계 검사 «조건부 미정의 변수 0건» 이 이 구조를 증명하지 못했다 · 동작은 그대로).
volcano_drive.py:1009: ★어느 파일이 어떻게 다른지를 돌려준다(2026-10-22 뇌전구 신고 · 윈도우 6건 · 10-13 까지 3D쇼츠 187건): 예전엔 참/거짓만이라
volcano_drive.py:1025: """풀자마자 다른 파일의 사실 — 누가 썼는지 가를 재료(2026-10-23 우팔롬아 신고 2명 · ytclip.py 34785 · newjob.py 18028:
volcano_drive.py:1099: # ★우리 서버의 자산 팩 — 중간에 끊기면 받은 데부터 이어받는다(2026-09-25 B11-코드 SR-19 ② · 209MB 참조 팩 끊김 17회·14명).
volcano_drive.py:1107: # ★응답 머리를 싣는다(2026-10-23): 새 판 주소(v=새 sha)에 바로 앞 판 바이트가 온 신고 15건(10-11~10-22) — 서버 경로로는 못 나온다.
volcano_drive.py:1145: # ★풀자마자(같은 실행 안 · 몇 ms) 다르면 이 실행 밖의 프로그램이 같은 파일에 쓴 것이다 — 신고 10-22 우팔롬아:
volcano_drive.py:1331:# `ref_*` 는 «채널을 통째로 뜯어 규격을 뽑는» 계측기다. 그것을 수강생 480명에게
volcano_drive.py:1333:# `runner` 팩에 22개가 통째로 실려 나갔다(실측: 159명이 받아갔고 94명은 실행기가
volcano_drive.py:1400: `measure_sfx`·`cut_sigs`·`factcheck` 셋이 그렇게 나흘간 92건·48명을 죽였다.
volcano_drive.py:1423: ■ 왜 (2026-08-22, 진단 저장소 304건·66명)
volcano_drive.py:1467: 나흘간 92건·48명을 죽였다(재기는 성공하고 **그 다음 줄**에서 죽는다).
volcano_drive.py:1484: # (`redub_source` 2건, 실측). 서버는 그 값을 경고에만 쓰는데도.
volcano_drive.py:1528: # 마스터에서 91건·11명이 **영상을 다 굽고 난 뒤** 그렇게 멎었다.
volcano_drive.py:1576: # 47명이 530회를 그렇게 돌았다.
volcano_drive.py:1594: # ★앞의 잡음은 건너뛰되 **객체 하나만** 읽는다 (2026-10-17 · 신고 #137). 예전에는 첫 '{' 부터 마지막 '}'
volcano_drive.py:1664: # ★★★**헤더가 아닌 것을 헤더로 내보내지 않는다** (2026-08-26 · 35명·69건).
volcano_drive.py:1669: # bytes-like object, got 'dict'` 로 죽었다(현 배포본 4.6시간에도 8회·6명).
volcano_drive.py:1781: # 상한에 닿은 것만 20건·10명).
volcano_drive.py:1809: 3건). 응답의 carry 는 «이 왕복을 다 하고 잰 값과 함께 다음 호출에 실을 것» 이다 — 합성 왕복의 `voice_state`
volcano_drive.py:2253: ★왜 (2026-10-05 · 원장 W2-14 · 23건·8명): 예전 정지문은 언제나 `review_replies` 를 시켰다. 서버는 답을 정본 칸
volcano_drive.py:2446: 2026.08.19 판 정상). 그런데 최신 판(2026.10.10)에서도 403 이 났고, 갱신해도 못 빠져나갔다(신고 #52 · 9명).
volcano_drive.py:2518: """측정한 사용자 자막·글꼴이 굽기 전에 없거나 바뀌었다 — 구동기가 subtitle 단계로 돌아가 다시 만든다(신고 #32)."""
volcano_drive.py:3263: # 존재하는 이유가 바로 그 경우다(2026-08-17 사진 지시 20건). 09-04 에
volcano_drive.py:3299: # 짜서 **구도가 갈린다** — 7일 87명이 그 자리에서 막혔다.
volcano_drive.py:3836: # 인물형 롱폼 누끼(2026-10-17 · 신고 #121) — 제작표 media.cutout 을 실행기 공용 nukki.py 로(본인 Cloudflare 0순위 · 아니면 Replicate).
volcano_drive.py:3892: # ★`source_candidates` 는 «찾아 봤다» 의 증거다 — 0건이어도 키를 넣는다(§«안 쟀다»
volcano_drive.py:3924: # 죽었다(2026-08-17 · 하루 553건). 자는 그대로고 오가는 양만 줄었다.
volcano_drive.py:4069: # 있어도 돌지 않는 것은 «없음» 이다 — pick_by 가 없는 단계도 같은 판정(신고 #45).
volcano_drive.py:4101: # «Python was not found» rc=9009 포함) 못 돌면 같은 인자로 이 파이썬을 시도한다(2026-10-17 · 쇼핑 env 2건).
volcano_drive.py:4151: # yt-dlp 는 PATH 에 없어도 실행기가 자기 파이썬에 공식 판을 올려 부른다(volcano_run._spawn · 신고 #211).
volcano_drive.py:4197: # 실측(2026-08-18): 마스터 오디오 측정에서 32명이 그렇게 막혔다.
volcano_drive.py:4214: # 20건이 오류 0줄로 통째로 사라졌다(받은 사진 0장). 그 뒤 단계는 "왜
volcano_drive.py:4259: # 배급 실행기를 안 쓰는 클라가 못 지켜 값이 통째로 안 왔다 — 304건·66명.
volcano_drive.py:4352: **완성본이 나왔는지 0명분도 모른다** — 3일 실측으로 `render_mix` 성공
volcano_drive.py:4353: 2,475회·175명 · `stitch_master` 11,017회·129명인데 완주 기록은 **0건**이다.
volcano_drive.py:4431: 실제로 `render_mix` 를 성공한 33명 중 **몇 명이 mp4 를 얻었는지 0명분도**
volcano_drive.py:4441: # 재실행마다 한 줄씩 쌓인다(10-04 강석주 render_mix: 반려 1건 뒤 43초에 feedback 20건). 처음 받았을 때 알렸다.
volcano_drive.py:4461: # '오작동' 으로 쌓였고(전수 1,518건 중 58.5%), 일일 리포트가 그것을
volcano_drive.py:4463: # 실제로 그날 서버 예외는 0건이었다.
volcano_drive.py:4598: # (2026-10-23 인물형 start 3건 «'list' object has no attribute 'get'» — 안내 줄 목록을 묶음으로 읽었다).
volcano_drive.py:5104: 보냈다(재현 run_sim2 · 잠재 338건). 래퍼 상태가 원래 상태 파일보다 **새것**이면 그것을 원래 파일로 옮긴다
volcano_drive.py:5163: 반려했다(반려 원문 26건 전부 source 없음 · 지어낸 client_retry 칸).
volcano_drive.py:5319: ■ 왜 — 윈도우 신고 «[WinError 3] … '\\?\D:\'» 5명(D: 4 · G: 1 — 경로 «내 드라이브» 라 구글 드라이브로 보임)은 `\\?\` 머리 탓이 아니었다.
volcano_drive.py:5793: 했다 — 1주 69건·17명(린박스·뇌전구·쇼핑·3D · 윈도우 `py` 런처·공용 폴더). 실행기는 자기를 다시 띄우는 문
volcano_drive.py:5826: 2026-10-17 실행기 중단 보고 26건·2명(05:5x·08:3x·15:00 — 그날 배포 시각과 겹친다). 예전에는 «같은 명령을 다시 실행하라» 로
volcano_drive.py:5839: 10-03 하루 646명이 2,804번 갈아탔다. 이 판부터 실행기가 `cow-v3` 를 알리면 서버는 정지 대신 새 팩 항목만 준다.
volcano_drive.py:5895: # 신고 #311(10-17~18 · 7명 · 같은 사람이 몇 시간 동안 되풀이): 키가 sha 주소라 저장소 바이트는 선언과 같아야 하는데
volcano_drive.py:6040: # (2026-08-16 실측: 오늘 그 경로로 3명이 막혔다).
volcano_drive.py:6133: # 처방이 «앞 단계 다시» 하나뿐인 멈춤 — 사람에게 시키지 않고 실행기가 그 단계로 돌아간다(신고 #32 자막 → subtitle ·
volcano_drive.py:6281: # 수강생 480명 요청이 한 글자도 안 바뀌어야 한다.
volcano_drive.py:6319: # (`알 수 없는 step: (완료)` 7건·4명). 구동기는 안 불렀지만 사람은 부른다.
volcano_drive.py:6323: # 실패만 알리고 성공은 안 알려서, 서버가 「해낸 사람」을 0명분도
volcano_run.py:115:# 로 실행기가 **9번 죽었다**(8명). 윈도우 콘솔의 기본 인코딩이 cp949 인데 우리
volcano_run.py:251: # ★거부 코드마다 사람이 바로 할 일을 붙인다(2026-10-17 실행기 중단 보고 — 이미지 402 6건·401 7건이 «거절» 한 마디로 끝났다).
volcano_run.py:320: — 전수 1,518건 중 **58.5%**(887건)가 서버 반려문 그대로였다.
volcano_run.py:323: **0건**이었고, 그 5건은 전부 본문에 고치는 법이 적힌 반려였다.
volcano_run.py:445: 같은 자산을 반복해 받아 재니 40회 중 5회, 65 이벤트 중 6건 = 약 9% 였다.
volcano_run.py:674:# 없애도 첫 제출 한 번이 상한을 넘었다(2일 413 보고 606건 · 명화관 31명 · 인물형 18명 ·
volcano_run.py:675:# 린박스 26명). 숫자 목록은 글자 하나로, 같은 열쇠의 사전 목록은 열(column)로 접는다 —
volcano_run.py:718: 2026-09-12 실측: pack v1 배포 뒤에도 새 실행기에서 413 이 났는데(명화관 4명 · 인물형 1명) 413 요청은
volcano_run.py:984: 사본만으로 풀다 멈췄다(7,558건 · 471명).
volcano_run.py:1324: 로 반려한다 — 한 사람이 34분에 45번, 배포 전 24시간 227회·78명. 잃어버린 정보는 되돌릴 수
volcano_run.py:1559: ★**기본값은 `volcano_video` 다.** 수강생 480명 경로는 한 글자도 안 바뀐다 —
volcano_run.py:1616: # 10-02 에 단발로 바꾼 뒤 caps 500 한 번에 작업이 멈췄다(10-04 1,419건·217명 · 배포 뒤 31건·23명).
volcano_run.py:2070: # 못 알아들어 같은 단계를 max_steps 까지 되풀이했다 — 실행 한 번에 서버 요청 40건 · 스스로 안 낫는다).
volcano_run.py:2265: # ★★크게 말한다 (2026-09-02 · 48h 실행기 사용자 93명 중 89명이 옛 팩).
volcano_run.py:2338: # ★★실행기 갱신 응답도 **실행 결과가 아니다** — 위 오류 응답과 같은 부류다 (2026-10-23 · 3D쇼츠 신고 10-22 21:00).
volcano_run.py:2407: ★서명 밖 통로(2026-10-23 · 신고 3건 09:38 뇌전구 sfx `_curl_dl` · 11:48 뇌전구 assets `_curl_download` · 13:59 리센느 `_patch.<locals>.download`):
volcano_run.py:2432: 본문 읽기는 다시 하지 않는다 · 17회·14명). 받는 동안은 `out + ".download"` 에 쓰고 다 받은 뒤에만 `out` 으로 옮긴다(반쪽 파일이 완성본
volcano_run.py:2442: 새 판 주소에 바로 앞 판 바이트가 온 신고가 10-11~10-22 15건인데 서버 경로로는 그 바이트가 나올 수 없어, 응답 쪽 사실이 없으면 못 가린다."""
volcano_run.py:2533: 갈아 끼운 받기 함수가 바이트를 냈다는 뜻이다(10-23 신고 2건: 운영은 같은 시각 20/20 새 판). 그 함수의 이름·파일을 적어 «서버가 옛 판을 줬다» 로
volcano_run.py:2628: # ★없으면 이 실행기 파이썬에 공식 PyPI 판을 한 번 깐다(2026-10-17 영화 리뷰 롱폼 longmovie_seed 2건 — 예전에는 사람에게
volcano_run.py:2658: 렌더 직전 «글꼴을 못 찾는다» 로 멈췄다(48h 4명). 받는 방법은 **전부 서버가 준다**
volcano_run.py:2698: # 그런데 작업 폴더마다 13종을 외부 배포처 7곳에서 다시 받아, 영화 한 편마다 그 배포처 장애(10-16 공유마당 503 · 2명)에 그대로 막혔다.
volcano_run.py:2718: # ★대체 글꼴(2026-10-17 · 영화 리뷰 롱폼 회원 2명 — 공유마당 503 한 번에 seed 가 멈췄다): 그 키의 원래 글꼴(산돌)이 깔려 있으면 쓰이지
volcano_run.py:2822: 93명 중 89명이 옛 팩이었다(이미 고친 결함을 계속 밟는다). 서버가 `_meta.runner_update`
volcano_run.py:3009: ★★왜 (2026-09-02 · 48h 162건·9명): 윈도우 ffmpeg 는 이름에 한글이 든 **없는** 파일을
volcano_run.py:3051:# 롱폼 「사전 점검에서 0건이 걸렸습니다」(09-05 3건·2명 — 점검 JSON 이 깨져
volcano_run.py:3084: # 이 실행기가 지금 도는 파이썬으로 띄운다(2026-10-17 플리 pli_check 2건). 맥·리눅스와 실제 설치본은 그대로 둔다.
volcano_run.py:3147: # 2026-10-17 실행기 중단 보고(유튜브 403 «unable to download video data» 20건·10명) — 최신 yt-dlp(2026.10.10)로
volcano_run.py:3201: keg-only 인 `ffmpeg-full` 이라 깔아도 PATH 에 안 붙는다(env «자막 필터가 없습니다» 맥 2명 · 한 명은 이미 깔아 두었다).
volcano_run.py:3285: # CREATE_NO_WINDOW 자식은 10번 다 정상이었다. 수강생 보고 1주 26건·16명이 전부 «시작 7초 뒤»(옛 재시도 2+5초를 다 써도 실패)였던 까닭이다.
volcano_run.py:3313: # ★이 컴퓨터의 yt-dlp 가 깨졌거나(«No module named 'yt_dlp'» · 2026-10-17 린박스 start 2건) 옛 판이라 유튜브가 막으면
volcano_run.py:3314: # («unable to download video data: HTTP Error 403» · 정치·쇼핑 start 10명 · 신고 #211 — 2026.08.19 판) 사람에게
volcano_run.py:3332:#: · «HTTP Error 403 · unable to download video data» — 신고 #211(2026.03.17 판 403 · 2026.08.19 판 정상 · 09-17 win-01)
volcano_run.py:3409:#: (10-24 쇼핑 shop_footage Vmake 신고 · 10-09 뒤 같은 모양 약 14건). err_gist(첫 줄 + 끝)로 처음 원인과 마지막 예외를 같이 싣는다.
volcano_run.py:3419: 회원 보고 4건(윈도우): «실행 실패: …python.exe» 뒤가 비어 무엇이 왜 죽었는지 알 수 없었다 — 오류 출력만 실었고 종료 코드를 안 실었다.
volcano_run.py:3468: """받은 원본(mkv — yt-dlp 가 어떤 코덱이든 다시 굽지 않고 담은 것)을 probe 가 찾는 mp4 로 만든다 (2026-10-22 신고 #34).
volcano_run.py:3474: (17건·14명). 코덱은 받은 뒤에야 안다 — 그래서 이 자리에서 한 번 재고, 스트림마다 서버가 준 인자 두 벌(복사 · 다시 굽기) 가운데
volcano_run.py:3640: 맥 1건. 그래서 (장치·아이노드·크기·수정 시각)이 그대로이고 변경 시각만 움직였으면 **다시 해시해** 처음 값과
volcano_run.py:3646: # 실행기 롱폼 모듈은 media/ 에 쓰지 않는다(신고 10-18·10-22 맥 · 42분 굽는 사이).
volcano_run.py:3882: # 폭 1 이어도 막아서, 같은 문장 두 블록(같은 캐시 raw)이 14건·1명을 죽였다.
volcano_run.py:4279: # ★for/else 로 쓰지 않는다 — 검사 「조건부 미정의 변수 0건」이
volcano_run.py:4457: # ★이 컴퓨터의 ffmpeg 에 soxr 가 없다(신고 #36 · 렌더가 다 끝난 뒤 마스터에서 죽었다). 사람에게 다른 ffmpeg 를 깔라고
volcano_run.py:4822:# 실물 완성본을 1~2px 깎아 "과잉 제거" 로 보이게 만든다(실측 12건 중 11건이 그것).
volcano_run.py:5323: # ★마지막 시도의 사유를 싣는다 (2026-10-17 · 신고 #150) — 예전에는 무엇이 왜 실패했는지 알 수 없었다.
volcano_run.py:6163: # 답의 모양을 아는 질문은 그 모양(JSON 스키마)을 요청에 싣는다(2026-10-21 쇼핑 신고 510306). 없으면 예전처럼 «답을 JSON 글자로».
volcano_run.py:6418: # ★같은 바이트를 조각으로 흘려 잰다(2026-10-17 강석주 render_plan MemoryError 2건·2명) — 원본 해상도 그림 바이트가 든 묶음을
volcano_run.py:6434: # = TranscriptionPending → 구동기의 «N초 뒤 재개» · 10-21 인물형 롱폼 5db32e 45건/1분: 앞서 띄운 실행이 render_plan 을
volcano_run.py:6704: `urlopen` 이 WinError 123 으로 죽었다(10-04 6건·5명 · 검수 그림 URL). 접두를 벗긴 뒤 URI 로 바꾼다 —
volcano_run.py:7445: # ★실패 사유(종료 코드·ffmpeg 오류 끝)를 버리지 않는다 (2026-10-17 · 신고 #150).
volcano_run.py:8002: # ★어느 파일이 없는지 말한다(2026-10-15) — 예전 문구는 경로가 한 글자도 없어 회원이 원인을 못 찾았다(4일 450건+ 한 사람).
volcano_run.py:8010: # 같은 빠진 칸에 한 번 · render_plan 의 빠진 칸과 같은 길). 2026-10-20 뇌전구 신고 290건: images 가 제공자 거절로 멈춘
volcano_run.py:8087: 하나로 작업 전체가 멈추고, 사용자가 같은 명령을 다시 돌리면 저장된 판정(.photo-qc)으로 같은 정지를 되풀이했다(10-23 7건·4명 중 5건).
volcano_run.py:8777:# «0건» 과 «못 물었다» 를 같은 말로 쓰지 않는다(§«안 쟀다» 와 «재 봤더니 0개»).
volcano_run.py:8937: ★사다리는 위에서부터 — 한 소스가 1건이라도 내면 그 소스는 다음 칸으로 안 내려간다.
volcano_run.py:8994: errors.append({"source": kind, "query": queries[-1], "error": "0건"})
volcano_run.py:9274: 인물명이라, 앞칸이 0건이면 여러 컷이 **같은 사진**으로 떨어진다 —
volcano_run.py:9522: 그 크기 때문에 워커가 **메모리 한도 초과**로 죽었다 — 하루 553건.
volcano_run.py:9697: ★★**모양이 아니면 아무 일도 하지 않는다** (2026-08-16, 수강생 7명이 여기서 죽었다).
volcano_run.py:9882: # ★★**무엇이 걸렸는지 남긴다** (2026-08-26 · 실측 385회·61명).
volcano_run.py:9983: """새 그림 접수(유료 POST) 직전 — 같은 키가 429 로 멈춰 있으면 보내지 않는다(2026-10-20 뇌전구 신고 · 한 사람 198건 → 같은 날 저녁 55편).
volcano_run.py:10111:#: 제공자가 «실패» 로 확정한 그림 작업 뒤 사람이 고를 길(2026-10-17 실행기 중단 보고 11건·7명 — 예전 글은 기록 경로뿐이라 같은 명령을
volcano_run.py:10211: # 사람이 그 슬롯만 «한 번 더 보내기» 를 골랐다(신고 #313 · #208 음성과 같은 길) — 표식은 한 번 쓰고 지운다 · 아래 갈래가 새로 보낸다.
volcano_run.py:10278: # ★402(잔액 부족)도 키에 걸린다(10-21 뇌전구 신고: 한 사람 60편 · 402 를 편마다 다시 보내 44분에 142건 — 429 만 기록해
volcano_run.py:11198:# 이라스토야 그림 **23,422건**의 인덱스가 이미 있다. 네트워크도 키도 필요 없다.
volcano_run.py:11748: 10-20 강석주 images 신고 4건: 네이버 검색 `items[].link`·웹 페이지 `src` 칸에 주소가 아닌 글(화면 틀 묶기 식
volcano_run.py:12324: """완료 여부를 모르는 유료 요청 하나(음성 컷 · 그림 슬롯)를 사람이 다시 보내는 길(신고 #208·#313 · response_receipts.RESEND_MARKER 와
volcano_run.py:12331: """이 예외가 «요청 본문이 제공자에 끝까지 닿지 않았다» 는 증거인가 (2026-10-17 · 실행기 중단 보고 51건·2명 + 음성 9건·5명).
volcano_run.py:12337: 접수 기록이 영구히 막혔다(한 사람 47건). 응답 단계 오류는 여전히 «모름» 이다(중복 과금 방지)."""
volcano_run.py:12597: # 고칠 일» 이다(#175 · 9명 · 한 사람이 15분에 같은 403 으로 23번). 끝까지 그것뿐이면 ASRSetupRequired 로 올려 서버의
volcano_run.py:12616: # 막혔다(08-25 12회·10명). 자리는 `auth_headers` 와 **같은 규약**으로
volcano_run.py:12876: """사진 후보를 담은 제3자 호스트가 그 주소를 HTTP 403 으로 막았다 — 우리 제공자의 거부가 아니라 «이 후보를 못 쓴다»(신고 #33 ·
volcano_run.py:12991: # 어느 이유로 못 받았는지 센다(2026-10-17 강석주 images 5건 — 예전 정지 글은 이유가 한 글자도 없었다).
volcano_run.py:13127: 붙었다** — 오류 0건. 판정은 '있느냐' 가 아니라 '**그 키의 것이냐**' 다.
volcano_run.py:13498: # ★GET 한 장이라 연결이 끊긴 것은 상한 안에서 다시 받는다(2026-10-17 군림보 images 4건 — 한 번 끊기면 편 전체가
volcano_run.py:13823: # 사람이 그 컷만 «한 번 더 보내기» 를 골랐다(신고 #208 · 5xx 는 과금 여부 공식 근거 없음 — 자동으로는 보내지 않는다).
volcano_run.py:13862: # 재요청하지 않습니다» 로 영구히 멈췄다(10-04 8건·7명 · 겹침 7/7). 이 실행은 지금처럼 즉시
volcano_run.py:14034: ★왜: 군림보 회원이 그림 칸(customization.images)에 .mp4 영상을 넣었다(진단 5건·4명). 서버는 파일을 못 보니 확장자로
volcano_run.py:14116: # (2026-10-21 뇌전구 신고: 윈도우 OneDrive 폴더에서 WinError 5 · 09-19~10-21 같은 자리 8건·6명). 예전에는 이 실패도 위
volcano_run.py:14128: 보내 서버가 측정·피사체 근거를 다시 만들게 한다(2026-10-17 실행기 중단 보고 16건·9명 · 예전에는 사람이 patch 를 손으로 보냈다)."""
volcano_run.py:14151: # ★무엇을 하라는지 말한다(2026-10-20 뇌전구 신고 6건 — 경로만 있어 같은 명령을 40초에 7번 되풀이했다). 원본은 회원이
```
