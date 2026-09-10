[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$HtmlPath,
    [ValidateRange(1024, 65535)][int]$Port = 8899,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$resultFile = Get-Item -LiteralPath $HtmlPath
if ($resultFile.PSIsContainer -or $resultFile.Extension -notin @('.html', '.htm')) {
    throw 'HtmlPath must point to an existing HTML file.'
}
$resultUrl = 'http://127.0.0.1:{0}/{1}' -f $Port, [Uri]::EscapeDataString($resultFile.Name)
$expectedHash = (Get-FileHash -LiteralPath $resultFile.FullName -Algorithm SHA256).Hash

function Test-ResultResponse {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $resultUrl -TimeoutSec 2
        $hasher = [Security.Cryptography.SHA256]::Create()
        try {
            $response.RawContentStream.Position = 0
            $actualHash = [BitConverter]::ToString($hasher.ComputeHash($response.RawContentStream)).Replace('-', '')
            return $response.StatusCode -eq 200 -and $actualHash -eq $expectedHash
        } finally { $hasher.Dispose() }
    } catch { return $false }
}

$listener = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
$startedServer = $null
if ($listener.Count -gt 0) {
    if (-not (Test-ResultResponse)) {
        throw "Port $Port is already in use but does not serve this exact HTML file. No process was stopped."
    }
} else {
    $pythonCommand = Get-Command python.exe -ErrorAction Stop
    # Start-Process detaches the server from this short-lived launcher. Never use -Wait.
    $startedServer = Start-Process -FilePath $pythonCommand.Source -ArgumentList @(
        '-m', 'http.server', "$Port", '--bind', '127.0.0.1',
        '--directory', ('"{0}"' -f $resultFile.DirectoryName)
    ) -WindowStyle Hidden -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-ResultResponse) { $ready = $true; break }
        if ($startedServer.HasExited) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "Result server could not start on port $Port. No existing process was stopped." }
}

if (-not $NoBrowser) {
    $chromePath = Join-Path ${env:ProgramFiles} 'Google\Chrome\Application\chrome.exe'
    if (-not (Test-Path -LiteralPath $chromePath)) {
        throw "Chrome was not found at $chromePath. The result server is ready at $resultUrl."
    }
    # Ordinary user Chrome window: not an ephemeral browser.tabs.new() automation tab.
    Start-Process -FilePath $chromePath -ArgumentList @('--new-window', $resultUrl)
}
[pscustomobject]@{
    url = $resultUrl
    started_pid = if ($startedServer) { $startedServer.Id } else { $null }
    reused = $null -eq $startedServer
    browser_opened = -not $NoBrowser
} | ConvertTo-Json -Compress
