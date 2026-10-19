# -*- coding: utf-8 -*-
"""사건별 효과음 카테고리 만들기 (관제 237, 2026-10-19).

노바작가 스타터킷이 '돈·충격·뽁·추임새'처럼 사건마다 소리를 나눈 것을 보고 우리 팩을 보충한다.
킷 파일은 쓰지 않는다(効果音ラボ mp3 재배포 금지) — 원본은 사장님 바탕화면 효과음 모음이다.

하는 일: 아래 TABLE 의 원본마다
  ① 모노 44.1kHz 로 읽고 ② 들리는 시점(최고점-6dB)이 5ms 에 오게 앞을 자르고(trim_onset.py 와 같은 기준)
  ③ 카테고리 최대 길이에서 끊되 소리가 먼저 잦아들면(최고점-35dB) 거기서 끊고 ④ 끝 60ms 를 줄여 끝낸다.
결과: shopping_shorts/assets/sfx_packs/_분류/<칸>/<번호>_<설명>.wav + catalog.json(원본 이름·길이).
여러 번 돌려도 결과가 같다(원본에서 다시 만든다).
사용: py tools/sfx_bench/make_categories.py [원본 바탕화면 폴더]
"""
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

SR = 44100
DESK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Desktop")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shopping_shorts", "assets", "sfx_packs", "_분류")

# 칸 → (최대 길이 초, [(설명, 바탕화면 기준 원본 경로)])
TABLE = {
    "money": (1.0, [
        ("코인먹기", "효과음/2 돈 (슈퍼마리오 코인먹).mp3"),
        ("계산대", "효과음/17 캐셔(돈).mp3"),
        ("동전떨어짐", "효과음/효과음_모음집/006_동전떨어지는소리.wav"),
    ]),
    "shock": (1.2, [
        ("두둥", "효과음 종합/튜브렌즈가 자주 사용하는 효과음/두둥2.mp3"),
        ("쾅", "효과음/효과음_모음집/025_터지는소리BOOM.WAV"),
        ("놀람발견", "효과음/111_놀람.발견.mp3"),
    ]),
    "gasp": (1.0, [
        ("헉", "효과음/094_헉.wav"),
        ("뜨헉", "효과음/3 뜨헉.mp3"),
        ("뜨헉2", "효과음/효과음_모음집/030_뜨헉!.mp3"),
    ]),
    "reveal": (1.3, [
        ("짜잔", "효과음/효과음_모음집/TADAAH Sound Effect.mp3"),
        ("샤라라", "효과음/12 샤라라랑 (등장용 마법가루).mp3"),
        ("뾰로롱", "효과음/6 뾰로로롱 (등장용 하프).mp3"),
    ]),
    "bubble": (0.7, [
        ("뾰옥", "효과음/7 뾰옥 (물방울).mp3"),
        ("물방울", "효과음 종합/튜브렌즈가 자주 사용하는 효과음/물방울소리.mp3"),
        ("보글", "효과음/귀여운느낌/2.buble -  - Output - Stereo Out.mp3"),
        ("뽀옹", "효과음/5 뽀옹 (폰문자전송).mp3"),
    ]),
    "wrong": (0.7, [
        ("삐삑", "효과음/8 삐삑 (오답 -짧은).mp3"),
        ("땡", "효과음 종합/튜브렌즈가 자주 사용하는 효과음/틀림 효과음 오류/Track05_에러 캔슬 취소 오답.wav"),
        ("뿌", "효과음 종합/튜브렌즈가 자주 사용하는 효과음/틀림 효과음 오류/Track09_에러 캔슬 취소 오답.wav"),
    ]),
    "laugh": (1.6, [
        ("카툰웃음", "효과음/091_카툰 웃음.mp3"),
        ("관객웃음", "효과음 종합/특별한 효과음/관객웃음소리1.mp3"),
    ]),
    "step": (1.0, [
        ("총총", "효과음/귀여운느낌/5.comic step -  - Output - Stereo Out.mp3"),
        ("뚜벅", "효과음/귀여운느낌/6.slow step -  - Output - Stereo Out.mp3"),
    ]),
}
LEAD_MS = 5
FADE_MS = 60
TAIL_DB = -35.0


def load(path):
    """ffmpeg 로 모노 44.1kHz float 배열."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(float)


def shape(x, max_s):
    k = int(0.005 * SR)
    r = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(k) / k, "same")) + 1e-9)
    top = r.max()
    on = max(0, int(np.argmax(r > top - 6)) - k // 2 - int(LEAD_MS / 1000 * SR))
    y = x[on:on + int(max_s * SR)].copy()
    ry = r[on:on + len(y)]
    loud = np.nonzero(ry > top + TAIL_DB)[0]
    if len(loud):
        y = y[:min(len(y), loud[-1] + int(0.03 * SR))]
    f_in = min(len(y), int(0.002 * SR)); y[:f_in] *= np.linspace(0, 1, f_in)
    f_out = min(len(y), int(FADE_MS / 1000 * SR)); y[-f_out:] *= np.linspace(1, 0, f_out)
    pk = np.abs(y).max()
    if pk > 0.95:
        y *= 0.95 / pk         # 찢어짐만 막는다 — 크기 맞춤은 sfx_pack._gain_for 몫
    return y


def main():
    cat = {}
    for slot, (max_s, rows) in TABLE.items():
        d = os.path.join(OUT, slot)
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            if f.endswith(".wav"):
                os.remove(os.path.join(d, f))
        cat[slot] = []
        for i, (name, rel) in enumerate(rows, 1):
            src = os.path.join(DESK, rel)
            y = shape(load(src), max_s)
            fn = "%d_%s.wav" % (i, name)
            sf.write(os.path.join(d, fn), y, SR, subtype="PCM_16")
            cat[slot].append({"file": fn, "src": rel, "sec": round(len(y) / SR, 3)})
            print("%-7s %-16s %.2f초  ← %s" % (slot, fn, len(y) / SR, rel))
    with open(os.path.join(OUT, "catalog.json"), "w", encoding="utf-8") as fp:
        json.dump(cat, fp, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
