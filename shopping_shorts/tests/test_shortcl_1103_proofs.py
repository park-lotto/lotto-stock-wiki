"""11-03 숏클 수리 증명 시험(관제 318, 대기실 전수조사 11-04).

같이 넣었던 시험 셋은 수리를 되돌려도 통과하거나(08·09) 이름 때문에만 실패했다(13), 14 는 시험이 없었다.
여기 시험은 전부 '수리를 되돌린 코드에서 실패'를 실측한 뒤 넣었다 — 결함이 다시 생기면 이 시험이 막는다.
"""
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from tools.calcopy.hybrid import material_fit as MF


def _gray(p: Path, sec: int = 10) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=64x64:d={sec}:r=30",
                    "-c:v", "libx264", "-preset", "ultrafast", str(p)], check=True)


@pytest.mark.parametrize("ss_b", [1.0, 1.5])
def test_08_reuse_only_cut_stays_when_another_shot_is_free(monkeypatch, tmp_path, ss_b):
    """A-08 f005627b5(김만기·김형관 팥→크림): 다른 샷에 빈자리가 있어도 재사용(B13, 경고)만 걸린 컷은 옮기지 않는다.
    빈 구간이 [0,3]·[5,10] 둘이어야 수리 전 코드가 5.4초(다른 샷)로 옮긴다 — 하나뿐이면 수리 전에도 못 옮겨 아무것도 안 잰다."""
    from tools.calcopy.hybrid import runner_ops as R
    _gray(tmp_path / "v.mp4")
    monkeypatch.setattr(R, "jump_free_spans", lambda src, spans, **k: [[0.0, 3.0], [5.0, 10.0]])
    monkeypatch.setattr(R, "_cut_jumps", lambda *a, **k: [])
    a = {"line": "E1", "t0": 0.0, "t1": 1.0, "dur": 1.0, "kind": "tts", "src": "v.mp4", "ss": 1.0}
    b = {"line": "E2", "t0": 1.0, "t1": 2.0, "dur": 1.0, "kind": "tts", "src": "v.mp4", "ss": ss_b, "reuse_unfixed": ["겹침"]}
    cuts = [a, b]
    MF.relocate_cuts(cuts, tmp_path, set(), log=lambda m: None, end=2.0)
    assert cuts == [a, b]
    assert b["ss"] == ss_b and "ss_moved" not in b


def test_09_engine_swap_waits_for_other_window_rent():
    """A-09 c1d656289(김효준 '판이 없다' 3번): 엔진 통째 교체(applyUpdate)는 engine/ 안의 빌린 판(styles)을 없앤다 —
    그래서 교체 신호와 받자마자 교체 둘 다 이 PC 어느 창이든 빌림 중(renting = rent.lock)이면 미뤄야 한다."""
    root = Path(__file__).resolve().parents[2] / "shortem_client" / "server"
    idx = (root / "index.js").read_text(encoding="utf-8")
    upd = (root / "updater.js").read_text(encoding="utf-8")
    swap = [ln for ln in idx.splitlines() if "process.send({ swap: 1 })" in ln]
    assert swap and all("!renting()" in ln for ln in swap), swap
    apply = [ln for ln in upd.splitlines() if ln.strip().startswith("applyDownloaded(")]
    assert apply and all("renting()" in ln for ln in apply), apply


