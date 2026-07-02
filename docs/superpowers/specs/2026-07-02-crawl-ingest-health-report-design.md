# 크롤·인제스트 텔레그램 헬스리포트 (2026-07-02)

## 배경

`scripts/slot_ingest.py`는 Task Scheduler(`LottoStock_SlotIngest_Main`: 08/12/15/18/21시,
`LottoStock_SlotIngest_Report`: 08/11시)에 의해 하루 7회 실행되며, 매 실행 후
`send_report()`가 텔레그램으로 "신규 원자 N개" 요약을 보낸다.

2026-07-02, PC가 밤새 절전 상태였다가 늦게 깨어나면서 Task Scheduler가 놓친 슬롯을
1회만 캐치업 실행했고, 그 결과 텔레그램/유튜브 원자가 하루 이상 비어있는 상태로
대시보드에 노출된 사고가 있었다(원인 조사·수동 복구 완료, 웨이크업 이벤트 트리거는
이미 추가함 — OS 레벨 조치이며 이 스펙 범위 밖).

기존 `send_report()`는 단순 숫자 나열이라 이런 이상 상태를 리포트에서 알아채기
어려웠다. 이번 스펙은 **매 슬롯 리포트 자체에 문제 감지 + 자동 재시도 + 결과를
표 형태로** 넣어서, 사용자가 텔레그램만 보고도 "오늘 크롤·인제스트가 정상인지"를
바로 판단할 수 있게 한다.

## 목표

- 기존 발송 빈도(하루 7회, 기존 Task Scheduler 트리거) 유지
- 표는 "오늘 누적(+이번 슬롯 신규)" 형식 — 슬롯이 진행될수록 표가 자라나는
  이어붙이기 방식(기존 대시보드 소스라이브러리 배지 표기 관습과 통일)
- 원본은 크롤됐는데 원자가 안 만들어진 경우(=버그) 를 감지해 자동 재시도 1회
- 재시도로 안 풀리는 문제만 "확인 필요"로 사용자에게 눈에 띄게 표시
- 조용한 뉴스데이(원본 자체가 적어서 원자도 적은 정상 상황)를 오탐하지 않음

## 범위 밖

- Task Scheduler 슬롯 자체 누락 감지(오늘 이미 웨이크업 트리거로 별도 해결됨)
- 채널별(텔레그램 12개 채널 개별) 세분화된 실패 리포트 — 카테고리(텔레그램/유튜브/
  블로그/리포트) 단위까지만
- 텔레그램 메시지 편집(edit) 방식 — 매번 새 메시지 발송

## 발송 채널

기존 브리핑·알림용 봇(`BOT_TOKEN`/`CHAT_ID`)과 분리된 **업무보고 전용 봇**으로 발송.
`.env`에 `OPS_BOT_TOKEN`/`OPS_CHAT_ID` 추가 완료(t.me/parklotto13bot, chat_id는 기존과
동일한 개인 계정 2121641255). `_send_tg()`를 그대로 재사용하지 않고, 이 리포트 전용
발송 함수(`_send_ops_tg()`)를 새로 만들어 `OPS_BOT_TOKEN`/`OPS_CHAT_ID`를 읽도록 한다
(기존 `_send_tg()`는 다른 스크립트에서 계속 `BOT_TOKEN`/`CHAT_ID`로 쓰이므로 건드리지
않음).

## 아키텍처

`scripts/slot_ingest.py` 내부에서 처리, 새 파일 추가 없음.

```
main()
 └─ ingest_cat(cat, date, extra_date)   # 기존 함수, subprocess 캡처하도록 수정
      └─ run() 이 subprocess stdout/stderr를 캡처 + 그대로 print (기존 가시성 유지)
 └─ diagnose(cat, output_text, since_iso)   # 신규
      ├─ _extract_pending(text) -> int          # "미처리 {cat}: N개" 정규식
      ├─ _extract_error(text) -> str|None       # 에러 시그니처 매칭
      ├─ _atoms_count(source_type, since_ts) -> int   # DB 델타 조회 (기존 로직 재사용)
      └─ 판정 후 필요시 ingest_cat() 1회 재호출(재시도)
 └─ build_report(cats, date)   # 신규 — 카테고리별 diagnose 결과 취합해 표 문자열 생성
 └─ _send_tg(build_report(...))   # 기존 발송 함수 그대로 사용
```

