# 종목별 태린이 지표 — 대시보드 종목 카드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 태린이 13개 파서가 이미 모으는 `results` dict를 종목코드별 스냅샷(`pipeline/taerini_stock.json`)으로 집계하고, 차트 모달에 "📊 태린이 지표" 패널로 표시한다.

**Architecture:** `ingest_excel.main()`이 수집한 `results`를 신규 `build_stock_index()`가 종목코드 기준으로 재구성해 JSON 스냅샷으로 저장(파서·텔레그램 무수정). 서버는 `/api/taerini_stock?code=`로 종목 레코드를 서빙하고, `market.html` 차트 모달이 종목 클릭 시 fetch해 패널을 그린다.

**Tech Stack:** Python 3.14, openpyxl(기존), FastAPI(기존), pytest(테스트), Lightweight Charts(기존, 변경 없음), vanilla JS.

## Global Constraints

- 파서 함수(`parse_*`)와 텔레그램 빌드 로직은 **수정 금지**. 회귀 위험 0 유지.
- `results` dict 키(파서 라벨): `"추정이익변경"`, `"컨센움직임"`, `"수급"`, `"중소형주수급"`, `"RS"`, `"가속화모멘텀"`, `"액티브ETF"`, `"일정"` (그 외 `"수출"`,`"유동성"`,`"쏠림지수"`,`"한국ETF_RS"`,`"투자아이디어"`는 종목 카드에서 미사용).
- 종목코드는 **6자리 문자열**로 정규화(`"A247540"`/`247540`/`"247540"` → `"247540"`).
- 종목명→코드 매핑: `pipeline/atoms/krx_codes.json`의 `{"codes": {종목명: 코드}}` 사용. **미매칭 종목명은 `meta.unmatched`에 기록(조용히 버리지 않음)**.
- 스냅샷은 일 1회(기존 07:50 인제스트). 카드에 `date` 항상 표기.
- 서버 재시작 필요(자동 reload 없음). 포트 8090.

## File Structure

- `scripts/ingest_excel.py` (수정) — 상단 `import json` 추가, name→code 헬퍼 3개 + `build_stock_index()` 추가, `main()`에서 호출.
- `pipeline/taerini_stock.json` (생성, 런타임 산출물) — 종목코드별 스냅샷.
- `dashboard/server.py` (수정) — `TAERINI_STOCK_PATH` 상수 + `GET /api/taerini_stock` 엔드포인트.
- `dashboard/market.html` (수정) — 차트 모달에 `#taerini-panel` + `_loadTaerini`/`_taeriniHtml` + CSS.
- `tests/test_taerini_stock.py` (생성) — `build_stock_index` 단위 테스트 + 엔드포인트 TestClient 테스트.

---

### Task 1: `build_stock_index()` + 종목명→코드 헬퍼

**Files:**
- Modify: `scripts/ingest_excel.py` (상단 import + 헬퍼/집계기 함수 추가; 권장 위치 `fmt_num`(L170) 근처 또는 `main()` 직전)
- Test: `tests/test_taerini_stock.py`

**Interfaces:**
- Produces:
  - `_load_name2code() -> dict` — `{종목명: "6자리코드"}` (캐시; `pipeline/atoms/krx_codes.json` 로드)
  - `_norm_code(raw) -> str | None` — 코드 정규화
  - `build_stock_index(results: dict, dest=None) -> dict` — 스냅샷 dict 반환 + `dest`(기본 `pipeline/taerini_stock.json`)에 원자적 저장. 반환 형식: `{"date": str, "stocks": {code: {...}}, "meta": {"built_at", "stock_count", "unmatched"}}`

- [ ] **Step 1: 상단 import에 json 추가**

`scripts/ingest_excel.py` 최상단 import 블록(현재 `import sys, os, re, glob, argparse, subprocess`)을 다음으로 교체:

```python
import sys, os, re, glob, argparse, subprocess, json
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_taerini_stock.py` 생성:

