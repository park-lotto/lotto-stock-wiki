# Remove orphaned Deny ACEs from .git
#
# WHY THIS EXISTS
#   Codex CLI (Windows sandbox) stamps Deny ACEs onto .git to "protect" git history.
#   When the sandbox user account is later deleted, the Deny ACE stays behind as an
#   unresolvable (orphan) SID. Windows evaluates Deny before Allow, so those leftover
#   entries block every Codex session from creating .git/refs/heads/*.lock -- which
#   makes "git branch" / "git worktree add" fail with "Permission denied".
#   See openai/codex issues #21304, #18918, #19315, #27418, #19190.
#
# WHY icacls DOES NOT WORK
#   "icacls /remove:d <SID>" resolves the trustee to a name before matching.
#   An orphan SID has no name, so nothing matches and icacls reports
#   "0 files processed" while the ACEs remain. Set-Acl matches the rule object
#   directly, so no name resolution is required.
#
# SAFETY
#   Only NON-inherited Deny entries whose SID cannot be resolved are removed.
#   Live accounts (CH, SYSTEM, Administrators, CodexSandboxUsers) resolve fine and
#   are therefore never touched. SIDs are not hardcoded, so new orphans are caught too.
#   The current SDDL is saved to %LOCALAPPDATA%\codex_git_acl_backup before any change.
#
# USAGE
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\fix_git_acl.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\fix_git_acl.ps1 -Preview

param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$Preview
)

$ErrorActionPreference = 'Stop'
$gitDir = Join-Path $RepoRoot '.git'

if (-not (Test-Path $gitDir)) {
    Write-Host "[FAIL] .git not found: $gitDir" -ForegroundColor Red
    exit 1
}

Write-Host "Target: $gitDir"

$acl = Get-Acl $gitDir

$orphanDenies = @()
foreach ($rule in @($acl.Access)) {
    if ($rule.AccessControlType -ne 'Deny') { continue }
    if ($rule.IsInherited) { continue }

    $resolved = $true
    try   { $null = $rule.IdentityReference.Translate([System.Security.Principal.NTAccount]) }
    catch { $resolved = $false }

    if (-not $resolved) { $orphanDenies += $rule }
}

if ($orphanDenies.Count -eq 0) {
    Write-Host "[OK] No orphan Deny entries. Nothing to do." -ForegroundColor Green
    exit 0
}

Write-Host "Found orphan Deny rules: $($orphanDenies.Count)" -ForegroundColor Yellow
foreach ($rule in $orphanDenies) {
    Write-Host ("  - {0} / {1}" -f $rule.IdentityReference, $rule.FileSystemRights)
}

if ($Preview) {
    Write-Host "[PREVIEW] -Preview specified. Nothing was changed." -ForegroundColor Cyan
    exit 0
}

$backupDir = Join-Path $env:LOCALAPPDATA 'codex_git_acl_backup'
if (-not (Test-Path $backupDir)) { $null = New-Item -ItemType Directory -Force -Path $backupDir }
$backupFile = Join-Path $backupDir ("git_sddl_{0}.txt" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
$acl.Sddl | Set-Content -Path $backupFile -Encoding UTF8
Write-Host "Backup saved: $backupFile"

foreach ($rule in $orphanDenies) { $null = $acl.RemoveAccessRuleSpecific($rule) }
Set-Acl -Path $gitDir -AclObject $acl

# Verify by re-reading, not by assuming the write worked.
$after = (Get-Acl $gitDir).Access | Where-Object { $_.AccessControlType -eq 'Deny' -and -not $_.IsInherited }
if (@($after).Count -eq 0) {
    Write-Host "[SUCCESS] Removed $($orphanDenies.Count) orphan Deny rules. Deny count is now 0." -ForegroundColor Green
} else {
    Write-Host "[WARN] $(@($after).Count) Deny entries still remain:" -ForegroundColor Red
    $after | ForEach-Object { Write-Host ("  - {0}" -f $_.IdentityReference) }
    exit 1
}

# Prove writability instead of inferring it from the ACL.
$probe = Join-Path $gitDir 'refs\heads\_acl_probe.tmp'
try {
    [System.IO.File]::WriteAllText($probe, 'probe')
    Remove-Item $probe -Force
    Write-Host "[VERIFIED] refs/heads is writable. Branch creation should work now." -ForegroundColor Green
} catch {
    Write-Host "[VERIFY FAILED] refs/heads still not writable: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
