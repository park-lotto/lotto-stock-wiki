# -*- coding: utf-8 -*-
"""레퍼런스 역설계 — 판단 주인 reverse_engineer (관제 244, 2026-10-20 사장님 "프롬프트 없는 레퍼런스도 역설계해서 진행해").

레퍼런스 mp4 → ① 실측(ffmpeg/ffprobe + PIL): 규격·장면 경계(scene 검출)·장면별 대표 프레임·바탕색 팔레트 HEX·전경 비율·움직임 세기·컷 박자
            → ② 16칸 시트 + 장면별 띠
            → ③ 지시서(brief): Claude(claude -p 헤드리스, 메모리 reference_claude_max_on_server 와 같은 길)가 프레임을 보고 쓴다.
               칸 = PRODUCT·STORY·FORMAT·LOOK·MOTION·SOUND·QUALITY_CHECK·RULES + FORBIDDEN. 줄마다 [실측]/[추정] 표시 —
               실측 = measure.json 숫자에서 온 것, 추정 = 모델이 프레임을 보고 읽은 것(수치 지어내기 금지, 없으면 "없음").
            → ④ 장부 data/refs.jsonl 에 저장(메타·실측·지시서·status draft) — 승인(approve_ref)은 작업대에서 사장님이.
산출물 폴더: shopping_shorts/data/mograph/refs/<id>/ (git 밖) — measure.json · sheet.png · scenes/s00.png… · strip.png · brief.md · brief.json · status.json
원본 mp4 는 저장소 밖(sources.jasonzhu_dir)에서만 읽는다 — 영상 권리는 제작자(라이선스 ref_only).

유튜브 조사(2026-10-20)에서 가져온 방법: 영상 파일을 쪼개 본다(wOF1EDpWxQw) / 레이아웃·타이포·페이싱·전환·이징은 배우고 색은 우리 브랜드,
수치 지어내지 말고 없으면 말하라(OIAWkkSO4WY) / Plan→stills→animatic→render 관문·8점 비평 루프(0xMovez)."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from shopping_shorts.mograph import ledger, sources

REFS_DIR = Path(__file__).resolve().parents[1] / "data" / "mograph" / "refs"
SCENE_THRESHOLD = 0.22          # ffmpeg scene 점수 문턱(0~1). 바탕색 통째 전환은 0.5 이상, 글자만 바뀌는 컷은 0.2~0.35 가 많다(Pocketsflow 실측)
MIN_SCENE_S = 0.25              # 이보다 짧은 경계는 앞 장면에 붙인다(플래시 프레임)
SAMPLE_FPS = 10                 # 움직임 세기 재는 표본 fps
SHEET_TILES = 16
BRIEF_SECTIONS = ("PRODUCT", "STORY", "FORMAT", "LOOK", "MOTION", "SOUND", "QUALITY_CHECK", "RULES", "FORBIDDEN")
_RUNNING = {}
_LOCK = threading.Lock()
_ID = re.compile(r"^[0-9]{10,25}$")


def out_dir(ref_id):
    return REFS_DIR / ref_id


def status(ref_id):
    p = out_dir(ref_id) / "status.json"
    if not p.exists():
        return {"id": ref_id, "state": "none"}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:       # noqa: BLE001 — 쓰는 도중 읽힘
        return {"id": ref_id, "state": "running"}


def _put(ref_id, **kw):
    d = out_dir(ref_id)
    d.mkdir(parents=True, exist_ok=True)
    st = status(ref_id)
    st.update(kw)
    st["id"] = ref_id
    st["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = d / "status.json.tmp"
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, d / "status.json")
    return st


def _run(cmd, timeout=300, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          cwd=cwd, shell=(os.name == "nt"))


# ── ① 실측 ──────────────────────────────────────────────────────────────────
def probe(mp4):
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
              "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", str(mp4)], 60)
    j = json.loads(r.stdout or "{}")
    s = (j.get("streams") or [{}])[0]
    num, _, den = str(s.get("r_frame_rate") or "30/1").partition("/")
    fps = float(num) / float(den or 1)
    has_audio = "audio" in (_run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
                                  "-of", "csv=p=0", str(mp4)], 60).stdout or "")
    return {"w": int(s.get("width") or 0), "h": int(s.get("height") or 0), "fps": round(fps, 3),
            "frames": int(s.get("nb_frames") or 0), "duration": float((j.get("format") or {}).get("duration") or 0),
            "has_audio": has_audio}


def _series(mp4, tmpdir):
    """영상 전체를 SAMPLE_FPS 로 뽑아(160px) 표본마다 바탕색(최빈 양자화 색)·이웃 프레임 평균 절대차를 잰다. 한 번만 뽑아 장면 검출·움직임 세기가 같이 쓴다."""
    import numpy as np
    from PIL import Image
    pat = Path(tmpdir) / "f%05d.png"
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vf", "fps=%d,scale=160:-1" % SAMPLE_FPS, str(pat)], 600)
    frames = sorted(Path(tmpdir).glob("f*.png"))
    out, prev = [], None
    for i, f in enumerate(frames):
        im = Image.open(f).convert("RGB")
        a = np.asarray(im, dtype=np.int16)
        q = (a // 32) * 32 + 16                                   # 32단계 양자화 → 최빈색 = 바탕색
        flat = q.reshape(-1, 3).astype(np.int64)
        keys, counts = np.unique(flat[:, 0] * 65536 + flat[:, 1] * 256 + flat[:, 2], return_counts=True)
        k = int(keys[counts.argmax()])
        bg = "#%02X%02X%02X" % (k >> 16, (k >> 8) & 255, k & 255)
        g = np.asarray(im.convert("L"), dtype=np.float32)
        diff = float(np.abs(g - prev).mean()) if prev is not None else 0.0
        out.append({"t": round(i / SAMPLE_FPS, 3), "bg": bg, "bg_share": round(float(counts.max() / flat.shape[0]), 3), "diff": round(diff, 2)})
        prev = g
    return out


def scene_cuts(mp4, duration, series, threshold=SCENE_THRESHOLD, diff_spike=28.0, min_gap=0.4):
    """장면 경계 = ffmpeg scene 검출(하드컷) ∪ 바탕색 전환(표본 바탕색이 바뀌어 0.3초 이상 유지) ∪ 프레임차 급등(와이프·줌 전환).
    애니메이션 전환이 많은 모션그래픽은 scene 점수만으론 못 잡는다(Pocketsflow 실측: 0.22 문턱에 3장면 — 시트는 8박자 이상)."""
    r = _run(["ffmpeg", "-v", "info", "-i", str(mp4), "-vf", "select='gt(scene,%s)',showinfo" % threshold, "-an", "-f", "null", "-"], 600)
    cand = [(float(m), "cut") for m in re.findall(r"pts_time:\s*([0-9.]+)", r.stderr or "")]
    hold = max(1, int(0.3 * SAMPLE_FPS))
    for i in range(1, len(series)):
        a, b = series[i - 1], series[i]
        if _dist(a["bg"], b["bg"]) > 80 and all(_dist(series[j]["bg"], b["bg"]) <= 80 for j in range(i, min(len(series), i + hold))):
            cand.append((b["t"], "bg"))
        if b["diff"] >= diff_spike and b["diff"] >= 1.8 * max(a["diff"], 1.0):
            cand.append((b["t"], "spike"))
    cuts, last = [], 0.0
    for t, why in sorted(cand):
        if t - last >= min_gap and duration - t >= MIN_SCENE_S:
            cuts.append((round(t, 3), why))
            last = t
    bounds = [0.0] + [t for t, _ in cuts] + [round(duration, 3)]
    whys = ["start"] + [w for _, w in cuts]
    return [{"i": i, "t0": bounds[i], "t1": bounds[i + 1], "dur": round(bounds[i + 1] - bounds[i], 3), "cut_by": whys[i]} for i in range(len(bounds) - 1)]


def _frame(mp4, t, png, width=480):
    _run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t, "-i", str(mp4), "-frames:v", "1", "-vf", "scale=%d:-1" % width, str(png)], 60)
    return png.exists()


def _palette(img, k=4):
    """대표색 k개(HEX, 비율). 양자화는 PIL 의 중앙값 자르기 — 바탕색 = 1위."""
    from PIL import Image
    small = img.convert("RGB").resize((96, int(96 * img.height / img.width) or 1))
    q = small.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: k * 3]
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    out = []
    for c, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        out.append({"hex": "#%02X%02X%02X" % (r, g, b), "share": round(c / total, 3)})
    return out


def _foreground(img, bg_hex, tol=60):
    """바탕색과 먼 픽셀 = 전경. 전경 비율·전경이 차지하는 세로 띠 높이 비율(글자·물체 크기의 상한)."""
    import numpy as np
    a = np.asarray(img.convert("RGB").resize((240, int(240 * img.height / img.width) or 1)), dtype=np.int16)
    bg = np.array([int(bg_hex[1:3], 16), int(bg_hex[3:5], 16), int(bg_hex[5:7], 16)], dtype=np.int16)
    mask = np.abs(a - bg).sum(axis=2) > tol
    h = mask.shape[0]
    rows = np.where(mask.mean(axis=1) > 0.02)[0]
    cols = np.where(mask.mean(axis=0) > 0.02)[0]
    band_h = (rows.max() - rows.min() + 1) / h if rows.size else 0.0
    band_w = (cols.max() - cols.min() + 1) / mask.shape[1] if cols.size else 0.0
    return {"fg_ratio": round(float(mask.mean()), 3), "fg_band_h": round(float(band_h), 3), "fg_band_w": round(float(band_w), 3),
            "fg_center_y": round(float(rows.mean() / h), 3) if rows.size else None}


def _motion_energy(series, t0, t1):
    """구간 표본의 이웃 프레임 평균 절대차(0~255). 0~4 정지 · 4~15 보통 · 15+ 큰 움직임/전환. 첫 표본(경계 자체)은 뺀다."""
    diffs = [x["diff"] for x in series if t0 < x["t"] < t1]
    if not diffs:
        return {"energy_mean": 0.0, "energy_max": 0.0, "samples": 0}
    return {"energy_mean": round(sum(diffs) / len(diffs), 2), "energy_max": round(max(diffs), 2), "samples": len(diffs)}


def measure(mp4, d):
    """실측 전부 → measure.json. 장면별 대표 프레임(scenes/sNN.png, 가운데 시각)과 시작 프레임(sNN_a.png)도 남긴다."""
    from PIL import Image
    pr = probe(mp4)
    sdir = d / "scenes"
    sdir.mkdir(parents=True, exist_ok=True)
    for f in sdir.glob("s*.png"):
        f.unlink()
    tmpdir = tempfile.mkdtemp(prefix="mg_rev_")
    try:
        series = _series(mp4, tmpdir)
        scenes = scene_cuts(mp4, pr["duration"], series)
        for sc in scenes:
            mid = sc["t0"] + sc["dur"] * 0.6          # 등장 모션이 끝난 뒤(60% 지점) 가 그 장면의 "완성 그림"
            png = sdir / ("s%02d.png" % sc["i"])
            _frame(mp4, mid, png)
            _frame(mp4, sc["t0"] + min(0.08, sc["dur"] / 2), sdir / ("s%02d_a.png" % sc["i"]))
            img = Image.open(png)
            pal = _palette(img)
            sc.update({"frame": png.name, "t_frame": round(mid, 3), "palette": pal, "bg": pal[0]["hex"]})
            sc.update(_foreground(img, pal[0]["hex"]))
            sc.update(_motion_energy(series, sc["t0"], sc["t1"]))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    durs = [s["dur"] for s in scenes]
    bgs = [s["bg"] for s in scenes]
    bg_flips = sum(1 for a, b in zip(bgs, bgs[1:]) if _dist(a, b) > 80)
    m = {"probe": pr, "ratio": "%d:%d" % _ratio(pr["w"], pr["h"]), "scene_count": len(scenes),
         "scene_dur": {"min": min(durs), "max": max(durs), "mean": round(sum(durs) / len(durs), 3)},
         "cuts_per_s": round((len(scenes) - 1) / pr["duration"], 3) if pr["duration"] else 0,
         "bg_flips": bg_flips, "bg_sequence": bgs, "scenes": scenes,
         "cut_by": {k: sum(1 for s in scenes if s["cut_by"] == k) for k in ("cut", "bg", "spike")},
         "series": series, "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "threshold": SCENE_THRESHOLD, "sample_fps": SAMPLE_FPS}
    (d / "measure.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return m


def _dist(h1, h2):
    a = [int(h1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(h2[i:i + 2], 16) for i in (1, 3, 5)]
    return sum(abs(x - y) for x, y in zip(a, b))


def _ratio(w, h):
    import math
    g = math.gcd(w, h) or 1
    return w // g, h // g


# ── ② 시트 ──────────────────────────────────────────────────────────────────
def contact_sheet(mp4, png, duration, tiles=SHEET_TILES, cols=4, width=320):
    step = max(duration / tiles, 1 / 30)
    rows = -(-tiles // cols)
    vf = "fps=1/%.4f,scale=%d:-1,tile=%dx%d:padding=4:margin=4" % (step, width, cols, rows)
    r = _run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vf", vf, "-frames:v", "1", str(png)], 120)
    return png.exists(), (r.stderr or "")[-300:]


def scene_strip(d, m, png, width=240):
    """장면별 대표 프레임을 한 줄 띠로(아래 시각·길이·바탕 HEX 글자). PIL 만."""
    from PIL import Image, ImageDraw
    imgs = []
    for sc in m["scenes"]:
        p = d / "scenes" / sc["frame"]
        if p.exists():
            im = Image.open(p).convert("RGB")
            imgs.append((sc, im.resize((width, int(width * im.height / im.width)))))
    if not imgs:
        return False
    h = max(im.height for _, im in imgs)
    sheet = Image.new("RGB", (width * len(imgs) + 4 * (len(imgs) + 1), h + 44), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    x = 4
    for sc, im in imgs:
        sheet.paste(im, (x, 4))
        dr.text((x + 4, h + 10), "#%d %.1f-%.1fs (%.1fs) bg %s fg %.0f%%" % (sc["i"], sc["t0"], sc["t1"], sc["dur"], sc["bg"], sc["fg_ratio"] * 100), fill=(230, 230, 230))
        x += width + 4
    sheet.save(png)
    return True


# ── ③ 지시서 ────────────────────────────────────────────────────────────────
def brief_prompt(meta, m, d, product_hint=""):
    sc_lines = "\n".join(
        "- 장면 %d: %.2f~%.2f초(%.2f초) 바탕 %s 팔레트 %s 전경 %.0f%% 전경띠 높이 %.0f%% 세로중심 %s 움직임 평균 %.1f 최대 %.1f · 프레임 %s"
        % (s["i"], s["t0"], s["t1"], s["dur"], s["bg"], " ".join(p["hex"] for p in s["palette"]), s["fg_ratio"] * 100, s["fg_band_h"] * 100,
           s["fg_center_y"], s["energy_mean"], s["energy_max"], str((d / "scenes" / s["frame"]).resolve()))
        for s in m["scenes"])
    t = meta.get("title") or {}
    return f"""당신은 모션그래픽 역설계자다. 아래 레퍼런스 영상의 프레임(시트 1장 + 장면별 프레임)을 Read 도구로 직접 보고, 이 영상을 **같은 문법으로 다시 만들 수 있는 지시서**를 쓴다.

