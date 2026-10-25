# 숏템MCP 볼케이노형 재설계 — 노하우는 서버 지시서 한 곳, 회원 PC는 손(실행기)과 눈(회원 Claude) (관제 234·097, 2026-10-21)

> 사장님(10-21): "설계는 페이블이 다시 해서 MCP화 — 지금까지 칼카피 숏템엔진 세션들의 노하우·과정기록을 녹여서 지금처럼(집 PC 결과물과 같은) 영상이 나오게."
> 이 문서는 **설계만**이다(코드 없음). 적힌 사실은 2026-10-21 두 트랙(`.tracks/숏템MCP` d4f6ad7f3 · `.tracks/칼카피숏템엔진` c49663f24)과 볼케이노 setup 응답 견본을 직접 읽은 것이다. 못 읽은 것은 **미확인**으로 갈라 적었다.

---

## 0. 한 줄 결론

**집 PC 제작순서 13단계(`channel/칼카피_제작순서/`)를 단계 진행표(지시서)로 옮겨 라이브 서버(`shopping_shorts`) 한 곳에 두고, 회원 PC 는 서버가 내려 준 `do`(허용된 명령 종류만) 를 실행기가 그대로 돌리고 `review`(실제 시트·후보표·받아쓰기 글을 보고 답하는 판정)만 회원 Claude 가 답한다.** 매 응답은 `message(한 줄) / do / measure / review / traps / next_step / next_payload(서명, 그대로 돌려줘야 함)` 꼴이며, 서버는 `measure`·`review_replies` 를 기존 주인 함수(script_audit·bench_check 판정·source_rule·caps↔tts…)로 검사해 규칙 위반이면 **같은 단계를 반려**한다. 지금 회원 PC 에 깔려 노하우를 새로 자동화하던 `customer.py`(1,075줄)는 ①기계 함수 → 실행기 ②지시문·순서·멈춤 규칙 → 서버 진행표 ③상태기계 → 서버 next_step 으로 **분해**된다. '됐다' = 회원 경로(MCP 경유)로 만든 편이 정답지(집 PC 편)와 원본·제품이 같고 bench_check 6항목·출처 규칙·자막↔목소리를 통과하고 완성본을 눈으로 확인한 상태.

---

## 1. 지금 사실 (실측 — 진단)

### 1-1. 집 PC 제작 라인(정본)
| 무엇 | 어디 | 실측 |
|---|---|---|
| 제작 순서 정본 | 엔진 트랙 `channel/칼카피_제작순서/00~13, 01b, 98, 99` | 18파일 764줄. 단계마다 들어가는 것·명령·판단·멈출 때·사고 |
| 규칙 원문 | `channel/칼카피_시작.md`(238줄) | 맨 위 1~12 · §0-2 드라이브 · §12 얜샷템 · 14-0~14-2 |
| 단계 실행기 | `tools/calcopy/hybrid/run.py`(326줄) STAGES 12개 | 도구 단계(candidates·download·asr·plan·name_check·render·checks·deliver)만 코드. research·screen 고르기·script 는 `StageError` 로 멈추고 브리프 경로를 찍는다 — **사람(Claude 워커) 몫** |
| 브리프(손 판단 지시문) | `hybrid/briefs/{worker_full_piece,research,screen_pick,script,review}.md` | 집 PC 워커가 읽고 손으로 한다 |
| 판단 주인 | `styles.py`(판 설정 `styles/<판>.json` 한 곳) · `placement.place/check_place` · `script_audit.audit` · `bench_check.check`(6항목) · `checks.reuse_violations/aba_violations` · `thumb.face_check` · `render_bench.render`(timeline·StageError '컷이 원본 샷보다 길다') · `name_dict` · `asr_local.transcribe` | 전부 엔진 트랙 |
| 산출물 | `channel/yanshottem/하이브리드_<키>/{조사/조사.md, <판>/대본.json·재료.json·근거.md·자동검사.json·final_sheet_1s.jpg}` | 하이브리드 폴더 29개. 편마다 손 스크립트(`asr_clips.py`·`make_render.py`·`make_stills.py` 등 39개 — 10-17~18 옛 잇썸홈·재미썸홈 시절 것, 지금 벤치 판은 `render_bench` 공용) |
| 정본 편(키치잇판) | `하이브리드_김나영/키치잇판/` | 대본 9줄(N1·O1·N2·O2·O3·N3~N6), facts f1~f7, 재료 컷에 `see`, 근거 = 줄마다 한 줄. ⚠ 제품 영상 0 → 공식 몰 사진 `move` (쿠팡 규칙 **전** 편) |

### 1-2. 회원 PC 라인(지금)
| 무엇 | 어디 | 실측 |
|---|---|---|
| 회원 라인 코드 | 엔진 트랙 `hybrid/customer.py`(1,075줄) — STAGES 12(bench→origin→product→research→material→asr→script→sign→plan→render→check→done) | 집 PC 손 판단을 **처음 자동화**한 것. 지시문 11개(`ORIGIN_READ`…`FINAL_LOOK`)가 코드 안 문자열, 재시도 횟수(스크립트 3·계획 4·눈 검수 2)도 코드 안 |
| 판단 주인(새로 생긴 것, 집 PC run.py 엔 없음) | `origin_offset`(받은 파일 0초 = 원본 몇 초, 잰다) · `shot_table/fill_shot_max`(샷 표·샷 끝 max·주인공 가운데) · `source_rule_bad`(벤치 재료 금지·얼굴 컷 원본만·다른 출연자 샷·남의 영상 장면 전환) · `_caps_vs_tts` · `_title_colors_bad` · `_name_hints/PRODUCT_TALK`(상표 없을 때) · `fingerprint`(자막 지문 대조) | 전부 customer.py 안. **이 함수들은 살린다**(§6 주인 표) |
| 회원 Claude 창구 | `engine/client_llm.py` — `SHORTEM_LLM_QUEUE/<id>/request.json` ↔ `answer.json`, `PROMPT_MAX` 4만 자, `tier_of` 기본 opus | MCP `shortem_ai(list/answer)` 가 넘긴다. 회원 Claude 는 `Read/Bash/Glob/Grep` 막힘(`skills/make/SKILL.md` disallowed-tools) |
| MCP | `shortem_client/server/` — `index.js` 도구 9개(setup·presets·profile·make·ai·job·feedback·login·settings) · `make_flow.js`(hybrid 입구 `make.py --json hybrid start/approve/resume/status`, 진행 `stage` 한 줄) · `firewall.shape`(금지 키 12·숫자 지우기·경로 가림) · `engine_bridge.js`(동봉 파이썬으로 make.py 띄우기, 키 환경변수) · `preset_rent.js`(AES-GCM 꾸러미, `.rented` 표식, `TECH_DIRS` hybrid·yanshot 코드까지 편마다 임대) · `local_settings.js` · `deliver.js`(텔레그램·드라이브) · `logins.js`(쿠키) · `updater.js` | 설치본 1.0.4~1.0.10 라이브. **하이브리드 라인 든 판 미배포** |
| 서버 | `shopping_shorts/claude_portal.py`(1,497줄) — license·lease·assets·rent·update·install·feedback·anomaly·home / app.py 라우트 `/api/claude/*` 12개 + `/api/claude/me/*` 7개 | 제작 지시 라우트 **없음**. 스위치 `claude_portal_enabled` 등 admin |
| 시험 | `shortem_client/test/` — `fake_server.js`(계약 모양 가짜 서버, FAKE_RENT_*) · `live_episode.js`(설치본 + 서버 + `claude -p opus` 완주) · `hybrid_dev_run.py`(엔진만, Claude CLI 가 AI 답) · `e2e_make.js` · pytest `test_claude_portal.py` 21 | 하이브리드 편을 **MCP 경유로 끝까지 돈 기록 없음**(hybrid_dev_run 으로만 2편: 이미도·선우용여 — 둘 다 눈 검수 미통과) |
| 기술 꾸러미 | 숏템MCP `tools/claude_portal/preset_pack.py` `TECH_CODE` 11모듈 + `TECH_DOCS`(제작순서 02·03·04·05·07·08·11) | 코드·문서가 회원 PC 에 풀린다(암호화 꾸러미지만 키가 같은 PC) |

### 1-3. 왜 집 PC 는 되고 회원 PC 는 처음처럼 틀리나 (98_오류기록 #18 · handoff 10-21)
- 집 PC: Claude 워커(오푸스)가 브리프를 읽고 **영상·시트를 직접 열어** 원본 판정·제품 사진 대조·컷 자리·크롭·원음 시작 시각을 손·눈으로 정한다. 그 "왜 그렇게 골랐나"는 조사.md·근거.md 에 결과만 남고 **규칙으로는 거의 문서화되지 않았다**(제작순서 02~08 이 그 첫 문서화).
- 회원 PC: 그 손 판단을 `customer.py` 가 코드+AI 요청으로 새로 짰다 → 처음 자동화할 때마다 새 오류(98_오류기록 10-21 하루 19건: 별 전환·장갑 손·영어 제목·대조 자리·원본 시각 20초 어긋남·눈곱→눈꽃·자막≠목소리 …).
- 구조 문제 둘: ① **노하우가 회원 PC 코드에 있어** 고칠 때마다 설치본·꾸러미를 다시 내야 한다 ② 회원 Claude 가 **엔진이 만든 질문 하나에 JSON 하나**만 답하고 끝이라, 집 PC 워커처럼 "다시 보고 고치는" 고리가 코드 안 재시도 횟수(3·4·2)에 갇혀 있다.

