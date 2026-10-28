#!/usr/bin/env bash
# 숏템 맥 설치팩 빌드 — arm64 / x64 각각 한 pkg.
#   실행도구 내려받기(버전·해시 고정 = common/tools.lock.json) → libass 포함 정적 ffmpeg·ffprobe 직접 빌드 →
#   Shortem 폴더 구성 → inside-out codesign(Developer ID Application, hardened runtime, timestamp) →
#   pkgbuild/productbuild(Developer ID Installer) → notarytool submit --wait → stapler staple
#
# ★이 스크립트는 윈도 PC 에서 작성했고 `bash -n` 문법 검사까지만 했다. 맥에서 실측 필요(설계 §3-4·§13-2).
#
# 쓰는 법(맥, Xcode Command Line Tools 필요):
#   ARCH=arm64 installer/mac/build_mac.sh [--out DIR] [--client DIR] [--version 1.0.0] [--skip-sign]
#   ARCH=x64   installer/mac/build_mac.sh ...        (Apple Silicon 에서 x64 를 만들면 교차 빌드 — Rosetta 필요)
# 서명·공증 자리(없으면 미서명 pkg 를 만들고 그렇다고 출력):
#   SHORTEM_APP_ID="Developer ID Application: 회사명 (TEAMID)"
#   SHORTEM_INSTALLER_ID="Developer ID Installer: 회사명 (TEAMID)"
#   SHORTEM_NOTARY_PROFILE=<xcrun notarytool store-credentials 로 만든 키체인 프로필 이름>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"            # installer/
LOCK="$ROOT/common/tools.lock.json"
ARCH="${ARCH:-$(uname -m | sed 's/x86_64/x64/')}"
OUT="$ROOT/build"
CLIENT="$(cd "$ROOT/.." && pwd)/shortem_client"
VERSION=""
SKIP_SIGN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --client) CLIENT="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --skip-sign) SKIP_SIGN=1; shift ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done

log() { printf '[build_mac %s] %s\n' "$ARCH" "$*" >&2; }   # stderr — $(fetch …) 결과에 섞이지 않게
die() { printf '[build_mac %s] 중단: %s\n' "$ARCH" "$*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "맥(Darwin)에서만 돈다. 지금: $(uname -s)"
case "$ARCH" in arm64) CARCH=arm64; HOSTTRIPLE=aarch64-apple-darwin; PIPPLAT=macosx_11_0_arm64 ;;
                x64)   CARCH=x86_64; HOSTTRIPLE=x86_64-apple-darwin; PIPPLAT=macosx_10_13_x86_64 ;;
                *) die "ARCH 는 arm64 또는 x64" ;; esac
PLAT="darwin-$ARCH"
for t in curl shasum plutil ditto codesign pkgbuild productbuild xcrun clang make git file; do
  command -v "$t" >/dev/null || die "필요한 도구 없음: $t (Xcode Command Line Tools 설치: xcode-select --install)"
done

# lock 읽기 — plutil 은 JSON 도 읽는다(키 경로는 점으로)
lk() { plutil -extract "$1" raw -o - "$LOCK" 2>/dev/null || true; }
[ -n "$VERSION" ] || VERSION="$(lk installer_version)"
MACOS_MIN="$(lk mac_ffmpeg_build.macos_min)"

DL="$OUT/downloads"; EX="$OUT/extract-$ARCH"; SRC="$OUT/src-$ARCH"; PREFIX="$OUT/prefix-$ARCH"
STAGE="$OUT/$PLAT/Shortem"; DIST="$OUT/dist"
mkdir -p "$DL" "$EX" "$SRC" "$PREFIX" "$DIST"
rm -rf "$STAGE"; mkdir -p "$STAGE/tools"

# ── 내려받기 + 검증(sha256 또는 GCS md5) ─────────────────────────────────────
fetch() {  # fetch <lock 키 경로> → 받은 파일 경로 출력
  local key="$1" url sha md5 f
  url="$(lk "$key.url")"; sha="$(lk "$key.sha256")"; md5="$(lk "$key.md5_b64")"
  [ -n "$url" ] || die "lock 에 $key.url 없음"
  f="$DL/$(basename "$url" | sed 's/%2B/+/g')"
  if [ ! -f "$f" ]; then
    log "내려받기 $url"
    curl -fL --retry 3 -o "$f.part" "$url" && mv "$f.part" "$f"
  fi
  if [ -n "$sha" ]; then
    [ "$(shasum -a 256 "$f" | cut -d' ' -f1)" = "$sha" ] || { rm -f "$f"; die "$key sha256 불일치"; }
  elif [ -n "$md5" ]; then
    [ "$(openssl dgst -md5 -binary "$f" | base64)" = "$md5" ] || { rm -f "$f"; die "$key md5 불일치"; }
  else
    die "$key 검증값 없음"
  fi
  echo "$f"
}
fresh() { rm -rf "$1"; mkdir -p "$1"; }

