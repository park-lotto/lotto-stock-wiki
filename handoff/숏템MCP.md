# 숏템MCP — 고객 PC 클로드형 설치팩·프리셋 옵션 페이지

관제 카드 234(사장님 승인 2026-10-18 "멈추지말고 마지막까지 끝까지해" — 회원 데이터: 라이선스·기기 잠금·탐지 로그·채널 옵션)

- 설계: `docs/superpowers/specs/2026-10-18-숏템MCP-design.md` (4판, 미결 0)
- API 계약: `docs/superpowers/specs/2026-10-18-숏템MCP-api.md`

## 2026-10-18 (TheRose PC) 구현

### 만든 것
| 갈래 | 위치 | 주인 함수 |
|---|---|---|
| 서버 포털 | `shopping_shorts/claude_portal.py` · `channel_profile.py` · app.py 라우트 `/api/claude/*`·`/api/claude/me/*`·`/claude`·관리자 경보 · `static/claude.html` · `static/admin.html` 경보 칸 | assets_for · preview · lease · anomaly_check · channel_profile.merge |
| 서버 도구 | `tools/claude_portal/` sync_assets(원본 내용주소 등록) · build_previews(견본 굽기) · check_previews(견본 규격 검사) · issue_key · mutation_check | — |
| 고객 PC | `shortem_client/server/` Node stdio MCP, 도구 6개, 상태기계 9단계 | `engine/next_step.js:nextStep` |
| 설치팩 | `installer/` 윈도 NSIS exe(실행도구 6개 동봉) · .mcpb · Claude Code 플러그인 · 시작.md · 설치안내.html(11장) · 맥 build_mac.sh(미실측) | — |

스위치(전부 기본 끔 → 관리자만 쓰려면 "admin"): `claude_portal_enabled` · `claude_assets_enabled` · `license_kv` · `claude_presets_off` · `claude_min_engine` · `claude_min_installer` · `claude_anomaly_thresholds`.

### 실측(이 세션)
- 서버 시험 `py -m pytest shopping_shorts/tests/test_claude_portal.py` 21 통과 · 판단 8곳 망가뜨리기 → 8곳 다 실패 감지(mutation_check)
- PC 시험 `cd shortem_client/server && npm test` 16 통과
- 로컬 서버(127.0.0.1:8849, 시험 DB) ↔ **설치본**(NSIS 203.4MB, PATH 비우고 동봉 도구만) 로 1편 끝까지: 9/9 완료, 12.174초 1080x1920 -14.3 LUFS, 묶음 표식 comment, 자가점검 3종(목소리는 키 없어 건너뜀)
- 견본 223개 규격 검사 기준 밖 0 · 자산 assets 14개 sha 14/14 · 다른 기기 409 · Range 조각 403 · 페이지 응답 금지 키 0
- 설치 → 제거 잔해 0(폴더·제거 키·환경변수)

### 고친 결함(내가 프레임을 보고 잡은 것)
- 채널명을 넣으면 brand 자리 "[광고]" 표시가 지워짐 → `_is_disclosure` 로 보존
- banggu 게시글형 틀에 벤치 영상의 게시글 제목이 고정 글로 박혀 나옴 → 서버가 비우고 `fill: "title"`, PC 가 그 편 제목으로 채움
- rules.formula(공식 문장 원문)가 PC 로 내려감 → 안 보냄
- 라이선스 키를 채팅에 쓰라던 안내 → 설정 칸(.mcpb sensitive / 플러그인 옵션)으로

## 2026-10-19 02:20~03:00 라이브 실측 (TheRose PC)
- 배포: 8b633ed 는 10-18 22:31 재시작으로 반영. 스위치 `claude_portal_enabled=admin` · `claude_assets_enabled=admin`(관리자만, 고객 공개는 사장님 결정)
- 서버 `sync_assets.py --db shopping_shorts/data/reference.db`: font 88 · sfx 147 · bgm 24 · template 12 · **meme 1283** → 저장소 1,438 파일(`shopping_shorts/data/claude_store`, 570MB, 서버 디스크 여유 26GB)
- 견본: font 87 · sfx 21 · bgm 24 · template 12 · voice 79 · **짤 시트 32장(칸 합계 1,283 = 전부)** · `check_previews` 기준 밖 0
- **라이브에서 잡은 결함 2 → 고쳐 병합(dc0e5f770, 관문 통과)**
  1. `/claude` 프리셋 0개 — 틀(`channel/*/preset/**`, 148파일 2.8MB)이 칼카피숏템엔진 트랙에만 있었다(로컬 시험은 CLAUDE_CHANNEL_ROOT 를 엔진 트랙에 붙여 안 보였다). 엔진 같은 내용을 main 으로 + `tools/calcopy/sync_preset_ledgers.py:_preset_frames` 가 앞으로 틀 폴더도 옮긴다(엔진에서 지운 틀은 안 지움)
  2. `build_previews.meme_sprites` — 0.5초보다 짧은 짤은 ffmpeg rc 0 인데 그림이 없어 FileNotFoundError 로 전체 중단 → 0초로 다시 + OSError 건너뜀. 0.3초 시험 클립으로 고치기 전 실패·후 2칸 대조
- 라이선스: `/claude` 의 키 발급 API 를 관리자 세션으로 눌러 발급(58자, 만료 2027-10-18, 원문은 세션 임시 파일에만). 서버 `issue_key.py` 는 서비스 env 읽기가 권한 분류기에 막혀 안 씀
- 프로필: 라이브 `/claude` 에서 프리셋(banggu 게시글형 p_850f616631) 고르고 채널명 '썰풀다실측' 저장 → v1
- **e2e 라이브 1편**(`SHORTEM_E2E_BASE=https://shoppingshorts.duckdns.org`, 개발 도구 모드): 9/9 완료, 12.174초 1080x1920 h264+aac -14.3 LUFS, comment `shortem:e41635236030:j_…`. 프레임 3장 눈으로: 머리띠·작성자 줄에 '썰풀다실측', 게시글 제목 자리 = 이 편 제목, 자막 줄마다 바뀜. 경보 0 · 기기 1/2 · lease 해제됨
- 못 한 것: 통과작 견본 15편 — 원본 mp4 가 이 PC `C:/숏템_칼카피/…` 에 없고 외장 D 미연결(서버에도 없음) → D 연결 뒤 이 PC 에서 `build_previews.py --kinds result --store <임시>` 로 굽고 서버 `claude_store/preview/result/` 로 올림 · 설치팩 파일은 서버에 안 올림(페이지 '준비 중', 미서명 203MB — 배포 여부 사장님 결정)

## ⏭ 다음
- **타입캐스트 실제 합성 미실측**(이 PC 에 키 없음) — 키 있는 PC 에서 shortem_setup selftest 로 시험 목소리
- 미구현: 고객 채널명 PNG 견본 · 캐시 틀 ±1px 지터 · 자막 효과 2초 견본 · 대본 뒤 extra(짤·효과음) 요청 · 원음 깔기 · 템플릿 자산 사용
- A1 국가 조건은 nginx 에 GeoIP 가 없어 라이브에선 미발동(미등록 기기 조건은 됨)
- 서명: 윈도 코드서명 인증서·Apple Developer(연 99달러) 필요 — 지금 미서명(SmartScreen 경고)
- 맥: `installer/mac/build_mac.sh` 는 `bash -n` 만 통과. 맥 기기 2대에서 libass 정적 ffmpeg 빌드·서명·공증 실측
- Claude Desktop 에서 .mcpb 실제 설치 UI 시험 미실측
