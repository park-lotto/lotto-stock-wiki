"""separate — 목소리 줄기/배경 소리 가르기 + 사람 말소리 판정 한 곳(표 #28, 11-06).

목소리 줄기 가르기 = demucs htdemucs(전용 가상환경 C:/Users/CH/demucs-venv, CPU torch — 엔진 파이썬과 따로: 3.14 에 torch 를 넣지 않는다).
엔진은 따로 띄운 프로세스로 부르고 결과 wav(vocals·no_vocals)만 받는다. 가상환경이 없으면 조용히 넘기지 않고 {"failed": 사유}.
사람 목소리 판정(voice_frames) = 0.1초 칸마다 목소리 줄기 RMS 가 ① 기준선(같은 칸 배경 줄기 − 6dB) 위 ② 절대 하한 −40dBFS 위 — 둘 다
(배경음이 새어 든 작은 소리·조용한 편의 잡음을 사람 말소리로 치지 않게).
★초안(draft) — 11-06 Jev 해결 0.69·위험 0.26: 판정·규칙 칸은 이 값을 쓰지 않는다(소리·자막 칸 측정만, 초안 표시를 옮긴다).
규칙으로 올리는 조건 = 사람 말 정답 편 중 '말 있는 칸·없는 칸이 섞인 편'(정답 목소리 지분 MIXED_LO~MIXED_HI) VOICE_RULE_MIN_MIXED 편 이상에서 F1 확인.
가상환경 경로는 이 PC 기준(C:/Users/CH/demucs-venv, 바꾸기 SHORTEM_DEMUCS_PY) — kal 경로에서만 부른다(analyze kal=True), 없으면 failed + [경보].
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

VENV_PY = Path(os.environ.get("SHORTEM_DEMUCS_PY") or "C:/Users/CH/demucs-venv/Scripts/python.exe")
MODEL = "htdemucs"
SR = 44100
STEP_S = 0.1               # 판정 격자(0.1초 — 소리·자막 칸 격자와 같은 칸)
VOICE_OVER_BG_DB = 6.0     # 기준선 = 같은 칸 배경 줄기 — 목소리가 배경 − 6dB 보다 커야
VOICE_ABS_DB = -40.0       # 절대 하한(dBFS) — 둘 다 넘어야 사람 목소리
BG_ABS_DB = -45.0          # 배경 줄기 있음 하한(dBFS)
MIXED_LO, MIXED_HI = 0.2, 0.8   # '말 없는 칸을 가려내는 힘'을 재는 정답 편 = 정답 목소리 지분이 이 사이
VOICE_RULE_MIN_MIXED = 3        # 그런 편이 이만큼 쌓여야 규칙으로 올린다(그 전 draft)
VOICE_EVIDENCE = {             # 11-06 실측(C:/t/eng_fix_run/06_voice_10.json · 정답 = 스피치매틱스 받아쓰기 구절 시각)
    "truth_videos": 7,          # fFhPI(받아쓰기 = 배경 노래 가사) + 나레 채널 6편(유머쇼쇼 4·이븐쇼핑 1·해외쇼쇼 1)
    "f1": {"fFhPI": 0.88, "BlA9": 0.982, "NBdm": 0.989, "Lr2H": 0.884, "jECu": 0.933, "QMJt": 0.655, "ABjQ": 0.99},
    "mixed_videos": 0,          # 정답 목소리 지분 0.2~0.8 = QMJt(0.5) 하나뿐인데 그 정답은 제미나이 무료 구절 시각이라 품질 낮음 → 0 으로 센다
    "same_f1_rule": "절대 −40dBFS 하나만도 F1 차 ≤0.012 — 기준선 조건이 더 낫다는 증거 없음",
    "gap": "원음 대사·노래가 섞인 편(스냅봤니 꼴)의 사람 말 정답 0편 · 목소리 줄기에 노래 부르는 소리도 들어간다"}

_WORKER = r'''
import sys, json, subprocess, numpy as np, torch, soundfile as sf
from demucs.pretrained import get_model
from demucs.apply import apply_model
src, out_dir, model = sys.argv[1], sys.argv[2], sys.argv[3]
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-f", "f32le", "-ac", "2", "-ar", "44100", "-"], capture_output=True).stdout
x = np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()
m = get_model(model); m.eval()
wav = torch.from_numpy(x)
ref = wav.mean(0); mu, sd = ref.mean(), ref.std() + 1e-8
with torch.no_grad():
    s = apply_model(m, ((wav - mu) / sd)[None], device="cpu", progress=False)[0] * sd + mu
names = list(m.sources); v = s[names.index("vocals")].numpy()
rest = sum(s[i] for i in range(len(names)) if names[i] != "vocals").numpy()
sf.write(out_dir + "/vocals.wav", v.T, 44100); sf.write(out_dir + "/no_vocals.wav", rest.T, 44100)
print(json.dumps({"sources": names, "sec": round(x.shape[1] / 44100, 3)}))
'''


def separate(mp4: str, out_dir: str, timeout: int = 1800) -> dict:
    """mp4 → out_dir/vocals.wav·no_vocals.wav. 이미 있으면 다시 안 나눈다(표식 sep.json 의 model·src 크기가 같을 때만)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mark = out / "sep.json"
    key = {"model": MODEL, "src": str(mp4), "size": Path(mp4).stat().st_size}
    if mark.exists() and (out / "vocals.wav").exists():
        try:
            old = json.loads(mark.read_text(encoding="utf-8"))
            if all(old.get(k) == v for k, v in key.items()):
                return {**old, "vocals": str(out / "vocals.wav"), "no_vocals": str(out / "no_vocals.wav"), "cached": True}
        except ValueError:
            pass
    if not VENV_PY.exists():
        return {"failed": f"demucs 가상환경 없음({VENV_PY}) — 목소리 줄기 가르기 못 함(판정 칸은 '못 잼')"}
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(_WORKER)
        wp = f.name
    try:
        r = subprocess.run([str(VENV_PY), wp, str(mp4), str(out), MODEL], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    finally:
        os.unlink(wp)
    if r.returncode != 0 or not (out / "vocals.wav").exists():
        return {"failed": f"demucs 실패 rc={r.returncode}: {(r.stderr or '')[-300:]}"}
    info = json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
    rec = {**key, **info}
    mark.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return {**rec, "vocals": str(out / "vocals.wav"), "no_vocals": str(out / "no_vocals.wav"), "cached": False}


def _db_grid(wav_path: str, step: float = STEP_S) -> np.ndarray:
    import wave                      # 엔진 파이썬엔 soundfile 이 없다 — 일꾼이 쓴 PCM_16 wav 를 표준 라이브러리로
    with wave.open(wav_path, "rb") as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        if sw != 2:
            raise ValueError(f"{wav_path} 표본 폭 {sw}바이트 — PCM_16 만 읽는다")
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, ch).astype(np.float32) / 32768.0
    m = x.mean(axis=1)
    n = int(len(m) / (sr * step))
    if n == 0:
        return np.zeros(0)
    m = m[: int(n * sr * step)].reshape(n, -1)
    return 20 * np.log10(np.sqrt((m.astype(np.float64) ** 2).mean(axis=1)) + 1e-9)


