# 핸드오프 — 렌즈CN통합 트랙

> **소유 트랙**: 렌즈CN통합 — 이 파일은 이 트랙 세션만 수정한다. 다른 트랙은 읽기만.
> 트리거: "렌즈CN통합 이어서"

두 세션(`CN검색통합` = 에피파이 붙이기 / `렌즈지연` = SerpApi)을 합류시킨 트랙이다.
각 트랙의 상세 기록은 `handoff/CN검색통합.md` · `handoff/렌즈지연.md`에 그대로 있다 — **지우지 마라**.

---

## 2026-08-17 (회사PC) — 합류 + SerpApi 실잔량 가드

### 먼저 확인한 것 — 두 작업은 이미 둘 다 main에 있었다

`git merge-base --is-ancestor origin/track/CN검색통합 origin/main` → **이미 포함**.
`렌즈지연`도 미병합 0. 즉 "합치는" 코드 작업은 필요 없었고, **남은 건 검증과 후속**이었다.

### ✅ CN검색통합의 유일한 미검증 게이트 — 서버 실측 통과

핸드오프가 "로컬엔 세션·Apify 키가 없어 배선만 검증했다"고 남겨둔 그 항목이다.

```
COUNT 16
META {'xiaohongshu': {'backend': 'pw_xiaohongshu', 'n': 8, 'cost_usd': 0},
      'douyin':      {'backend': 'apify_douyin',   'n': 8, 'cost_usd': 0.04005}}
```

기대치와 **정확히 일치** → 샤오홍슈 세션 살아있음(`apify_xiaohongshu`로 떨어지면 세션 사망 신호).

⚠️ **서버에서 이 검증을 재현할 때 `sudo`를 쓰지 마라.** 핸드오프에 적힌 명령은
`sudo /usr/bin/python3`인데 그러면 `ModuleNotFoundError: openpyxl`로 죽는다 —
의존성이 `/home/ubuntu/.local/lib/python3.12/site-packages`에 있어 root가 못 본다.
`/etc/shopping-shorts.env`는 그룹 `ubuntu`에 읽기권한이 있으니 **그냥 ubuntu로** 돌리면 된다:

```bash
cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && python3 -c '...'
```

### ✅ 렌즈지연 1순위 — "카운터가 실소진과 어긋난다"를 수치로 확정하고 고쳤다

서버 실측(2026-08-17):

| | 값 |
|---|---|
| 우리 `lens_count` | **196 / 500** (39% 썼다고 믿음) |
| 실제 SerpApi | **369 / 500** 소진 (키1 250/250 **소진** · 키2 119/250) |
| 남은 실잔량 | **131회 ≈ 43클릭** |

우리 가드는 앞으로 **304클릭을 더 허용**하는데 실제로는 43클릭 뒤 키가 전부 죽는다.
그때 렌즈는 "한도 초과" 안내도 없이 **조용히 빈손**이 된다. 어긋나는 이유는 단순하다 —
카운터는 클릭당 1인데 실제로는 **로케일 3벌 × 재시도로 최대 3회**가 나간다.

**고친 것** (커밋 `4746cf8d3` → main 병합):

- `lens_discover.account_searches_left()` — 모든 키의 `total_searches_left` 합,
  TTL 캐시(기본 600초, `LENS_QUOTA_TTL`). 렌즈 호출마다 왕복을 더하지 않는다.
  - ★**한 키도 못 읽으면 `None`(=모른다)이지 0이 아니다.** 잔량을 못 읽었다고
    렌즈를 막아버리면 더 나쁘다 → 호출부가 기존 상수 방식으로 폴백한다.
  - 문자열·`None`을 `int`로 뭉개 0을 만들지 않는다(테스트로 고정).
- `app._lens_quota_guard(store, month)` — `/api/lens/search`와 `/api/lens/trace_url`
  **두 곳에 따로 적혀 있던 같은 판정**을 한 함수로(0순위-B). 실잔량 우선 → 못 읽으면 카운터.

