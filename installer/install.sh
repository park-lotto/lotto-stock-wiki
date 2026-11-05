#!/bin/bash
# 숏클 맥 설치(관제 328) — 회원 페이지 '설치 명령 복사하기'(맥)가 터미널에 붙여 넣는 한 줄이 부른다.
#   SHORTEM_START='<인증값>' bash -c "$(curl -fsSL <주소>/api/claude/start.sh)"
# 윈도 installer/install.ps1 과 같은 순서·같은 서버 함수: 회원 확인 → 묶음 → 실행 도구 → 키 저장 → Claude Code → 플러그인 → 작업 폴더 → 로그인 → 점검.
# 판단 주인: 키·인증 = claude_portal.start_redeem · 묶음 = install_info(plat=mac-arm64|mac-x64) ·
#   맥 실행 도구 출처·해시 = installer/common/tools.lock.json(darwin-*) · 엔진 부품 = requirements-engine-py312-mac.txt(mac_requirements.py) ·
#   풀기 후 검사 = postinstall.js(묶음 안). 맥 묶음은 서버에서 make_mac_bundle.py 가 윈도 묶음에서 tools/ 를 빼고 mac/ 을 넣어 만든다.
# 애플칩(맥미니 M 시리즈 등)·인텔 맥 둘 다 — uname -m 으로 갈라 받는다. 둘 다 macOS 14 이상.
# 시험 환경변수: SHORTEM_BASE · SHORTEM_INSTALL_DIR · SHORTEM_NO_PERSIST(셸 설정 안 씀) · SHORTEM_NO_LAUNCH(Claude 안 띄움)
set -uo pipefail
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

SHORTEM_HOME="${SHORTEM_HOME:-$HOME/.shortem}"
mkdir -p "$SHORTEM_HOME"
LOG="$SHORTEM_HOME/install.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1        # 실패하면 이 파일을 보내 달라고 안내한다(맥은 우리가 직접 못 본다)

say() { printf '[숏클] %s\n' "$*"; }
die() {   # stderr 로 — $(get …) 안에서 불려도 문구가 삼켜지지 않는다
  printf '\033[31m[숏클] 설치를 마치지 못했습니다: %s\033[0m\n' "$*" >&2
  printf '[숏클] 같은 줄을 다시 붙여 넣으면 받은 것은 이어서 씁니다. 계속 안 되면 이 파일을 보내 주세요: %s\n' "$LOG" >&2
  exit 1
}

BASE="${SHORTEM_BASE:-__BASE__}"; BASE="${BASE%/}"
TOKEN="${SHORTEM_START:-}"
[ -n "$TOKEN" ] || die '설치 명령을 숏템메이커 페이지에서 새로 복사해 주세요'

# ── 컴퓨터 확인 ───────────────────────────────────────────────────────────────
[ "$(uname -s)" = Darwin ] || die '맥에서만 쓰는 설치 명령입니다(윈도는 페이지의 윈도 명령을 쓰세요)'
case "$(uname -m)" in
  arm64)  PLAT=mac-arm64; LPLAT=darwin-arm64; CHIP='애플 칩' ;;
  x86_64)
    if [ "$(sysctl -in sysctl.proc_translated 2>/dev/null)" = 1 ]; then PLAT=mac-arm64; LPLAT=darwin-arm64; CHIP='애플 칩'   # 로제타 터미널
    else PLAT=mac-x64; LPLAT=darwin-x64; CHIP='인텔'; fi ;;
  *) die "모르는 맥 종류입니다($(uname -m))" ;;
esac
OSV="$(sw_vers -productVersion 2>/dev/null || echo 0)"
[ "${OSV%%.*}" -ge 14 ] 2>/dev/null || die "macOS 14(Sonoma) 이상이 필요합니다. 지금 버전은 $OSV 입니다. 시스템 설정 > 일반 > 소프트웨어 업데이트에서 올린 뒤 다시 해 주세요"
say "맥 확인: $CHIP · macOS $OSV"

