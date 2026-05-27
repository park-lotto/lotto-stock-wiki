#!/usr/bin/env python3
"""
wiki_patch.py — 일일 변화 MD → wiki stock 파일 자동 패치
사용법: python wiki_patch.py
결과:  처리 완료 항목은 stock 파일에 행 추가
       미등록 종목은 raw/매일요약/YYYYMMDD_미처리.md 에 저장
"""
import re, json
from datetime import datetime
from pathlib import Path

ROOT     = Path(__file__).parent
WIKI     = ROOT / "wiki" / "L5_섹터"
MAP_FILE = ROOT / "sector_map.json"
DAILY    = ROOT / "raw" / "매일요약"
TODAY    = datetime.now().strftime("%Y%m%d")
DATE     = datetime.now().strftime("%Y-%m-%d")

TEMPLATE = """\
> [!NOTE] 탑픽 스코어
> **수급빈집**: ❌  **수출🔴**: ❌  **판가**: ❌  **어닝서프**: ❌
> **리포트신고가**: ❌  **미국커플링**: ❌  **정책이슈**: ❌  **일정재료**: ❌
> **총점**: 0/9점  →  🟡 대기
> **결론**: 데이터 수집 중

# {name} ({code})
> 섹터: {sector} / 서브섹터: — / 미국 페어: —

## 종합 스토리
> **{date} 기준**: 데이터 수집 중

---

## 최신 이벤트
| 날짜 | 내용 | 출처 | 신호 |
|------|------|------|------|

---

## 일정
| 날짜 | 일정 | 종류 | 기대 |
|------|------|------|------|
| — | — | — | — |

---

## 수출 데이터
| 날짜 | 물량YoY | 판가YoY | 판가절대값 | 신호 |
|------|--------|--------|---------|-----|

---

## 증권사 컨센서스
| 증권사 | TP | 의견 | 날짜 | 변화 |
|--------|-----|------|------|------|

---

## 수주잔고 흐름
| 분기 | 수주잔고 | QoQ | 신호 |
|------|---------|-----|------|

---

## 수급 흐름
| 날짜 | 오실레이터 | 빈집등급 | 백분위 | 5일방향 | 탑픽점수 변화 |
|------|---------|--------|-------|--------|------------|
| — | — | — | — | — | supply 데이터 ingest 필요 |

---

## ⚠️ 충돌·모순
(현재 없음)

---

## 관련 페이지
- [[L5_섹터/{sector}/index]] — 섹터 종합
"""

_counts = {"ok": 0, "dup": 0, "skip": 0, "new": 0}
_pending = []


def load_map() -> dict:
    if not MAP_FILE.exists():
        print("⚠️  sector_map.json 없음. 모두 미처리로 분류됩니다.")
        return {}
    return json.loads(MAP_FILE.read_text(encoding="utf-8"))


def ensure_file(name: str, code: str, sector: str) -> Path:
    p = WIKI / sector / "stock" / f"stock_{name}.md"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            TEMPLATE.format(name=name, code=code or "코드확인필요",
                            sector=sector, date=DATE),
            encoding="utf-8"
        )
        _counts["new"] += 1
        print(f"    [신규생성] stock_{name}.md")
    return p


def insert_after_divider(path: Path, section: str, row: str) -> bool:
    """## section 아래 테이블의 |---|---| 구분선 바로 다음에 row 삽입. 중복이면 False."""
    text = path.read_text(encoding="utf-8")

    # 중복 확인: 앞 3개 열을 조합한 키 (단일 열보다 훨씬 정확)
    # 증권사 컨센서스: "NH투자증권|310,000원|—"
    # 최신 이벤트:    "2026-05-26|내용|출처"
    # 수주잔고:       "1Q26|123,456백만원|8.34%"
    cells = [c.strip() for c in row.split("|") if c.strip()]
    dup_key = "|".join(cells[:3]) if len(cells) >= 3 else row[:60]
    if dup_key in text:
        _counts["dup"] += 1
        return False

    lines = text.splitlines(keepends=True)
    sec = next((i for i, l in enumerate(lines)
                if l.strip().startswith(section)), None)
    if sec is None:
        _counts["skip"] += 1
        return False

    div = next((i for i in range(sec + 1, min(sec + 12, len(lines)))
                if re.match(r"^\s*\|[-:\s|]+\|\s*$", lines[i])), None)
    if div is None:
        _counts["skip"] += 1
        return False

    lines.insert(div + 1, row + "\n")
    path.write_text("".join(lines), encoding="utf-8")
    _counts["ok"] += 1
    return True


