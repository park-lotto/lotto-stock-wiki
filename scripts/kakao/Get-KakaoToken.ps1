# Get-KakaoToken.ps1
# 카카오 OAuth 토큰 1회 발급 스크립트.
# 실행: .\scripts\kakao\Get-KakaoToken.ps1
# 결과: scripts\kakao\.tokens.json 에 access_token / refresh_token 저장

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# .env 로드
$envFile = Join-Path $here '.env'
if (-not (Test-Path $envFile)) {
    Write-Host ".env 파일이 없습니다. .env.example 을 복사해서 .env 로 만들고 키를 채우세요." -ForegroundColor Red
    exit 1
}

$envMap = @{}
Get-Content $envFile -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*([^=\s]+)\s*=\s*(.+)\s*$') {
        $envMap[$matches[1]] = $matches[2].Trim()
    }
}

$restKey = $envMap['KAKAO_REST_API_KEY']
$redirect = $envMap['KAKAO_REDIRECT_URI']
$clientSecret = $envMap['KAKAO_CLIENT_SECRET']

if ([string]::IsNullOrWhiteSpace($restKey) -or $restKey -like '*여기에*') {
    Write-Host ".env 의 KAKAO_REST_API_KEY 가 비어있습니다." -ForegroundColor Red
    exit 1
}

# 1) 인가코드 URL 생성 + 브라우저 오픈
$authUrl = "https://kauth.kakao.com/oauth/authorize?client_id=$restKey&redirect_uri=$([uri]::EscapeDataString($redirect))&response_type=code&scope=talk_message"
Write-Host ""
Write-Host "[1/3] 브라우저가 열립니다. 카카오 로그인 후 동의해주세요." -ForegroundColor Cyan
Write-Host "      Redirect URI: $redirect"
Start-Process $authUrl

# 2) HttpListener 로 콜백 대기
$port = ([uri]$redirect).Port
$prefix = "http://localhost:$port/"
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add($prefix)

try {
    $listener.Start()
} catch {
    Write-Host "포트 $port 점유 중. 다른 프로세스 종료 후 재시도하세요." -ForegroundColor Red
    exit 1
}

Write-Host "[2/3] 로컬 콜백 대기중... ($prefix)" -ForegroundColor Cyan

$ctx = $listener.GetContext()
$req = $ctx.Request
$code = $req.QueryString['code']
$err  = $req.QueryString['error']

$resp = $ctx.Response
$html = if ($code) {
    "<html><body style='font-family:sans-serif;text-align:center;padding:60px'><h2>인증 완료. 창을 닫아주세요.</h2></body></html>"
} else {
    "<html><body style='font-family:sans-serif;text-align:center;padding:60px'><h2>인증 실패: $err</h2></body></html>"
}
$buf = [System.Text.Encoding]::UTF8.GetBytes($html)
$resp.ContentType = 'text/html; charset=utf-8'
$resp.OutputStream.Write($buf, 0, $buf.Length)
$resp.Close()
$listener.Stop()

if (-not $code) {
    Write-Host "인가코드 미수신: $err" -ForegroundColor Red
    exit 1
}
Write-Host "      인가코드 수신 OK" -ForegroundColor Green

# 3) 토큰 교환
Write-Host "[3/3] 토큰 교환중..." -ForegroundColor Cyan
$body = @{
    grant_type    = 'authorization_code'
    client_id     = $restKey
    redirect_uri  = $redirect
    code          = $code
}
if (-not [string]::IsNullOrWhiteSpace($clientSecret)) {
    $body.client_secret = $clientSecret
}

Write-Host "      body keys: $($body.Keys -join ', ')" -ForegroundColor DarkGray
try {
    $token = Invoke-RestMethod -Method Post -Uri 'https://kauth.kakao.com/oauth/token' -Body $body -ContentType 'application/x-www-form-urlencoded;charset=utf-8'
} catch {
    $errBody = ''
    try {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $errBody = $reader.ReadToEnd()
    } catch {}
    Write-Host "토큰 교환 실패: $_" -ForegroundColor Red
    Write-Host "Kakao 응답: $errBody" -ForegroundColor Yellow
    exit 1
}

# 저장
$tokenFile = Join-Path $here '.tokens.json'
$saved = [pscustomobject]@{
    access_token              = $token.access_token
    refresh_token             = $token.refresh_token
    expires_at                = (Get-Date).AddSeconds($token.expires_in).ToString('o')
    refresh_token_expires_at  = (Get-Date).AddSeconds($token.refresh_token_expires_in).ToString('o')
    scope                     = $token.scope
}
$saved | ConvertTo-Json | Out-File -FilePath $tokenFile -Encoding utf8

Write-Host ""
Write-Host "토큰 저장 완료: $tokenFile" -ForegroundColor Green
Write-Host "  scope = $($token.scope)"
Write-Host "  access_token 만료까지: $([math]::Round($token.expires_in / 3600, 1))시간"
Write-Host "  refresh_token 만료까지: $([math]::Round($token.refresh_token_expires_in / 86400, 1))일"
Write-Host ""
Write-Host "이제 Send-KakaoMemo.ps1 으로 메시지를 보낼 수 있습니다." -ForegroundColor Cyan