def test_09_swap_really_drops_rented_styles(tmp_path):
    """09 의 전제 실측 — applyUpdate 가 engine 폴더를 바꾸면 빌린 판 폴더가 사라진다(이 전제가 바뀌면 위 미루기 판단도 다시 본다)."""
    probe = tmp_path / "probe.mjs"
    sup = (Path(__file__).resolve().parents[2] / "shortem_client" / "server" / "supervisor.js").as_uri()
    probe.write_text("""
import fs from 'node:fs'; import path from 'node:path';
const home = process.argv[2];
const mk = (p, t='x') => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, t); };
mk(path.join(home, 'engine/tools/calcopy/make.py'));
mk(path.join(home, 'engine/tools/calcopy/hybrid/styles/rented_v2/frame.json'));
mk(path.join(home, 'engine/tools/calcopy/hybrid/styles/.rented'));
mk(path.join(home, 'server/index.js'));
for (const d of ['server/index.js', 'engine/tools/calcopy/make.py']) mk(path.join(home, '_update/9.9.9', d));
mk(path.join(home, '_update/9.9.9/app_version.json'), '{"version":"9.9.9"}');
mk(path.join(home, '_update/pending.json'), JSON.stringify({ version: '9.9.9', dir: '9.9.9' }));
process.env.SHORTEM_HOME = home;
const S = await import(process.argv[3]);
const v = S.applyUpdate(home);
console.log(JSON.stringify({ v, after: fs.existsSync(path.join(home, 'engine/tools/calcopy/hybrid/styles/rented_v2/frame.json')) }));
""", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    r = subprocess.run(["node", str(probe), str(home), sup], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"v": "9.9.9", "after": False}


def test_13_basic_key_sends_basic_from_second_episode(tmp_path, monkeypatch):
    """A-13 c1ede660a(사장님 11-03): 고급이 거절된 키는 편 3개 = [고급,기본]·[기본]·[기본]. 수리 전 = 편마다 [고급,기본]."""
    from tools.calcopy import vmake_clean as VC
    kf = tmp_path / "vmake"
    kf.write_text("old:key", encoding="utf-8")
    monkeypatch.setattr(VC, "MEMBER_KEY_FILE", kf)
    if hasattr(VC, "TIER_FILE"):
        monkeypatch.setattr(VC, "TIER_FILE", tmp_path / "vmake.tier")
    monkeypatch.setattr(VC, "paid_off", lambda: False)
    monkeypatch.delenv("VMAKE_API_KEY", raising=False)
    sent = []

    def remove_subtitles(src, key, dst, tier="pro", resume_key=""):
        sent.append(tier)
        if tier != "basic":
            raise RuntimeError("Switch to New API")
        open(dst, "wb").write(b"x")
    fake = types.SimpleNamespace(remove_subtitles=remove_subtitles)
    import shopping_shorts
    monkeypatch.setitem(sys.modules, "shopping_shorts.vmake_client", fake)
    monkeypatch.setattr(shopping_shorts, "vmake_client", fake, raising=False)
    monkeypatch.setattr(VC, "swap_in", lambda f, tmp: None)
    monkeypatch.setattr(VC, "log_entry", lambda *a, **k: None)
    monkeypatch.setattr(VC, "_sent", lambda f: {})
    f = tmp_path / "a.mp4"
    f.write_bytes(b"v")
    eps = []
    for _ in range(3):
        sent.clear()
        VC.member_clean([f], "old:key", log=lambda *_: None, tier="pro")
        eps.append(list(sent))
    assert eps == [["pro", "basic"], ["basic"], ["basic"]]


def test_14_erase_gate_counts_text_under_blur(tmp_path):
    """A-14 5ae67c81c(#3344·#3445 김준용 VMake 0회): 지우는 판 관문④는 흐림 칸에 덮인 글자도 지울 컷으로 센다.
    진짜 영상·진짜 글자 인식 — 수리 전 코드는 흐림 칸이 있으면 erase [] (VMake 0회)."""
    from tools.calcopy.hybrid import render_bench as RB
    cand = tmp_path / "cand"
    cand.mkdir()
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
    if not font.exists():
        pytest.skip("글자 박을 글꼴 없음")
    (tmp_path / "f.ttf").write_bytes(font.read_bytes())       # drawtext 는 짧은 상대 경로가 안전하다(드라이브 콜론·한글 경로)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x406080:s=720x1280:d=6:r=30",
                    "-vf", "drawtext=fontfile=f.ttf:text='COSTCO SALE 13990 WON':fontsize=64:fontcolor=white:borderw=4:x=(w-tw)/2:y=1050",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cand / "a.mp4")], check=True, cwd=tmp_path)
    T = {"cuts": [{"src": "a.mp4", "ss": 1.0, "t0": 0.0, "t1": 2.0, "dur": 2.0, "line": "L1", "kind": "tts"}], "end": 2.0}
    st = {"frame": {"kind": "window", "window": [0, 0, 720, 1280]}}
    got = {}
    for name, blur in (("plain", None), ("blurred", [[0, 1000, 720, 180, 0.0, 6.0]])):
        M = {"cand_dir": str(cand)}
        if blur:
            M["blur"] = {"a.mp4": blur}
        erase = []
        RB.cut_content_gate(T, M, st, None, None, log=lambda *a: None, erase=erase)
        got[name] = erase
    assert got["plain"] == [0], got          # 글자 인식이 이 글자를 잡는다(못 잡으면 아래 비교가 아무것도 안 잰다)
    assert got["blurred"] == [0], got
