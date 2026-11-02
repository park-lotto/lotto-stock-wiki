# 숏템리폿 제작

이 폴더는 숏템리폿 쇼츠를 만드는 꾸러미다. 고객은 Claude 만 설치돼 있다. 나머지 준비는 네가 한다. 답은 쉬운 한국어로 하고, 명령어·파일 경로·오류 원문을 고객에게 보여 주지 않는다.

아래에서 `python` 은 `tools\python\python.exe -X utf8` 이다.

## 1. 폴더 자리

폴더 경로에 한글이나 공백이 있으면 영상 도구가 멈춘다. 그러면 이 폴더 전체를 `C:\shorcl` 로 복사하고, 고객에게 "준비 폴더를 옮겼어요. Claude 를 C:\shorcl 에서 다시 열어 주세요"라고 말한다.

## 2. 준비 (순서대로, 끝난 단계는 건너뛴다)

1. 도구: `tools\python\python.exe` 가 없으면 `powershell -NoProfile -ExecutionPolicy Bypass -File setup.ps1 -ToolsOnly`. 먼저 "필요한 프로그램을 설치할게요. 3분쯤 걸려요"라고 말한다.
2. 키: `python keys_input.py`. 먼저 "메모장이 열리면 키를 붙여넣고 저장한 뒤 닫아 주세요"라고 말한다. 키를 대화로 받지 않는다.
3. 로그인: `python login.py`. 먼저 "창이 열리면 유튜브, 인스타그램, 틱톡에 로그인해 주세요"라고 말한다.
4. 검수: `python check.py`. "시작 불가"면 빠진 것을 쉬운 말로 알리고 그 단계만 다시 한다.

## 3. 한 편 만들기

고객이 영상 주소를 안 줬으면 달라고 한다. 해외 제품 쇼츠 주소다.

1. `python run.py start <주소>`
2. `python run.py pending` 으로 질문을 본다.
3. 질문 폴더의 `request.json` 과 그림을 읽고 답을 JSON 으로 쓴다. `need` 칸을 전부 채운다.
4. `python run.py answer <id> <답파일>`
5. `python run.py go`
6. 끝날 때까지 2~5를 되풀이한다. `go` 가 시간으로 돌아오면 다시 `go`.

단계가 바뀔 때마다 고객에게 한 줄로 알린다. 예: "대본을 쓰는 중이에요".

| status | 할 일 |
|---|---|
| review, reject | 질문에 답한다. reject 는 이유를 읽고 고쳐 답한다 |
| wait_user | `wait` 내용을 고객에게 보여 주고 확인받은 뒤 `run.py approve` |
| done | 완성 파일 위치를 알려 준다 |
| 그 밖 | 이유를 읽고 준비 단계를 다시 하거나 `run.py retry`. 그래도 안 되면 쉬운 말로 알린다 |

수정 요청: `python run.py revise "L3=고칠 문장"`.

## 지키는 것

- 질문의 규칙을 그대로 따른다. 검사 기준을 낮추지 않는다.
- 근거 없는 수치·후기를 쓰지 않는다.
- 답을 쓰기 전에 그림을 실제로 본다.
- 돈이 드는 재시도가 반복되면 고객에게 먼저 말한다.
- `engine` 폴더는 고치지 않는다.
- `data\keys`, `data\sessions` 내용은 읽거나 출력하지 않는다.
