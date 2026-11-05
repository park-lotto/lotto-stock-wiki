# -*- coding: utf-8 -*-
"""channelkit.bench 결과물 검사 — 뜨거운사람들 표본 10편을 bench.run으로 재서 이번 주 기준선을 재현하는가.

기준선: shopping_shorts/channelkit/bench/baselines/hotpeople_2026-09-28.json (옛 자 tools/hotpeople/measure 실측값)
허용 오차: 좌표 ±5px · 개수 ±1 · 초 ±0.1 · LUFS ±0.2 · 비율 ±2%p · 획/줄높이 ±1px
사보타주: constants.SCENE_T를 0.15로 바꾸면 컷 수가 기준선을 벗어나 빨강이 떠야 한다(2026-09-28 확인).

표본 mp4는 git에 없다(out/bench_cache/ gitignore). 찾는 순서:
  환경변수 BENCH_SAMPLES_HOTPEOPLE → <repo>/out/bench_cache/hotpeople
  → 없고 BENCH_DOWNLOAD=1이면 yt-dlp로 id별 재다운로드 → 그래도 없으면 skip(이유 표시).
  (병합 게이트의 임시 폴더에서 매번 200MB를 받지 않도록 다운로드는 명시 요청일 때만)
"""
from __future__ import annotations

import importlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from shopping_shorts.channelkit import bench

REPO = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO / "shopping_shorts" / "channelkit" / "bench"
BASE = bench.baseline("hotpeople")
TOL = BASE["tolerance"]


def _sample_dir() -> Path | None:
    cands = [os.environ.get("BENCH_SAMPLES_HOTPEOPLE"), str(REPO / "out" / "bench_cache" / "hotpeople")]
    for c in cands:
        if c and all((Path(c) / f"{v}.mp4").exists() for v in BASE["sample"]):
            return Path(c)
    if os.environ.get("BENCH_DOWNLOAD") == "1" and shutil.which("yt-dlp"):
        d = REPO / "out" / "bench_cache" / "hotpeople"
        d.mkdir(parents=True, exist_ok=True)
        for v in BASE["sample"]:
            if not (d / f"{v}.mp4").exists():
                subprocess.run(["yt-dlp", "-f", "bv*[height=1920]+ba/b", "--merge-output-format", "mp4",
                                "-o", str(d / f"{v}.%(ext)s"), f"https://www.youtube.com/shorts/{v}"], check=False)
        if all((d / f"{v}.mp4").exists() for v in BASE["sample"]):
            return d
    return None


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    d = _sample_dir()
    if d is None:
        pytest.skip("뜨거운사람들 표본 mp4 없음 — out/bench_cache/hotpeople 에 두거나 BENCH_DOWNLOAD=1")
    return bench.run("hotpeople", str(d), str(tmp_path_factory.mktemp("bench_hotpeople")),
                     profile=BASE["profile"])


def near(got, want, tol, what):
    assert got is not None, f"{what}: 값 없음"
    assert abs(float(got) - float(want)) <= tol + 1e-9, f"{what}: {got} (기준 {want} ±{tol})"


# ── 코드 규칙(표본 없이도 돈다) ─────────────────────────────────────────────
def test_bench_code_has_no_channel_name_or_channel_coordinate():
    """설계 §2: 코드에 채널 이름·채널 좌표가 나오면 위반. 좌표는 layout.py가 찾는다."""
    names = [r"hotpeople", r"뜨거운"] + [re.escape(v) for v in BASE["sample"]]      # 주석까지 금지
    coords = [r"\b48[23]\b", r"\b12(6[89]|7[0-9]|8[0-4])\b", r"\b790\b", r"\b1569\b"]  # 코드에서 금지
    hits = []
    for p in sorted(BENCH_DIR.glob("*.py")):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if any(re.search(b, line) for b in names) or any(re.search(b, code) for b in coords):
                hits.append(f"{p.name}:{n}: {line.strip()}")
    assert not hits, "채널 이름/좌표 하드코딩:\n" + "\n".join(hits)


