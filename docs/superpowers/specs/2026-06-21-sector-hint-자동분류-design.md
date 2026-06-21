# 종목 섹터 자동분류 (sector_hint) — 설계

- **날짜**: 2026-06-21
- **배경**: 텔레그램 인제스트([[project_telegram_ingest]]) 후속 개선 1순위. 현재 stock_tips·
  insight 채널의 종목 원자는 **섹터가 "기타"로 고정**된다 (meta에 섹터가 없음). 외국주는
  `foreign_sector_map.json` 수동 매핑에만 의존해, 모르는 외국주는 코멘트가 손실된다.
  리포트 파이프라인의 `_guess_sector_from_stock`도 "기타" 고정 — 양쪽 공통 미해결 갭.
- **핵심 전환**: Gemini가 추출하면서 **각 종목에 섹터를 같이 태깅**(sector_hint)한다.
  Gemini는 "마이크론=메모리=반도체", "삼성전자=반도체"를 이미 안다. → 한국주·외국주 모두
  자동 섹터 분류. 수동 매핑은 오버라이드로 강등.
- **범위**: 종목 섹터 분류만. daily_health 검증시스템은 별도 후속 spec.

---

## 1. 결정 사항 (brainstorming 확정)

| 항목 | 결정 |
|---|---|
| 적용 범위 | **모든 종목** (한국주 + 외국주). "기타" 고정 근본 해결 |
| 분류 방식 | **인라인 hint** — 추출 1콜에 묻어감 (추가 호출/비용 0). 별도 분류패스(B)·학습캐시(C)는 후속 |
| 택소노미 | **고정 목록에서 선택** (표기 일관·집계 깔끔) |
| 확장성 | 섹터 목록을 **`sectors.json` config**로 — 추가 시 JSON만 편집 |
| 외국 매핑 | `foreign_sector_map.json`은 **오버라이드**로 강등 (Gemini 틀릴 때만 교정) |

---

## 2. 섹터 택소노미 (config)

`pipeline/atoms/sectors.json` — 단일 진실 소스. Gemini 프롬프트와 fan-out 정규화가
**둘 다 여기서 읽는다.** 섹터 추가 = 이 파일에 한 줄.

```json
{
  "sectors": [
    "반도체", "2차전지", "자동차", "조선", "방산", "로봇",
    "전력", "원전", "신재생", "바이오", "통신", "철강",
    "IT", "양자보안", "화장품미용", "소비내수", "중국", "기타"
  ]
}
```

- "기타"는 항상 폴백으로 존재.
- "중국"은 지역테마(하나차이나 채널용) — 유지.
- 기존 코드의 흩어진 섹터 리스트(`_SECTOR_KEYS`, 리포트 `_SECTOR_LIST`)를 이 config로 **통일**.

---

## 3. 아키텍처

```
질문지 추출 (Gemini)
  └ 각 종목 슬롯에 sector 칸 추가 → Gemini가 sectors.json 목록 중 1개 선택
       (프롬프트에 목록 주입, "모르면 기타")
        │
fan-out (코드, 결정론)
  └ 종목원자 sector 결정 우선순위:
       1. foreign_sector_map 오버라이드 (외국주, 있으면)   ← 교정용
       2. Gemini sector_hint (목록 정규화)
       3. 기타 + 큐레이션 로그 (hint 없음/목록밖)
```

### 섹터 결정 함수 (신규 `sector_classify.py`)
**항상 `list[str]` 반환** (단일 섹터도 길이1 리스트 — multi-sector 애플=[반도체,IT] 일관 처리):
```
resolve_sector(name, hint, *, is_foreign) -> (sectors: list[str], source: str)
  - is_foreign이고 foreign_sector_map에 있으면 → (map[name], "map")        # 리스트 그대로
  - hint가 sectors 목록에 정확매칭 → ([hint], "gemini")
  - hint가 목록 부분매칭("반도체장비"→"반도체") → ([정규화값], "gemini_norm")
  - 아니면 → (["기타"], "fallback")  + 로그
```
> 종목원자(단일 섹터): sectors[0] 사용. 외국 컨텍스트 원자: sectors 각각 1개씩 생성.

