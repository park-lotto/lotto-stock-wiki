# 릴리리아 자막 프리셋 페이지 열기 — 로컬 http 서버 + 크롬.
$root = $PSScriptRoot
$port = 8791
$listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    $py = "C:\Users\CH\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    Start-Process -FilePath $py -ArgumentList "-m http.server $port --bind 127.0.0.1" -WorkingDirectory $root -WindowStyle Hidden
    Start-Sleep -Seconds 1
}
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "http://127.0.0.1:$port/index.html"