def test_ffmpeg_only_through_probe():
    """설계 §2: ffmpeg/ffprobe 호출은 probe.py 하나."""
    hits = [p.name for p in BENCH_DIR.glob("*.py") if p.name != "probe.py"
            and re.search(r"subprocess|\"ffmpeg\"|'ffmpeg'|\"ffprobe\"", p.read_text(encoding="utf-8"))]
    assert not hits, f"probe 밖 ffmpeg 호출: {hits}"


# ── 결과물 검사 ────────────────────────────────────────────────────────────
def test_every_criterion_names_its_function(result):
    """기준마다 method = 실제로 있는 함수 이름(0순위-C 표식)."""
    assert result["criteria"]
    for cid, c in result["criteria"].items():
        assert c.get("method"), f"{cid}: method 없음"
        for m in c["method"].split("+"):
            mod, fn = m.split(".")
            assert hasattr(importlib.import_module(f"shopping_shorts.channelkit.bench.{mod}"), fn), f"{cid}: {m} 없음"


def test_layout_found_automatically(result):
    lay = BASE["layout"]
    L = result["layout"]
    per = result["criteria"]["L.window"]["per_video"]
    assert set(result["layout"]["variants"][result["main_variant"]]) == set(lay["main_videos"])
    for v, (y0, y1) in lay["window_y"].items():
        near(per[v][0], y0, TOL["px"], f"{v} 창 y0")
        near(per[v][1], y1, TOL["px"], f"{v} 창 y1")
    near(L["window"][0], lay["window_x"][0], TOL["px"], "창 x0")
    near(L["window"][0] + L["window"][2], lay["window_x"][1], TOL["px"], "창 x1")
    near(L["logo"][0], lay["logo_band"][0], TOL["px"], "로고 y0")
    near(L["logo"][1], lay["logo_band"][1], TOL["px"], "로고 y1")
    assert L["caption"]["pos"] == lay["caption_pos"] and L["caption"]["ink"] == lay["ink"]
    assert [c // 8 * 8 for c in L["bg_rgb"]] == lay["bg_rgb_bin8"]


def test_black_frame_video_is_a_separate_variant(result):
    for v, want in BASE["layout"]["other_variants"].items():
        pv = result["per_video"][v]
        assert pv["variant"] != result["main_variant"], f"{v}가 대표 틀에 섞였다"
        assert pv["layout"]["caption"]["pos"] == want["caption_pos"]
        assert pv["layout"]["caption"]["ink"] == want["ink"]
        w = pv["layout"]["window"]
        near(w[1], want["window_y"][0], TOL["px"], f"{v} 창 y0")
        near(w[1] + w[3], want["window_y"][1], TOL["px"], f"{v} 창 y1")


def test_captions(result):
    cr, b = result["criteria"], BASE["criteria"]
    near(cr["T.sub_count"]["total"], b["T.sub_count"]["total"], TOL["count"], "자막 총수")
    for v, n in b["T.sub_count"]["per_video"].items():
        near(len(result["per_video"][v]["captions"]["spans"]), n, TOL["count"], f"{v} 자막 수")
    for k, n in b["S.lines"]["hist"].items():
        near(cr["S.lines"]["value"].get(k, 0), n, TOL["count"], f"{k}줄 자막 수")
    near(cr["S.line_w"]["value"], b["S.line_w"]["median"], TOL["px"], "줄 폭 중앙")
    near(cr["S.line_w"]["p90"], b["S.line_w"]["p90"], TOL["px"], "줄 폭 p90")
    near(cr["S.line_w"]["max"], b["S.line_w"]["max"], TOL["px"], "줄 폭 최대")
    near(cr["L.sub_top"]["value"], b["L.sub_top"]["median"], TOL["px"], "첫 줄 y 중앙")
    near(cr["S.leading"]["value"], b["S.leading"]["median"], TOL["px"], "행간 중앙")
    m = b["S.mark"]
    near(cr["S.mark_rate"]["count"], m["count"], TOL["count"], "형광펜 자막 수")
    near(100 * cr["S.mark_rate"]["value"], 100 * m["count"] / m["n"], TOL["ratio_pp"], "형광펜 비율 %p")
    near(cr["S.mark_first"]["value"], m["first"], TOL["count"], "첫 자막 형광펜")
    near(cr["S.mark_last"]["value"], m["last"], TOL["count"], "마지막 자막 형광펜")
    s = b["T.sub_sec"]
    for k in ("median", "p10", "p90"):
        near(cr["T.sub_sec"]["value" if k == "median" else k], s[k], TOL["sec"], f"자막 노출 {k}")
    for v, med in s["per_video_median"].items():
        near(cr["T.sub_sec"]["per_video_median"][v], med, TOL["sec"], f"{v} 자막 노출 중앙")


def test_glyph(result):
    cr, b = result["criteria"], BASE["criteria"]
    near(cr["S.weight"]["value"], b["S.weight"]["median"], TOL["glyph_px"], "획 폭")
    near(cr["S.size_px"]["value"], b["S.size_px"]["median"], TOL["glyph_px"], "줄 높이")
    near(cr["S.outline"]["value"], b["S.outline"]["count"], TOL["count"], "외곽선 수")
    near(cr["S.shadow"]["value"], b["S.shadow"]["count"], TOL["count"], "그림자 수")
    assert cr["S.outline"]["n"] == b["S.outline"]["n"]


def test_cuts_raw_reproduce_old_ruler(result):
    """병합·검증 전 컷(scene>T 그대로)이 옛 자(cuts.py·rhythm_stats)와 편별로 같은가."""
    b = BASE["criteria"]["T.cut_raw"]
    pcts = []
    for v, n in b["shots_per_video"].items():
        rs = result["per_video"][v]["cuts"]["raw_stats"]
        near(rs["shots"], n, TOL["count"], f"{v} 컷 수(원자료)")
        a, m = map(int, b["cut_eq_sub_per_video"][v].split("/"))
        near(rs["cut_eq_sub"][0], a, TOL["count"], f"{v} 컷=자막 일치 수")
        near(rs["first_cut"], b["first_cut_per_video"][v], TOL["sec"], f"{v} 첫 컷")
        pcts.append(100 * rs["cut_eq_sub"][0] / max(rs["cut_eq_sub"][1], 1))
    pcts.sort()
    near(pcts[len(pcts) // 2], b["cut_eq_sub_median_pct"], TOL["ratio_pp"], "컷=자막 일치율 중앙")


def test_cuts_final(result):
    """설계 §1 컷(0.2s 병합 + 상관<0.6 검증)이 기준선 − 기록된 제외분과 같은가."""
    b = BASE["criteria"]["T.cut_count"]
    for v, n in b["per_video_final"].items():
        near(result["per_video"][v]["cuts"]["shots"], n, TOL["count"], f"{v} 컷 수")
    near(result["criteria"]["T.cut_count"]["value"], b["median"], TOL["count"], "컷 수 중앙")
    for v, ex in b["excluded"].items():
        c = result["per_video"][v]["cuts"]
        for key, got in (("merged", c["merged_out"]), ("rejected", c["rejected"])):
            assert len(got) == len(ex[key]) and all(abs(x - y) <= TOL["sec"] for x, y in zip(sorted(got), sorted(ex[key]))), \
                f"{v} {key}: {got} (기준 {ex[key]})"


def test_duration(result):
    near(result["criteria"]["T.duration"]["value"], BASE["criteria"]["T.duration"]["median"], TOL["sec"], "길이 중앙")


def test_audio(result):
    cr, b = result["criteria"], BASE["criteria"]
    for cid in ("A.lufs", "A.tp", "A.lra", "A.s_spread", "A.open3s_M"):
        for v, want in b[cid]["per_video"].items():
            near(cr[cid]["per_video"][v], want, TOL["lufs"], f"{cid} {v}")
    near(cr["A.lufs"]["value"], b["A.lufs"]["median"], TOL["lufs"], "LUFS 중앙")
    near(cr["A.lufs"]["range"][0], b["A.lufs"]["range"][0], TOL["lufs"], "LUFS 최소")
    near(cr["A.lufs"]["range"][1], b["A.lufs"]["range"][1], TOL["lufs"], "LUFS 최대")
    near(cr["A.tp"]["range"][0], b["A.tp"]["range"][0], TOL["lufs"], "TP 최소")
    near(cr["A.tp"]["range"][1], b["A.tp"]["range"][1], TOL["lufs"], "TP 최대")
    near(cr["A.open3s_M"]["quieter_open"], b["A.open3s_M"]["quieter_open"], TOL["count"], "오프닝이 조용한 편 수")
