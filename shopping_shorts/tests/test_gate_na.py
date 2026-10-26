"""검수단축 ⑧(사장님 10-26 결정): 그 편에 원래 없는 칸 = 해당 없음(통과로 셈) · 잴 수 있는데 못 잰 칸 = 불합격(그대로).
옛 코드: 카드 없는 편(썸네일.json 없음·빈 3안)·문장부호 없는 대본도 '미측정'으로 품질 관문 미달 — 이 시험에서 실패한다."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import quality_gate as QG  # noqa: E402


def test_no_card_is_na_and_counts_as_pass(tmp_path):
    rows = []
    QG._row(rows, "썸네일", "썸네일 맨 앞 2프레임", lambda: QG.thumb_stamped(tmp_path / "x.mp4", tmp_path), "t")
    (tmp_path / "썸네일.json").write_text(json.dumps({"options": [], "auto": True}), encoding="utf-8")
    QG._row(rows, "썸네일", "빈 3안", lambda: QG.thumb_stamped(tmp_path / "x.mp4", tmp_path), "t")
    assert all(r["ok"] is True and r.get("na") and str(r["value"]).startswith(QG.NA) for r in rows)


def test_no_punctuation_is_na():
    ok, _ = QG.inline_pause_verdict([], {"comma": 0.22, "period": 0.3})
    assert ok == QG.NA


def test_unmeasured_still_fails():
    rows = []
    QG._row(rows, "소리", "받아쓰기", lambda: (None, "받아쓰기 안 함(--no-asr, 미측정)"), "x")
    QG._row(rows, "소리", "터짐", lambda: 1 / 0, "x")
    assert [r["ok"] for r in rows] == [None, None] and not any(r.get("na") for r in rows)