**검증**: 신규 테스트 10개(네트워크 안 탐). **되돌리기 확인** — 실잔량 분기를 없애고
`None`을 `0`으로 바꿔보니 각각 빨간불(3 failed) → 복원하면 10 green. 가짜 green 아니다.
렌즈+CN 관련 전체 175 passed / 0 failed.

### ⚠️ 게이트가 한 번 막았는데, 내 변경 때문이 아니었다 (판정 기록)

첫 `finish`가 2건으로 막혔다. 세 번 돌려보니 **실패 조합이 매번 달랐다**:

| 실행 | 실패 |
|---|---|
| 게이트(트랙) | `mix_pipeline` + `product_prefetch` |
| 트랙 전체 스위트 | `edit_plan_build` + `product_prefetch` |
| **main 기준선(내 변경 0)** | `app_lens::test_lens_cn_search_no_tokens` + `edit_plan_build` |

공통은 **알려진 기준선 실패 `edit_plan_build` 하나뿐**이고, 나머지는 매번 다른 테스트다.
**내 변경이 하나도 없는 main에서도 2건이 깨진다** → 무관 확정.
`pytest-randomly`는 설치돼 있지 않으니 순서 문제도 아니다. main 전체 스위트가
**28분 45초**(평소 4분)나 걸린 걸 보면 **다른 세션과의 CPU 경쟁에 따른 타이밍 flaky**로 보인다.

> 교훈: 게이트가 막았을 때 **바로 코드를 고치러 가지 마라.** 단독 실행 → 조합 실행 →
> main 기준선 순으로 갈라야 "내 것이냐"가 갈린다. 여기선 단독·조합 모두 통과였다.

재-`finish` 통과 → main 병합·push 완료.

---

## ⏭ 다음 할 일

### 🔴 사장님 몫

- [ ] **`SERPAPI_KEY_3` 서버 env 추가.** 실잔량 **131회 ≈ 43클릭**밖에 안 남았다.
      코드가 키 개수로 자동 스케일하므로 **env에 한 줄만** 넣으면 된다.
      이제 잔량은 상수가 아니라 **실제로 읽으니** 키를 넣는 즉시 반영된다.
- [ ] **죽은 Apify 토큰 정리 승인** — 17개 중 6개가 401 무효, 6개 중복
      (목록은 `handoff/CN검색통합.md`). 무효 토큰이 로테이션 앞쪽에 있으면
      매 검색마다 헛때려 느려진다. ⚠️ `/etc/shopping-shorts.env` 변경은 git에 안 남으니
      건드리면 반드시 거기에 적을 것.

### 🟡 다음 세션

- [ ] **재시도 낭비** — 빈 결과 시 `_MAX_ATTEMPTS`(3)까지 때린다. 2회로 줄이면 소진이 준다.
      이제 실잔량이 보이니 **줄이기 전후를 실측으로 비교**할 수 있다.
- [ ] `lens_count` 카운터 자체는 남겨뒀다 — 실잔량을 못 읽을 때의 폴백이라 필요하다.
      다만 **화면에 보이는 숫자**가 어느 쪽인지 확인 안 했다(미확인 항목).
- [ ] 도우인은 세션이 없어 **항상 Apify**($0.04/회). QR 로그인 실패(+82 SMS 거부).
      세션이 생기면 `_CHAIN` 무수정으로 자동 $0이 된다.

## 참고

- 관련 트랙: `CN검색통합` · `렌즈지연` · `렌즈인스타정보` · `렌즈CN검색`
- 코드: `shopping_shorts/lens_discover.py`(`account_searches_left`) ·
  `shopping_shorts/app.py`(`_lens_quota_guard`) · `shopping_shorts/cn_search.py`(`_CHAIN`)
- 테스트: `shopping_shorts/tests/test_lens_quota_real.py`
