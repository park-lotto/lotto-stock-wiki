# 꾸러미 준비: 도구를 받아 설치하고 키를 저장한다. 여러 번 실행해도 된다.
param([switch]$ToolsOnly)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($root -match '[^\x00-\x7F]') { Write-Host '폴더 경로에 한글이 있으면 영상 도구가 멈출 수 있어요. C:\shorcl 같은 영문 폴더로 옮긴 뒤 다시 실행해 주세요.'; exit 1 }
$tools = Join-Path $root 'tools'; New-Item -ItemType Directory -Force $tools | Out-Null
$lock = (Get-Content (Join-Path $root 'tools.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json).'win-x64'

function Get-Tool($name, $spec, $dest) {
  $file = Join-Path $env:TEMP ("shorcl_" + $name + "_" + [IO.Path]::GetFileName(([uri]$spec.url).LocalPath))
  Write-Host "받는 중: $name"
  Invoke-WebRequest -Uri $spec.url -OutFile $file -UseBasicParsing
  if ($spec.sha256) {
    $h = (Get-FileHash $file -Algorithm SHA256).Hash.ToLower()
    if ($h -ne $spec.sha256) { Remove-Item $file; throw "$name 파일 확인값이 다릅니다" }
  }
  return $file
}

$ff = Join-Path $tools 'ffmpeg'
if (-not (Test-Path (Join-Path $ff 'ffmpeg.exe'))) {
  $z = Get-Tool 'ffmpeg' $lock.ffmpeg $ff
  $x = Join-Path $env:TEMP 'shorcl_ff'; if (Test-Path $x) { Remove-Item -Recurse -Force $x }
  Expand-Archive $z $x
  New-Item -ItemType Directory -Force $ff | Out-Null
  Get-ChildItem $x -Recurse -Include ffmpeg.exe,ffprobe.exe | Copy-Item -Destination $ff
  Remove-Item -Recurse -Force $x; Remove-Item $z
}
$yd = Join-Path $tools 'ytdlp'
if (-not (Test-Path (Join-Path $yd 'yt-dlp.exe'))) {
  New-Item -ItemType Directory -Force $yd | Out-Null
  $z = Get-Tool 'yt-dlp' $lock.'yt-dlp' $yd
  Move-Item $z (Join-Path $yd 'yt-dlp.exe')
}
$py = Join-Path $tools 'python'
$pyexe = Join-Path $py 'python.exe'
if (-not (Test-Path $pyexe)) {
  $z = Get-Tool 'python' $lock.python $py
  $x = Join-Path $env:TEMP 'shorcl_py'; New-Item -ItemType Directory -Force $x | Out-Null
  & "$env:SystemRoot\System32\tar.exe" -xzf $z -C $x
  if ($LASTEXITCODE -ne 0) { throw '파이썬 풀기 실패' }
  Move-Item (Join-Path $x 'python') $py
  Remove-Item -Recurse -Force $x; Remove-Item $z
}
$mark = Join-Path $py '.pip_done'
if (-not (Test-Path $mark)) {
  Write-Host '실행 도구 설치 중 (몇 분 걸립니다)'
  & $pyexe -m pip install --quiet --no-warn-script-location --disable-pip-version-check -r (Join-Path $root 'requirements.txt')
  if ($LASTEXITCODE -ne 0) { throw '실행 도구 설치 실패' }
  & $pyexe -m pip install --quiet --no-warn-script-location --disable-pip-version-check playwright
  if ($LASTEXITCODE -ne 0) { throw '로그인 도구 설치 실패' }
  New-Item -ItemType File $mark | Out-Null
}

if ($ToolsOnly) { & $pyexe -X utf8 -c "import cv2, PIL, numpy, faster_whisper, yt_dlp, requests, playwright; print('패키지 확인')"; exit $LASTEXITCODE }

$keys = Join-Path $root 'data\keys'; New-Item -ItemType Directory -Force $keys | Out-Null
$ask = @(
  @('typecast', '타입캐스트 API 키 (목소리, 필수)'),
  @('vmake_ak', 'VMake AK (원본 자막 지우기, 필수)'),
  @('vmake_sk', 'VMake SK (원본 자막 지우기, 필수)'),
  @('coupang_access', '쿠팡 파트너스 Access Key (없으면 Enter)'),
  @('coupang_secret', '쿠팡 파트너스 Secret Key (없으면 Enter)'),
  @('speechmatics', 'Speechmatics 키 (없으면 Enter, 위스퍼로 진행)')
)
foreach ($k in $ask) {
  $p = Join-Path $keys $k[0]
  if (Test-Path $p) { continue }
  $s = Read-Host -AsSecureString $k[1]
  $v = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
  if ($v) { [IO.File]::WriteAllText($p, $v.Trim()) }
}

& $pyexe -X utf8 (Join-Path $root 'login.py')
& $pyexe -X utf8 (Join-Path $root 'check.py')
