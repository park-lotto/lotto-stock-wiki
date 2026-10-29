"""원어민 운율 기준 범위 재기(관제 254) — 일본 쇼핑 쇼츠 실음성(ja_shorts_corpus.py 결과)을 음성 듣기 엔진으로 재서
말 빠르기·음높이 폭·긴 쉼의 분포(10~90%)를 낸다. 결과를 shopping_shorts/voice_listen.NATIVE_BAND 에 옮긴다.

  py tools/ja_caption/native_band.py <corpus폴더>
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main(folder):
    import numpy as np
    from shopping_shorts import voice_listen as vl
    rows = []
    for v in json.loads((Path(folder) / "corpus.json").read_text(encoding="utf-8")):
        mp3 = Path(folder) / f"{v['id']}.mp3"
        heard, words = vl.transcribe(mp3, "ja")
        if len(words) < 10:
            continue
        pr = vl.prosody(mp3, words, vl.reading(heard, "ja"), "ja")
        rows.append(pr); print(v["id"], pr["syl_per_sec"], pr["pitch_semitones"], pr["long_pause_per_10s"])
    for k in ("syl_per_sec", "pitch_semitones", "long_pause_per_10s"):
        xs = [r[k] for r in rows]
        print(k, "10%%=%.2f 50%%=%.2f 90%%=%.2f" % tuple(np.percentile(xs, [10, 50, 90])))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