# ── 1) node ──────────────────────────────────────────────────────────────────
f="$(fetch "$PLAT.node")"; fresh "$EX/node"; tar -xzf "$f" -C "$EX/node"
NODE_SRC="$(find "$EX/node" -maxdepth 1 -mindepth 1 -type d | head -1)"
mkdir -p "$STAGE/tools/node/bin"
cp "$NODE_SRC/bin/node" "$STAGE/tools/node/bin/node"; cp "$NODE_SRC/LICENSE" "$STAGE/tools/node/LICENSE"
BUILD_NODE="$NODE_SRC/bin/node"           # 빌드 중 npm·manifest 용(설치팩엔 bin/node 만)
export PATH="$NODE_SRC/bin:$PATH"

# ── 2) chrome-headless-shell ────────────────────────────────────────────────
f="$(fetch "$PLAT.chrome-headless-shell")"; fresh "$EX/chrome"; ditto -x -k "$f" "$EX/chrome"
ditto "$(find "$EX/chrome" -maxdepth 1 -mindepth 1 -type d | head -1)" "$STAGE/tools/chrome-headless-shell"

# ── 3) python(standalone) + Pillow·numpy + yt-dlp(패키지) ────────────────────
f="$(fetch "$PLAT.python")"; fresh "$EX/python"; tar -xzf "$f" -C "$EX/python"
ditto "$EX/python/python" "$STAGE/tools/python"
PY="$STAGE/tools/python/bin/python3"
SITE="$("$PY" -I -c 'import sysconfig;print(sysconfig.get_paths()["purelib"])')"
log "python 패키지 설치(해시 고정, 플랫폼 $PIPPLAT)"
for req in "$ROOT/common/requirements-py312.txt" "$ROOT/common/requirements-py312-mac-extra.txt"; do
  "$PY" -I -m pip install --no-cache-dir --disable-pip-version-check --no-compile --only-binary=:all: \
    --platform "$PIPPLAT" --implementation cp --python-version 3.12 --abi cp312 --abi none \
    --target "$SITE" --upgrade --require-hashes -r "$req"
done
# 고객 PC 에 필요 없는 것(시험 묶음·GUI·pip·캐시)
find "$STAGE/tools/python" -type d \( -name __pycache__ -o -name tests -o -name test -o -name idlelib \
  -o -name tkinter -o -name turtledemo -o -name ensurepip \) -prune -exec rm -rf {} +
rm -rf "$SITE"/pip "$SITE"/pip-*.dist-info
# yt-dlp 실행기: 동봉 파이썬으로 yt_dlp 모듈을 부르는 얇은 스크립트(서버 tools_paths.js 가 이 경로를 sha 로 대조)
mkdir -p "$STAGE/tools/yt-dlp"
cat > "$STAGE/tools/yt-dlp/yt-dlp" <<'SH'
#!/bin/sh
here="$(cd "$(dirname "$0")" && pwd)"
exec "$here/../python/bin/python3" -I -m yt_dlp "$@"
SH
chmod 755 "$STAGE/tools/yt-dlp/yt-dlp"

