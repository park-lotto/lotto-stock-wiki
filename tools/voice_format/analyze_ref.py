"""사장님이 보내준 대화형 참고 쇼츠를 분석한다 (관제 128, 2026-10-10).

  py analyze_ref.py <유튜브/인스타 링크> [링크 …]

① yt-dlp 로 영상 받기 → ② 제미니 2.5-flash 가 영상을 보고 들어 줄마다 화자·목소리·대사·역할을 적는다
③ 로컬 Whisper 받아쓰기로 대사 글을 교차 확인(제미니가 지어낸 줄 잡기) ④ 우리 5틀(dialogue_script.FORMS)과 대조
결과: refs/<id>.json (줄·구조) + refs/요약.md(전체 json 으로 매번 다시 씀) — 여러 편이 쌓이면 공통 규칙을 뽑는다.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFS = HERE / "refs"
REFS.mkdir(exist_ok=True)
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

env = {}
for p in (ROOT / "shopping_shorts/.env", Path(r"C:/Users/TheRose/Desktop/로또의 주식/shopping_shorts/.env")):
    if p.exists():
        for line in open(p, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1); env.setdefault(k, v.strip().strip('"'))
KEYS = [env[k] for k in ("GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4", "GEMINI_API_KEY") if env.get(k)]

PROMPT = """이 한국어 쇼핑 쇼츠를 보고 들어라. 배경음악은 무시하고 사람 목소리(성우·TTS·실제 사람)만 본다.
JSON 하나만 답하라:
{"lines":[{"t":"MM:SS","who":"나레이터|등장인물 이름(엄마·딸·남편 등)|리액션","voice":"성별·TTS인지 사람인지·톤","text":"들리는 말 그대로","role":"훅|상황|갈등|제품등장|기능설명|반전|마무리|CTA"}],
 "n_voices": 서로 다른 목소리 수,
 "product": "제품이 무엇인가", "product_t": "제품이 처음 화면/말에 나온 MM:SS",
 "format": "한 줄 형식 요약(예: 나레이션으로 열고 딸·아빠 대화로 전개)",
 "hook": "첫 2초에 무엇으로 붙잡나",
 "turns": "대화가 어떻게 주고받나(질문→답, 반대→설득, 감탄 연쇄 등)",
 "why_works": "이 형식이 왜 먹히는가 2줄",
 "subtitle": "자막이 대사를 그대로 받나·화자별로 색/위치가 다르나"}
★who 규칙: 장면 밖에서 상황을 들려주는 목소리(과거형·"~했더니" 같은 서술)는 같은 사람 목소리여도 반드시 "나레이터".
  장면 안에서 상대에게 직접 하는 말만 등장인물 이름(딸·아빠 등)으로 적는다.
