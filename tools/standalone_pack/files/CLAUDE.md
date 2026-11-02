# 숏템리폿 제작

이 폴더는 숏템리폿 쇼츠를 만드는 꾸러미다. 답은 쉬운 한국어로 하고, 고객에게 명령어나 파일 경로를 보여 주지 않는다.

## 처음

`tools/python/python.exe` 가 없으면 고객에게 "시작.bat 을 더블클릭해 주세요"라고 안내한다. 있으면 `tools/python/python.exe -X utf8 check.py` 를 돌린다. "시작 불가"면 빠진 것을 쉬운 말로 알려 주고 멈춘다.

## 한 편 만들기

아래에서 `python` 은 `tools/python/python.exe -X utf8` 이다.

1. 고객이 준 해외 제품 쇼츠 주소로 `python run.py start <주소>`
2. `python run.py pending` 으로 질문을 본다.
3. 질문마다 그 폴더의 `request.json` 과 그림을 읽고 답을 JSON 으로 쓴다. `need` 칸을 전부 채운다.
4. `python run.py answer <id> <답파일>`
5. `python run.py go`
6. 끝날 때까지 2~5를 되풀이한다. 실행 단계는 오래 걸릴 수 있다. `go` 가 시간으로 돌아오면 다시 `go` 한다.

## 상태별 할 일

| status | 할 일 |
|---|---|
| review, reject | 질문에 답한다. reject 는 이유를 읽고 고쳐 답한다 |
| wait_user | `wait` 내용을 고객에게 보여 주고 확인받은 뒤 `run.py approve` |
| done | 완성 파일을 알려 주고 끝낸다 |
| 그 밖 | 이유를 읽고 고칠 수 있으면 고친 뒤 `run.py retry`. 안 되면 쉬운 말로 알린다 |

수정 요청은 `python run.py revise "L3=고칠 문장"`.

## 지키는 것

- 질문의 규칙을 그대로 따른다. 검사 기준을 낮추지 않는다.
- 근거 없는 수치·후기를 쓰지 않는다.
- 답을 쓰기 전에 그림을 실제로 본다.
- 돈이 드는 재시도가 반복되면 고객에게 먼저 말한다.
- `engine/` 파일은 고치지 않는다.
- `data/keys`, `data/sessions` 내용은 읽어 출력하지 않는다.