# 값 하나 꺼내기(macOS 기본 plutil 은 JSON 도 읽는다 — 아직 node·python 이 없을 때 쓴다)
# 값이 없으면 빈 값 — plutil 이 실패하면 무엇을 찍었든 버린다(고객 맥 11-05: 크롬 확인값 대조 실패 뒤 단단히)
jget() { local v; v="$(plutil -extract "$2" raw -o - "$1" 2>/dev/null)" || return 0; printf '%s' "$v"; }
sha_of() { shasum -a 256 "$1" | awk '{print $1}'; }
# out_has <정규식> <명령…> — 출력을 다 받은 뒤 찾는다. 'cmd | grep -q' 는 grep 이 먼저 끝나 cmd 가 SIGPIPE(141)로 죽고
#   pipefail 때문에 '없다'가 된다(고객 맥미니 11-05: 자막 필터가 있는데 'ffmpeg 에 자막 기능이 없습니다'). 이 꼴을 새로 쓰지 마라.
out_has() { local re="$1" o; shift; o="$("$@" 2>&1)"; grep -Eq -- "$re" <<<"$o"; }

# ── 회원 확인 ─────────────────────────────────────────────────────────────────
say '회원 확인 중'
TMPJ="$(mktemp "${TMPDIR:-/tmp}/shortem.XXXXXX")" || die '임시 파일을 만들지 못했습니다'
trap 'rm -f "$TMPJ"' EXIT
curl -fsS -X POST -H "X-Shortem-Start: $TOKEN" -o "$TMPJ" "$BASE/api/claude/start/redeem" \
  || die '회원 확인이 안 됐습니다. 페이지에서 설치 명령을 새로 복사해 주세요'
KEY="$(jget "$TMPJ" key)"
[ -n "$KEY" ] || die '회원 확인 응답이 비었습니다'

say '설치 묶음 확인 중'
curl -fsS -H "Authorization: Bearer $KEY" -o "$TMPJ" "$BASE/api/claude/install?plat=$PLAT" || die '설치 묶음 정보를 받지 못했습니다'
[ "$(jget "$TMPJ" ready)" = true ] || die '맥 설치 묶음이 아직 준비되지 않았습니다. 잠시 뒤 다시 해 주세요'
VER="$(jget "$TMPJ" version)"; SHA="$(jget "$TMPJ" sha256)"; SIZE="$(jget "$TMPJ" size)"; URL="$(jget "$TMPJ" url)"
[[ "$VER" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$SHA" =~ ^[0-9a-f]{64}$ ]] || die '서버 응답이 올바르지 않습니다'
case "$URL" in http*) ;; *) URL="$BASE/${URL#/}" ;; esac

APP="${SHORTEM_INSTALL_DIR:-$HOME/Library/Application Support/Shortem}"   # 연결 프로그램 tools_paths.js 기본 자리와 같다
PARENT="$(dirname "$APP")"
mkdir -p "$PARENT"
NODE="$APP/tools/node/bin/node"

# ── 묶음 받기·풀기 ────────────────────────────────────────────────────────────
MARK="$APP/mac/bundle.sha256"          # 이 묶음을 다 풀었다는 표시 — 뒤 단계에서 멈춰도 다시 받지 않는다(맥 흉내 시험 11-05)
if [ -f "$MARK" ] && [ "$(cat "$MARK")" = "$SHA" ] && [ -f "$APP/server/index.js" ]; then
  say "이미 받은 묶음입니다($VER)"
