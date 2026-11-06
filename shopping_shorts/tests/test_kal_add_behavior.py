"""칼카피 엔진 추가 1~8번 — 동작 시험(11-06 감시 ② 보강).

앞 시험은 고치기 전 판에서 '함수가 없어서' 실패했다(무엇을 고쳤는지 재지 못함). 여기 시험은 **고치기 전부터 있던 입구**
(step_collect·scene_cuts·to_frame.build·fontmatch.line_masks·preset_gates.text_gate·step_tteutgi·step_rules·skeleton)만 부르고,
새 인자는 그 함수가 받을 때만 넘긴다(_kw) — 그래서 고치기 전 판(cd98e3202)에서는 **값이 틀려서**(AssertionError) 실패한다.
새 판단 이름(check_fetched·crop_vf·caption_cluster·separate·state4_of·line_kind_draft·paren_tts_gate)을 맨 위에서 import 하지 않는다.
"""
import inspect
import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from tools.calcopy.engine import kal
from tools.calcopy.engine import kal_analyze as KA


def _kw(fn, *a, **kw):
    """fn 이 받는 키워드만 넘긴다 — 고치기 전 판(인자 없음)은 옛 동작으로 돈다."""
    ps = inspect.signature(fn).parameters
    return fn(*a, **{k: v for k, v in kw.items() if k in ps})


def _mp4(path: Path, dur=3.0, audio=True):
    a = ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"] if audio else []
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=30", *a,
                    "-t", str(dur), "-c:v", "libx264", "-preset", "ultrafast", *(["-c:a", "aac", "-shortest"] if audio else []), str(path)],
                   check=True)


def _state(tmp_path, monkeypatch, slug="s1"):
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    monkeypatch.setattr(kal, "DATA", tmp_path / "data")
    S = kal.State(slug, "@ch", "우리", 2, "아니오", "v")
    S.d["slug"] = slug
    return S


# 1 · 표 #14·#15 — 받은 영상 검사: 소리 줄기 없는 파일은 '받음'에 넣지 않는다
def test_1_collect_drops_file_without_audio(tmp_path, monkeypatch):
    S = _state(tmp_path, monkeypatch)
    monkeypatch.setattr(kal, "disk_gate", lambda w: None)
    monkeypatch.setattr(kal, "MIN_FILE_BYTES", 1000, raising=False)        # 시험 파일은 작다(없던 판엔 그냥 새 이름)
    S.d["channel"] = {"top_ids": ["a", "b", "c"]}

    def fake_fetch(base, vid, url, fmt):
        d = {"a": 3.0, "b": 3.2, "c": 3.4}[vid]                          # 길이를 달리해 같은 파일(sha256) 빼기에 안 걸리게
        _mp4(base / f"{vid}.mp4", dur=d, audio=(vid != "b"))
        (base / f"{vid}.info.json").write_text(json.dumps({"duration": d}), encoding="utf-8")
        return 0, ""
    monkeypatch.setattr(kal, "fetch_one", fake_fetch)
    monkeypatch.setattr(kal, "_run", lambda cmd, timeout=0: subprocess.CompletedProcess(cmd, 0, "", ""))
    st, out, note = kal.step_collect(S)
    assert st == "done", note
    assert out["ids"] == ["a", "c"], out["ids"]          # 고치기 전: ['a','b','c'] — 소리 없는 b 도 '받음'


# 2 · 표 #71·#219 — 홀수 창 크롭은 exact(1px 밀림 금지): 분석 자 scene_cuts 가 ffmpeg 에 넘기는 필터
def test_2_scene_cuts_crop_is_exact(monkeypatch):
    seen = []

    def fake_run(cmd, **k):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    KA.scene_cuts("x.mp4", win=(0, 521, 1080, 1399))
    vf = next(c[c.index("-vf") + 1] for c in seen if "-vf" in c)
    assert vf.startswith("crop=1080:1399:0:521:exact=1"), vf   # 고치기 전: 'crop=1080:1399:0:521,' (짝수로 내려 한 줄 위)


# 3 · 표 #112·#174 — kal 뜯기(kal_mode)는 자막 칸 폭 = 벤치 1줄 자막 잰 폭, 크기 = (표본 없으면) 군집 폭 역산
def _cap_tear(fam_size_widths, kal_mode=True):
    texts, widths = zip(*fam_size_widths)
    J = {"engine": "합성", "source": "none.mp4", "probe": {"w": 1080, "h": 1920, "duration": 20.0},
         "layout": {"window": [0, 500, 1080, 1000], "bg_rgb": [250, 250, 250], "ink_polarity": "dark", "above_bands": [], "other_frame_segments": []},
         "captions": {"spans": [[0, 20]], "items": [{"i": k, "t0": 2 * k, "t1": 2 * k + 2, "lines": 1, "widths": [w], "top_y": 1600, "text": [t]}
                                                   for k, (t, w) in enumerate(zip(texts, widths))], "glyph": [{"line_h": 30}]},
         "text_fx": {"summary": {"fill_rgb": [0, 0, 0], "outline_px": 0, "outline_rgb": None, "box": None, "shadow": None, "line_h_px": 30}},
         "fonts": {"ok": True, "top3": [{"font": "BMJUA.ttf", "score": 0.5}], "per_crop": []}}
    if kal_mode:
        J["kal_mode"] = True
    return J


