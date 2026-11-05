#!/bin/bash
# 맥 설치 리허설(관제 328) — 리눅스 서버에서 installer/install.sh 를 실제로 돌린다. 맥이 없어서 만든 도구.
# 윈도 흉내로는 유닉스 동작(SIGPIPE·심볼릭 링크·권한)을 못 잡는다(11-05 고객 맥미니 'cmd | grep -q' 오판). 리눅스는 맥과 같은 유닉스라 잡힌다.
#   맥 전용 명령(uname·sw_vers·sysctl·plutil·ditto·stat -f·xattr)만 흉내 내고, 실행 도구는 리눅스판(node·ffmpeg·python3)으로 채운다.
#   라이브 서버·진짜 회원 인증값(관리자 줄)·진짜 맥 묶음을 받는다. Claude 설정은 임시 HOME/CLAUDE_CONFIG_DIR 라 서버 설정은 안 건드린다.
# 쓰는 법(서버): bash mac_rehearsal.sh <install.sh> <관리자 맥 줄 파일> [--claude-install]
#   --claude-install : PATH 에서 claude 를 숨겨 Claude Code 설치 분기까지 돈다(임시 HOME 의 ~/.local/bin 에 깐다)
# 못 재는 것: 맥 실행 파일(크롬·ffmpeg·파이썬 맥판) 실행, 브라우저 로그인 — 실행 도구 단계는 리눅스판을 미리 깔고 표시로 건너뛴다.
set -uo pipefail
SCRIPT="$1"; LINE="$2"; MODE="${3:-}"
R=/tmp/mr; ST="$R/stub"; H="$R/home"
rm -rf "$H" "$R/bin"; mkdir -p "$ST" "$H"
APP="$H/Library/Application Support/Shortem"
REPO=/home/ubuntu/lotto-stock-wiki

mk() { printf '#!/bin/bash\n%s\n' "$2" > "$ST/$1"; chmod 755 "$ST/$1"; }
mk uname   'case "$1" in -s) echo Darwin;; -m) echo arm64;; *) /usr/bin/uname "$@";; esac'
mk sw_vers 'echo 15.6'
mk sysctl  'echo 0'
mk xattr   'exit 0'
mk ditto   'if [ "$1" = -x ]; then /usr/bin/unzip -q -o "$3" -d "$4"; else mkdir -p "$2"; cp -a "$1"/. "$2"/; fi'
mk stat    '[ "$1" = "-f%z" ] && { /usr/bin/stat -c %s "$2"; exit; }; /usr/bin/stat "$@"'
mk plutil  'python3 -c "
import json,sys
d=json.load(open(sys.argv[1],encoding=\"utf-8\"))
for k in sys.argv[2].split(\".\"):
    if not isinstance(d,dict) or k not in d: sys.exit(1)
    d=d[k]
print(str(d).lower() if isinstance(d,bool) else d, end=\"\")" "$6" "$2"'

# 실행 도구(리눅스판) + 표시 — install.sh 가 같은 잠금 파일·부품 목록이면 건너뛴다
T="$APP/tools"; mkdir -p "$T/node/bin" "$T/ffmpeg" "$T/python/bin" "$T/chrome-headless-shell" "$T/yt-dlp"
cp /usr/bin/node "$T/node/bin/node"; cp /usr/bin/ffmpeg /usr/bin/ffprobe "$T/ffmpeg/"
ln -s /usr/bin/python3 "$T/python/bin/python3"
printf '#!/bin/sh\necho "HeadlessChrome 131 (리허설)"\n' > "$T/chrome-headless-shell/chrome-headless-shell"
printf '#!/bin/sh\nexec python3 -m yt_dlp "$@"\n' > "$T/yt-dlp/yt-dlp"; chmod 755 "$T"/*/* "$T/node/bin/node"
node "$REPO/installer/common/write_manifest.js" --stage "$APP" --plat darwin-arm64 --version 0.0.0 --lock "$REPO/installer/common/tools.lock.json" || { echo "리허설: write_manifest 실패"; exit 2; }
WANT="$(cat "$REPO/installer/common/tools.lock.json" "$REPO/installer/common/requirements-engine-py312-mac.txt" | shasum -a 256 | awk '{print $1}')-darwin-arm64"
printf '%s' "$WANT" > "$T/.mac-tools"

P="$ST:/usr/local/bin:/usr/bin:/bin"
if [ "$MODE" = --claude-install ]; then        # claude 를 뺀 /usr/bin 사본
  mkdir -p "$R/bin"; for f in /usr/bin/*; do [ "$(basename "$f")" = claude ] || ln -s "$f" "$R/bin/"; done
  P="$ST:$R/bin"
fi
TOKEN="$(sed -E "s/^SHORTEM_START='([^']+)'.*/\1/" "$LINE")"
BASE="$(grep -oE 'https://[^/]+' "$LINE" | head -1)"
echo "리허설: $BASE · $( [ "$MODE" = --claude-install ] && echo 'Claude Code 설치 분기 포함' || echo 'claude 있음')"
env -i HOME="$H" PATH="$P" TERM=dumb LANG=en_US.UTF-8 CLAUDE_CONFIG_DIR="$H/.claude" \
  SHORTEM_START="$TOKEN" SHORTEM_BASE="$BASE" SHORTEM_INSTALL_DIR="$APP" SHORTEM_NO_LAUNCH=1 \
  bash "$SCRIPT"
rc=$?
echo "리허설: 종료코드 $rc"
echo "--- 결과물"
ls "$APP" | head -20
ls -la "$H/.shortem/" 2>/dev/null | head
[ -f "$H/.zshenv" ] && { echo "--- .zshenv"; cat "$H/.zshenv"; }
[ -d "$H/.shortem/work" ] && ls -la "$H/.shortem/work" "$H/.shortem/work/.claude"
exit $rc
