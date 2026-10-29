"""관제 272 — 사이드바 '내 작업' 진행바가 제작소 단계 순서와 같고, 완성한 작업은 done 으로 내려간다."""
import re
from pathlib import Path

from shopping_shorts.store import Store

STATIC = Path(__file__).resolve().parents[1] / "static"


def _orb(src, where):
    m = re.search(r"ORB_TO_PANEL\s*=\s*\[([0-9,\s]+)\]", src)
    assert m, f"{where}에 ORB_TO_PANEL 이 없다"
    return [int(x) for x in m.group(1).split(",")]


def test_sidebar_orb_order_matches_produce():
    side = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    prod = (STATIC / "produce.html").read_text(encoding="utf-8")
    assert _orb(side, "sidebar.js") == _orb(prod, "produce.html")


def test_list_marks_done_job(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    jid = "jdone0000001"
    st.create_mix_job(jid, ["https://x/1"], 30, "auto")
    st.update_mix_job(jid, status="done")
    wid = st.upsert_produce_work(None, {"script": "핫팩 대본"}, job_id=jid, step=0)
    wid2 = st.upsert_produce_work(None, {"script": "다른 대본"}, step=3)
    rows = {r["work_id"]: r for r in st.list_produce_works()}
    assert rows[wid]["done"] is True
    assert rows[wid2]["done"] is False
