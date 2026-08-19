> **소유 트랙**: CN검색통합 — 이 파일은 이 트랙 세션만 수정한다. 다른 트랙은 읽기만.
> 트리거: "CN검색통합 이어서"

## CN 검색 통합 파서 — 2026-08-17 (구현 완료, 서버 실측 대기)

사장님 요구: **"뭐는 에피파이고 뭐는 프록시고 이런거 없고 한번에 다 되게 설계하고 파서 만들어야대"**
+ 렌즈 후보 버튼이 **외부 사이트로 나가지 말고 우리 페이지 안에 카드로**.

### 무엇을 만들었나

```
cn_search.search(keyword, max_results)     ← 호출부는 이것만 안다
   ├ 샤오홍슈: pw_xiaohongshu(무료) → apify_xiaohongshu($0.098)
   └ 도우인  : pw_douyin(무료)      → apify_douyin($0.04005)
```

**폴백 = A안: 0건이면 다음 백엔드로.** 예외뿐 아니라 빈손도 폴백 사유다.
근거: Apify 무료한도는 계정당 월 $5인데 **이월 안 됨**(안 쓰면 소멸). 4계정 = 월 약 500회.
돈 아끼려다 사장님이 결과를 못 보는 쪽이 더 비싼 손해다.

**★백엔드 순서는 `cn_search._CHAIN` 한 곳에서만 정한다**(0순위-B). 도우인 세션이 생기면
`pw_douyin`이 성공하기 시작해 자동으로 $0이 된다 — **_CHAIN·엔드포인트·프론트 전부 무수정**.

### 커밋 (트랙 브랜치, 7개)

| SHA | 내용 |
|---|---|
| `d97dba1e2` | 공통 스키마 `normalize` |
| `5ec1ba22f` | fix: `_num`이 OverflowError(inf)에 안 죽게 |
| `e9ef51ca5` | Apify 백엔드 2종 |
| `1f2ffb781` | 샤오홍슈 Playwright(무료) |
| `589a17d70` | 도우인 Playwright(CN프록시+세션 짝) |
| `820055cb0` | 사슬 + 0건 폴백 |
| `c1bf444fe` | `/api/lens/cn/search` 교체 |
| `a8260c08b` | 프론트 인앱 카드 |

로컬 테스트 **21 passed**. 회귀: 1 failed / 3777 passed (그 1건은 `test_edit_plan_build.py`의
기존 cp949 이슈로 `cn_search` 참조 0건 = 무관). 기준선(main 12 failed)보다 안 늘었다.

### 구현 중 잡은 버그 3건 (전부 실행으로 발견, 추측 아님)

1. **`_num`이 `inf`에 크래시** — `float('inf')`는 ValueError가 아니라 **OverflowError**라
   `except (TypeError, ValueError)`가 못 잡았다. `normalize`는 행마다 불리므로 값 하나가
   `inf`면 **그 백엔드 결과가 통째로 죽는다**(모듈 계약 위반). JSON 파서가 `Infinity`를
   기본 허용하니 실제로 들어올 수 있다.
2. **`_apify`의 normalize가 try 밖** — 백엔드가 `[None]` 같은 행을 뱉으면 `AttributeError`가
   밖으로 샜다. 계약("백엔드는 예외를 안 던진다") 위반.
3. **프론트 `zh` 미이스케이프** — 설계서엔 "이미 `&quot;`로 이스케이프됨"이라 적었지만
   **실제 코드는 raw 보간**이었다(`${c.zh||''}`). onclick에 그대로 넣으면 중국어에 따옴표가
   섞일 때 2026-07-19 사고가 재발한다. → **인덱스를 넘기고 `st.cnCands[idx].zh`를 안에서
   조회**하는 방식으로 회피(이 코드베이스가 onclick에 ID만 넘기는 관례와도 일치).

### ⏭ 다음 (서버 실측 = 진짜 게이트)

로컬엔 세션·Apify 키가 없어 **배선만 검증**했다. 브라우저 경로는 서버에서만 확인된다.

```bash
ssh -i "C:/Users/CH/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem" ubuntu@43.200.48.69 \
  "cd /home/ubuntu/lotto-stock-wiki && sudo bash -c 'set -a; . /etc/shopping-shorts.env; set +a; /usr/bin/python3 -c \"
import sys; sys.path.insert(0,\\\"/home/ubuntu/lotto-stock-wiki\\\")
from shopping_shorts import cn_search
r=cn_search.search(\\\"蒜泥保存\\\", 8); print(r[\\\"count\\\"], r[\\\"meta\\\"])\"'"
```

기대(2026-08-17 실측 기준): 샤오홍슈 `backend=pw_xiaohongshu, cost_usd=0, n≥8` /
도우인 `backend=apify_douyin, cost_usd=0.04, n≥8`.

⚠️ **샤오홍슈가 `apify_xiaohongshu`로 나오면 세션이 죽은 것**이다(쿠키 재추출 필요).
판정은 문자열이 아니라 **이 meta**로 한다.

화면 확인: shoppingshorts.duckdns.org → 렌즈 → 후보 행 `📕🎬 여기서 찾기` →
**페이지를 안 떠나고** 카드가 합류하는가.

### ⏭ 별건 — 죽은 Apify 토큰 정리 (사장님 확인 후)

17개 중 **6개가 401 무효, 6개가 중복**(2026-08-17 실행 검증). 무효 토큰이 로테이션 앞쪽에
있으면 매 검색마다 헛때려 느려지고 원인이 숨는다.

- 401 무효: `…1vUZQD` `…0bKVDt` `…4DpAJV` `…2lBaDI` `…21MkD4` `…1HSxOh`
- 살아있음(실행 검증 통과, 각 12건 반환): `…4DT6FN` `…4w7hFQ` `…3VmSdD` `…0liNLo`
- `…1atbro`는 한도소진($5 초과)이나 **09-08 리셋**되므로 남긴다

⚠️ 서버 `/etc/shopping-shorts.env` 변경은 **git에 안 남는다** — 하면 반드시 여기 적을 것.

### 알려진 갭 (지금은 안 고침, YAGNI)

- `"1.2만"` 같은 중국어/한국어 축약 숫자 → `_num`이 `None`으로 버린다. 좋아요 수가 화면에서
  **빈칸**이 된다. 틀린 값을 지어내지 않으니 안전하지만, 정보 손실이라 나중에 파서 추가 여지.
- 음수 duration 그대로 통과 / non-dict `row` 가드 없음 / url·title 문자열 타입 미검증
- 도우인은 세션이 없어 **항상 Apify**. QR 로그인 실패(+82 번호는 SMS 거부).
