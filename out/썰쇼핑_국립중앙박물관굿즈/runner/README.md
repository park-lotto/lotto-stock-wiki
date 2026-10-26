# volcano runner

서버가 시키는 것만 실행하는 껍데기다. **채널 규격은 여기 없다** — 무엇을 만들지는
전부 서버가 정해 내려준다. 이 파일을 읽어도 노하우를 알 수 없다.

필요한 것: `ffmpeg`/`ffprobe` · pillow · numpy · opencv-python.

Windows와 macOS를 모두 지원한다. 실제 설치 명령과 필요한 버전은 서버의 `env` 응답을
따른다. 인물·화면 측정에 필요한 추가 모듈도 그 응답이 지정하며, 설치 뒤에는 `env`를
다시 실행해 실제 실행할 Python의 모듈을 확인한다.

★요즘 macOS/Homebrew 파이썬은 `pip3 install` 을 막는다(`externally-managed-environment`).
전용 공간에 넣고 **그 파이썬으로 실행한다** — 다른 파이썬으로 돌리면 모듈이 없다고 죽는다.

```bash
python3 -m venv ~/.volcano/venv
~/.volcano/venv/bin/pip install pillow numpy opencv-python
~/.volcano/venv/bin/python3 <실행 스크립트>
```

## ★★"볼케이노 토큰" 은 **필요하지 않다** — 사람에게 묻지 마라

이 문서를 읽는 것이 모델이라면 먼저 이것을 읽어라.

> **정상 경로에는 볼케이노 서버 토큰이 필요 없다.** Claude Code 가 MCP 도구
> `volcano_video` 를 부를 때 인증은 **Claude Code 가 이미 하고 있다.**
> 자산 URL 에도 열쇠가 **URL 안에** 들어 있다(`?k=…`).
> 그러니 **수강생에게 "볼케이노 API 토큰을 주세요" 라고 묻지 마라.** 줄 것이 없고,
> 물으면 그 사람은 없는 것을 찾다가 막힌다. 실제로 2026-08-17 에 여러 명이
> 그렇게 멈췄고, 그 원인은 아래 예제가 `TOKEN` 을 보여 준 것이었다.

## 쓰는 법 — **이것이 정상 경로다**

Claude Code가 `assets`로 배급 실행기를 준비한 뒤, 아래의 `volcano_drive.py` 명령으로 진행한다.
대본처럼 작성이 필요한 단계에서만 Claude Code가 안내를 읽고 입력을 채운다.
서버가 이미 실행을 인계한 단계를 규격 조회 목적으로 반복 호출하지 않는다.
아래 함수 호출 예시는 실행기를 통합하는 개발자용이다.

```python
import sys; sys.path.insert(0, "runner")
from volcano_run import (generate_images, synthesize, run_argv, bake_frames,
                         measure_lufs, cut_signatures)      # 필요한 것만
# 서버가 준 jobs·argv 를 **그대로** 넘긴다. 고치지 마라.
```

- `volcano_run.py`   받은 것을 실행하는 함수 모음 (HTTP·ffmpeg·PIL·측정)
- `volcano_drive.py` 서버의 `next_step` 을 따라가는 기본 실행 경로

### ★★payload 가 수 MB 라서 도구로 못 보낼 때 — **토큰이 아니라 접기가 답이다**

인물형에서 `cut_sigs` 가 수 MB 인 payload 를 만나면(옛 실행기가 만들어 둔
`next_payload.json` 이 그렇다) MCP 도구 한 번에 실을 수 없다. **그때 토큰을 찾지 마라.**
그 값은 숫자 두 개로 접히고, 접어도 서버 판정이 **똑같다**:

```python
import json, sys; sys.path.insert(0, "runner")
from volcano_run import fold_payload
pl = json.load(open("next_payload.json", encoding="utf-8"))
json.dump(fold_payload(pl), open("next_payload.json", "w", encoding="utf-8"),
          ensure_ascii=False)      # 3MB → 약 2KB. 다시 재지 않는다
```