# ── 4) ffmpeg·ffprobe 정적 빌드(libass·freetype·fribidi·harfbuzz·x264) ─────────
build_ffmpeg() {
  local ff_ver; ff_ver="$(lk mac_ffmpeg_build.ffmpeg.version)"
  if [ -x "$PREFIX/bin/ffmpeg" ] && [ -f "$PREFIX/.built-$ff_ver" ]; then log "ffmpeg 빌드본 재사용"; return; fi
  local J; J="$(sysctl -n hw.ncpu)"
  export CC="clang -arch $CARCH" CXX="clang++ -arch $CARCH"
  export CFLAGS="-arch $CARCH -mmacosx-version-min=$MACOS_MIN -O2" CXXFLAGS="-arch $CARCH -mmacosx-version-min=$MACOS_MIN -O2"
  export LDFLAGS="-arch $CARCH -mmacosx-version-min=$MACOS_MIN" MACOSX_DEPLOYMENT_TARGET="$MACOS_MIN"
  export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig" PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
  export PATH="$PREFIX/bin:$PATH"
  unpack() { local f d; f="$(fetch "mac_ffmpeg_build.$1")"; d="$SRC/$1"; fresh "$d"; tar -xf "$f" -C "$d" --strip-components 1; echo "$d"; }

  # 빌드 도구(호스트용) — pkgconf · nasm(x64 만) · meson/ninja(동봉 파이썬과 별개의 빌드 전용 venv)
  local d
  d="$(unpack pkgconf)"; (cd "$d" && env -u CC -u CFLAGS -u LDFLAGS ./configure --prefix="$PREFIX" --with-pkg-config-dir="$PREFIX/lib/pkgconfig" >/dev/null && make -j"$J" >/dev/null && make install >/dev/null)
  ln -sf pkgconf "$PREFIX/bin/pkg-config"
  if [ "$ARCH" = x64 ]; then
    d="$(unpack nasm)"; (cd "$d" && env -u CC -u CFLAGS -u LDFLAGS ./configure --prefix="$PREFIX" >/dev/null && make -j"$J" >/dev/null && make install >/dev/null)
  fi
  local BVENV="$OUT/buildvenv-$(uname -m)"
  if [ ! -x "$BVENV/bin/meson" ]; then
    "$EX/python/python/bin/python3" -m venv "$BVENV"
    "$BVENV/bin/pip" install --disable-pip-version-check --require-hashes -r "$ROOT/common/requirements-build-mac.txt"
  fi
  export PATH="$BVENV/bin:$PATH"
  local CROSS=()
  if [ "$CARCH" != "$(uname -m)" ]; then
    cat > "$OUT/meson-cross-$ARCH.ini" <<EOF
[binaries]
c = ['clang', '-arch', '$CARCH']
cpp = ['clang++', '-arch', '$CARCH']
pkg-config = '$PREFIX/bin/pkg-config'
[host_machine]
system = 'darwin'
cpu_family = '$( [ "$CARCH" = x86_64 ] && echo x86_64 || echo aarch64 )'
cpu = '$CARCH'
endian = 'little'
EOF
    CROSS=(--cross-file "$OUT/meson-cross-$ARCH.ini")
  fi
  local AC=(--prefix="$PREFIX" --host="$HOSTTRIPLE" --enable-static --disable-shared)

  log "freetype"; d="$(unpack freetype)"
  (cd "$d" && ./configure "${AC[@]}" --without-png --without-harfbuzz --without-brotli --without-bzip2 --with-zlib=yes >/dev/null && make -j"$J" >/dev/null && make install >/dev/null)
  log "fribidi"; d="$(unpack fribidi)"
  (cd "$d" && meson setup build "${CROSS[@]}" --prefix="$PREFIX" --default-library=static --buildtype=release -Ddocs=false -Dtests=false -Dbin=false >/dev/null && ninja -C build install >/dev/null)
  log "harfbuzz"; d="$(unpack harfbuzz)"
  (cd "$d" && meson setup build "${CROSS[@]}" --prefix="$PREFIX" --default-library=static --buildtype=release \
      -Dfreetype=enabled -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dicu=disabled -Dchafa=disabled \
      -Dcoretext=disabled -Dtests=disabled -Ddocs=disabled -Dutilities=disabled -Dintrospection=disabled >/dev/null && ninja -C build install >/dev/null)
  log "libass"; d="$(unpack libass)"
  (cd "$d" && ./configure "${AC[@]}" --disable-fontconfig --enable-coretext --disable-require-system-font-provider --disable-libunibreak >/dev/null && make -j"$J" >/dev/null && make install >/dev/null)
  log "x264"; local xc; xc="$(lk mac_ffmpeg_build.x264.commit)"
  rm -rf "$SRC/x264"; git clone -q "$(lk mac_ffmpeg_build.x264.git)" "$SRC/x264"; git -C "$SRC/x264" checkout -q "$xc"
  [ "$(git -C "$SRC/x264" rev-parse HEAD)" = "$xc" ] || die "x264 커밋 불일치"
  (cd "$SRC/x264" && ./configure --prefix="$PREFIX" --host="$HOSTTRIPLE" --enable-static --disable-cli --enable-pic \
      --extra-cflags="$CFLAGS" --extra-ldflags="$LDFLAGS" >/dev/null && make -j"$J" >/dev/null && make install >/dev/null)

  log "ffmpeg $ff_ver configure(옵션 고정)"; d="$(unpack ffmpeg)"
  local FFX=()
  [ "$CARCH" != "$(uname -m)" ] && FFX=(--enable-cross-compile --arch="$CARCH" --target-os=darwin)
  (cd "$d" && ./configure \
      --prefix="$PREFIX" "${FFX[@]}" --cc="clang -arch $CARCH" --cxx="clang++ -arch $CARCH" \
      --pkg-config="$PREFIX/bin/pkg-config" --pkg-config-flags=--static \
      --extra-cflags="-I$PREFIX/include -mmacosx-version-min=$MACOS_MIN" \
      --extra-ldflags="-L$PREFIX/lib -mmacosx-version-min=$MACOS_MIN" \
      --extra-libs="-lc++ -framework CoreText -framework CoreFoundation -framework CoreGraphics" \
      --enable-gpl --enable-version3 --enable-static --disable-shared --disable-debug --disable-doc \
      --disable-ffplay --disable-sdl2 --disable-xlib --disable-libxcb --disable-indev=avfoundation \
      --enable-pthreads --enable-videotoolbox --enable-audiotoolbox \
      --enable-libx264 --enable-libass --enable-libfreetype --enable-libfribidi --enable-libharfbuzz \
      >"$OUT/ffmpeg-configure-$ARCH.log" && make -j"$J" >/dev/null && make install >/dev/null)
  touch "$PREFIX/.built-$ff_ver"
}
build_ffmpeg
mkdir -p "$STAGE/tools/ffmpeg"
cp "$PREFIX/bin/ffmpeg" "$PREFIX/bin/ffprobe" "$STAGE/tools/ffmpeg/"
# 정적 확인: 시스템(/usr/lib·/System) 밖 동적 라이브러리가 붙어 있으면 실패
for b in ffmpeg ffprobe; do
  bad="$(otool -L "$STAGE/tools/ffmpeg/$b" | tail -n +2 | awk '{print $1}' | grep -vE '^(/usr/lib/|/System/Library/)' || true)"
  [ -z "$bad" ] || die "$b 가 외부 dylib 에 묶여 있음: $bad"