def test_3_caption_width_and_size_from_bench_widths():
    from tools.calcopy.engine import to_frame as T
    T_ = ["유치원 학예회 무대에서", "한 친구의 의자만 감쪽같이", "다들 앉아 율동하는데", "아무리 둘러봐도 빈 의자가 없자"]
    probe = T.build(_cap_tear([(t, 500) for t in T_]), None, None)
    fam = next(l for l in probe["layers"] if l.get("role") == "caption")["font"]
    f = T._pil_font(fam, 64)
    J = _cap_tear([(t, round(f.getlength(t))) for t in T_])
    c = next(l for l in T.build(J, None, None)["layers"] if l.get("role") == "caption")
    assert c["w"] == max(round(f.getlength(t)) for t in T_), c["w"]      # 고치기 전: 1000(W − 2×40 상수)
    assert abs(c["size"] - 64) <= 2, c["size"]                          # 고치기 전: 높이 30 에서 역산한 작은 크기


def test_3b_member_tear_keeps_old_width():
    """회원 PC 벤치마킹(kal_mode 표식 없음)은 예전 동작 — 상수 폭 그대로(11-06 Jev 해결 0.80)."""
    from tools.calcopy.engine import to_frame as T
    T_ = ["유치원 학예회 무대에서", "한 친구의 의자만 감쪽같이", "다들 앉아 율동하는데"]
    f = T._pil_font("BMJUA", 64)
    c = next(l for l in T.build(_cap_tear([(t, round(f.getlength(t))) for t in T_], kal_mode=False), None, None)["layers"] if l.get("role") == "caption")
    assert c["w"] == 1080 - 2 * T.SIDE_PAD


# 4 · 표 #222 — 자막 아래 영상 속 흰 덩어리가 붙어도 줄 마스크 높이는 줄 높이 근처
def test_4_line_mask_ignores_video_blob():
    from PIL import Image, ImageDraw
    from tools.calcopy.engine import fontmatch as FM, to_frame as T
    im = Image.new("RGB", (1080, 300), (40, 60, 80))
    d = ImageDraw.Draw(im)
    d.text((540, 120), "한 친구의 의자만 감쪽같이", font=T._pil_font("BMJUA", 60), fill=(255, 255, 255), anchor="ms",
           stroke_width=4, stroke_fill=(0, 0, 0))
    d.rectangle((700, 118, 900, 290), fill=(250, 250, 250))       # 글자 줄에 붙은 흰 옷(영상)
    ms = _kw(FM.line_masks, np.asarray(im), "bright", line_h=54, n_lines=1)
    assert len(ms) == 1
    assert ms[0].shape[0] <= 54 + FM.__dict__.get("LINE_PAD_PX", 6), ms[0].shape   # 고치기 전: 흰 덩어리까지 한 줄(170px 넘음)


# 5 · 표 #230 — TTS 줄이 통째 괄호(지문)면 G-1 관문(판 칸 checks.paren_tts)이 막는다
def test_5_text_gate_blocks_whole_paren_tts_line():
    from tools.calcopy.engine import preset_gates as PG
    w = {"lines": [{"text": "첫 줄 이야기", "tts": "첫 줄 이야기"}, {"text": "(바로 퀵 전화해봄)", "tts": "(바로 퀵 전화해봄)"},
                   {"text": "이걸(채소보관용기) 팔더라고요", "tts": "이걸(채소보관용기) 팔더라고요"}]}
    bad = PG.text_gate(w, {"checks": {"paren_tts": True}})
    assert any("2줄" in b and "괄호" in b for b in bad), bad            # 고치기 전: 판 칸을 몰라 통과
    assert not any("3줄" in b and "괄호" in b for b in bad)           # 줄 일부 괄호(뜻풀이)는 건드리지 않는다