def parse_pipe_rows(text: str) -> tuple:
    """파이프 구분 테이블 파싱 → (헤더, [행 목록])"""
    header = []
    rows = []
    in_code = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if "|" not in s:
            continue
        if re.match(r"^[|\-:\s]+$", s):
            continue
        parts = [p.strip() for p in s.split("|")]
        parts = [p for p in parts if p != ""]
        if not parts:
            continue
        if not header:
            header = parts
        else:
            rows.append(parts)
    return header, rows


def get_section(text: str, tag: str) -> str:
    """[tag] 섹션 추출"""
    m = re.search(r"\[" + re.escape(tag) + r"\]", text)
    if not m:
        return ""
    start = m.start()
    nxt = re.search(r"\n\[|\n\*\*\[|\Z", text[start + 1:])
    end = start + 1 + (nxt.start() if nxt else len(text))
    return text[start:end]


def fmt_num(s: str) -> str:
    try:
        return f"{int(s.replace(',', '')):,}"
    except Exception:
        return s


def add_pending(kind: str, name: str, **kw):
    _pending.append({"종류": kind, "종목": name, "날짜": DATE, **kw})
    _counts["skip"] += 1


# ─────────────────────────────────────────────
# [1/5] 추정이익 변화
# ─────────────────────────────────────────────
def proc_추정이익(smap: dict):
    f = DAILY / f"{TODAY}_추정이익_변화.md"
    if not f.exists():
        print("\n[1/5] 추정이익 파일 없음 — skip")
        return
    text = f.read_text(encoding="utf-8")
    print("\n[1/5] 추정이익...")

    for tag, arrow in [("TP_Up", "↑"), ("TP_Down", "↓")]:
        sec = get_section(text, tag)
        if not sec:
            continue
        _, rows = parse_pipe_rows(sec)
        for r in rows:
            if len(r) < 4:
                continue
            name, firm, tp_raw, pct = r[0], r[1], r[2].replace(",", ""), r[3]
            m = re.match(r"(\d+)→(\d+)", tp_raw)
            if not m:
                continue
            old_tp, new_tp = m.group(1), m.group(2)
            if name not in smap:
                add_pending(tag, name, 증권사=firm, TP=fmt_num(new_tp), 변화=pct)
                continue
            info = smap[name]
            p = ensure_file(name, info.get("코드", ""), info["섹터"])
            row = (f"| {firm} | {fmt_num(new_tp)}원 | — | {DATE} "
                   f"| {arrow} ({fmt_num(old_tp)} → {fmt_num(new_tp)}, {pct}) |")
            if insert_after_divider(p, "## 증권사 컨센서스", row):
                print(f"    {tag} {name}  {firm} {pct}")

    for tag, arrow in [("Rating_Up", "↑"), ("Rating_Down", "↓")]:
        sec = get_section(text, tag)
        if not sec:
            continue
        _, rows = parse_pipe_rows(sec)
        for r in rows:
            if len(r) < 4:
                continue
            name, firm, change, date_ = r[0], r[1], r[2], r[3]
            new_grade = change.split("→")[-1].strip()
            if name not in smap:
                add_pending(tag, name, 증권사=firm, 변화=change)
                continue
            info = smap[name]
            p = ensure_file(name, info.get("코드", ""), info["섹터"])
            row = f"| {firm} | — | {new_grade} | {date_ or DATE} | {arrow} Rating ({change}) |"
            if insert_after_divider(p, "## 증권사 컨센서스", row):
                print(f"    {tag} {name}  {firm} {change}")

    sec = get_section(text, "신규커버리지")
    if sec:
        _, rows = parse_pipe_rows(sec)
        for r in rows:
            if len(r) < 4:
                continue
            name, firm, grade, tp = r[0], r[1], r[2], r[3]
            if name not in smap:
                add_pending("신규커버리지", name, 증권사=firm, 등급=grade, TP=tp)
                continue
            info = smap[name]
            p = ensure_file(name, info.get("코드", ""), info["섹터"])
            tp_clean = tp.replace(",", "").replace("원", "").strip()
            tp_str = f"{fmt_num(tp_clean)}원" if tp_clean.isdigit() else tp
            row = f"| {firm} | {tp_str} | {grade} | {DATE} | 신규 커버리지 |"
            if insert_after_divider(p, "## 증권사 컨센서스", row):
                print(f"    신규커버리지 {name}  {firm} {grade}")


