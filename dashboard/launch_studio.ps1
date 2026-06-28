# 딸깍 스튜디오 런처
# 서버(8090)가 안 떠 있으면 최소화 상태로 자동 기동한 뒤, /studio 를 브라우저로 연다.
$ErrorActionPreference = "SilentlyContinue"

$proj   = "C:\Users\TheRose\Desktop\로또의 주식"
$python = "C:\Users\TheRose\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$url    = "http://localhost:8090/studio"

Set-Location $proj

# 이미 8090이 LISTENING이면 서버 재기동 생략
$running = Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue
if (-not $running) {
    # 최소화된 독립 콘솔로 서버 기동 (더블클릭 시 런처가 끝나도 살아남음)
    Start-Process -FilePath $python -ArgumentList "dashboard\server.py" -WorkingDirectory $proj -WindowStyle Minimized
    # 서버 기동 대기 (최대 ~10초)
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        if (Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue) { break }
    }
}

Start-Process $url
