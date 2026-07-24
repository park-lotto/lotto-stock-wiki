"""트렌드 검색카드(2026-07-24) — 소재추출·묶기·정렬 순수함수(node 드라이버)."""
import json
import pathlib
import shutil
import subprocess

import pytest

INDEX_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
NODE = shutil.which("node")

_START = "// ── 트렌드 검색카드(2026-07-24) ──"
_END = "// ── 트렌드 검색카드 끝 ──"


def _slice():
    src = INDEX_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_DRIVER = r"""
(function(){
  const items = [
    {vision_subject:'다이소 신상', title:'다이소 신상 털기', views:5000, platform:'instagram'},
    {vision_subject:'다이소 신상', title:'또 다이소', views:9000, platform:'tiktok'},
    {vision_subject:'', title:'집에서 만드는 베이글', views:3000, platform:'youtube'},
    {vision_subject:'', title:'', caption:'', views:100, platform:'instagram'},
  ];
  const groups = _groupBySubject(items);
  console.log(JSON.stringify({
    diso: groups.find(g=>g.subjectKo==='다이소 신상'),
    bagel: !!groups.find(g=>g.subjectKo && g.subjectKo.indexOf('베이글')>=0),
    total: groups.length,
    firstIsDiso: groups[0].subjectKo==='다이소 신상',
    likesFallback: _score({likes:200}),
    viewsWins: _score({views:5, likes:9999}),
  }));
})();
"""


@pytest.mark.skipif(NODE is None, reason="node 미설치")
def test_trend_card_functions():
    proc = subprocess.run([NODE, "-e", _slice() + _DRIVER],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    r = json.loads(proc.stdout)
    assert r["diso"]["platforms"] and len(r["diso"]["platforms"]) == 2
    assert r["diso"]["count"] == 2
    assert r["diso"]["maxScore"] == 9000
    assert r["bagel"] is True
    assert r["total"] == 2
    assert r["firstIsDiso"] is True
    assert r["likesFallback"] == 200
    assert r["viewsWins"] == 5
