"""편집 화면 합본(pvproxy) 서명 — 한 곳(_pvproxy_sig)에서, 칸 음성까지 싣는다(2026-09-27).

사고 꼴: 성우·톤만 바꾸면 resynth_one_beat 가 **같은 mp3 경로를 덮어쓰고** tts_ver 만 올린다.
서명에 음성이 없어 컷이 같으면 옛 목소리가 구워진 합본을 ready 로 줬다
(실측: 바꾼 뒤 mp3 -91dB 인데 합본은 -21.5dB 그대로). 그리고 서명이 화면 요청·미리굽기 두 벌이라
같은 편성을 서로 못 알아봤다(3자리+fit vs 2자리 내림).
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from shopping_shorts import app
from shopping_shorts import video_assemble as va

HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
APP_SRC = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def _ff(*a):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)


def _mp3(path, kind):
    src = "sine=frequency=440:duration=3" if kind == "loud" else "anullsrc=r=44100:cl=mono"
    tmp = str(path) + ".new.mp3"
    _ff("-f", "lavfi", "-i", src, "-t", "3", "-c:a", "libmp3lame", "-b:a", "128k", tmp)
    shutil.move(tmp, str(path))       # resynth_one_beat 처럼 **같은 경로**를 덮어쓴다


def _bump_mtime(path):
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))


CUTS = [{"video_id": "R", "start": 0.5, "dur": 1.405, "src_dur": 1.405},
        {"video_id": "G", "start": 0.2, "dur": 1.595, "src_dur": 1.595}]


class _Env:
    def __init__(self, tmp_path, monkeypatch, tts):
        self.beat = {"beat_idx": 0, "narration": "테스트", "tts_path": str(tts), "tts_ver": 1,
                     "voice_override": {"voice_id": "A"}}
        self.job = {"id": "j", "edit_plan": {"beats": [self.beat]}}
        env = self

        class _Store:
            def __init__(self, *a, **k):
                pass

            def get_mix_job(self, *_a, **_k):
                return env.job

        self.pv = tmp_path / "pv"
        monkeypatch.setattr(app, "Store", _Store)
        monkeypatch.setattr(app, "_pvproxy_dir", lambda _j: self.pv)
        app._PVPROXY_BUSY.clear()


# ── (a) 같은 컷·다른 음성 → 다른 서명 ─────────────────────────────────────────
def test_same_cuts_different_voice_changes_sig(tmp_path):
    tts = tmp_path / "beat_0_x.mp3"
    tts.write_bytes(b"voice-A" * 100)
    beat = {"beat_idx": 0, "tts_path": str(tts), "tts_ver": 1, "voice_override": {"voice_id": "A"}}
    s1 = app._pvproxy_sig(CUTS, [2], app._pvproxy_beat_meta([beat]))
    # 파일 내용만 바뀜(tts_ver·voice 그대로 — 전체 재합성 resynth_tts_job 꼴)
    tts.write_bytes(b"voice-B" * 100)
    _bump_mtime(tts)
    s2 = app._pvproxy_sig(CUTS, [2], app._pvproxy_beat_meta([beat]))
    assert s1 != s2, "같은 경로에 음성만 바뀌었는데 서명이 같다 — 옛 목소리 합본을 재사용한다"
    # tts_ver 만 올라감
    beat2 = dict(beat, tts_ver=2)
    assert app._pvproxy_sig(CUTS, [2], app._pvproxy_beat_meta([beat2])) != s2
    # 성우만 바뀜
    beat3 = dict(beat, voice_override={"voice_id": "B"})
    assert app._pvproxy_sig(CUTS, [2], app._pvproxy_beat_meta([beat3])) != s2
    # 구도만 바뀜(frame_vf 결과가 달라지는 확대)
    beat4 = dict(beat, scene_zoom=1.6)
    assert va.frame_vf(beat4, 720, 1280) != va.frame_vf(beat, 720, 1280)
    assert app._pvproxy_sig(CUTS, [2], app._pvproxy_beat_meta([beat4])) != s2
    # 아무것도 안 바뀌면 같은 서명(재사용은 살아 있어야 한다)
    assert app._pvproxy_sig(CUTS, [2], app._pvproxy_beat_meta([beat])) == s2


def test_api_does_not_serve_old_voice_proxy(tmp_path, monkeypatch):
    """화면 요청 경로 그대로 — 음성을 바꾸면 이미 있는 합본을 ready 로 주면 안 된다."""
    tts = tmp_path / "beat_0_x.mp3"
    tts.write_bytes(b"voice-A" * 100)
    e = _Env(tmp_path, monkeypatch, tts)
    monkeypatch.setattr(app, "_resolve_sources", lambda job, w: {})
    monkeypatch.setattr(app, "_pvproxy_build", lambda *a, **k: None)
    body = {"cuts": [dict(c) for c in CUTS], "beat_lens": [2]}
    r1 = app.api_mix_preview_proxy("j", json.loads(json.dumps(body)))
    e.pv.mkdir(parents=True, exist_ok=True)
    (e.pv / ("%s.mp4" % r1["sig"])).write_bytes(b"old")          # 옛 목소리로 구워진 합본
    assert app.api_mix_preview_proxy("j", json.loads(json.dumps(body)))["state"] == "ready"
    tts.write_bytes(b"voice-B" * 100)                              # 성우 변경 = 같은 경로 덮어쓰기
    _bump_mtime(tts)
    e.beat["tts_ver"] = 2
    app._PVPROXY_BUSY.clear()
    r2 = app.api_mix_preview_proxy("j", json.loads(json.dumps(body)))
    assert r2["sig"] != r1["sig"] and r2["state"] != "ready", "성우를 바꿨는데 옛 합본을 ready 로 줬다"


# ── (b) 미리굽기와 화면 요청이 같은 편성에서 같은 서명 ──────────────────────────
@pytest.mark.skipif(not HAS_FF, reason="ffmpeg 없음")
def test_prewarm_and_screen_agree(tmp_path, monkeypatch):
    tts = tmp_path / "beat_0_x.mp3"
    _mp3(tts, "loud")
    _Env(tmp_path, monkeypatch, tts)
    src = tmp_path / "R.mp4"
    src.write_bytes(b"x")
    monkeypatch.setattr(app, "_resolve_sources", lambda job, w: {"R": str(src), "G": str(src)})
    # 서버 계획 = 화면 컷(1.405 처럼 3자리 값 — 종전 미리굽기는 2자리로 내려 서명이 갈렸다)
    plan = [{"video_id": c["video_id"], "start": c["start"], "src_dur": c["src_dur"], "out_dur": c["dur"]}
            for c in CUTS]
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda *a, **k: [dict(x) for x in plan])
    seen = []
    monkeypatch.setattr(app, "_pvproxy_build", lambda job_id, sig, *a, **k: seen.append(sig))
    app._pvproxy_prewarm("j")
    assert seen, "미리굽기가 굽기를 부르지 않았다"
    app._PVPROXY_BUSY.clear()
    # 화면(scene_play.js pvxCut)이 보내는 모양 = toFixed(3)
    screen = [{"video_id": c["video_id"], "start": float("%.3f" % c["start"]), "dur": float("%.3f" % c["dur"]),
               "src_dur": float("%.3f" % c["src_dur"])} for c in CUTS]
    r = app.api_mix_preview_proxy("j", {"cuts": screen, "beat_lens": [2]})
    assert r["sig"] == seen[0], "같은 편성인데 미리굽기와 화면 요청의 서명이 다르다"


def test_both_paths_use_one_sig_function():
    """서명 식이 두 벌로 돌아오지 않게 — 두 경로 모두 _pvproxy_sig 를 부르고 옛 식은 없다."""
    pre = APP_SRC[APP_SRC.index("def _pvproxy_prewarm("):APP_SRC.index("def _pvproxy_build(")]
    api = APP_SRC[APP_SRC.index("def api_mix_preview_proxy("):APP_SRC.index("def api_mix_preview_proxy_file(")]
    for name, body in (("미리굽기", pre), ("화면 요청", api)):
        assert "_pvproxy_sig(" in body, "%s가 공용 서명 함수를 안 쓴다" % name
        assert "_pvproxy_beat_meta(" in body, "%s 서명에 칸 음성·구도가 안 실린다" % name
        assert "hashlib.sha1(" not in body, "%s에 서명 식이 따로 남아 있다" % name


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_screen_key_changes_with_tts_ver(tmp_path):
    """화면(pvxCuts)을 실제로 돌려 — 컷이 그대로여도 칸 음성 버전이 오르면 key 가 바뀌어 다시 묻는다."""
    js = (Path(__file__).resolve().parents[1] / "static" / "scene_play.js").read_text(encoding="utf-8")
    fns = js[js.index("function pvxCut("):js.index("function pvxClock(")]
    harness = "\n".join([
        "let DATA = {beats: [{beat_idx: 0, tts_ver: 1}]};",
        "const lists = [[1]], STRETCH = [0];",
        "function beatDur(){ return 3; }",
        "function planClips(){ return [{video_id:'R', start:0.5, dur:1.405, src_dur:1.405}]; }",
        fns,
        "const a = pvxCuts(); DATA.beats[0].tts_ver = 2; const b = pvxCuts();",
        "console.log(JSON.stringify({same: a.key === b.key, beatsSame: a.beats[0] === b.beats[0]}));",
    ])
    f = tmp_path / "h.js"
    f.write_text(harness, encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(f)], capture_output=True, text=True, check=True).stdout)
    assert out["beatsSame"], "칸 컷 목록(pvxAttach 대조용) 모양이 바뀌면 안 된다"
    assert not out["same"], "성우만 바꿨는데 화면 key 가 그대로 — 합본을 다시 묻지 않는다"


# ── 렌더까지: 실제로 구운 합본에 **새 목소리**가 들어가나(같은 길이 = 칸 음성 곳간 키가 같아지는 꼴) ──
def _mean_db(p):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(p), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True)
    for ln in r.stderr.decode("utf-8", "ignore").splitlines():
        if "mean_volume:" in ln:
            return float(ln.split("mean_volume:")[1].split("dB")[0])
    raise AssertionError("음량 측정 실패")


@pytest.mark.skipif(not HAS_FF, reason="ffmpeg 없음")
def test_rebaked_proxy_has_new_voice(tmp_path, monkeypatch):
    tts = tmp_path / "tts" / "beat_0_x.mp3"
    tts.parent.mkdir()
    _mp3(tts, "loud")
    e = _Env(tmp_path, monkeypatch, tts)
    srcs = {}
    for k, col in (("R", "red"), ("G", "green")):
        p = tmp_path / ("%s.mp4" % k)
        _ff("-f", "lavfi", "-i", "color=%s:s=720x1280:r=30:d=6" % col, "-c:v", "libx264",
            "-preset", "ultrafast", str(p))
        srcs[k] = str(p)
    monkeypatch.setattr(app, "_resolve_sources", lambda job, w: dict(srcs))
    body = {"cuts": [dict(c) for c in CUTS], "beat_lens": [2]}

    def _ready():
        t0 = time.time()
        r = app.api_mix_preview_proxy("j", json.loads(json.dumps(body)))
        while r.get("state") != "ready" and time.time() - t0 < 120:
            time.sleep(0.3)
            r = app.api_mix_preview_proxy("j", json.loads(json.dumps(body)))
        assert r.get("state") == "ready", "합본 굽기 실패"
        return e.pv / ("%s.mp4" % r["sig"])

    assert _mean_db(_ready()) > -40, "첫 합본에 음성이 없다"
    _mp3(tts, "silent")            # 같은 경로·같은 길이로 성우 변경
    _bump_mtime(tts)
    e.beat["tts_ver"] = 2
    assert _mean_db(_ready()) < -80, "성우를 바꿨는데 합본에서 옛 목소리가 난다"
