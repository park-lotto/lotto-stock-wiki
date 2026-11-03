# -*- coding: utf-8 -*-
"""숏클 썰템쇼 PC 제작 라인 — 짤 단계(PC 10편 편당 짤 2~5개, 회원은 0개였다 — 수리자료 3-3).
  · 서버 claude_flow.sign_memes: 지시서 do memes{stems} → 받을 주소·지문(claude_assets 'meme:<번호>', 짝 = hybrid/meme_catalog.json)
  · 회원 PC runner_ops.c_memes: 받아 지문 대조(다르면 버림) + 후보 시트"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shopping_shorts import claude_flow as cf  # noqa: E402
from shopping_shorts.tests.test_claude_portal import env  # noqa: E402,F401 — pytest 픽스처
from tools.calcopy.hybrid import runner_ops as RO  # noqa: E402

CAT = json.loads((ROOT / "tools/calcopy/hybrid/meme_catalog.json").read_text(encoding="utf-8"))["memes"]


def test_catalog_covers_pc_memes():
    stems = {m["stem"] for m in CAT}
    assert len(CAT) >= 1000 and {"fm_travolta", "gfr_Xh3A"} <= stems          # PC 작품1 이 쓴 짤
    assert all(m["asset"].startswith("meme:") for m in CAT)


def test_sign_memes(env, monkeypatch):
    monkeypatch.setattr(cf, "engine_root", lambda: ROOT)        # 시험 저장소 대신 이 트랙(짤 목록이 있는 엔진)
    m = CAT[0]
    cf.CP.upsert_asset(env["store"], m["asset"], "meme", m["stem"] + ".mp4", "ab" * 32, 10, grp=m["tone"])
    res = {"do": [{"id": "memes", "cmd": "memes", "stems": [m["stem"], "없는짤"]}, {"id": "env", "cmd": "env"}]}
    cf.sign_memes(res, 7, "s1", env["store"])
    it = res["do"][0]["items"]
    assert [x["stem"] for x in it] == [m["stem"]] and it[0]["sha256"] == "ab" * 32 and it[0]["url"].startswith("/api/claude/blob/")
    assert "stems" not in res["do"][0] and res["do"][1] == {"id": "env", "cmd": "env"}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_c_memes_download_verify_sheet(tmp_path):
    src = tmp_path / "x.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10:duration=1", "-pix_fmt", "yuv420p", str(src)], check=True)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    W = tmp_path / "W"
    r = RO.c_memes(W, {"items": [{"stem": "ok1", "url": src.as_uri(), "sha256": sha, "tone": "놀람"},
                                 {"stem": "bad1", "url": src.as_uri(), "sha256": "00" * 32}]})
    assert r["got"] == ["ok1"] and r["fail"] == {"bad1": "지문 다름"}
    assert (W / "memes" / "ok1.mp4").exists() and not (W / "memes" / "bad1.mp4").exists()
    assert r["sheet"] and (W / r["sheet"]).exists()
