# 관제(管制) — 모든 요청은 여기서 시작하고, 라이브 실물 숫자로만 닫힌다

설계: `docs/superpowers/specs/2026-09-27-관제시스템-design.md` · 시작: 2026-09-28 (사장님 "매우 중요하니까 시작해")

## 원칙 3줄

1. **모든 시작은 관제 등록에서.** 카드 없는 트랙·finish 는 없다 — `track.py` 가 막는다.
2. **수리는 뿌리다.** "이 판단이 몇 벌인가·주인이 어디인가"를 먼저 정하고 그 한 곳을 고친다. 주인 밖에 같은 판단을 새로 적으면 `finish` 가 막는다(`관제/ownership.json`).
3. **"됐다" = 라이브 실물 숫자가 카드의 '됐다의 기준'을 채운 상태.** 그 전 이름은 "진행 중 / 반영됨·미검증".

## 파일

| 파일 | 무엇 | 누가 고치나 |
|---|---|---|
| `cards/<번호>-<제목>.md` | 카드 = 요청 하나. 머리 블록(`- 키: 값`)은 기계가 읽는다 | `py tools/control.py …` (손으로 고쳐도 되지만 **origin/main 에서만** — 트랙 폴더 사본은 낡는다) |
| `BOARD.md` | 상태별 보드 | **자동 생성** — 손대지 마라 |
| `ownership.json` | 판단 소유권 지도(주인 함수·시그니처·소비처·예외) | 판단을 새로 만들거나 두 벌을 줄였을 때. 예외는 사유 + 카드 번호 필수 |
| `rules.json` | 승인 표식 규칙(고객 화면·과금·고객 데이터) | 거의 안 바뀜 |
| `claims.json` | 트랙 간 선점 신고 | `py tools/track.py claim <트랙> <카드> <파일|파일:함수>` |

사람이 읽는 소유권 표: `wiki/rules/판단소유권.md` (`py tools/ownership_check.py render` 로 생성 — 두 벌로 적지 않는다).

## 흐름

```
① 등록   py tools/control.py new "제목" --from <제보자> --owner <파일:함수> --done "<됐다의 기준(숫자·도구)>" [--body 원문]
② 트랙   py tools/track.py start <트랙> --card <번호>        ← 카드 없으면 거절
③ 수리   (트랙 폴더에서) 커밋 메시지에 [관제 N] 을 적어도 연결된다
④ 승인   고객 화면(static/*.html|js) 변경 → 관문 통과면 **관제 자동 승인**(카드에 근거 기록)
         돈(과금 함수)·회원 데이터 쓰기 → 사장님 승인(카드 만들 때 먼저 말한다) py tools/control.py approve <번호> "사장님 구두 …"
⑤ 병합   py tools/track.py finish <트랙>
         관제 관문 = 카드 있나 → 승인 필요한가 → 다른 트랙 선점과 겹치나(경고) → 주인 밖 시그니처 새로 생겼나(거절)
         통과·push 뒤 카드에 "병합 <sha> (반영됨·미검증)" 이 자동으로 적힌다
⑥ 실측   반영 뒤 실제 job 에 검사 도구를 돌려 숫자를 카드에 적는다
         py tools/control.py set <번호> "라이브 실측" "2026-.. 도구 X: 다른 장면 0 …"  → status 완료
```

상태: `등록 → 분배 → 수리 → 로컬검증 → 병합 → 서버반영 → 라이브실측 → 완료` / 예외 `승인대기` · `회귀`

## 영향 지도 — 카드 002

주인 함수를 고치면 어디까지 번지는지 도구가 센다. 판단 주인 `tools/impact.py:consumers`.

```
py tools/impact.py spec render_cut_plan        # 수리 명세서: 소비처 파일 N · 결과물 노드 · 다시 재야 할 검사 · 승인
py tools/impact.py template render_cut_plan    # 카드에 붙일 '영향 없음: <파일> — <이유>' 줄 틀
py tools/impact.py diff                        # 지금 워킹트리 변경이 어떤 주인 함수를 건드렸나
```
finish 관문 ⑤: 주인 함수(ownership.json 의 `주인`)가 바뀐 병합은 소비처 파일이 **diff 에 있거나** 카드에 `영향 없음: <파일> — 이유` 가 있어야 통과.
새 소비처(주인 함수를 새로 부르는 파일)가 생기면 지도 갱신을 요구하는 줄이 찍힌다.

## 관리자 화면 보드·승인 — 카드 004

관리자 페이지(admin.html) `🎛 관제 보드` 상자: 카드를 상태별 표로, 승인이 필요한 카드엔 [승인] 버튼. 버튼은 서버 `data/control_approvals.json` 에 적히고(서버는 git 을 못 고친다), 로컬 `finish` 가 ssh 로 읽어 카드 '승인' 칸으로 옮긴다. 정본은 여전히 git 카드.

## 라이브 실측 — 카드 003

병합 뒤 실제 고객 작업으로 결과물 검사 4층(영상·소리·자막·캡컷)을 서버에서 돌려 숫자를 카드에 붙인다. 판정은 `video_gate.judge` 한 곳(매일 점검 도구 `daily_video_audit.py --dry-run` 을 그대로 부른다).

```
py tools/live_check.py --card 23 [--jobs 4]     # 그 카드의 병합 시각 이후 작업으로 실측 → 카드 '라이브 실측' 칸 + 상태(라이브실측/회귀)
py tools/live_check.py --all                    # 상태가 병합·서버반영 이고 병합 10분 지난 카드 전부
py tools/live_check.py --card 23 --no-write     # 찍기만
```
대상 작업이 0이면 상태는 그대로 두고 "대상 없음"만 이력에 남긴다. SSH 가 안 되면 실패로 끝난다 — 실측 없이 '됐다'로 만들지 않는다.

## 저장 층(C/D) — 카드 023

SSD(C)에는 **코드가 도는 것만**(활성 트랙·DB·병합 임시), 나머지는 외장 HDD(D:\숏템). 지도 `storage.json`, 판단 주인 `tools/storage.py:plan`.
실측: D 는 큰 파일 124MB/s 지만 작은 파일은 C 의 1/10 속도 — 그래서 7일 안 손댄 트랙은 C 에 둔다.

```
py tools/storage.py status                 # C/D 여유·죽은 정션·D 에 있는 트랙·소비 상위
py tools/storage.py plan                   # 지금 D 로 보낼 것 + GB (실행 없음)
py tools/storage.py apply --auto           # 7일+ 트랙 → D(폴더 이동 + C 정션) · 끊긴 병합 잔해 삭제 · out/ 30일+ → D
py tools/storage.py apply --research       # research/ → D, C 에는 정션
py tools/storage.py warm <트랙>            # D 에 있는 트랙을 C 로 되돌린다(다시 일할 때 — 느리면 이걸)
py tools/storage.py schedule               # 작업 스케줄러에 매일 04:40 --auto 등록
```
`apply` 는 D:\숏템 과 `_저장규칙.txt` 가 보일 때만 돈다. D 를 뽑으면 정션이 죽는다 — `status` 가 빨강으로 알린다.

## 아직 없는 것 (카드로 등록됨)

- 영향 지도 `tools/impact.py`(호출 그래프 → 수리 명세서, finish 가 diff 와 대조)
- 라이브 실측 `tools/live_check.py --card N` + 관리자 버튼 + 반영 뒤 자동 1회 실측
- 관리자 페이지 보드 탭(지금은 이 폴더의 BOARD.md)
- 트랙 대청소(닫기 기준 확정 뒤 실행 — 사장님 승인)