done

# ── 5) 실측(이 맥에서 돌릴 수 있는 아키텍처일 때) ───────────────────────────
if [ "$CARCH" = "$(uname -m)" ] || { [ "$CARCH" = x86_64 ] && arch -x86_64 /usr/bin/true 2>/dev/null; }; then
  log "node $("$STAGE/tools/node/bin/node" -v)"
  log "chrome $("$STAGE/tools/chrome-headless-shell/chrome-headless-shell" --version)"
  log "$("$STAGE/tools/ffmpeg/ffmpeg" -hide_banner -version | head -1)"
  "$STAGE/tools/ffmpeg/ffmpeg" -hide_banner -filters | grep -q ' ass ' || die "ffmpeg 에 ass 필터 없음"
  log "ass 필터 있음"
  "$PY" -I -c 'import PIL,numpy,yt_dlp;print("python ok",PIL.__version__,numpy.__version__)'
  log "yt-dlp $("$STAGE/tools/yt-dlp/yt-dlp" --version)"
fi

# ── 6) 서버·연결 파일·안내 ───────────────────────────────────────────────────
if [ -f "$CLIENT/server/index.js" ]; then
  rsync -a --exclude node_modules --exclude test --exclude tests --exclude '*.log' --exclude '.env*' "$CLIENT/server/" "$STAGE/server/"
  if [ -f "$STAGE/server/package-lock.json" ]; then
    (cd "$STAGE/server" && PUPPETEER_SKIP_DOWNLOAD=1 npm ci --omit=dev --ignore-scripts --no-audit --no-fund >/dev/null)
  elif [ -f "$STAGE/server/package.json" ]; then
    (cd "$STAGE/server" && PUPPETEER_SKIP_DOWNLOAD=1 npm install --omit=dev --ignore-scripts --no-audit --no-fund >/dev/null)
  fi
  find "$STAGE/server/node_modules" -type f \( -name '*.map' -o -name '*.d.ts' -o -name '*.d.mts' -o -name '*.d.cts' \) -delete 2>/dev/null || true
  SERVER_KIND=real
