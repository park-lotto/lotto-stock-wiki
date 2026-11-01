"""10-30 회사 PC 회원 완성본 2편 검토에서 나온 결함 3개.
① 썰템홈샷 '아웃백' 편: 게시글 본문 제목이 훅 2줄 중 1줄째('영업 기밀을')만 — 판 제목 칸에 join 이 없었다(렌더러는 join 을 안다).
② 숏템리폿 '전기 바이크' 편: 소재 쇼츠(남의 재편집) 문장을 그대로 옮겼다 — rules.bench_copy_problems.
③ 같은 편: 비슷한 제품 + 제품 영상 못 받음 → 원음 뒤 제품 줄 13초가 상품 사진만 — rules.alt_tail_problems."""
import json
from pathlib import Path

from tools.calcopy.hybrid import render_bench as R
from tools.calcopy.hybrid import rules as RU
from tools.calcopy.hybrid import styles as ST

ROOT = Path(__file__).resolve().parents[2]
TWO = {"title_lines": [[["영업 기밀을", None]], [["빼앗겨버린 아웃백", "hi"]]]}


def _post_frames(d):
    F = d.get("frame") or {}
    return [f for f in [F] + [(s.get("frame") or {}) for s in F.get("segments") or []] if f.get("kind") == "post"]


def test_post_title_one_slot_joins_every_line():
    """게시글형 판에서 제목 칸이 1개면 대본 제목 줄을 전부 잇는다(join) — 판 전수."""
    bad = []
    for p in sorted((ROOT / "tools/calcopy/hybrid/styles").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for F in _post_frames(d):
            if len(F.get("title") or []) == 1 and F["title"][0].get("join") is None:
                bad.append(p.stem)
    assert not bad, f"게시글 제목 칸 1개인데 join 없음(2줄 제목이 잘린다): {bad}"


def test_ssultem_homeshot_post_title_draws_whole_title(tmp_path):
    F = ST.load("썰템홈샷판")["frame"]
    segs = R.title_segs(F, TWO)
    assert len(segs) == 1 and "".join(s if isinstance(s, str) else s[0] for s in segs[0]) == "영업 기밀을 빼앗겨버린 아웃백"
    R.frame_png(TWO, {"frame": F, "version": "썰템홈샷판"}, tmp_path / "f.png")    # hi 색 칸 없는 제목 칸도 죽지 않는다


BENCH = [{"text": t} for t in ("미국에서 난리난", "전기 자전거가 있는데요", "완충하면 최대", "160km까지 간다는데", "무채색 일색인", "한국 도로에서",
                               "이거 타고 다니면", "제대로", "시선 강탈이겠네요")]


def test_bench_copy_flags_copied_line_only():
    S = {"lines": [{"id": "a", "kind": "tts", "tts": "완충하면 최대 160km까지 간다네요"},
                   {"id": "b", "kind": "tts", "tts": "한국 도로에서 이거 타고 다니면 제대로 시선 강탈이겠네요"},
                   {"id": "c", "kind": "tts", "tts": "한 번 충전에 160km를 달린대요"},
                   {"id": "d", "kind": "orig", "tts": "한국 도로에서 이거 타고 다니면 제대로 시선 강탈이겠네요"}]}
    got = RU.bench_copy_problems(S, BENCH)
    assert [x.split(":")[0] for x in got] == ["a", "b"]
    assert RU.bench_copy_problems(S, []) == []


def test_alt_tail_limits_photo_only_product_lines():
    long = {"lines": [{"id": "o", "kind": "orig", "tts": "x"}] + [{"id": f"t{i}", "kind": "tts", "tts": "쿠팡에서 비슷한 빈티지 전기 자전거로 골라 봤어요"} for i in range(4)]}
    short = {"lines": [{"id": "o", "kind": "orig", "tts": "x"}, {"id": "t", "kind": "tts", "tts": "똑같은 건 없어 비슷한 걸로 골랐어요"}]}
    assert RU.alt_tail_problems(long, 7.0)
    assert RU.alt_tail_problems(short, 7.0) == []
