# -*- coding: utf-8 -*-
"""프리셋 별칭(10-26) — 회원이 '키치잇 스타일로' 처럼 채널 이름으로 불러도 그 프리셋. 주인 = channel/프리셋.json bench_option·member.preset_name."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shopping_shorts import claude_portal as cp  # noqa: E402


def test_aliases_from_preset_ledger(tmp_path, monkeypatch):
    (tmp_path / "channel").mkdir()
    (tmp_path / "channel" / "프리셋.json").write_text(json.dumps({"presets": {
        "kitchit": {"bench_option": "키치잇", "member": {"preset_name": "연예인상품+후기형"}},
        "mantem": {"bench_option": "만템", "member": {"preset_name": "연예인상품+후기형"}},
        "banggu": {"bench_option": "방구석 친구들", "member": {"preset_name": "제품비하인드썰형(옛 길 설명)"}},
        "none": {"bench_option": "없음", "member": {"preset_name": None}}}}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CHANNEL_ROOT", str(tmp_path))
    al = cp.preset_aliases()
    assert al[cp._name_key("연예인상품+후기형")] == ["키치잇", "만템"]
    assert al[cp._name_key("제품비하인드썰형")] == ["방구석 친구들"]
    assert "없음" not in sum(al.values(), [])


def test_no_ledger_no_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CHANNEL_ROOT", str(tmp_path))
    assert cp.preset_aliases() == {}
