#!/bin/bash
# 숏템 제거(맥) — 설치 폴더에서 두 번 누르면 터미널이 열려 확인 뒤 지운다.
# 지우는 것: ~/Library/Application Support/Shortem · ~/.zshenv 의 숏템 블록 · 로그인 세션 환경변수
# 남기는 것: 바탕화면 '숏템작업'(내 영상) · ~/.shortem(키·캐시) — 고객 자료라 직접 지우게 둔다
# ★맥에서 실측 전(윈도 PC 에서 bash -n 문법 검사만 함)
set -u
TARGET="$HOME/Library/Application Support/Shortem"
echo "숏템을 이 맥에서 지웁니다: $TARGET"
printf "계속할까요? (y/N) "
read -r ans
case "$ans" in y|Y) ;; *) echo "취소했습니다."; exit 0 ;; esac
if [ -f "$TARGET/tools/tools.manifest.json" ]; then
  rm -rf "$TARGET"
  echo "설치 폴더를 지웠습니다."
else
  echo "숏템 설치 폴더가 아니어서 지우지 않았습니다: $TARGET"
fi
if [ -f "$HOME/.zshenv" ]; then
  /usr/bin/sed -i '' '/# >>> shortem >>>/,/# <<< shortem <<</d' "$HOME/.zshenv"
fi
launchctl unsetenv SHORTEM_INSTALL 2>/dev/null || true
launchctl unsetenv SHORTEM_NODE 2>/dev/null || true
for id in com.shortem.installer.arm64 com.shortem.installer.x64; do
  pkgutil --forget "$id" >/dev/null 2>&1 || true
done
echo "끝났습니다. Claude Desktop 의 숏템 확장은 설정 ▸ 확장 프로그램에서 제거하세요."
