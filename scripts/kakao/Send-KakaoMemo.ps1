# Send-KakaoMemo.ps1
# 카카오톡 "나에게 보내기" — 텍스트 메시지 전송 (필요 시 토큰 자동 갱신).
# 사용:
#   .\scripts\kakao\Send-KakaoMemo.ps1 -Text "안녕"
#   .\scripts\kakao\Send-KakaoMemo.ps1 -Text "아침노트" -Link "https://example.com"
#   "여러줄`n메시지" | .\scripts\kakao\Send-KakaoMemo.ps1

[CmdletBinding()]
param(
    [Parameter(ValueFromPipeline=$true, Position=0)]
    [string]$Text,

    [string]$Link,
    [string]$ButtonTitle = '자세히 보기'
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# 파이프 입력 누적
if ($MyInvocation.ExpectingInput) {
    $Text = $input -join "`n"
}

if ([string]::IsNullOrWhiteSpace($Text)) {
    Write-Host "보낼 메시지가 비었습니다. -Text '내용' 또는 파이프로 전달하세요." -ForegroundColor Red
    exit 1
}

# .env 로드
$envFile = Join-Path $here '.env'
if (-not (Test-Path $envFile)) {
    Write-Host ".env 파일이 없습니다." -ForegroundColor Red; exit 1
}
$envMap = @{}
Get-Content $envFile -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*([^=\s]+)\s*=\s*(.+)\s*$') {
        $envMap[$matches[1]] = $matches[2].Trim()
    }
}
$restKey = $envMap['KAKAO_REST_API_KEY']
$clientSecret = $envMap['KAKAO_CLIENT_SECRET']

# 토큰 로드
$tokenFile = Join-Path $here '.tokens.json'
if (-not (Test-Path $tokenFile)) {
    Write-Host ".tokens.json 없음. 먼저 Get-KakaoToken.ps1 실행하세요." -ForegroundColor Red
    exit 1
}
$tokens = Get-Content $tokenFile -Raw -Encoding UTF8 | ConvertFrom-Json

# 만료 임박 시 갱신 (5분 여유)
$expiresAt = [datetime]::Parse($tokens.expires_at)
if ((Get-Date).AddMinutes(5) -ge $expiresAt) {
    Write-Host "access_token 만료 임박 → refresh 중..." -ForegroundColor Yellow
    $refreshBody = @{
        grant_type    = 'refresh_token'
        client_id     = $restKey
        refresh_token = $tokens.refresh_token
    }
    if (-not [string]::IsNullOrWhiteSpace($clientSecret)) {
        $refreshBody.client_secret = $clientSecret
    }
    try {
        $refreshed = Invoke-RestMethod -Method Post -Uri 'https://kauth.kakao.com/oauth/token' `
            -Body $refreshBody `
            -ContentType 'application/x-www-form-urlencoded;charset=utf-8'
    } catch {
        Write-Host "refresh 실패. Get-KakaoToken.ps1 재실행 필요: $_" -ForegroundColor Red
        exit 1
    }

    $tokens.access_token = $refreshed.access_token
    $tokens.expires_at   = (Get-Date).AddSeconds($refreshed.expires_in).ToString('o')
    if ($refreshed.refresh_token) {
        $tokens.refresh_token = $refreshed.refresh_token
        $tokens.refresh_token_expires_at = (Get-Date).AddSeconds($refreshed.refresh_token_expires_in).ToString('o')
    }
    $tokens | ConvertTo-Json | Out-File -FilePath $tokenFile -Encoding utf8
    Write-Host "refresh OK" -ForegroundColor Green
}

# 템플릿 구성 (text 템플릿)
$linkObj = if ($Link) {
    @{ web_url = $Link; mobile_web_url = $Link }
} else {
    @{ web_url = 'https://developers.kakao.com'; mobile_web_url = 'https://developers.kakao.com' }
}

$template = @{
    object_type = 'text'
    text        = $Text
    link        = $linkObj
}
if ($Link) {
    $template.button_title = $ButtonTitle
}

$templateJson = $template | ConvertTo-Json -Depth 5 -Compress

# 전송
$headers = @{ Authorization = "Bearer $($tokens.access_token)" }
$body = @{ template_object = $templateJson }

try {
    $result = Invoke-RestMethod -Method Post -Uri 'https://kapi.kakao.com/v2/api/talk/memo/default/send' `
        -Headers $headers -Body $body -ContentType 'application/x-www-form-urlencoded;charset=utf-8'
} catch {
    $msg = $_.ErrorDetails.Message
    Write-Host "전송 실패: $msg" -ForegroundColor Red
    exit 1
}

if ($result.result_code -eq 0) {
    Write-Host "전송 완료 → 카카오톡 '나와의 채팅' 확인" -ForegroundColor Green
} else {
    Write-Host "응답: $($result | ConvertTo-Json -Compress)" -ForegroundColor Yellow
}
