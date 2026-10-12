# -*- coding: utf-8 -*-
"""소재의 **장면 전환 시각 목록** — 검출과 캐시는 여기 한 곳(2026-09-27).

쓰는 곳: app.api_mix_scene_lab_data 가 소재마다 `DATA.scenecuts[video_id]` 로 싣고, 편집 화면 컷 계산
  (static/scene_play.js planClips → guardReadWindow)이 컷이 **실제로 읽는 창**의 머리·꼬리 0.1초 안에 걸친 전환을 보고
  창을 전환 안쪽으로 줄인다. 서버 러너(screen_clips)가 같은 JS·같은 DATA 를 돌리므로 화면·미리보기·완성본·캡컷이 같은 창을 받는다.
왜: 컷 가장자리에 딴 장면 1~3프레임(서버 6 job 실측 23프레임). 조각 좌표를 고치는 방식(경계 붙이기)은 30일 job 90%의 좌표를
  바꾸고 창이 통째로 밀려 새 잔상을 만들어 버렸다 — 좌표는 두고 **읽는 창**만 줄인다.

규칙:
  - 장면 전환 = 이웃 프레임 특징 거리(frame_match.feats — 도구의 잔상 판정과 같은 자)가 CUT_T 이상이고
    앞뒤 6프레임 안 튐 중앙값의 JUMP 배 이상(빠른 움직임은 전환이 아니다). 값 = 새 장면 첫 프레임의 pts 를 0.001초 내림.
  - 영상당 한 번 계산해 영상 옆 `<파일>.scenecuts.json`(크기·수정시각·규칙판 표식 — 다르면 다시 잰다).
    SEG_SNAP_CACHE_DIR 이 있으면 그 폴더(서버 점검·테스트가 고객 폴더를 안 건드리게).
  - 못 재면 빈 목록(가드 안 함 = 종전 동작) + stderr 한 줄.
"""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

RULE = "cuts-v1"          # 전환 판정 규칙판 — 바꾸면 옛 캐시를 버린다
CUT_T = 0.40              # 이웃 프레임 특징 거리 — 이 이상이면 전환 후보(도구 CUT_T 와 같은 값)
JUMP = 3.0                # 앞뒤 튐 중앙값의 이 배수 이상이어야 전환(도구 GHOST_JUMP 와 같은 값)
_W, _H = 90, 160
_MEM = {}                 # (경로, 크기, mtime_ns) → 전환 시각 목록


def _feats(fr):
    from shopping_shorts import frame_match as fm
    return fm.feats(fr)


def _cache_path(video_path):
    p = Path(video_path)
    d = os.getenv("SEG_SNAP_CACHE_DIR")
    if d:
        key = hashlib.sha1(str(p.resolve()).encode("utf-8", "ignore")).hexdigest()[:16]
        return Path(d) / ("%s_%s.scenecuts.json" % (p.stem[:40], key))
    return p.with_name(p.name + ".scenecuts.json")


def detect_cuts(video_path, timeout=300):
    """영상 → 장면 전환 프레임의 pts(초) 목록(새 장면 첫 프레임). 원본 프레임률 그대로(60fps 소재도 프레임마다)."""
    cmd = ["ffmpeg", "-v", "info", "-nostats", "-threads", "2", "-i", str(video_path), "-an",
           "-vf", "scale=%d:%d,format=rgb24,showinfo" % (_W, _H), "-vsync", "passthrough", "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-300:])
    pts = [float(x) for x in re.findall(r"pts_time:\s*([0-9.eE+-]+)", r.stderr.decode("utf-8", "ignore"))]
    fr = np.frombuffer(r.stdout, np.uint8)
    n = min(len(pts), fr.size // (_W * _H * 3))
    if n < 3:
        return []
    fe = _feats(fr[: n * _W * _H * 3].reshape(n, _H, _W, 3))
    m = np.zeros(n, np.float32)
    m[1:] = np.abs(fe[1:] - fe[:-1]).mean(axis=(1, 2))
    return cuts_from_motion(m, pts[:n])


def cuts_from_motion(m, pts, span=6):
    """이웃 프레임 튐 m[i](i-1→i) → 전환 pts 목록. 순수 함수(테스트용)."""
    out = []
    for i in range(1, len(m)):
        if m[i] < CUT_T:
            continue
        nb = [float(m[j]) for j in range(max(1, i - span), min(len(m), i + span + 1)) if j != i]
        med = float(np.median(nb)) if nb else 0.0
        if m[i] >= JUMP * med:
            out.append(round(float(pts[i]), 4))
    return out


def scene_cuts(video_path):
    """전환 목록 — 메모리 → 파일 캐시 → 계산 순. 계산 실패는 빈 목록 + stderr(조용히 삼키지 않는다)."""
    p = Path(video_path)
    try:
        st = p.stat()
    except OSError as e:
        print("[seg_snap] 영상 없음 %s: %s" % (video_path, e), file=sys.stderr)
        return []
    mk = (str(p), st.st_size, st.st_mtime_ns)
    if mk in _MEM:
        return _MEM[mk]
    cp = _cache_path(p)
    try:
        if cp.exists():
            j = json.loads(cp.read_text(encoding="utf-8"))
            if j.get("rule") == RULE and j.get("size") == st.st_size and j.get("mtime_ns") == st.st_mtime_ns:
                _MEM[mk] = [float(x) for x in j.get("cuts") or []]
                return _MEM[mk]
    except (OSError, ValueError) as e:
        print("[seg_snap] 캐시 읽기 실패(다시 잰다) %s: %s" % (cp, e), file=sys.stderr)
    try:
        cuts = detect_cuts(p)
    except Exception as e:      # noqa: BLE001 — 전환을 못 재면 좌표를 안 바꾼다(종전 동작). 대신 소리 낸다
        print("[seg_snap] 전환 계산 실패(좌표 그대로) %s: %r" % (video_path, e), file=sys.stderr)
        return []
    _MEM[mk] = cuts
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps({"rule": RULE, "size": st.st_size, "mtime_ns": st.st_mtime_ns, "cuts": cuts}),
                      encoding="utf-8")
    except OSError as e:
        print("[seg_snap] 캐시 저장 실패(무해) %s: %s" % (cp, e), file=sys.stderr)
    return cuts


def edge_of(cut):
    """전환 pts → 붙일 좌표(0.001초 내림). 60fps 소재의 x.xxx67 같은 pts 도 반올림으로 넘지 않게 내린다."""
    return math.floor(float(cut) * 1000 + 1e-6) / 1000


def scenecuts_map(src_paths):
    """{video_id: 경로} → {video_id: [전환 시각(0.001초 내림), ...]}. 처음 한 번만 비싸다(실측 35초 영상 3.1초) — 영상끼리 나란히."""
    items = [(k, str(v)) for k, v in (src_paths or {}).items() if v]
    if len(items) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(min(4, len(items))) as ex:
            got = list(ex.map(lambda kv: scene_cuts(kv[1]), items))
    else:
        got = [scene_cuts(v) for _, v in items]
    return {k: [edge_of(c) for c in cuts] for (k, _), cuts in zip(items, got)}
