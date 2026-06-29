$ErrorActionPreference = "SilentlyContinue"
$proj   = "C:\Users\TheRose\Desktop\로또의 주식"
$python = "C:\Users\TheRose\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$url    = "http://localhost:8090/market"

Set-Location $proj

$running = Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue
if (-not $running) {
    Start-Process -FilePath $python -ArgumentList "dashboard\server.py" -WorkingDirectory $proj -WindowStyle Minimized
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        if (Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue) { break }
    }
}

Start-Process $url
