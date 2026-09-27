# PC등록해제 — 관리자가 등록 PC를 골라서 푼다

## 2026-09-15 (CH PC) — 완료·병합

사장님 요청 발단: **박복래 회원(체험단 15명 중 1명, 네이버 메일)이 PC 2대 중 1대를
삭제해 달라고 했다** → 확인해 보니 관리자 화면은 **전부 해제만** 됐다.

### 무엇이 문제였나

- 계정당 PC 2대 상한 (`store.py` `Store.PC_SLOTS = 2`)
- API `/api/admin/customer/device_reset` 는 **처음부터 `slot` 을 받았다**
  (`store.device_reset(cid, slot)` 도 칸 단위 삭제를 지원)
- 그런데 **`admin.html` 이 `slot` 을 안 보냈다** → 기능이 반쯤 있다가 배선만 빠진 상태
- 전부 해제를 쓰면 멀쩡한 PC까지 재등록해야 한다 — 등록은 **회원이 마이페이지에서
  직접** 눌러야 하므로(자동등록은 2026-08-31 사고로 제거됨) 그만큼 번거롭다

### 고친 것

| 파일 | 내용 |
|---|---|
| `shopping_shorts/static/admin.html` | 🖥 클릭 → PC 목록 보여주고 **해제할 번호 입력**(0=전부, 취소=무동작). 고른 번호를 `body.slot` 으로 전송. 응답을 보고 성공/실패를 말한다 |
| `shopping_shorts/app.py` | `slot` 검증(비숫자 400 / 범위밖 400 / 미등록 404) + 응답에 `removed`·`left` |
| `shopping_shorts/tests/test_pc_device_gate.py` | 회귀 가드 7개 추가 (24 passed) |

**곁에서 같이 고친 버그** — `loadCustomers` 는 `admin.html` 에 **존재하지 않는 함수**였다.
`typeof loadCustomers==='function'` 방어에 걸려 조용히 아무것도 안 했고, 그래서
**PC 해제·결제기간 설정 후 화면이 갱신되지 않았다**(호출부 2곳). 실제 이름은
`load()` + `renderCustomers()`. 갱신을 정하는 곳을 `refreshCustomers()` **한 곳**으로
뽑았다(0순위-B).

### 실측 (0순위-A1)

- 로컬 서버(8772) + **실제 브라우저 클릭** 12항목 PASS
  → 1번만 해제하면 DB에 2번만 남고 쓰던 PC의 `device_id` 가 보존된다
  → 취소·빈칸·없는번호는 DB 무변화 / `0` 은 전부해제 / 0대일 때 안내 / JS 오류 0
- 배지 자동갱신 4항목 PASS → 해제 후 **새로고침 없이** 🖥2 → 🖥1
- `pytest test_pc_device_gate.py` **24 passed**
- ★**사보타주 검증**: `body.slot = Number(ans)` 를 지우면 1건 FAIL,
  백엔드 검증을 지우면 3건 FAIL → 테스트가 실제로 계약을 잡는다. 원복 후 24 passed 재확인

### 쓰는 법 (사장님)

1. 관리페이지 → 회원관리에서 그 회원 줄의 **🖥N** 을 누른다
2. 등록된 PC 목록(번호·마지막 접속시각·브라우저)이 뜬다
3. **지울 PC 번호를 입력** → 확인 → 그 칸만 빠진다. 나머지 PC는 그대로 쓴다
4. 전부 지우려면 `0`

### ⏭ 다음 (미결)

- **박복래님 실제 처리는 아직 안 했다.** 라이브 DB 조회가 이 세션에서 막혀
  (자동승인 모드 `[Production Reads]`) **어느 PC가 안 쓰는 것인지 못 봤다**.
  → 배포 후 관리페이지에서 🖥 를 눌러 두 PC의 **마지막 접속시각·브라우저**를 보고
    안 쓰는 번호를 고르면 된다. 판단은 사장님 몫(어느 PC를 버릴지는 회원 사정).
- 개선 여지(사장님이 원하면): 지금은 `prompt` 로 번호를 받는다 — 이 파일 전체가
  `alert/confirm/prompt` 관례라 맞췄다. 슬롯별 버튼이 있는 커스텀 모달로 바꾸면
  더 편하지만 파일 관례를 깨고 검증 범위가 커진다.

## 2026-09-25 (CH PC) — 이윤정 PC 2칸 전부 해제 (완료)

- 사장님: "이윤정님 pc 2개 가득찬거 리셋좀해줘"
- 라이브 `reference.db` 조회: 이윤정 = id **505** (irene24754947@gmail.com, 09-10 가입, 승인됨).
  slot 1(ip 58.29.190.153, 마지막 09-25) · slot 2(ip 14.5.241.56, 마지막 09-23) 둘 다 Chrome/Win.
- 서버에서 앱 코드 그대로 `Store(DB_PATH).device_reset(505, None)` → before 2건 / after 0건.
- 회원은 **마이페이지에서 PC를 다시 등록**해야 한다(자동등록 없음).
- 함정: 서버에 `sqlite3` CLI가 없다 → `python3 -c "import sqlite3..."`로 조회.

### 관련 파일

- `shopping_shorts/store.py:6360` `PC_SLOTS = 2` (늘리려면 여기 한 곳)
- `shopping_shorts/store.py:6396` `device_register` — 회원이 직접 누를 때만 등록
- `shopping_shorts/store.py:6442` `device_reset(cid, slot)`
- `shopping_shorts/app.py:13983` 해제 API
- `shopping_shorts/static/admin.html:433` `refreshCustomers()` / `:470` 🖥 핸들러
- 게이트 본체: `shopping_shorts/app.py:12532~` (`_DEVICE_COOKIE = "ss_pc"`, 2년)
- 회원 기기 테이블: `customer_devices(customer_id, slot, device_id, first_seen, last_seen, ua, ip)`

### 함정 메모

- 🖥 배지는 `renderCustomers()` 가 그리는데 **`acked_at != null` 인 회원만** 그린다
  — 검증용 회원을 심을 때 승인 상태로 안 만들면 배지가 안 보여 "기능이 안 된다"고 오판한다
- 로컬은 `DASH_PASS` 미설정이면 **전원 admin** → 권한 테스트는
  `monkeypatch.setattr(app_mod, "_AUTH_ON", True)` 로 켜야 한다(`setenv` 로는 안 켜진다)
- 권한 테스트에서 일반 회원은 `_require_admin` 전에 **402(유료 게이트)** 가 먼저 걸린다
  — 그래서 관리자 판정은 `_is_admin()` 을 직접 재서 갈라 확인했다
- Playwright **MCP** 는 다이얼로그를 자체 모달 상태로 가로채 `page.on('dialog')` 와
  경합한다 → 독립 스크립트(`sync_playwright`)로 검증했다
