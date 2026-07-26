# AE영상제작 (영상제작 방향) — 핸드오프

> 소유 트랙: **AE영상제작** · 이 파일은 이 트랙 세션만 수정한다.
> 최종 갱신: 2026-07-26 (사무실 PC) · 다음: 집에서 이어감

**트리거**: "AE영상제작 이어서" → 이 파일 + `out/AE_클로드_고퀄영상_계획.md` 읽고 시작

---

## 🆕 2026-07-26 세션 — 방향 전환: AE 단독 → Remotion 주력 + 음성 파이프라인 확립

**핵심 결정**: 영상은 **컴퓨터 화면 only**. 제작은 **Remotion 주력(≈80%)** + AE는 킬러컷 마감만.

### ① 대본 확정 (out/숏템박스_1회차_VSL_대본.md)
- S2·S3 → **한 씬(S2, 0:40–3:20)으로 통합**, 중복 제거. 이후 사장님이 S1·S2·S4·S5·S6 직접 다듬음.
- S6 = "증거 + 실행은 본인 몫"으로 피벗. 씬번호는 S3 없이 S2→S4 (재정렬 안 함).

### ② 음성 파이프라인 확립 (★재현 핵심)
- **TTS = 일레븐랩스 v3, Liam(Energetic) 음성으로 통일, 안정성=Robust, 블록 통째 생성**(문단 쪼개면 목소리 튐).
- v3는 **속도 슬라이더 없음** → 느리면 `ffmpeg atempo 1.1~1.2배`(음정 유지)로 가속. 실측: 53.8s→46.8s(1.15x)/44.8s(1.20x).
- **실수/더듬음 자동 편집**: `faster-whisper`(설치됨) 단어별 타임스탬프 → 잘못말한 구간 컷 → whisper 재전사로 검증. Gemini 타임스탬프는 단어단위 부정확해서 못 씀.
  - 코드 흐름: m4a→ffmpeg wav→faster-whisper word_timestamps→구간 aselect 컷→재전사 확인.
- 바탕화면 산출물: `S1_음성_수정본.mp3`(더듬음 정리본), `S1_속도1.15.mp3`/`S1_속도1.20.mp3`.

### ③ 타입캐스트/일레븐 대사 파일 (바탕화면)
- `숏템메이커_VSL_일레븐랩스_대사.txt` — 씬별 [감정태그]+호흡 (v3용, S5는 S5-1~7+마무리 분할).
- `숏템메이커_VSL_타입캐스트_대사.txt` — 태그 없는 순수 대사(참고용).

### ④ 씬별 제작 정리 (바탕화면 `숏템메이커_VSL_제작정리_S2부터.txt`)
- **사장님 녹화 필요**: S1(완성쇼츠3), S2(유튜브검색·캡컷), S4(터미널·대시보드), S5(제품데모 원테이크), S6(카톡·결과물).
- **녹화 없이 Claude 단독 제작 가능**: **S7·S8·S9·S10 + S4 원리도식**.

### ⏭ 다음 (집에서)
1. **S8(타이머·혜택 스택) Remotion 프로토타입**부터 뽑아 퀄리티 감 잡기(추천). 또는 사장님 지정 씬.
2. S1은 완성 쇼츠 3개 mp4 오면 트립틱 콜드오픈 조립.
3. S2~ 씬별 음성 mp3 오면 whisper 정리 → 속도 → Remotion 싱크.

---

## 한 줄

숏템메이커 **런칭 VSL**을 만들기 위해, **Claude가 After Effects를 코드로 조종하는 파이프라인**을 세웠다.
**P0(조종 가능한가) 전부 통과.** 지금은 **화면녹화 도구 3종 비교 테스트** 단계.

---

## ✅ 오늘 확정된 것 (P0 — 전부 실측 통과)

| # | 검증 | 결과 |
|---|---|---|
| ① | 모달 대화상자로 멈춤 | ✅ 방어 확보 (억제 안 하면 **실제로 멈춤** 실증) |
| ② | aerender 렌더 | ✅ `aerender version 26.3x87`, exit 0 |
| ③ | **템플릿 `.aep` 열기·치환·저장** | ✅ **통과 — 계획의 축** |
| ④ | 한글 폰트 | ✅ Bold/Regular·₩·가운뎃점 정상 렌더 |

