# extract_유동성.ps1
# 용도: 유동성 체크 xlsm 파일 → 마크다운 요약 출력
# 사용: .\extract_유동성.ps1 -FilePath "raw\market\20260526_유동성.xlsm"
#       FilePath 생략 시 raw\market\ 에서 최신 *_유동성*.xlsm 자동 탐지
# 출력: raw\market\YYYYMMDD_유동성_요약.md  (Claude가 /ingest로 처리)

param(
    [string]$FilePath = "",
    [string]$BaseDir  = "C:\Users\TheRose\Desktop\로또의 주식"
)

Set-Location $BaseDir
$OutputDir = "raw\market"

# ── 파일 탐지 ──────────────────────────────────────────────────────
if (-not $FilePath) {
    $candidates = @(
        (Get-ChildItem "$OutputDir\*_유동성*.xlsm" -ErrorAction SilentlyContinue),
        (Get-ChildItem "raw\*유동성*.xlsm" -ErrorAction SilentlyContinue)
    ) | ForEach-Object { $_ } | Where-Object { $_ }
    $latest = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) { $FilePath = $latest.FullName }
    else {
        Write-Error "xlsm 파일을 찾을 수 없습니다. -FilePath 로 지정하세요."
        exit 1
    }
}

if (-not (Test-Path $FilePath)) {
    Write-Error "파일 없음: $FilePath"
    exit 1
}

$absPath = (Resolve-Path $FilePath).Path
$fname   = [System.IO.Path]::GetFileNameWithoutExtension($absPath)

# 날짜 추출 (파일명에 8자리 숫자 있으면 사용, 없으면 오늘)
if ($fname -match "(\d{8})") {
    $ds      = $Matches[1]
    $dateStr = "$($ds.Substring(0,4))-$($ds.Substring(4,2))-$($ds.Substring(6,2))"
} else {
    $ds      = Get-Date -Format "yyyyMMdd"
    $dateStr = Get-Date -Format "yyyy-MM-dd"
}

$outputFile = Join-Path $BaseDir "$OutputDir\${ds}_유동성_요약.md"

# ── Wiki 종목 목록 ─────────────────────────────────────────────────
$wikiStocks = @(
    [PSCustomObject]@{Name="삼성전자";         Code="005930"; Sector="반도체"}
    [PSCustomObject]@{Name="SK하이닉스";        Code="000660"; Sector="반도체"}
    [PSCustomObject]@{Name="피에스케이";        Code="319660"; Sector="반도체장비"}
    [PSCustomObject]@{Name="피에스케이홀딩스";   Code="286940"; Sector="반도체장비"}
    [PSCustomObject]@{Name="솔브레인";          Code="357780"; Sector="반도체소재"}
    [PSCustomObject]@{Name="동진쎄미켐";        Code="005290"; Sector="반도체소재"}
    [PSCustomObject]@{Name="코미코";            Code="183300"; Sector="반도체부품"}
    [PSCustomObject]@{Name="원익머트리얼즈";     Code="104830"; Sector="반도체소재"}
    [PSCustomObject]@{Name="브이엠";            Code="314130"; Sector="반도체장비"}
    [PSCustomObject]@{Name="테스";              Code="095610"; Sector="반도체장비"}
    [PSCustomObject]@{Name="파크시스템스";       Code="140860"; Sector="반도체장비"}
    [PSCustomObject]@{Name="주성엔지니어링";     Code="036930"; Sector="반도체장비"}
    [PSCustomObject]@{Name="원익IPS";           Code="240810"; Sector="반도체장비"}
    [PSCustomObject]@{Name="덕산하이메탈";       Code="077360"; Sector="반도체소재"}
    [PSCustomObject]@{Name="효성중공업";         Code="298040"; Sector="전력기기"}
    [PSCustomObject]@{Name="대한광통신";         Code="010170"; Sector="광통신"}
    [PSCustomObject]@{Name="HD현대중공업";       Code="009540"; Sector="조선"}
    [PSCustomObject]@{Name="한화오션";           Code="042660"; Sector="조선"}
    [PSCustomObject]@{Name="삼성중공업";         Code="010140"; Sector="조선"}
    [PSCustomObject]@{Name="HD현대마린솔루션";   Code="443060"; Sector="조선"}
    [PSCustomObject]@{Name="대한조선";           Code="439260"; Sector="조선"}
    [PSCustomObject]@{Name="HJ중공업";           Code="097230"; Sector="조선"}
    [PSCustomObject]@{Name="씨엠티엑스";          Code="TBD";    Sector="반도체소재"}  # CMTX — 한국거래소 정확한 종목명 미확정
)
$wikiNames = $wikiStocks | ForEach-Object { $_.Name }