들리지 않는 말은 지어내지 마라. 확실하지 않으면 비워라."""


def fetch(url):
    vid = re.search(r"(?:shorts/|v=|youtu\.be/|reel/|p/)([\w-]{6,})", url)
    vid = vid.group(1) if vid else str(abs(hash(url)))[:10]
    mp4 = REFS / f"{vid}.mp4"
    if not mp4.exists():
        subprocess.run(["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mp4", "-o", str(mp4), url],
                       check=True, capture_output=True)
    # ★소리 없는 파일이면 멈춘다 — 2026-10-10 첫 시험에서 영상만 받아 제미니가 자막만 보고 답했다(결과가 매번 달랐다)
    a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(mp4)],
                       capture_output=True, text=True).stdout.strip()
    if not a:
        mp4.unlink()
        raise RuntimeError(f"{vid}: 받은 파일에 소리가 없다")
    return vid, mp4


def gemini(mp4):
    from google import genai
    from google.genai import types
    last = None
    for k in KEYS * 2:
        try:
            c = genai.Client(api_key=k, http_options=types.HttpOptions(timeout=180000))
            f = c.files.upload(file=str(mp4))
            while f.state.name == "PROCESSING":
                time.sleep(3); f = c.files.get(name=f.name)
            r = c.models.generate_content(model="gemini-2.5-flash", contents=[f, PROMPT],
                                          config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            return json.loads(r.text)
        except Exception as e:          # 키 소진·401 → 다음 키
            last = e
    raise RuntimeError(f"제미니 실패: {last}")


def whisper_text(mp4):
    import numpy as np
    import whisper
    # 한글 경로를 whisper 의 ffmpeg 호출이 못 읽는다 → 원시 PCM 을 파이프로 받아 넘긴다
    raw = subprocess.run(["ffmpeg", "-nostdin", "-i", str(mp4), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    m = whisper.load_model("medium")
    r = m.transcribe(audio, language="ko")
    return [{"t": round(s["start"], 1), "text": s["text"].strip()} for s in r["segments"]]


def _norm(s):
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", s or "")


def _sec(t):
    """제미니 시각 "MM:SS"(또는 숫자) → 초."""
    if isinstance(t, (int, float)):
        return float(t)
    m = re.match(r"^\s*(\d+):(\d+(?:\.\d+)?)\s*$", str(t or ""))
    return int(m.group(1)) * 60 + float(m.group(2)) if m else None


def cross_check(lines, wsegs):
    """제미니 줄 글이 Whisper 받아쓰기에 실제로 있나(2글자 조각 겹침 비율)."""
    wall = _norm(" ".join(s["text"] for s in wsegs))
    big = {wall[i:i + 2] for i in range(len(wall) - 1)}
    for L in lines:
        t = _norm(L.get("text"))
        grams = [t[i:i + 2] for i in range(len(t) - 1)]
        L["heard"] = round(sum(g in big for g in grams) / len(grams), 2) if grams else None
    return lines


def compare_forms(g):
    from shopping_shorts import dialogue_script as ds
    lines = g.get("lines") or []
    narr = sum(1 for L in lines if L.get("who") == "나레이터")
    who = [L.get("who") for L in lines]
    switches = sum(1 for a, b in zip(who, who[1:]) if a != b)
    first_talk = next((L["t"] for L in lines if L.get("who") not in ("나레이터", None)), None)
    return {"줄": len(lines), "나레이션줄": narr, "화자전환": switches,
            "첫대사초": first_talk, "제품초": g.get("product_t"),
            "우리틀": {k: v["label"] for k, v in ds.FORMS.items()}}


def write_summary():
    """refs/*.json 전부로 요약표를 다시 쓴다(같은 영상을 다시 돌려도 줄이 겹치지 않게)."""
    rows = ["# 대화형 참고 쇼츠 분석 누적 (analyze_ref.py)", "",
            "| id | 제품 | 목소리 | 줄 | 나레이션줄 | 화자전환 | 첫대사(초) | 제품(초) | 형식 | 훅 |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for f in sorted(REFS.glob("*.json"), key=lambda p: p.stat().st_mtime):
        g = json.loads(f.read_text(encoding="utf-8")); st = g.get("stats") or {}
        rows.append(f"| [{f.stem}]({g.get('url','')}) | {g.get('product','')} | {g.get('n_voices')} | {st.get('줄')} | {st.get('나레이션줄')} "
                    f"| {st.get('화자전환')} | {st.get('첫대사초')} | {st.get('제품초')} | {g.get('format','')} | {g.get('hook','')} |")
    (REFS / "요약.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(urls):
    whisper_ok = True
    for url in urls:
        vid, mp4 = fetch(url)
        g = gemini(mp4)
        for L in g.get("lines") or []:
            L["t"] = _sec(L.get("t"))
        g["product_t"] = _sec(g.get("product_t"))
        try:
            ws = whisper_text(mp4) if whisper_ok else []
        except Exception as e:          # Whisper 없으면 교차 확인만 건너뛴다(결과에 표시)
            whisper_ok, ws = False, []
            g["whisper_error"] = str(e)[:120]
        if ws:
            cross_check(g.get("lines") or [], ws)
            g["whisper"] = ws
        g["stats"] = compare_forms(g)
        g["url"] = url
        (REFS / f"{vid}.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
        st = g["stats"]
        write_summary()
        print(json.dumps({"id": vid, "format": g.get("format"), "stats": st}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
