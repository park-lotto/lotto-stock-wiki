$ErrorActionPreference = 'Stop'
$install = Join-Path $env:LOCALAPPDATA 'Programs/MakersLab-Blender'
$exe = Join-Path $install 'blender-4.5.9-windows-x64/blender.exe'
if (!(Test-Path -LiteralPath $exe)) { throw 'Install the documented Blender version first.' }
if (Get-NetTCPConnection -LocalPort 9876 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 9876 is already in use. Inspect the existing Blender instance; do not start a second server.'
}
$env:DISABLE_TELEMETRY = 'true'
$env:BLENDER_USER_CONFIG = Join-Path $install 'profile/config'
$env:BLENDER_USER_SCRIPTS = Join-Path $install 'profile/scripts'
$bootstrap = Join-Path $PSScriptRoot 'bootstrap.py'
$artifacts = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.artifacts'))
New-Item -ItemType Directory -Force $artifacts | Out-Null
$process = Start-Process -FilePath $exe -ArgumentList @('--factory-startup','--python',('"'+$bootstrap+'"')) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $artifacts 'blender-runtime.log') -RedirectStandardError (Join-Path $artifacts 'blender-runtime.err')
Write-Output ('Blender PID: ' + $process.Id + '. Verify using mcp_check.py; process start alone is not connection proof.')