# 6 · 표 #28 — kal 뜯기 단계는 옛 뜯기에 목소리 칸(초안)과 kal 표식을 더한다
def test_6_tteutgi_adds_separation_draft(tmp_path, monkeypatch):
    S = _state(tmp_path, monkeypatch)
    S.d["channel"] = {"top_ids": ["v1"]}
    S.mark("collect", "done", 0, {"ids": ["v1"]})
    (tmp_path / "data/s1/src").mkdir(parents=True)
    (tmp_path / "data/s1/src/v1.mp4").write_bytes(b"x")
    tp = S.dir / "뜯기" / "v1" / "뜯기.json"
    tp.parent.mkdir(parents=True)
    tp.write_text(json.dumps({"engine": "x", "captions": {"spans": []}}), encoding="utf-8")
    monkeypatch.setattr(kal, "_stale_tear", lambda p: None)
    fake = types.ModuleType("tools.calcopy.engine.separate")
    fake.separation_of = lambda mp4, out: {"model": "htdemucs", "voice": {"frames": [True, False], "draft": True}, "bg": {"frames": [True, True]}}
    import tools.calcopy.engine as E
    monkeypatch.setitem(sys.modules, "tools.calcopy.engine.separate", fake)
    monkeypatch.setattr(E, "separate", fake, raising=False)
    st, out, note = kal.step_tteutgi(S)
    J = json.loads(tp.read_text(encoding="utf-8"))
    assert st == "done"
    assert J.get("kal_mode") is True and (J.get("separation") or {}).get("voice", {}).get("draft") is True, J   # 고치기 전: 칸 없음


def test_6b_voice_frames_are_draft(tmp_path):
    """목소리 칸 판정은 초안 — 말 섞인 정답 편이 모자라면 draft=True(규칙·판정에 쓰지 않는다)."""
    import wave
    from tools.calcopy.engine import separate as SEP
    for name, amp in (("v.wav", 8000), ("b.wav", 400)):
        with wave.open(str(tmp_path / name), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes((np.sin(np.arange(44100) / 5) * amp).astype(np.int16).tobytes())
    r = SEP.voice_frames(str(tmp_path / "v.wav"), str(tmp_path / "b.wav"))
    assert r["draft"] is True and r["evidence"]["mixed_videos"] < SEP.VOICE_RULE_MIN_MIXED
    assert "초안" in r["use"]


# 7 · 표 #32·#33 — rules 단계가 0.1초 소리·자막 칸 격자를 쓴다(초안 표시·쉼 메우기 포함)
class _Stop(Exception):
    pass


def test_7_rules_writes_grid(tmp_path, monkeypatch):
    S = _state(tmp_path, monkeypatch)
    S.mark("tteutgi", "done", 0, {"ids": ["v1"]})
    tp = S.dir / "뜯기" / "v1" / "뜯기.json"
    tp.parent.mkdir(parents=True)
    voice = [1] * 10 + [0] + [1] * 9 + [0] * 10           # 1.0초 말 + 0.1초 쉼 + 0.9초 말 + 1초 자막만
    tp.write_text(json.dumps({"captions": {"spans": [[0, 3.0]]},
                              "separation": {"voice": {"frames": voice, "draft": True}, "bg": {"frames": [1] * 30}}}), encoding="utf-8")
    monkeypatch.setattr(KA, "_load_docs", lambda dirs: [])
    monkeypatch.setattr(KA, "write_rules", lambda d, docs, slug: {"rules": {}, "script": {}, "palette": {"roles": {}}})
    monkeypatch.setattr(KA, "rules_md", lambda R, slug: (_ for _ in ()).throw(_Stop()))    # 격자 쓴 다음 줄에서 멈춘다
    with pytest.raises(_Stop):
        kal.step_rules(S)
    got = list((S.dir / "_kal").glob("*.json"))
    grid = [json.loads(p.read_text(encoding="utf-8")) for p in got]
    pv = next((g["per_video"]["v1"] for g in grid if "per_video" in g), None)
    assert pv is not None, [p.name for p in got]                           # 고치기 전: 격자 파일 없음
    assert pv["seq"] == "V" * 20 + "S" * 10 and pv["gap_fill"]["cells"] == 1    # 0.1초 쉼은 메운다
    assert pv["draft"] is True


# 8 · 표 #30 — 줄판독 뼈대가 줄 종류 초안을 채운다(사람 칸은 비움)
def test_8_skeleton_fills_kind_draft():
    tt = {"probe": {"h": 1920, "duration": 4},
          "captions": {"items": [{"i": 0, "t0": 0, "t1": 1, "top_y": 1200, "text": ["안녕하세요 여러분"]},
                                 {"i": 1, "t0": 1, "t1": 2, "top_y": 1200, "text": ["오늘은 이걸 봐요"]},
                                 {"i": 2, "t0": 2, "t1": 3, "top_y": 600, "text": ["쾅 터졌다"]}]},
          "audio": {"transcript": {"segments": [{"start": 0.0, "end": 2.0, "text": "안녕하세요 여러분 오늘은 이걸 봐요"}]}}}
    L = KA.skeleton("v1", tt)["lines"]
    g = [(l.get("_kind_draft") or {}).get("guess") for l in L]
    assert g[0] == g[1] == "말과 같은 자막(대사·나레)" and g[2] == "말과 다른 자막(해설·효과)", g   # 고치기 전: 칸 없음(None)
    assert all(l["speaker"] is None and l["layer"] is None for l in L)          # 사람 칸은 비워 둔다