### 1-4. 볼케이노 응답 견본에서 가져올 것(실측 `volcano_setup_response.json`)
`status / message / do[{cmd, argv_candidates…}] / measure[{as, from, unit}] / next_step / then_call_with[] / traps[] / carry[] / review{policy, client, replies, budget} / review_policy / review_client / next_payload / next_payload_note / payload_discard / author_view`.
- `do` 안에 **코드가 통째로 실린다**(env_probe 4.2만 자) — 실행기는 껍데기.
- `review` 는 회원 Claude 가 실제 자료를 보고 `review_replies` 로 답한다(`review_client: claude`).
- `next_payload` 는 "한 글자라도 다르면 반려" + `measure` 는 "새로 재서 넣어라"(옛 값 재전송 감지).
- `traps` = 그 단계에서 빠지는 함정 문장. `carry` = 다음 호출에 꼭 실어야 할 키.
- 약점(18일 설계 §1-3 실측): argv 허용 목록 없음 → 서버가 임의 명령 가능 / 응답에 지시·반려 규칙 원문이 다 실려 역분석됨. **우리는 둘 다 피한다**(§2-3·§4).

---

## 2. 응답 규약 — 우리 판 볼케이노형

### 2-1. 호출 한 번의 모양
```
회원 PC → 서버  POST /api/claude/step
  { preset:"연예인상품+후기형", step:"origin", payload:<next_payload 그대로>,
    measure:{…서버가 시킨 측정의 실제 값…}, review_replies:{<review.id>: <회원 Claude 답 JSON>},
    source?:{kind:"youtube", url} }       # start 때만
서버 → 회원 PC
  { status:"execute"|"review"|"wait_user"|"reject"|"stop"|"done",
    message:"원본 영상 찾는 중 → 다음: 제품 확인",          # 회원에게 보이는 한 줄(이것만 전한다)
    stage:{no:2, total:13, text:"원본 영상 찾는 중"},
    do:[{cmd:"ytdlp_bench", url, out:"bench/"}, {cmd:"sheet", src:"bench/bench.mp4", fps:1, tile:"6x5", out:"bench/sheet.jpg"}, …],
    measure:[{as:"bench_info", from:"cmd:ytdlp_bench", unit:"json"}, {as:"bench_asr", from:"cmd:asr", unit:"segments"}],
    review:{id:"origin_read", model:"opus", show:["bench/sheet.jpg", "bench_info.title/desc", "bench_asr"],
            ask:"이 시트에서 '출처:' 글자·방송 로고·이름표를 읽고, 말하는 사람과 제품 낱말을 적어라 …",
            answer_schema:{celeb:"str|불명", source_label:"str", product_words:["str"], is_shopping:"bool", queries:["str"]}},
    traps:["설명란 '영상 속 제품'은 그 채널의 파트너스 상품일 뿐 — 근거 아님", …],
    reject?:{why:["…"], fix:["…"]},                              # 같은 단계 반려일 때
    next_step:"origin", then_call_with:["payload 는 next_payload 그대로", "measure 는 새로 잰 값", "review_replies.origin_read 를 넣어라"],
    next_payload:"<불투명 문자열: base64(JSON)+HMAC>" }
```
- **`do` = 허용 목록 안의 명령 종류(cmd)와 인자만**. 코드·argv 를 보내지 않는다(볼케이노 약점 회피, 18일 설계 §7-5 유지). 실행기가 cmd→함수로 푼다(§3-3).
- **`measure`** = 실행기가 do 결과에서 뽑아 보내는 값(JSON·숫자·글). 그림·영상은 서버로 **안 보낸다**(회원 Claude 가 PC 에서 본다). 크기 상한 200KB(받아쓰기 글·후보 표·샷 표·자동검사 결과가 가장 크다 — 10-21 실측 대본 질문 1.7만 자·제품 판정 1.8만 자 참고).
- **`review`** = 회원 Claude 몫. `show` 는 PC 에 있는 파일·measure 이름(실행기가 그림은 이미지 내용으로, 글은 본문으로 MCP 에 싣는다 — 지금 `engine_bridge.requestContent` 그대로). `ask` 는 **판정 질문**(규칙 원문·판 설정·임계값은 싣지 않는다, §4). 답은 `answer_schema` 꼴 JSON. 틀린 꼴이면 서버가 `reject` 로 같은 review 를 다시(지금 client_llm RETRIES 2 와 같은 뜻).
- **`next_payload`** = 서버가 만든 상태(sid·step·done 목록·measure 요약 해시·review 답 해시·판 이름·회원 cid) + HMAC(서버 비밀). 회원 PC 는 **그대로** 되돌린다. 다르면 `400 payload_tampered` 반려. 옛 measure 재전송은 서버가 measure 해시로 감지해 "새로 재라" 반려.
- **진행 안내 = `message` 한 줄**("OO 완료 → 다음 OO"). firewall 은 `message`·`stage`·`review.ask/show`·`reject.why/fix` 만 모델에 보이고 `do`·`measure` 는 실행기가 먹는다(모델이 보지 않는다).

### 2-2. 상태(status)와 MCP `need` 대응
| status | 뜻 | MCP need(회원 Claude 가 할 일) |
|---|---|---|
| execute | do 만 있다 — 실행기가 돌리고 다음 호출 | `wait` → 실행기 자동(모델 개입 0) |
| review | do 끝난 뒤 회원 Claude 판정이 필요 | `ai` → `shortem_ai(list)` 로 보고 `answer` |
| wait_user | 회원 사인(대본) 또는 회원이 줄 것(원본 URL) | `approve` / `input` |
| reject | 같은 단계 반려(사유·고칠 방향) | 실행기가 자동 재시도(review 가 걸렸으면 `ai` 로 다시) · 횟수 초과면 `fail` |
| stop | 그 편은 만들지 않는다(제작순서 '멈출 때') | `fail{why, fix}`(예 "연예인 본인 원본을 못 찾았습니다 — 원본 주소를 알려 주세요") |
| done | 완성 | `done{video}` |

### 2-3. 실행기 cmd 허용 목록(초안 — T3 에서 확정, 인자 스키마는 zod/pydantic 으로 고정)
`ytdlp_meta` · `ytdlp_bench` · `ytdlp_subs` · `ytdlp_channel_list` · `ytdlp_search` · `ytdlp_section`(m3u8 구간) · `sheet` · `frame` · `crop_frames` · `silence` · `asr`(engine=auto|speechmatics|whisper) · `fingerprint`(벤치 말 ↔ 자막) · `origin_offset` · `shot_table` · `fill_shot_max` · `lens`(회원 크롬) · `coupang_search`(키→크롬) · `naver_text` · `screen_search/screen/download` · `name_check` · `render_bench`(plan|render) · `bench_check` · `source_rule_scan`(장면 전환 프레임 차) · `caps_vs_tts` · `title_colors` · `script_audit`(PC 사본 — 서버 판정이 정답, §5) · `deliver` · `cleanup`.
모두 **지금 있는 함수**(customer.py·screen.py·render_bench·bench_check·asr_local·coupang_customer)의 얇은 포장이다. 새 판단 없음.

---

## 3. 지시서를 어디에 두나 — 두 안 비교와 추천

| | A. 라이브 서버 `shopping_shorts` 신규 라우트 `/api/claude/step` | B. 회원 PC 에 암호화 임대 꾸러미(지금 `preset_rent` TECH_DIRS 확장) |
|---|---|---|
| 노하우 자리 | 서버 한 곳(진행표·지시문·반려 규칙·판 설정 임계값) | 회원 PC 에 풀린다(AES 지만 복호 키가 같은 PC — 18일 설계 §7-4 "완전 방지 불가") |
| 고칠 때 | 서버 코드·데이터만 고치면 **모든 회원이 다음 호출부터**(설치본 재빌드 0) | 꾸러미 재빌드 → 서버 업로드 → 다음 편부터. 코드는 설치본 재빌드·자동 업데이트 |
| 반려·검사 | 서버가 measure·review 답을 주인 함수로 판정 → 회원 PC 가 검사를 건너뛸 수 없다 | PC 가 스스로 검사 → 건너뛰기·개조 가능 |
| 서버 부담 | 편당 호출 ≈ 13단계 + 반려 ≈ 25~40회, 요청 ≤200KB·응답 ≤40KB, CPU = JSON 검사(script_audit 류 ms 단위). **영상·그림·키 0** | 0 (라이선스·임대만) |
| 서버 죽으면 | 새 편 못 시작, 진행 중 편은 다음 단계에서 멈춤(payload 는 PC 에 있어 서버 복구 뒤 이어 감) | 영향 없음 |
| 라이브 배포 | **필요**(0순위-A1c 승인) — 로컬 시험 서버에서 끝까지 검증 뒤 | 서버 변경 거의 없음 |
| 사장님 10-19 원칙(무거운 일·키 = 회원 PC, 서버 = 화면·로그인·임대·상태) | **맞는다** — 지시서 왕복은 '상태' 범주(작은 JSON). 무거운 일(받기·렌더·받아쓰기·크롬)·키는 그대로 회원 PC | 맞는다 |
| 볼케이노형 원칙("노하우 서버 한 곳") | **맞는다** | 어긋난다(노하우가 PC) |

