"""원어민 역할 검수 엔진(관제 254, 2026-10-23 사장님 "검수엔진을 역할로 하나 만들어 … 교차검증을 ai별로").

왜: 대본·번역을 쓰는 AI(Gemini)가 스스로 채점하면 같은 약점을 못 본다. 그래서 **회사가 다른 AI 여럿**에게
그 나라 쇼핑 쇼츠 전문가 역할을 주고 줄마다 따로 채점시킨 뒤, **2명 이상이 어색하다고 한 줄만** 문제로 본다.

심사위원(전부 무료·구독 안에서 돈다 — 2026-10-23 실측으로 확인한 것만):
  gemini  = script_generate._call_json(버텍스→키풀)     구글
  qwen    = Groq qwen/qwen3.8-27b                          알리바바(중국어 원어민 쪽 데이터)
  gptoss  = Groq openai/gpt-oss-120b                       오픈AI 공개 모델
  claude  = `claude -p` (사장님 Max 구독, API 과금 없음)   앤트로픽 — 이 PC·claude CLI 가 있는 곳에서만
없는 심사위원은 건너뛴다(조용히 넘기지 않고 결과의 skipped 에 이유를 남긴다).

  from shopping_shorts.native_review import review
  r = review(["这个真的绝了", ...], "zh", source=["이거 진짜 미쳤다", ...])
  → {"lines":[{i, text, votes:{judge:{score,problem,fix}}, flagged, fix}], "judges":[...], "skipped":{...}}
"""
import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

PERSONA = {
    "zh": ("你是在抖音、快手做了10年带货短视频的中国本土内容总监，每天审几百条口播文案。"
           "你一听就知道一句话是不是中国人会说的，还是翻译腔、书面语、外国人写的中文。"),
    "ja": ("あなたはTikTok・YouTubeショートで10年間ショッピング動画を作ってきた日本人のディレクターです。"
           "一目で「日本人が実際に言うセリフ」か「翻訳っぽい・書き言葉・外国人が書いた日本語」かが分かります。"),
    "en": ("You are an American TikTok Shop creative director with 10 years of experience reviewing hundreds of "
           "voice-over scripts a day. You instantly hear whether a line is how a native US creator talks or a translation."),
    "ko": ("당신은 한국 쇼핑 쇼츠(유튜브·인스타)를 10년 동안 만든 PD입니다. 한 줄만 들어도 한국 사람이 실제로 하는 말인지, "
           "번역투·글말·외국인이 쓴 한국어인지 바로 압니다."),
}

_ASK = """{persona}

Below is a shopping-shorts voice-over script{src_note}. Judge EVERY line as a native speaker hearing it spoken.
For each line give:
- score: 1-5 (5 = exactly how a native creator would say it, 3 = understandable but a native would not say it this way, 1 = wrong/unnatural)
- problem: short reason in Korean if score <= 3, else ""
- fix: if score <= 3, the natural native rewrite written in {lang_name} ONLY (never Korean unless the script is Korean; same meaning, nothing added), else ""
Return ONLY JSON: {{"lines":[{{"i":0,"score":5,"problem":"","fix":""}}, ...]}} with exactly {n} items.

Lines (JSON, [index, line{src_col}]):
{rows}
"""

_LANG_NAME = {"zh": "Simplified Chinese", "ja": "Japanese", "en": "English", "ko": "Korean"}
GROQ_MODELS = {"qwen": "qwen/qwen3.8-27b", "gptoss": "openai/gpt-oss-120b"}
FLAG_SCORE = 3          # 이 점수 이하 = 어색하다는 표
FLAG_VOTES = 2          # 이만큼 모이면 문제 줄


def _prompt(lines, lang, source):
    rows = [[i, x] + ([source[i]] if source else []) for i, x in enumerate(lines)]
    return _ASK.format(persona=PERSONA[lang], n=len(lines), lang_name=_LANG_NAME[lang],
                       src_note=" (third column = original it was adapted from — meaning must match)" if source else "",
                       src_col=", original" if source else "", rows=json.dumps(rows, ensure_ascii=False))


