"""담은 영상 ▶ 재생 — 렌즈 해시를 영상 ID로 쓰지 않는다(2026-08-23 사장님).

사장님 제보: ▶를 누르면 "사라짐".

실측 원인: 렌즈로 찾은 영상은 shortcode가 진짜 ID가 아니라 내부 해시다
(lens_instagram_quypyf). 그걸 /api/media에 보내면 ok:False가 오고, 인스타는
임베드 폴백이 없어 썸네일로 되돌아간다 — ▶ 배지는 이미 지워져 "사라진" 것처럼 보인다.

서버 실측(핸들러 직접 호출):
    lens_instagram_quypyf -> {'ok': False, 'url': ''}
    DcNGvmCT_JX           -> {'ok': True,  'url': mp4}

규모: 최근 작업 handoff 59건 중 43건(73%)이 lens_/grab_ 해시. 전부 url은 갖고 있다.

같은 함정이 서버에도 있었고 처방이 같다 — mix_pipeline._cache_keys_for_url
("추론 전에 적힌 것을 읽는다"), 메모리 reference_캐시키_URL추론금지.
"""
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"


def _code(name):
    src = (_STATIC / name).read_text(encoding="utf-8")
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith("//"))


def test_재생ID_판정처가_하나다():
    pro = _code("produce.html")
    assert "function _poolPlayId(" in pro, "_poolPlayId 판정처가 없다"


def test_poolPlay가_판정처를_쓴다():
    """shortcode를 그대로 쓰면 렌즈 해시가 그대로 서버로 간다.

    ⚠️끊는 지점은 `\\nfunction `이지 `\\nasync function `이 아니다(2026-08-23 실측).
    poolPlay 다음에 오는 건 **비동기가 아닌** _poolFallback이라, async로만 끊으면
    슬라이스가 60줄짜리 함수를 넘어 **128줄**(_poolPlayId·_srcPendingCount까지)을
    삼킨다. 그러면 _poolPlayId 안의 정상 코드 `String(it.shortcode || '')`가 걸려
    **고쳐도 빨간불**이 된다 — 판정 범위가 틀리면 테스트가 남의 코드를 심판한다.
    """
    pro = _code("produce.html")
    body = pro.split("async function poolPlay(")[1].split("\nfunction ")[0]
    assert "_poolPlayId(" in body, "poolPlay가 판정처를 안 쓴다"
    assert "it.shortcode ||" not in body, "아직 shortcode를 그대로 쓴다"


def test_렌즈해시를_거른다():
    """판정 로직을 실제로 실행해 확인한다 — 문자열 검사로는 동작을 모른다."""
    pro = (_STATIC / "produce.html").read_text(encoding="utf-8")
    i = pro.index("function _poolPlayId(")
    j = pro.index("\nfunction ", i + 10)
    fn = pro[i:j]
    # _poolVideoIdOf도 함께 떼어 온다(판정이 이걸 부른다)
    k = pro.index("function _poolVideoIdOf(")
    m = pro.index("\nfunction ", k + 10)
    helper = pro[k:m]
    out = run_js(helper + "\n" + fn + "\n" + r"""
const cases = [
  // 렌즈 해시 + 진짜 url → url에서 뽑아야 한다
  [{shortcode:'lens_instagram_quypyf', url:'https://www.instagram.com/reel/DcNGvmCT_JX/'}, 'DcNGvmCT_JX'],
  // grab_ 접두사도 같다
  [{shortcode:'grab_douyin_b26e5b24ee36', url:'https://www.instagram.com/reel/ABCdef12345/'}, 'ABCdef12345'],
  // 진짜 shortcode는 그대로 쓴다
  [{shortcode:'DcP5AMoypLc', url:'https://www.instagram.com/reel/DcP5AMoypLc/'}, 'DcP5AMoypLc'],
  // shortcode 없으면 url에서
  [{shortcode:'', url:'https://www.instagram.com/reel/DNSu6tABMCj/'}, 'DNSu6tABMCj'],
];
let bad = 0;
for (const [it, want] of cases) {
  const got = _poolPlayId(it);
  if (got !== want) { bad++; console.log('FAIL', JSON.stringify(it), '->', got, '기대', want); }
}
console.log(bad === 0 ? 'ALL_OK' : ('BAD=' + bad));
""")
    assert "ALL_OK" in out, out


def test_인스타도_실패표시가_있다():
    """인스타는 임베드 폴백이 없다 — 조용히 사라지면 안 된다."""
    pro = _code("produce.html")
    body = pro.split("function _poolFallback(")[1].split("\nfunction ")[0]
    assert "instagram" in body, "인스타 실패 처리가 없다"


def test_즐겨찾기가_지표를_넘긴다():
    """카드에 그리는 코드(_poolStat)와 값을 가진 화면(즐겨찾기)은 이미 있었다 —
    넘기는 줄에서만 빠져 있었다(2026-08-23 사장님 "댓글이랑 팔로워수 끌고오는거")."""
    col = _code("collection.html")
    body = col.split("function sendToProduce(")[1].split("\nfunction ")[0]
    for f in ("views", "comments", "followers"):
        assert f in body, f"{f}를 제작소로 안 넘긴다"


def test_카드가_지표를_그린다():
    pro = _code("produce.html")
    body = pro.split("function _poolStat(")[1].split("\nfunction ")[0]
    for f in ("views", "comments", "followers"):
        assert f"it.{f}" in body, f"카드가 {f}를 안 그린다"
