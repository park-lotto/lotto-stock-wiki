"""클로드형 판 올리기(관제 234, 사장님 10-20 "지금해") — 이 PC 빌드 결과를 서버 claude_store 에 넣는다. 서버 git 작업 트리는 건드리지 않는다
(claude_store = shopping_shorts/data/claude_store, gitignore). 숏템MCP 병합(finish)이 라이브에 들어간 뒤에 돌린다(서버에 publish_update.py --install 필요).

  py tools/claude_portal/upload_release.py --dist <빌드>/dist --packs <프리셋 꾸러미 폴더> --version 1.0.0 [--dry]

올리는 것: ①프리셋 꾸러미 p_*.zip → preset_packs/ ②연결 파일 shortem.mcpb·Claude Code 꾸러미 → installers/ + manifest.json(페이지 ④ 두 칸)
          ③설치 묶음 shortem-win-x64-<판>.zip → publish_update.py --install(내용주소 assets/ + install/latest-win-x64.json)
확인: 라이브 /api/claude/install 이 키 없으면 막는가(창구가 살아 있나) · 서버 디스크 여유. 결과 JSON 한 줄.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HOST = "ubuntu@3.35.251.172"      # 바뀌면 nslookup shoppingshorts.duckdns.org (tools/live_admin.py 와 같은 자리)
KEY = os.path.join(os.path.expanduser("~"), "crawling_bot_client", "LightsailDefaultKey-ap-northeast-2.pem")
REPO = "/home/ubuntu/lotto-stock-wiki"
STORE = REPO + "/shopping_shorts/data/claude_store"
UPLOAD = "/home/ubuntu/claude_upload"
BASE = "https://shoppingshorts.duckdns.org"
MIN_FREE_GB = 4


def sh(args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        raise SystemExit(f"[upload] 실패: {' '.join(map(str, args[:3]))}… → {(r.stderr or r.stdout)[-400:]}")
    return r.stdout


def ssh(cmd):
    return sh(["ssh", "-o", "ConnectTimeout=20", "-i", KEY, HOST, cmd], timeout=1800)


def scp(files, dst):
    return sh(["scp", "-o", "ConnectTimeout=20", "-i", KEY, *map(str, files), f"{HOST}:{dst}"], timeout=3600)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True)
    ap.add_argument("--packs", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--dry", action="store_true", help="파일·서버 상태만 보고 올리지 않는다")
    a = ap.parse_args(argv)
    dist, packs = Path(a.dist), Path(a.packs)
    mcpb = dist / "shortem.mcpb"
    kit = dist / f"shortem-claude-code-win-x64-{a.version}.zip"
    pack = dist / f"shortem-win-x64-{a.version}.zip"
    presets = sorted(packs.glob("p_*.zip"))
    for f in (mcpb, kit, pack):
        if not f.is_file():
            raise SystemExit(f"[upload] 없음: {f}")
    if not presets:
        raise SystemExit(f"[upload] 프리셋 꾸러미 없음: {packs}")
    free = int(ssh("df -k --output=avail / | tail -1").strip()) / 1e6
    out = {"version": a.version, "presets": len(presets), "pack_mb": round(pack.stat().st_size / 1e6, 1), "server_free_gb_before": round(free, 1)}
    need = pack.stat().st_size * 2 / 1e9 + MIN_FREE_GB
    if free < need:
        raise SystemExit(f"[upload] 서버 디스크 여유 {free:.1f}GB < 필요 {need:.1f}GB — 먼저 치워야 합니다")
    n = ssh(f"grep -c -- '--install' {REPO}/tools/claude_portal/publish_update.py 2>/dev/null || echo 0").strip().splitlines()[-1]
    out["server_has_install_tool"] = n not in ("0", "")
    if not out["server_has_install_tool"] and not a.dry:
        raise SystemExit("[upload] 서버에 새 publish_update.py(--install)가 아직 없습니다 — 숏템MCP 병합이 라이브에 들어간 뒤 다시")
    if a.dry:
        print(json.dumps({**out, "dry": True}, ensure_ascii=False))
        return 0

    ssh(f"mkdir -p {STORE}/preset_packs {STORE}/installers {UPLOAD}")
    scp(presets, f"{STORE}/preset_packs/")
    items = [{"os": "desktop", "file": mcpb.name, "version": a.version, "sha256": sha256(mcpb), "size": mcpb.stat().st_size},
             {"os": "code-win-x64", "file": kit.name, "version": a.version, "sha256": sha256(kit), "size": kit.stat().st_size}]
    with tempfile.TemporaryDirectory() as td:
        mf = Path(td) / "manifest.json"
        mf.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
        scp([mcpb, kit, mf], f"{STORE}/installers/")
    local_sha = sha256(pack)
    scp([pack], f"{UPLOAD}/")
    pub = ssh(f"cd {REPO} && /usr/bin/python3 tools/claude_portal/publish_update.py --install {UPLOAD}/{pack.name} --plat win-x64 --version {a.version} && rm -f {UPLOAD}/{pack.name}")
    got = json.loads(pub.strip().splitlines()[-1])
    out["install_sha_match"] = got.get("sha256") == local_sha
    out["server_presets"] = int(ssh(f"ls {STORE}/preset_packs/p_*.zip | wc -l").strip())
    out["server_installers"] = ssh(f"ls {STORE}/installers").split()
    out["server_free_gb_after"] = round(int(ssh("df -k --output=avail / | tail -1").strip()) / 1e6, 1)
    try:   # 창구가 살아 있나 — 키 없이 부르면 막혀야 한다
        with urllib.request.urlopen(BASE + "/api/claude/install?plat=win-x64", timeout=20) as r:
            out["live_install_route"] = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        out["live_install_route"] = {"status": e.code, "body": json.loads(e.read().decode() or "{}")}
    out["ok"] = out["install_sha_match"] and out["server_presets"] >= len(presets) and {"shortem.mcpb", kit.name, "manifest.json"} <= set(out["server_installers"])
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