# ─────────────────────────────────────────────
# [2/5] 컨센서스 변화
# ─────────────────────────────────────────────
def proc_컨센(smap: dict):
    f = DAILY / f"{TODAY}_컨센_변화.md"
    if not f.exists():
        print("\n[2/5] 컨센서스 파일 없음 — skip")
        return
    text = f.read_text(encoding="utf-8")
    print("\n[2/5] 컨센서스...")

    sec = get_section(text, "서프라이즈")
    if sec:
        _, rows = parse_pipe_rows(sec)
        for r in rows:
            if len(r) < 5:
                continue
            name, rate, actual, cons, qtr = r[0], r[1], r[2], r[3], r[4]
            if name not in smap:
                add_pending("서프라이즈", name, 서프라이즈율=rate)
                continue
            info = smap[name]
            p = ensure_file(name, info.get("코드", ""), info["섹터"])
            row = (f"| {DATE} | {qtr} 어닝서프: 실적 {actual} vs 컨센 {cons} "
                   f"(서프라이즈율 {rate}) | raw/매일요약/{TODAY}_컨센_변화.md | 🔴 |")
            if insert_after_divider(p, "## 최신 이벤트", row):
                print(f"    서프라이즈 {name}  {rate}")

    sec = get_section(text, "쇼크")
    if sec:
        _, rows = parse_pipe_rows(sec)
        for r in rows:
            if len(r) < 5:
                continue
            name, rate, actual, cons, qtr = r[0], r[1], r[2], r[3], r[4]
            if name not in smap:
                add_pending("어닝쇼크", name, 쇼크율=rate)
                continue
            info = smap[name]
            p = ensure_file(name, info.get("코드", ""), info["섹터"])
            row = (f"| {DATE} | {qtr} 어닝쇼크: 실적 {actual} vs 컨센 {cons} "
                   f"(쇼크율 {rate}) | raw/매일요약/{TODAY}_컨센_변화.md | ⚠️ |")
            if insert_after_divider(p, "## 최신 이벤트", row):
                print(f"    쇼크 {name}  {rate}")

    sec = get_section(text, "컨센상향")
    if sec:
        _, rows = parse_pipe_rows(sec)
        for r in rows:
            if len(r) < 2:
                continue
            name, rate = r[0], r[1]
            change = r[2] if len(r) > 2 else ""
            if name not in smap:
                add_pending("컨센상향", name, 변화율=rate)
                continue
            info = smap[name]
            p = ensure_file(name, info.get("코드", ""), info["섹터"])
            row = f"| 컨센서스 합산 | — | — | {DATE} | 1개월 컨센상향 {rate} ({change}) |"
            if insert_after_divider(p, "## 증권사 컨센서스", row):
                print(f"    컨센상향 {name}  {rate}")

    sec = get_section(text, "컨센하향")
    if sec:
        _, rows = parse_pipe_rows(sec)
        for r in rows:
            if len(r) < 2:
                continue
            name, rate = r[0], r[1]
            if name not in smap:
                add_pending("컨센하향", name, 변화율=rate)
                continue
            info = smap[name]
            p = ensure_file(name, info.get("코드", ""), info["섹터"])
            row = f"| 컨센서스 합산 | — | — | {DATE} | 1개월 컨센하향 {rate} |"
            if insert_after_divider(p, "## 증권사 컨센서스", row):
                print(f"    컨센하향 {name}  {rate}")


# ─────────────────────────────────────────────
# [3/5] 일정·수주잔고
# ─────────────────────────────────────────────
def proc_일정수주(smap: dict):
    f = DAILY / f"{TODAY}_일정수주_변화.md"
    if not f.exists():
        print("\n[3/5] 일정·수주 파일 없음 — skip")
        return
    text = f.read_text(encoding="utf-8")
    print("\n[3/5] 일정·수주잔고...")

    sec = get_section(text, "수주잔고")
    if not sec:
        return
    _, rows = parse_pipe_rows(sec)
    for r in rows:
        if len(r) < 5:
            continue
        name, sector_hint, prev, curr, qoq = r[0], r[1], r[2], r[3], r[4]
        try:
            qoq_f = float(qoq.rstrip("%"))
        except Exception:
            qoq_f = 0
        if name not in smap:
            add_pending("수주잔고", name, 업종=sector_hint, QoQ=qoq)
            continue
        info = smap[name]
        p = ensure_file(name, info.get("코드", ""), info["섹터"])
        signal = "🔴" if qoq_f > 10 else "🟠" if qoq_f > 0 else "⚠️"
        curr_clean = curr.replace(",", "")
        row = f"| 1Q26 | {fmt_num(curr_clean)}백만원 | {qoq} | {signal} |"
        if not insert_after_divider(p, "## 수주잔고 흐름", row):
            ev = (f"| {DATE} | 수주잔고 1Q26 {fmt_num(curr_clean)}백만원 "
                  f"QoQ {qoq} | raw/매일요약/{TODAY}_일정수주_변화.md | {signal} |")
            insert_after_divider(p, "## 최신 이벤트", ev)
        print(f"    수주잔고 {name}  QoQ {qoq}")


