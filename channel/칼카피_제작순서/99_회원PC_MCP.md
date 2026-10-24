# 99 회원 PC(숏템 MCP)가 이 순서를 그대로 도는 법 — 볼케이노형 (2026-10-21 재설계, 관제 234 · 097)

사장님(10-21): **"집에서는 한마디면 영상이 만들어지는데 여기서도 똑같애야 된다"** / **"볼케이노처럼 단계별로 착착"** /
**"그 세션을 덮어서 수정을 싹 해 — 설계는 페이블이 다시, 칼카피 노하우를 녹여서 지금처럼 영상이 나오게"**.
설계 문서: 숏템MCP 트랙 `docs/superpowers/specs/2026-10-21-숏템MCP-볼케이노형-design.md`.

## 원칙 — 노하우는 서버 한 곳, 회원 PC 는 손과 눈
| 자리 | 무엇 | 파일 |
|---|---|---|
| **서버 지시서**(노하우) | 13단계 순서·판정 질문·반려 규칙·함정(98 번호) — 이 폴더 00~13 을 옮긴 것 | `tools/calcopy/hybrid/flow.py` (서버 `shopping_shorts/claude_flow.py` 가 `POST /api/claude/step` 으로 부른다) |
| **판정 함수**(서버·PC 공용) | 지문 대조·자막↔목소리·제목 색·출처 규칙 ①②·샷 끝·주인공 가운데·확대 1.0(fit_height)·박힌 글자 흐림(text_blur_all) | `tools/calcopy/hybrid/rules.py` |
| **회원 PC 손**(실행기) | do 명령만(허용 목록) — 받기·시트·받아쓰기·쿠팡·재료·계획·렌더·검사(quality_gate)·해외 원본(origin_foreign)·글자 지우기(clean_text)·재료 초안(materials_draft) | `tools/calcopy/hybrid/runner_ops.py` (+ render_bench·quality_gate·vmake_clean·ititemlog_make, 설치본 `engine_bundle.HAND` — 새 모듈 포함은 09) |
| **회원 PC 눈**(회원 Claude) | review 마다 실제 자료(시트·사진·글)를 보고 JSON 하나로 답 | MCP `shortem_ai`(요청 폴더) ← `shortem_client/server/flow_driver.js` |
| **고리** | 서버 응답 → do 실행 → measure / review → 답 → replies / 사인 → approve | `flow_driver.js` · 입구 `make_flow.makeStep`(영상 주소로 start) |

- 응답 = `status`(execute·review·reject·wait_user·stop·done) · `message`("OO 완료 → 다음 OO" 한 줄) · `stage` · `do` · `review` · `traps` · `next_payload`(서버 서명, 그대로 되돌림 — 바꾸면 400, 옛 것은 stale).
- 서버는 **요약만** 남긴다(sid·판·원본 id·쿠팡 번호·검사 ○/×). 영상·대본 본문·키는 받지 않는다(서버 부담 0 — 편당 JSON 왕복만).
- **노하우를 고칠 때 = `flow.py` 를 이 폴더 문서와 같은 커밋에**(칼카피_시작.md 11번). 서버 반영만 하면 모든 회원이 다음 호출부터 바뀐다(설치본 재배포 없음).
- 옛 회원 라인 `hybrid/customer.py`(10-21 TheRose PC, 회원 PC 에서 노하우를 코드로 돌리던 것)는 지웠다 — 기계 함수는 runner_ops, 판정 함수는 rules, 질문·순서는 flow 로 나눴다.

## 형식 분기 (관제 263 지시서 08 · 표준 §7) — "<프리셋> 스타일로 만들어줘" 가 어느 형식이든 같은 서버 지시서
- 형식 = `channel/프리셋.json` presets[slug].member.flow_format(주인). `flow.start(url, version, sid, product, fmt=None)` 가 판 이름(업그레이드 판은 base 를 따라)으로 찾고,
  장부에 없거나 형식이 둘로 갈리거나 flow 표에 없는 형식(여행형·인물형)이면 **`flow.FormatError` 로 거절**(조용히 연예인형으로 돌리지 않는다). 서버(09)는 fmt 를 넘기기만 — 다르면 거절.
- 단계표 `flow.FORMAT_STAGES`: **연예인형**(아래 13단계) · **해외원본형**(아래 별표) · **쇼핑형**(소재 확인 → 제품 → 자료 조사 → 재료 영상 → 대본 → … — 원본 찾기·원음 없음) · **레시피형**(연예인형 단계 + 판의 재료 스티커).
- 세부 단계 처리기 = `flow.FORMAT_PHASES[형식]` 이 있으면 그것, 없으면 공용. 질문문도 형식별(`flow._q`) — 연예인형 문장('연예인 본인 원본')을 다른 형식에 쓰지 않는다. 함정 = `TRAPS` / `TRAPS_FOREIGN`.
- 회원 맞춤 자리 = 대본 검사 통과 뒤·사인 전 `customize`(지시서 12 가 채운다 — 지금은 그대로 지나감).