레퍼런스: {t.get('en') or ''} / 제작자 {((meta.get('creator') or {}).get('handle') or '')} / 조회 {meta.get('views') or ''} / 모델 {','.join(meta.get('models') or [])}
규격(실측): {m['probe']['w']}×{m['probe']['h']} {m['probe']['fps']}fps {m['probe']['duration']:.2f}초 · 장면 {m['scene_count']}개 · 컷/초 {m['cuts_per_s']} · 바탕색 통째 전환 {m['bg_flips']}회 · 소리 트랙 {'있음' if m['probe']['has_audio'] else '없음'}
장면별 실측(바탕 HEX = 대표 프레임 1위 색, 전경 = 바탕과 먼 픽셀, 움직임 = 이웃 프레임 평균 절대차 0~255):
{sc_lines}
시트(16칸, 시간순): {str((d / 'sheet.png').resolve())}
장면 띠: {str((d / 'strip.png').resolve())}

규칙(유튜브 조사 2026-10-20 OIAWkkSO4WY·0xMovez 에서 가져옴):
1. 레이아웃·타이포 위계·페이싱·전환·이징·카메라·연결 물체는 **레퍼런스에서 배운다**. 색은 바꿀 수 있는 자리(우리 브랜드 색)로 표시한다.
2. 수치를 지어내지 마라. 숫자는 위 실측에서만 가져오고, 프레임을 보고 읽은 것은 [추정] 으로 표시한다. 모르면 "없음" 이라고 쓴다.
3. 줄마다 앞에 [실측] 또는 [추정] 을 붙인다. [실측] 은 위 숫자를 그대로 인용할 때만.
4. 가짜 UI·가짜 결제·실제 브랜드 로고·실사 사진을 지어내 넣으라는 지시는 금지 목록에 넣어라(상품 이미지가 없으면 도형/아이콘으로 대체하라고 적는다).
5. 한국어로 쓴다. 영어 고유명사는 그대로.

