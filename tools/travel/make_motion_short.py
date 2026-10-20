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


def stage_voice(sb, work):
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
            audio_post.finish_line_audio(str(mp3), tempo=MINA["tempo"] if mina else 1.12, silence_trim="mid")
        dur = float(va._probe_duration(str(mp3)))
        if mina:
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
                    "voice": "미나(일레븐)" if mina else "제미나이 Kore(대역 — 이 PC에 일레븐 키 없음)"})
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


def stage_mix(work):
    """raw.mp4(목소리+효과음) + 배경음 — 목소리가 나올 때 배경음을 눌러(사이드체인) 깔고 -14 LUFS·TP -1.5 로."""
    work = Path(work)
    raw, out = work / "raw.mp4", work / "final.mp4"
    fc = ("[0:a]asplit=2[v][k];[1:a]volume=0.30[m];"
          "[m][k]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=350:makeup=1[md];"
          "[v][md]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-stream_loop", "-1", "-i", str(BGM),
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                    "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    # 덕킹 실측용 — 같은 설정으로 배경음만 뽑아 둔다(검사가 말할 때·쉴 때 크기를 잰다)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-stream_loop", "-1", "-i", str(BGM), "-filter_complex",
                    "[0:a]anull[k];[1:a]volume=0.30[m];[m][k]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=350:makeup=1[a]",
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
        for dt in (-0.10, 0.25):
            im = Image.open(_frame(mp4, hit[1] + dt, work / "chk.png")).convert("RGB").crop((0, 1380, 1080, 1760))
            cnt.append(sum(1 for r, g, b in im.getdata() if r > 210 and g > 200 and b < 90))
        good = cnt[0] < 300 and cnt[1] > 3000
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
        stage_voice(sys.argv[2], sys.argv[3])
    elif st == "build":
        stage_build(sys.argv[2], sys.argv[3])