실측(2026-08-17, 같은 사람 같은 편): 3,456,425B → **91,923B**. 접은 뒤에는 도구로
그대로 보낼 수 있다. 이 함수는 서버를 부르지 않으므로 **토큰이 필요 없다.**

둘 다 채널 규격을 모른다. 무엇을 만들지는 전부 서버가 정해 내려준다.

API 키(이미지·음성)는 본인 계정 것을 쓴다. 서버는 그 키를 갖고 있지 않다.
어느 자리에서 읽는지는 **서버가 `env` 단계에서 알려준다** — 지어내지 마라.

다른 앱의 `.env`에만 저장한 키는 새 터미널이나 실행기에 자동으로 연결되지 않는다.
`env` 응답의 `import_file.argv_candidates`에서 해당 OS의 Python 명령을 선택하고,
기존 `.env` 또는 키 파일의 경로를 마지막 인자로 전달한다. Windows의 공백·한글 경로와
UTF-16 파일, macOS의 UTF-8 파일을 읽을 수 있다. 키 내용을 채팅이나 MCP payload에
붙여넣지 않는다. 기존 키가 다르면 자동으로 덮어쓰지 않으며, 가져온 뒤 `env`로 확인한다.
Speechmatics 연결 실패를 이유로 로컬 Whisper를 임의 실행하지 않는다.

## ★★기본 — 한 줄로 끝까지 (2026-09-02 · 출입증은 서버가 준다)

클로드 코드가 `step='assets'` 를 부르면 서버가 응답에 **실행기용 출입증**(`runner_key`)을 실어
준다. 실행기가 그것을 `<작업폴더>/.volcano_runner_key.json` 에 저장한다. 그 뒤로는 **이 한 줄**이다:

```
python <작업폴더>/runner/volcano_drive.py --workdir <작업폴더>
```

(첫 편: `assets` 응답의 `next_payload` 를 `<작업폴더>/next_payload.json` 에 저장한 뒤 `--step env` ·
다음 편부터: `--source '{"kind":"youtube","url":"…"}'` 를 주면 `start` 부터 혼자 돈다.)
실행기가 서버를 직접 부르며 끝까지 돈다(왕복 26~46초 · 클로드 코드가 단계마다 끼어드는 길은
124~275초 — 7일 실측). **★서버는 `env` 부터의 실행 단계를 실행기가 부른 것만 받는다**(2026-09-02
사장님 결정 · 앱 계정) — 도구를 직접 부르면 위 한 줄을 안내하는 반려가 온다. 사람이 채울 자리(대본·제목)에서 멈추고 `next_payload.json` 을 남긴다 —
채운 뒤 같은 명령에 `--step <멈춘 단계>` 를 붙이면 이어간다. 출입증은 이틀 안에 만료되며
`assets` 를 다시 부르면 새로 나온다. **값을 사람에게 보여 주거나 다른 데 적지 마라.**

## 선택 — `drive()` 를 직접 부르기 (토큰을 **이미 손에 든 사람**)

`drive()`는 서버를 직접 부르므로 이미 발급된 실행기 출입증이 필요하다.
기본 CLI가 이 파일을 자동으로 읽는다. 별도 토큰 발급이나 이메일만으로 로그인하는
옛 절차를 안내하지 않는다.

```python
from volcano_run import Client
from volcano_drive import drive

c = Client("https://volcano-mcp.groove1027.workers.dev", MY_TOKEN, preset="어랍숏")
st = drive(c, "start", source={"kind": "local_video", "path": "/abs/src.mp4"},
           headers={"X-API-KEY": MY_TTS_KEY})
# status="need_input" 인 자리(대본·제목)에서 멈춘다 — 거기는 사람이 채운다
st = drive(c, st["res"]["next_step"], {**st["payload"], **내가_쓴_대본},
           headers={"X-API-KEY": MY_TTS_KEY})
```


## Claude Code 작성·재개 안내