else
  FREE_KB="$(df -k "$PARENT" | awk 'NR==2{print $4}')"
  NEED_KB=$(( SIZE * 4 / 1024 + 3 * 1024 * 1024 ))     # 묶음 ×4 + 실행 도구·부품 3GB
  [ "$FREE_KB" -ge "$NEED_KB" ] || die "디스크 여유가 부족합니다. $(( NEED_KB / 1024 / 1024 + 1 ))GB 이상 비워 주세요"
  ZIP="$PARENT/Shortem.download.part"
  if ! { [ -f "$ZIP" ] && [ "$(stat -f%z "$ZIP")" = "$SIZE" ] && [ "$(sha_of "$ZIP")" = "$SHA" ]; }; then
    say "내려받는 중(약 $(( SIZE / 1048576 ))MB, 끊겨도 이어 받습니다)"
    curl -# -fL --retry 5 --retry-delay 5 -C - -o "$ZIP" "$URL" || { rm -f "$ZIP"; die '내려받기 실패. 다시 시도해 주세요'; }
  fi
  say '받은 파일 확인 중'
  [ "$(sha_of "$ZIP")" = "$SHA" ] || { rm -f "$ZIP"; die '받은 파일 확인값이 다릅니다. 다시 시도해 주세요'; }
  say '푸는 중(몇 분 걸립니다)'
  FRESH="$APP.new"; rm -rf "$FRESH"; mkdir -p "$FRESH"
  ditto -x -k "$ZIP" "$FRESH" || die '풀기 실패'
  [ -f "$FRESH/server/index.js" ] && [ -f "$FRESH/mac/tools.lock.json" ] && [ -f "$FRESH/mac/requirements-engine-py312-mac.txt" ] \
    || die '풀린 묶음이 덜 찼습니다'
  if [ -d "$APP/tools" ]; then mv "$APP/tools" "$FRESH/tools.prev"; fi   # 이미 받은 실행 도구는 아래에서 그대로 다시 쓴다
  OLD=""
  if [ -d "$APP" ]; then OLD="$APP.old-$(date +%Y%m%d%H%M%S)"; mv "$APP" "$OLD"; fi
  mv "$FRESH" "$APP"
  printf '%s' "$SHA" > "$MARK"
  rm -f "$ZIP"
  [ -n "$OLD" ] && rm -rf "$OLD"
fi

# ── 실행 도구(node·크롬·파이썬·ffmpeg·ffprobe·yt-dlp) ─────────────────────────
LOCK="$APP/mac/tools.lock.json"
REQ="$APP/mac/requirements-engine-py312-mac.txt"
T="$APP/tools"
DL="$PARENT/Shortem.tools.download"; mkdir -p "$DL"
STAMP="$T/.mac-tools"                 # 이번 잠금 파일·부품 목록으로 다 깔았다는 표시 — 같으면 건너뛴다
WANT="$(cat "$LOCK" "$REQ" | shasum -a 256 | awk '{print $1}')-$LPLAT"
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$WANT" ] && [ -x "$NODE" ]; then
  say '실행 도구는 이미 깔려 있습니다'
else
  [ -d "$APP/tools.prev" ] && { rm -rf "$T"; mv "$APP/tools.prev" "$T"; }
  mkdir -p "$T"
  get() {   # get <이름> → 받은 파일 경로(확인값 대조까지)
    local n="$1" url sha md5 f
    url="$(jget "$LOCK" "$LPLAT.$n.url")"; [ -n "$url" ] || die "도구 목록에 $n 이 없습니다"
    sha="$(jget "$LOCK" "$LPLAT.$n.sha256")"; md5="$(jget "$LOCK" "$LPLAT.$n.md5_b64")"
    f="$DL/$LPLAT-$n-$(basename "$url")"
    got() { if [ -n "$sha" ]; then sha_of "$f"; else openssl md5 -binary "$f" | base64; fi; }
    ok() { [ "$(got)" = "${sha:-$md5}" ]; }
    if ! { [ -f "$f" ] && ok; }; then
      say "  $n 받는 중" >&2
      curl -fsSL --retry 5 --retry-delay 5 -o "$f" "$url" || die "$n 내려받기 실패"
      ok || { printf '[숏클]   %s 받은 값 %s · 기대 값 %s · 크기 %s\n' "$n" "$(got)" "${sha:-$md5}" "$(stat -f%z "$f")" >&2; rm -f "$f"; die "$n 확인값이 다릅니다"; }
    fi
    printf '%s' "$f"
  }
  say '실행 도구 받는 중'
  f="$(get node)" || exit 1
  rm -rf "$T/node" "$DL/x"; mkdir -p "$DL/x" "$T/node/bin"; tar -xzf "$f" -C "$DL/x" || die 'node 풀기 실패'
  src="$(find "$DL/x" -maxdepth 1 -mindepth 1 -type d | head -1)"
  cp "$src/bin/node" "$T/node/bin/node"; cp "$src/LICENSE" "$T/node/LICENSE" 2>/dev/null; chmod 755 "$T/node/bin/node"; rm -rf "$DL/x"

  f="$(get chrome-headless-shell)" || exit 1
  rm -rf "$T/chrome-headless-shell" "$DL/x"; mkdir -p "$DL/x"; ditto -x -k "$f" "$DL/x" || die '크롬 풀기 실패'
  ditto "$(find "$DL/x" -maxdepth 1 -mindepth 1 -type d | head -1)" "$T/chrome-headless-shell"; rm -rf "$DL/x"

  f="$(get python)" || exit 1
  rm -rf "$T/python" "$DL/x"; mkdir -p "$DL/x"; tar -xzf "$f" -C "$DL/x" || die '파이썬 풀기 실패'
  mv "$DL/x/python" "$T/python"; rm -rf "$DL/x"

  mkdir -p "$T/ffmpeg"
  for n in ffmpeg ffprobe; do
    f="$(get $n)" || exit 1
    rm -rf "$DL/x"; mkdir -p "$DL/x"; ditto -x -k "$f" "$DL/x" || die "$n 풀기 실패"
    b="$(find "$DL/x" -type f -name "$n" | head -1)"; [ -n "$b" ] || die "$n 파일이 묶음에 없습니다"
    cp "$b" "$T/ffmpeg/$n"; chmod 755 "$T/ffmpeg/$n"; rm -rf "$DL/x"
  done

  # 인터넷에서 받은 표시가 붙어 있으면 맥이 실행을 막는다 — curl 로 받으면 안 붙지만 혹시 몰라 지운다
  xattr -dr com.apple.quarantine "$T" 2>/dev/null

  PY="$T/python/bin/python3"
  say '영상 엔진 부품 설치 중(몇 분 걸립니다)'
  "$PY" -I -m pip install --no-cache-dir --disable-pip-version-check --no-warn-script-location --only-binary=:all: \
    --require-hashes -r "$REQ" >"$SHORTEM_HOME/pip.log" 2>&1 || { tail -20 "$SHORTEM_HOME/pip.log"; die '엔진 부품 설치 실패'; }
  mkdir -p "$T/yt-dlp"
  cat > "$T/yt-dlp/yt-dlp" <<'SH'
