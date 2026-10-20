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

## ⏭ 다음
- 라이브: 병합 뒤 서버에서 `py tools/claude_portal/sync_assets.py` · `build_previews.py` 를 돌려 저장소 채우기(서버엔 짤 1,283·통과작 mp4 있음) → `claude_portal_enabled=admin` 으로 관리자 실측
- **타입캐스트 실제 합성 미실측**(이 PC 에 키 없음) — 키 있는 PC 에서 shortem_setup selftest 로 시험 목소리
- 미구현: 고객 채널명 PNG 견본 · 캐시 틀 ±1px 지터 · 자막 효과 2초 견본 · 대본 뒤 extra(짤·효과음) 요청 · 원음 깔기 · 템플릿 자산 사용
- A1 국가 조건은 nginx 에 GeoIP 가 없어 라이브에선 미발동(미등록 기기 조건은 됨)
- 서명: 윈도 코드서명 인증서·Apple Developer(연 99달러) 필요 — 지금 미서명(SmartScreen 경고)
- 맥: `installer/mac/build_mac.sh` 는 `bash -n` 만 통과. 맥 기기 2대에서 libass 정적 ffmpeg 빌드·서명·공증 실측
- Claude Desktop 에서 .mcpb 실제 설치 UI 시험 미실측
