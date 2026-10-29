"""받아쓰기 엔진 대조 — 위스퍼 vs 스피치매틱스, 같은 TTS 를 '읽는 소리'로 대본과 맞춰 오독을 몇 건 잡나(관제 254, 2026-10-23).

키: ~/.volcano/keys/speechmatics (볼케이노·칼카피 엔진과 같은 자리). 언어는 ja 로 고정(auto 는 짧은 줄을 틀리게 고를 수 있다).
  py tools/ja_caption/asr_compare.py [--lang zh] <index.json> [...]   → 첫 index.json 옆 asr_compare.json + 줄별 차이 출력
"""
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def speechmatics(path, lang="ja"):
    import requests
    key = os.environ.get("SPEECHMATICS_API_KEY") or Path(os.path.expanduser("~/.volcano/keys/speechmatics")).read_text().strip()
    H = {"Authorization": f"Bearer {key}"}
    lang = {"zh": "cmn"}.get(lang, lang)      # 스피치매틱스 표준중국어 코드는 cmn(zh 는 400 — 실측 10-23)
    cfg = {"type": "transcription", "transcription_config": {"language": lang, "operating_point": "enhanced"}}
    with open(path, "rb") as f:
        r = requests.post("https://asr.api.speechmatics.com/v2/jobs", headers=H, files={"data_file": f},
                          data={"config": json.dumps(cfg)}, timeout=120)
    r.raise_for_status()
    jid = r.json()["id"]
    for _ in range(100):
        time.sleep(2)
        s = requests.get(f"https://asr.api.speechmatics.com/v2/jobs/{jid}", headers=H, timeout=30).json()["job"]["status"]
        if s == "done":
            break
        if s in ("rejected", "deleted"):
            raise RuntimeError(s)
    t = requests.get(f"https://asr.api.speechmatics.com/v2/jobs/{jid}/transcript?format=txt", headers=H, timeout=60)
    return t.content.decode("utf-8").strip()   # requests 가 txt 를 latin-1 로 짐작해 일본어가 깨진다(실측 10-23)


def _bad_positions(sent, heard, lang):
    """대본 '읽는 소리'에서 받아쓰기와 어긋난 자리(인덱스 집합) — 두 엔진이 같은 자리를 짚었나 보려고."""
    import difflib
    from shopping_shorts.voice_listen import reading
    a, b = reading(sent, lang), reading(heard, lang)
    if lang == "zh":
        a, b = [x.rstrip("012345") for x in a], [x.rstrip("012345") for x in b]
    out = set()
    for t, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if t != "equal":
            out |= set(range(i1, max(i2, i1 + 1)))
    return out


def agreed(rows, lang):
    """두 엔진이 **같은 자리**를 짚은 줄 = 확실한 오독(다시 합성). 한쪽만이면 사람이 듣는다(관제 254 규칙)."""
    return [r for r in rows if _bad_positions(r["sent"], r["whisper"]["heard"], lang)
            & _bad_positions(r["sent"], r["speechmatics"]["heard"], lang)]


def main(indexes, lang="ja"):
    from concurrent.futures import ThreadPoolExecutor
    from shopping_shorts.voice_listen import transcribe, compare_reading
    rows = []
    for ix in indexes:
        rows += [r for r in json.loads(Path(ix).read_text(encoding="utf-8")) if r.get("sent")]
    prev = Path(indexes[0]).with_name("asr_compare.json")   # 다시 돌릴 때 위스퍼 받아쓰기는 재사용(CPU 20분)
    _old = json.loads(prev.read_text(encoding="utf-8")) if prev.exists() else []
    old = {r["file"]: r["whisper"]["heard"] for r in _old}
    old_sm = {r["file"]: r["speechmatics"]["heard"] for r in _old if r.get("speechmatics")}
    with ThreadPoolExecutor(8) as ex:   # 스피치매틱스는 원격이라 동시에, 위스퍼는 이 PC에서 하나씩
        sm = list(ex.map(lambda r: old_sm.get(r["file"]) or speechmatics(r["file"], lang), rows))
    for r, s in zip(rows, sm):
        w = old.get(r["file"]) or transcribe(r["file"], lang)[0]
        for name, heard in (("whisper", w), ("speechmatics", s)):
            c = compare_reading(r["sent"], heard, lang)
            r[name] = {"heard": heard, "match": c["match"],
                       "diffs": [f"{d['where']}→{d['heard_where']}" for d in c["diffs"]]}
        print(Path(r["file"]).name, "| W", r["whisper"]["match"], r["whisper"]["diffs"], "| S", r["speechmatics"]["match"], r["speechmatics"]["diffs"], flush=True)
    Path(indexes[0]).with_name("asr_compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    for n in ("whisper", "speechmatics"):
        print(n, "차이 있는 줄", sum(1 for r in rows if r[n]["diffs"]), "/", len(rows))
    ag = agreed(rows, lang)
    print("두 엔진이 같은 자리를 짚은 줄(확실한 오독)", len(ag), "/", len(rows))
    for r in ag:
        print(" ", r.get("preset", ""), r.get("i", ""), r["sent"], "| W:", r["whisper"]["heard"], "| S:", r["speechmatics"]["heard"])


if __name__ == "__main__":
    a = sys.argv[1:]
    lg = "ja"
    if a[:1] == ["--lang"]:
        lg, a = a[1], a[2:]
    main(a, lg)