### 판정 로직 (카테고리 1개당)

1. `pending = _extract_pending(첫 실행 출력)`
2. `atoms_delta = _atoms_count(source_type, since_iso)` (이번 슬롯에서 새로 쌓인 원자 수)
3. `error = _extract_error(출력)`
4. 분기:
   - `error is not None` 이거나 (`pending > 0 and atoms_delta == 0`)
     → 🔴 **문제** → `ingest_cat()` 1회 재시도 → 재시도 후 `atoms_delta_retry` 재조회
       - `atoms_delta_retry > 0` 이고 재시도 출력에 에러 없음 → ✅ "재시도로 해결" (재시도분 포함해 표시)
       - 아니면 → 🔴 "확인 필요" + 에러 메시지 요약(있으면) 리포트에 포함
   - `atoms_delta > 0` 이고 `atoms_delta < trailing_avg * 0.3` (trailing_avg = 최근 7일
     동일 source_type 일평균, DB 조회) → ⚠️ "급감" (재시도 안 함, 표시만)
   - 그 외(원본 자체가 없어서 신규 0인 정상 상황 포함) → ✅ 정상

재시도는 슬롯당 카테고리별 최대 1회. 재시도가 실패해도 같은 슬롯에서 반복하지 않음
(다음 슬롯에서 다시 자연스럽게 시도됨).

### 표 형식

`<pre>` 블록, 한글 폭(동아시아 넓은 문자)을 2칸으로 계산하는 패딩 헬퍼 사용.
표시값은 "오늘 누적(+이번 슬롯 신규)": 누적은 `SELECT COUNT(*) FROM atoms WHERE
source_type=? AND date=오늘`, 신규는 위 `atoms_delta`(재시도 성공분 포함).

```
📥 크롤 인제스트  07-02 15:10
카테고리    오늘누적    상태
──────────────────────────
텔레그램   45(+12)   ✅ 정상
유튜브      9(+0)    ✅ 정상
블로그      7(+3)    ✅ 정상
리포트     46(+0)    🔴 확인필요

🔴 확인 필요 1건
· 리포트: 원본 3건 크롤됐으나 원자 0건, 재시도도 실패
  → Gemini 키 소진(429) 추정 — 키 확인 부탁
```

문제/경고가 하나도 없으면 하단 섹션(🔴/⚠️ 목록) 자체를 생략.

## 에러 처리

- `run()`이 subprocess 출력을 캡처하지 못하는 경우(타임아웃 등) → 해당 카테고리는
  판정 불가로 처리하고 표에 "❔ 확인불가"로 표시(문제로 오인해 재시도 폭주하지 않도록).
- DB 조회 실패(atoms.db 잠금 등) → 해당 슬롯 리포트 발송을 건너뛰지 않고, 표 대신
  "⚠️ DB 조회 실패, 다음 슬롯에서 재확인" 텍스트만 발송.
- 텔레그램 발송 자체 실패(`_send_tg` 기존 로직) → 콘솔에만 로그, 파이프라인은 계속
  진행(원자 인제스트 자체는 리포트 발송 성공 여부와 무관하게 완료돼야 함).

## 테스트

`tests/test_slot_ingest_report.py` 신규 — subprocess/DB 없이 순수 로직만 검증:
- 패딩 헬퍼: 한글/영문 혼합 문자열 폭 계산이 의도한 정렬을 만드는지
- `_extract_pending`: 정상 패턴/패턴 없음/개수 0 케이스
- `_extract_error`: 각 에러 시그니처 매칭 + 정상 로그에서 오탐 없음
- 판정 로직(`diagnose`의 순수 부분): pending/atoms_delta/error 조합별 기대 상태값
  (✅/⚠️/🔴) 표 기반 파라미터라이즈드 테스트

## 롤아웃

Task Scheduler 트리거 변경 없음(기존 7회 그대로). 코드 배포 후 다음 슬롯부터 자동 적용.
