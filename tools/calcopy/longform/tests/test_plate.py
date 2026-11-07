# 판(plates/<이름>/channel.json) 시험 — 판을 고르면 그 값이 기본 위에 얹히고, 안 고르면 기본(지식롱폼)과 같아야 한다.
# studio 는 모듈을 읽을 때 작업 폴더(SHORCL_WORK)를 보므로, 작업 폴더마다 새 파이썬을 띄워 잰다.
import json, os, subprocess, sys
import pytest

HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = json.load(open(os.path.join(HERE, "channel.json"), encoding="utf-8"))
PLATE = json.load(open(os.path.join(HERE, "plates", "모둠경제", "channel.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "plates", "모둠경제", "channel.json")) else None


def work(tmp_path, cfg=None, lines=None):
    d = tmp_path / "w"; d.mkdir(parents=True)
    (d / "장면표.py").write_text("SKIP = []\nPARA = []\nS = []\ndef add(a, b, t, **k): S.append(dict(s=[a, b], type=t, **k))\n"
                                 "add(1, 2, 'ai', prompt='x')\nadd(3, 4, 'typo', items=[(3, '', '가나', 'black', 'C', 'S1', 'stamp')])\n", encoding="utf-8")
    if cfg is not None: (d / "channel.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    if lines is not None:
        (d / "voice").mkdir(); (d / "voice" / "lines.json").write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    return str(d)


def run(wd, code, env_plate=None):
    env = dict(os.environ, SHORCL_WORK=wd, PYTHONIOENCODING="utf-8"); env.pop("SHORCL_PLATE", None)
    if env_plate: env["SHORCL_PLATE"] = env_plate
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", "import json\n" + code], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


DUMP = "from studio.settings import CFG\nprint(json.dumps(CFG, ensure_ascii=False))"


def test_default_is_base_channel_json(tmp_path):
    """판을 안 고르면 CFG = 기본 channel.json ← 작업 폴더 channel.json(얕게) 그대로."""
    cfg = run(work(tmp_path, {"channel_name": "숏클"}), DUMP)
    want = dict(BASE); want["channel_name"] = "숏클"
    assert cfg == want


def test_plate_overlays_base(tmp_path):
    assert PLATE is not None, "plates/모둠경제/channel.json 이 없다"
    cfg = run(work(tmp_path, {"channel_name": "숏클", "plate": "모둠경제"}), DUMP)
    assert cfg["plate"] == "모둠경제"
    assert cfg["logo_style"] == "badge" and cfg["logo_text"] == "숏클"
    assert cfg["caption_box"]["y0"] == 935 and cfg["caption_box"]["y1"] == 1014 and cfg["caption_box"]["bar_rgb"] == [23, 158, 198]
    assert cfg["caption_num_accent"] is False and cfg["caption_shade"] is False
    assert cfg["film_grain"] is False and cfg["dot_grid"] is False and cfg["music"] is False and cfg["bumpers"] is False
    assert cfg["chapter_label"] is False and cfg["outro_style"] == "thanks"
    assert cfg["beat_sec"] == 10.0 and cfg["cut_sec"] == 0.22 and set(cfg["cuts"]) <= {"dissolve", "blur"}
    assert abs(cfg["target_lufs"] - -15.65) < 1e-9 and cfg["voice"] == "Piljae"
    # 판의 색은 칸별로 얹힌다: 바꾼 칸만 바뀌고 나머지는 기본 그대로
    assert cfg["colors"]["yellow"] == [248, 192, 56] and cfg["colors"]["navy"] == BASE["colors"]["navy"]
    assert cfg["typo_colors"]["lime"] == [248, 192, 56] and cfg["typo_colors"]["black"] == BASE["typo_colors"]["black"]
    # 작업 폴더 값이 판보다 이긴다
    cfg2 = run(work(tmp_path / "b", {"plate": "모둠경제", "beat_sec": 7.0}), DUMP)
    assert cfg2["beat_sec"] == 7.0


def test_plate_by_env(tmp_path):
    cfg = run(work(tmp_path, {}), DUMP, env_plate="모둠경제")
    assert cfg["plate"] == "모둠경제" and cfg["music"] is False


def test_unknown_plate_stops(tmp_path):
    wd = work(tmp_path, {"plate": "없는판"})
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", "import studio.settings"], cwd=HERE, env=dict(os.environ, SHORCL_WORK=wd), capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0 and "없는판" in (r.stderr + r.stdout)


PIX = """from studio.marks import caption_bar, corner_marks
from studio.motion import film_grain, cut_in
from studio.settings import W, H
from PIL import Image
f = Image.new('RGBA', (W, H), (90, 90, 90, 255)); caption_bar(f, '1992년 4월, 서울 서초동', 1.0)
lg = Image.new('RGBA', (W, H), (90, 90, 90, 255)); lg.alpha_composite(corner_marks('본론', False))
g = film_grain(Image.new('RGBA', (W, H), (90, 90, 90, 255)), 0.3)
import numpy as np
a = np.asarray(f.convert('RGB')); lgo = np.asarray(lg.convert('RGB'))
row = a[975]; bar = [int(x) for x in np.where((abs(row[:, 0].astype(int) - 22) < 12) & (abs(row[:, 1].astype(int) - 159) < 12) & (abs(row[:, 2].astype(int) - 198) < 12))[0]]
box_dark = int((a[940, W // 2] < 70).all() and (a[925, W // 2] > 80).all())   # 상자 안은 어둡고 바로 위는 그대로(그늘이 아니라 상자)
gold = int(((a[900:1080, :, 0] > 200) & (a[900:1080, :, 1] > 150) & (a[900:1080, :, 2] < 90)).sum())
gv = np.asarray(g.convert('RGB')).astype(int); grain = int(abs(gv - 90).sum())
logo_ring = int(((abs(lgo[30:130, 30:130, 0].astype(int) - 22) < 14) & (abs(lgo[30:130, 30:130, 2].astype(int) - 198) < 14)).sum())
cur = Image.new('RGBA', (W, H), (200, 50, 50, 255))
from studio.motion import blend_cut
mid = np.asarray(blend_cut(Image.new('RGBA', (W, H), (0, 0, 200, 255)), cur, 0.5).convert('RGB'))[540, 960].tolist()
bl = np.asarray(cut_in(Image.new('RGBA', (W, H), (0, 0, 0, 255)), 'blur', 0.0).convert('RGB')).shape[0]
print(json.dumps(dict(bar=len(bar), bar_x0=bar[0] if bar else -1, box_dark=box_dark, gold=gold, grain=grain, logo_ring=logo_ring, mid=mid, bl=bl)))
"""


def test_caption_box_logo_grain_and_dissolve(tmp_path):
    """판 = 자막 상자(검정 반투명)+왼쪽 막대 #169FC6 10px, 숫자 금색 없음, 입자 없음, 원형 배지 로고, 디졸브 섞기."""
    m = run(work(tmp_path, {"plate": "모둠경제"}), PIX)
    assert 8 <= m["bar"] <= 12, m
    assert m["box_dark"] == 1 and m["gold"] == 0 and m["grain"] == 0 and m["logo_ring"] > 200
    assert all(abs(a - b) <= 3 for a, b in zip(m["mid"], [100, 25, 125])), m["mid"]
    assert m["bl"] == 1080


BASEPIX = PIX.replace("from studio.motion import blend_cut\n", "blend_cut = lambda a, b, p: b\n")


def test_default_has_no_box_and_keeps_grain(tmp_path):
    """기본 판: 띠 없음 · 숫자 금색 · 입자 있음 · 원형 배지 없음."""
    m = run(work(tmp_path, {}), BASEPIX)
    assert m["bar"] == 0 and m["box_dark"] == 0 and m["gold"] > 0 and m["grain"] > 0 and m["logo_ring"] < 50


LINES = [dict(type="line", i=1, chapter="훅", text="첫 문장입니다.", dur=2.0), dict(type="line", i=2, chapter="훅", text="둘째 문장입니다.", dur=2.0),
         dict(type="bumper"), dict(type="line", i=3, chapter="본론", text="셋째 문장입니다.", dur=2.0), dict(type="line", i=4, chapter="본론", text="넷째 문장입니다.", dur=2.0)]
SCHED = "from studio.timing import make_schedule\ntl = make_schedule()\nprint(json.dumps(dict(ev=[e['kind'] for e in tl['events']], total=tl['total'], last_t1=tl['shots'][-1]['t1'], subs=[s['text'] for s in tl['subs']])))"


def test_schedule_plate_no_bumper_thanks_outro(tmp_path):
    m = run(work(tmp_path, {"plate": "모둠경제"}, LINES), SCHED)
    assert m["ev"] == ["outro"], m["ev"]                          # 범퍼·챕터 와이프 없음
    assert m["subs"][-1] == PLATE["outro_text"]                   # 마지막 자막 = 감사 인사
    assert abs(m["last_t1"] - m["total"]) < 1e-6                  # 마지막 장면이 끝까지 이어진다(끝 화면 카드 없음)
    assert abs(m["total"] - (8.0 + PLATE.get("line_gap", BASE["line_gap"]) * 4 + PLATE.get("chapter_gap", BASE["chapter_gap"]) + 0.4 + PLATE["outro_sec"])) < 0.01


def test_schedule_default_unchanged(tmp_path):
    m = run(work(tmp_path, {}, LINES), SCHED)
    assert m["ev"] == ["bumper", "outro"] and m["subs"][-1] != "끝까지 시청해 주셔서 감사합니다"
    assert m["last_t1"] < m["total"]


def _narrate(tmp_path, cfg):
    """합성 소리(무음 0.3초 + 1초 소리 + 무음 0.3초)를 raw 에 두고 narrate.py 자르기만 돌린다(raw 가 있으면 녹음 호출 없음, 키도 가짜)."""
    import wave, math, struct
    wd = tmp_path / "n"; (wd / "voice" / "raw").mkdir(parents=True)
    if cfg is not None: (wd / "channel.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    (wd / "대본.md").write_text("## [훅]\n첫 문장입니다.\n", encoding="utf-8")
    sr = 48000; fr = [0.0] * int(0.3 * sr) + [0.5 * math.sin(2 * math.pi * 220 * k / sr) for k in range(sr)] + [0.0] * int(0.3 * sr)
    with wave.open(str(wd / "voice" / "raw" / "001.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(b"".join(struct.pack("<h", int(x * 32767)) for x in fr))
    env = dict(os.environ, TYPECAST_API_KEY="no-call", PYTHONIOENCODING="utf-8"); env.pop("SHORCL_PLATE", None); env.pop("SHORCL_WORK", None)
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "steps", "narrate.py"), str(wd / "대본.md"), str(wd / "voice")], cwd=str(wd), env=env, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    L = json.load(open(wd / "voice" / "lines.json", encoding="utf-8"))
    return L[0]["dur"], (wd / "voice" / "trim" / "001.wav").read_bytes(), r.stdout


def test_narrate_stretch_default_is_old_filter(tmp_path):
    """기본(voice_stretch 1.0)은 예전 자르기 필터와 같은 바이트."""
    import subprocess as sp
    dur, data, out = _narrate(tmp_path, None)
    assert "voice_stretch 1.0" in out
    raw = tmp_path / "n" / "voice" / "raw" / "001.wav"; old = tmp_path / "old.wav"
    af = ("silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.06,"
          "areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.08,areverse,"
          "aresample=48000,aformat=channel_layouts=mono")
    sp.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", af, str(old)], check=True)
    assert data == old.read_bytes()


def test_narrate_stretch_plate(tmp_path):
    """판 모둠경제(voice_stretch 0.917)는 자른 소리가 1/0.917 배 길다."""
    d0, _, _ = _narrate(tmp_path / "a", None)
    d1, _, out = _narrate(tmp_path / "b", {"plate": "모둠경제"})
    assert "voice_stretch 0.917" in out
    assert abs(d1 / d0 - 1 / PLATE["voice_stretch"]) < 0.03, (d0, d1)   # atempo 는 끝을 20~40ms 짧게 낸다(실녹음 3줄 1.080~1.089 / 기대 1.0905)


WRAP = """from studio.stage import side_word
from studio.settings import W, H
from PIL import Image
import numpy as np
im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); side_word(im, 'slant_r', '1인당 5845만 원', 1.0)
a = np.asarray(im.convert('RGB'))[:, 1430:1900].max(axis=2) > 200
rows = np.where(a.any(axis=1))[0]; bands, cur = [], [rows[0], rows[0]]
for y in rows[1:]:
    if y - cur[1] > 8: bands.append(cur); cur = [y, y]
    else: cur[1] = y
bands.append(cur); last = a[bands[-1][0]:bands[-1][1] + 1]; xs = np.where(last.any(axis=0))[0]
print(json.dumps(dict(n=len(bands), last_w=int(xs.max() - xs.min()))))
"""


def test_side_word_keeps_number_with_unit(tmp_path):
    """옆 큰 글자: '5845만 원' 의 단위가 혼자 다음 줄로 떨어지지 않는다(timing.glued)."""
    m = run(work(tmp_path, {"plate": "모둠경제"}), WRAP)
    assert m["last_w"] > 150, m   # 마지막 줄이 '원' 한 글자(약 70px)면 실패
