# 칼카피 엔진 — 소재창고 워커 상시 가동 (관제 097)

## 켜기 · 끄기 · 상태 (한 줄)

```
powershell -ExecutionPolicy Bypass -File tools/calcopy/engine/warehouse.ps1 start    # 로컬 서버(:8851) + 채널 워커 4
powershell -ExecutionPolicy Bypass -File tools/calcopy/engine/warehouse.ps1 stop     # 멈춤(pids.json 의 프로세스 전부)
powershell -ExecutionPolicy Bypass -File tools/calcopy/engine/warehouse.ps1 status   # 살아있나
```

- 코드: `C:/숏템_칼카피/창고/code` (트랙 브랜치 `track/칼카피숏템엔진` 의 **커밋된** 코드만. 엔진 커밋이 바뀌면 워커가 스스로 따라가 다시 읽는다)
- 데이터: `C:/숏템_칼카피/창고` (`CALCOPY_DATA_DIR`) — 창고 DB `calcopy/topics.db`, 장부 `calcopy/worker_ledger.jsonl`, 로그 `worker_<채널>.log`
- 채널·카테고리·검색 명사·단계 = `warehouse_channels.json` 한 곳(만들기 입구도 같은 파일)
- `worker.py` 자체를 고쳤으면 `stop` → `start` 로 다시 띄운다(따라가기·재로드는 엔진·worker_steps·장부만)

## 한도 (판정 = `worker_ledger.take` 한 곳)

| 항목 | 한도 |
|---|---|
| 제미나이 | 워커당 시간당 10회 (`GEMINI_PER_HOUR`) |
| 유튜브 조회 | 4워커 합 시간당 300편 (`YT_PER_HOUR`), 실제 온 편수만 셈 |
| 429·쿼터 | 그 워커 30분 쉼 (장부 `pause`) |
| 엔진(topic_find·script_engine) 커밋 바뀜 | scored 소재를 benched 로 되돌려 새 엔진으로 재점수 |

넘으면 이유가 장부 `limit` 줄과 보드 워커 칸에 남는다(조용히 넘어가지 않음).

## KPI 보기

```
CALCOPY_DATA_DIR=C:/숏템_칼카피/창고 py tools/calcopy/engine/worker_ledger.py --hours 1
```
`kpi` = 시간당 새 후보 · 단계별 통과율(ok / ok+error) · 제미나이·유튜브 시간당 · 한도 · 429.
같은 값이 `/api/admin/calcopy/workers/kpi?hours=1` 과 `/admin/calcopy` 엔진 탭에 뜬다.
