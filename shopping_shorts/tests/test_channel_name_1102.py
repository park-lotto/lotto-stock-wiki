"""프리셋 채널 글자(관제 304): 회원이 넣으면 그 이름, 안 넣으면 비운다. 원래 채널 글자는 절대 안 나간다."""
import json

from tools.calcopy.hybrid import styles as ST


def _load(tmp_path, monkeypatch, name, brand):
    f = tmp_path / "pack.json"
    f.write_text(json.dumps({"member": {"brand": brand, "text": {}}}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(f))
    return ST.load(name)


def _bar_texts(st):
    return [i["text"] for i in ((st["frame"].get("post") or {}).get("head_bar") or {}).get("icons") or [] if i.get("kind") == "text"]


def test_no_name_no_brand_text(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, "썰템쇼판", {})
    assert _bar_texts(st) == [] and not st["frame"].get("logo") and not st["frame"].get("watermark")


def test_member_name_replaces_fixed_letters(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, "썰템쇼판", {"channel_name": "내채널"})
    assert _bar_texts(st) == ["내채널"]


def test_no_pack_keeps_original(monkeypatch):
    monkeypatch.delenv("SHORTEM_MEMBER_PACK", raising=False)
    assert _bar_texts(ST.load("썰템쇼판")) == ["썰", "템", "쇼"]


def test_guide_blocks_server_phrase_and_source_names():
    from pathlib import Path
    g = (Path(__file__).parents[2] / "installer/common/MEMBER_GUIDE.md").read_text(encoding="utf-8")
    assert "서버에서 막혔다" in g and "참고 채널 이름은 말하지 않는다" in g and "brand.channel_name" in g
