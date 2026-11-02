# 숏템 시작

숏템을 이 Claude Code 에 연결하는 입구입니다. 아래 두 줄로 숏템 플러그인을 등록해 주세요(실행 허용을 물으면 '예').

```
claude plugin marketplace add "{{PLUGIN_DIR}}"
claude plugin install shortem@shortem
```

등록이 끝나면 Claude Code 를 껐다 켜고, 입력창에 `/plugin configure shortem@shortem` 으로 라이선스 키를 붙여 넣은 뒤 `/shortem:setup` 을 실행해 주세요.