# ── 빈집 등급 함수 ──────────────────────────────────────────────────
# 통합순위: 1 = 가장 빈집(기관 매수 가장 없음) / 2574 = 기관이 가장 많이 매수(과매수)
function Get-BinjiGrade {
    param([double]$rank, [int]$total = 2574)
    $pct = $rank / $total   # 낮을수록 빈집
    if ($pct -le 0.10) { return "A 완전빈집" }
    if ($pct -le 0.25) { return "B 반빈집" }
    if ($pct -le 0.75) { return "C 정상" }
    return "D 과매수"
}

function Get-BinjiEmoji { param([string]$g)
    switch ($g) {
        "A 완전빈집" { return "🔴" }
        "B 반빈집"   { return "🟠" }
        "C 정상"     { return "🟡" }
        "D 과매수"   { return "⚫" }
        default       { return "—" }
    }
}

# ── 시트 탐색 함수 ─────────────────────────────────────────────────
function Find-Sheet {
    param($wb, [string[]]$patterns)
    foreach ($pat in $patterns) {
        foreach ($sh in $wb.Sheets) {
            if ($sh.Name -like "*$pat*") { return $sh }
        }
    }
    return $null
}

# 헤더 행에서 특정 텍스트의 열 번호 반환
function Find-ColByHeader {
    param($sheet, [string]$text, [int]$searchRows = 3)
    $lastCol = [Math]::Min($sheet.UsedRange.Columns.Count, 30)
    for ($r = 1; $r -le $searchRows; $r++) {
        for ($c = 1; $c -le $lastCol; $c++) {
            if ($sheet.Cells($r,$c).Text -like "*$text*") {
                return [PSCustomObject]@{ Row=$r; Col=$c }
            }
        }
    }
    return $null
}

# ── Excel 열기 ─────────────────────────────────────────────────────
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host "유동성 데이터 추출 — $dateStr"
Write-Host "파일: $absPath"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

$excel = New-Object -ComObject Excel.Application
$excel.Visible          = $false
$excel.DisplayAlerts    = $false
$excel.AutomationSecurity = 1

$liquidResults  = @()
$sinhogaResults = @()
$moResults      = @()
$topSectors     = @()
$moTopSectors   = @()
$sheetList      = @()

