"""칸 편집 상태 복원 = scene_play.js screenStateFromServer / applyScreenState 한 곳(관제 148, 2026-10-06).

사고: 서버 편성 → 화면 상태 되살리기가 세 벌(서버 컷 러너 · 화면 restoreServer · 제작소 큰 화면)이었고 벌마다 되살린 칸이
달랐다. 러너는 늘려 채우기(stretch_fill)를 안 읽어 화면에서 [전체 늘리기]를 켠 칸이 완성본엔 안 늘어난 채 나왔다
(실측 b5ee8d89bedb 칸 3·4·5, efbd5ca2173e 칸 2). 픽스처 = b5ee8d89bedb 칸 4 의 실제 화면 데이터.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
PLAY = HERE / "static" / "scene_play.js"
FX = Path(__file__).resolve().parent / "fixtures" / "screen_state_stretch_b5ee_beat4.json"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")


def _run(data, tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(PLAY), str(p)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)[0]["c"]


@node
def test_runner_reads_stretch_fill(tmp_path):
    """서버 러너(→ 완성본)가 늘려 채우기를 읽는다 — 화면에서 켠 칸이 완성본에서도 다르게 짜진다."""
    d = json.loads(FX.read_text(encoding="utf-8"))
    on = _run(d, tmp_path)
    d["beats"][0].pop("stretch_fill")
    off = _run(d, tmp_path)
    assert on != off, "늘려 채우기를 켜도 러너 컷이 같다 — 러너가 stretch_fill 을 안 읽는다"
    assert [(c["s"], c["d"]) for c in on] == [(16.02, 0.98), (17.001, 1.2)], on      # 서버 실측(2026-10-06)과 같은 값


@node
def test_runner_reads_trims_from_scene_lab_edits(tmp_path):
    """✂ 트림(plan.scene_lab.trims → DATA.scene_lab_edits)도 러너가 되살린다 — 안 하면 잘라 낸 구멍이 완성본에 되살아난다."""
    d = json.loads(FX.read_text(encoding="utf-8"))
    d["beats"][0].pop("stretch_fill")
    base = _run(d, tmp_path)
    d["scene_lab_edits"] = {"trims": {"film_s2_16.02_18.90": [0.3, 2.0]}, "merges": {}}
    cut = _run(d, tmp_path)
    assert cut != base, "트림을 줘도 러너 컷이 같다"
    for c in cut:
        assert not (16.32 + 1e-6 < c["s"] < 18.02 - 1e-6), ("잘라 낸 구멍 안에서 시작하는 컷", c)


def test_one_owner_for_screen_state():
    """되살리는 자리 셋이 같은 함수를 부르고, 칸별로 따로 적은 복원이 남아 있지 않다(0순위-B)."""
    runner = RUNNER.read_text(encoding="utf-8")
    lab = (HERE / "static" / "scene_lab.html").read_text(encoding="utf-8")
    prod = (HERE / "static" / "produce.html").read_text(encoding="utf-8")
    assert "applyScreenState(screenStateFromServer(DATA))" in runner
    body = lab.split("function restoreServer(")[1].split("\nfunction ")[0]
    assert "applyScreenState(screenStateFromServer(DATA))" in body
    prep = prod.split("function _sceneLabPrep(")[1].split("\nfunction ")[0]
    assert "applyScreenState(" in prep
    # 옛 칸별 복원이 되살아나면 실패 — 상태 전역에 서버 칸 값을 직접 넣는 꼴
    for src, name in ((runner, "runner"), (lab, "scene_lab.html"), (prod, "produce.html")):
        assert not re.search(r"PHRASE_SYNC\[i\]\s*=\s*false;\s*\}?\s*\)?;?.*b\.phrase_sync", src), name
        assert "function hydrateCuts(" not in src and "function fixlenFromBeats(" not in src, name
        assert "Object.assign(STRETCH," not in src, name


@node
def test_cleaned_beat_keeps_recorded_cuts_without_stretch(tmp_path):
    """청소 당시 컷 기록이 있는 칸은 늘려 채우기를 되살리지 않는다 — 청소본이 그 컷으로 지워졌다(라이브 실측 b5ee 5번 칸 0.6초 밀림)."""
    d = json.loads(FX.read_text(encoding="utf-8"))
    d["clean_cuts"] = {"0": [["s2", 16.02, 2.18]]}
    with_rec = _run(d, tmp_path)
    d["beats"][0].pop("stretch_fill")
    off = _run(d, tmp_path)
    assert with_rec == off, "청소 기록이 있는 칸인데 늘려 채우기로 컷이 바뀌었다"