---

## 4. 질문지 변경 (5종)

각 종목 멘션 슬롯에 `sector` 추가:
- `[stock_tips] stocks[]`: {name, signal, reason, ts, quote, **sector**}
- `[sector] stocks_mentioned[]`: {name, comment, ts, quote, **sector**}
- `[insight] stocks_mentioned[]`: 동일
- `[market]`: sectors_mentioned는 이미 sector 있음 (변경 없음)
- `[report_relay] reports[]`: {broker, stock, rating, tp, ts, quote, **sector**}

공통 철칙 추가:
```
각 종목에 sector를 붙여라. 아래 목록에서 정확히 하나만 고른다 (모르면 "기타"):
{sectors.json에서 주입}
```

---

## 5. fan-out 변경

- `_stock_atom`: `sector` 인자 받아 원자에 반영 (현재 meta.sector 기본값 대체).
- `add_stocks`:
  - 한국주(matched): `resolve_sector(name, s["sector"], is_foreign=False)` → 종목원자 sector
  - 외국주: `resolve_sector(name, s["sector"], is_foreign=True)`
    - 오버라이드 map 있으면 그 섹터(들)로 컨텍스트 원자 (기존 동작)
    - 없고 hint 있으면 hint 섹터로 컨텍스트 원자 (← 신규: 모르는 외국주도 살림)
    - 둘 다 없으면 기타 컨텍스트 원자 + foreign_unmapped 로그
- report_relay: 한국주 종목원자에 sector 반영.

### 외국주 손실 해결 (이번 핵심 효과)
기존: 모르는 외국주 = 이름만 로그, 코멘트 손실.
변경: Gemini hint로 섹터 분류 → **코멘트가 hint 섹터 컨텍스트 원자로 보존**.
foreign_unmapped 로그는 "Gemini도 기타로 본 것"만 남아 진짜 큐레이션 큐가 됨.

---

## 6. 검증/테스트

- `sectors.json` 로드 + `resolve_sector` 단위테스트:
  - 한국주 hint="반도체" → ("반도체","gemini")
  - 외국주 애플 (map 오버라이드) → ([반도체,IT],"map") (hint 무시)
  - 외국주 hint만 (map 없음) → (hint,"gemini") — 모르는 외국주 살림
  - hint 목록밖("메모리") → 부분매칭 시 반도체, 아니면 기타+로그
  - hint 없음 → 기타+로그
- fan-out: stock_tips 한국주가 "기타" 아닌 실섹터 받는지.
- 골든셋 회귀: `tg_spike.json`에 sector 필드 보강 후 재실행.
- 로그 격리(테스트가 운영 로그 오염 금지) — 기존 패턴 준수.

---

## 7. 기존 자산 통합

| 자산 | 역할 변경 |
|---|---|
| `foreign_sector_map.json` | 1차 소스 → **오버라이드**(Gemini 교정용) |
| `_norm_sector` / `_SECTOR_KEYS` (telegram) | `sectors.json` 읽도록 교체 |
| 리포트 `_SECTOR_LIST` / `_guess_sector_from_stock` | (후속) 같은 config·resolve_sector로 통일 — 이 spec은 텔레그램만, 리포트 통일은 범위표시만 |
| `telegram_foreign_unmapped.log` | "Gemini도 기타로 본 외국주"만 남는 정제된 큐 |

---

## 8. 범위 밖 (후속)
- 리포트 파이프라인 `_guess_sector_from_stock` 통일 (같은 resolve_sector 적용)
- 학습 캐시(C안): 종목→섹터 1회 분류 후 재사용
- daily_health 검증시스템 (별도 spec)

---

## 9. 미해결/결정 필요
- `sectors.json` 위치를 `pipeline/atoms/`에 둘지 프로젝트 공용으로 둘지 → 일단 `pipeline/atoms/`
- hint 목록밖 값의 부분매칭 강도 (예 "반도체장비"→"반도체") → 부분문자열 포함이면 매칭
