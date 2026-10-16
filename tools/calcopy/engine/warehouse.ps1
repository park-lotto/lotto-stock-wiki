# 소재창고 상시 가동(관제 097, 2026-10-16 사장님 "소재·대본 워커를 상시로 돌려 창고에 쌓아라") — 로컬 서버 1 + 채널 워커 4.
#   powershell -ExecutionPolicy Bypass -File tools/calcopy/engine/warehouse.ps1 start|stop|status
# 데이터 = C:/숏템_칼카피/창고 (CALCOPY_DATA_DIR) · 로그 = 창고/server.log · 창고/worker_<채널>.log · PID = 창고/pids.json
# 워커 단계 = bench·score·assign·script·source (produce·check·plan 없음 — 타입캐스트·유료 0, 재료 고르기는 사람/오푸스 자리)
# 한도는 코드(worker_ledger.py): 유튜브 4워커 합 시간당 300편 · 제미나이 워커당 시간당 10회 · 429 면 30분 쉼.
param([string]$cmd = "status")
$ErrorActionPreference = "Stop"
$track = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$data = "C:\숏템_칼카피\창고"
# ★서버·워커는 창고 전용 체크아웃에서 돈다 — 트랙 폴더는 담당 여럿이 편집 중이라 커밋 안 된 반쪽 코드를 읽는다(10-16 실측).
#   커밋된 것만: 시작 때 이 브랜치 끝으로 옮기고, 워커는 엔진 커밋이 바뀌면 스스로 따라간다(CALCOPY_FOLLOW_REF).
$branch = "track/칼카피숏템엔진"
$root = Join-Path $data "code"
$py = (Get-Command python.exe).Source
$pidf = Join-Path $data "pids.json"
$port = 8851
$workers = @(
  @{slug="sseolpulda";  category="해외썰";     preset="channel/sseolpulda/preset/A_흰바탕창/창아래_검정"; steps="bench,score,assign,script,source"; extra=@()},
  @{slug="yummyknow";   category="식품";       preset="channel/yummyknow/preset/게시글형";            steps="bench,score,assign,script,source"; extra=@()},
  @{slug="banggu";      category="숨은이유";   preset="channel/banggu/preset/게시글형";               steps="bench,score,assign,script,source"; extra=@()},
  # 핫템은 프리셋(뜯기·틀)이 아직 없다 → 재료 후보(source)는 못 받는다. 소재·벤치·점수·대본까지만.
  @{slug="hottemreport"; category="신기한제품"; preset="hottemreport";                                steps="bench,score,assign,script";        extra=@("--source-kind","해외영상","--keywords","신기한 제품,신박한 아이템,생활 발명품,amazing gadget,cool gadgets,kitchen gadget")}
)

function Start-One($name, $args_, $log) {
  # Start-Process 는 인자를 공백으로 다시 쪼갠다 — 공백 있는 인자는 따옴표로 감싼다(핫템 --keywords 가 깨졌다, 10-16 실측)
  $q = $args_ | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
  $p = Start-Process -FilePath $py -ArgumentList $q -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError ($log -replace '\.log$', '.err.log')
  return @{name=$name; pid=$p.Id}
}

function Alive($id) { try { Get-Process -Id $id -ErrorAction Stop | Out-Null; $true } catch { $false } }

if ($cmd -eq "start") {
  New-Item -ItemType Directory -Force $data | Out-Null
  if (-not (Test-Path (Join-Path $root ".git"))) { git -C $track worktree add --detach $root $branch | Out-Null }
  git -C $root checkout --detach -q $branch
  if (-not (Test-Path (Join-Path $root ".env")) -and (Test-Path (Join-Path $track ".env"))) { Copy-Item (Join-Path $track ".env") $root }
  $env:CALCOPY_FOLLOW_REF = $branch
  Write-Output ("코드 = {0} @ {1}" -f $root, (git -C $root rev-parse --short HEAD))
  $env:CALCOPY_DATA_DIR = $data
  $env:PYTHONUTF8 = "1"
  $env:PYTHONIOENCODING = "utf-8"
  $env:PYTHONUNBUFFERED = "1"
  $procs = @()
  $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($busy) { Write-Output "포트 $port 이미 사용 중(PID $($busy.OwningProcess)) — 서버는 새로 안 띄운다" }
  else { $procs += Start-One "server" @("-m","uvicorn","shopping_shorts.app:app","--port","$port","--lifespan","off") (Join-Path $data "server.log") }
  for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/api/admin/calcopy/topics?limit=1" -TimeoutSec 3 | Out-Null; break } catch { Start-Sleep 2 }
  }
  foreach ($w in $workers) {
    $a = @("tools/calcopy/engine/worker.py","--category",$w.category,"--track","bench","--channel",$w.slug,"--preset",$w.preset,
           "--name","창고-$($w.slug)","--server","http://127.0.0.1:$port","--cookie","local","--out",(Join-Path $data "work\$($w.slug)"),
           "--steps",$w.steps,"--find-every","30","--llm-budget","6","--idle-sleep","60","--loop") + $w.extra
    $procs += Start-One "worker-$($w.slug)" $a (Join-Path $data "worker_$($w.slug).log")
  }
  $procs | ConvertTo-Json | Set-Content -Encoding utf8 $pidf
  $procs | ForEach-Object { Write-Output "$($_.name) PID $($_.pid)" }
}
elseif ($cmd -eq "stop") {
  if (Test-Path $pidf) {
    (Get-Content $pidf -Raw | ConvertFrom-Json) | ForEach-Object { if (Alive $_.pid) { Stop-Process -Id $_.pid -Force; Write-Output "멈춤 $($_.name) $($_.pid)" } }
  }
}
else {
  if (Test-Path $pidf) {
    (Get-Content $pidf -Raw | ConvertFrom-Json) | ForEach-Object { Write-Output ("{0,-22} PID {1,-7} {2}" -f $_.name, $_.pid, $(if (Alive $_.pid) {"살아있음"} else {"죽음"})) }
  } else { Write-Output "pids.json 없음 — start 안 함" }
}
