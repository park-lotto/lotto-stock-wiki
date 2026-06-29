"""
yt_plan.py — 유튜브 발언카드 + 70/20/10 대본 골격

사용법:
    python -m pipeline.atoms.yt_plan "반도체 버블 고점"
    python -m pipeline.atoms.yt_plan "금리 인하 전망" --n 15
"""
import sys
import io
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .db import get_conn
from .vector_db import query_similar

_STANCE_KO = {
    "bullish": "강세",
    "bearish": "약세",
    "neutral": "중립",
    "risk": "리스크",
    "catalyst": "촉매",
    "conflict": "충돌",
}


def search_yt_atoms(topic: str, n: int = 20) -> list[dict]:
    """주제 유사 원자 검색 후 youtube만 필터."""
    atoms = query_similar(topic, n_results=n * 4)
    yt = [a for a in atoms if a.get("source_type") == "youtube"]
    # 부족하면 SQL fallback
    if len(yt) < 5:
        conn = get_conn()
        kw = topic.split()[0]
        rows = conn.execute(
            "SELECT * FROM atoms WHERE source_type='youtube' AND content LIKE ? LIMIT ?",
            (f"%{kw}%", n * 2),
        ).fetchall()
        conn.close()
        seen = {a["id"] for a in yt}
        for r in rows:
            d = dict(r)
            if d["id"] not in seen:
                yt.append(d)
    return yt[:n]


def build_speech_card_table(atoms: list[dict]) -> str:
    """발언카드 마크다운 표 생성."""
    if not atoms:
        return "_유튜브 발언 원자 없음 — `youtube_ingest` 실행 필요_"

    lines = [
        "| # | 화자 | 입장 | 핵심 발언 | 시간 | 채널 |",
        "|---|------|------|-----------|------|------|",
    ]
    for i, a in enumerate(atoms, 1):
        speaker = a.get("speaker") or a.get("source_name", "?")
        stance_raw = a.get("stance_key") or a.get("signal", "")
        stance = _STANCE_KO.get(stance_raw, stance_raw or "-")
        content = a.get("content", "")
        short = content[:65] + ("…" if len(content) > 65 else "")
        ts = a.get("yt_timestamp", "") or "-"
        deeplink = a.get("deeplink", "")
        link = f"[{ts}]({deeplink})" if deeplink else ts
        channel = a.get("source_name", "")
        lines.append(f"| {i} | {speaker} | {stance} | {short} | {link} | {channel} |")

    return "\n".join(lines)


def build_script_skeleton(topic: str, atoms: list[dict]) -> str:
    """70/20/10 대본 골격 생성."""
    bullish = [a for a in atoms if a.get("stance_key") in ("bullish", "catalyst")]
    bearish = [a for a in atoms if a.get("stance_key") in ("bearish", "risk")]
    neutral  = [a for a in atoms if a.get("stance_key") not in ("bullish", "catalyst", "bearish", "risk")]

    def quote(a: dict) -> str:
        speaker  = a.get("speaker") or a.get("source_name", "전문가")
        content  = (a.get("content") or "")[:80]
        deeplink = a.get("deeplink", "")
        ts       = a.get("yt_timestamp", "")
        link     = f"[{ts}]({deeplink})" if deeplink else (ts or "")
        return f'  > "{content}…" — **{speaker}** {link}'

    bullish_block = "\n".join(quote(a) for a in bullish[:3]) or "  _(없음)_"
    bearish_block = "\n".join(quote(a) for a in bearish[:3]) or "  _(없음)_"
    neutral_block = "\n".join(quote(a) for a in neutral[:2])  or "  _(없음)_"

    return f"""## 영상 대본 골격 — {topic}

---

### [S1 Hook / 0~5초]
> "{topic}, 전문가들은 지금 뭐라고 할까요? 결론부터 드릴게요."

---

### [S2~S5 본문 70% — 순수 정보 / 서비스 언급 금지]

**강세 논거** ({len(bullish)}건)
{bullish_block}

**약세·리스크 논거** ({len(bearish)}건)
{bearish_block}

**중립·조건부** ({len(neutral)}건)
{neutral_block}

---

### [S6~S7 간접 노출 20% — "나는 이렇게 본다"]
> 방법론·프레임만. "제 수급 빈집 기준으로는…" / "저는 이 발언에서 이것을 봤어요"
> ⚠️ 서비스명·CTA 이 구간 금지

---

### [S8 CTA 10% — 단 한 번]
> "이런 분석 매일 받고 싶으시면 → [서비스명] 프로필 링크"
> 구독 / 알림 설정

---
_📌 발언카드 {len(atoms)}개 | atoms.db youtube 원자 기반_
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", help="검색 주제 (예: '반도체 버블 고점')")
    parser.add_argument("--n", type=int, default=15, help="최대 발언카드 수 (기본 15)")
    args = parser.parse_args()

    print(f"\n🔍 [{args.topic}] 유튜브 발언 검색 중...\n")
    atoms = search_yt_atoms(args.topic, args.n)
    print(f"✅ {len(atoms)}개 원자 발견\n")
    print("## 발언카드\n")
    print(build_speech_card_table(atoms))
    print()
    print(build_script_skeleton(args.topic, atoms))


if __name__ == "__main__":
    main()