#!/bin/sh
here="$(cd "$(dirname "$0")" && pwd)"
exec "$here/../python/bin/python3" -I -m yt_dlp "$@"
SH
  chmod 755 "$T/yt-dlp/yt-dlp"

  say '실행 도구 확인 중'
  out_has ' ass ' "$T/ffmpeg/ffmpeg" -hide_banner -filters || die 'ffmpeg 에 자막 기능이 없습니다'
  "$T/chrome-headless-shell/chrome-headless-shell" --version >/dev/null 2>&1 || die '렌더러(크롬)가 실행되지 않습니다'
  "$PY" -I -c 'import PIL,numpy,cv2,faster_whisper,yt_dlp,requests,dotenv,onnxruntime,av;from google import genai' \
    || die '엔진 부품 확인 실패'
  "$NODE" "$APP/mac/write_manifest.js" --stage "$APP" --plat "$LPLAT" --version "$VER" --lock "$LOCK" >/dev/null || die '도구 목록 기록 실패'
  printf '%s' "$WANT" > "$STAMP"
fi
rm -rf "$DL" "$APP/tools.prev"
"$NODE" "$APP/postinstall.js" --home "$APP" --version "$VER" || die '설치 파일 확인 실패'

# ── 회원 키 저장 ──────────────────────────────────────────────────────────────
say '회원 키 저장 중'
SHORTEM_K="$KEY" "$NODE" --input-type=module -e "const m=await import(process.argv[1]);m.saveLicense(process.env.SHORTEM_K)" \
  "file://$APP/server/license.js" || die '회원 키 저장 실패'
unset KEY

export SHORTEM_INSTALL="$APP" SHORTEM_NODE="$NODE"
LOCALBIN="$HOME/.local/bin"
export PATH="$LOCALBIN:$PATH"
if [ -z "${SHORTEM_NO_PERSIST:-}" ]; then        # 다음에 여는 터미널에서도 찾게(zsh 기본 + bash)
  blk="# >>> shortcl >>>
export SHORTEM_INSTALL=\"$APP\"
export SHORTEM_NODE=\"$NODE\"
case \":\$PATH:\" in *\":$LOCALBIN:\"*) ;; *) export PATH=\"$LOCALBIN:\$PATH\" ;; esac
# <<< shortcl <<<"
  for rc in "$HOME/.zshenv" "$HOME/.bash_profile"; do
    old="$( [ -f "$rc" ] && cat "$rc" )"
    new="$(printf '%s\n' "$old" | sed '/^# >>> shortcl >>>$/,/^# <<< shortcl <<<$/d')"
    printf '%s\n%s\n' "$new" "$blk" | sed '/./,$!d' > "$rc.shortem.tmp" && mv "$rc.shortem.tmp" "$rc"
  done