# ─────────────────────────────────────────────
# [4/5] 투자아이디어
# ─────────────────────────────────────────────
def proc_투자아이디어(smap: dict):
    f = DAILY / f"{TODAY}_투자아이디어_변화.md"
    if not f.exists():
        print("\n[4/5] 투자아이디어 파일 없음 — skip")
        return
    text = f.read_text(encoding="utf-8")
    print("\n[4/5] 투자아이디어...")

    for line in text.splitlines():
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 3:
            continue
        name, qtr, memo = parts[0], parts[1], parts[2]
        if "장기" in qtr:
            continue
        if name in ("종목명",) or qtr in ("분기",):
            continue
        if name not in smap:
            add_pending("투자아이디어", name, 분기=qtr, 내용=memo[:30])
            continue
        info = smap[name]
        p = ensure_file(name, info.get("코드", ""), info["섹터"])
        file_text = p.read_text(encoding="utf-8")
        if qtr in file_text:
            _counts["dup"] += 1
            continue
        row = f"| {qtr} | {memo} | — | 📈 |"
        if insert_after_divider(p, "## 일정", row):
            print(f"    아이디어 {name}  {qtr}")


# ─────────────────────────────────────────────
# [5/5] 액티브ETF
# ─────────────────────────────────────────────
def proc_etf(smap: dict):
    f = DAILY / f"{TODAY}_액티브ETF_변화.md"
    if not f.exists():
        print("\n[5/5] 액티브ETF 파일 없음 — skip")
        return
    text = f.read_text(encoding="utf-8")
    print("\n[5/5] 액티브ETF...")

    m = re.search(r"공통편입 상위(.*?)(?=###|\Z)", text, re.DOTALL)
    if not m:
        return
    _, rows = parse_pipe_rows(m.group(0))
    for r in rows:
        if len(r) < 3:
            continue
        name, cnt, etf_list = r[0], r[1], r[2]
        if not cnt.isdigit():
            continue
        if name not in smap:
            add_pending("ETF편입", name, ETF수=cnt)
            continue
        info = smap[name]
        p = ensure_file(name, info.get("코드", ""), info["섹터"])
        short = etf_list[:60] + "..." if len(etf_list) > 60 else etf_list
        row = (f"| {DATE} | 액티브ETF {cnt}개 편입: {short} "
               f"| raw/매일요약/{TODAY}_액티브ETF_변화.md | 🟠 |")
        if insert_after_divider(p, "## 최신 이벤트", row):
            print(f"    ETF편입 {name}  {cnt}개")


# ─────────────────────────────────────────────
# 미처리 큐 저장
# ─────────────────────────────────────────────
def write_pending():
    if not _pending:
        return
    out = DAILY / f"{TODAY}_미처리.md"
    lines = [
        f"# 미처리 목록 — {DATE}\n\n",
        "sector_map.json 미등록 종목. Claude `/ingest` 시 섹터 등록 필요.\n\n",
        "| 종목 | 종류 | 데이터 |\n",
        "|------|------|--------|\n",
    ]
    for item in _pending:
        name = item.get("종목", "")
        kind = item.get("종류", "")
        data = " / ".join(f"{k}={v}" for k, v in item.items()
                          if k not in ("종목", "종류", "날짜"))
        lines.append(f"| {name} | {kind} | {data} |\n")
    out.write_text("".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────
# main
# ─────────────────────────────────────────────
def main():
    smap = load_map()
    print(f"\n{'━'*50}")
    print(f"  wiki_patch.py  {DATE}")
    print(f"{'━'*50}")

    proc_추정이익(smap)
    proc_컨센(smap)
    proc_일정수주(smap)
    proc_투자아이디어(smap)
    proc_etf(smap)
    write_pending()

    print(f"\n{'━'*50}")
    print(f"  반영 {_counts['ok']}건  중복 {_counts['dup']}건  "
          f"신규파일 {_counts['new']}개  미처리 {len(_pending)}건")
    if _pending:
        print(f"  → {TODAY}_미처리.md 확인 필요")
    print(f"{'━'*50}\n")


if __name__ == "__main__":
    main()