try {
    $wb = $excel.Workbooks.Open($absPath, 0, $true)

    foreach ($sh in $wb.Sheets) { $sheetList += $sh.Name }
    Write-Host "시트 목록 ($($sheetList.Count)개): $($sheetList -join ' | ')"

    # ════════════════════════════════════════════════════════
    # 1. 유동성 컨셉 — 수급 빈집 판단
    # ════════════════════════════════════════════════════════
    $liqSheet = Find-Sheet $wb @("유동성컨셉","유동성 컨셉","유동성")
    if ($liqSheet) {
        Write-Host "`n[1] 유동성 컨셉: $($liqSheet.Name)"
        $usedRange = $liqSheet.UsedRange
        $totalRows = $usedRange.Rows.Count
        $totalCols = $usedRange.Columns.Count
        Write-Host "    범위: ${totalRows}행 × ${totalCols}열"

        # 종목명 컬럼 탐색
        $nameHdr = Find-ColByHeader $liqSheet "종목명"
        if (-not $nameHdr) { $nameHdr = [PSCustomObject]@{ Row=1; Col=2 } }

        $headerRow = $nameHdr.Row
        $nameCol   = $nameHdr.Col
        $codeCol   = $nameCol - 1   # 왼쪽이 종목코드
        $sectorCol = $nameCol + 2   # D = 업종
        $ret1mCol  = $nameCol + 3   # E = 1개월수익률
        # H(C8)부터 통합순위(C18)까지: nameCol+6 ~ nameCol+16
        $rankBase  = $nameCol + 6   # C8 = 사모 시총대비 순위 시작
        $totalRankCol = $nameCol + 16  # C18 = 통합순위

        Write-Host "    헤더행: $headerRow  종목명열: $nameCol  통합순위열: $totalRankCol"

        $dataStart  = $headerRow + 1
        $scanEnd    = [Math]::Min($dataStart + 2600, $totalRows)

        # ① 먼저 전체 종목 수 사전 카운팅
        $totalStocks = 0
        for ($r = $dataStart; $r -le $scanEnd; $r++) {
            if ($liqSheet.Cells($r, $nameCol).Text) { $totalStocks++ }
        }
        Write-Host "    총 종목 수: $totalStocks"

        # ② Wiki 종목 데이터 추출
        for ($r = $dataStart; $r -le $scanEnd; $r++) {
            $sn = $liqSheet.Cells($r, $nameCol).Text
            if (-not $sn) { continue }

            if ($wikiNames -contains $sn) {
                $rawRank = $liqSheet.Cells($r, $totalRankCol).Value2
                $r1m     = $liqSheet.Cells($r, $ret1mCol).Text
                $forPct  = $liqSheet.Cells($r, $rankBase + 3).Value2   # C11 외국인 시총대비
                $penPct  = $liqSheet.Cells($r, $rankBase + 2).Value2   # C10 연금

                if ($rawRank -and $rawRank -gt 0) {
                    # 빈집 판정: 통합순위 낮을수록 빈집 (rank 1 = 기관 매수 가장 없음)
                    $grade  = Get-BinjiGrade -rank $rawRank -total $totalStocks
                    $pctNum = [Math]::Round($rawRank / $totalStocks * 100, 1)   # 빈집 상위 X%
                    $ws = $wikiStocks | Where-Object { $_.Name -eq $sn } | Select-Object -First 1
                    $liquidResults += [PSCustomObject]@{
                        Name      = $sn
                        Code      = $ws.Code
                        Sector    = $ws.Sector
                        TotalRank = [int]$rawRank
                        TotalN    = $totalStocks
                        Pct       = $pctNum
                        Grade     = $grade
                        Emoji     = Get-BinjiEmoji -g $grade
                        Score     = if ($grade -match "A|B") { 2 } else { 0 }
                        Ret1M     = $r1m
                        ForeignPct= $forPct
                        PensionPct= $penPct
                    }
                }
            }
        }

        # A→B→C→D 순 (빈집 심한 것 먼저 = 낮은 rank 먼저)
        $liquidResults = $liquidResults | Sort-Object TotalRank
        Write-Host "    스캔: $totalStocks 종목 / Wiki 발견: $($liquidResults.Count)개"
    } else {
        Write-Host "[1] ⚠️ 유동성 컨셉 시트 없음 — 시트명 확인 필요"
    }

    # ════════════════════════════════════════════════════════
    # 2. 2027년 컨센 신고가 — 리포트신고가 탑픽 +1점
    # ════════════════════════════════════════════════════════
    $sgSheet = Find-Sheet $wb @("신고가","컨센신고가","컨센 신고가","2027")
    if ($sgSheet) {
        Write-Host "`n[2] 컨센 신고가: $($sgSheet.Name)"
        $lastRow = $sgSheet.UsedRange.Rows.Count
        $nameHdr = Find-ColByHeader $sgSheet "종목명"
        $nc = if ($nameHdr) { $nameHdr.Col } else { 2 }
        $hr = if ($nameHdr) { $nameHdr.Row } else { 1 }

        for ($r = $hr + 1; $r -le $lastRow; $r++) {
            $sn   = $sgSheet.Cells($r, $nc).Text
            if (-not $sn) { continue }
            $isNew = $sgSheet.Cells($r, $nc + 1).Value2   # C3: 0=신고가
            $date  = $sgSheet.Cells($r, $nc + 3).Text     # C5: 발표일
            $firm  = $sgSheet.Cells($r, $nc + 4).Text     # C6: 증권사
            $op27  = $sgSheet.Cells($r, $nc + 6).Value2   # C8: 2027E OP

            if ($wikiNames -contains $sn) {
                $sinhogaResults += [PSCustomObject]@{
                    Name   = $sn
                    IsNew  = ($isNew -eq 0)
                    NewStr = if ($isNew -eq 0) { "✅ 신고가" } else { "—" }
                    Date   = $date
                    Firm   = $firm
                    OP2027 = $op27
                }
            }
        }
        Write-Host "    Wiki 발견: $($sinhogaResults.Count)개 (신고가: $(($sinhogaResults | Where-Object IsNew).Count)개)"
    } else {
        Write-Host "[2] ⚠️ 컨센 신고가 시트 없음"
    }

    # ════════════════════════════════════════════════════════
    # 3. 가속화모멘텀 — 주도섹터 + Wiki 종목
    # ════════════════════════════════════════════════════════
    $moSheet = Find-Sheet $wb @("가속화모멘텀","가속화 모멘텀","모멘텀")
    if ($moSheet) {
        Write-Host "`n[3] 가속화모멘텀: $($moSheet.Name)"
        $lastRow = $moSheet.UsedRange.Rows.Count
        $nameHdr = Find-ColByHeader $moSheet "종목명"
        $nc = if ($nameHdr) { $nameHdr.Col } else { 2 }
        $hr = if ($nameHdr) { $nameHdr.Row } else { 1 }
        $sectorBucket = @{}

        for ($r = $hr + 1; $r -le $lastRow; $r++) {
            $sn    = $moSheet.Cells($r, $nc).Text
            if (-not $sn) { continue }
            $score = $moSheet.Cells($r, $nc + 1).Value2
            $opChg = $moSheet.Cells($r, $nc + 2).Value2
            $sectr = $moSheet.Cells($r, $nc + 3).Text    # 업종

            if ($sectr) {
                if (-not $sectorBucket.ContainsKey($sectr)) { $sectorBucket[$sectr] = 0 }
                $sectorBucket[$sectr]++
            }

            if ($wikiNames -contains $sn) {
                $moResults += [PSCustomObject]@{
                    Name    = $sn
                    Score   = $score
                    OPChange= $opChg
                }
            }
        }

        # 업종 군집 → 주도섹터 (3개 이상 종목 군집된 업종)
        $moTopSectors = $sectorBucket.GetEnumerator() |
            Where-Object { $_.Value -ge 3 } |
            Sort-Object Value -Descending |
            Select-Object -First 8 |
            ForEach-Object { [PSCustomObject]@{ Sector=$_.Key; Count=$_.Value } }

        Write-Host "    Wiki 발견: $($moResults.Count)개 / 군집 업종: $($moTopSectors.Count)개"
    } else {
        Write-Host "[3] ⚠️ 가속화모멘텀 시트 없음"
    }

    # ════════════════════════════════════════════════════════
    # 4. 업종 1개월 컨센 — 주도섹터 점수
    # ════════════════════════════════════════════════════════
    $secSheet = Find-Sheet $wb @("업종 1개월","업종1개월","업종컨센","업종 컨센","업종")
    if ($secSheet) {
        Write-Host "`n[4] 업종 컨센: $($secSheet.Name)"
        $lastRow  = $secSheet.UsedRange.Rows.Count
        $lastCol  = $secSheet.UsedRange.Columns.Count

        # 최종점수 컬럼 탐색
        $finalCol = $lastCol
        for ($c = 1; $c -le $lastCol; $c++) {
            $hdr = $secSheet.Cells(1,$c).Text
            if ($hdr -like "*최종*" -or $hdr -like "*종합*" -or $hdr -like "*total*") {
                $finalCol = $c; break
            }
        }

        for ($r = 2; $r -le $lastRow; $r++) {
            $secName = $secSheet.Cells($r, 1).Text
            $score   = $secSheet.Cells($r, $finalCol).Value2
            if ($secName -and $score) {
                $topSectors += [PSCustomObject]@{ Sector=$secName; Score=[double]$score }
            }
        }
        $topSectors = $topSectors | Sort-Object Score -Descending | Select-Object -First 10
        Write-Host "    업종 상위10: $(($topSectors | Select-Object -First 5 | ForEach-Object { "$($_.Sector)($($_.Score))" }) -join ', ')"
    } else {
        Write-Host "[4] ⚠️ 업종 컨센 시트 없음"
    }

    # ════════════════════════════════════════════════════════
    # 마크다운 출력
    # ════════════════════════════════════════════════════════
    $lines = [System.Collections.Generic.List[string]]::new()

    $lines.Add("# 유동성 데이터 요약 — $dateStr")
    $lines.Add("")
    $lines.Add("> **소스**: $fname.xlsm")
    $lines.Add("> **생성**: $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
    $lines.Add("> **Wiki 종목**: $($wikiStocks.Count)개 추적")
    $lines.Add("")
    $lines.Add("---")
    $lines.Add("")

    # ── 섹션 1: 수급 빈집 ──
    $lines.Add("## 1. 수급 빈집 현황 (탑픽 수급빈집 점수)")
    $lines.Add("")
    $gradeA = $liquidResults | Where-Object { $_.Grade -eq "A 완전빈집" }
    $gradeB = $liquidResults | Where-Object { $_.Grade -eq "B 반빈집" }
    $gradeC = $liquidResults | Where-Object { $_.Grade -eq "C 정상" }
    $gradeD = $liquidResults | Where-Object { $_.Grade -eq "D 과매수" }

    $lines.Add("### 🔴 A 완전빈집 — 하위 10% (탑픽 2점)")
    if ($gradeA.Count -gt 0) {
        $lines.Add("| 종목 | 섹터 | 통합순위 | 빈집 상위% | 1개월수익률 |")
        $lines.Add("|------|------|---------|----------|----------|")
        foreach ($s in $gradeA) {
            $lines.Add("| **$($s.Name)** | $($s.Sector) | $($s.TotalRank)/$($s.TotalN) | 상위$($s.Pct)% | $($s.Ret1M) |")
        }
    } else { $lines.Add("_없음_") }
    $lines.Add("")

    $lines.Add("### 🟠 B 반빈집 — 하위 10~25% (탑픽 2점)")
    if ($gradeB.Count -gt 0) {
        $lines.Add("| 종목 | 섹터 | 통합순위 | 빈집 상위% |")
        $lines.Add("|------|------|---------|----------|")
        foreach ($s in $gradeB) {
            $lines.Add("| **$($s.Name)** | $($s.Sector) | $($s.TotalRank)/$($s.TotalN) | 상위$($s.Pct)% |")
        }
    } else { $lines.Add("_없음_") }
    $lines.Add("")

    $lines.Add("### 🟡 C 정상 / ⚫ D 과매수")
    if ($gradeC.Count -gt 0 -or $gradeD.Count -gt 0) {
        $lines.Add("| 종목 | 섹터 | 등급 | 통합순위 |")
        $lines.Add("|------|------|------|---------|")
        foreach ($s in ($gradeC + $gradeD)) {
            $lines.Add("| $($s.Name) | $($s.Sector) | $($s.Grade) | $($s.TotalRank)/$($s.TotalN) |")
        }
    }
    $lines.Add("")
    $lines.Add("---")
    $lines.Add("")

    # ── 섹션 2: 컨센 신고가 ──
    $lines.Add("## 2. 2027 컨센 신고가 (탑픽 리포트신고가 +1점)")
    $lines.Add("")
    if ($sinhogaResults.Count -gt 0) {
        $lines.Add("| 종목 | 신고가 | 증권사 | 2027E OP | 발표일 |")
        $lines.Add("|------|-------|-------|---------|-------|")
        foreach ($s in ($sinhogaResults | Sort-Object IsNew -Descending)) {
            $lines.Add("| $($s.Name) | $($s.NewStr) | $($s.Firm) | $($s.OP2027) | $($s.Date) |")
        }
    } else {
        $lines.Add("_Wiki 종목 중 신고가 리스트 없음 (시트 컬럼 구조 확인 필요)_")
    }
    $lines.Add("")
    $lines.Add("---")
    $lines.Add("")

    # ── 섹션 3: 주도섹터 ──
    $lines.Add("## 3. 주도섹터")
    $lines.Add("")
    $lines.Add("### 업종 1개월 컨센 상위 (이익모멘텀+밸류+성장+트렌드 종합)")
    if ($topSectors.Count -gt 0) {
        $lines.Add("| 순위 | 업종 | 종합점수 |")
        $lines.Add("|------|------|---------|")
        $rn = 1
        foreach ($s in $topSectors) {
            $star = if ($rn -le 3) { "⭐" } else { "" }
            $lines.Add("| $rn $star| $($s.Sector) | $($s.Score) |")
            $rn++
        }
    } else { $lines.Add("_데이터 없음_") }
    $lines.Add("")

    $lines.Add("### 가속화모멘텀 군집 업종 (추정이익 증가+주가 동시 가속)")
    if ($moTopSectors.Count -gt 0) {
        $lines.Add("| 업종 | 포함 종목 수 |")
        $lines.Add("|------|------------|")
        foreach ($s in $moTopSectors) {
            $lines.Add("| $($s.Sector) | $($s.Count)개 |")
        }
    } else { $lines.Add("_데이터 없음_") }
    $lines.Add("")
    $lines.Add("---")
    $lines.Add("")

    # ── 섹션 4: 가속화모멘텀 Wiki 종목 ──
    $lines.Add("## 4. 가속화모멘텀 — Wiki 종목 포함 여부")
    $lines.Add("")
    if ($moResults.Count -gt 0) {
        $lines.Add("| 종목 | 모멘텀스코어 | OP추정치변화 |")
        $lines.Add("|------|------------|------------|")
        foreach ($s in ($moResults | Sort-Object Score -Descending)) {
            $lines.Add("| **$($s.Name)** | $($s.Score) | $($s.OPChange) |")
        }
    } else {
        $lines.Add("_Wiki 종목 없음 (가속화 구간 아님)_")
    }
    $lines.Add("")
    $lines.Add("---")
    $lines.Add("")

    # ── 섹션 5: 탑픽 통합 점수 요약 ──
    $lines.Add("## 5. 탑픽 자동 점수 변화 요약")
    $lines.Add("")
    $lines.Add("> 아래 항목은 /ingest 처리 시 stock/ 파일 수급흐름 + 탑픽점수에 반영")
    $lines.Add("")
    $lines.Add("| 종목 | 수급빈집(0~2) | 리포트신고가(0~1) | 비고 |")
    $lines.Add("|------|-------------|---------------|------|")
    foreach ($s in $wikiStocks) {
        $liq = $liquidResults | Where-Object { $_.Name -eq $s.Name } | Select-Object -First 1
        $sg  = $sinhogaResults | Where-Object { $_.Name -eq $s.Name -and $_.IsNew } | Select-Object -First 1
        $binjiScore = if ($liq) { $liq.Score } else { "?" }
        $sgScore    = if ($sg) { 1 } else { 0 }
        $binjiStr   = if ($liq) { "$binjiScore ($($liq.Grade))" } else { "? (미발견)" }
        if ($liq -or $sg) {
            $lines.Add("| $($s.Name) | $binjiStr | $sgScore | |")
        }
    }
    $lines.Add("")

    # ── 섹션 6: 미발견 종목 ──
    $foundNames = $liquidResults | ForEach-Object { $_.Name }
    $notFound = $wikiNames | Where-Object { $foundNames -notcontains $_ }
    if ($notFound.Count -gt 0) {
        $lines.Add("## 6. 유동성 시트 미발견 종목")
        $lines.Add("")
        $lines.Add("_아래 종목은 유동성 컨셉 시트에서 이름 불일치 또는 미포함:_")
        $lines.Add("")
        $lines.Add(($notFound -join ", "))
        $lines.Add("")
    }

    $lines.Add("---")
    $lines.Add("_이 파일은 자동 생성. `/ingest raw/market/${ds}_유동성_요약.md` 로 wiki 반영._")

    # 파일 저장 (UTF-8 without BOM)
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($outputFile, $lines, $utf8NoBom)

    Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Write-Host "✅ 완료: $outputFile"
    Write-Host ""
    Write-Host "다음 단계:"
    Write-Host "  Claude에게 '/ingest raw\market\${ds}_유동성_요약.md' 입력"
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

} catch {
    Write-Error "오류 발생: $_"
    Write-Error $_.ScriptStackTrace
} finally {
    if ($wb)    { try { $wb.Close($false) }    catch {} }
    if ($excel) {
        try { $excel.Quit() }                   catch {}
        try {
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
        } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