def voice_frames(vocals_wav: str, no_vocals_wav: str) -> dict:
    """0.1초 칸마다 사람 목소리 있음(bool) — ① 기준선 = 같은 칸 배경 줄기: 목소리 > 배경 − VOICE_OVER_BG_DB ② 목소리 > VOICE_ABS_DB. 둘 다.
    (Jev 해결 0.84·위험 0.38 · 11-06) 정답 = 받아쓰기 구절 시각 7편(VOICE_EVIDENCE) — 초안(draft_mark).
    처음 설계(편 목소리 하위 20% + 12dB)는 말이 계속되는 편에서 기준선이 곧 목소리라 F1 0.0~0.33 — 버림."""
    a, b = _db_grid(vocals_wav), _db_grid(no_vocals_wav)
    n = min(len(a), len(b))
    if not n:
        return {"failed": "줄기 비었음", "frames": []}
    a, b = a[:n], b[:n]
    v = (a > b - VOICE_OVER_BG_DB) & (a > VOICE_ABS_DB)
    return {"frames": v.tolist(), "voiced_share": round(float(v.mean()), 3), "step_s": STEP_S,
            "vocals_db_median": round(float(np.median(a)), 1), "bg_db_median": round(float(np.median(b)), 1),
            "rule": f"vocals RMS > 같은 칸 배경 − {VOICE_OVER_BG_DB}dB 그리고 > {VOICE_ABS_DB}dBFS (0.1초 칸)",
            **draft_mark()}


def draft_mark() -> dict:
    """목소리 칸 초안 표시 한 곳 — 쌓인 정답이 조건(VOICE_RULE_MIN_MIXED)에 못 미치면 draft=True. 소리·자막 칸이 이 표시를 옮긴다."""
    ready = VOICE_EVIDENCE["mixed_videos"] >= VOICE_RULE_MIN_MIXED
    return {"draft": not ready, "evidence": VOICE_EVIDENCE,
            "use": "규칙·판정에 써도 됨" if ready else
                   f"초안 — 측정만(규칙·판정 칸에 쓰지 않는다 · 말 섞인 정답 편 {VOICE_EVIDENCE['mixed_videos']}/{VOICE_RULE_MIN_MIXED})"}


def bg_frames(no_vocals_wav: str) -> dict:
    """0.1초 칸마다 배경음(현장음·음악·효과음) 있음 — 절대 하한 BG_ABS_DB 위."""
    b = _db_grid(no_vocals_wav)
    v = b > BG_ABS_DB
    return {"frames": v.tolist(), "share": round(float(v.mean()), 3) if len(v) else 0.0, "step_s": STEP_S, "rule": f"no_vocals RMS > {BG_ABS_DB}dBFS"}


def separation_of(mp4: str, out_dir: str) -> dict:
    """뜯기 칸 'separation' — 나누기 + 목소리·배경 칸 판정. 못 하면 {"failed"} (소리·자막 칸 격자는 그때 원음 대사/현장음을 못 가른다고 적는다)."""
    r = separate(mp4, out_dir)
    if r.get("failed"):
        return {"failed": r["failed"], "model": MODEL}
    vf = voice_frames(r["vocals"], r["no_vocals"])
    bf = bg_frames(r["no_vocals"])
    return {"model": MODEL, "dir": str(out_dir), "voice": vf, "bg": bf, "sec": r.get("sec")}
