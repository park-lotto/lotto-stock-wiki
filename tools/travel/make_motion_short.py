"""여행 숏폼 모션 버전 — 콘티(shots.json)를 말에 맞춰 움직이는 영상으로(HyperFrames).

    py tools/travel/make_motion_short.py voice  <콘티폴더> <작업폴더>      # 미나 TTS + 단어 시각(일레븐 정렬, 추가비용 없음)
    py tools/travel/make_motion_short.py build  <콘티폴더> <작업폴더>      # index.html(HyperFrames) + 재료 복사
    npx -y hyperframes@0.8.105 render <작업폴더> -o <작업폴더>/raw.mp4     # 그림+목소리+효과음
    py tools/travel/make_motion_short.py mix    <작업폴더>                # 배경음 덕킹·-14 LUFS → final.mp4
    py tools/travel/make_motion_short.py check  <작업폴더>                # 결과물 검사(시트·멈춤·강조 상자 등장 시각)

레퍼런스(모션그래픽엔진/jasonzhu, 2026-10-20 조사)에서 옮긴 숫자 — 지어낸 값 없음:
  · 글자는 그 단어가 들리는 순간 등장(2110019799342260630) · 강조 단어 상자 = 그 단어 시작 시각(2107822293653041659)
  · 등장 = 아래에서·흐림 6px→0·오버슈트 3% 이내, 바운스 금지(2109454493415023080·2102…8152)
  · 컷마다 줌 1.0↔1.075 번갈아, 그 밖엔 1~2% 숨쉬기 줌(…3454) · 카드 순차 간격 125ms(…8498)
  · 강조색 1개 + 은은한 그레인(…3454) · 효과음 = 전환 whoosh·등장 pop, 음악보다 낮게 · 덕킹 9~12dB, -14 LUFS, TP -1.5(…3454)
대본·사진·손님 말 고르기는 콘티(make_storyboard)의 몫이고, 여기서는 시간과 움직임만 정한다.
"""
from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FPS = 30
GAP = 0.12            # 줄 사이 숨
ACCENT = "#FFE600"    # 자막팩 '예능 텐션' wordFx 색 = 강조색 1개
HF = "hyperframes@0.8.105"
SFX = ROOT / "shopping_shorts/assets/sfx_packs/팩21_사장님"
BGM = ROOT / "shopping_shorts/assets/bgm_lib/otsukare_summer.mp3"


def _shots(sb):
    return json.loads((Path(sb) / "shots.json").read_text(encoding="utf-8"))


def _mean_db(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    for ln in r.stderr.splitlines():
        if "mean_volume:" in ln:
            return float(ln.split("mean_volume:")[1].split()[0])
    return -99.0


def _gemini_tts(line, wav):
    """일레븐 키가 없는 PC용 대역 음성(제미나이 Kore). 본편은 미나 — voice.json 에 대역 표시를 남긴다."""
    import os
    import time
    import wave
    from google import genai
    from google.genai import types
    keys = [v for k, v in sorted(os.environ.items()) if k.startswith("GEMINI_API_KEY") and v]
    for a in range(6):
        try:
            c = genai.Client(api_key=keys[a % len(keys)].strip('"'))
            r = c.models.generate_content(
                model="gemini-2.5-flash-preview-tts", contents="친한 친구에게 숙소 꿀팁을 알려주듯 밝고 빠르게 말해: " + line,
                config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")))))
            data = r.candidates[0].content.parts[0].inline_data.data
            break
        except Exception as e:  # noqa: BLE001 — 키 돌려 재시도, 6번 다 실패하면 아래에서 멈춘다
            print("  재시도", str(e)[:80], flush=True)
            time.sleep(4)
    else:
        raise SystemExit("제미나이 TTS 6회 실패")
    w = wave.open(str(wav), "wb")
    w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000)
    w.writeframes(data)
    w.close()


def _align_words(line, heard):
    """받아쓴 단어 시각(heard) → 우리 원문 어절마다 시각. 글자 단위로 맞춘다(띄어쓰기·숫자 표기가 달라도).
    원문 글자가 받아쓴 글자와 하나도 안 맞는 어절은 앞뒤 시각 사이로 채우고 'guess' 표시."""
    import difflib
    hc, ht = [], []
    for w in heard:
        s = w["word"].replace(" ", "")
        for k, ch in enumerate(s):
            hc.append(ch)
            ht.append(w["start"] + (w["end"] - w["start"]) * k / max(1, len(s)))
    ours = line.split()
    oc, owner = [], []
    for wi, w in enumerate(ours):
        for ch in w:
            oc.append(ch)
            owner.append(wi)
    t_of = [None] * len(oc)
    for a, b, n in difflib.SequenceMatcher(None, oc, hc, autojunk=False).get_matching_blocks():
        for k in range(n):
            t_of[a + k] = ht[b + k]
    out = []
    for wi, w in enumerate(ours):
        ts_ = [t_of[k] for k in range(len(oc)) if owner[k] == wi and t_of[k] is not None]
        out.append({"word": w, "start": ts_[0] if ts_ else None, "guess": not ts_})
    known = [i for i, w in enumerate(out) if w["start"] is not None]
    for i, w in enumerate(out):
        if w["start"] is None:
            prev = max((k for k in known if k < i), default=None)
            nxt = min((k for k in known if k > i), default=None)
            a = out[prev]["start"] if prev is not None else 0.0
            b = out[nxt]["start"] if nxt is not None else a + 0.3
            w["start"] = (a + b) / 2
    return out


def stage_voice(sb, work, gem_tempo=1.12):
    """줄마다 음성 + 어절별 시작 시각. 키 있으면 미나(일레븐 정렬), 없으면 제미나이 대역 + GROQ 받아쓰기 정렬."""
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from shopping_shorts import config, tts, audio_post, asr_check, tts_timestamps as tt
    from shopping_shorts import video_assemble as va
    from tools.travel.make_travel_short import MINA
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    lines = [s["line"] for s in _shots(sb)]
    mina = bool(config.ELEVENLABS_API_KEY)
    out = []
    for i, line in enumerate(lines):
        mp3 = work / ("tts_%d.mp3" % i)
        if mp3.exists() and _mean_db(mp3) < -60:      # 키 없을 때 tts.py 가 만드는 무음 대역 파일 — 쓰지 않는다
            print("  %d줄 남은 음성이 무음(%.0fdB) — 다시 만든다" % (i + 1, _mean_db(mp3)), flush=True)
            mp3.unlink()
            Path(str(mp3) + ".fin").unlink(missing_ok=True)
        if not mp3.exists():
            if mina:
                tts.synthesize_tts(line, str(mp3), voice_id=MINA["voice_id"], voice_settings=MINA["voice_settings"],
                                   model_id=MINA["model_id"], speed=1.0,
                                   previous_text=lines[i - 1] if i else None,
                                   next_text=lines[i + 1] if i + 1 < len(lines) else None)
            else:
                wav = work / ("tts_%d.wav" % i)
                _gemini_tts(line, wav)
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-ar", "44100", "-b:a", "192k", str(mp3)], check=True)
        # 마무리(빠르기·무음 정리)는 한 번만 — 서버에서 미나로 합성해 받아 온 mp3(일레븐 키 없는 PC)도 여기서 마무리한다
        fin = Path(str(mp3) + ".fin")
        side = Path(tt.sidecar_path(str(mp3))).exists()
        if not fin.exists():
            audio_post.finish_line_audio(str(mp3), tempo=MINA["tempo"] if (mina or side) else gem_tempo, silence_trim="mid")
            fin.write_text("finished", encoding="utf-8")
        eleven = mina or side
        dur = float(va._probe_duration(str(mp3)))
        if eleven:
            words = tt.words_from_mp3(str(mp3))
            if not words:
                raise SystemExit("%d줄 단어 시각이 없다(일레븐 정렬 사이드카 없음) — 글자 수 추정으로 때우지 않는다" % (i + 1))
            words = tt.rescale(words, dur, removed=tt.load_removed(str(mp3)))
        else:
            heard = asr_check.transcribe_words(str(mp3))
            if not heard:
                raise SystemExit("%d줄 받아쓰기 실패: %s" % (i + 1, asr_check._LAST.error))
            words = _align_words(line, heard)
        out.append({"line": line, "mp3": mp3.name, "dur": round(dur, 3), "words": words,
                    "voice": ("미나(일레븐)" if mina else "미나(일레븐, 서버 합성)") if eleven else "제미나이 Kore(대역 — 이 PC에 일레븐 키 없음)"})
        print("%d줄 %.2f초 어절 %d개 추정 %d" % (i + 1, dur, len(words), sum(1 for w in words if w.get("guess"))), flush=True)
    (work / "voice.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 시간표: 줄마다 시작·끝, 사진→손님 장면 넘김 시각, 자막 덩어리, 단어 시각. 화면은 전부 이 표만 읽는다 ──
SPLIT_AT = 0.45       # 줄 길이의 이 지점에 가장 가까운 자막 덩어리 경계에서 공식 사진 → 손님 장면
CAP_CHARS = 14        # 자막 한 덩어리 글자 수(콘티 make_storyboard 와 같은 값)


def plan_timeline(shots, voice):
    from shopping_shorts.video_assemble import simple_caption_split
    out, t = [], 0.0
    for s, v in zip(shots, voice):
        words = v["words"]
        chunks, k = [], 0
        for c in simple_caption_split(s["line"], CAP_CHARS):
            n = len(c.split())
            chunks.append(list(range(k, k + n)))
            k += n
        if k != len(words):
            raise SystemExit("%d줄 자막 덩어리 어절 수(%d)와 음성 어절 수(%d)가 다르다" % (s["n"], k, len(words)))
        dur = v["dur"]
        bounds = [words[c[0]]["start"] for c in chunks[1:]]
        split = min(bounds, key=lambda b: abs(b - dur * SPLIT_AT)) if bounds else dur * SPLIT_AT
        end = t + dur + GAP
        caps = []
        for ci, c in enumerate(chunks):
            c0 = 0.0 if ci == 0 else words[c[0]]["start"]
            c1 = words[chunks[ci + 1][0]]["start"] if ci + 1 < len(chunks) else dur + GAP
            caps.append({"t0": t + c0, "t1": t + c1, "words": [(words[w]["word"], t + max(c0, words[w]["start"])) for w in c]})
        out.append({"n": s["n"], "t": t, "dur": dur, "end": end, "split": t + split, "caps": caps,
                    "emph": (s.get("plan") or {}).get("emph", "")})
        t = end
    return out


_GRAIN = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>"
          "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' seed='7'/>"
          "<feColorMatrix values='0 0 0 0 .5 0 0 0 0 .5 0 0 0 0 .5 0 0 0 .55 0'/></filter>"
          "<rect width='300' height='300' filter='url(%23n)'/></svg>")

# 카드 자리(사진 수별) — x, y, 폭, 높이, 기울기. 카드 영역 y 330~1090(아래는 손님 말·자막 자리)
_CARDS = {1: [(190, 360, 700, 700, -2)],
          2: [(70, 380, 520, 600, -4), (490, 470, 520, 600, 4)],
          3: [(50, 350, 480, 500, -5), (550, 340, 480, 500, 4), (280, 600, 520, 440, -2)],
          4: [(60, 350, 460, 400, -4), (560, 340, 460, 400, 3), (70, 700, 460, 380, 3), (560, 690, 460, 380, -3)]}


def _img(src, dst, w=1080):
    from PIL import Image
    im = Image.open(src).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)))
    im.save(dst, quality=88)
    return dst.name


