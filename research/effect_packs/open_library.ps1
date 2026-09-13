# 효과팩 라이브러리 열기 — 로컬 서버(포트 8765)를 띄우고 크롬으로 연다.
# file:// 대신 http 로 여는 이유: 크롬 확장·플레이라이트가 file:// 을 못 다뤄 검수가 불가능하고,
# 브라우저마다 file:// 미디어 처리가 달라 "재생 안 됨"이 재현되기 때문(2026-09-13).
param([string]$Page = "index.html")
$root = "C:\Users\CH\Desktop\effect_packs\library"
$port = 8765
$listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    $py = "C:\Users\CH\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    Start-Process -FilePath $py -ArgumentList "-m http.server $port --bind 127.0.0.1" -WorkingDirectory $root -WindowStyle Hidden
    Start-Sleep -Seconds 1
}
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
Start-Process -FilePath $chrome -ArgumentList "http://127.0.0.1:$port/$Page"
