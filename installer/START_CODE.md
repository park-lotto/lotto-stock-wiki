# 숏템 시작 (Claude Code)

이 파일을 Claude Code 입력창에 끌어다 놓고 엔터를 누르면, Claude 가 아래 순서로 숏템을 연결합니다. 실행 허용을 물으면 '예'를 눌러 주세요.

Claude 에게 — 아래 세 가지만 하세요. 다른 파일은 열거나 고치지 마세요.

1. 이 파일이 있는 폴더 안의 `claude-plugin` 폴더 경로(절대 경로)로 숏템 플러그인을 등록합니다.
   ```
   claude plugin marketplace add "<이 파일이 있는 폴더>/claude-plugin"
   claude plugin install shortem@shortem
   ```
2. 사용자에게 "Claude Code 를 껐다 켠 뒤 `/shortem:setup` 을 입력해 주세요. 라이선스 키는 숏템메이커 '클로드형' 페이지에서 복사합니다"라고 알려 줍니다.
3. 껐다 켠 뒤 `/shortem:setup` 에서 실행 도구가 없다고 나오면, `shortem_setup` 을 `install: true`(설정에 키가 없으면 `license_key` 도)로 불러 설치를 시작하고, 30초마다 다시 불러 진행을 알려 줍니다. 끝나면 한 번 더 껐다 켜 달라고 합니다.
