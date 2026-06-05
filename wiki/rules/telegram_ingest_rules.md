# 텔레그램 인제스트 운영규칙

## 핵심 원칙

텔레그램 파일은 30분마다 업데이트된다.
같은 날 여러 번 인제스트해도 **중복 없이 증분만 처리**한다.

---

## ⛔ 위키에 반영하지 않는 것 — 양질의 내용만 뽑기 위함

텔레그램에는 당일 주가 등락·지수 변동 언급이 많다.
이런 내용은 **하루짜리 노이즈**로, 위키에 누적하면 오히려 신호 대비 잡음이 증가한다.

**Gemini 추출 시 + Claude 인제스트 시 모두 아래 내용은 제외:**

| 제외 유형 | 예시 |
|---------|------|
| 당일 종목 등락% | "삼성전자 -6%", "브로드컴 -12.6%" |
| 당일 지수 등락 | "코스피 +0.5%", "필라델피아반도체 +1.39%" |
| 미국 종목 당일 움직임 | "엔비디아 -3.62%", "릴리 신고가" |
| 원자재·환율 당일 가격 | "WTI 96달러", "금 4,466달러" |

**추출해야 하는 것 (구조적 정보):**

| 추출 유형 | 예시 |
|---------|------|
| 섹터 방향 판단 | "반도체→헬스케어 순환매 흐름" |
| 종목 수급 빈집 | "한미약품 수급 비어있음 포착" |
| 리포트 TP·투자전략 | "KB TP 200만원 상향" |
| 이벤트·트리거 | "ADA학회 6/5~8 GLP-1 발표" |
| 구조적 리스크 | "담합 수사, ETF 리밸런싱 압력" |
| 매매 전략 원칙 | "10일선 이탈 즉시 매도" |

---

## 타임스탬프 구조

텔레그램 md 파일 내 메시지는 아래 형식:

```
**06:14**

메시지 내용...

---

**10:27**

다음 메시지...
```

- 형식: `**HH:MM**` (24시간제)
- 타임스탬프 = 해당 메시지의 발송 시각

---

## 상태 추적 (`pipeline/crawl_ingest_state.json`)

```json
{
  "telegram": {
    "2026-06-05": {
      "태린이아빠 주식투자": {
        "last_extracted_ts": "10:59",
        "last_ingested_ts":  "10:59"
      },
      "미래시황": {
        "last_extracted_ts": "09:15",
        "last_ingested_ts":  "09:15"
      }
    }
  }
}
```

- `last_extracted_ts`: Gemini가 마지막으로 처리한 타임스탬프
- `last_ingested_ts`: Claude가 wiki에 반영한 마지막 타임스탬프

---

## 증분 처리 로직

### telegram_extract.py 실행 시

```
1. state.json에서 {날짜}/{채널}의 last_extracted_ts 확인
2. 없으면 → 파일 전체 처리
3. 있으면 → last_extracted_ts 이후 메시지만 슬라이싱
4. Gemini에 증분 내용만 전달
5. JSON 저장 후 state.json의 last_extracted_ts 갱신
```

### Claude 인제스트 시

```
1. extracted/{채널}.json 읽기
2. json.timestamp_range 확인 ("06:00~10:59")
3. wiki 업데이트
4. state.json의 last_ingested_ts 갱신
```

---

## 파일 슬라이싱 규칙

```python
# 타임스탬프 파싱: "**HH:MM**" 패턴
import re

def split_by_timestamp(content):
    # 각 메시지 블록을 timestamp와 함께 분리
    pattern = r'\*\*(\d{2}:\d{2})\*\*'
    ...

def get_incremental(content, last_ts):
    # last_ts 이후 메시지만 반환
    # 같은 시각(HH:MM)이 여러 개면 마지막 것 이후부터
    ...
```

---

## extracted JSON 파일 구조

```json
{
  "channel": "태린이아빠 주식투자",
  "date": "2026-06-05",
  "timestamp_range": "06:00~10:59",
  "is_incremental": false,
  "type": "personal_analyst",

  "market_view": "브로드컴 쇼크. 순환매 헬스케어·금융.",
  "sector_signals": [
    {"sector": "반도체", "direction": "조정", "reason": "10일선 기준 관망"},
    {"sector": "바이오", "direction": "강세", "reason": "릴리 신고가·ADA 발표"}
  ],
  "stock_signals": [
    {
      "name": "한미약품",
      "code": "128940",
      "direction": "관심",
      "reason": "릴리 계약. 수급 빈 상태.",
      "trigger": "ADA학회 6/5-8"
    }
  ],
  "supply_vacuum": ["한미약품"],
  "strategy": "10일선 이탈 즉시 매도. 현금 30% 확보.",
  "images_missed": "수급빈집 리스트 이미지 - 종목명 파악 불가"
}
```

---

## 파일 경로 규칙

```
crawling_bot_data/{날짜}/
  telegram/{채널}.md              ← 원본 (수정 안 함)
  extracted/
    {채널}.json                   ← Gemini 추출 결과
    {채널}_prev.json              ← 이전 추출본 (덮어쓰기 전 백업)
```

---

## 실행 명령

```bash
# 오늘 전체 채널 추출
python scripts/telegram_extract.py --date 2026-06-05

# 특정 채널만
python scripts/telegram_extract.py --date 2026-06-05 --channel "태린이아빠 주식투자"

# 강제 전체 재처리 (타임스탬프 무시)
python scripts/telegram_extract.py --date 2026-06-05 --force
```

---

## Claude 인제스트 순서

1. `extracted/` 폴더 확인 → priority 순 정렬
2. 채널 1개 JSON 읽기
3. wiki 업데이트 (섹터/종목 페이지)
4. "완료, 다음: {다음채널명}?" 확인
5. 사용자 OK → 다음 채널
