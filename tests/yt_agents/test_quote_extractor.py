from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "yt_agents"))
import quote_extractor as qe

FIX = Path(__file__).parent / "fixtures"

def test_parse_vtt_basic():
    segs = qe.parse_vtt((FIX / "sample.ko.vtt").read_text(encoding="utf-8"))
    assert len(segs) == 2
    assert segs[0].start == 12.0
    assert segs[0].text == "HBM 공급부족은 최소 내년까지 갑니다"
    assert segs[1].start == 220.5
    assert segs[1].text == "밸류 부담은 분명히 있습니다"   # 태그 제거됨

def test_to_mmss():
    assert qe.to_mmss(73.4) == "01:13"
    assert qe.to_mmss(220.5) == "03:40"