**추천 = A.** 근거: ① 사장님 재설계 지시의 핵심이 "노하우 한 곳 + 회원 PC 는 손·눈"이다 ② 10-21 하루 19건처럼 **노하우는 매일 바뀐다** — B 는 바뀔 때마다 1GB 설치본·꾸러미를 다시 내야 하고 10-21 처럼 "하이브리드 라인 든 판 미배포" 상태가 반복된다 ③ 서버 부담은 작은 JSON 왕복뿐이라 10-19 원칙 안이다(실측치는 T6 에서 편당 호출 수·바이트를 재서 이 표를 고친다).
A 에서도 PC 에 남는 노하우: 렌더러·배치 코드(`render_bench`·`placement`)와 실행기. 이건 '손'으로 본다 — 판 설정(`styles/<판>.json`, 배치 counted 포함)이 없으면 그리지 못하고, 판 설정은 **렌더 단계 do 에만 실려 편이 끝나면 지운다**(지금 `preset_rent` 의 channel 임대 방식 그대로, 코드 임대 `TECH_DIRS` 는 §9 에서 뺀다).

지시서 데이터의 git 주인: 엔진 트랙 `tools/calcopy/hybrid/flow/`(단계 진행표 — 제작순서 문서와 **같은 커밋**에 고친다, 칼카피_시작.md 11번 규칙과 같다) → 라이브 반영은 장부처럼 `tools/calcopy/preset_publish.py` 한 곳(§0-1 5-1). ⚠ **미확인**: 라이브 main 에 `tools/calcopy/hybrid/*`(styles·script_audit·placement)가 있는지 — 10-19 handoff 는 틀 폴더(`channel/*/preset/**`)만 main 으로 옮겼다고 적혀 있다. T0 에서 `git -C <main> ls-files tools/calcopy/hybrid` 로 확인하고 없으면 preset_publish 옮길 목록에 넣는다.

---

## 4. 내부 노출 금지 ↔ 회원 Claude 가 실제 자료를 봐야 함 — 양립

| 보이는 것(회원 Claude·채팅) | 안 보이는 것 |
|---|---|
| `message` 한 줄 · `stage` | do·measure·next_payload(실행기만) |
| `review.show` 의 **그 편 자료**: 벤치/원본 1초 시트, 제품 장면 자른 사진, 쿠팡 후보 표(이름·대표 이미지), 받아쓰기 글, 샷 표, 계획 시트, 완성본 1초 시트, 자동검사 결과 ○/× | 판 설정 원문(배치 비율·좌표·색)·규칙 원문(칼카피_시작.md)·제작순서 문서·임계값 숫자·엔진 파일 경로 |
| `review.ask` = **판정 질문**("출처 글자를 읽어라", "쿠팡 후보 중 포장·로고·모양이 같은 것의 번호", "컷마다 대사와 화면이 맞나") + 답 꼴 | "왜 그 규칙인지"·규칙 번호(A3·B17)·사장님 결정 원문 |
| `reject.why/fix` = 고칠 방향 문장("3번 줄 자막이 읽는 말과 다르다 — 자막을 읽는 말 그대로") | 걸린 규칙 id·임계값 |
| 회원 사인용 대본(제목·줄) | 재료.json·근거.md·조사.md 본문 |

- 회원 Claude 도구는 지금처럼 `Read/Bash/Glob/Grep` 금지(SKILL.md). 자료는 **MCP 응답 안 이미지 내용·글**로만 받는다(`requestContent` 방식). 파일은 `~/.shortem/jobs/<sid>/` 에 남지만 도구가 열어 주지 않는다(18일 설계 §4-4).
- `review.ask` 글은 서버가 만든다. **숨길 수 없는 것**(18일 §7-4): 질문 글과 시트는 채팅 로그에 남는다 — 질문은 "무엇을 보고 무엇을 답하나"까지만 쓰고 판 설정·비율·사장님 결정 원문은 넣지 않는다. 검사 = `firewall` 금지 키·`secretNumbers`(판 설정 숫자) 그대로 + 서버 쪽 `ask` 생성기에 같은 검사(T2 시험: 모든 단계 ask 에 금지 키·판 설정 숫자 0).
- 지금 `customer.py` 의 `brief_text("channel/칼카피_제작순서/07_대본.md" …)` 처럼 **문서 원문을 요청에 통째로 붙이는 것은 없앤다**(07_대본 §4 미나 오독 표처럼 회원 Claude 가 알아야 품질이 나는 것은 '판정 질문 안 목록'으로 옮긴다 — 예: 대본 질문에 "미나가 틀리게 읽는 말: 따라 사 봤는데요→…" 를 **대체어 목록**으로만).

---

## 5. 13단계 진행표 — 단계마다 do / review / 서버 검사 / traps / 멈춤 / 한 줄

