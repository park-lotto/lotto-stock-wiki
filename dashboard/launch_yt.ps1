$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$url = "http://127.0.0.1:8090/yt"
$python = "C:\Users\TheRose\AppData\Local\Python\pythoncore-3.14-64\python.exe"

$running = Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue
if (-not $running) {
    Start-Process `
        -FilePath $python `
        -ArgumentList "dashboard\server.py" `
        -WorkingDirectory $repo `
        -WindowStyle Hidden

    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            # 서버 부팅 중에는 재시도한다.
        }
    }

    if (-not $ready) {
        throw "영상 제작소 서버가 15초 안에 시작되지 않았습니다."
    }
}

Start-Process $url