def _parse(text):
    """모델 답에서 JSON 덩어리만 꺼낸다(생각 과정·코드펜스가 앞뒤에 붙어 와도)."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = re.search(r"\{.*\}", t, flags=re.S)
    return json.loads(m.group(0)) if m else {}


def _env_key(name):
    v = os.environ.get(name)
    if v:
        return v
    from pathlib import Path
    for env in (Path(__file__).resolve().parents[1] / ".env",):
        if env.exists():
            for ln in env.read_text(encoding="utf-8").splitlines():
                if ln.startswith(name + "="):
                    return ln.split("=", 1)[1].strip().strip('"')
    return None


def _judge_gemini(prompt):
    from shopping_shorts import script_generate
    schema = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
        "i": {"type": "integer"}, "score": {"type": "integer"}, "problem": {"type": "string"}, "fix": {"type": "string"}},
        "required": ["i", "score", "problem", "fix"]}}}, "required": ["lines"]}
    return script_generate._call_json(prompt, schema, vertex_op="native_review") or {}


def _judge_groq(model):
    def run(prompt):
        import requests
        key = _env_key("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY 없음")
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=120,
                          headers={"Authorization": "Bearer " + key},
                          json={"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
                                "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return _parse(r.json()["choices"][0]["message"]["content"])
    return run


def _judge_claude(prompt):
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI 없음")
    import tempfile
    # ★프로젝트 폴더에서 띄우면 이 프로젝트의 CLAUDE.md·훅(대시보드 기록)을 따라가 채점 대신 딴 일을 한다(실측 10-23).
    #   설정·훅·도구 없이, 프로젝트 밖 빈 폴더에서, 채점 전용 지시로만 띄운다(--bare 는 구독 로그인까지 막아 못 쓴다)
    p = subprocess.run([exe, "-p", "--setting-sources", "", "--tools", "", "--output-format", "text",
                        "--system-prompt", "You are a strict script grader. Output only the requested JSON."],
                       input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=300,
                       cwd=tempfile.gettempdir())
    if p.returncode != 0:
        raise RuntimeError("claude -p 실패: " + (p.stderr or "")[:200])
    return _parse(p.stdout)


JUDGES = {"gemini": _judge_gemini, "qwen": _judge_groq(GROQ_MODELS["qwen"]),
          "gptoss": _judge_groq(GROQ_MODELS["gptoss"]), "claude": _judge_claude}


def review(lines, lang, source=None, judges=None):
    """줄마다 심사위원 표를 모아 판정. 판단 주인 = 이 함수(FLAG_SCORE·FLAG_VOTES)."""
    if lang not in PERSONA:
        raise ValueError("지원하지 않는 언어: %r" % (lang,))
    lines = [str(x or "").strip() for x in lines]
    prompt = _prompt(lines, lang, source)
    names = list(judges or JUDGES)
    got, skipped = {}, {}

    def call(name):
        try:
            return name, JUDGES[name](prompt), None
        except Exception as e:      # noqa: BLE001 — 한 심사위원이 죽어도 나머지로 판정, 이유는 남긴다
            return name, None, f"{type(e).__name__}: {e}"[:200]
    with ThreadPoolExecutor(len(names)) as ex:
        for name, res, err in ex.map(call, names):
            rows = (res or {}).get("lines") if isinstance(res, dict) else None
            if err or not isinstance(rows, list):
                skipped[name] = err or "응답에 lines 없음"
                continue
            got[name] = {int(r.get("i", -1)): r for r in rows if isinstance(r, dict)}
    from shopping_shorts.script_translate import _is_lang
    out = []
    for i, text in enumerate(lines):
        votes = {n: {"score": int(v[i].get("score") or 0), "problem": str(v[i].get("problem") or ""),
                     "fix": str(v[i].get("fix") or "")} for n, v in got.items() if i in v}
        for v in votes.values():        # 다른 언어로 쓴 고친 문장은 버린다(실측: 문제 설명 따라 한국어로 써 옴)
            if v["fix"] and not _is_lang(v["fix"], lang):
                v["fix"] = ""
        bad = [n for n, v in votes.items() if 0 < v["score"] <= FLAG_SCORE]
        flagged = len(bad) >= min(FLAG_VOTES, max(1, len(votes)))
        fix = ""
        if flagged:     # 고친 문장 = 어색하다고 한 심사위원 중 가장 낮은 점수를 준 쪽의 안(중국어는 qwen 우선)
            pref = sorted(bad, key=lambda n: (0 if (lang == "zh" and n == "qwen") else 1, votes[n]["score"]))
            fix = next((votes[n]["fix"] for n in pref if votes[n]["fix"]), "")
        out.append({"i": i, "text": text, "votes": votes, "flagged": flagged, "fix": fix})
    return {"lang": lang, "judges": list(got), "skipped": skipped, "lines": out}
