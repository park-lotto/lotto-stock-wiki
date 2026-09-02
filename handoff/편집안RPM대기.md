# 편집안RPM대기 — 편집안(EDL) 429 분당한도 대기 재시도

## 2026-08-31 (마감)

### 사고
운영사고 "편집안(EDL)을 만들지 못했습니다 — 대본은 234자 뽑혔는데 편집안(EDL)이
비었습니다 [생성기=legacy]". code=plan_empty.

### 실측 원인 (서버 로그, job 498afe4046a3 / 13:28:01~02)
```
POST .../gemini-3.1-flash-lite:generateContent "HTTP/1.1 429 Too Many Requests"  x4 (0.7초)
edit_plan._vault_call: 키 4개를 다 돌았는데 결과 없음 — 429 RESOURCE_EXHAUSTED
  "Quota exceeded for quota metric 'Generate Content API requests per minute'"
[EDL빈원인] code=plan_empty sources=1 chars=234 generator='legacy'
```
- 429가 **분당(RPM)** 한도였다. 20여 초 쉬면 저절로 풀리는 것.
- 그런데 `_vault_call`은 429에 **대기가 없다** — `is_quota_error` → `continue`뿐.
  그때 살아있던 general 키가 4개뿐이라 0.7초 만에 전부 태우고 포기 → beats 0.
- 같은 시각 4건 실패(13:28:02 / 13:28:39 / 13:28:45 / 13:29:54).

### 고친 것 (커밋 fb830011c, main 병합·배포됨)
`shopping_shorts/edit_plan.py`
- 본체 → `_vault_call_once`, 마지막 사유를 모듈 전역 `_LAST_VAULT_ERR`에 남긴다.
- 새 `_vault_call` 래퍼: 사유가 **분당 한도일 때만** 22초 쉬고 최대 3라운드 재시도.
  일일 소진·403 계정차단은 종전대로 즉시 포기(무의미한 대기 금지).
- 판정 `_is_per_minute_quota()`: 429/RESOURCE_EXHAUSTED + "per minute" 계열.

### 검증(실측)
- 판정: RPM=True / 일일=False / 403=False
- RPM 3라운드째 성공 → 결과 반환(호출 3회) / 403 → 즉시 포기(호출 1회) / 계속 RPM → 3라운드로 종료
- pytest `-k "edit_plan or vault or key"` 471 passed, 2 skipped

### ⚠ 같이 발견한 것
- **서버 IP가 또 바뀌었다: 43.200.48.69 → 3.35.251.172** (shoppingshorts.duckdns.org 실측).
  CLAUDE.md·메모리의 옛 IP로 SSH하면 다른(죽은) 인스턴스에 붙는다.
- 사고 시점 general 라이브 키가 **4개**였다(지금은 10개). 왜 4개까지 줄었는지는 미조사.

### ⏭ 다음
- 라이브에서 429 재시도 로그(`분당 한도(429 RPM)로 키풀 전멸`)가 실제로 찍히는지 관측
- general 풀이 4개로 줄어든 경위 조사(일일소진 표시 오탐 가능성)
- CLAUDE.md의 서버 IP 갱신 여부 사장님 확인

---

## 2026-08-31 오후 — 고객 5명 제작 불가 사고 대응

### 증상
cid 57(김용덕)·193(김종룡)·109·168(이유준)·241(김데릭)이 제작 실패.
`EDL 비어있음(plan_empty)` 또는 `(extract_empty)`.

### 실측한 진짜 원인 (셋이 겹쳤다)
1. **회원 키가 제작에 안 쓰였다** — 합류가 `app.py @app.on_event("startup")`에만 걸려
   있고 워커는 FastAPI를 안 띄운다. 워커 유닛 `[keypool]` 로그 24시간 **0건**.
   회원 49개가 등록만 된 채 놀았다.
2. **사장님 키 6개가 죽어 있었다** — 401 `bound service account is deleted or disabled`
   (general[3~6]·ingest[4]·embed[4]). 실측으로 확인.
3. **전원이 keys[0]부터 쳤다** — `_vault_call(key_offset=0)` 기본값.

### ★진단 함정 — `extract_empty`는 사후 추측 라벨이다
김종룡 job은 `extract_empty`(대사 0자)로 떴지만 **실제 원인은 429+401**이었다.
`_edl_empty_reason`은 beats가 0이 된 **뒤에** 손에 있는 것(소스 글자수)만 보고
이름을 붙인다. 대사 없는 소스여도 확정 대본이 있으면 정상 제작된다(scene_desc로 매칭).
→ **EDL 실패는 라벨을 믿지 말고 그 시각 `_vault_call` 로그를 봐라.**
   (나는 이 라벨을 믿고 "대사 없는 영상이라 안 된다"고 사장님께 잘못 보고했다)

### 조치 (시각순)
- 14:47 키 소진 표시 리셋 → 라이브 10→21 (백업 /tmp/keystate.bak)
- 15:35 **회원 키 23개를 .env에 투입** → 사용가능 11→34개
        (49개 살아있음 확인. `GEMINI_API_KEY_1~30` 상한 때문에 23개만 들어감)
        백업 /home/ubuntu/env.bak2 · 목록 /tmp/allive.txt · 스크립트 /tmp/fixenv.py
- 15:42 워커 12개 재시작 → 키 분산 코드 가동

### 효과 (실측)
- cid 241 김데릭: 15:26·15:27·15:30 실패 → **15:35 성공**(ready_for_review)
- cid 57 김용덕: 6연속 실패 → **성공**(ready_for_review, job 5658f68dc267)

### 게이트 교훈 — 범인은 내 테스트였다
`test_byok_charge_wiring` 3건이 계속 깨졌다. 단독·부분조합은 전부 통과, 전체에서만 실패.
`test_vault_key_spread.py`를 빼니 **즉시 통과**. `_vault_call_once` 바꿔치기가
뒤에 도는 테스트에 샜다. 나는 "테스트 오염이 아니다"라고 두 번 잘못 판단했고,
`keypool`을 통째로 되돌리는 헛수고를 했다.
→ **게이트가 새 실패를 지목하면 내가 추가한 파일부터 빼고 돌려봐라(이분법이 제일 빠르다).**

### ⏭ 다음 (중요도순)
1. **워커 합류 배선 다시 얹기** — 커밋 `1ce6de3ae`에 보관(keypool.py + worker.py).
   지금은 손으로 .env에 넣어 때웠을 뿐, 신규 회원 키는 여전히 자동 합류 안 된다.
2. 분산 회귀 테스트를 오염 없는 방식으로 복원(전역·모듈속성 안 건드리게)
3. **죽은 사장님 키 6개 .env에서 제거** — 매번 시도해 시간을 버린다
4. `_MAX_KEYS_PER_GROUP=30` 상한 — 회원 키 26개가 상한에 걸려 못 들어갔다
5. `_edl_empty_reason`이 실패 시점의 `_vault_call` 사유를 함께 싣게 개선
   (라벨만 보고 오진하는 일을 구조적으로 막는다)
