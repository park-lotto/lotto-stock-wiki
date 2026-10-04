# -*- coding: utf-8 -*-
"""관제 084(2026-10-04): 분석 캐시 길에서도 스토리를 쓰고(없으면 만들고) 캐시에 한 칸만 저장한다.
실측: 10-02 저녁 뒤 분석 영상 377개 중 스토리 0 — 손님 작업은 거의 캐시 길이었다."""
import inspect, json
from shopping_shorts import mix_pipeline as mp
from shopping_shorts.store import Store


def test_cache_path_carries_or_makes_story():
    src = inspect.getsource(mp)
    i = src.index("def _extract(item):")
    body = src[i:src.index("return vid, r", i)]
    assert 'r["story"] = cached.get("story")' in body and "_story_for(" in body and "save_extract_story(" in body


def test_save_extract_story_only_adds_story(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_script("abc", {"segments": [{"seg_id": "s0-0"}], "full_text": "x"}, category="레시피", method="m1")
    st.save_extract_story("abc", [{"text": "물만 쏙", "cuts": ["s0-0"]}])
    got = st.get_extract("abc")
    assert got["story"][0]["text"] == "물만 쏙" and got["segments"][0]["seg_id"] == "s0-0" and got["full_text"] == "x"
