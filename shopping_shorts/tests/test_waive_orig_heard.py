"""#4150~#4158(11-04 박준영 d4fcd042116a): 원음 대조(orig_heard) 3번 반려 → 제작자 과제 waive → 곧바로 다시 멈춤.
대본 검사 합격 뒤 원음 대조에서 걸린 대본은 _script_try 에 안 들어가, _waive('script') 가 넘길 대본이 없거나(None → 다시 멈춤)
예전 불합격 대본을 저장했다. 판단 주인 = flow._waive · 넘길 대본 자리 = ph_script_heard 가 _script_try 에 지금 대본을 둔다."""
from tools.calcopy.hybrid import flow as FL

S_NOW = {"lines": [{"id": "O1", "kind": "orig", "src": "o.mp4", "spans": [[1.0, 3.0]], "caps_rel": [["두바두", 0, 2]]}], "title_lines": ["새 대본"]}
S_OLD = {"lines": [], "title_lines": ["옛 불합격 대본"]}


def _st(old=None):
    st = {"version": "잇템로그판_v2", "tries": {}, "log": [], "phase": "script_heard",
          "script": {"S": S_NOW, "M": {"cuts": {}}, "G": "근거"}}
    if old:
        st["_script_try"] = {"S": old, "M": {}, "G": "", "causes": ["form"]}
    return st


def _heard_until_stop(st):
    for _ in range(5):
        try:
            FL.ph_script_heard(st, {"heard": {"bad": ["O1: 들리는 말 다름"]}}, {}, {})
        except FL._Stop:
            return
    raise AssertionError("원음 대조 반려가 멈추지 않았다")


def test_원음대조로_멈춘_대본은_넘기기가_지금_대본을_저장():
    st = _st()
    _heard_until_stop(st)
    got = FL._waive(st, "script")
    assert got is not None, "넘길 대본이 없어 다시 멈췄다"
    saved = got["do"][0]["files"]["잇템로그판_v2/대본.json"]
    assert saved["title_lines"] == ["새 대본"]


def test_예전_불합격_대본이_남아도_지금_대본을_저장():
    st = _st(old=S_OLD)
    _heard_until_stop(st)
    got = FL._waive(st, "script")
    assert got["do"][0]["files"]["잇템로그판_v2/대본.json"]["title_lines"] == ["새 대본"]