```python
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ingest_excel as ix


def _sample_results():
    return {
        "수급": {"빈집_A": [{"name": "에코프로비엠", "code": "247540",
                              "osc": -0.42, "pct": 8.0, "trend": "↓ 빈집심화"}]},
        "중소형주수급": {},
        "RS": {"top30": [{"name": "삼성전자", "RS_avg": 1.23, "norm_RS_avg": 0.9}],
               "bottom10": []},
        "추정이익변경": {"results": {
            "TP_Up": [{"name": "삼성전자", "code": "A005930",
                       "tp_old": 80000, "tp_new": 92000}],
            "TP_Down": []}},
        "컨센움직임": {"results": {
            "쇼크": [{"name": "에코프로비엠", "code": "A247540",
                      "csen_chg": -12.0, "surprise_rate": -30.0}]}},
        "가속화모멘텀": {"results": {
            "주당순이익1개+": [{"name": "삼성전자", "score": 0.61}]}},
        "액티브ETF": {"increase": [{"etf": "TIGER", "name": "삼성전자",
                                     "diff": 0.3, "rate": 1.1}], "decrease": []},
        "일정": {"d7": [{"date": "2999-01-01", "related": "삼성전자",
                         "content": "실적발표"}], "d30": []},
    }


def test_build_stock_index_maps_codes_and_fields(tmp_path):
    # 종목명→코드 매핑 고정 (krx_codes.json 의존 제거)
    ix._KRX_NAME2CODE = {"삼성전자": "005930", "에코프로비엠": "247540"}
    dest = tmp_path / "taerini_stock.json"

    out = ix.build_stock_index(_sample_results(), dest=dest)

    assert out["date"]
    s = out["stocks"]
    # 코드 정규화 (A 제거 / 6자리)
    assert "247540" in s and "005930" in s
    # 코드 보유 파서 (오실레이터)
    assert s["247540"]["osc"]["trend"] == "↓ 빈집심화"
    # 종목명만 있는 파서 (RS) → 코드 매핑
    assert s["005930"]["rs"]["bucket"] == "상위"
    # TP 변화율 계산
    assert s["005930"]["tp"]["change_pct"] == 15.0
    assert s["005930"]["tp"]["dir"] == "상향"
    # 컨센 타입
    assert s["247540"]["consensus"]["type"] == "쇼크"
    # 가속/ETF/일정
    assert s["005930"]["accel"]["score"] == 0.61
    assert s["005930"]["etf"]["action"] == "비중증가"
    assert s["005930"]["schedule"]["dday"] is not None
    # 파일 저장 + meta
    assert dest.exists()
    saved = json.loads(dest.read_text(encoding="utf-8"))
    assert saved["meta"]["stock_count"] == 2
    assert isinstance(saved["meta"]["unmatched"], list)


def test_unmatched_names_recorded(tmp_path):
    ix._KRX_NAME2CODE = {}   # 매핑 없음
    out = ix.build_stock_index(
        {"RS": {"top30": [{"name": "없는종목", "RS_avg": 1.0}], "bottom10": []}},
        dest=tmp_path / "x.json")
    assert "없는종목" in out["meta"]["unmatched"]
    assert out["stocks"] == {}
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd "C:/Users/TheRose/Desktop/로또의 주식" && python -m pytest tests/test_taerini_stock.py -v`
Expected: FAIL (`AttributeError: module 'ingest_excel' has no attribute 'build_stock_index'`)

- [ ] **Step 4: 헬퍼 + 집계기 구현**

`scripts/ingest_excel.py`에 추가 (예: `fmt_num` 함수 뒤):

