# Keeps the Telegram bot token owned by the control window (관제창.bat).
# Telegram allows one getUpdates poller per token. Any other Claude session that loads
# the telegram plugin starts a second poller and silently takes the control window's
# messages. This loop kills Telegram servers whose claude.exe was not started with --channels.
# Started by 관제창.bat; exits when no --channels session is left.
$ErrorActionPreference = 'SilentlyContinue'
$log = Join-Path $env:USERPROFILE '.claude\channels\telegram\guard.log'

function Get-ClaudeAncestor($proc, $all) {
    $cur = $proc
    for ($i = 0; $i -lt 6 -and $cur; $i++) {
        if ($cur.Name -eq 'claude.exe') { return $cur }
        $cur = $all | Where-Object { $_.ProcessId -eq $cur.ParentProcessId } | Select-Object -First 1
    }
    return $null
}

while ($true) {
    $all = @(Get-CimInstance Win32_Process)
    $channels = $all | Where-Object { $_.Name -eq 'claude.exe' -and $_.CommandLine -match '--channels' }
    if (-not $channels) { break }

    # Only the telegram plugin's server: its bun-run wrapper's command line names the telegram plugin dir.
    $servers = $all | Where-Object { $_.Name -eq 'bun.exe' -and $_.CommandLine -match 'server\.ts' } | Where-Object {
        $pid0 = $_.ParentProcessId; ($all | Where-Object { $_.ProcessId -eq $pid0 }).CommandLine -match 'telegram'
    }
    foreach ($s in $servers) {
        $owner = Get-ClaudeAncestor $s $all
        if ($owner -and $owner.CommandLine -notmatch '--channels') {
            taskkill /PID $s.ProcessId /T /F | Out-Null
            Add-Content $log ("{0} killed stray telegram poller pid={1} owner={2} {3}" -f (Get-Date -Format s), $s.ProcessId, $owner.ProcessId, $owner.CommandLine)
        }
    }
    Start-Sleep -Seconds 15
}
