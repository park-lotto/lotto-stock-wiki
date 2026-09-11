# 볼케이노 MCP — 핸드오프 (2026-09-11, 세션 전체 기록)

트랙: 볼케이노MCP · PC: TheRose · 작업 폴더는 main(코드 수정 없음, 문서·설정만)
관련 문서: `channel/volcano/뇌전구_역분석_2026-09-11.md` (규격 실측 본문)

---

## 1. 볼케이노가 무엇인가 (실측)

- **본체는 원격 서버** `https://volcano-mcp.groove1027.workers.dev` (Cloudflare Workers). 이 PC엔 `~/.claude.json`에 연결 설정 한 줄 + OAuth 토큰뿐.
- 설치 프로그램 `Downloads/volcano-setup-windows.exe` (부산 Krisweintz Ltd. 유효 코드서명)가 18:52~19:28에 돌며 `claude mcp login volcano`, 바탕화면 `볼케이노 시작.lnk`, `Desktop/볼케이노작업/` 폴더, `~/.volcano/*.log` 4개를 만들었다.
- ⚠ `볼케이노작업/.vscode/tasks.json`은 폴더를 열면 **`claude --dangerously-skip-permissions`를 자동 실행**한다. 그 창에선 서버 지시가 확인 없이 실행된다. 일반 창에서 쓰면 명령마다 확인이 뜬다 → 일반 창 권장.
- 예약작업·서비스·시작프로그램·훅에 볼케이노 등록 없음. 악성 징후 없음.

## 2. 제작 구조

- MCP 도구 `volcano_video`(숏폼)·`volcano_cardnews`. 서버가 `next_step`을 주면 그대로 따르는 방식.
- 채널(preset) 10개: 린박스·명화관cinema·뇌전구·웃긴버거·어랍숏·인물형·군림보·강석주·쇼핑·인물형 롱폼.
- 첫 편은 `assets` 단계에서 **팩 5종**을 서명 URL(6시간 유효)로 받는다: sfx(효과음 79)·pepe(밈 57)·fonts(4종+라이선스)·runner(실행기 11파일)·framevision(얼굴·OCR 모델 80MB).
- 그 뒤는 실행기 `runner/volcano_drive.py`가 서버와 직접 통신하며 끝까지 돈다. 사람(모델)이 채우는 자리에서만 멈추고 `next_payload.json`을 남긴다.
  ```
  python ./runner/volcano_drive.py --workdir . --step <멈춘단계> --payload ./next_payload.json --tool volcano_video
  ```
- 출입증 `.volcano_runner_key.json`(작업 폴더, 이틀 만료)이 없으면 실행기가 안 돈다. MCP로 `assets`를 부르면 응답에 담겨 온다 → 파일로 저장해야 한다(실행기 형식: token·url·expires·preset).
- 서버가 보내는 API 키 위치·헤더·목적지 URL은 **전부 서버가 지정**한다. 키는 로그에 지문(sha256 앞 12자)만 찍힌다. 구조상 서버 운영자를 신뢰해야 성립.

## 3. 이 PC 준비 상태 (완료)

| 항목 | 위치 | 상태 |
|---|---|---|
| 전용 파이썬 | `~/.volcano/venv` (3.14, pillow·numpy·cv2·onnxruntime 1.29·fonttools·Brotli) | OK |
| whisper | `~/.volcano/whisper-venv`(3.12) + `~/bin/whisper.cmd` shim, 사용자 PATH에 `~/bin` 추가 | OK (새 창부터) |
| 키 | `~/.volcano/keys/{evolink,typecast,speechmatics}` (줄바꿈 없이 값만) | OK |
| ffmpeg 8.1.1 / yt-dlp / curl / pdftotext | 기존 설치 | OK |
| 없음 | textutil(문서 소재) · gemini/serper/naver_hub(인물형 롱폼 전용) | 롱폼만 막힘 |

⚠ Typecast 키는 **`__plt`로 시작하는 개발자 API 키**여야 한다. 64자 hex 키는 401(AUTH_TOKEN_INVALID). EvoLink는 `sk-` 키 정상.

## 4. 오늘 만든 것