```python
# ─── 종목별 태린이 지표 집계 (대시보드 종목 카드용) ──────────────────
_KRX_NAME2CODE = None


def _load_name2code() -> dict:
    """pipeline/atoms/krx_codes.json ({"codes": {종목명: 코드}}) → {종목명: '6자리코드'}."""
    global _KRX_NAME2CODE
    if _KRX_NAME2CODE is not None:
        return _KRX_NAME2CODE
    m = {}
    try:
        path = ROOT / "pipeline" / "atoms" / "krx_codes.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, code in (data.get("codes") or {}).items():
            c = _norm_code(code)
            if c:
                m[name.strip()] = c
    except Exception:
        pass
    _KRX_NAME2CODE = m
    return m


def _norm_code(raw) -> str | None:
    """'A247540' / 247540 / '247540' → '247540'. 6자리 숫자 아니면 None."""
    if raw is None:
        return None
    s = str(raw).strip().upper()
    if s.startswith("A"):
        s = s[1:]
    if s.isdigit():
        s = s.zfill(6)
    return s if (s.isdigit() and len(s) == 6) else None


def _resolve_code(item: dict, name2code: dict, unmatched: list) -> str | None:
    """항목에서 코드 확보: code 필드 우선, 없으면 종목명(name/related)→코드 매핑."""
    c = _norm_code(item.get("code"))
    if c:
        return c
    name = (item.get("name") or item.get("related") or "").strip()
    if name and name in name2code:
        return name2code[name]
    if name:
        unmatched.append(name)
    return None


def build_stock_index(results: dict, dest=None) -> dict:
    """파서 results → 종목코드별 태린이 지표 스냅샷. pipeline/taerini_stock.json 저장."""
    name2code = _load_name2code()
    stocks: dict = {}
    unmatched: list = []

    def slot(code: str, name: str) -> dict:
        s = stocks.setdefault(code, {"name": name or ""})
        if name and not s.get("name"):
            s["name"] = name
        return s

    # 1) 오실레이터 (수급 + 중소형주) → osc
    for key in ("수급", "중소형주수급"):
        r = results.get(key) or {}
        for grp in ("빈집_A", "빈집_B", "과매수_상승", "과매수_하락"):
            for it in (r.get(grp) or []):
                code = _resolve_code(it, name2code, unmatched)
                if not code:
                    continue
                slot(code, it.get("name", ""))["osc"] = {
                    "group": grp, "osc": it.get("osc"),
                    "pct": it.get("pct"), "trend": it.get("trend"),
                }

    # 2) RS → rs (top30 / bottom10 만 존재)
    r = results.get("RS") or {}
    for bucket, tag in (("top30", "상위"), ("bottom10", "하위")):
        for it in (r.get(bucket) or []):
            code = _resolve_code(it, name2code, unmatched)
            if not code:
                continue
            slot(code, it.get("name", ""))["rs"] = {
                "rs_avg": it.get("RS_avg"), "norm": it.get("norm_RS_avg"),
                "bucket": tag,
            }

    # 3) 추정이익변경 → tp (TP_Up / TP_Down)
    r = (results.get("추정이익변경") or {}).get("results") or {}
    for bucket, d in (("TP_Up", "상향"), ("TP_Down", "하향")):
        for it in (r.get(bucket) or []):
            code = _resolve_code(it, name2code, unmatched)
            if not code:
                continue
            tp_new, tp_old = it.get("tp_new"), it.get("tp_old")
            pct = None
            if isinstance(tp_new, (int, float)) and isinstance(tp_old, (int, float)) and tp_old:
                pct = round((tp_new - tp_old) / tp_old * 100, 1)
            slot(code, it.get("name", ""))["tp"] = {
                "target": tp_new, "prev": tp_old, "change_pct": pct, "dir": d,
            }

    # 4) 컨센움직임 → consensus
    r = (results.get("컨센움직임") or {}).get("results") or {}
    for bucket in ("컨센상향", "컨센하향", "서프라이즈", "쇼크"):
        for it in (r.get(bucket) or []):
            code = _resolve_code(it, name2code, unmatched)
            if not code:
                continue
            slot(code, it.get("name", ""))["consensus"] = {
                "type": bucket, "csen_chg": it.get("csen_chg"),
                "surprise_rate": it.get("surprise_rate"),
            }

    # 5) 가속화모멘텀 → accel (그룹별, 종목명만; 점수 높은 그룹 우선)
    r = (results.get("가속화모멘텀") or {}).get("results") or {}
    for grp, items in r.items():
        for it in (items or []):
            code = _resolve_code(it, name2code, unmatched)
            if not code:
                continue
            cur = slot(code, it.get("name", ""))
            prev = cur.get("accel")
            if prev and (prev.get("score") or 0) >= (it.get("score") or 0):
                continue
            cur["accel"] = {"group": grp, "score": it.get("score")}

    # 6) 액티브ETF → etf
    r = results.get("액티브ETF") or {}
    for bucket, act in (("increase", "비중증가"), ("decrease", "비중감소")):
        for it in (r.get(bucket) or []):
            code = _resolve_code(it, name2code, unmatched)
            if not code:
                continue
            slot(code, it.get("name", ""))["etf"] = {
                "action": act, "diff": it.get("diff"), "rate": it.get("rate"),
            }

    # 7) 일정 → schedule (related = 종목명)
    r = results.get("일정") or {}
    today = date.today()
    for bucket in ("d7", "d30"):
        for it in (r.get(bucket) or []):
            code = _resolve_code({"name": it.get("related")}, name2code, unmatched)
            if not code:
                continue
            dday = None
            try:
                ev = datetime.strptime((it.get("date") or "").strip(), "%Y-%m-%d").date()
                dday = (ev - today).days
            except Exception:
                pass
            slot(code, it.get("related", ""))["schedule"] = {
                "event": it.get("content", ""), "date": it.get("date"), "dday": dday,
            }

    out = {
        "date": TODAY,
        "stocks": stocks,
        "meta": {
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "stock_count": len(stocks),
            "unmatched": sorted(set(unmatched)),
        },
    }
    dest = Path(dest) if dest else (ROOT / "pipeline" / "taerini_stock.json")
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, dest)
    return out
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd "C:/Users/TheRose/Desktop/로또의 주식" && python -m pytest tests/test_taerini_stock.py -v`
Expected: PASS (2개 — `test_build_stock_index_maps_codes_and_fields`, `test_unmatched_names_recorded`)

