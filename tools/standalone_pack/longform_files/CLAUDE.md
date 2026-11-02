# 숏클 지식롱폼

시사·경제 해설 가로 롱폼을 만드는 꾸러미다. 고객은 Claude 만 설치돼 있다. 준비와 제작은 네가 진행한다. 답은 쉬운 한국어로 하고, 명령어·경로·오류 원문을 보여 주지 않는다.

`python` 은 `tools\python\python.exe -X utf8` 이다. 작업 폴더는 `work\<편이름>` 이고 명령 전에 환경변수 `SHORCL_WORK` 를 그 폴더로 둔다. `-m studio` 명령은 이 폴더(꾸러미 맨 위)에서 실행한다.

## 1. 준비

1. 폴더 경로에 한글이나 공백이 있으면 전체를 `C:\shorcl_long` 으로 복사하고, Claude 를 거기서 다시 열어 달라고 말한다.
2. `tools\python\python.exe` 가 없으면 "프로그램을 설치할게요. 3분쯤 걸려요"라고 말하고 `powershell -NoProfile -ExecutionPolicy Bypass -File setup.ps1`.
3. `python steps\keys_input.py`. "메모장이 열리면 키를 붙여넣고 저장한 뒤 닫아 주세요"라고 말한다. 키를 대화로 받지 않는다.
4. `python steps\checkup.py`. 그림 확인에 약 50원이 든다고 먼저 말한다. 막힘이 있으면 쉬운 말로 알리고 그 단계만 다시 한다. 통과 전에는 제작하지 않는다.

## 2. 채널 설정 (처음 한 번)

고객에게 고르게 한다.

| 항목 | 선택지 |
|---|---|
| 채널명 | 자유 |
| 색 | mint, navy, coral |
| 글꼴 | gmarket, pretendard, blackhan |
| 사진 움직임 | pan(이동), zoom(확대) |
| 채널 패 위치 | right, left |

`work\<편이름>\설정.json` 에 쓰고 `python steps\pick_look.py 설정.json`.

## 3. 제작

`README.md` 의 제작 순서와 `guide\` 지침을 그대로 따른다. 기준작은 `sample\` 이다. 쓰기 전에 지침을 읽는다.

긴 실행 전에는 시간과 비용을 한 줄로 말한다. 그림 약 3달러, 렌더 약 10분(GPU 기준)이다. 렌더 전 `steps\shot_board.py` 표를 전부 보고, 앞 25초 샘플을 고객에게 먼저 확인받는다. 막히면 `막힘대응표.md` 를 본다.

## 지키는 것

- 사실기록에 없는 숫자를 쓰지 않는다.
- 방송사 공식 영상을 쓰지 않는다.
- 검사 기준을 낮추지 않는다.
- 사람이 보고 듣기 전에는 합격이라고 말하지 않는다.
- `data\keys` 내용은 읽거나 출력하지 않는다.