- `~/.volcano/jobs/20260911_뇌전구/` → `out/장례식_손절_v001.mp4` (43.3초, 1080×1920) · 바탕화면 사본 `뇌전구_장례식_손절_v001.mp4`
- 다른 창에서 2편 더: `out/volcano/뇌전구_20260911/`(지하철피자 27초), `out/volcano_뇌전구_0009164072/`(개미머니무브 32초)
- 역분석 문서(3편 교차확인 포함) 커밋·푸시 `392acb722`

## 5. 대본 작성 요령 (반려 30건→통과에서 배운 것)

- 제목 구두점 금지 · 자막 쉼표 금지 · 한 줄은 픽셀 폭 기준(대략 12~14자, 5어절) · 강조색 3연속 금지
- 나레는 반말체(~였다/~임/~됨). `-습니다` 과반이면 반려, 격식체 의문문 반려
- 원문 요약이 아니라 **다시 쓰기**. h2에 숫자, 추상명사로 끝내지 않기. card는 읽어주는 한 문장
- 컷마다 `img`(슬롯번호) 또는 `meme: null`. 밈 감정은 10종 문자열 그대로
- **마지막 컷은 RED PUNCH 단정문**으로 닫는 게 관행(다른 두 편 실측). WHITE 나레로 닫으면 경고
- 이미지 프롬프트는 영문, `cast`로 인물 인상착의 고정하면 컷 간 동일 인물. `illustration` 단어는 경고
- 밈에 박힌 글자가 OCR에 걸려 렌더가 멈추면 `photo_text_results['group:N']`을 `text_ids=[] · preserve_text=True`로 고쳐 재시도
- `card_img`는 **숫자**(슬롯번호). `compact_plan=True`, `imgdir='img43'`, `narr_list=['tts/00.wav',…]`

## 6. 팩·폰트·밈 재사용

- 밈 57장 `pepe/fm/`, 폰트 4종 `fonts/`(에스코어 드림 6·7, 여기어때 잘난체, SB 어그로 — 권리자 재배포 허용, LICENSE.txt 동봉), 효과음 79개 `sfx_norm/`. 모두 일반 파일이라 복사해 쓸 수 있다. 밈·효과음 저작권은 미확인.
- 숏템메이커 폰트 라이브러리(`shopping_shorts/static/fonts` 41종)에는 이 4종이 **없다**. 추가하려면 트랙 폴더에서 한글 목록 코드까지 손봐야 한다(영문전용 폰트 두부 전례 주의).
- 다른 채널 팩은 그 채널로 첫 편을 만들 때 받는다. 가짜 소재로 `start`만 거는 방식은 auto 모드 안전장치가 막았다(우회 안 함).

## 7. 프리셋 복제·역분석 한계

- 실행기는 범용 실행 코드. 채널이 무엇인지(대본 검증·줄나눔·타이밍·효과음 순환·밈 매핑)는 서버가 단계마다 내려주는 지시와 반려로만 드러난다.
- 산출물(`sub.ass`·`timing.json`·`render_frames.json`·`sfx_plan`)은 설계도 수준으로 남아 **겉모습 재현은 가능**. 다만 판정 프롬프트·함수 원문은 못 본다. 모방은 볼케이노 약관 문제가 될 수 있음(사장님 판단 몫).

## 8. 깃 주의

- `out/volcano/`·`out/volcano_*/`는 **gitignore** (2026-09-11). 서버 토큰 `.volcano_runner_key.json`과 팩 수백 파일이 들어 있어 auto 커밋이 1,890파일을 쓸어 담았던 것을 되돌렸다(541e3ba88 → 소프트 리셋). 원격에 올라간 적 없음.
- 완성 mp4는 깃에 올리지 않는다(저장소 2.24GB, 서버가 main을 자동 pull). 설계 텍스트만 남긴다.

## ⏭ 다음 할 일

- 다음 뇌전구 편: 마지막 컷 RED PUNCH · ~임체 · 밈 20% 안팎으로 맞춰 제작, `sub.ass` 대조로 "고정값" 재확인
- 원하면 편별 설계 텍스트(대본·timing·sub.ass)를 `channel/volcano/<편>/`에 복사해 재현 자료로 축적
- 인물형 롱폼 쓰려면 Serper·네이버 API HUB(ID/Secret)·Gemini 키 필요
- 실행기 로그에 ffmpeg 전체 인자를 남기는 옵션이 있는지 `volcano_drive.py` 확인(미착수)