- [ ] **Step 6: 커밋**

```bash
git add scripts/ingest_excel.py tests/test_taerini_stock.py
git commit -m "feat(taerini): 종목코드별 태린이 지표 집계기 build_stock_index"
```

---

### Task 2: `main()`에서 집계기 호출

**Files:**
- Modify: `scripts/ingest_excel.py:2044-2061` (파서 루프 직후, 리포트 저장 부근)

**Interfaces:**
- Consumes: `build_stock_index(results)` (Task 1)

- [ ] **Step 1: 파서 루프 직후 호출 추가**

`scripts/ingest_excel.py`의 `main()`에서 파서 루프(`for key, (label, fn) in parsers.items(): ...`)가 끝난 직후, `# 리포트 저장` 줄 **앞에** 추가:

```python
    # 종목별 태린이 지표 스냅샷 (대시보드 종목 카드용)
    try:
        idx = build_stock_index(results)
        msg = f"  📦 taerini_stock.json — {idx['meta']['stock_count']}종목"
        if idx["meta"]["unmatched"]:
            msg += f" (미매칭 {len(idx['meta']['unmatched'])})"
        print(msg)
    except Exception as e:
        print(f"  ⚠️ build_stock_index 실패: {e}")
```

- [ ] **Step 2: 실제 엑셀로 빌드 검증 (스냅샷 생성)**

Run: `cd "C:/Users/TheRose/Desktop/로또의 주식" && python scripts/ingest_excel.py --dry-run`
Expected: 출력에 `📦 taerini_stock.json — N종목` (N>0), 그리고 `pipeline/taerini_stock.json` 생성됨.

확인:
```bash
python -c "import json; d=json.load(open('pipeline/taerini_stock.json',encoding='utf-8')); print('종목수',d['meta']['stock_count'],'날짜',d['date']); print('샘플코드', list(d['stocks'])[:3])"
```
Expected: 종목수 > 0, 샘플 6자리 코드 출력.

- [ ] **Step 3: 커밋**

```bash
git add scripts/ingest_excel.py pipeline/taerini_stock.json
git commit -m "feat(taerini): 일일 인제스트에서 종목 스냅샷 자동 생성"
```

---

### Task 3: `/api/taerini_stock` 엔드포인트

**Files:**
- Modify: `dashboard/server.py` (다른 `@app.get` 엔드포인트 근처, 예: `/api/stock_candles` 뒤)
- Test: `tests/test_taerini_stock.py` (추가)

**Interfaces:**
- Consumes: `pipeline/taerini_stock.json` (Task 2 산출)
- Produces: `GET /api/taerini_stock?code=` → `{"found": bool, "date": str|None, "stock": {...}|생략}`

- [ ] **Step 1: 실패하는 엔드포인트 테스트 작성**

`tests/test_taerini_stock.py` 끝에 추가:

```python
def test_api_taerini_stock(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "dashboard"))
    import server
    from fastapi.testclient import TestClient

    snap = tmp_path / "taerini_stock.json"
    snap.write_text(json.dumps({
        "date": "2026-06-30",
        "stocks": {"247540": {"name": "에코프로비엠",
                              "tp": {"target": 330000, "dir": "하향"}}},
        "meta": {"stock_count": 1, "unmatched": []},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(server, "TAERINI_STOCK_PATH", str(snap))

    c = TestClient(server.app)
    # 존재 코드
    r = c.get("/api/taerini_stock?code=247540").json()
    assert r["found"] is True and r["stock"]["tp"]["dir"] == "하향"
    # 미존재 코드
    r = c.get("/api/taerini_stock?code=000000").json()
    assert r["found"] is False
    # 빈 코드
    assert c.get("/api/taerini_stock?code=").json()["found"] is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd "C:/Users/TheRose/Desktop/로또의 주식" && python -m pytest tests/test_taerini_stock.py::test_api_taerini_stock -v`