출력은 아래 JSON 하나만(코드펜스 없이). 각 칸은 문자열 줄 배열이다.
{{
 "PRODUCT": ["[추정] 무엇을 파는 영상인가, 누구에게"],
 "STORY": ["[실측] 장면 N: t0~t1 — 무슨 일이 일어나나(글자·물체·행동)", "..."],
 "FORMAT": ["[실측] 규격·길이·장면 수·컷 박자", "[추정] 세로 1080×1920 로 옮길 때 바꿀 것"],
 "LOOK": ["[실측] 팔레트 HEX 와 역할(바탕/강조/글자)", "[추정] 글꼴 성격·글자 크기(화면 높이 대비)·질감(하프톤 등)·레이아웃 격자"],
 "MOTION": ["[추정] 등장·전환·이징·연결 물체·카메라, 장면마다", "[실측] 움직임 세기 숫자 인용"],
 "SOUND": ["[실측] 소리 트랙 유무", "[추정] 어울리는 효과음 자리(장면 번호)"],
 "QUALITY_CHECK": ["렌더 뒤 0.5초 프레임을 보고 확인할 것 N개(빈 프레임 없음·글자 겹침 없음·안전영역 등)"],
 "RULES": ["이 문법을 지키기 위한 규칙(장면마다 바탕 통째 전환 등)"],
 "FORBIDDEN": ["금지 목록"],
 "grammar": {{"bg_flip_every_scene": true/false, "one_connecting_object": "무엇", "text_height_ratio": "[추정] 0.xx", "accent_count": 1, "texture": "..."}},
 "score_ref": {{"clarity":0-10,"rhythm":0-10,"typography":0-10,"consistency":0-10,"note":"레퍼런스 자체 점수(비평 루프 기준점)"}}
}}
{('상품 힌트: ' + product_hint) if product_hint else ''}"""


def write_brief_claude(prompt, d, model="opus", timeout=900):
    """claude -p 헤드리스로 지시서를 받는다(구독 인증, API 과금 아님 — 메모리 reference_claude_max_on_server). 되돌려 주는 값 = (brief dict|None, 기록).
    실측(2026-10-20): ① 프롬프트를 인자로 주면 Windows shell 경유에서 줄바꿈에서 잘려 "프레임 경로 누락"으로 답했다 → stdin 으로 준다.
    ② cwd 가 저장소 안이면 프로젝트 CLAUDE.md·훅(대시보드 기록)이 딸려 와 승인 대기로 멈췄다 → 저장소 밖 임시 폴더 + --setting-sources user."""
    import shutil as _sh
    exe = _sh.which("claude")
    if not exe:
        return None, {"writer": "claude", "model": model, "error": "claude CLI 없음(PATH)"}
    cwd = Path(tempfile.gettempdir()) / "mograph_claude" / d.name
    cwd.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("CLAUDECODE", None)
    cmd = [exe, "-p", "--model", model, "--output-format", "json", "--permission-mode", "bypassPermissions", "--allowedTools", "Read",
           "--setting-sources", "user"]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=str(cwd), env=env)
    except subprocess.TimeoutExpired:
        return None, {"writer": "claude", "model": model, "error": "timeout %ss" % timeout}
    log = {"writer": "claude", "model": model, "rc": r.returncode, "elapsed_s": round(time.time() - t0, 1)}
    (d / "claude.log").write_text((r.stdout or "") + "\n--- stderr ---\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0:
        log["error"] = (r.stderr or r.stdout)[-400:]
        return None, log
    try:
        j = json.loads(r.stdout)
        log["model_used"] = list((j.get("modelUsage") or {}).keys())
        log["cost_usd"] = j.get("total_cost_usd")
        text = j.get("result") or ""
    except Exception as e:      # noqa: BLE001
        log["error"] = "json 파싱 실패: %r / 앞 200자: %s" % (e, (r.stdout or "")[:200])
        return None, log
    brief = parse_brief(text)
    if not brief:
        log["error"] = "지시서 JSON 을 못 읽음(claude.log 참고)"
    return brief, log


def parse_brief(text):
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:       # noqa: BLE001
        return None
    if not all(k in j for k in ("STORY", "LOOK", "MOTION")):
        return None
    for k in BRIEF_SECTIONS:
        j.setdefault(k, [])
    return j


def brief_markdown(meta, m, brief, log):
    t = meta.get("title") or {}
    out = ["# 역설계 지시서 — %s" % (t.get("en") or meta.get("id")), "",
           "- 레퍼런스: %s (%s · 조회 %s)" % (meta.get("original_post_url", ""), (meta.get("creator") or {}).get("handle", ""), meta.get("views", "")),
           "- 실측: %d×%d %.2f초 장면 %d개 컷/초 %s 바탕 전환 %d회" % (m["probe"]["w"], m["probe"]["h"], m["probe"]["duration"], m["scene_count"], m["cuts_per_s"], m["bg_flips"]),
           "- 쓴 이: %s %s %s" % (log.get("writer"), log.get("model") or "", ("(" + ",".join(log.get("model_used") or []) + ")") if log.get("model_used") else ""),
           "- 표시: **[실측]** = measure.json 숫자 · **[추정]** = 프레임을 보고 읽은 것", ""]
    for k in BRIEF_SECTIONS:
        out.append("## " + k)
        out += ["- " + str(x) for x in (brief.get(k) or [])] or ["- 없음"]
        out.append("")
    if brief.get("grammar"):
        out += ["## grammar", "```json", json.dumps(brief["grammar"], ensure_ascii=False, indent=1), "```", ""]
    if brief.get("score_ref"):
        out += ["## score_ref", "```json", json.dumps(brief["score_ref"], ensure_ascii=False), "```", ""]
    return "\n".join(out)


# ── ④ 장부 ──────────────────────────────────────────────────────────────────
def _write_refs(rows):
    ledger._write(ledger.REFS, rows)


def upsert_ref(rec):
    with ledger._LOCK:
        rows = ledger.load_refs()
        for i, r in enumerate(rows):
            if r.get("id") == rec["id"]:
                keep = {k: r[k] for k in ("status", "approved_at", "approved_by", "verdicts") if k in r}
                rows[i] = {**r, **rec, **keep}
                _write_refs(rows)
                return rows[i]
        rows.append(rec)
        _write_refs(rows)
        return rows[-1]


def find_ref(ref_id):
    for r in ledger.load_refs():
        if r.get("id") == ref_id:
            return r
    return None


def approve_ref(ref_id, approved=True, by="사장님", note=""):
    with ledger._LOCK:
        rows = ledger.load_refs()
        for r in rows:
            if r.get("id") == ref_id:
                r["status"] = "approved" if approved else "rejected"
                r["approved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                r["approved_by"] = by
                r.setdefault("verdicts", []).append({"at": r["approved_at"], "by": by, "verdict": "good" if approved else "bad", "note": (note or "")[:300]})
                _write_refs(rows)
                return r
    raise KeyError("없는 레퍼런스: %s" % ref_id)


# ── 주인 함수 ───────────────────────────────────────────────────────────────
def reverse_engineer(ref_id, writer="claude", model="opus", product_hint="", force=False):
    """레퍼런스 1건 역설계(동기). 되돌려 주는 값 = status dict(state done|error). writer: claude | none(실측·시트만)."""
    if not _ID.match(ref_id or ""):
        raise ValueError("레퍼런스 id 가 아닙니다")
    meta = sources.jasonzhu_meta(ref_id) or {"id": ref_id}
    mp4 = sources.jasonzhu_video(ref_id)
    if not mp4:
        raise FileNotFoundError("원본 mp4 없음: %s (MOGRAPH_JZ_DIR=%s)" % (ref_id, sources.jasonzhu_dir()))
    d = out_dir(ref_id)
    t0 = time.time()
    _put(ref_id, state="running", step="measure", started=time.strftime("%Y-%m-%d %H:%M:%S"))
    try:
        mp = d / "measure.json"
        if force or not mp.exists():
            m = measure(mp4, d)
        else:
            m = json.loads(mp.read_text(encoding="utf-8"))
        _put(ref_id, step="sheet", scene_count=m["scene_count"])
        ok, err = contact_sheet(mp4, d / "sheet.png", m["probe"]["duration"])
        if not ok:
            raise RuntimeError("시트 실패: " + err)
        scene_strip(d, m, d / "strip.png")
        brief, log = None, {"writer": writer}
        if writer == "claude":
            _put(ref_id, step="brief")
            brief, log = write_brief_claude(brief_prompt(meta, m, d, product_hint), d, model=model)
            if not brief:
                raise RuntimeError("지시서 실패: %s" % log.get("error"))
        if brief:
            (d / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8")
            (d / "brief.md").write_text(brief_markdown(meta, m, brief, log), encoding="utf-8")
        rec = {"id": ref_id, "source": "jasonzhu", "title": (meta.get("title") or {}).get("en") or "", "url": meta.get("original_post_url", ""),
               "creator": (meta.get("creator") or {}).get("handle", ""), "views": meta.get("views"), "models": meta.get("models") or [],
               "has_prompt": bool(sources.jasonzhu_prompt(ref_id)), "license": {"origin": "JasonZhu 라이브러리(제작자 %s)" % (meta.get("creator") or {}).get("handle", ""), "status": "ref_only",
                                                                                  "note": "영상 권리는 제작자 — 문법만 배운다, 영상·프레임 회원 노출 금지"},
               "measure": {k: m[k] for k in ("probe", "ratio", "scene_count", "scene_dur", "cuts_per_s", "bg_flips", "bg_sequence", "measured_at")},
               "brief": brief, "brief_log": log, "status": "draft", "reversed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "files": {"sheet": "sheet.png", "strip": "strip.png", "measure": "measure.json", "brief": "brief.md" if brief else ""}}
        upsert_ref(rec)
        return _put(ref_id, state="done", step="done", error="", elapsed_s=round(time.time() - t0, 1), writer=log.get("writer"), model_used=log.get("model_used"),
                    cost_usd=log.get("cost_usd"), has_brief=bool(brief))
    except Exception as e:      # noqa: BLE001 — 실패도 status 에(조용한 실패 금지)
        return _put(ref_id, state="error", error=str(e)[:600], elapsed_s=round(time.time() - t0, 1))


def reverse_async(ref_id, **kw):
    with _LOCK:
        th = _RUNNING.get(ref_id)
        if th and th.is_alive():
            return False
        th = threading.Thread(target=reverse_engineer, args=(ref_id,), kwargs=kw, daemon=True, name="mograph-reverse-" + ref_id)
        _RUNNING[ref_id] = th
        th.start()
        return True


def list_refs():
    """작업대 카드용: 받아진 JasonZhu 영상 전부(색인 메타 + 프롬프트 유무 + 장부 상태 + 역설계 상태)."""
    by_id = {r.get("id"): r for r in ledger.load_refs()}
    out = []
    for meta in sources.jasonzhu_index():
        rid = str(meta.get("id"))
        mp4 = sources.jasonzhu_video(rid)
        rec = by_id.get(rid) or {}
        out.append({"id": rid, "title": (meta.get("title") or {}).get("en") or "", "title_zh": (meta.get("title") or {}).get("zh") or "",
                    "creator": (meta.get("creator") or {}).get("handle", ""), "views": meta.get("views"), "models": meta.get("models") or [],
                    "duration_s": meta.get("duration_seconds"), "url": meta.get("original_post_url", ""), "has_video": bool(mp4),
                    "has_prompt": bool(sources.jasonzhu_prompt(rid)), "status": rec.get("status") or ("none"),
                    "has_brief": bool(rec.get("brief")), "measure": rec.get("measure"), "reverse": status(rid).get("state", "none"),
                    "verdicts": rec.get("verdicts") or []})
    return out


if __name__ == "__main__":      # py -m shopping_shorts.mograph.reverse <id> [--writer none|claude] [--model opus] [--force]
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ref_id")
    ap.add_argument("--writer", default="claude")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--hint", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    st = reverse_engineer(a.ref_id, writer=a.writer, model=a.model, product_hint=a.hint, force=a.force)
    print(json.dumps(st, ensure_ascii=False, indent=1))
