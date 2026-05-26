# 수급오실레이터 추출 스크립트
# oscillator = (5일누적 외인순매수 + 5일누적 기관순매수) / 시가총액
param(
    [string]$XlsmPath = "C:\Users\TheRose\Desktop\로또의 주식\raw\외국인기관수급오실레이터0521.xlsm",
    [string]$DateTag  = "20260521"
)

$ErrorActionPreference = "Stop"

$watchedStocks = @(
    "삼성전자","SK하이닉스","삼성전기","LG에너지솔루션",
    "POSCO홀딩스","포스코인터내셔널","크래프톤","카카오",
    "셀트리온","한화에어로스페이스","한화시스템","HD한국조선해양",
    "씨에스윈드","팬오션","엘앤에프","심텍","엠케이전자",
    "덕산하이메탈","대한광통신","효성중공업","주성엔지니어링",
    "STX엔진","현대백화점","세나테크놀로지","HD현대마린엔진",
    "지에프아이","코미코"
)

Write-Host "=== 수급오실레이터 추출 ($DateTag) ==="

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
$xl.AutomationSecurity = 1

try {
    $wb = $xl.Workbooks.Open($XlsmPath)

    $wsForeign = $wb.Sheets.Item("외국인매수데이터")
    $wsInsti   = $wb.Sheets.Item("기관매수데이터")
    $wsMktCap  = $wb.Sheets.Item("시가총액")
    $wsStats   = $wb.Sheets.Item("수급오실레이터")

    # 퍼센타일 임계값 (수급오실레이터 시트 C11~C12 블록)
    $pct90 = $wsStats.Cells.Item(7,  12).Value2
    $pct75 = $wsStats.Cells.Item(8,  12).Value2
    $avg   = $wsStats.Cells.Item(9,  12).Value2
    $pct25 = $wsStats.Cells.Item(10, 12).Value2
    $pct10 = $wsStats.Cells.Item(11, 12).Value2

    Write-Host ("상위10%:{0:F6}  상위25%:{1:F6}  평균:{2:F6}  하위25%:{3:F6}  하위10%:{4:F6}" -f $pct90,$pct75,$avg,$pct25,$pct10)
    Write-Host ""

    # 종목명 -> 컬럼 매핑
    $totalCols = $wsForeign.UsedRange.Columns.Count
    $nameToCol = @{}
    for ($c = 2; $c -le $totalCols; $c++) {
        $name = $wsForeign.Cells.Item(9, $c).Value2
        if ($name -ne $null) { $nameToCol[$name] = $c }
    }
    Write-Host "매핑: $($nameToCol.Count)개 종목"

    # 최신 행
    $lastRow    = $wsForeign.UsedRange.Rows.Count + $wsForeign.UsedRange.Row - 1
    $lastMktRow = $wsMktCap.UsedRange.Rows.Count  + $wsMktCap.UsedRange.Row - 1

    # 결과 계산
    $results = @()
    foreach ($stock in $watchedStocks) {
        if (-not $nameToCol.ContainsKey($stock)) {
            $results += [PSCustomObject]@{ Name=$stock; Found=$false; Osc=$null; Grade="미등록"; Pct="-"; MktCap=$null; Foreign=$null; Insti=$null }
            continue
        }
        $col    = $nameToCol[$stock]
        $f5d    = $wsForeign.Cells.Item($lastRow,    $col).Value2
        $i5d    = $wsInsti.Cells.Item($lastRow,      $col).Value2
        $mcap   = $wsMktCap.Cells.Item($lastMktRow,  $col).Value2

        if ($mcap -eq $null -or $mcap -eq 0) {
            $results += [PSCustomObject]@{ Name=$stock; Found=$true; Osc=$null; Grade="시총없음"; Pct="-"; MktCap=$null; Foreign=$f5d; Insti=$i5d }
            continue
        }
        $osc = ($f5d + $i5d) / $mcap

        if     ($osc -le $pct10) { $grade="A 완전빈집"; $pct="하위10%" }
        elseif ($osc -le $pct25) { $grade="B 반빈집";   $pct="하위25%" }
        elseif ($osc -ge $pct90) { $grade="D 과매수";   $pct="상위10%" }
        elseif ($osc -ge $pct75) { $grade="D 상위25%";  $pct="상위25%" }
        else                     { $grade="C 정상";     $pct="중간" }

        $results += [PSCustomObject]@{ Name=$stock; Found=$true; Osc=$osc; Grade=$grade; Pct=$pct; MktCap=$mcap; Foreign=$f5d; Insti=$i5d }
    }

    # 콘솔 출력
    Write-Host ("{0,-22} {1,-12} {2,-14} {3,-8}" -f "종목","오실레이터","등급","백분위")
    Write-Host ("-" * 60)
    foreach ($r in $results) {
        $oscStr = if ($r.Osc -ne $null) { "{0:F6}" -f $r.Osc } else { "-" }
        Write-Host ("{0,-22} {1,-12} {2,-14} {3,-8}" -f $r.Name, $oscStr, $r.Grade, $r.Pct)
    }

    Write-Host ""
    Write-Host "[ 빈집 종목 ]"
    $empty = $results | Where-Object { $_.Grade -like "A*" -or $_.Grade -like "B*" }
    foreach ($r in $empty) {
        Write-Host ("  [$($r.Grade)] $($r.Name)  osc=$("{0:F6}" -f $r.Osc)  외인=$("{0:F1}" -f $r.Foreign)bil  기관=$("{0:F1}" -f $r.Insti)bil  시총=$("{0:F0}" -f $r.MktCap)bil")
    }

    # MD 파일 저장
    $outFile = "C:\Users\TheRose\Desktop\로또의 주식\raw\supply\${DateTag}_oscillator_result.md"
    $lines = @()
    $lines += "# 수급오실레이터 결과 — $DateTag"
    $lines += ""
    $lines += "## 임계값"
    $lines += "| 구분 | 값 |"
    $lines += "|------|-----|"
    $lines += ("| 상위10% | {0:F6} |" -f $pct90)
    $lines += ("| 상위25% | {0:F6} |" -f $pct75)
    $lines += ("| 평균    | {0:F6} |" -f $avg)
    $lines += ("| 하위25% | {0:F6} |" -f $pct25)
    $lines += ("| 하위10% | {0:F6} |" -f $pct10)
    $lines += ""
    $lines += "## 추적 종목 오실레이터"
    $lines += "| 종목 | 오실레이터 | 빈집등급 | 백분위 | 시총(bil) | 외인5d | 기관5d |"
    $lines += "|------|---------|--------|-------|---------|--------|--------|"
    foreach ($r in $results) {
        if (-not $r.Found) {
            $lines += "| $($r.Name) | - | 미등록 | - | - | - | - |"
        } else {
            $oscStr = if ($r.Osc -ne $null) { "{0:F6}" -f $r.Osc } else { "-" }
            $mcStr  = if ($r.MktCap  -ne $null) { "{0:F0}" -f $r.MktCap }  else { "-" }
            $fStr   = if ($r.Foreign -ne $null) { "{0:F1}" -f $r.Foreign } else { "-" }
            $iStr   = if ($r.Insti   -ne $null) { "{0:F1}" -f $r.Insti }   else { "-" }
            $lines += "| $($r.Name) | $oscStr | $($r.Grade) | $($r.Pct) | $mcStr | $fStr | $iStr |"
        }
    }
    $lines += ""
    $lines += "## 빈집 종목 요약"
    foreach ($r in $empty) {
        $lines += ("- **[$($r.Grade)]** $($r.Name) — osc={0:F6}  시총={1:F0}bil" -f $r.Osc, $r.MktCap)
    }
    $lines | Out-File -FilePath $outFile -Encoding utf8

    Write-Host ""
    Write-Host "저장: $outFile"

} finally {
    $wb.Close($false)
    $xl.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}