**증거물**(바탕화면): `AE_한글렌더_검증.png`, `AE_템플릿치환_검증.png`

---

## 🔧 환경 — 집 PC에서 다시 세팅해야 하는 것

> ⚠️ 아래는 **사무실 PC에만** 설치돼 있다. 집 PC에서는 다시 해야 한다.

| 항목 | 위치 / 방법 |
|---|---|
| After Effects 2026 | Adobe CC 월간 구독 ₩46,200 (계정 공유되므로 집에서도 설치 가능) |
| **after-effects-mcp** | `git clone https://github.com/Dakkshin/after-effects-mcp` → `npm i` → `npm run build` |
| **★브리지 패치** | `mcp-bridge-auto.jsx`에 **`executeScript` 케이스를 직접 추가**했다. 아래 "재현 방법" 참조 |
| 브리지 설치 | `npm run install-bridge` → **실패해도 "성공"이라 출력하므로 파일 존재를 직접 확인** → 없으면 관리자 권한으로 수동 복사 |
| MCP 등록 | `claude mcp add --scope user AfterEffectsMCP -- node <경로>/build/index.js` |
| AE 설정 | 편집>환경설정>스크립팅및표현식 → **"스크립트에서 파일 쓰기 및 네트워크 액세스 허용"** 체크 → AE 재시작 |
| 패널 열기 | 창 > `mcp-bridge-auto.jsx` → **Auto-run commands** 체크 |

### ★ executeScript 패치 재현 방법
`build/scripts/mcp-bridge-auto.jsx`와 `src/scripts/mcp-bridge-auto.jsx` 양쪽에:
1. `\n// Execute command` 앞에 `executeScriptCmd(args)` 함수 삽입
   (args.script = 코드 문자열 / args.file = .jsx 경로, `eval` 실행 후 JSON 반환)