## 단계 대응 (집 PC → 회원 PC, `flow.STAGES` = 연예인형)
| # | 단계(회원에게 보이는 말) | do(회원 PC 손) | review(회원 Claude 눈) | 서버 반려·멈춤 |
|---|---|---|---|---|
| 1 | 준비 확인 | env(키·디스크·도구) | — | 판 목소리 키 없음 · 디스크 < 1.5GB |
| 2 | 영상 확인 | bench(벤치 받기·시트·받아쓰기) | origin_read(출처 글자·인물·제품 낱말) | 쇼핑 소재 아님 |
| 3 | 원본 영상 찾기 | peer_sheet · search(고정 검색어 먼저) · channel_list(본인 채널) · origin_subs(지문 대조) · origin_get(구간 받기·**시작 시각 재기**) | peer_read · titles(120편씩) · origin_pick | 후보 0 · 본인 말 아님 |
| 4 | 제품 확인 | sheet(맞은 초 −25부터) · frames · coupang(키 → 크롬) · naver | product_pick · product_same → name_find → named_same → best_same | 같은 종류도 없음 · 의약품 |
| 5 | 자료 조사 | origin_words(자막 또는 받아쓰기) | research(조사.md 6절·spans·facts, 웹 검색) | 절 빠짐·구간이 파일 밖·출처 없는 사실(3번) |
| 6 | 재료 영상 모으기 | screen · download · product_stills(쿠팡 상품 사진 → prod_*.jpg) | screen_pick(연예인 나오는 남의 영상 금지) | — |
| 7 | 원음 정리 | asr_spans(스피치매틱스+위스퍼 교차) · shot_sheets | shot_*(샷마다 누가·제품·얼굴 가로 위치) | — |
| 8 | 대본 쓰기 | mat_sheets · write_doc · orig_heard(원음 줄 실제 받아쓰기 ↔ 자막) | script(판 brief + 결 기준 + 미나 오독 대체어) | script_audit · 제목 색 · 자막↔목소리 · 출처 규칙 · 제품 컷 0개 · 원음 귀 확인(5번) — 출처 줄은 서버가 원본 채널 이름으로 |
| 9 | 대본 확인 | — | (회원 사인) | 사인 전 목소리·렌더 0 |
| 10 | 장면 맞추기 | plan(시간표·계획 시트·장면 전환 재기) | plan_*(컷마다 대사↔화면·남의 글자·주인공 가운데 — 샷 표에 박힌 글자 상자) | 샷 초과·출처 규칙(8번 — 집 PC VERIFY_ROUNDS) |
| 10-1 | (장면 맞추기 안) 썸네일 카드 | write_doc(`<판>/썸네일.json`) — 계획 시트 칸 위 `c번호` = part | thumb_*(3안: axis·mood·part·t·원/화살표/?/흐림·글 — 판정 주인 `thumb_rule` FIND_ORDER·GOOD, 사장님 10-24) | `thumb_rule.check` 반려 → 다시(2번) → 그래도면 카드 없이 렌더(로그) · 렌더가 맨 앞 2프레임(0.067초)에 무작위 1안 |
| 11 | 목소리·영상 만들기 | render | render_fix_* | 샷 초과(3번) |
| 12 | 완성본 검사 | check(**`quality_gate.gate` 전체** — 표준 §5-1 1단, 우리 PC 와 같은 함수 · 눈 검수 묶음 `<판>/eye/`) | eye_*(표준 §5-2 **E1~E8** 번호 그대로 — 질문 = `quality_gate.EYE_Q`, 업그레이드 판은 E9) → `<판>/눈검수.json` | 1단 × 면 눈 생략 · 1단 × 또는 눈 ×·△ → 재료 고쳐 다시(final_fix, 2번) → 그래도면 **멈춤**(사유 = × 항목 이름·E 번호, 완성본을 done 으로 내지 않는다). 길이 × 는 대본 다시 |
| 13 | 완성 | finish | — | 관문 2단을 안 거친 영상은 finish 가 멈춘다 · 키 없으면 "귀 확인 없음" 한 줄 |

