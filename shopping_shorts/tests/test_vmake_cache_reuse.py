"""11-04 이성택 문의 '재작업으로 크레딧이 반복해서 빠지나' — 같은 원본으로 편을 새로 시작하면 앞 편에서 이미 VMake 로 지운 구간을 다시 보냈다
(지운 구간 기록 tf.done 은 편 상태에만, resume 장부는 작업 폴더 옆 24시간만). 판단 주인 = vmake_clean._cut_send(돈 드는 곳 한 곳):
보내기 전에 회원 PC 보관함에서 (원본 이름·크기·구간·길) 열쇠로 지운 조각을 찾아 그대로 쓰고, 나머지만 보낸다."""
import shutil
import subprocess
from pathlib import Path

from tools.calcopy import vmake_clean as VC


def _src(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    f = d / "abcdEFGH123.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=30:d=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)],
                   check=True, stdin=subprocess.DEVNULL)
    return f


def _fake(calls):
    def member_clean(files, api_key, log=print, tier=VC.TIER):
        calls.append([Path(f).name for f in files])
        return {"cleaned": [Path(f).name for f in files], "calls": len(files), "fail": {}}
    return member_clean


def test_같은_원본_새_편은_다시_보내지_않는다(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_VMAKE_CACHE", str(tmp_path / "cache"))
    calls = []
    monkeypatch.setattr(VC, "member_clean", _fake(calls))
    monkeypatch.setattr(VC, "member_key", lambda: "app:secret")
    rd = {"via": "member", "mode": "vmake"}
    spans = {"abcdEFGH123.mp4": [[1.0, 2.5], [3.0, 4.2]]}
    a = tmp_path / "ep1" / "src"
    shutil.copyfile(_src(tmp_path / "orig"), (a.mkdir(parents=True) or a) / "abcdEFGH123.mp4")
    _, r1 = VC._cut_send(a, spans, rd, None, log=lambda *_: None)
    assert calls and len(r1["cleaned"]) == 2
    b = tmp_path / "ep2" / "src"          # 새 편 = 새 작업 폴더, 같은 원본
    b.mkdir(parents=True)
    shutil.copyfile(tmp_path / "orig" / "abcdEFGH123.mp4", b / "abcdEFGH123.mp4")
    n = len(calls)
    _, r2 = VC._cut_send(b, spans, rd, None, log=lambda *_: None)
    assert len(calls) == n, "새 편이 이미 지운 구간을 다시 보냈다(크레딧 또 빠짐)"
    assert sorted(r2["cleaned"]) == sorted(r1["cleaned"]) and r2["calls"] == 0


def test_구간이_다르면_보낸다(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_VMAKE_CACHE", str(tmp_path / "cache"))
    calls = []
    monkeypatch.setattr(VC, "member_clean", _fake(calls))
    monkeypatch.setattr(VC, "member_key", lambda: "app:secret")
    rd = {"via": "member", "mode": "vmake"}
    a = tmp_path / "ep1"
    _src(a)
    VC._cut_send(a, {"abcdEFGH123.mp4": [[1.0, 2.5]]}, rd, None, log=lambda *_: None)
    n = len(calls)
    VC._cut_send(a, {"abcdEFGH123.mp4": [[3.0, 4.2]]}, rd, None, log=lambda *_: None)
    assert len(calls) == n + 1