Expected: FAIL (`AttributeError: ... 'TAERINI_STOCK_PATH'` 또는 404)

- [ ] **Step 3: 상수 + 엔드포인트 구현**

`dashboard/server.py`에서 `KRX_CODES_PATH = ...` 줄 근처에 상수 추가:

```python
TAERINI_STOCK_PATH = os.path.join(ROOT, "pipeline", "taerini_stock.json")
```

그리고 `/api/stock_candles` 엔드포인트 함수 뒤에 추가:

```python
@app.get("/api/taerini_stock")
def api_taerini_stock(code: str = ""):
    code = (code or "").strip()
    if code.isdigit():
        code = code.zfill(6)
    if not code or not os.path.exists(TAERINI_STOCK_PATH):
        return JSONResponse(content={"found": False})
    try:
        with open(TAERINI_STOCK_PATH, encoding="utf-8") as f:
            data = json.load(f)
        stock = (data.get("stocks") or {}).get(code)
        if not stock:
            return JSONResponse(content={"found": False, "date": data.get("date")})
        return JSONResponse(content={"found": True, "date": data.get("date"), "stock": stock})
    except Exception as e:
        return JSONResponse(content={"found": False, "error": str(e)})
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd "C:/Users/TheRose/Desktop/로또의 주식" && python -m pytest tests/test_taerini_stock.py -v`
Expected: PASS (3개 전부)

- [ ] **Step 5: 서버 재시작 + 실데이터 curl 검증**

서버 재시작(기존 절차) 후:
```bash
curl -s "http://localhost:8090/api/taerini_stock?code=247540" -o t.json && python -c "import json;d=json.load(open('t.json',encoding='utf-8'));print(d.get('found'),d.get('date'));print(list((d.get('stock') or {}).keys()))" && rm -f t.json
```
Expected: `found` True/False + (있으면) 필드 키 목록(osc/rs/tp/... 중 일부).

- [ ] **Step 6: 커밋**

```bash
git add dashboard/server.py tests/test_taerini_stock.py
git commit -m "feat(taerini): /api/taerini_stock 엔드포인트"
```

---

### Task 4: 차트 모달 "📊 태린이 지표" 패널

**Files:**
- Modify: `dashboard/market.html` (차트 모달 HTML + JS + CSS)

**Interfaces:**
- Consumes: `GET /api/taerini_stock?code=` (Task 3)
- 기존 `openStockChart(code, name)` 함수에서 호출.

- [ ] **Step 1: CSS 추가**

`dashboard/market.html` `<style>`에 추가:

```css
.taerini-panel{font-size:12px;color:#bbb;padding:4px 10px;border-top:1px solid #1c1c1c;
  white-space:nowrap;overflow-x:auto;line-height:1.6;}
.taerini-panel .tk-lab{color:#777;margin-right:2px;}
```

- [ ] **Step 2: 모달에 패널 컨테이너 추가**

`openStockChart`가 만드는 모달 HTML에서 시간대/지표 버튼 줄(`.chart-tf`가 포함된 헤더) **바로 아래**에 패널 div 삽입:

```html
<div id="taerini-panel" class="taerini-panel">📊 태린이 지표 로딩…</div>
```

(차트 컨테이너 `#tv_chart_container` div **직전**에 위치)

- [ ] **Step 3: 렌더 함수 + fetch 추가**

`dashboard/market.html` `<script>`에 추가 (예: `openStockChart` 정의 근처):

