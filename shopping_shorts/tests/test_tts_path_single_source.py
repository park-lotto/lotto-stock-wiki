"""TTS 파일 경로를 짓는 곳은 `_beat_tts_path` **한 곳뿐**이어야 한다(0순위-B).

## 왜 이 테스트가 있나

2026-07-27에 "대본이랑 TTS가 다르게 나온다" 사고를 고치며 파일명에 나레이션 해시를
넣었다(`_beat_tts_path`). 그런데 경로를 짓는 코드가 그 뒤로도 **세 군데**에 남아 있었다:

| 위치 | 이름 | 해시 |
|---|---|---|
| `_beat_tts_path` | `beat_{i}_{해시}.mp3` | ✅ |
| `_conform_beats` | `beat_{i}.mp3` | ❌ |
| `resynth_one_beat` | `beat_{i}.mp3` | ❌ |
| `/shorten`(app) | `beat_{i}.mp3` | ❌ |

해시 없는 이름은 **어느 대본으로 만든 파일인지 알 수 없다** → `tts_matches_narration`이
판정을 포기하고(fail-open) 통과시킨다 → 어긋나도 아무도 못 잡는다.
즉 해시 규칙이 있으나 마나가 된다. 그래서 규칙 자체를 테스트로 못박는다.

이 테스트가 실패하면: 새로 추가한 코드가 파일명을 직접 짓고 있다는 뜻이다.
문자열을 만들지 말고 `_beat_tts_path(tts_dir, beat)`를 불러라.
"""
import re
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent

# 파일명을 직접 조립하는 모양: f"beat_{...}.mp3" (해시 자리가 없는 것)
_LEGACY = re.compile(r'f"beat_\{[^}]+\}\.mp3"')


def _offenders(path):
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _LEGACY.search(line):
            out.append("%s:%d: %s" % (path.name, n, line.strip()))
    return out


def test_tts_경로를_직접_짓는_곳이_없다():
    bad = []
    for f in (_SRC / "mix_pipeline.py", _SRC / "app.py"):
        bad += _offenders(f)
    assert not bad, (
        "TTS 파일명을 직접 조립한 곳이 있다 — mix_pipeline._beat_tts_path를 쓰라.\n"
        "해시 없는 이름은 어느 대본의 음성인지 알 수 없어 어긋남을 영영 못 잡는다.\n  "
        + "\n  ".join(bad))
