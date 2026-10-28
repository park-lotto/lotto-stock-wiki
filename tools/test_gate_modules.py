# -*- coding: utf-8 -*-
"""관문 모듈 목록 정본은 하나다(2026-10-03 관제 085) — 옛 6벌(사본)이 되살아나면 실패한다."""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate_modules as gm  # noqa: E402

USERS = ("video_gate.py", "editor_vs_final_video.py", "final_audio_audit.py", "capcut_export_audit.py", "clean_left_audit.py")


def test_도구들은_목록_사본을_두지_않는다():
    """모듈 이름을 3개 이상 늘어놓은 튜플·for 루프가 도구 안에 있으면 사본이다."""
    names = "|".join(gm.PATCH_MODULES)
    for f in USERS:
        src = (HERE / f).read_text(encoding="utf-8")
        for m in re.finditer(r"\(([^()]*)\)", src):
            hits = re.findall(r'"(%s)"' % names, m.group(1))
            assert len(set(hits)) < 3, "%s 에 모듈 목록 사본: %s" % (f, hits)


def test_감시_파일은_json_이_아니라_정본에서():
    import json
    cfg = json.loads((HERE / "gate_video.json").read_text(encoding="utf-8"))
    assert "watch_files" not in cfg, "gate_video.json 에 감시 목록 사본이 되살아났다"


def test_정본_목록은_모두_실재하고_서로_맞물린다():
    root = HERE.parent
    for rel in list(gm.PATCH_RELS.values()) + list(gm.TOOL_RELS):
        assert (root / rel).exists(), rel
    assert "tools/gate_modules.py" in gm.TOOL_RELS, "도구가 import 하므로 서버에 함께 올라가야 한다"
    assert set(gm.TOOL_RELS) <= set(gm.WATCH_FILES)
    assert "shopping_shorts/app.py" not in gm.WATCH_FILES, "app.py 는 함수 단위 판정으로 따로 본다"
    assert gm.PATCH_MODULES[0] == "config"


def test_적재는_PATCH_DIR_모듈을_얹고_경로를_되돌린다(tmp_path, monkeypatch):
    pd = tmp_path / "pd"
    pd.mkdir()
    (pd / "seg_snap.py").write_text("from pathlib import Path\nMARK = 'patched'\n_ROOT = Path(__file__).parent\n", encoding="utf-8")
    monkeypatch.chdir(HERE.parent)
    import shopping_shorts
    old = sys.modules.get("shopping_shorts.seg_snap")
    try:
        assert gm.load_patch_modules(str(pd)) == pd
        m = sys.modules["shopping_shorts.seg_snap"]
        assert m.MARK == "patched"
        assert Path(m._ROOT) == (HERE.parent / "shopping_shorts").resolve().parent, "파일 위치 기준 경로는 저장소로"
    finally:
        if old is not None:
            sys.modules["shopping_shorts.seg_snap"] = old
            shopping_shorts.seg_snap = old
        else:
            sys.modules.pop("shopping_shorts.seg_snap", None)
