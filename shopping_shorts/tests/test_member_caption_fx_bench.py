"""11-05 문인석·박은숙: 회원 설정 자막 칸(text.caption.enter·emphasis·outline_px·outline_rgb)·자막팩 선택이 저장 관문(preview_request.check)은
통과하는데 bench 렌더 스냅샷(render_bench.snapshot)에 안 닿았다 — 주인 = styles.member_frame(회원 값 → 판), 그리는 쪽 = precision20-ui.js captionOverride.
렌더 입력 스냅샷과 렌더러 팩 고치기 결과로 잰다."""
import json
import subprocess
from pathlib import Path

import pytest

from tools.calcopy import preview_request as PR
from tools.calcopy.hybrid import render_bench as RB, styles as STY

ROOT = Path(__file__).resolve().parents[2]
V = "이븐쇼핑판"          # bench 판(자막팩 evenshopping)


def _load(tmp_path, monkeypatch, member):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"member": member}), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(p))
    return STY.load(V)


def test_회원_자막_등장_외곽선_강조_자막팩이_스냅샷에(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTEM_MEMBER_PACK", raising=False)
    before = RB.snapshot(STY.load(V))
    st = _load(tmp_path, monkeypatch, {"text": {"caption_pack": "hottemreport", "caption": {
        "enter": {"kind": "pop", "ms": 250}, "emphasis": {"words": "auto", "style": "color", "rgb": [255, 0, 0]},
        "outline_px": 8, "outline_rgb": [255, 255, 255]}}})
    snap = RB.snapshot(st)
    assert before["captionPack"] != "hottemreport" and snap["captionPack"] == "hottemreport"
    ov = snap.get("captionOverride") or {}
    assert ov.get("enter") == {"kind": "pop", "ms": 250}
    assert ov.get("outline") == {"px": 8, "rgb": "#FFFFFF"}
    assert snap["wordFx"] == {"style": "mark", "color": "#FF0000", "grow": ""}      # 핵심 단어 색칠은 그대로, 색만 회원 색


def test_강조_없음_키우기_밑줄(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, {"text": {"caption": {"emphasis": "none"}}})
    assert RB.snapshot(st)["wordFx"]["style"] == ""
    st = _load(tmp_path, monkeypatch, {"text": {"caption": {"emphasis": {"words": "auto", "style": "grow", "rgb": [0, 0, 255]}}}})
    assert RB.snapshot(st)["wordFx"] == {"style": "mark", "color": "#0000FF", "grow": "pop"}
    st = _load(tmp_path, monkeypatch, {"text": {"caption": {"emphasis": {"words": "auto", "style": "underline", "rgb": [0, 0, 255]}}}})
    assert RB.snapshot(st)["wordFx"]["style"] == "underline"


def test_등장_없음(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, {"text": {"caption": {"enter": "none"}}})
    assert RB.snapshot(st)["captionOverride"]["enter"]["kind"] == "none"


def test_bench_쌓기_칸은_안_닿는다고_알린다(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, {"text": {"caption": {"mode": "replace"}}})
    assert any("mode" in m for m in st.get("member_unused") or [])


def test_자막팩_칸_저장_관문():
    cat = PR.catalog()
    assert "hottemreport" in cat["caption_packs"]
    assert PR.check({"text": {"caption_pack": "hottemreport"}}, cat) == []
    assert PR.check({"text": {"caption_pack": "없는팩"}}, cat)


def _js(pack, ov):
    src = (ROOT / "out" / "precision20-ui.js").read_text(encoding="utf-8")
    i = src.index("{const ov=saved&&saved.captionOverride")
    j = src.index("sceneContext=context;", i)
    js = f"const CAPTION_PACKS={{p:{json.dumps(pack)}}};const saved={{captionPack:'p',captionOverride:{json.dumps(ov)}}};{src[i:j]};console.log(JSON.stringify(CAPTION_PACKS.p))"
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


def test_렌더러가_외곽선_등장을_팩에_입힌다():
    pk = {"size": 100, "text": {"color": "#fff", "style": {"WebkitTextStroke": "0.2em #000000", "paintOrder": "stroke fill"}},
          "emph": {"size": 150, "style": {"WebkitTextStroke": "0.2em #000000"}},
          "variants": {"hook": {"enter": "itlHookPop", "text": {"style": {"WebkitTextStroke": "0.1em #111111"}}}}, "speakers": {"narr": {"enter": "typeFlash"}},
          "motion": {"body": "overPop"}}
    out = _js(pk, {"outline": {"px": 8, "rgb": "#FFFFFF"}, "enter": {"kind": "pop", "ms": 250}})
    assert out["text"]["style"]["WebkitTextStroke"] == "0.16em #FFFFFF"
    assert out["emph"]["style"]["WebkitTextStroke"] == "0.16em #FFFFFF"
    assert out["variants"]["hook"]["text"]["style"]["WebkitTextStroke"] == "0.16em #FFFFFF"
    assert out["enter"] == out["variants"]["hook"]["enter"] == out["speakers"]["narr"]["enter"] == {"kind": "pop", "ms": 250}
    out = _js({"size": 100, "text": {"style": {"WebkitTextStroke": "0.2em #000000"}}}, {"outline": {"px": 0}})
    assert "WebkitTextStroke" not in out["text"]["style"]
    out = _js({"size": 100, "text": {"style": {"WebkitTextStroke": "0.2em #000000"}}}, {"outline": {"rgb": "#FF0000"}})
    assert out["text"]["style"]["WebkitTextStroke"] == "0.2em #FF0000"     # 굵기는 팩 그대로, 색만


def test_고정_색칠도_회원_키우기를_읽는다():
    src = (ROOT / "out" / "precision20-ui.js").read_text(encoding="utf-8")
    assert "WORD_FX_GROWS[m.grow||wordFx.grow]" in src
