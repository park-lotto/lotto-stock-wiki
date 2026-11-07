# 도구를 받아 설치한다. 여러 번 실행해도 된다.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($root -match '[^\x00-\x7F]' -or $root -match ' ') { Write-Host '영문 폴더(C:\shorcl_long)로 옮긴 뒤 다시 실행해 주세요.'; exit 1 }
$tools = Join-Path $root 'tools'; New-Item -ItemType Directory -Force $tools | Out-Null
$lock = (Get-Content (Join-Path $root 'tools.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json).'win-x64'

function Get-Tool($name, $spec) {
  $file = Join-Path $env:TEMP ("shorcl_" + $name + "_" + [IO.Path]::GetFileName(([uri]$spec.url).LocalPath))
  Write-Host "받는 중: $name"
  Invoke-WebRequest -Uri $spec.url -OutFile $file -UseBasicParsing
  if ($spec.sha256 -and (Get-FileHash $file -Algorithm SHA256).Hash.ToLower() -ne $spec.sha256) { Remove-Item $file; throw "$name 파일 확인값이 다릅니다" }
  return $file
}

$ff = Join-Path $tools 'ffmpeg'
if (-not (Test-Path (Join-Path $ff 'ffmpeg.exe'))) {
  $z = Get-Tool 'ffmpeg' $lock.ffmpeg
  $x = Join-Path $env:TEMP 'shorcl_ff'; if (Test-Path $x) { Remove-Item -Recurse -Force $x }
  Expand-Archive $z $x
  New-Item -ItemType Directory -Force $ff | Out-Null
  Get-ChildItem $x -Recurse -Include ffmpeg.exe,ffprobe.exe | Copy-Item -Destination $ff
  Remove-Item -Recurse -Force $x; Remove-Item $z
}
$py = Join-Path $tools 'python'
$pyexe = Join-Path $py 'python.exe'
if (-not (Test-Path $pyexe)) {
  $z = Get-Tool 'python' $lock.python
  $x = Join-Path $env:TEMP 'shorcl_py'; if (Test-Path $x) { Remove-Item -Recurse -Force $x }
  New-Item -ItemType Directory -Force $x | Out-Null
  & "$env:SystemRoot\System32\tar.exe" -xzf $z -C $x
  if ($LASTEXITCODE -ne 0) { throw '파이썬 풀기 실패' }
  Move-Item (Join-Path $x 'python') $py
  Remove-Item -Recurse -Force $x; Remove-Item $z
}
$mark = Join-Path $py '.pip_done'
if (-not (Test-Path $mark)) {
  Write-Host '실행 도구 설치 중'
  & $pyexe -m pip install --quiet --no-warn-script-location --disable-pip-version-check -r (Join-Path $root 'requirements.txt')
  if ($LASTEXITCODE -ne 0) { throw '실행 도구 설치 실패' }
  New-Item -ItemType File $mark | Out-Null
}
Write-Host '설치 끝'
