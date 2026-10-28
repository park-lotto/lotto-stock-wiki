# -*- coding: utf-8 -*-
"""배경음 목록(관제 146) 결과물 검사 — 고른 곡이 **완성본 소리**와 **캡컷 초안**에 실제로 들어가는가.

  py tools/bgm_lib/check_render_capcut.py [곡id ...]     (없으면 전 곡)

① 렌더: 무음 나레이션 + deco.bgm.lib → resolve_deco_media(렌더·캡컷 공용) → video_assemble._burn_captions(실 ffmpeg).
   완성본 소리를 뽑아 목록 곡 파일과 파형 상관(정규화 상호상관 최대값)을 잰다. 곡 없음 대조군은 무음이어야 한다.
② 캡컷: /api/mix/capcut 실제 라우트 → 초안 오디오 소재 + 내려받기 URL 바이트 = 목록 곡 파일(md5), 볼륨 = 저장값.
"""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
from shopping_shorts import bgm_lib, mix_pipeline, video_assemble as va

SR = 8000
CORR_MIN = 0.8


def _ff(*a):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *a], check=True, capture_output=True)


def _pcm(path, ss=0.0, t=4.0):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(ss), "-t", str(t), "-i", str(path),
                          "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def _corr(out_wave, ref_wave):
    """out 안에 ref 가 들어 있나 — FFT 상호상관 최대값(정규화)."""
    n = len(out_wave) + len(ref_wave)
    a = out_wave - out_wave.mean(); b = ref_wave - ref_wave.mean()
    if not a.any() or not b.any():
        return 0.0
    c = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    return float(np.max(np.abs(c)) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _env_corr(out_wave, ref_wave, hop=80, max_lag=20):
    """음량 윤곽(10ms 창 RMS) 상관 — 배속 필터는 파형 샘플이 실행마다 달라 파형 상관이 안 맞는다(실측 0.3).
    윤곽은 박자·강약 흐름이라 속도가 같으면 높고 다르면 낮다. ±0.2초 어긋남까지 본다."""
    def env(w):
        n = len(w) // hop
        return np.sqrt((w[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    a, b = env(out_wave), env(ref_wave)
    n = min(len(a), len(b)) - max_lag
    return max(float(np.corrcoef(a[l:l + n], b[:n])[0, 1]) for l in range(0, max_lag))


def check_render(tid, tmp, speed=1.0):
    tmp.mkdir(parents=True, exist_ok=True)
    src = tmp / "src.mp4"; tts = tmp / "t0.wav"
    if not src.exists():
        _ff("-f", "lavfi", "-i", "color=c=gray:s=360x640:r=30:d=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src))
        _ff("-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "3.5", str(tts))
    plan = {"structure": "t", "beats": [{"beat_idx": 0, "role": "본문", "narration": "배경음 검사", "target_seconds": 3.5,
            "primary": {"video_id": 0, "seg_id": "s0", "start": 0.0, "end": 3.5}, "alternates": [], "effect": "cut", "fit": 0}]}
    work = tmp / "w"; work.mkdir(exist_ok=True)
    mix = va._render_mix(plan, {0: str(tts)}, {0: str(src)}, work, cutaway_paths=None)
    res = {}
    bg = {"lib": tid, "volume": 15, **({"speed": speed} if speed != 1.0 else {})}
    for name, deco in (("곡", {"bgm": bg}), ("없음", {"bgm": {"volume": 15}})):
        out = tmp / f"out_{name}.mp4"
        va._burn_captions(mix, plan, {0: str(tts)}, str(out), work, deco=mix_pipeline.resolve_deco_media(deco, work))
        w = _pcm(out, 0, 3.0)
        ref = bgm_lib.path_of(tid)
        if speed != 1.0:                    # 기대 소리 = 곡 파일을 그 배속으로(독립 ffmpeg 한 번)
            ref = str(tmp / f"ref_{speed}.wav")
            _ff("-i", bgm_lib.path_of(tid), "-af", f"atempo={speed}", "-t", "4", ref)
        _m = _corr if speed == 1.0 else _env_corr    # 1배속은 파형 그대로, 배속은 음량 윤곽으로 잰다
        res[name] = (_m(w, _pcm(ref, 0, 3.0)), float(np.sqrt((w ** 2).mean())),
                     _m(w, _pcm(bgm_lib.path_of(tid), 0, 3.0)))
    ok = res["곡"][0] >= CORR_MIN and res["곡"][1] > 1e-3 and res["없음"][1] < 1e-4
    msg = f"상관 {res['곡'][0]:.3f} · 소리 RMS {res['곡'][1]:.4f} / 곡없음 RMS {res['없음'][1]:.6f}"
    if speed != 1.0:                        # 배속이 실제로 걸렸나 — 1배속 원본과는 덜 닮아야 한다
        ok = ok and res["곡"][2] < res["곡"][0] - 0.2
        msg += f" · 1배속 원본과 상관 {res['곡'][2]:.3f}(기대값보다 0.2 이상 낮아야 함)"
    return ok, msg


def check_capcut(tid, tmp, speed=1.0):
    import pytest  # noqa: F401 — monkeypatch 대용으로 직접 바꾼다
    from fastapi.testclient import TestClient
    from shopping_shorts import app as A
    from shopping_shorts.store import Store
    db = tmp / "t.db"; root = tmp / "mix_jobs"; work = root / "jc"
    (work / "s0").mkdir(parents=True, exist_ok=True)
    _ff("-f", "lavfi", "-i", "color=c=gray:s=360x640:r=30:d=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(work / "s0" / "src.mp4"))
    t0 = work / "tts" / "beat_0.mp3"; t0.parent.mkdir(exist_ok=True)
    _ff("-f", "lavfi", "-i", "sine=frequency=300:duration=2", str(t0))
    final = work / "final.mp4"; _ff("-f", "lavfi", "-i", "color=c=gray:s=360x640:r=30:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(final))
    old = (A.DB_PATH, A._MIX_WORK_DIR)
    A.DB_PATH, A._MIX_WORK_DIR = db, root
    try:
        st = Store(db)
        st.create_mix_job("jc", ["https://www.instagram.com/reel/AAA111/"], 20, "free")
        st.update_mix_job("jc", status="done", video_path=str(final), deco={"bgm": {"lib": tid, "volume": 25, **({"speed": speed} if speed != 1.0 else {})}}, edit_plan={
            "structure": "free", "beats": [{"beat_idx": 0, "role": "훅", "narration": "첫 장면", "tts_path": str(t0),
                                            "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0}}]})
        c = TestClient(A.app)
        r = c.get("/api/mix/capcut/jc", params={"base": "C:/capcutproject/CapCut Drafts"})
        if r.status_code != 200:
            return False, f"캡컷 API {r.status_code}"
        d = r.json()
        draft = json.loads(d["texts"]["draft_content.json"])
        auds = [m for m in draft["materials"]["audios"] if m["path"].endswith("bgm.mp3")]
        if not auds:
            return False, "초안에 배경음 소재 없음"
        seg = next(s for t in draft["tracks"] if t["type"] == "audio" for s in t["segments"] if s["material_id"] == auds[0]["id"])
        url = next(a["url"] for a in d["assets"] if a["name"] == "bgm.mp3")
        body = c.get(url).content
        same = hashlib.md5(body).hexdigest() == hashlib.md5(Path(bgm_lib.path_of(tid)).read_bytes()).hexdigest()
        tgt, src = seg["target_timerange"]["duration"], seg["source_timerange"]["duration"]
        sp_ok = abs(seg["speed"] - speed) < 1e-6 and abs(src / tgt - speed) < 0.01
        if speed != 1.0:
            sp_ok = sp_ok and any(m["id"] in seg["extra_material_refs"] and abs(m["speed"] - speed) < 1e-6
                                  for m in draft["materials"].get("speeds", []))
        return (same and seg["volume"] == 0.25 and sp_ok),             f"파일 md5 일치={same} · 볼륨 {seg['volume']} · 배속 {seg['speed']}(원본 {src/1e6:.2f}s / 화면 {tgt/1e6:.2f}s)"
    finally:
        A.DB_PATH, A._MIX_WORK_DIR = old


def main(ids):
    ids = ids or [t["id"] for t in bgm_lib.list_tracks()]
    base = Path(tempfile.mkdtemp(prefix="bgmchk_"))
    bad = 0
    for tid in ids:
        ok, msg = check_render(tid, base / "r")
        print(("✅" if ok else "❌"), "렌더", tid, msg, flush=True)
        bad += not ok
    ok, msg = check_capcut(ids[0], base / "c")
    print(("✅" if ok else "❌"), "캡컷", ids[0], msg)
    bad += not ok
    for sp in (0.8, 1.25):                  # 속도 조절(관제 146) — 렌더 atempo·캡컷 배속 칸
        ok, msg = check_render(ids[0], base / f"rs{sp}", speed=sp)
        print(("✅" if ok else "❌"), f"렌더 {sp}x", ids[0], msg, flush=True); bad += not ok
        ok, msg = check_capcut(ids[0], base / f"cs{sp}", speed=sp)
        print(("✅" if ok else "❌"), f"캡컷 {sp}x", ids[0], msg); bad += not ok
    print(f"결과: {len(ids)}곡 렌더 + 캡컷 1건 + 속도 2단(렌더·캡컷), 실패 {bad}")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1:]) else 0)
