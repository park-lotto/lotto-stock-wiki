"""TTS 음성이 **그 비트의 현재 대본**을 읽은 것임을 구조적으로 보장한다(2026-08-19).

## 실사고 (라이브 실측, 잡 f8d373618c0f)

사장님 제보: "후킹대본이랑 미리보기에 나오는 tts랑 다르다 — tts가 우리 대본을 읽고 딴소리한다"

beat 2의 대본은
    "영양사 친구가 알려준 치즈, 계란, 우유만 쓰는 고칼슘 고담백 치즈 스틱 레시피인데…"
인데 실제로 나온 소리는(align.json 실측)
    "치즈와 우유에 계란까지 톡 까서 넣으면 고칼슘 고단백 치즈 스틱 반죽 완성!이에요…"
**같은 소재의 다른 문장**이었다.

근거 — 같은 초(19:09:38)에 만들어진 형제 잡과 대조하면 명확하다:

| 잡 | beat2 대본 | tts_path |
|---|---|---|
| `e7bf5dbccd04` | (동일) | `beat_2_9f96900420.mp3` ← 대본 해시와 일치 |
| `f8d373618c0f` | (동일) | `beat_2_77fe718ad7.mp3` ← **다른 해시** |

대본이 같으면 해시도 같아야 한다. 즉 `77fe718ad7`은 **지금은 사라진 제3의 대본**으로
지어진 이름이다 → 합성 뒤에 narration만 갈리고 재합성이 안 됐다.
(tts 디렉터리 실측: 6개 파일이 04:10:05~04:10:23 한 번의 런에 생성됐고,
 현재 대본의 해시 `9f96900420` 파일은 **아예 존재하지 않는다**)

## 왜 "그때그때 고치기"로는 안 끝나나

`beat["narration"] = ...` 를 하는 곳이 코드베이스에 **20곳이 넘는다**(edit_plan 12곳,
single_source 6곳, backbone 2곳, mix_pipeline·app 각각). 새 리라이터가 하나 생길 때마다
"재합성도 같이 해야 한다"를 기억해야 하는 구조라면 반드시 또 샌다 —
2026-07-27에 파일명 해시를 도입했는데도 오늘 같은 증상이 재발한 이유가 이것이다.

그래서 **기억에 의존하지 않는 판정**을 둔다:
`tts_matches_narration(beat)` 한 곳이 "이 mp3가 이 대본 것이냐"를 파일명으로 판정하고,
어긋나면 재생·렌더 전에 드러난다. 판단처는 `_beat_tts_path` 하나뿐이다(0순위-B).
"""
import hashlib

import shopping_shorts.mix_pipeline as mp


def _p(tts_dir, beat):
    return mp._beat_tts_path(tts_dir, beat)


def test_같은_대본이면_같은_파일명():
    """대본이 같으면 파일명도 같다 — 형제 잡이 다른 이름을 쓸 수 없다는 근거."""
    b1 = {"beat_idx": 2, "narration": "영양사 친구가 알려준 치즈 스틱 레시피"}
    b2 = {"beat_idx": 2, "narration": "영양사 친구가 알려준 치즈 스틱 레시피"}
    assert _p("/t", b1) == _p("/t", b2)


def test_대본이_다르면_파일명도_다르다():
    """실사고의 핵심 — 다른 문장이 같은 파일을 공유하면 소리가 섞인다."""
    a = {"beat_idx": 2, "narration": "영양사 친구가 알려준 치즈 스틱 레시피"}
    b = {"beat_idx": 2, "narration": "치즈와 우유에 계란까지 톡 까서 넣으면"}
    assert _p("/t", a) != _p("/t", b)


def test_tts_matches_narration_판정():
    """★핵심 방어선: tts_path가 현재 narration으로 지어진 이름인지 판정한다."""
    beat = {"beat_idx": 2, "narration": "영양사 친구가 알려준 치즈 스틱 레시피"}
    beat["tts_path"] = _p("/t", beat)
    assert mp.tts_matches_narration(beat) is True

    # 대본만 갈아치우고 재합성을 안 한 상태 = 라이브에서 난 그 사고
    beat["narration"] = "치즈와 우유에 계란까지 톡 까서 넣으면"
    assert mp.tts_matches_narration(beat) is False, \
        "대본이 바뀌었는데 옛 mp3를 그대로 가리키는 상태를 못 잡았다"


def test_실사고_재현_f8d373618c0f():
    """라이브에서 실제로 난 모양 그대로 — 해시가 붙어 있어도 '다른 대본의 해시'면 잡는다."""
    beat = {
        "beat_idx": 2,
        "narration": "영양사 친구가 알려준 치즈, 계란, 우유만 쓰는 고칼슘 고담백 "
                     "치즈 스틱 레시피인데 이거 만든 후로 애들 간식 고민 싹 해결됐잖아요.",
        # 지금은 사라진 제3의 대본으로 지어진 이름(라이브 실측값)
        "tts_path": "/w/f8d373618c0f/tts/beat_2_77fe718ad7.mp3",
    }
    assert mp.tts_matches_narration(beat) is False


def test_tts_path_없으면_불일치_아님():
    """아직 합성 전(경로 없음)은 '어긋남'이 아니다 — 과잉 경보 금지."""
    assert mp.tts_matches_narration({"beat_idx": 0, "narration": "아직 합성 전"}) is True


def test_옛_비해시_이름은_어긋남으로_보지_않는다():
    """2026-07-27 이전 잡(beat_0.mp3)은 해시가 없다. 이걸 전부 '어긋남'으로 치면
    옛 잡 758건이 통째로 빨개진다 — 판정 불가는 통과시킨다(fail-open)."""
    beat = {"beat_idx": 0, "narration": "옛날 잡의 대본",
            "tts_path": "/w/j/tts/beat_0.mp3"}
    assert mp.tts_matches_narration(beat) is True


def test_해시는_narration만_본다():
    """beat_idx가 같아도 대본이 다르면 다른 파일 — 인덱스 공유로 섞이지 않는다."""
    n = "같은 문장"
    a = _p("/t", {"beat_idx": 0, "narration": n})
    b = _p("/t", {"beat_idx": 1, "narration": n})
    assert a != b                      # 인덱스가 다르면 파일도 다르다
    h = hashlib.md5(n.encode("utf-8")).hexdigest()[:10]
    assert h in a and h in b           # 그러나 해시 부분은 대본만 따른다
