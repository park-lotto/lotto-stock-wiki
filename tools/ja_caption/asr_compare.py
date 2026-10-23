"""받아쓰기 엔진 대조 — 위스퍼 vs 스피치매틱스, 같은 TTS 를 '읽는 소리'로 대본과 맞춰 오독을 몇 건 잡나(관제 254, 2026-10-23).

키: ~/.volcano/keys/speechmatics (볼케이노·칼카피 엔진과 같은 자리). 언어는 ja 로 고정(auto 는 짧은 줄을 틀리게 고를 수 있다).
  py tools/ja_caption/asr_compare.py <index.json> [...]   → 첫 index.json 옆 asr_compare.json + 줄별 차이 출력
"""
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def speechmatics(path, lang="ja"):
    import requests
    key = os.environ.get("SPEECHMATICS_API_KEY") or Path(os.path.expanduser("~/.volcano/keys/speechmatics")).read_text().strip()
    H = {"Authorization": f"Bearer {key}"}
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


def main(indexes):
    from concurrent.futures import ThreadPoolExecutor
    from shopping_shorts.voice_listen import transcribe, compare_reading
    rows = []
    for ix in indexes:
        rows += [r for r in json.loads(Path(ix).read_text(encoding="utf-8")) if r.get("sent")]
    prev = Path(indexes[0]).with_name("asr_compare.json")   # 다시 돌릴 때 위스퍼 받아쓰기는 재사용(CPU 20분)
    old = {r["file"]: r["whisper"]["heard"] for r in json.loads(prev.read_text(encoding="utf-8"))} if prev.exists() else {}
    with ThreadPoolExecutor(8) as ex:   # 스피치매틱스는 원격이라 동시에, 위스퍼는 이 PC에서 하나씩
        sm = list(ex.map(lambda r: speechmatics(r["file"]), rows))
    for r, s in zip(rows, sm):
        w = old.get(r["file"]) or transcribe(r["file"], "ja")[0]
        for name, heard in (("whisper", w), ("speechmatics", s)):
            c = compare_reading(r["sent"], heard, "ja")
            r[name] = {"heard": heard, "match": c["match"],
                       "diffs": [f"{d['where']}→{d['heard_where']}" for d in c["diffs"]]}
        print(Path(r["file"]).name, "| W", r["whisper"]["match"], r["whisper"]["diffs"], "| S", r["speechmatics"]["match"], r["speechmatics"]["diffs"], flush=True)
    Path(indexes[0]).with_name("asr_compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    for n in ("whisper", "speechmatics"):
        print(n, "차이 있는 줄", sum(1 for r in rows if r[n]["diffs"]), "/", len(rows))


if __name__ == "__main__":
    main(sys.argv[1:])