### 해외원본형 단계 (잇템로그·핫템리포트·쇼츠비트 등 — `FORMAT_STAGES["해외원본형"]`)
| # | 단계 | do(회원 PC 손) | review(회원 Claude 눈) | 서버 반려·멈춤 |
|---|---|---|---|---|
| 1 | 준비 확인 | env | — | 연예인형과 같음 |
| 2 | 영상 확인 | bench | ref_read(한국 재편집인가 해외 원본인가·제품 낱말·영어 검색어 — `REF_READ_FOREIGN` + `briefs/origin_foreign.md`) | 제품이 화면에 없음 |
| 3 | 해외 원본 찾기 | origin_foreign(lens = 소재 장면 4장 → 구글 렌즈 → 영상 링크·메타 / peers = 같은 제품 다른 해외 반응 검색) · origin_get(통째로) | of_judge(같은 촬영분 — `origin_find.JUDGE_PROMPT`) · of_peer(같은 제품·다른 해외 사람 최대 2) | 원본 = `origin_find.pick_origins`(해외 채널마다 가장 먼저 · 한국 재편집보다 늦은 것 제외) · 원본 2~3개 · 유튜브 밖 원본은 받기 길 없어 뺌(기록) |
| 4 | 제품 확인 | sheet(원본마다) · frames · coupang · cand_sheet | product_pick(원본 출연자가 쓰는 그 제품 — 장면마다 src) → product_same → best_same(비슷한 제품 허용 — 현장썰 규칙) | 의약품 |
| 5 | 자료 조사 | origin_words(원본마다) | research(`RESEARCH_FOREIGN` — spans 마다 원본 파일 src) | 절 빠짐·구간이 그 파일 밖·출처 없는 사실 |
| 6 | 원본 정리·글자 지우기 | shot_sheets · product_stills · **clean_text**(회원 VMake 키 `VMAKE_API_KEY` 있으면 `vmake_clean.member_clean`, 없으면 **호출 0 — 흐림**) · **materials_draft**(`ititemlog_make.draft` — 원본별 시간순·재사용 0·확대 1.0 구간표) | shot_*(`SHOT_READ_FOREIGN` — 박힌 글자 상자·다른 제품 샷) | 흐림 칸 = 서버 `rules.text_blur_all`(지운 파일 빼고) |
| 7 | 원음 정리 | asr_spans(구간마다 원본 파일) | — | — |
| 8~13 | 대본 쓰기 ~ 완성 | 연예인형과 같음(orig_heard 는 said 원문으로 대조) | script(`SCRIPT_FOREIGN` + `briefs/script_foreign.md` + 판 brief + 원본 목록·글자 처리·재료 초안) · plan_*(`PLAN_LOOK_FOREIGN`) · thumb_* · eye_* | 제품 컷 0개 규칙은 연예인형만 · 세로 원본 확대 판정 = `rules.fit_height`(폭 전체가 확대 1.0) · 회원이 해외 원본을 바로 줬으면 그 영상은 벤치가 아니라 원본(출처 규칙 ①) |

## 시험·정답지
- 개발 완주(서버 HTTP 없이 지시서↔실행기↔Claude CLI): `PYTHONUTF8=1 py tools/calcopy/hybrid/flow_dev.py --ref <벤치> --version 키치잇판 --work <폴더> [--cache <소스 캐시>] --approve`
  · 해외원본형: `answer_key.py cache 잇템로그_ep13 --to <캐시>` → `flow_dev.py --ref https://www.youtube.com/shorts/8U0MvYtEAOo --version 잇템로그판_v2 --fmt 해외원본형 --cache <캐시> --no-paid --approve`
  · 돈 0: `--no-paid`(TTS 캐시만·스피치매틱스·VMake 0) · `--tts-seed <렌더 폴더>` · `--replay <폴더>`(답 고정) · `--from-plan <대본 답>`(대본 검사 없이 계획부터 — 시험 전용) · 사보타주 `QG_FORCE_FAIL=1`.
- 받아 둔 파일만으로(유튜브 0회, 10-21 'not a bot' 차단 중): `answer_key.py cache 성시경 --to <캐시>` → `--cache` · 실행기는 캐시 모드에서 yt-dlp 자체를 못 띄운다.
- 정답지 대조: `answer_key.py compare 성시경 --job <폴더>` → `answer_key_report.md`.
- 회원 경로 그대로(MCP·서버 HTTP·설치본): `shortem_client/test/live_episode.js --say "<벤치 URL> 이걸로 연예인상품+후기형으로 만들어줘"`.
- '됐다' = 회원 경로로 만든 편이 정답지와 원본·제품이 같고 quality_gate 1단 ○ + 눈 2단 E1~E8 ○ + 집 PC 세션이 완성본을 눈으로 확인.

## 회원 키 (설정 화면)
타입캐스트 · 일레븐랩스(미나 판) · 쿠팡 파트너스 access/secret(없으면 크롬) · 스피치매틱스(있으면 교차 받아쓰기). 값은 회원 PC 파일에만, 화면엔 지문만.