```javascript
function _taeriniHtml(d){
  const L=t=>`<span class="tk-lab">${t}</span>`;
  if(!d || !d.found) return `📊 ${L("태린이")}미수록${d&&d.date?` (${d.date})`:""}`;
  const s=d.stock||{}, parts=[];
  const C=(t,c)=>`<span style="color:${c}">${t}</span>`;
  if(s.osc) parts.push(`${L("수급")}${C(s.osc.trend||s.osc.group||"-","#e0b94a")}`
    + (s.osc.pct!=null?`(${Math.round(s.osc.pct)}%ile)`:""));
  if(s.rs) parts.push(`${L("RS")}${s.rs.rs_avg!=null?Number(s.rs.rs_avg).toFixed(2):"-"}(${s.rs.bucket})`);
  if(s.tp){ const up=s.tp.dir==="상향"; const tgt=s.tp.target!=null?Math.round(s.tp.target/1000)+"천":"";
    parts.push(`${L("TP")}${C(tgt+(up?"↑":"↓"), up?"#e74c3c":"#3aa0ff")}`
      + (s.tp.change_pct!=null?`(${s.tp.change_pct>0?"+":""}${s.tp.change_pct}%)`:"")); }
  if(s.consensus){ const t=s.consensus.type||""; const good=(t==="컨센상향"||t==="서프라이즈");
    parts.push(`${L("컨센")}${C(t||"-", good?"#e74c3c":"#3aa0ff")}`); }
  if(s.accel) parts.push(`${L("가속")}${s.accel.score!=null?Number(s.accel.score).toFixed(2):"-"}`);
  if(s.etf){ const inc=s.etf.action==="비중증가";
    parts.push(`${L("ETF")}${C(inc?"비중↑":"비중↓", inc?"#e74c3c":"#3aa0ff")}`); }
  if(s.schedule&&s.schedule.dday!=null){ const dd=s.schedule.dday;
    parts.push(`${L("실적")}D${dd<=0?dd:"+"+dd}`); }
  if(!parts.length) return `📊 ${L("태린이")}미수록 (${d.date||""})`;
  return `📊 ` + parts.join(" · ") + ` <span style="color:#555">(${d.date||""})</span>`;
}

async function _loadTaerini(code){
  const box=document.getElementById("taerini-panel");
  if(!box) return;
  box.innerHTML='📊 <span class="tk-lab">태린이 지표 로딩…</span>';
  try{
    const r=await fetch("/api/taerini_stock?code="+encodeURIComponent(code));
    box.innerHTML=_taeriniHtml(await r.json());
  }catch(e){ box.innerHTML='📊 <span style="color:#a55">태린이 지표 로드 실패</span>'; }
}
```

- [ ] **Step 4: `openStockChart`에서 호출**

`openStockChart(code, name)` 안에서 모달이 DOM에 삽입되고 차트 로드를 시작하는 지점(예: `loadChartData()` 호출 부근)에 추가:

```javascript
  _loadTaerini(code);
```

- [ ] **Step 5: 브라우저 검증**

서버 재시작 후 `http://localhost:8090/market` 로드 → 종목(예: 에코프로비엠) 클릭 → 차트 모달의 시간대 버튼 줄 아래 `📊 태린이 …` 패널 표시 확인. 콘솔 JS:

```javascript
openStockChart('247540','에코프로비엠');
await new Promise(r=>setTimeout(r,2000));
document.getElementById('taerini-panel').textContent;
```
Expected: `📊 ...` (데이터 있으면 지표 나열, 없으면 "태린이 미수록 (날짜)"). 차트는 정상 동작, 콘솔 신규 에러 없음.

- [ ] **Step 6: 커밋**

```bash
git add dashboard/market.html
git commit -m "feat(taerini): 차트 모달 태린이 지표 패널"
```

---

## Self-Review

- **Spec coverage:** ① 집계기(Task 1) ② 일일 자동 생성(Task 2) ③ 엔드포인트(Task 3) ④ 종목 카드 패널(Task 4) — 스펙 §3·4·5·6 전부 매핑. 표시 항목(수급/컨센TP/RS/가속/ETF/실적) 모두 포함. 미매칭 기록·부분 빌드·graceful 엔드포인트·날짜 표기 반영.
- **알려진 한계(스펙과 일치):** RS는 파서가 top30/bottom10만 반환 → RS 필드는 순위권 종목만. 가속/ETF/일정도 신호에 잡힌 종목만(희소). 카드 성격상 정상("이 종목이 태린이 신호에 잡혔나").
- **Placeholder scan:** 모든 step에 실제 코드/명령/기대값 포함. 없음.
- **Type consistency:** `build_stock_index(results, dest=None)`·`_norm_code`·`_resolve_code`·`_load_name2code` 시그니처 Task 1 정의와 Task 2·3 사용 일치. 엔드포인트 응답 키(`found`/`date`/`stock`)와 `_taeriniHtml` 소비 키 일치. 필드 키(osc/rs/tp/consensus/accel/etf/schedule)가 집계기 산출과 JS 렌더 간 일치.