표기: **do** = 실행기(§2-3 cmd) · **review** = 회원 Claude 판정(실제 자료) · **검사** = 서버가 measure·review 답을 판정(주인 함수 §6) · **traps** = 98_오류기록(#)·제작순서 함정 · **멈춤** = status stop(그 편 안 만듦) · **한 줄** = customer.STAGES 글.

| # | 단계 | do(실행기) | review(회원 Claude 가 보고 답하는 것) | 서버 검사(반려 조건) | traps | 멈춤 | 한 줄 |
|---|---|---|---|---|---|---|---|
| 0 | setup | `env_probe`(ffmpeg·yt-dlp·python·위스퍼 모델·크롬·디스크 여유·키 유무: 타입캐스트/일레븐랩스/쿠팡/스피치매틱스) | — | 판에 필요한 키(키치잇판=일레븐랩스) 없으면 reject{fix:"설정 화면 소리 칸에 일레븐랩스 키"} · 디스크 < 편당 1.5GB 면 reject(00_공통) | 키 값은 지문만 · 한글 작업 폴더는 볼케이노 도구만 문제(우리 파이프라인은 돈다) | — | 준비 확인 중 |
| 1 | 소재 | 회원이 준 벤치 쇼츠 URL(`source`) → `ytdlp_bench`(720p+·info.json·자동자막) · `sheet` · `asr`(벤치 말) | `source_read`: 시트+제목·설명·받아쓰기 → `{is_shopping, celeb|불명, source_label, product_words, queries, channel_hint}` | is_shopping=false → stop · celeb 불명 → wait_user("누구 영상인지") | 설명란 '영상 속 제품'=파트너스 링크, 근거 아님(02 §2) · 사람 이름은 화면 글자로만(12) | 쇼핑 소재 아님·의약품 | 영상 확인 중 |
| 2 | 원본 찾기 | `ytdlp_search`(고정 검색어 이름·이름+출처·이름+꿀템 먼저, `youtube:lang=ko`) · `ytdlp_channel_list`(본인 채널 ≤300편) · `ytdlp_subs`(후보 16편, 검색·채널 번갈아) · `fingerprint` · 확정 뒤 `ytdlp_section`(m3u8 ±90초) · `origin_offset` · `ytdlp_meta`(남의 쇼츠 출처 글자 `_peer_labels` 5편) | `origin_titles`(채널 목록 120편씩 → 후보 id ≤8) · `origin_pick`(지문 맞은 후보 ≤5 + 벤치 시트 → `{origin_id, self_spoken, matched[]}`) | 본인 채널 후보를 검색 후보보다 앞에 두었나(서버가 정렬) · `matched` ≥2줄 아니면 reject("두세 줄 이상 맞아야 확정") · 원본 업로드일 > 벤치 업로드일이면 reject · `origin_offset` 이 잰 값 없이 guess 면 reject("오프셋을 재라") | #4 제목 묶음 4만 자 · #5 대조 자리 밀림 · #6 영어 제목 · #7 검색어 흔들림 · #8 본인 채널 1순위 · #9 남의 쇼츠 출처 글자 · #16 원본 시각 20초 어긋남 · 요청 간 쉼(10-21 not a bot) | 원본 못 찾음 → stop{fix:"연예인 본인 원본 주소"} · 말한 사람이 본인 아님(정보석) | 원본 영상 찾는 중 |
| 3 | 제품·쿠팡 | `sheet`(원본, 지문 맞은 초 −25 부터 36초) · `crop_frames`(고른 장면 2~4장, 전체 모양) · `lens`(회원 크롬, 여러 장 hits 겹침) · `coupang_search`(파트너스 키 → 없으면 크롬) · 없으면 `naver_text`(연예인+제품 낱말) → 다시 `coupang_search` → 그래도 없으면 같은 종류 후보 | `product_pick`(원본 시트+벤치 시트 → 자를 장면 t·crop, 쿠팡 검색어) · `product_same`(자른 사진 ↔ 쿠팡 후보 이름·대표 이미지 → `{product_id, name, category, mode:exact}`) · 상표 없을 때 `product_named`(포털 글 근거) · `product_best`(alt: 같은 종류·후기 많은 것 → mode alt) | product_id 없으면 stop · category 의약품·의료기기 → stop · mode 를 서버가 기록(대본 단계 `PRODUCT_TALK` 에 쓴다) · 장면 2장 미만이면 reject("전체 모양 여러 장") | 파트너스 API 에 명품·단종품 없음(03) · 남의 설명란 파트너스 상품 근거 아님 · #10 상표 안 보임 → 이름 찾기 → alt · #11 후기 수 칸 없음(alt 대본에 '후기 제일 많은' 금지) · 출처 줄 중간에 바뀌는 벤치 = 원본 둘(박세리) | 쿠팡에 같은 종류도 없음 | 제품 확인 중 |
| 4 | 조사 | `ytdlp_subs`(원본 자동자막 → 받은 구간 안 낱말·초) | `research`(원본 URL·오프셋·지문·자동자막·제품 판정·사진 → `{조사_md, keywords, queries, exclude, spans[{a,b,tag}], facts{f1..}, stop?}`) — 웹 검색은 회원 Claude 가 한다(WebSearch 허용 — **미확인**: 지금 SKILL.md allowed-tools 에 WebSearch 없음, T4 에서 추가) | 조사_md 에 §0 결론·§1 출처표·§2 원음표·§3 사실표(f번호+출처 URL)·§4 금지품목·§5 검색어·§6 확인 못 한 것 머리글 6개 있나(없으면 reject) · facts 마다 URL 또는 원본 초 없으면 reject · spans 가 받은 파일 길이 밖이면 reject · 질병명·효능 낱말(판 설정 `_common` forbid)이 facts 글에 있으면 reject | 다른 회사 숫자 금지(이혜정 250만 개) · 효능 해시태그 따라 쓰기 금지 · 남의 말(PD·가족) 원음 제외 · −35dB 웅얼거림 제외 | 전문의약품·의료기기 효능 | 자료 조사 중 |
| 5 | 재료 영상 | `screen_search`(yt-dlp 만, exclude) · `screen`(360p 토막 시트·메타) · `download`(chosen 구간 m3u8) · 원본 안 제품 근접 장면은 3단계 사진·원본 파일로 이미 있음 | `screen_pick`(후보 시트 ≤8 + 메타 → `{chosen[{id, why, sections}], rejected[]}`) | chosen 에 그 연예인이 나오는 영상(why 에 연예인)·벤치 id 가 있으면 reject · max_height<720 이면 reject · chosen 0 이고 쿠팡 대표 이미지도 없으면 stop · chosen 0 이면 서버가 "쿠팡 사진 move 컷" 모드 표시(05 재료가 모자랄 때) | #1·#2 남의 리뷰 영상 전환·장갑 손 → 원본 제품 장면 먼저 · m3u8 구간 받기 · C 가득 차면 json 0바이트 · 세로 쇼츠 608×1080 · id 가 `-` 로 시작 | — | 재료 영상 모으는 중 |
| 6 | 받아쓰기 | `asr`(spans 마다 wav → 스피치매틱스(회원 키) → 없으면 위스퍼; 키 있으면 둘 다 = 교차) · `silence`(−26/−30/−32/−38dB 경계) · `shot_table`(원본 샷 표·샷마다 누가) | `asr_check`(두 받아쓰기 + 원본 자막 + 그 구간 시트 → 조각마다 `{said, a, b, speaker_is_celeb, keep}`) | 두 모델 다 못 알아들은 조각 keep=true 면 reject · speaker_is_celeb=false 인데 keep 이면 reject · 스피치매틱스 없을 때는 결과에 `asr_single:true` 표식(§7) | #12 눈곱→눈꽃(문맥 교정은 대본 단계) · #13 방송 카메라 1~2초마다 바뀜 → 샷 표 · 위스퍼는 numpy 배열로 | — | 원음 정리 중 |
| 7 | 대본·재료·근거 | `fill_shot_max`(답 받은 재료에 샷 끝 max·주인공 가운데) · `caps_vs_tts` · `title_colors` · `source_rule_scan`(남의 영상 컷 장면 전환) · `script_audit`(PC 사본, 참고용) | `script`(판 규칙 **요약 질문**(박자·줄 수·어미·길이·CTA 없음·금액 없음·말투 '따라 사 봤는데'·미나 대체어 목록) + 조사.md + 원음 받아쓰기 + 재료 파일 시트 + 샷 표 + PRODUCT_TALK(mode) → `{대본, 재료, 근거_md}`) | **서버 `script_audit.audit(대본, 판)` ok** 아니면 reject(사유를 방향 문장으로) · `_caps_vs_tts` 0 · `_title_colors_bad` 0 · `source_rule_bad` 0(벤치 재료·얼굴 컷 원본 밖·다른 출연자 샷·장면 전환은 PC `source_rule_scan` measure 로) · 근거 줄 수 = 대본 줄 수 · tts 줄 끝 문장부호 · 숫자·영문은 읽는 대로(A11) · 같은 소스 ±3초 재사용(`checks.reuse_violations`)·A-B-A(`aba_violations`) 0 · 반려 **5회**까지(지금 3회 → 집 PC 워커처럼 고쳐 가게 늘린다, 18일 설계 MAX_SCRIPT_TRIES 5 와 맞춤) | #17 자막≠목소리 · #19 caps 꼴 둘 · tts_text 칸 안 읽힘(07) · 조사 없는 명사 연속(A13) · 길이 넘치면 배속 아니라 글 줄이기 | — | 대본 쓰는 중 |
| 7' | 회원 사인 | — | — (회원이 본다: 제목·줄만) | 사인 전 TTS·렌더 0(비용) · 고치라 하면 7 로(회원 요청 글을 script review 에 덧붙임) | — | — | 대본 확인을 기다립니다 |
| 8 | 계획 | `render_bench plan`(TTS 0) · 멈추면(컷이 샷보다 김) 사유 measure · `plan_sheet`(컷마다 렌더러와 같은 크롭) · `source_rule_scan`(시간표 컷) | `plan_look`(계획 시트 + 대본 + 재료 + 샷 표 → `{ok, problems, 재료|null}`) — A3 대사↔화면 · A13 남의 손 · A5 남의 글자·자막 띠 · T1 0초 얼굴 · A-B-A · 주인공 가운데 | ok=true 인데 PC measure(샷 초과·source_rule) 가 걸리면 reject · 고친 재료가 또 걸리면 reject(**4회**, 지금과 같음) · 재료 컷 ≥1.2초·끝 ≥1.5초·컷 중앙 벤치 1.0~1.3초 범위 | #13·#14 샷 넘는 컷·주인공 가운데 · 'face' 크롭은 높이 전체라 박힌 자막이 들어온다 → 숫자 crop · 10-21 세 번째도 자막 띠 남은 채 넘어감 | — | 장면 맞추는 중 |
| 9 | 이름 발음 | `name_check`(판 목소리로 — 미나면 **일레븐랩스 회원 키**, 지금 name_check.py:56 은 타입캐스트 고정 = 결함 T3) → 받아쓰기 → `name_dict` 적용 | — (받아쓰기가 둘 다 틀리면 `name_fix` review: 표기 후보 고르기) | 사전(`name_dict.json`)에 통한 표기가 있으면 0초 · 서버가 사전 주인(회원 PC 결과를 서버 사전에 올리지 않는다 — 회원 키로 합성한 결과는 그 편에만) | 최은경→최화정·이영자→미영자 · 이름 구절 ≤6회 | — | 이름 발음 확인 중 |
| 10 | 렌더 | `render_bench render`(판 설정은 이 단계 do 에 실어 보내고 편 끝나면 지움 · TTS 1회 · 나레 캐시) · 멈추면 사유 measure → 8 로 되돌림(재료 고침 review) · `source_rule_scan`(실제 시간표) | — | 로그 measure: 어느 줄 atempo > 판 상한(미나 1.35·타입캐스트 1.25)이면 reject · 샷 초과 3회면 stop(지금과 같음) | 줄 끝 문장부호 없음 · 고정 배속 더 빠르게 금지 · 서버 렌더 금지(회원 PC 에서만) | — | 목소리·영상 만드는 중 |
| 11 | 검사 | `bench_check`(6항목 → 자동검사.json measure) · `asr`(완성본 전체 + 짧은 줄 따로) · `sheet`(1초) · `source_rule_scan`(최종) · 틀 빠짐 검사(사진 컷 경계 0.04초, 11 '걸리면') | `final_look`(1초 시트 + 자동검사 ○/× + 받아쓰기 글 + 대본 → `{ok, problems}`) — 틀·제목·자막 자리·출처 줄 · A3 · 남의 얼굴·손·글자 · 0초 얼굴 · 장면 전환 · 받아쓰기 ↔ 대본 글자(이름·브랜드) | **6항목 전부 ○** 아니면 reject(얼굴×→8 로, 음량×→10 로, 길이×→7 로) · 받아쓰기 줄 일치율(§8 기준) 미달이면 reject(표기 고쳐 9·10) · look.ok=false 면 재료 고침(**2회**) 뒤 10 → 그래도 아니면 stop(지금은 done 으로 넘김 #15 → 바꾼다) | #1 1초 시트에 0.5초 전환 안 보임 · #15 ok 아닌데 done · 틀 빠짐(yuvj420p) · 짧은 질문 줄 잘라 듣기 · 같은 꼴 결함 전체 재검사 | 세 번 고쳐도 눈 검수 × | 완성본 검사 중 |
| 12 | 납품 | `deliver`(완성본 폴더 복사 → `deliver.js` 텔레그램·구글 드라이브 데스크톱 폴더 — 집 PC robocopy/G: 규칙은 우리 운영용, 회원은 deliver.js 한 곳) | — | 완성본 크기 = 복사본 크기(measure) · mp4 만(jpg 안 보냄) | 50MB 넘으면 텔레그램 알림만 · 같은 파일 두 번 안 보냄 | — | 저장 중 |
| 13 | 정리 | `cleanup`(src·screen·asr·render 조각 삭제, 완성본·대본·근거는 남김) · 서버에 **요약만** 기록(sid·판·원본 id·쿠팡 번호·자동검사 ○/×·look ok·길이·LUFS — 영상·대본 본문 안 올림) | — | — | 삭제 전 복사본 크기 확인 | — | 완성 |

보조 흐름: 회원이 "다음꺼 만들어줘"(제작순서 01 A/B 소재 고르기)는 **T9 후순위** — 서버가 키치잇 인기순(`yt-dlp --flat-playlist`)·이미 만든 인물+제품 제외 목록을 `wait_user{choices}` 로 준다(지금 handoff ⏭ 4).

---

## 6. 판단 주인 · 결과물 검사 표 (0순위-B·C — 새로 적지 않고 부른다)

| 판단 | 주인 함수(지금 자리) | 볼케이노형에서 부르는 곳 | 결과물 검사 |
|---|---|---|---|
| 판(채널) 설정·목소리·길이·배치 비율 | `hybrid/styles.py load/brief` + `styles/<판>.json` | 서버(진행표 질문·검사 임계값) · 렌더 do 에 실어 PC(편 뒤 삭제) | `styles.py list` 출력 = 진행표 숫자(시험) |
| 대본 규칙 | `hybrid/script_audit.audit` | **서버**(7단계 검사) · PC 사본은 참고 | 정답지 대본 ok · 망가뜨린 대본 reject(mutation) |
| 자막↔읽는 글 | `customer._caps_vs_tts` | 서버 | 선우용여 N3 꼴 reject |
| 제목 색 | `customer._title_colors_bad` | 서버 | 둘째 줄 hi reject |
| 재료 출처 규칙 | `customer.source_rule_bad`(③ 장면 전환은 영상이 필요 → PC `source_rule_scan` measure, ①② 는 서버) | 서버+PC | `test_source_rule.py`(엔진 트랙) 그대로 |
| 원본 파일 시작 시각 | `customer.origin_offset` | PC 실행기 → measure, 서버는 '잰 값인가' 검사 | 선우용여 339.8 재현 |
| 원본 샷 표·샷 끝·주인공 가운데 | `customer.shot_table/fill_shot_max` | PC 실행기(얼굴 모델 onnx 동봉) | 샷 넘는 컷 0 |
| 지문 대조 | `customer.fingerprint` + `yanshot.common.vtt_words` | PC 실행기 → measure | 김나영 257.6·269.9 재현 |
| 자막·효과 배치 | `placement.place/check_place` | PC(render_bench 안) · check 결과 measure → 서버 판정 | `bench_check` 배치 항목 |
| 컷 시각·샷 초과 | `render_bench.timeline` StageError | PC → measure | 계획·렌더 멈춤 사유 |
| 자동 검사 6항목 | `bench_check.check` | PC 가 재고 → 서버가 ○/× 판정(임계값은 판 설정) | 자동검사.json |
| 같은 소스 ±3초·A-B-A | `checks.reuse_violations/aba_violations` | 서버(재료.json 만 보면 됨) | 정답지 재료 0건 |
| 얼굴 | `thumb.face_check` | PC | 0초·첫 줄 ○ |
| 이름 발음 사전 | `engine/name_dict.json`+`name_dict.py` | 서버가 사전 주인, PC 는 적용 | — |
| 받아쓰기 창구 | `engine/asr_local.transcribe(engine=)` | PC | 교차 결과 measure |
| 쿠팡 검색 | `coupang_customer.search` → `customer.coupang_chrome` | PC | 상품번호 measure |
| 유튜브 받기 | `customer.ytdlp`(lang=ko) + `screen.download`(m3u8) · 요청 간 쉼은 `origin_find` 39b4618f3 에만 있음 → **한 함수로**(T3) | PC | not a bot 0 |
| 단계 전이·반려·멈춤 | 지금 `customer.advance`(PC) → **서버 `claude_flow.next_step` 한 곳**(새 자리, 기존 `next_step.js` 상태기계는 §9 에서 버림) | 서버 | 흐름 시험(모든 status 전이) |
| payload 위변조 | 서버 HMAC(`claude_portal._mac` 재사용) | 서버 | 바꾼 payload 400 |
| 노출 | `firewall.shape` + 서버 ask 생성기 검사 | 양쪽 | 금지 키·판 설정 숫자 0 |

---

## 7. 받아쓰기·목소리·쿠팡·유튜브 — 사장님 결정 반영(10-21)

- **받아쓰기**: `asr_local.transcribe` 한 곳. 회원 스피치매틱스 키 있으면 스피치매틱스 **먼저** + 위스퍼 = 교차 대조(6·11단계). 없으면 위스퍼만 + 결과에 `asr_single` 표식 → 11단계 판정은 "위스퍼 + 회원 Claude 눈(원본 박힌 자막·대본 글자 대조)"로 하고 완성 응답에 "귀 확인 없음" 한 줄(§12 "위스퍼 단독 판정 금지"와 충돌 → **사장님 결정 ①**). 설정 화면 '소리' 칸에 스피치매틱스 키 칸 추가(`voice.js KEY_SERVICES` 4개 → 5개; `engine_bridge` 는 이미 `readKey('speechmatics')` 를 읽는다).
- **목소리**: 판 파일 `voice` 그대로 — 키치잇·스타픽룸·연예인레시피 = 미나(일레븐랩스, 회원 키), 꿀템노트 = 박창수, 잇템로그 = 유라(타입캐스트 회원 키). 필재 금지(`kal.py BANNED_VOICES`). 미나 1.35 고정·타입캐스트 1.25 상한은 렌더러 판단 그대로, 서버는 로그 measure 로 확인만.
- **쿠팡**: 회원 파트너스 키 → 없으면 회원 PC 크롬(`coupang_chrome`). 둘 다 미실측(handoff ⏭ 7) → T6 에서 실측.
- **유튜브 받기**: 요청 간 쉼·메타 1개씩(39b4618f3 의 방식)을 실행기 `ytdlp_*` 한 포장 함수에 넣는다. 로그인 쿠키는 지금 `logins.js` 그대로.
- **AI 모델**: review 는 `model:"opus"` 기본(10-19 결정). 서버가 단계마다 지정(제목 목록 고르기 같은 단순 판독만 sonnet 허용 — 품질 무관 근거를 진행표에 적는다).

---

## 8. 정답지 검증 도구 — `answer_key`(엔진 트랙 `tools/calcopy/hybrid/answer_key.py` + 숏템MCP `shortem_client/test/answer_key_run.js`)

**목적**: 집 PC 가 만든 편을 기준으로 같은 벤치 URL 을 회원 경로(MCP 경유 — 개발 모드 또는 설치본)에 넣어 **단계별 답을 대조**한다. 합격이 '됐다'의 수치 기준이다.

입력: 정답지 폴더 `channel/yanshottem/하이브리드_<키>/`(조사.md·<판>/대본.json·재료.json·근거.md·자동검사.json) + 벤치 URL + 판 / 회원 경로 산출물 `~/.shortem/jobs/<sid>/`.

| 단계 | 대조 항목 | 합격 기준 | 근거 |
|---|---|---|---|
| 2 원본 | 원본 영상 id | **일치(필수)** | 정답지 조사.md §1 |
| 2 원본 | 지문 대조 원본 초(matched) | 정답지 초와 ±2.0초 안, 2줄 이상 | 02 §4 |
| 2 원본 | origin_offset | 잰 값 있음, 받은 파일 길이 안 | #16 |
| 3 제품 | 쿠팡 상품번호 | mode exact 면 **일치(필수)** · 정답지가 옵션 다른 같은 상품이면 '같은 제품' 눈 판정 ○ | 03 |
| 3 제품 | mode | 정답지와 같음(exact/named/alt) | #10 |
| 4 조사 | facts 수·출처 URL | facts ≥ 정답지 −2, URL 또는 원본 초 100% | 04 §3 |
| 4 조사 | 금지 품목 결론 | 같음 | 04 |
| 6 원음 | spans(원본 초 환산) | 정답지 orig 줄 spans 와 겹침 ≥80%(조각 단위) · 화자 본인 100% | 06 |
| 7 대본 | script_audit | ok · 줄 수 정답지 ±1 · est_length 판 범위 | 07 §7 |
| 7 대본 | 결 | 훅 어미·질문 줄·'따라 ~ 봤'·끝 줄 사회 반응 = audit 통과로 잰다 · 금액·CTA·질병 0 | 07 §3 |
| 7 재료 | source_rule_bad · reuse · aba | 0 · 0 · 0 | #1~#3·B13·B16 |
| 7 재료 | 얼굴 컷 src | 100% 원본 파일 | 00 절대 금지 |
| 11 검사 | bench_check | 6/6 ○ | 11 ① |
| 11 검사 | 받아쓰기 ↔ 대본 tts | 줄 단위 핵심 어절 일치 ≥90%(스피치매틱스 기준, 위스퍼만이면 ≥80% + 짧은 줄 재청취) · 이름·브랜드 들림 | 11 ② |
| 11 검사 | 길이·LUFS | 판 범위 · −14.0±0.5 | 판 설정 |
| 11 검사 | 눈 검수 | 회원 Claude final_look ok **+ 집 PC 세션이 1초 시트·0초 프레임 직접 확인 ○** | 11 ③·0순위-A1 |
| 전체 | 회원 Claude 요청 수·반려 수·편당 서버 호출 수·바이트·소요 분 | 기록(기준선 — 첫 완주 값이 기준) | §3 서버 부담 표 갱신 |

도구 출력: `answer_key_report.md`(항목별 ○/×·값·정답지 값) + 종료코드. 합격 못 하면 그 단계의 progress 표(진행표)와 98_오류기록에 한 줄.

### 8-1. 제약: 이 PC 회선은 유튜브 쇼츠가 'not a bot' 으로 막혀 있다(사장님 10-21 "유튜브는 두드리지 말고 기다려") → **1차 검증은 이미 받아 둔 파일로, 유튜브 받기 0회**

`C:\숏템_칼카피\yanshottem\` 실측(2026-10-21, `find -size +1M`, render 폴더 제외):

| 편(폴더) | 원본 영상 파일 | 벤치 파일 | 재료 영상 | git 문서(정답지) | 1차 검증에 쓸 수 있나 |
|---|---|---|---|---|---|
| **하이브리드_성시경** | `src/Wy9--jw0ZsM.mp4` 66.8MB(본인 채널 '성시경 SUNG SI KYUNG' 원본 308초, 조사.md §1) + `src/Wy9--jw0ZsM__s093-100.mp4` + `Wy9--jw0ZsM.info.json` | `bench/sMx9RWuifCA.info.json·.ko.vtt`(**mp4 없음**) | `src/ramen/-o8gedIaYmA.mp4` 64MB · `FaIQ3NIgVbU.mp4` 20MB | `channel/kitchit/하이브리드_성시경/{대본·재료·근거·자막표·plan}` (재료 src = `Wy9--jw0ZsM_<초>.mp4`·`-o8gedIaYmA_<초>.mp4` 조각 — 전체 원본에서 다시 자를 수 있다) + `starpickroom/`·`kkultemnote/` 같은 편 + `channel/yanshottem/하이브리드_성시경/조사/조사.md` + 잇썸홈·재미썸홈 완성본 2개 | **○ 1차 정답지(유일하게 원본+재료+문서가 다 있다)**. ⚠ 벤치 mp4 가 없어 1단계(소재 시트)는 info.json·vtt 로 대신하거나 벤치를 틱톡·인스타 사본으로 — 미확인. ⚠ 제품 = 신라면, 조사.md 에 **쿠팡 상품번호 없음**("쿠팡·마트 어디서나") → 3단계 대조는 '같은 제품 이름' 까지 |
| 하이브리드_박세리_선크림 | `src/Oyst-fSZKpc.mp4` 40MB | `bench/Ks5kYYKAUlQ.mp4` 2.5MB + sheet.jpg | 없음 | **없음**(10-21 제품 판정 남음 — handoff) | △ 1·2단계(소재 읽기·원본 확정)만 대조 가능(정답 = 원본 id 손으로 적음). 3단계 이후 정답지 없음 |
| 하이브리드_박정수 | **없음**(`src/IjTVGH5SNZQ.info.json·.ko.vtt` 만) | `bench/04xwiT9bj2s.mp4` 4.1MB | 없음 | `조사/` 만 | △ 1단계 + 원본 id 대조(자막 vtt 는 있어 지문 대조 가능, 영상 없어 3단계 이후 불가) |
| 하이브리드_이영자·장윤정·최은경·박세리 | **없음**(폴더엔 `잇썸홈판/재미썸홈판/render/final.mp4` 와 문서만. 원본 yj_BHuue4ga-w0·jyj_XzCEZtLDV-A·5ublOh8gB4o·WHzwVWvEvQ8 는 §0-2 로 지워짐) | 기본편 폴더에만: `이영자_실내화/bench/nt6WIGFmILE.mp4` · `장윤정_덴마크수건/bench/bench.mp4` · `최은경_자라슈즈/bench/bench_mHHUlYnVgdQ.mp4` · `박세리_면세점/bench/BzEO7-_uXkQ.mp4` | `이영자_실내화/broll/*.mp4` 3개 | 조사·대본·재료·근거(잇썸홈판·재미썸홈판 — 옛 판) | × 원본이 없어 2단계 지문 대조부터 유튜브 받기 필요. 유튜브가 풀린 뒤 2차 |
| 10-21 키치잇판 8편(안문숙·고현정·김영옥·손태영·신세경·장윤주·최화정·최강희) | 없음(§0-2 삭제 완료 — handoff) | 없음 | 없음 | 있음(쿠팡 번호 포함) | × 지금은 전부 받기 필요 → **2차**(유튜브 풀린 뒤, 쿠팡 번호까지 전 항목 대조) |

**결정**: 1차 정답지 = **성시경(키치잇판 문서 `channel/kitchit/하이브리드_성시경/`)**. 2차(유튜브 풀린 뒤) = 안문숙 도브 비누·고현정 케뎀 재킷(쿠팡 번호 있음 → §8 표 전 항목).
⚠ 성시경은 사장님 10-19 분류가 **연예인레시피** 소재(스타픽룸판)지만 키치잇판 문서도 같은 폴더에 있어 라인 검증엔 쓸 수 있다 — 결과물을 드라이브에 올리지는 않는다(**사장님 결정 ④**).

### 8-2. 유튜브 받기 없이 검증하는 경로 — "받은 파일 주입(소스 캐시)"
- **판단 주인 한 곳** = 실행기의 유튜브 포장 함수(`runner_ops.ytdlp_*`, §6 '유튜브 받기' 행). 환경변수 `SHORTEM_SOURCE_CACHE=<폴더>` 가 있으면 **받기 전에 캐시를 본다**: `cache/yt/<id>.mp4`·`<id>.info.json`·`<id>.ko.vtt`·`search/<검색어 sha>.json`·`channel/<채널id>.json` 이 있으면 그 파일을 쓰고 유튜브를 두드리지 않는다. 없으면 캐시 모드에선 **받지 않고 `cache_miss` 로 멈춘다**(조용히 유튜브로 가지 않는다 — 사장님 "두드리지 말고"). measure 에 `from_cache:true` 표식 → 서버 응답 `message` 에 "(시험: 받아 둔 파일)" 한 줄. 서버 지시서는 바뀌지 않는다(서버는 캐시를 모른다 — 지시서가 시험·실전 두 벌이 되지 않게).
- **자막이 없는 캐시 원본**(성시경 `src/` 실측: `Wy9--jw0ZsM.mp4` 1920×1080·307.6초 + `.info.json` 만, **`.ko.vtt` 없음**)은 `ytdlp_subs` 가 캐시 mp4 를 **위스퍼(또는 스피치매틱스)로 받아써 낱말·초 목록**을 만들어 vtt 자리에 둔다(`fingerprint` 는 낱말·초 목록만 받으므로 같은 함수가 돈다). 표식 `subs_from:asr`.
- **검색·채널 목록 캐시**는 정답지에서 만든다: `answer_key.py fixtures <편>` 이 조사.md §1(원본 URL·채널·날짜·길이)·info.json 으로 `search/*.json`(원본 1건 + 다른 영상 몇 건 섞어 — 후보가 하나뿐이면 2단계 판정이 시험되지 않는다)·`channel/<id>.json` 을 쓴다. 벤치 mp4 가 없으면(성시경) `bench/<id>.info.json`·`.ko.vtt` 만으로 1단계를 돌리고 시트 review 는 `bench_sheet_missing` 로 건너뛴다 — 또는 틱톡·인스타 사본 URL 을 `source` 로(받기는 된다, 사장님 10-21).
- 재료 영상(5단계) 캐시 = `src/ramen/*.mp4` 두 편을 `cache/yt/<id>.mp4` 로, `screen_search` 결과는 fixtures 에서. 재료가 쿠팡 사진이 필요한 편은 쿠팡은 그대로(회원 키·크롬 — 유튜브 아님).
- 캐시 채우기 명령(T6a): `py tools/calcopy/hybrid/answer_key.py cache 성시경 --from C:\숏템_칼카피\yanshottem\하이브리드_성시경 --to <cache>` — src·bench·ramen 파일을 **복사**(원본 폴더는 건드리지 않는다, 마지막 남은 원본이다).
- 틱톡·인스타 소재는 받기가 된다(`logins.js` 쿠키·10-20 실측) → 얜샷템 라인은 벤치가 유튜브 쇼츠라 1단계 입력만 대체 가능하고 원본(연예인 본인 유튜브)은 결국 유튜브다. 그래서 2차(유튜브 풀린 뒤)가 꼭 있어야 '됐다'다 — 1차는 **라인·검사·반려 고리 검증**, 2차가 **실전 검증**.

---

## 9. 기존 숏템MCP 자산 — 살릴 것 / 버릴 것 / 바꿀 것

| 자산 | 판정 | 어떻게 |
|---|---|---|
| 설치팩(exe 없이 연결 파일+묶음, 자동 업데이트 `updater.js`, `launcher applyPending`) | **살림** | 실행기 코드(§2-3)가 묶음에 들어간다. 노하우 변경은 설치본 재빌드 없이 서버 |
| 회원 키 칸(`voice.js KEY_SERVICES` 4 + 설정 화면) | **바꿈** | 스피치매틱스 키 칸 추가(5개). 키는 환경변수로 실행기에만 |
| 로그인·라이선스·기기 1대·lease·anomaly(`claude_portal`) | **살림** | `/api/claude/step` 도 같은 `_front` 관문(키·기기·lease) 뒤 |
| 드라이브/텔레그램 보내기(`deliver.js`) | **살림** | 12단계 do `deliver` 가 부른다 |
| 프리셋 임대(`preset_rent.js` + 서버 `preset_rent`) | **바꿈** | channel 틀·판 설정 임대는 유지(렌더 단계만) · **`TECH_DIRS` 코드 임대는 뺀다**(코드는 설치본 실행기로, 지시문·문서(`TECH_DOCS`)는 서버 진행표로) |
| 설정 화면(`local_ui.js`·`ui/index.html`·`local_settings.js`) | **살림** | 프리셋 고르기·키·완성본 탭 그대로 |
| `make_flow.js`(hybrid 입구·shapeHybrid·aiNeed) | **바꿈** | 엔진 `make.py hybrid …` 를 띄우는 대신 **서버 step 왕복 고리**(실행기 run → measure → POST step → 응답 분기)로. `shapeSession` 의 옛 calcopy_make 라인(후보·choose·restyle)은 다른 프리셋용으로 남긴다 |
| `engine/next_step.js`(PC 로컬 상태기계 9단계, `STEP_NAMES` 9) | **버림**(얜샷템 라인에서) | 전이 판단은 서버 한 곳. 옛 9단계 이름은 lease `step_name` 검사와 묶여 있어(계약 §2) **13단계 이름으로 계약을 고친다**(api.md §8) |
| `firewall.shape` | **바꿈** | review(id·ask·show 이름·answer_schema)·reject(why·fix)·stage 13 꼴 추가. 금지 키·숫자 지우기 그대로 |
| `engine_bridge.js`(파이썬 띄우기·AI 요청 큐·`requestContent`) | **바꿈** | 요청 큐 = 서버 review 를 그대로 담는 자리로(파일 꼴 유지). `startRun(make.py)` → `runner_ops` 호출로 |
| `client_llm.py`(엔진 쪽 요청 큐) | **축소** | 다른 프리셋 라인(calcopy_make)에서만. 얜샷템 라인은 서버 review 가 대신 |
| `customer.py` | **분해** | ① 기계 함수 → `hybrid/runner_ops.py`(실행기, 설치본) ② 지시문 11개·단계 순서·멈춤 규칙·재시도 횟수·`PRODUCT_TALK` → 서버 진행표 `hybrid/flow/kitchit.json`(+ 생성기) ③ `advance/approve/resume/status`·`Piece`·`progress.json` → 서버 `claude_flow.next_step` + PC `jobs/<sid>/` 파일만. 분해가 끝나면 customer.py 는 지운다(두 벌 금지) |
| `make.py --json hybrid` | **버림** | 실행기 입구로 대체 |
| `hybrid_dev_run.py` | **바꿈** | 로컬 시험 서버 + 실행기 + `claude -p opus` 가 review 답 → `answer_key_run.js` 와 합침 |
| `fake_server.js` | **바꿈** | `/api/claude/step` 은 가짜로 만들지 않는다 — 진짜 `claude_flow` 를 **로컬 시험 서버(127.0.0.1:8849, 시험 DB)** 로 돌린다(§10). fake 는 license·rent 시험용으로만 |
| `live_episode.js` | **살림** | `--say "<URL> 이걸로 연예인상품+후기형으로"` 완주 도구 그대로(기준 §8) |
| `claude_preset_names.json`·`line.json`(얜샷템=hybrid·키치잇판) | **살림** | 서버가 프리셋 → 진행표를 고르는 열쇠 |
| `SKILL.md`(make) | **바꿈** | need 에 `input`(원본 주소 요청) 추가 · WebSearch 허용(조사 단계) · "message 한 줄만 전한다" |

---

## 10. 로컬 시험 → 라이브 승인 경로 (0순위-A1c)

1. **로컬 시험 서버** = 숏템MCP 트랙 `shopping_shorts` 앱을 127.0.0.1:8849 시험 DB 로(10-18 실측 경로 그대로) + 스위치 `claude_portal_enabled=admin`. `/api/claude/step` 을 여기서 먼저 돌린다.
2. 회원 PC 쪽 = ① 개발 모드(`SHORTEM_ENGINE=엔진 트랙`, `SHORTEM_BASE=http://127.0.0.1:8849`) ② 설치본 1.0.11(실행기 포함) + 같은 로컬 서버 — `live_episode.js --install … --say …` 로 **MCP 경유 완주**.
3. `answer_key_run.js` 합격 + 집 PC 세션 눈 검수 ○ → **사장님께 "라이브에 올릴까요?"** → 승인 → `finish`(두 트랙 모아서 한 번, handoff ⏭ 8) → 라이브 스위치 admin → 라이브에서 같은 완주 → 고객 공개 스위치는 또 승인.
4. 서버 상태 기록(sid·판·원본 id·쿠팡 번호·검사 요약)은 **회원 데이터** → 카드 234 범위 안인지 확인, 벗어나면 `control.py new --approval 예`(**사장님 결정 ⑤**).

---

## 11. 구현 순서 (T0~T9 · 각 작업 = 바꿀 파일 · 시험 · 완료 기준)

| T | 일 | 바꿀 파일(트랙) | 시험 | 완료 기준 |
|---|---|---|---|---|
| T0 | 사전 확인 | — | `git -C main ls-files tools/calcopy/hybrid`(라이브 main 에 styles·script_audit 있나) · 로컬 시험 서버 기동 · 성시경 편 `조사.md`·`kitchit/대본.json·재료.json` 전부 읽기(원본 1920×1080·307.6초·vtt 없음은 이미 실측) · **유튜브 호출 0 으로** | 미확인(§13) 해소, 1차 정답지 = 성시경 확정 |
| T1 | 서버 흐름 뼈대 | 숏템MCP `shopping_shorts/claude_flow.py`(next_step·payload mac·status 6종·reject/stop 꼴) · `app.py` 라우트 `POST /api/claude/step`(`_front` 관문 뒤) · `claude_portal` STEP_NAMES 13 · api.md §8·§10 | pytest `test_claude_flow.py`: 위변조 400 · 옛 measure 재전송 reject · 모든 status 전이 · 응답 금지 키 0 | 가짜 measure 로 13단계 끝까지 전이 |
| T2 | 단계 진행표 데이터 | 엔진 트랙 `tools/calcopy/hybrid/flow/kitchit.json`(13단계 do·measure·review ask/schema·traps·검사 목록 — customer.py 지시문 11개와 제작순서 02~13·98 을 옮김) + `flow/build.py`(판 설정에서 숫자 채움) · `preset_publish.py` 옮길 목록에 flow·hybrid 모듈 | `test_flow_spec.py`: 단계 13 · ask 에 금지 키·판 설정 숫자 0 · 98_오류기록 19건이 traps 에 전부 있나(번호 대조) | 진행표가 제작순서 문서와 1:1(단계·멈춤·traps) |
| T3 | PC 실행기 | 엔진 트랙 `hybrid/runner_ops.py`(cmd 허용 목록 + customer.py 기계 함수 이전 + ytdlp 쉼 한 곳 + **소스 캐시 `SHORTEM_SOURCE_CACHE`(§8-2, 캐시 모드에선 cache_miss 로 멈춤)** + name_check 미나=일레븐랩스 수리) · 숏템MCP `engine_bridge.js`(run cmd)·`make_flow.js`(step 고리)·`firewall.js`(review·reject·stage 13)·`voice.js`(speechmatics 칸)·`preset_rent.js`(TECH_DIRS 제거) | `npm test` 기존 35 + `flow_step.test.js`(허용 밖 cmd 거절 · payload 그대로 되돌림 · measure 새로) · 엔진 `test_runner_ops.py`(customer 함수와 결과 동일 — origin_offset·fingerprint·source_rule 기존 시험 재사용) | 허용 밖 cmd 0 실행 · customer.py 함수 호출 0(분해 끝) |
| T4 | 회원 Claude review 통로 | `engine_bridge.requestContent`(review → 글+그림) · `index.js shortem_ai` · `SKILL.md`(input·WebSearch·한 줄) · 플러그인 안내 | `mcp.test.js` 확장: review 응답에 시트 이미지 실림 · 답 꼴 틀리면 reject 재요청 | 13단계 review 전부 Claude CLI(opus) 가 답해 전이 |
| T5 | 서버 검사 주인 연결 | `claude_flow.py` 에서 `script_audit.audit`·`_caps_vs_tts`·`_title_colors_bad`·`source_rule_bad(①②)`·`reuse/aba_violations`·bench_check 판정·받아쓰기 일치율 호출(엔진 모듈 import — T0 결과대로 main 에 있어야) | mutation: 정답지 대본·재료를 8곳 망가뜨려 8곳 reject(`mutation_check` 방식) | 거짓 통과 0(고치기 전 코드로 실패가 뜨는지 먼저 본다, A1c) |
| T6a | 정답지 도구 + **주입 완주(유튜브 0회)** | 엔진 `hybrid/answer_key.py`(`fixtures`·`cache`·`compare`) · 숏템MCP `test/answer_key_run.js`(hybrid_dev_run 흡수, `--cache <폴더>`) · 쿠팡 키/크롬·일레븐랩스 실측 | 성시경 캐시 → 개발 모드 완주 → `answer_key_report.md` · 실행기 로그에 유튜브 호출 0(캐시 모드 cache_miss 0) | §8 표 중 2·4·6·7·8·10·11 항목 ○(3단계는 제품 이름 일치) + 집 PC 세션 눈 ○ · 편당 호출 수·바이트·분 기록(§3 표 갱신) |
| T6b | **2차 실전 완주(유튜브 풀린 뒤)** | — | 안문숙 또는 고현정 벤치 URL 로 캐시 없이 완주 · 요청 간 쉼 로그 | §8 표 **전 항목** ○(쿠팡 번호 포함) + 눈 ○ |
| T7 | 설치본 1.0.11 + 로컬 서버 완주 | `installer`(실행기 포함·얼굴 onnx·playwright) · `engine_bundle.py` 목록(hybrid 코드 허용, 문서·flow 금지) · `upload_release.py`(로컬) | `noexe_install_check` · `test_engine_installed` · `live_episode.js --say` ↔ 로컬 시험 서버(캐시 모드로 먼저, 유튜브 풀리면 실전) | 설치본으로 MCP 경유 1편 완주 + answer_key ○ |
| T8 | 라이브 | (승인 뒤) `finish` 두 트랙 · 라이브 스위치 admin · 라이브 완주 · 눈 검수 · handoff·98 기록 | `live_episode.js` 라이브 · 경보 0 · 회원 데이터 카드 | **'됐다'**: 라이브 회원 경로 완주(T6b 조건 — 유튜브 실전) + §8 합격 + 눈 ○ |
| T9 | 후속 | 소재 "다음꺼"(01 A/B 서버 제공) · 다른 프리셋 라인 진행표(제품비하인드썰형 등 — 집 PC 제작 문서 없음, handoff ⏭ 6) · 스피치매틱스 안내 · 반려 통계로 진행표 개선 | — | — |

순서 근거: T1·T2 는 독립(서버 뼈대 ↔ 진행표 데이터) → 병렬 가능. T3·T4 는 T1 응답 꼴이 정해져야. T5 는 T0 확인 뒤. T6 이 첫 '결과물' — 그 전엔 "진행 중"이라고만 말한다(0순위-A1).

---

## 12. 서버 부담 0 원칙과의 관계 (정리)
- 서버가 **하는 것**: 로그인·등급·lease(그대로) + 단계 진행표 내려주기 + measure·review 답의 규칙 판정(글·숫자) + 상태 요약 기록. 전부 작은 JSON.
- 서버가 **안 하는 것**: 영상·그림·소리 받기, 받아쓰기, 렌더, 크롬, 키 보관, 회원 Claude 호출. 10-19 결정 그대로.
- 숫자 기준(T6 에서 실측해 고친다): 편당 호출 ≤40, 요청 합 ≤3MB, 응답 합 ≤1MB, 서버 CPU 합 ≤2초. 넘으면 measure 를 줄인다(받아쓰기 글은 요약·샷 표는 PC 에 두고 요청 시만).

---

## 13. 위험 · 미결 (미확인은 T0)

| # | 위험·미결 | 대응 |
|---|---|---|
| 1 | **미확인**: 라이브 main 에 `tools/calcopy/hybrid/*`(styles·script_audit·placement·checks) 가 있는가 — 서버 검사(T5)가 import 한다 | T0 `ls-files`. 없으면 `preset_publish.py` 로 옮기는 목록에 추가(코드 병합 = 라이브 변경 → 승인) |
| 2 | 하이브리드 편을 MCP 경유로 끝까지 돈 기록이 0 — 응답 꼴·대기(45초 wait)·AI 요청 이미지 40장 상한이 13단계에서 어떻게 되는지 모른다 | T6 개발 모드 완주가 첫 실측. 그 전 수치는 전부 추정 |
| 3 | 받아쓰기 교차가 없는 회원(스피치매틱스 키 없음) — §12 "위스퍼 단독 판정 금지"와 충돌 | 사장님 결정 ① |
| 4 | 렌더러·배치 코드(`render_bench`·`placement`)가 설치본에 고정 = 노하우 일부가 PC 에 남는다(판 설정은 편마다만) | 18일 §7-4 "최소한" 정의 안. 사장님 결정 ③ |
| 5 | 서버 죽으면 새 편 못 시작(B 안은 가능) | 진행 중 편은 payload 가 PC 에 있어 복구 뒤 이어 감. 수용 |
| 6 | 쿠팡 파트너스 키·크롬 길·일레븐랩스 회원 키 **미실측**(handoff ⏭ 7) · 이 PC 회선은 쿠팡 차단 | T6 에서 실측. 안 되면 그 단계 stop 사유를 회원에게 |
| 7 | 회원 Claude 모델이 opus 가 아닐 때 품질(대본·판정) | review.model 지정 + SKILL 의 Agent(model=opus) 위임 유지 |
| 8 | lease `step_name` 9개 고정(계약 §2)이 13단계와 어긋남 | T1 에서 계약 §8 을 13 으로 고치고 두 쪽 시험 같이 |
| 9 | 정답지 편의 재료(src·screen)는 대부분 삭제(§0-2) — 받아 둔 원본이 있는 편은 **성시경 하나**(§8-1 실측). 유튜브는 지금 막혀 있어(10-21) 다시 받을 수도 없다 | 1차 = 성시경 캐시 주입(§8-2, 유튜브 0회) · 2차 = 유튜브 풀린 뒤 안문숙·고현정. 성시경 원본 폴더는 복사만(지우지 않는다) |
| 9-1 | 성시경 벤치 mp4 없음·원본 vtt 없음(실측)·쿠팡 번호 없음 → 1단계 시트 review·2단계 지문·3단계 번호 대조가 완전하지 않다 | 1단계는 info/vtt 로, 지문은 위스퍼 낱말로(§8-2), 3단계는 이름 일치까지. 빠진 항목은 보고에 "1차에서 못 잰 것"으로 적는다 |
| 10 | 진행표가 제작순서 문서와 어긋나는 날이 온다(두 벌) | 같은 커밋 규칙(칼카피_시작 11번) + `test_flow_spec` 이 traps 번호를 98 과 대조 |
| 11 | 다른 프리셋 4개(제품비하인드썰형·샤크탱크·해외핫영상·연예인꿀맛)는 집 PC 제작 문서가 없어 진행표를 못 만든다 | 이번 범위 = 연예인상품+후기형(키치잇판)만. 나머지는 옛 calcopy_make 라인 유지 |

---

## 14. 사장님께 꼭 물을 것
1. **지시서 = 라이브 서버 신규 라우트(A안)** 로 가도 되나 — 서버가 작은 JSON 왕복(편당 ≤40회)을 맡는다. 라이브 배포는 로컬 시험 완주 뒤 다시 승인 요청.
2. **스피치매틱스 키 없는 회원**: 위스퍼 단독 + 회원 Claude 눈 대조로 판정하고 "귀 확인 없음" 표시해도 되나, 아니면 키 없으면 그 판은 안 되게 막나.
3. **렌더·배치 코드**는 설치본에 고정(판 설정만 편마다 임대)으로 가도 되나 — 지금의 "코드까지 편마다 임대"는 뺀다.
4. **정답지 편**: 1차(유튜브 막힌 지금) = 성시경 신라면(받아 둔 원본·재료·키치잇판 문서가 다 있는 유일한 편 — 결과물은 드라이브에 안 올림) · 2차(유튜브 풀린 뒤) = 안문숙 도브 비누·고현정 케뎀 재킷. 이대로 가도 되나.
5. **서버 상태 기록**(sid·판·원본 id·쿠팡 번호·검사 요약 — 영상·대본 본문 없음)이 카드 234 회원 데이터 범위 안인지. 벗어나면 승인 카드를 새로 만든다.

---

## 15. 결정 (2026-10-21 집 PC 세션 — 사장님 "왔다갔다하지 말고 다 된 다음에 푸시" 지시로 기본값 채택, 최종 보고 때 함께 알림)
1. 지시서 = **A안(서버 `/api/claude/step`)**. 로컬 시험 서버로 끝까지 검증 → 라이브 배포만 마지막에 승인 요청(0순위-A1c).
2. 스피치매틱스 키 없는 회원 = 위스퍼 + 회원 Claude 눈 대조, 완성 응답에 "귀 확인 없음" 한 줄(`asr_single`). 키 있으면 교차.
3. 렌더·배치 코드 = 설치본 고정, 판 설정만 렌더 단계 임대.
4. 정답지 1차 = 성시경(캐시 주입, 유튜브 0회, 드라이브 업로드 안 함) · 2차 = 유튜브 풀린 뒤 안문숙·고현정.
5. 서버 상태 기록 = sid·판·원본 id·쿠팡 번호·검사 요약만(본문·영상 없음) — 카드 234 승인 범위(라이선스·기기·탐지 로그·채널 옵션)와 같은 회원 운영 데이터로 보고 진행, 라이브 배포 승인 때 함께 확인.
