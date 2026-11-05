"""11-05 김효준 #6290: 회원 자막색(captionOverride.color)이 팩 화자 층(speakers) 색을 덮지 못해 narr 줄이 팩 노란색으로 나왔다(훅 변형 줄만 회원색).
렌더러(out/precision20-ui.js load)의 회원 값 적용 블록을 그대로 떼어 가짜 팩에 돌린다 — 색·세로 위치·크기가 variants 와 speakers 모두에 간다."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(pack, ov):
    src = (ROOT / "out" / "precision20-ui.js").read_text(encoding="utf-8")
    i = src.index("{const ov=saved&&saved.captionOverride")
    j = src.index("sceneContext=context;", i)
    block = src[i:j]
    js = f"const CAPTION_PACKS={{p:{json.dumps(pack)}}};const saved={{captionPack:'p',captionOverride:{json.dumps(ov)}}};{block};console.log(JSON.stringify(CAPTION_PACKS.p))"
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


def test_member_color_reaches_speaker_layer():
    pk = {"text": {"color": "#fff"}, "variants": {"hook": {"text": {"color": "#f00"}}}, "speakers": {"narr": {"text": {"color": "#ffd400"}}}}
    out = _run(pk, {"color": "#00aaff"})
    assert out["text"]["color"] == "#00aaff" and out["variants"]["hook"]["text"]["color"] == "#00aaff"
    assert out["speakers"]["narr"]["text"]["color"] == "#00aaff", "화자 층 색이 회원색으로 안 바뀌었다(narr 줄이 팩 색으로 나온다)"


def test_member_scale_and_dy_reach_speaker_layer():
    pk = {"size": 50, "place": {"y": 1400}, "speakers": {"narr": {"size": 40, "place": {"y": 1500}}}}
    out = _run(pk, {"scale": 1.5, "dy": 20})
    assert out["speakers"]["narr"]["size"] == 60 and out["speakers"]["narr"]["place"]["y"] == 1520