else
  log "주의: $CLIENT/server/index.js 없음 → 자리표시 서버"
  mkdir -p "$STAGE/server"; cp "$ROOT/common/placeholder_server/index.js" "$STAGE/server/index.js"
  SERVER_KIND=placeholder
fi
cp "$ROOT/common/postinstall.js" "$STAGE/postinstall.js"
cp "$ROOT/시작.md" "$STAGE/시작.template.md"
cp "$ROOT/guide/설치안내.html" "$STAGE/설치안내.html"
cp "$HERE/uninstall.command" "$STAGE/숏템 제거.command"; chmod 755 "$STAGE/숏템 제거.command"
rm -rf "$STAGE/claude-plugin"; ditto "$ROOT/plugin" "$STAGE/claude-plugin"
cp "$ROOT/mcpb/launcher.js" "$STAGE/claude-plugin/shortem/launcher.js"
MS="$OUT/mcpb_stage"; fresh "$MS"; cp "$ROOT/mcpb/manifest.json" "$ROOT/mcpb/launcher.js" "$ROOT/mcpb/icon.png" "$MS/"
MCPB_CLI="$(lk mcpb_cli)"
npx -y "$MCPB_CLI" validate "$MS/manifest.json"
rm -f "$DIST/shortem.mcpb"; npx -y "$MCPB_CLI" pack "$MS" "$DIST/shortem.mcpb"
cp "$DIST/shortem.mcpb" "$STAGE/shortem.mcpb"

# ── 7) tools.manifest.json(윈도와 같은 주인: common/write_manifest.js) ─────────
"$BUILD_NODE" "$ROOT/common/write_manifest.js" --stage "$STAGE" --plat "$PLAT" --version "$VERSION" --lock "$LOCK"