def stage_build(sb, work):
    from shopping_shorts import video_assemble as va
    sb, work = Path(sb), Path(work)
    shots = _shots(sb)
    voice = json.loads((work / "voice.json").read_text(encoding="utf-8"))
    tl = plan_timeline(shots, voice)
    a = work / "assets"
    a.mkdir(exist_ok=True)
    fonts = ROOT / "shopping_shorts/static/fonts"
    for f in ("SBAggroB.ttf", "Gaegu-Bold.ttf", "Pretendard-ExtraBold.otf"):
        shutil.copy(fonts / f, a / f)
    shutil.copy(Path.home() / "숏템자료/모션그래픽엔진/work/2026-10-20_라면레시피/ramen/brand/gsap.min.js", a / "gsap.min.js")
    for f in ("whoosh.wav", "pop.wav"):
        shutil.copy(SFX / f, a / f)
    for v in voice:
        shutil.copy(work / v["mp3"], a / v["mp3"])
    disc = va.disclosure_layer_png({"disclosure": {"ad": True, "ai": True, "source": "여기어때"}}, str(a / "disclosure.png"))
    guide = sorted(sb.parent.glob("sl_*.png"))[:3]
    e = html.escape
    body, js = [], []
    sfx = []                                   # (시각, 파일, 볼륨) — 정점 보정: whoosh 0.02s, pop 0.068s 앞당김
    for i, (s, L) in enumerate(zip(shots, tl)):
        p = s.get("plan") or {}
        off = _img(s["official"]["path"], a / ("off_%d.jpg" % i))
        aid, bid = "a%d" % i, "b%d" % i
        # ① 공식 사진 — 숨쉬기 줌(1.00→1.045), 홀수 줄은 1.075 에서 들어와 펀치 느낌
        body.append('<div id="%s" class="clip shot" data-start="%.3f" data-duration="%.3f" data-track-index="1">'
                    '<div class="cam"><img src="assets/%s"></div></div>' % (aid, L["t"], L["split"] - L["t"], off))
        z0 = 1.075 if i % 2 else 1.0
        js.append('tl.fromTo("#%s .cam",{scale:%.3f},{scale:%.3f,duration:%.3f,ease:"sine.inOut"},%.3f);'
                  % (aid, z0, z0 + 0.045 if z0 == 1.0 else 1.0, L["split"] - L["t"], L["t"]))
        if i:
            sfx.append((L["t"] - 0.02, "whoosh.wav", 0.22))
        # ② 손님 장면
        guests = [] if s.get("fallback") else (s.get("guests") or [])[:4]
        if p.get("kind") == "guidebook":
            guests = [str(g) for g in guide]
        cards = []
        for j, g in enumerate(guests):
            x, y, w, h, r = _CARDS[len(guests)][j]
            cards.append('<div class="card%s" id="%s_c%d" style="left:%dpx;top:%dpx;width:%dpx;height:%dpx;--r:%ddeg">'
                         '<img src="assets/%s"></div>' % (" doc" if p.get("kind") == "guidebook" else "", bid, j, x, y, w, h, r, _img(g, a / ("g_%d_%d.jpg" % (i, j)), 900)))
        v = s.get("variety") or {}
        punch, react = (v.get("punch") or "").strip(), (v.get("react") or "").strip()
        bubble = ('<div class="bub" id="%s_q"><span class="q">“%s”</span>%s<small>실제 투숙객 후기</small></div>'
                  % (bid, e(punch), ('<b class="tag">%s</b>' % e(react)) if react else "")) if punch else ""
        title = ('<div class="ttl" id="%s_t"><i></i><span>%s</span></div>' % (bid, e(p.get("title", "")))) if p.get("title") else ""
        bg = "bgsharp" if not guests else "bgblur"
        body.append('<div id="%s" class="clip scene" data-start="%.3f" data-duration="%.3f" data-track-index="2">'
                    '<div class="cam %s"><img src="assets/%s"></div><div class="dim"></div>%s%s%s'
                    '<div class="src">%s</div></div>'
                    % (bid, L["split"], L["end"] + (0.4 if i == len(shots) - 1 else 0.0) - L["split"], bg, off, title, "".join(cards), bubble,
                       e("실제 투숙객 사진 · 출처: 여기어때") if guests and p.get("kind") != "guidebook" else ""))
        b0 = L["split"]
        b1 = L["end"] + (0.4 if i == len(shots) - 1 else 0.0)        # 장면 끝(마지막 줄은 꼬리 0.4초까지)
        # 펀치 1.075→1.03(0.5초) 뒤에도 멈추지 않게 1.03→1.0 숨쉬기 줌(레퍼런스: 0.3초 넘게 멈춘 구간 없음)
        js.append('tl.fromTo("#%s .cam",{scale:1.075},{scale:1.03,duration:0.5,ease:"power2.out"},%.3f);' % (bid, b0))
        js.append('tl.fromTo("#%s .cam",{scale:1.03},{scale:1.0,duration:%.3f,ease:"none"},%.3f);' % (bid, max(0.1, b1 - b0 - 0.5), b0 + 0.5))
        sfx.append((b0 - 0.02, "whoosh.wav", 0.22))
        if title:
            js.append('tl.fromTo("#%s_t i",{scaleX:0},{scaleX:1,duration:0.32,ease:"power2.out"},%.3f);' % (bid, b0 + 0.05))
            js.append('tl.fromTo("#%s_t span",{opacity:0,y:20},{opacity:1,y:0,duration:0.28,ease:"power2.out"},%.3f);' % (bid, b0 + 0.08))
        for j in range(len(cards)):         # 순차 125ms, 아래에서·흐림 6px→0, 바운스 없음
            js.append('tl.fromTo("#%s_c%d",{opacity:0,y:80,scale:0.9,filter:"blur(6px)"},'
                      '{opacity:1,y:0,scale:1,filter:"blur(0px)",duration:0.42,ease:"power3.out"},%.3f);' % (bid, j, b0 + 0.12 + j * 0.125))
        for j in range(len(cards)):         # 등장 뒤 천천히 떠오름(카드마다 방향 번갈아)
            t_in = b0 + 0.12 + j * 0.125 + 0.42
            js.append('tl.fromTo("#%s_c%d",{y:0},{y:%d,duration:%.3f,ease:"sine.inOut"},%.3f);' % (bid, j, -16 if j % 2 else -10, max(0.1, b1 - t_in), t_in))
        if bubble:
            tq = b0 + 0.12 + len(cards) * 0.125 + 0.25
            js.append('tl.fromTo("#%s_q",{opacity:0,y:30,scale:0.94},{opacity:1,y:0,scale:1,duration:0.3,ease:"back.out(1.15)"},%.3f);' % (bid, tq))
            if react:
                js.append('tl.fromTo("#%s_q .tag",{opacity:0,scale:0.6},{opacity:1,scale:1,duration:0.22,ease:"back.out(1.2)"},%.3f);' % (bid, tq + 0.35))
            sfx.append((tq - 0.068, "pop.wav", 0.3))
            js.append('tl.fromTo("#%s_q",{y:0},{y:-8,duration:%.3f,ease:"sine.inOut"},%.3f);' % (bid, max(0.1, b1 - tq - 0.3), tq + 0.3))
        # ③ 말 자막 — 덩어리마다 한 칸, 단어는 그 단어가 들리는 순간 등장, 강조 단어는 노란 상자
        for ci, c in enumerate(L["caps"]):
            cid = "c%d_%d" % (i, ci)
            spans = []
            for wi, (w, wt) in enumerate(c["words"]):
                em = L["emph"]
                if em and em in w:
                    k = w.find(em)
                    inner = '%s<span class="em"><i></i><span>%s</span></span>%s' % (e(w[:k]), e(em), e(w[k + len(em):]))
                    js.append('tl.fromTo("#%s_w%d .em i",{scaleX:0},{scaleX:1,duration:0.18,ease:"power2.out"},%.3f);' % (cid, wi, wt))
                    js.append('tl.set("#%s_w%d .em span",{color:"#111",webkitTextStroke:"0px #000"},%.3f);' % (cid, wi, wt))
                    js.append('tl.fromTo("#%s_w%d .em",{scale:1},{scale:1.08,duration:0.12,yoyo:true,repeat:1,ease:"power1.out"},%.3f);' % (cid, wi, wt))
                else:
                    inner = e(w)
                spans.append('<span class="w" id="%s_w%d">%s</span>' % (cid, wi, inner))
                js.append('tl.fromTo("#%s_w%d",{opacity:0,y:26,filter:"blur(6px)"},{opacity:1,y:0,filter:"blur(0px)",duration:0.16,ease:"power2.out"},%.3f);' % (cid, wi, wt))
            body.append('<div id="%s" class="clip cap" data-start="%.3f" data-duration="%.3f" data-track-index="5"><div class="ln">%s</div></div>'
                        % (cid, c["t0"], c["t1"] - c["t0"], " ".join(spans)))
    total = tl[-1]["end"] + 0.4
    auds = ['<audio id="v%d" src="assets/%s" data-start="%.3f" data-duration="%.3f" data-track-index="10" data-volume="1"></audio>'
            % (i, v["mp3"], L["t"], v["dur"], ) for i, (v, L) in enumerate(zip(voice, tl))]
    auds += ['<audio id="s%d" src="assets/%s" data-start="%.3f" data-duration="%.2f" data-track-index="%d" data-volume="%.2f"></audio>'
             % (k, f, max(0.0, t0), 0.5 if f.startswith("whoosh") else 0.3, 11 + k % 2, vol) for k, (t0, f, vol) in enumerate(sfx)]
    doc = _PAGE % {"dur": "%.3f" % total, "body": "\n".join(body), "auds": "\n".join(auds), "grain": _GRAIN,
                   "disc": '<img class="disc" src="assets/disclosure.png">' if disc else "", "js": "\n".join(js),
                   "acc": ACCENT}
    (work / "index.html").write_text(doc, encoding="utf-8")
    (work / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    print("만듦", work / "index.html", "길이 %.2f초, 효과음 %d개" % (total, len(sfx)))


_PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080, height=1920">
<script src="assets/gsap.min.js"></script>
<style>
@font-face{font-family:"Aggro";src:url("assets/SBAggroB.ttf")}
@font-face{font-family:"Gaegu";src:url("assets/Gaegu-Bold.ttf")}
@font-face{font-family:"PretendardX";src:url("assets/Pretendard-ExtraBold.otf")}
html,body{margin:0;background:#000}
#root{position:relative;width:100%%;height:100%%;overflow:hidden;background:#000}
.clip{position:absolute;inset:0;overflow:hidden}
.cam{position:absolute;inset:0}
.cam img{width:100%%;height:100%%;object-fit:cover;display:block}
.bgblur img{filter:blur(26px) brightness(.62) saturate(1.1)}
.bgsharp img{filter:brightness(.9)}
.dim{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.25),rgba(0,0,0,0) 30%%,rgba(0,0,0,0) 55%%,rgba(0,0,0,.55))}
.card{position:absolute;background:#fff;padding:14px 14px 48px;box-sizing:border-box;border-radius:6px;box-shadow:0 18px 40px rgba(0,0,0,.45);rotate:var(--r)}
.card img{width:100%%;height:100%%;object-fit:cover;display:block;border-radius:2px}
.card.doc{padding:10px}.card.doc img{object-fit:contain;background:#fff}
.ttl{position:absolute;left:0;right:0;top:170px;text-align:center}
.ttl span{position:relative;font-family:"Gaegu";font-size:96px;color:#fff;text-shadow:0 4px 14px rgba(0,0,0,.6);display:inline-block}
.ttl i{position:absolute;left:50%%;width:560px;margin-left:-280px;top:96px;height:30px;background:%(acc)s;opacity:.92;border-radius:14px;transform-origin:left center;display:block}
.bub{position:absolute;left:70px;right:70px;top:1110px;background:#fff;border-radius:30px;padding:26px 34px 22px;box-shadow:0 14px 34px rgba(0,0,0,.4)}
.bub .q{display:block;font-family:"PretendardX";font-size:50px;line-height:1.25;color:#1d1b18;letter-spacing:-.02em}
.bub small{display:block;margin-top:8px;font-family:"PretendardX";font-size:26px;color:#8a837a}
.bub .tag{position:absolute;right:26px;top:-34px;background:%(acc)s;color:#111;font-family:"PretendardX";font-size:34px;padding:6px 18px;border-radius:999px;rotate:-4deg;display:block}
.src{position:absolute;left:0;right:0;bottom:46px;text-align:center;font-family:"PretendardX";font-size:24px;color:rgba(255,255,255,.75)}
.cap{pointer-events:none}
.cap .ln{position:absolute;left:50px;right:50px;top:1420px;text-align:center;font-family:"Aggro";font-size:90px;line-height:1.22;color:#fff;
 -webkit-text-stroke:.07em #000;paint-order:stroke fill;text-shadow:0 .05em .1em rgba(0,0,0,.7);word-break:keep-all}
.w{display:inline-block}
.em{position:relative;display:inline-block}
.em i{position:absolute;left:-8px;right:-3px;top:4px;bottom:-2px;background:%(acc)s;border-radius:12px;z-index:-1;transform-origin:left center;display:block}
.em span{position:relative}
.grain{position:absolute;inset:0;background-image:url("%(grain)s");opacity:.07;mix-blend-mode:overlay;pointer-events:none}
.disc{position:absolute;left:0;top:0;width:1080px;height:1920px;pointer-events:none}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="%(dur)s" data-fps="30">
%(body)s
<div class="grain"></div>
%(disc)s
%(auds)s
</div>
<script>
const tl = gsap.timeline({ paused: true });
%(js)s
window.__timelines["main"] = tl;
</script>
</body></html>
"""


def stage_veo(sb, work, sec=4):
    """공식 사진 → 세로 시작 화면(travel_build.start_frame) → Veo(ai_scene.generate, 여행 프롬프트 build_travel_prompt). 7컷 동시."""
    from concurrent.futures import ThreadPoolExecutor
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from shopping_shorts import ai_scene, travel_build as tb
    work = Path(work)
    shots = _shots(sb)

    def one(i):
        s = shots[i]
        out = work / ("clip_%d.mp4" % i)
        if out.exists():
            return i, "있음"
        fp, mode = tb.start_frame(s["official"]["path"], work / ("start_%d.png" % i))
        prompt = ai_scene.build_travel_prompt(s["official"]["kind"], s["official"]["desc_en"], sec)
        (work / ("prompt_%d.txt" % i)).write_text(prompt, encoding="utf-8")
        t0 = __import__("time").time()
        ai_scene.generate(fp, prompt, sec, str(out))
        return i, "%.0f초(%s)" % (__import__("time").time() - t0, mode)
    with ThreadPoolExecutor(7) as ex:
        for i, msg in ex.map(one, range(len(shots))):
            print("클립 %d %s" % (i + 1, msg), flush=True)


# ── 2판(사장님 2026-10-20 "집중이 안 되고 정보를 받는 느낌이 없다 / 자막 너무 짧게 끊지 말고") ──
# 한 문장 = 한 컷(Veo 영상) · 자막은 반 문장씩 통째로 · 주장마다 근거 카드(후기 N건, 숫자 올라감)
def _halves(line):
    """자막 덩어리 — 짧으면 한 덩어리, 길면 자연 경계에서 두 덩어리(한 화면 1~2초에 휙 지나가지 않게)."""
    from shopping_shorts.video_assemble import simple_caption_split
    n = len(line.replace(" ", ""))
    if n <= 13:
        return [line.split()]
    parts = simple_caption_split(line, (n + 1) // 2 + 3)
    while len(parts) > 2:                      # 셋 이상이면 짧은 쪽끼리 붙인다
        k = min(range(len(parts) - 1), key=lambda j: len(parts[j]) + len(parts[j + 1]))
        parts[k:k + 2] = [parts[k] + " " + parts[k + 1]]
    return [p.split() for p in parts]


def stage_build2(sb, work):
    from shopping_shorts import video_assemble as va
    sb, work = Path(sb), Path(work)
    shots = _shots(sb)
    voice = json.loads((work / "voice.json").read_text(encoding="utf-8"))
    a = work / "assets"
    a.mkdir(exist_ok=True)
    fonts = ROOT / "shopping_shorts/static/fonts"
    for f in ("SBAggroB.ttf", "Pretendard-ExtraBold.otf"):
        shutil.copy(fonts / f, a / f)
    shutil.copy(Path.home() / "숏템자료/모션그래픽엔진/work/2026-10-20_라면레시피/ramen/brand/gsap.min.js", a / "gsap.min.js")
    for f in ("whoosh.wav", "pop.wav"):
        shutil.copy(SFX / f, a / f)
    disc = va.disclosure_layer_png({"disclosure": {"ad": True, "ai": True, "source": "여기어때"}}, str(a / "disclosure.png"))
    e = html.escape
    body, js, sfx, tl, auds = [], [], [], [], []
    t = 0.0
    for i, (s, v) in enumerate(zip(shots, voice)):
        words, dur = v["words"], v["dur"]
        end = t + dur + GAP + (0.5 if i == len(shots) - 1 else 0.0)
        shutil.copy(work / ("clip_%d.mp4" % i), a / ("clip_%d.mp4" % i))
        shutil.copy(work / v["mp3"], a / v["mp3"])
        body.append('<video id="vid%d" class="clip vid" src="assets/clip_%d.mp4" data-start="%.3f" data-duration="%.3f" '
                    'data-track-index="1" muted playsinline></video>' % (i, i, t, end - t))
        if i:
            sfx.append((t - 0.02, "whoosh.wav", 0.2))
        auds.append('<audio id="v%d" src="assets/%s" data-start="%.3f" data-duration="%.3f" data-track-index="10" data-volume="1"></audio>'
                    % (i, v["mp3"], t, dur))
        # 자막(반 문장씩 통째로)
        groups, k = _halves(s["line"]), 0
        caps, em = [], s["plan"]["emph"]
        em_t = None
        for gi, g in enumerate(groups):
            idx = list(range(k, k + len(g)))
            k += len(g)
            c0 = t if gi == 0 else t + words[idx[0]]["start"]
            c1 = (t + words[k]["start"]) if gi + 1 < len(groups) else end
            cid = "c%d_%d" % (i, gi)
            spans = []
            for wi in idx:
                w = words[wi]["word"]
                if em and em in w and em_t is None:
                    em_t = t + words[wi]["start"]
                    p = w.find(em)
                    spans.append('%s<span class="em"><i></i><span>%s</span></span>%s' % (e(w[:p]), e(em), e(w[p + len(em):])))
                    js.append('tl.fromTo("#%s .em i",{scaleX:0},{scaleX:1,duration:0.2,ease:"power2.out"},%.3f);' % (cid, em_t))
                    js.append('tl.set("#%s .em span",{color:"#111",webkitTextStroke:"0px #000"},%.3f);' % (cid, em_t))
                else:
                    spans.append(e(w))
            body.append('<div id="%s" class="clip cap" data-start="%.3f" data-duration="%.3f" data-track-index="5"><div class="ln">%s</div></div>'
                        % (cid, c0, c1 - c0, " ".join(spans)))
            js.append('tl.fromTo("#%s .ln",{opacity:0,y:22},{opacity:1,y:0,duration:0.18,ease:"power2.out"},%.3f);' % (cid, c0))
            caps.append({"t0": c0, "t1": c1, "words": [(words[w]["word"], t + words[w]["start"]) for w in idx]})
        # 근거 카드 — 강조 단어가 들리는 순간, 숫자가 0에서 올라간다(레퍼런스 count-up)
        ev = s.get("evidence")
        if ev:
            eid = "ev%d" % i
            t_ev = t + 0.2      # 컷 시작 0.2초 뒤 등장 → 컷 끝까지(사장님 10-20 "너무 늦게 나오고 빨리 사라진다": 강조 단어 시각에 띄우면 0.8~2.9초뿐이었다)
            thumb = ""
            if ev.get("photo"):
                thumb = '<img class="th" src="assets/%s">' % _img(ev["photo"], a / ("ev_%d.jpg" % i), 480)
            body.append('<div id="%s" class="clip evc" data-start="%.3f" data-duration="%.3f" data-track-index="4">'
                        '<div class="box">%s<div class="tx"><b class="pill">후기 <span class="num">0</span>건</b>'
                        '<span class="it">%s</span></div></div></div>' % (eid, t_ev, end - t_ev, thumb, e(ev["item"])))
            js.append('tl.fromTo("#%s .box",{opacity:0,y:40,scale:0.95,filter:"blur(6px)"},{opacity:1,y:0,scale:1,filter:"blur(0px)",duration:0.32,ease:"power3.out"},%.3f);' % (eid, t_ev))
            js.append('(function(){var o={v:0},el=document.querySelector("#%s .num");tl.to(o,{v:%d,duration:0.6,ease:"power2.out",'
                      'onUpdate:function(){el.textContent=Math.round(o.v).toLocaleString("ko-KR")}},%.3f);})();' % (eid, ev["count"], t_ev + 0.05))
            sfx.append((t_ev - 0.068, "pop.wav", 0.28))
        tl.append({"n": s["n"], "t": t, "dur": dur, "end": end, "split": t, "caps": caps, "emph": em})
        t = end
    auds += ['<audio id="s%d" src="assets/%s" data-start="%.3f" data-duration="%.2f" data-track-index="%d" data-volume="%.2f"></audio>'
             % (k, f, max(0.0, t0), 0.5 if f.startswith("whoosh") else 0.3, 11 + k % 2, vol) for k, (t0, f, vol) in enumerate(sfx)]
    doc = _PAGE2 % {"dur": "%.3f" % t, "body": "\n".join(body), "auds": "\n".join(auds), "grain": _GRAIN,
                    "disc": '<img class="disc" src="assets/disclosure.png">' if disc else "", "js": "\n".join(js), "acc": ACCENT}
    (work / "index.html").write_text(doc, encoding="utf-8")
    (work / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    print("만듦", work / "index.html", "길이 %.2f초, 컷 %d, 효과음 %d개" % (t, len(shots), len(sfx)))


_PAGE2 = """<!doctype html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080, height=1920">
<script src="assets/gsap.min.js"></script>
<style>
@font-face{font-family:"Aggro";src:url("assets/SBAggroB.ttf")}
@font-face{font-family:"PretendardX";src:url("assets/Pretendard-ExtraBold.otf")}
html,body{margin:0;background:#000}
#root{position:relative;width:100%%;height:100%%;overflow:hidden;background:#000}
.clip{position:absolute;inset:0}
.vid{width:100%%;height:100%%;object-fit:cover;z-index:0}
.cap,.evc{z-index:3}
.shade{z-index:1;position:absolute;left:0;right:0;bottom:0;height:900px;background:linear-gradient(180deg,rgba(0,0,0,0),rgba(0,0,0,.55));pointer-events:none}
.cap .ln{position:absolute;left:60px;right:60px;top:1420px;text-align:center;font-family:"Aggro";font-size:84px;line-height:1.25;color:#fff;
 -webkit-text-stroke:.07em #000;paint-order:stroke fill;text-shadow:0 .05em .1em rgba(0,0,0,.7);word-break:keep-all}
.em{position:relative;display:inline-block}
.em i{position:absolute;left:-8px;right:-3px;top:4px;bottom:-2px;background:%(acc)s;border-radius:12px;z-index:-1;transform-origin:left center;display:block}
.em span{position:relative}
.evc .box{position:absolute;left:70px;right:70px;top:1110px;height:230px;box-sizing:border-box;display:flex;align-items:center;gap:26px;
 padding:22px 28px;border-radius:30px;background:rgba(14,14,14,.72);box-shadow:0 14px 34px rgba(0,0,0,.35)}
.evc .th{width:186px;height:186px;object-fit:cover;border-radius:20px;flex:none;border:4px solid #fff}
.evc .tx{display:flex;flex-direction:column;gap:12px;min-width:0}
.evc .pill{align-self:flex-start;background:%(acc)s;color:#111;font-family:"PretendardX";font-size:44px;padding:6px 20px;border-radius:999px}
.evc .it{font-family:"PretendardX";font-size:40px;line-height:1.25;color:#fff;letter-spacing:-.02em;word-break:keep-all}
.grain{position:absolute;inset:0;z-index:2;background-image:url("%(grain)s");opacity:.06;mix-blend-mode:overlay;pointer-events:none}
.disc{position:absolute;left:0;top:0;width:1080px;height:1920px;pointer-events:none;z-index:4}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="%(dur)s" data-fps="30">
%(body)s
<div class="shade"></div>
<div class="grain"></div>
%(disc)s
%(auds)s
</div>
<script>
const tl = gsap.timeline({ paused: true });
%(js)s
window.__timelines["main"] = tl;
</script>
</body></html>
"""


# ── 3판: 보내주신 레퍼런스(2110019799342260630, 2초 간격 40장 실측)의 화면 문법을 그대로 ──
#   크림 바탕 · 위 = 말하는 문장(굵은 검정 + 핵심 단어만 기울인 명조 주황, 말하는 순간 등장)
#   가운데 = 둥근 카드 안 영상(컷마다 휙 밀려 들어옴, 첫 컷은 당겼다 빠지는 줌) · 카드 모서리 '후기 N건' 도장 쾅
#   아래 = 칩(취소선 → 화살표 → 새 칩), 끝 = 막대가 자라는 정리 화면(후기 분석 숫자)
ORANGE = "#E8542A"
CREAM = "#F6F1EA"
# 줄별 그림 요소 — 칩 글자는 후기 분석 항목·숙소 주소에 있는 말만(지어낸 사실 금지)
_V3 = {1: {"chips": ["인천 영종구 운서동"]},
       2: {"chips": ["누운 채로 보는 일출"]},
       3: {"chips": ["해물짬뽕은 필수"]},
       4: {"chips": ["사우나 · 노천탕 무료"]},
       5: {"strike": "3시 체크인", "to": "2시 전 번호표"},
       6: {"chips": ["호텔 바로 앞 산책로"]},
       7: {"chart": ["한겨울에도 따뜻한 야외 인피니티 온수풀", "룸서비스 해물짬뽕은 필수, 치킨도 같이",
                     "침대에 누운 채로 보는 바다와 일출", "호텔 바로 앞 갈대밭 바닷가 산책로"],
           "labels": ["온수풀", "해물짬뽕", "누워서 일출", "갈대밭 산책"]}}


# 카드 아래 '실제 후기 댓글 + 손님 사진' (사장님 10-20 "영상 아래쪽에 댓글이랑 사진들 있음 보여주면 좋을듯")
# 사진 고르기 = travel_scene.scene_photos(그 장면이 실제로 보이는 손님 사진), 문구 = photo_quotes(원문 글자 그대로 검사)
_COMMENT_KEYS = {1: (["온수풀", "인피니티"], "야외 인피니티 온수풀"),
                 2: (["일출", "해돋이"], "객실 창밖 바다나 일출"),
                 3: (["짬뽕"], "룸서비스 해물짬뽕 그릇"),
                 4: (["노천탕", "사우나"], "사우나 또는 노천탕"),
                 5: (["번호표"], "체크인 번호표나 로비 대기", ["대기", "기다", "웨이팅", "줄이"], ["없었", "없어서", "바로 체크인"]),
                 6: (["갈대"], "호텔 앞 갈대밭 산책로")}


def stage_comments(sb, work, reviews_path, want=2):
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from shopping_shorts import travel_scene as ts
    work = Path(work)
    reviews = json.loads(Path(reviews_path).read_text(encoding="utf-8"))
    out_f = work / "comments.json"
    out = json.loads(out_f.read_text(encoding="utf-8")) if out_f.exists() else {}
    for s in _shots(sb):
        n = str(s["n"])
        cm = s.get("comment")      # 콘티에 적힌 것이 우선(숙소마다 다르다) — 없으면 네스트호텔 표
        if n in out or not (cm or s["n"] in _COMMENT_KEYS):
            continue
        keys, topic, must, avoid = ((cm["keys"], cm["topic"], cm.get("must"), cm.get("avoid")) if cm
                                    else (list(_COMMENT_KEYS[s["n"]]) + [None, None])[:4])
        # 대본과 반대되는 후기(예: 대본 '대기 1시간' ↔ 후기 '웨이팅 없었어요')는 아예 후보에서 뺀다 — 실측 10-20 5줄
        pool_ = [r for r in reviews if (not must or any(m in r.get("content", "") for m in must))
                 and not any(x in r.get("content", "") for x in (avoid or []))]
        sel = ts.scene_photos(pool_, keys, topic, work / ("cm_%s" % n), want=want)
        if not sel:       # 손님이 찍지 않는 순간(번호표 등) — 사진 없이 후기 댓글만(핵심어 겹침·공감 순)
            rv = sorted((r for r in pool_ if any(k in r.get("content", "") for k in keys)),
                        key=lambda r: (-sum(k in r.get("content", "") for k in keys), -int(r.get("likes") or 0)))[:want]
            sel = [{"path": None, "review": r} for r in rv]
        qs = ts.photo_quotes([x["review"] for x in sel], keys, topic)
        out[n] = [{"photo": x.get("path"), "quote": q, "rating": x["review"].get("rating")} for x, q in zip(sel, qs) if q]
        out_f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("%s줄 사진 %d · 댓글 %s" % (n, sum(1 for x in out[n] if x["photo"]), [x["quote"] for x in out[n]]), flush=True)


def _fit_clip(src, dst, need):
    """Veo 4초 클립이 그 줄보다 짧으면 그 줄 길이에 맞춰 느리게(멈춤 방지). 길면 그대로(줄 끝에서 잘린다)."""
    have = _dur(src)
    if need <= have - 0.05:
        shutil.copy(src, dst)
        return
    k = need / have + 0.03
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", "setpts=%.4f*PTS" % k, "-an", "-c:v", "libx264",
                    "-crf", "16", "-pix_fmt", "yuv420p", str(dst)], check=True)


def _photo_card(i, frames, cms, a, t, end, small, body, js, sfx):
    """한 줄의 가운데 카드를 사진 여러 장으로 — 줄 길이를 장 수로 나눠 1~2초마다 바꾼다(터진 숙소 쇼츠 8/9편이 컷 1.6초 이하).
    장마다 천천히 당기거나 빠지는 줌(1.0↔1.075 번갈아). 칸 종류:
      {"photo": 경로}                         공식 사진 한 장
      {"photo": 경로, "fade_to": 경로}         같은 곳이 0.8초에 걸쳐 바뀜(낮→노을 등)
      {"compare": [공식 경로, "g0"]}           위 '호텔 사진' / 아래 '실제 손님 사진' 나란히
    "g0"·"g1" = 그 줄 손님 후기 사진(comments.json). 없으면 그 칸을 빼고 알린다(조용히 넘기지 않는다).
    반환 (첫 장 선택자, 마지막 장 선택자) — 줄 사이 휙 전환은 부르는 쪽이 건다."""
    def src(x):
        if x and x.startswith("g") and x[1:].isdigit():
            k = int(x[1:])
            return cms[k]["photo"] if k < len(cms) and cms[k].get("photo") else None
        return x
    ok = []
    for f in frames:
        need = [f.get("photo"), f.get("fade_to")] if "photo" in f else list(f["compare"])
        if all(src(x) for x in need if x):
            ok.append(f)
        else:
            print("  %d줄 사진 칸 빠짐(손님 사진 없음): %s" % (i + 1, f), flush=True)
    seg = (end - t) / len(ok)
    if seg > 2.2:       # 한 장이 2초를 넘게 서 있으면 '휙휙'이 아니라 멈춘 화면이 된다 — 콘티에 장을 더 넣으라고 알린다
        print("  %d줄 사진 한 장 %.1f초 — 2초 안팎이 되게 장을 늘릴 것" % (i + 1, seg), flush=True)
    ids = []
    for j, f in enumerate(ok):
        fid = "pc%d_%d" % (i, j)
        t0 = t + j * seg
        z0, z1 = (1.0, 1.075) if (i + j) % 2 == 0 else (1.075, 1.0)
        if "compare" in f:
            o, g = (src(x) for x in f["compare"])
            inner = ('<div class="half top"><img class="kb" src="assets/%s"><b class="tag">호텔 사진</b></div>'
                     '<div class="half bot"><img class="kb" src="assets/%s"><b class="tag guest">실제 손님 사진</b></div>'
                     % (_img(o, a / (fid + "_o.jpg"), 1000), _img(g, a / (fid + "_g.jpg"), 1000)))
            # 나란히 칸도 멈춰 보이지 않게 두 장 다 천천히 줌(실측 10-22: 줌 없던 비교 칸 3.6초가 멈춤 검사에 걸림)
            js.append('tl.fromTo("#%s .kb",{scale:%.3f},{scale:%.3f,duration:%.3f,ease:"none"},%.3f);' % (fid, z0, z1, seg, t0))
            js.append('tl.fromTo("#%s .bot",{yPercent:100},{yPercent:0,duration:0.32,ease:"power3.out"},%.3f);' % (fid, t0 + 0.125))
            js.append('tl.fromTo("#%s .tag",{opacity:0,y:16},{opacity:1,y:0,duration:0.2,ease:"power2.out",stagger:0.125},%.3f);'
                      % (fid, t0 + 0.3))
            sfx.append((t0 + 0.125 - 0.068, "pop.wav", 0.2))
        else:
            inner = '<img class="kb" src="assets/%s">' % _img(src(f["photo"]), a / (fid + ".jpg"), 1200)
            js.append('tl.fromTo("#%s .kb",{scale:%.3f},{scale:%.3f,duration:%.3f,ease:"none"},%.3f);' % (fid, z0, z1, seg, t0))
            if f.get("fade_to"):
                inner += '<img class="kb2" src="assets/%s">' % _img(src(f["fade_to"]), a / (fid + "_b.jpg"), 1200)
                js.append('tl.fromTo("#%s .kb2",{opacity:0,scale:%.3f},{opacity:1,scale:%.3f,duration:0.8,ease:"power2.inOut"},%.3f);'
                          % (fid, z0 + (z1 - z0) * 0.4, z1, t0 + seg * 0.4))
        body.append('<div id="%s" class="clip card pc%s" data-start="%.3f" data-duration="%.3f" data-track-index="1">%s</div>'
                    % (fid, " small" if small else "", t0, seg, inner))
        if j:       # 줄 안에서 바뀔 땐 짧게 휙(줄 사이보다 작게)
            js.append('tl.fromTo("#%s",{x:140,filter:"blur(8px)"},{x:0,filter:"blur(0px)",duration:0.22,ease:"power3.out"},%.3f);' % (fid, t0))
            sfx.append((t0 - 0.02, "whoosh.wav", 0.12))
        ids.append("#" + fid)
    return ids[0], ids[-1]


def stage_build3(sb, work):
    from shopping_shorts import video_assemble as va
    sb, work = Path(sb), Path(work)
    shots = _shots(sb)
    voice = json.loads((work / "voice.json").read_text(encoding="utf-8"))
    # 숙소 자료 = 콘티 폴더의 state.json·insights.json(숙소마다), 없으면 네스트호텔(3판을 만든 자료)
    stp = sb / "state.json" if (sb / "state.json").exists() else ROOT / "tools/travel/work_nest/state.json"
    st = json.loads(stp.read_text(encoding="utf-8"))
    ins = st["detail"].get("review_insights") or json.loads((sb / "insights.json").read_text(encoding="utf-8"))
    counts = {x["item"]: x.get("count") for c, it in ins.items() if not c.startswith("_") for x in it}
    a = work / "assets"
    a.mkdir(exist_ok=True)
    fonts = ROOT / "shopping_shorts/static/fonts"
    for f in ("Pretendard-ExtraBold.otf", "NanumMyeongjo-ExtraBold.ttf"):
        shutil.copy(fonts / f, a / f)
    shutil.copy(Path.home() / "숏템자료/모션그래픽엔진/work/2026-10-20_라면레시피/ramen/brand/gsap.min.js", a / "gsap.min.js")
    for f in ("whoosh.wav", "pop.wav", "dung.wav", "tick.wav"):
        shutil.copy(SFX / f, a / f)
    disc = va.disclosure_layer_png({"disclosure": {"ad": True, "ai": True, "source": st["detail"].get("site_name") or "여기어때"}},
                                   str(a / "disclosure.png"))
    cf = work / "comments.json"
    comments = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    e = html.escape
    body, js, sfx, tl, auds = [], [], [], [], []
    t = 0.0
    n = len(shots)
    for i, (s, v) in enumerate(zip(shots, voice)):
        words, dur = v["words"], v["dur"]
        end = t + dur + GAP + (0.6 if i == n - 1 else 0.0)
        g = s["fx"] if "fx" in s else _V3.get(s["n"], {})
        shutil.copy(work / v["mp3"], a / v["mp3"])
        auds.append('<audio id="v%d" src="assets/%s" data-start="%.3f" data-duration="%.3f" data-track-index="10" data-volume="1"></audio>'
                    % (i, v["mp3"], t, dur))
        # 가운데 카드 영상 — 마지막 줄(정리 화면)은 카드를 작게 위로
        small = bool(g.get("chart"))
        if s.get("frames"):     # Veo 없이 사진으로(사장님 10-22 "veo 안 쓰고") — 줄 안에서 1~2초마다 사진이 바뀐다
            first, last = _photo_card(i, s["frames"], comments.get(str(s["n"])) or [], a, t, end, small, body, js, sfx)
        else:
            _fit_clip(work / ("clip_%d.mp4" % i), a / ("clip_%d.mp4" % i), end - t)
            body.append('<video id="vid%d" class="clip card%s" src="assets/clip_%d.mp4" data-start="%.3f" data-duration="%.3f" '
                        'data-track-index="1" muted playsinline></video>' % (i, " small" if small else "", i, t, end - t))
            first = last = "#vid%d" % i
        if i == 0:      # 당겼다 빠지는 줌(pull-back) — 첫 화면 시선 잡기
            js.append('tl.fromTo("%s",{scale:1.22},{scale:1,duration:0.55,ease:"power3.out"},0);' % first)
        else:           # 휙 밀려 들어옴(whip) — 흐림 12px→0, 0.32초
            js.append('tl.fromTo("%s",{x:340,filter:"blur(12px)"},{x:0,filter:"blur(0px)",duration:0.32,ease:"power3.out"},%.3f);' % (first, t))
            sfx.append((t - 0.02, "whoosh.wav", 0.22))
        if i < n - 1:   # 나갈 때 왼쪽으로
            js.append('tl.to("%s",{x:-260,filter:"blur(10px)",duration:0.14,ease:"power2.in"},%.3f);' % (last, end - 0.14))
        # 위 제목 = 말하는 문장(반 문장씩), 단어는 들리는 순간
        groups, k, em, em_t = _halves(s["line"]), 0, s["plan"]["emph"], None
        caps = []
        for gi, grp in enumerate(groups):
            idx = list(range(k, k + len(grp)))
            k += len(grp)
            c0 = t if gi == 0 else t + words[idx[0]]["start"]
            c1 = (t + words[k]["start"]) if gi + 1 < len(groups) else end
            cid = "h%d_%d" % (i, gi)
            spans = []
            for wi in idx:
                w, wt = words[wi]["word"], t + words[wi]["start"]
                if em and em in w and em_t is None:
                    em_t = wt
                    p = w.find(em)
                    inner = '%s<span class="acc">%s</span>%s' % (e(w[:p]), e(em), e(w[p + len(em):]))
                else:
                    inner = e(w)
                spans.append('<span class="w" id="%s_%d">%s</span>' % (cid, wi, inner))
                js.append('tl.fromTo("#%s_%d",{opacity:0,y:24,filter:"blur(6px)"},{opacity:1,y:0,filter:"blur(0px)",duration:0.2,ease:"power2.out"},%.3f);'
                          % (cid, wi, max(c0, wt)))
            body.append('<div id="%s" class="clip head" data-start="%.3f" data-duration="%.3f" data-track-index="5"><div class="ln">%s</div></div>'
                        % (cid, c0, c1 - c0, " ".join(spans)))
            caps.append({"t0": c0, "t1": c1, "words": [(words[w]["word"], t + words[w]["start"]) for w in idx]})
        ev = s.get("evidence")
        # 도장 '후기 N건' — 강조 단어 순간 쾅(1.6배→1, 기울기 -8°)
        if ev:
            sid = "st%d" % i
            ts_ = (em_t or t + 0.4)
            body.append('<div id="%s" class="clip stamp" data-start="%.3f" data-duration="%.3f" data-track-index="4">'
                        '<div class="sp">후기 %s건</div></div>' % (sid, ts_, end - ts_, format(ev["count"], ",")))
            js.append('tl.fromTo("#%s .sp",{scale:1.6,opacity:0,rotate:-14},{scale:1,opacity:1,rotate:-8,duration:0.22,ease:"power4.out"},%.3f);' % (sid, ts_))
            sfx.append((ts_, "dung.wav", 0.3))
        # 아래 칩 / 취소선→화살표→새 칩
        if g.get("chips"):
            tc = t + 0.35
            body.append('<div id="ch%d" class="clip chips" data-start="%.3f" data-duration="%.3f" data-track-index="3">%s</div>'
                        % (i, tc, end - tc, "".join('<span class="chip" id="ch%d_%d">%s</span>' % (i, j, e(c)) for j, c in enumerate(g["chips"]))))
            for j in range(len(g["chips"])):
                js.append('tl.fromTo("#ch%d_%d",{opacity:0,y:30,scale:0.9},{opacity:1,y:0,scale:1,duration:0.28,ease:"back.out(1.3)"},%.3f);' % (i, j, tc + j * 0.125))
            sfx.append((tc - 0.068, "pop.wav", 0.24))
        if g.get("strike"):
            tc = t + 0.3
            t_to = em_t or t + dur * 0.6
            body.append('<div id="sk%d" class="clip chips" data-start="%.3f" data-duration="%.3f" data-track-index="3">'
                        '<span class="chip old" id="sk%d_a"><i></i>%s</span><b class="arr" id="sk%d_r">→</b>'
                        '<span class="chip new" id="sk%d_b">%s</span></div>' % (i, tc, end - tc, i, e(g["strike"]), i, i, e(g["to"])))
            js.append('tl.fromTo("#sk%d_a",{opacity:0,y:24},{opacity:1,y:0,duration:0.25,ease:"power2.out"},%.3f);' % (i, tc))
            js.append('tl.fromTo("#sk%d_a i",{scaleX:0},{scaleX:1,duration:0.3,ease:"power2.inOut"},%.3f);' % (i, tc + 0.5))
            js.append('tl.fromTo("#sk%d_r",{opacity:0,x:-20},{opacity:1,x:0,duration:0.2,ease:"power2.out"},%.3f);' % (i, t_to - 0.15))
            js.append('tl.fromTo("#sk%d_b",{opacity:0,scale:0.8},{opacity:1,scale:1,duration:0.28,ease:"back.out(1.4)"},%.3f);' % (i, t_to))
            sfx.append((t_to - 0.068, "pop.wav", 0.26))
        if g.get("chart"):      # 막대가 자라는 정리 화면 — 숫자는 후기 분석 그대로
            tc = t + 0.25
            vals = [counts[x] for x in g["chart"]]
            mx = max(vals)
            rows = "".join('<div class="row" id="cr%d"><span class="lb">%s</span><span class="bar"><i id="cb%d" style="width:%dpx"></i></span>'
                           '<b class="nv" id="cn%d">0</b></div>' % (j, e(lb), j, round(560 * vv / mx), j)
                           for j, (lb, vv) in enumerate(zip(g["labels"], vals)))
            body.append('<div id="chart" class="clip chart" data-start="%.3f" data-duration="%.3f" data-track-index="3">'
                        '<div class="ct">후기 %s건이 꼽은 것</div>%s</div>' % (tc, end - tc, format(st["detail"]["review_count"], ","), rows))
            for j, vv in enumerate(vals):
                tj = tc + 0.2 + j * 0.18
                js.append('tl.fromTo("#cr%d",{opacity:0,x:-30},{opacity:1,x:0,duration:0.25,ease:"power2.out"},%.3f);' % (j, tj))
                js.append('tl.fromTo("#cb%d",{scaleX:0},{scaleX:1,duration:0.55,ease:"power3.out"},%.3f);' % (j, tj + 0.05))
                js.append('(function(){var o={v:0},el=document.getElementById("cn%d");tl.to(o,{v:%d,duration:0.55,ease:"power3.out",'
                          'onUpdate:function(){el.textContent=Math.round(o.v)}},%.3f);})();' % (j, vv, tj + 0.05))
                sfx.append((tj, "tick.wav", 0.2))
        cms = comments.get(str(s["n"])) or []
        if cms:     # 카드 아래 손님 사진 + 후기 댓글 — 컷 시작 0.4초부터 컷 끝까지, 줄마다 0.45초 간격
            tcm = t + 0.4
            rows = []
            for j, c in enumerate(cms[:2]):
                th = ('<img class="th" src="assets/%s">' % _img(c["photo"], a / ("cm_%d_%d.jpg" % (i, j)), 320)) if c.get("photo")                     else '<span class="th qi">“</span>'
                star = ("★ %s · " % c["rating"]) if c.get("rating") else ""
                rows.append('<div class="cm" id="cm%d_%d">%s<div class="bx"><p class="q">%s</p><small>%s실제 투숙객 후기 · 여기어때</small></div></div>'
                            % (i, j, th, e(c["quote"]), e(star)))
                js.append('tl.fromTo("#cm%d_%d",{opacity:0,x:60,filter:"blur(6px)"},{opacity:1,x:0,filter:"blur(0px)",duration:0.32,ease:"power3.out"},%.3f);'
                          % (i, j, tcm + j * 0.45))
                sfx.append((tcm + j * 0.45 - 0.068, "pop.wav", 0.16))
            body.append('<div id="cms%d" class="clip cmts" data-start="%.3f" data-duration="%.3f" data-track-index="6">%s</div>'
                        % (i, tcm, end - tcm, "".join(rows)))
        tl.append({"n": s["n"], "t": t, "dur": dur, "end": end, "split": t, "caps": caps, "emph": em,
                   "probe": [200, 470, "orange"]})
        t = end
    auds += ['<audio id="s%d" src="assets/%s" data-start="%.3f" data-duration="%.2f" data-track-index="%d" data-volume="%.2f"></audio>'
             % (k, f, max(0.0, t0), 0.5 if f.startswith("whoosh") else 0.4, 11 + k % 3, vol) for k, (t0, f, vol) in enumerate(sfx)]
    doc = _PAGE3 % {"dur": "%.3f" % t, "body": "\n".join(body), "auds": "\n".join(auds), "grain": _GRAIN,
                    "disc": '<img class="disc" src="assets/disclosure.png">' if disc else "", "js": "\n".join(js),
                    "or": ORANGE, "cr": CREAM}
    (work / "index.html").write_text(doc, encoding="utf-8")
    (work / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    print("만듦", work / "index.html", "길이 %.2f초, 효과음 %d개" % (t, len(sfx)))


_PAGE3 = """<!doctype html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080, height=1920">
<script src="assets/gsap.min.js"></script>
<style>
@font-face{font-family:"PretendardX";src:url("assets/Pretendard-ExtraBold.otf")}
@font-face{font-family:"MyeongjoX";src:url("assets/NanumMyeongjo-ExtraBold.ttf")}
html,body{margin:0;background:%(cr)s}
#root{position:relative;width:100%%;height:100%%;overflow:hidden;background:%(cr)s}
.clip{position:absolute}
.card{left:90px;top:500px;width:900px;height:940px;object-fit:cover;border-radius:36px;box-shadow:0 28px 60px rgba(40,25,10,.28);z-index:1}
.card.small{left:240px;top:430px;width:600px;height:720px}
.pc{overflow:hidden;background:#d9d2c8}
.pc img{position:absolute;left:0;top:0;width:100%%;height:100%%;object-fit:cover}
.pc .half{position:absolute;left:0;right:0;height:50%%;overflow:hidden}
.pc .half.top{top:0}
.pc .half.bot{bottom:0;border-top:8px solid %(cr)s}
.pc .tag{position:absolute;left:24px;top:22px;font-family:"PretendardX";font-size:36px;color:#16130f;background:#fff;padding:8px 20px;border-radius:999px}
.pc .tag.guest{background:%(or)s;color:#fff}
.head{left:0;right:0;top:0;height:460px;z-index:3}
.head .ln{position:absolute;left:70px;right:70px;top:235px;text-align:center;font-family:"PretendardX";font-size:80px;line-height:1.22;
 color:#16130f;letter-spacing:-.03em;word-break:keep-all}
.w{display:inline-block}
.acc{font-family:"MyeongjoX";color:%(or)s;display:inline-block;transform:skewX(-11deg);letter-spacing:-.02em}
.stamp{left:0;top:0;width:100%%;height:100%%;z-index:4;pointer-events:none}
.stamp .sp{position:absolute;right:70px;top:468px;padding:12px 26px;border:6px solid %(or)s;border-radius:16px;color:%(or)s;
 font-family:"PretendardX";font-size:54px;background:rgba(246,241,234,.92);letter-spacing:-.02em}
.chips{left:0;right:0;top:1335px;display:flex;justify-content:center;align-items:center;gap:22px;z-index:4}
.chip{position:relative;display:inline-block;font-family:"PretendardX";font-size:50px;color:#16130f;background:#fff;
 padding:16px 34px;border-radius:999px;box-shadow:0 10px 24px rgba(40,25,10,.16)}
.chip.old{color:#8b8279}
.chip.old i{position:absolute;left:22px;right:22px;top:50%%;height:6px;margin-top:-3px;background:%(or)s;transform-origin:left center;display:block}
.chip.new{background:%(or)s;color:#fff}
.arr{font-family:"PretendardX";font-size:60px;color:%(or)s}
.cmts{left:70px;right:70px;top:1470px;z-index:4;display:flex;flex-direction:column;gap:18px}
.cm{display:flex;align-items:center;gap:20px;background:#fff;border-radius:26px;padding:16px 22px 16px 16px;box-shadow:0 10px 26px rgba(40,25,10,.13)}
.cm .th{width:140px;height:140px;object-fit:cover;border-radius:18px;flex:none}
.cm .qi{display:flex;align-items:center;justify-content:center;background:%(cr)s;color:%(or)s;font-family:"MyeongjoX";font-size:110px;line-height:1}
.cm .bx{min-width:0}
.cm .q{margin:0;font-family:"PretendardX";font-size:40px;line-height:1.25;color:#16130f;letter-spacing:-.02em;word-break:keep-all;
 display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.cm small{display:block;margin-top:6px;font-family:"PretendardX";font-size:26px;color:#9a9086}
.chart{left:90px;right:90px;top:1190px;z-index:4;background:#fff;border-radius:32px;padding:30px 36px;box-shadow:0 20px 44px rgba(40,25,10,.18)}
.chart .ct{font-family:"PretendardX";font-size:40px;color:#8b8279;margin-bottom:14px}
.row{display:flex;align-items:center;gap:18px;height:74px}
.row .lb{width:220px;font-family:"PretendardX";font-size:40px;color:#16130f}
.row .bar{flex:1;height:30px}
.row .bar i{display:block;height:30px;border-radius:15px;background:%(or)s;transform-origin:left center}
.row .nv{width:90px;text-align:right;font-family:"PretendardX";font-size:42px;color:%(or)s}
.grain{position:absolute;inset:0;z-index:5;background-image:url("%(grain)s");opacity:.05;mix-blend-mode:multiply;pointer-events:none}
.disc{position:absolute;left:0;top:0;width:1080px;height:1920px;pointer-events:none;z-index:6}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="%(dur)s" data-fps="30">
%(body)s
<div class="grain"></div>
%(disc)s
%(auds)s
</div>
<script>
const tl = gsap.timeline({ paused: true });
%(js)s
window.__timelines["main"] = tl;
</script>
</body></html>
"""


def stage_mix(work):
    """raw.mp4(목소리+효과음) + 배경음 — 목소리가 나올 때 배경음을 눌러(사이드체인) 깔고 -14 LUFS·TP -1.5 로."""
    work = Path(work)
    raw, out = work / "raw.mp4", work / "final.mp4"
    fc = ("[0:a]asplit=2[v][k];[1:a]volume=0.30[m];"
          "[m][k]sidechaincompress=threshold=0.012:ratio=10:attack=15:release=350:makeup=1[md];"
          "[v][md]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-stream_loop", "-1", "-i", str(BGM),
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                    "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    # 덕킹 실측용 — 같은 설정으로 배경음만 뽑아 둔다(검사가 말할 때·쉴 때 크기를 잰다)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-stream_loop", "-1", "-i", str(BGM), "-filter_complex",
                    "[0:a]anull[k];[1:a]volume=0.30[m];[m][k]sidechaincompress=threshold=0.012:ratio=10:attack=15:release=350:makeup=1[a]",
                    "-map", "[a]", "-t", "%.2f" % _dur(raw), str(work / "bgm_ducked.wav")], check=True)
    print("완성", out)


def _dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def _frame(mp4, t, out):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t, "-i", str(mp4), "-frames:v", "1", str(out)], check=True)
    return out


def stage_check(work):
    """결과물 검사 — 계산이 아니라 나온 영상에서 잰다.
    ① 강조 상자: 강조 단어 시각 0.10초 전엔 자막 자리에 노란 칸이 없고 0.25초 뒤엔 있어야 한다
    ② 멈춤: 0.3초 넘게 멈춘 구간(freezedetect) ③ 소리 크기: 통합 -14±1 LUFS
    ④ 덕킹: 배경음이 말할 때가 쉴 때보다 9dB 이상 낮은가 ⑤ 다시 받아쓰기 일치 95% 이상 ⑥ 40프레임 시트"""
    import difflib
    from PIL import Image
    work = Path(work)
    mp4 = work / "final.mp4"
    tl = json.loads((work / "timeline.json").read_text(encoding="utf-8"))
    rep, ok = {}, True
    rows = []
    for L in tl:
        em = L["emph"]
        hit = next(((w, t) for c in L["caps"] for w, t in c["words"] if em and em in w), None)
        if not hit:
            continue
        cnt = []
        y0, y1, col = L.get("probe") or [1380, 1760, "yellow"]
        hitc = (lambda r, g, b: r > 210 and g > 200 and b < 90) if col == "yellow" else (lambda r, g, b: r > 200 and 55 < g < 125 and b < 85)
        for dt in (-0.10, 0.30):
            im = Image.open(_frame(mp4, hit[1] + dt, work / "chk.png")).convert("RGB").crop((0, y0, 1080, y1))
            cnt.append(sum(1 for r, g, b in im.getdata() if hitc(r, g, b)))
        good = cnt[0] < 300 and cnt[1] > (3000 if col == "yellow" else 1200)
        ok &= good
        rows.append({"줄": L["n"], "강조": em, "시각": round(hit[1], 2), "전 노란칸": cnt[0], "후 노란칸": cnt[1], "통과": good})
    rep["강조 상자"] = rows
    fz = subprocess.run(["ffmpeg", "-v", "info", "-i", str(mp4), "-vf", "freezedetect=n=0.002:d=0.3", "-f", "null", "-"],
                        capture_output=True, text=True, errors="replace").stderr
    fr = [ln.split("freeze_duration:")[1].strip() for ln in fz.splitlines() if "freeze_duration" in ln]
    rep["0.3초 넘게 멈춤"] = fr
    ok &= not fr
    lo = subprocess.run(["ffmpeg", "-v", "info", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "-"],
                        capture_output=True, text=True, errors="replace").stderr
    I = float(lo.rsplit("I:", 1)[1].split()[0])
    rep["통합 LUFS"] = I
    ok &= abs(I + 14) <= 1
    # 덕킹: 말 구간(줄 0.3초 안쪽) vs 줄 사이·끝 쉼의 배경음 RMS
    import array
    import wave
    w = wave.open(str(work / "bgm_ducked.wav"))
    sr, ch = w.getframerate(), w.getnchannels()
    a = array.array("h", w.readframes(w.getnframes()))

    def rms(t0, t1):
        s = a[int(t0 * sr) * ch:int(t1 * sr) * ch]
        return 20 * __import__("math").log10(max(1e-9, (sum(x * x for x in s[::7]) / max(1, len(s[::7]))) ** 0.5 / 32768))
    speech = sum(rms(L["t"] + 0.5, L["t"] + L["dur"] - 0.3) for L in tl) / len(tl)
    quiet = rms(tl[-1]["end"] - 0.05, _dur(mp4) - 0.02)
    rep["덕킹(dB)"] = round(quiet - speech, 1)
    ok &= quiet - speech >= 9
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from shopping_shorts import asr_check
    au = work / "final_audio.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-b:a", "96k", str(au)], check=True)
    heard = "".join(x["word"] for x in (asr_check.transcribe_words(str(au)) or [])).replace(" ", "")
    want = "".join(json.loads((work / "voice.json").read_text(encoding="utf-8"))[i]["line"] for i in range(len(tl))).replace(" ", "")
    strip = lambda s: "".join(c for c in s if c.isalnum())  # noqa: E731
    ratio = difflib.SequenceMatcher(None, strip(want), strip(heard), autojunk=False).ratio()
    rep["다시 받아쓰기 일치"] = round(ratio, 3)
    ok &= ratio >= 0.95
    n = 40
    D = _dur(mp4)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vf", "fps=%f,scale=216:384,tile=10x4" % (n / D),
                    "-frames:v", "1", str(work / "sheet40.jpg")], check=True)
    rep["통과"] = bool(ok)
    (work / "check.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return ok


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "mix":
        stage_mix(sys.argv[2])
    elif st == "check":
        sys.exit(0 if stage_check(sys.argv[2]) else 1)
    elif st == "voice":
        stage_voice(sys.argv[2], sys.argv[3], *(float(x) for x in sys.argv[4:5]))
    elif st == "comments":
        stage_comments(sys.argv[2], sys.argv[3], sys.argv[4])
    elif st == "build3":
        stage_build3(sys.argv[2], sys.argv[3])
    elif st == "build2":
        stage_build2(sys.argv[2], sys.argv[3])
    elif st == "veo":
        stage_veo(sys.argv[2], sys.argv[3])
    elif st == "build":
        stage_build(sys.argv[2], sys.argv[3])
