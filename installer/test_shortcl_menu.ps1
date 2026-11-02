# 숏클 시작 메뉴 시험 — Read-Host 와 claude 를 가짜 함수로 바꿔 메뉴를 그대로 돌린다.  powershell -NoProfile -File installer/test_shortcl_menu.ps1
$menu = if ($env:MENU_FILE) { $env:MENU_FILE } else { Join-Path $PSScriptRoot 'shortcl_menu.ps1' }
$global:fail = 0
function Case($name, $inputs, $logged, $afterLogin, $want) {
    $global:afterLogin = $afterLogin
    $global:q = [Collections.Queue]::new(); $inputs | ForEach-Object { $global:q.Enqueue($_) }
    $global:calls = @(); $global:isIn = $logged
    function global:Read-Host { param($p) if ($global:q.Count) { $global:q.Dequeue() } else { throw '입력 부족' } }
    function global:claude { $a = if ($args.Count) { $args -join ' ' } else { 'START' }; $global:calls += $a
        if ($a -eq 'auth status') { '{"loggedIn": ' + $(if ($global:isIn) { 'true' } else { 'false' }) + '}' }
        if ($a -eq 'auth login') { $global:isIn = $global:afterLogin } }
    function global:Set-Location { }
    $null = & $menu -Work 'C:\x' *>&1
    $got = ($global:calls | Where-Object { $_ -ne 'auth status' }) -join ','
    if ($got -ne $want) { $global:fail++; Write-Output "실패 $name : [$got] != [$want]" } else { Write-Output "통과 $name : [$got]" }
}
$code = '2qo9IIiB6ytaSvPfC47eg0UAkzzLtUYlKJWV6#NreWC9pc59VjrSZH_j2AKxNwQQVXOtve7P7mgQqXyvs'
Case '코드 붙임 → 로그인 뒤 시작' @($code) $false $true 'auth login,START'
Case '코드 붙임 → 로그인 실패면 시작 안 함' @($code) $false $false 'auth login'
Case '이상한 글 → 다시 묻고 엔터' @('abc', '') $false $false ''
Case '1 로그인됨 → 시작' @('1') $true $true 'START'
Case '이미 로그인 + 코드 → 다시 묻고 엔터' @($code, '') $true $true ''
Case '엔터 → 끝' @('') $false $false ''
exit $global:fail
