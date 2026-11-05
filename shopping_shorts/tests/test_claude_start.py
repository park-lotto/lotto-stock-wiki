# -*- coding: utf-8 -*-
"""회원별 시작 한 줄·START.md(관제 294) — 파일에는 키 원문이 없고, 인증값으로 지금 키를 받되 옛 키를 끊지 않는다."""
import io
import zipfile

import pytest

from shopping_shorts import app as app_module
from shopping_shorts import claude_portal as cp
from shopping_shorts.store import Store


@pytest.fixture
def st(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_STORE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("CLAUDE_LICENSE_SECRET", "test-secret")
    store = Store(tmp_path / "t.db")
    store.set_setting("claude_portal_enabled", "1")
    return store


def test_인증값으로_지금_키를_받고_옛_키를_끊지_않는다(st):
    key = cp.issue_license(7, st)["key"]
    assert cp.start_redeem(cp.start_token(7), st)["key"] == key
    assert cp.verify_license(key, st)["cid"] == 7


def test_키가_없는_회원은_새로_발급(st):
    got = cp.start_redeem(cp.start_token(8), st)["key"]
    assert cp.verify_license(got, st)["cid"] == 8


def test_회수된_키는_되살리지_않고_새_키(st):
    key = cp.issue_license(9, st)["key"]
    new = cp.issue_license(9, st)["key"]
    assert cp.start_redeem(cp.start_token(9), st)["key"] == new != key


def test_파일에_키_원문이_없다(st):
    key = cp.issue_license(7, st)["key"]
    md = cp.start_md(7, "https://x.test")
    assert key not in md and "SHORTEM_START" in md
    with zipfile.ZipFile(io.BytesIO(cp.start_zip(7, "https://x.test"))) as z:
        body = z.read("START.md").decode("utf-8")
    assert key not in body and "SHORTEM_START" in body


@pytest.mark.parametrize("bad", ["", "x", "7.9999999999.abc", "a.b.c"])
def test_위조는_거절(st, bad):
    with pytest.raises(cp.PortalError) as e:
        cp.start_redeem(bad, st)
    assert e.value.code == "bad_key"


def test_다른_회원_번호로_바꾸면_거절(st):
    cid, exp, sig = cp.start_token(7).split(".")
    with pytest.raises(cp.PortalError):
        cp.start_redeem(f"8.{exp}.{sig}", st)


def test_기한_지나면_거절(st, monkeypatch):
    token = cp.start_token(7)
    monkeypatch.setattr(cp, "_now", lambda: int(token.split(".")[1]) + 1)
    with pytest.raises(cp.PortalError) as e:
        cp.start_redeem(token, st)
    assert e.value.code == "expired"


def test_스위치가_꺼지면_거절(st):
    st.set_setting("claude_portal_enabled", "")
    with pytest.raises(cp.PortalError) as e:
        cp.start_redeem(cp.start_token(7), st)
    assert e.value.code == "disabled"


def test_설치_스크립트에_주소가_채워지고_비밀이_없다():
    from fastapi.testclient import TestClient
    r = TestClient(app_module.app).get("/api/claude/start.ps1", headers={"host": "stmaker.kr"})
    assert r.status_code == 200 and "https://stmaker.kr" in r.text and "__BASE__" not in r.text and "SHORTEM-L1." not in r.text


def test_승인하면_열리고_해제하면_닫힌다(st, monkeypatch):
    monkeypatch.setattr(app_module, "_is_admin", lambda cid: False)
    st.set_setting("claude_portal_enabled", "admin")
    assert not app_module._setting_gate(st, "claude_portal_enabled", 7)
    cp.set_member(7, True, st)
    cp.set_member(11, True, st)
    assert app_module._setting_gate(st, "claude_portal_enabled", 7)
    assert not app_module._setting_gate(st, "claude_portal_enabled", 8)
    cp.set_member(7, False, st)
    assert not app_module._setting_gate(st, "claude_portal_enabled", 7)
    cp.set_member(11, False, st)
    assert st.get_setting("claude_portal_enabled", "") == "admin"


def test_전체_공개면_승인_목록을_덮지_않는다(st):
    with pytest.raises(cp.PortalError):
        cp.set_member(7, True, st)
    assert st.get_setting("claude_portal_enabled", "") == "1"


def test_회원_1번_승인이_전체_공개가_되지_않는다(st, monkeypatch):
    monkeypatch.setattr(app_module, "_is_admin", lambda cid: False)
    st.set_setting("claude_portal_enabled", "admin")
    cp.set_member(1, True, st)
    assert app_module._setting_gate(st, "claude_portal_enabled", 1)
    assert not app_module._setting_gate(st, "claude_portal_enabled", 2)
    cp.set_member(1, False, st)
    assert st.get_setting("claude_portal_enabled", "") == "admin"


def test_더블클릭_파일에_키_원문이_없다(st):
    key = cp.issue_license(7, st)["key"]
    body = cp.start_cmd(7, "https://x.test")
    assert key not in body and "SHORTEM_START" in body and body.startswith("@echo off")


def test_메뉴_스크립트에_비밀이_없다():
    from fastapi.testclient import TestClient
    r = TestClient(app_module.app).get("/api/claude/start_menu.ps1")
    assert r.status_code == 200 and "숏클 시작" in r.text and "SHORTEM-L1." not in r.text


# ── 맥 한 줄 설치(관제 328) ─────────────────────────────────────────────────────
def test_맥_설치_줄에_키_원문이_없고_인증값으로_키를_받는다(st):
    import re
    key = cp.issue_license(7, st)["key"]
    line = cp.start_line(7, "https://x.test", "mac")
    assert key not in line and "/api/claude/start.sh" in line and line.startswith("SHORTEM_START='")
    tok = re.match(r"SHORTEM_START='([^']+)'", line).group(1)
    assert cp.start_redeem(tok, st)["key"] == key
    assert cp.start_line(7, "https://x.test").startswith("$env:SHORTEM_START=")     # 윈도 줄은 그대로


def test_맥_설치_스크립트에_주소가_채워지고_비밀이_없다():
    from fastapi.testclient import TestClient
    r = TestClient(app_module.app).get("/api/claude/start.sh", headers={"host": "stmaker.kr"})
    assert r.status_code == 200 and r.text.startswith("#!/bin/bash")
    assert "https://stmaker.kr" in r.text and "__BASE__" not in r.text and "SHORTEM-L1." not in r.text


def test_맥_스크립트가_부르는_묶음_종류는_서버가_아는_것():
    from pathlib import Path
    body = (Path(app_module.__file__).resolve().parents[1] / "installer" / "install.sh").read_text(encoding="utf-8")
    for plat in ("mac-arm64", "mac-x64"):
        assert f"PLAT={plat}" in body and plat in cp.INSTALL_PLATS


def test_맥_엔진_부품_목록이_윈도_목록을_다_담는다():
    import re
    from pathlib import Path
    common = Path(app_module.__file__).resolve().parents[1] / "installer" / "common"
    norm = lambda n: re.sub(r"[-_.]+", "-", n).lower()
    win = {norm(n) for n in re.findall(r"(?m)^([A-Za-z0-9_.\-]+)==", (common / "requirements-engine-py312-win.txt").read_text(encoding="utf-8"))}
    mac = {norm(n) for n in re.findall(r"(?m)^([A-Za-z0-9_.\-]+)==", (common / "requirements-engine-py312-mac.txt").read_text(encoding="utf-8"))}
    assert win <= mac


def test_맥_묶음은_윈도_도구를_빼고_맥_목록을_넣는다(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(app_module.__file__).resolve().parents[1] / "tools" / "claude_portal"))
    import make_mac_bundle as mb
    src = tmp_path / "win.zip"
    with zipfile.ZipFile(src, "w") as z:
        for n in ("server/index.js", "server/license.js", "postinstall.js", "claude-plugin/shortem/x.json",
                  "engine/a.py", "tools/node/node.exe", "tools/tools.manifest.json", "server/vcrt/msvcp140.dll"):
            z.writestr(n, "x")
    rep = mb.build(src, tmp_path / "mac.zip")
    with zipfile.ZipFile(tmp_path / "mac.zip") as z:
        names = set(z.namelist())
    assert not any(n.startswith(("tools/", "server/vcrt/")) for n in names)
    assert {"engine/a.py", "mac/tools.lock.json", "mac/requirements-engine-py312-mac.txt", "mac/write_manifest.js"} <= names
    assert rep["dropped"] == 3


def test_맥_스크립트에_윈도_줄바꿈이_없다():
    # 윈도 PC 에서 고쳐 쓰다 CRLF 가 섞이면 맥 bash 가 깨진다(11-05 실사고 직전 발견)
    from pathlib import Path
    root = Path(app_module.__file__).resolve().parents[1] / "installer"
    for p in (root / "install.sh", root / "common" / "tools.lock.json", root / "common" / "requirements-engine-py312-mac.txt"):
        assert b"\r" not in p.read_bytes(), p.name


def test_맥_도구는_전부_sha256_으로_대조한다():
    import json
    from pathlib import Path
    lock = json.loads((Path(app_module.__file__).resolve().parents[1] / "installer" / "common" / "tools.lock.json").read_text(encoding="utf-8"))
    for plat in ("darwin-arm64", "darwin-x64"):
        for n in ("node", "chrome-headless-shell", "python", "ffmpeg", "ffprobe"):
            assert len(lock[plat][n].get("sha256") or "") == 64, (plat, n)