fi

# ── Claude Code ───────────────────────────────────────────────────────────────
if ! command -v claude >/dev/null 2>&1; then
  say 'Claude Code 설치 중'
  bash -c "$(curl -fsSL https://claude.ai/install.sh)" || die 'Claude Code 설치 실패'
  hash -r
  command -v claude >/dev/null 2>&1 || die 'Claude Code 설치를 확인하지 못했습니다'
fi

say '숏클 연결 중'
claude plugin marketplace add "$APP/claude-plugin" >/dev/null 2>&1
claude plugin marketplace update shortem >/dev/null 2>&1
claude plugin install 'shortem@shortem' >/dev/null 2>&1
out_has shortem claude plugin list || die '숏클 플러그인 등록을 확인하지 못했습니다'

# ── 작업 폴더·회원 지침·첫 화면 설정 ─────────────────────────────────────────
WORK="$SHORTEM_HOME/work"
OLDWORK="$HOME/Desktop/숏템작업"
[ -d "$OLDWORK" ] && WORK="$OLDWORK"
mkdir -p "$WORK/.claude"
GUIDE="$APP/server/guide/MEMBER_GUIDE.md"
[ -f "$GUIDE" ] || die '회원 지침 파일이 없습니다. 같은 줄을 다시 붙여 넣어 주세요'
{ printf '<!-- 숏클 회원 지침 — 숏클이 자동으로 관리합니다. 고치면 다음 업데이트에 덮입니다. -->\n'; cat "$GUIDE"; } > "$WORK/CLAUDE.md"

CFG="${CLAUDE_CONFIG_DIR:+$CLAUDE_CONFIG_DIR/.claude.json}"; CFG="${CFG:-$HOME/.claude.json}"
"$NODE" -e '
const fs = require("fs");
const [cfg, work] = process.argv.slice(1);
let j = {};
if (fs.existsSync(cfg)) j = JSON.parse(fs.readFileSync(cfg, "utf8"));
if (!j.theme) j.theme = "dark";
j.hasCompletedOnboarding = true;
j.hasCompletedClaudeInChromeOnboarding = true;
if (j.claudeInChromeDefaultEnabled === undefined) j.claudeInChromeDefaultEnabled = false;
j.projects = j.projects || {};
j.projects[work] = Object.assign({}, j.projects[work], { hasTrustDialogAccepted: true });
const tmp = cfg + ".shortem.tmp";
fs.writeFileSync(tmp, JSON.stringify(j, null, 2));
fs.renameSync(tmp, cfg);' "$CFG" "$WORK" || say '첫 화면 설정은 건너뜁니다'
"$NODE" -e '
const fs = require("fs");
const f = process.argv[1];
let j = {};
try { j = JSON.parse(fs.readFileSync(f, "utf8")); } catch (e) {}
j.permissions = j.permissions || {};
const need = ["mcp__plugin_shortem_shortem", "Skill", "Read", "Edit", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch", "Agent"];
j.permissions.allow = [...new Set([...(j.permissions.allow || []), ...need])];
fs.writeFileSync(f, JSON.stringify(j, null, 2));' "$WORK/.claude/settings.json" || say '권한 설정은 건너뜁니다'

say '설치 완료'
[ -n "${SHORTEM_NO_LAUNCH:-}" ] && exit 0

# 온보딩을 건너뛰면 Claude 가 로그인 화면을 안 띄운다(윈도 11-01 실측) — 여기서 먼저 로그인시킨다
if ! out_has '"loggedIn":[[:space:]]*true' claude auth status; then
  say 'Claude 로그인 — 브라우저가 열리면 로그인하고 허용을 누르세요'
  claude auth login </dev/tty
  out_has '"loggedIn":[[:space:]]*true' claude auth status || die 'Claude 로그인이 끝나지 않았습니다. 같은 줄을 다시 붙여 넣고 엔터를 눌러 주세요'
fi
say '준비 점검을 시작합니다'
cd "$WORK" || die '작업 폴더로 가지 못했습니다'
exec claude '숏클 점검 준비해줘' </dev/tty >/dev/tty 2>&1