2. switch 문의 `            default:` 앞에 `case "executeScript":` 추가
3. 관리자 권한으로 `C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Scripts\ScriptUI Panels\`에 복사
4. **AE에서 패널을 닫았다 다시 열어야 반영됨**

---

## ⚠️ 실측으로 확정된 함정 (다시 밟지 말 것)

1. **`run-script` MCP 툴은 화이트리스트 20개 전용** — 임의 스크립트 실행 아님. 그래서 `executeScript`를 직접 추가한 것.
2. **브리지는 MCP 툴 없이 파일로 직접 호출 가능** (세션 재시작 없이 테스트할 때 유용)
   - 명령: `C:\Users\<user>\Documents\ae-mcp-bridge\ae_command.json`
     `{"command":"executeScript","args":{"file":"...jsx"},"status":"pending"}`
   - 결과: 같은 폴더 `ae_mcp_result.json` (2~3초)
3. **모달 억제 필수** — `app.open()` 전에
   `app.beginSuppressDialogs()` + `app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES)`
   안 하면 "변경사항 저장?" 대화상자로 **status=running에서 영구 정지**
4. **한글 폰트는 PostScript명** — `MalgunGothic` ✅ / `Malgun Gothic` ❌ (공백 오류)
5. **aerender 템플릿명은 한글판 기준** — `"최고 설정"` / `"손실 없음"` (영문 `"Best Settings"` 없음)
6. **`AfterFX.exe -r script.jsx`는 40초 무응답으로 실패** (원인 미규명). 브리지 경로를 쓸 것.
7. **Program Files 쓰기는 관리자 권한 필요**

---

## 📍 지금 위치 — 녹화 도구 비교 테스트 (미완)

**왜 하나**: 요청하신 8개 효과 중 ①화면 3D 기울임 ②클릭 줌·커서 강조는
**AE 템플릿이 아니라 녹화 도구가 자동으로** 해준다. 이게 되면 AE 템플릿 구매량이 줄어든다.

### 진행 상황

| 도구 | 무료 조건 | 테스트 |
|---|---|---|
| **Cursorful** (크롬 확장) | 내보내기 무제한 · **비상업용** · 4K ❌ | ✅ **완료** |
| **FocuSee** (데스크톱) | **4K 1편** 내보내기 가능 | ⏳ 미완 |
| **Canvid** (데스크톱) | **내보내기 불가**(미리보기만) | ⏳ 미완 |

### Cursorful 테스트 결과 (바탕화면 `cursorful-video-1784979179235.mp4`, 23.1초/1496×1080)
- ✅ 자동 줌·팬 작동, 배경+라운드코너+그림자 좋음 → **AE 목업 템플릿 불필요 판정**
- ⚠️ 고칠 것 3개: **탭·북마크바 9개 노출** / **1496×1080(4K 아님)** / **줌 과다로 좌측 잘림**
- 판정: **도구는 합격**, 위 3개는 전부 설정 문제

### 다음 액션
1. FocuSee 설치 → 동일 30초 시나리오 → **4K로 1편 내보내기** (`focusee_test.mp4`)
   - 워터마크 붙는지 확인
2. Canvid 설치 → 동일 시나리오 → **편집기 스크린샷 3~4장**
3. 셋 비교 → 하나 결제
   - Canvid Desktop **$75 평생**(정가 $159 할인) / Cursorful Pro **$79 일회** / FocuSee 확인 필요

**동일 30초 시나리오** (비교하려면 같은 걸 찍어야 함):
레퍼런스 랭킹 → 카테고리 클릭(3초 내 2번) → [대본 추출] 클릭(3초 내 2번) → 세그먼트 팝업 ★ → 담기
공통 준비: 브라우저 최대화 / 탭·북마크 숨기기 / 줌 깊이 낮추기

---

## 💰 비용 현황

| 항목 | 상태 |
|---|---|
| After Effects 월간 ₩46,200 | ✅ 결제 완료 (무약정, 언제든 해지) |
| 녹화 도구 $75~79 | ⏳ 비교 후 하나 |
| Envato Elements $39 (1개월) | ⏳ 템플릿 목록은 작성됨 (`out/AE_템플릿_쇼핑리스트.md`) |
| Trapcode Particular 40만원대 | ❌ P3에서 실제로 막힐 때만 |

---

## 📄 관련 문서

| 파일 | 내용 |
|---|---|
| `out/AE_클로드_고퀄영상_계획.md` | **메인 계획서** · P0 결과 · 운영 규칙 · P1~P4 |
| `out/AE_템플릿_쇼핑리스트.md` | Envato에서 받을 6종 + 검색어 + 선정 기준 |
| `out/녹화도구_비교테스트_가이드.md` | 3종 비교 절차 |
| `out/Cursorful_테스트가이드.md` | Cursorful 사용법 |
| `out/AE_체험판_설치가이드.md` | AE 설치·해지 |
| `out/숏템박스_1회차_VSL_대본.md` | **VSL 대본 S1~S10** (조립 대상) |
| `out/숏템박스_VSL_촬영제작시트.md` | 촬영 분담표 |
| `out/fx_3d_ui_scene.html` · `fx_3d_ui_render.mjs` | 폐기된 Three.js 경로(참고용) |

---

## ⏭ 미결 (우선순위)

1. **녹화 도구 3종 비교 완료 → 결제 확정** ← 지금 여기
2. Envato 결제 → 템플릿 다운 → Claude가 `.aep` 구조 분석·한글 주입·시험 렌더 (P1)
3. **★진짜 병목: 촬영 소재.** 대본 체크리스트 8개가 전부 미완
   (완성 쇼츠 3개 / 빌드 몽타주 / 페인 짚기 캡처 / 베타테스터 후기 / 실루엣 세팅 / S5 원테이크)
4. P2 자동 조립 파이프라인 (JSON → MP4)
5. 프리미어 MCP는 P0 통과 후 별도 검토 (무음 컷·숏폼 슬라이싱에 유용, AE+Pr이면 모든앱 ₩46,860이 유리)

---

## 🧹 정리 필요

- 사무실 AE에 `P0_TEST` 컴프와 테스트 프로젝트(`C:\Users\TheRose\tools\ae-test\*.aep`) 잔존 — 무해하나 나중에 삭제
