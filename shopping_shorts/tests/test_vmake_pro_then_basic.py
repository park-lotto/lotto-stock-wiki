# -*- coding: utf-8 -*-
"""사장님 11-03 'VMake 고급 있음 고급으로, 없음 기본으로' — 회원 PC 는 등급이 pro 고정이라 옛 키(new_api)·Pro 아님(not_pro) 회원 6명이
전부 실패해 흐림으로 갔고(이정민·홍광수·김형관·한정수·임수정), 확정 실패 기록이 다음 편까지 흐림에 묶었다.
member_clean: 고급이 그 두 가지로 거절되면 같은 조각을 기본으로 한 번 더. bad_key·note_hard: 두 가지는 확정 실패로 치지 않는다."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy import vmake_clean as VM  # noqa: E402
from shopping_shorts import vmake_client as VC  # noqa: E402


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
@pytest.mark.parametrize("why", ["고급 자막제거(Smart Pro)는 VMake 새 API 키가 필요합니다. VMake 대시보드에서 'Switch to New API'로 전환한 뒤",
                                 "ConsumeDeniedError 60001"])
def test_pro_refused_then_basic(tmp_path, monkeypatch, why):
    f = tmp_path / "a__vm_0.00_1.00.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10:duration=1", "-pix_fmt", "yuv420p", str(f)], check=True)
    seen = []

    def fake(src, key, out, tier="basic", resume_key=None, **kw):
        seen.append(tier)
        if tier == "pro":
            raise RuntimeError(why)
        shutil.copy(src, out)
        return out
    monkeypatch.setattr(VC, "remove_subtitles", fake)
    monkeypatch.delenv("SHORTEM_NO_PAID", raising=False)
    r = VM.member_clean([f], "ak:sk", log=lambda *a: None, tier="pro")
    assert seen == ["pro", "basic"] and r["cleaned"] == [f.name] and not r["fail"], (seen, r)


def test_other_failure_not_retried(tmp_path, monkeypatch):
    f = tmp_path / "b.mp4"
    f.write_bytes(b"x")
    seen = []
    monkeypatch.setattr(VC, "remove_subtitles", lambda src, key, out, tier="basic", resume_key=None, **kw: seen.append(tier) or (_ for _ in ()).throw(RuntimeError("10021 sign not equals")))
    monkeypatch.delenv("SHORTEM_NO_PAID", raising=False)
    r = VM.member_clean([f], "ak:sk", log=lambda *a: None, tier="pro")
    assert seen == ["pro"] and f.name in r["fail"]


def test_old_basic_ok_record_does_not_lock_blur(tmp_path, monkeypatch):
    monkeypatch.setattr(VM, "BAD_KEY_FILE", tmp_path / "bad.json")
    monkeypatch.setattr(VM, "member_key", lambda: "ak:sk")
    for kind, want in (("new_api", ""), ("not_pro", ""), ("sign", "sign")):
        (tmp_path / "bad.json").write_text(json.dumps({"fp": VM._key_fp("ak:sk"), "kind": kind}), encoding="utf-8")
        assert VM.bad_key() == want, kind