# ── 8) inside-out 서명(깊은 파일부터) ─────────────────────────────────────────
APP_ID="${SHORTEM_APP_ID:-}"; INST_ID="${SHORTEM_INSTALLER_ID:-}"; NOTARY="${SHORTEM_NOTARY_PROFILE:-}"
SIGNED=0
if [ "$SKIP_SIGN" = 0 ] && [ -n "$APP_ID" ]; then
  log "codesign(inside-out, hardened runtime, timestamp) — $APP_ID"
  ent_for() {
    case "$1" in
      */tools/chrome-headless-shell/*) echo "$HERE/entitlements-chromium.plist" ;;
      */tools/node/*)                  echo "$HERE/entitlements-node.plist" ;;
      */tools/python/*)                echo "$HERE/entitlements-python.plist" ;;
      *)                               echo "$HERE/entitlements-default.plist" ;;
    esac
  }
  # Mach-O 전부(실행 파일·dylib·so·node 확장) — 경로 깊이 내림차순
  find "$STAGE" -type f -print0 | while IFS= read -r -d '' p; do
    if file -b "$p" | grep -q 'Mach-O'; then printf '%d\t%s\n' "$(echo "$p" | tr -cd '/' | wc -c)" "$p"; fi
  done | sort -rn | cut -f2- > "$OUT/macho-$ARCH.txt"
  log "Mach-O $(wc -l < "$OUT/macho-$ARCH.txt" | tr -d ' ')개 서명"
  while IFS= read -r p; do
    codesign --force --timestamp --options=runtime --entitlements "$(ent_for "$p")" --sign "$APP_ID" "$p"
  done < "$OUT/macho-$ARCH.txt"
  # 서명이 sha 를 바꾸므로 manifest 를 다시 쓴다(설치 뒤 대조는 서명된 파일 기준)
  "$BUILD_NODE" "$ROOT/common/write_manifest.js" --stage "$STAGE" --plat "$PLAT" --version "$VERSION" --lock "$LOCK"
  while IFS= read -r p; do codesign --verify --strict "$p" || die "서명 검증 실패: $p"; done < "$OUT/macho-$ARCH.txt"
  SIGNED=1
else
  log "codesign: 미서명 — SHORTEM_APP_ID 없음(공증 불가, Gatekeeper 가 막는다)"
fi

# ── 9) pkg(사용자 홈 도메인: ~/Library/Application Support/Shortem) ────────────
PKGID="com.shortem.installer.$ARCH"
COMP="$OUT/shortem-component-$ARCH.pkg"
SCRIPTS="$OUT/pkgscripts-$ARCH"; fresh "$SCRIPTS"; cp "$HERE/scripts/postinstall" "$SCRIPTS/postinstall"; chmod 755 "$SCRIPTS/postinstall"
pkgbuild --root "$STAGE" --identifier "$PKGID" --version "$VERSION" \
  --install-location "/Library/Application Support/Shortem" --scripts "$SCRIPTS" "$COMP"
RES="$OUT/pkgres-$ARCH"; fresh "$RES"
cat > "$RES/welcome.html" <<'EOF'
<html><head><meta charset="utf-8"></head><body style="font-family:-apple-system,sans-serif">
<h2>숏템 설치</h2><p>숏템이 영상을 만드는 데 쓰는 실행 도구(렌더러·ffmpeg·파이썬)와 숏템 로컬 서버를 <b>내 사용자 폴더</b>(~/Library/Application Support/Shortem)에 설치합니다. 관리자 권한이나 인터넷 내려받기는 필요 없습니다.</p></body></html>
EOF
cat > "$RES/conclusion.html" <<'EOF'
<html><head><meta charset="utf-8"></head><body style="font-family:-apple-system,sans-serif">
<h2>설치가 끝났습니다</h2><p>Claude Desktop: 바탕화면 '숏템작업' 옆 설치 폴더의 <b>shortem.mcpb</b>를 두 번 누르고 라이선스 키를 붙여 넣으세요.</p>
<p>Claude Code: 바탕화면 '숏템작업' 폴더의 <b>시작.md</b>를 Claude Code 입력창에 끌어다 놓고 엔터.</p></body></html>
EOF
HOSTARCH="$( [ "$ARCH" = arm64 ] && echo arm64 || echo x86_64 )"
cat > "$OUT/distribution-$ARCH.xml" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
  <title>숏템</title>
  <welcome file="welcome.html" mime-type="text/html"/>
  <conclusion file="conclusion.html" mime-type="text/html"/>
  <options customize="never" require-scripts="false" hostArchitectures="$HOSTARCH"/>
  <domains enable_anywhere="false" enable_currentUserHome="true" enable_localSystem="false"/>
  <volume-check><allowed-os-versions><os-version min="$MACOS_MIN"/></allowed-os-versions></volume-check>
  <choices-outline><line choice="default"><line choice="$PKGID"/></line></choices-outline>
  <choice id="default"/>
  <choice id="$PKGID" visible="false"><pkg-ref id="$PKGID"/></choice>
  <pkg-ref id="$PKGID" version="$VERSION" onConclusion="none">$(basename "$COMP")</pkg-ref>
</installer-gui-script>
EOF
PKG="$DIST/shortem-setup-mac-$ARCH-$VERSION.pkg"; rm -f "$PKG"
if [ "$SIGNED" = 1 ] && [ -n "$INST_ID" ]; then
  productbuild --distribution "$OUT/distribution-$ARCH.xml" --resources "$RES" --package-path "$OUT" --sign "$INST_ID" --timestamp "$PKG"
else
  productbuild --distribution "$OUT/distribution-$ARCH.xml" --resources "$RES" --package-path "$OUT" "$PKG"
  log "pkg: 미서명(SHORTEM_INSTALLER_ID 없음)"
fi

# ── 10) 공증·스테이플 ─────────────────────────────────────────────────────────
if [ "$SIGNED" = 1 ] && [ -n "$INST_ID" ] && [ -n "$NOTARY" ]; then
  log "notarytool submit --wait"
  xcrun notarytool submit "$PKG" --keychain-profile "$NOTARY" --wait | tee "$OUT/notary-$ARCH.log"
  grep -q 'status: Accepted' "$OUT/notary-$ARCH.log" || die "공증 거절 — xcrun notarytool log <id> --keychain-profile $NOTARY 로 사유 확인"
  xcrun stapler staple "$PKG"
  xcrun stapler validate "$PKG"
  spctl -a -vvv -t install "$PKG" || die "Gatekeeper 평가 실패"
  pkgutil --check-signature "$PKG"
else
  log "공증: 안 함(서명 신원·SHORTEM_NOTARY_PROFILE 필요)"
fi

shasum -a 256 "$PKG" "$DIST/shortem.mcpb" | sed "s#$DIST/##" > "$DIST/SHA256SUMS-mac-$ARCH.txt"
log "끝: $PKG ($(du -m "$PKG" | cut -f1)MB) 서버=$SERVER_KIND 서명=$SIGNED"