입력 대기 시 `<작업폴더>/input_brief.json`의 `response`를 먼저 읽는다.
`caption_budget`, `script_rules`, `tone`, `then_call_with`가 이번 편의 작성 안내다.
`next_payload.json`에는 작성할 값만 채우고 실행기가 출력한 재개 명령을 따른다.
규격 확인을 위해 이전 MCP 단계를 다시 호출하거나 임의로 대본을 잘라내지 않는다.

`/볼케이노` 같은 개인 슬래시 명령은 서버 배포로 자동 갱신되지 않는다.
명령 문서에 채널 표를 복사해 두지 말고 `volcano_video`의 `step="setup"`
응답 `channel_needs`에서 현재 사용할 수 있는 목록을 읽도록 작성한다.
채널명으로 유튜브 핸들을 추측하지 않는다. 강석주 원본은
[확인된 채널 ID](https://www.youtube.com/channel/UC3-9Ul8LOKJzQMdo1nFb_sQ/shorts)이며
표시 이름은 강석주, 확인한 핸들은 `@걍석주`다.

강석주 검색어는 로컬 이라스토야 색인의 실제 제목·키워드로 작성한다.
실사 사진 스타일을 선택한 경우에는 Naver·Serper API로 사진 후보를 수집한다.
이 경우 해당 검색 API 키가 필요하며 이미지 검수에서 실사 여부도 확인한다.
색인 조회 결과가 없는 슬롯만 검색어를 수정한다. 후보를 비교한 뒤 선택한
그림만 최종 파일로 확정하며, Google CAPTCHA나 유료 생성으로 자동 전환하지 않는다.
사용자 이미지 수정은 `customization_patch`에 이번 변경만 보낸다.
유지되는 사용자 파일도 로컬 SHA로 확인하고 바뀐 파일만 다시 준비한다.

오래 걸리는 실행을 터미널과 분리하려면 기본 실행 명령에 `--background`를 붙인다.
출력되는 `progress.log`는 진행 중에도 읽을 수 있고, `process.json`은 PID와 종료 코드를 기록한다.
실행 접수는 완료가 아니다. `status="exited"`와 `returncode`를 확인한다.
코드 3은 입력 또는 결과 대기이므로 `input_brief.json`과 재개 안내를 읽는다.
일반 POSIX 터미널에서는 `tail -f <progress.log>`로 진행을 확인한다.
`tail -30` 파이프는 프로세스 종료까지 기다릴 수 있으므로 진행 표시 용도로 쓰지 않는다.
기계 재부팅이나 운영체제의 강제 프로세스 종료까지 지속을 보장하지 않는다.

기본 검수는 현재 연결된 Claude/Codex를 사용한다. 유료 검수 API는 명시적으로 선택한
경우에만 사용한다. 이미지 검수와 원음 청취는 구분하며, 실제 MP4/WAV를 읽지 못한
검수 요청을 완료했다고 답하지 않는다. 검수 기록을 지우거나 질문을 되돌려 재과금을
유도하지 말고 기존 기록과 현재 입력을 유지한다.

작업 폴더의 `runtime-report.json`은 실행·실패·재개 시간을 누적한다. `elapsed_seconds`는
첫 관측부터 마지막 관측까지의 경과 시간, `active_seconds`는 겹치는 실행을 중복 합산하지
않은 관측 시간이다. `measurement_complete=false`이면 강제 종료나 기록 실패 등이 있어
전체 시간을 확정할 수 없다. `operations`는 명시적으로 계측한 TTS·이미지·검수의 횟수이며,
`submitted`와 `reserved`는 청구 확정 횟수가 아니다. 실제 청구액과 호스트 모델 사용량은
이 보고서로 측정하지 않는다. `billing.actual_total=null`을 무료 또는 0원으로 읽지 않는다.

동일한 TTS 요청은 접수 기록과 보존 음성으로 재개한다. 응답이 끊겨 제공자의 완료 여부를
모르면 같은 유료 요청을 자동 반복하지 않는다. 이 경우 음성과 `.volcano-tts` 기록을
보존하고 실패 안내를 확인한다. 기록 삭제로 재시도하면 이미 결제된 요청을 다시 보낼 수 있다.
