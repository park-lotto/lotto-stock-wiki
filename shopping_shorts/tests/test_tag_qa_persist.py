"""tag_qa가 **저장까지** 살아남는지 — A코호트 기준선의 생사가 여기 달려 있다.

배경(2026-08-01): `_attach_qa`가 결과에 tag_qa를 붙여도, 저장부 3곳이 각자
`{"full_text":…, "segments":…}`를 손으로 다시 만들어 **저장 순간 버리고 있었다**.
그러면 tag_audit의 A코호트(실시간 채점 점수)가 영원히 0건이라 기준선 자체가 안 생긴다.
검사 코드는 멀쩡한데 결과가 안 쌓이는, 눈에 안 띄는 종류의 구멍이다.
"""
import ast
from pathlib import Path

from shopping_shorts.script_extract import storable

_SRC = Path(__file__).resolve().parent.parent


# ── storable() 계약 ───────────────────────────────────────────────

def test_tag_qa를_보존한다():
    r = {"full_text": "말", "segments": [{"seg_id": "s0"}],
         "tag_qa": {"score": 0.42, "flags": ["훅 누락"], "retried": True}}
    assert storable(r)["tag_qa"] == r["tag_qa"]


def test_tag_qa가_없어도_키는_있다():
    """옛 경로가 tag_qa 없이 부를 수 있다 — 저장부가 KeyError로 죽으면 안 된다."""
    assert storable({"full_text": "말", "segments": []})["tag_qa"] == {}


def test_저장_대상_밖의_필드는_안_담는다():
    """화이트리스트가 유지되는지 — 중간 부산물까지 DB에 실리면 안 된다."""
    out = storable({"full_text": "말", "segments": [], "tag_qa": {},
                    "video_path": "/tmp/x.mp4", "raw_response": "…"})
    assert set(out) == {"full_text", "segments", "tag_qa"}


def test_None이나_빈_입력도_안전하다():
    assert storable(None) == {"full_text": "", "segments": [], "tag_qa": {}}


# ── 저장부가 헬퍼를 실제로 쓰는지 (하네스가 계약을 발명하지 않게) ──

def _slim_dict_literals(path):
    """`{"full_text": …, "segments": …}` **딱 그 두 키만** 든 dict 리터럴의 줄번호.

    ★왜 소스를 파싱하나: storable()을 아무리 잘 만들어도 **저장부가 안 쓰면** 의미가 없다.
    실제 저장 경로는 Gemini·다운로드·DB가 다 걸려 있어 단위 테스트로 태우기 어렵다.
    그래서 '손으로 만든 축약 dict가 다시 생기지 않는가'를 구조로 잠근다.

    ★키가 '정확히 그 둘'일 때만 잡는 이유: 처음엔 '두 키를 포함'으로 짰다가 응답 스키마
    (`_RESPONSE_SCHEMA`의 properties)와 추출 결과 원본(product_benefits 등을 더 든 dict)까지
    걸려 노이즈가 났다. 위험한 건 '축약본'이지 두 키를 쓰는 모든 dict가 아니다."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        if any(k is None for k in node.keys):        # {**other} 스프레드는 판단 보류
            continue
        keys = {k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if keys == {"full_text", "segments"}:
            found.append(node.lineno)
    return found


def test_저장부가_손으로_만든_dict를_다시_들이지_않는다():
    """full_text+segments만 든 dict 리터럴이 새로 생기면 tag_qa가 또 샌다.

    허용 목록(캐시 히트 등)은 tag_qa를 되쓰지 않는 자리라 무해하지만, 새 자리가
    늘어나면 이 테스트가 먼저 깨져 '여기도 storable() 써라'를 알려준다."""
    # 허용된 3곳은 전부 **읽기 전용 재구성**이라 tag_qa를 덮어쓰지 않는다(실측 확인):
    #   app.py 1829 — 도서관 저장 핸들러의 캐시히트 분기. 이 분기엔 save_script 호출이
    #                 아예 없다(미스 분기만 저장한다).
    #   app.py 6548 — _load_work_sources용 소스 빌더. DB에 쓰지 않는다.
    #   app.py 6747 — 자동적재 캐시히트. todo에 save_script 플래그를 안 세워 되쓰지 않는다.
    #   script_extract.py — `_EMPTY` 센티넬(추출 실패 시 반환값). 저장부가 아니다.
    # 이 중 하나라도 저장 경로로 바뀌면 그 자리에 storable()을 쓰고 이 수를 줄여라.
    allowed = {"app.py": 2, "script_extract.py": 1}
    for name in ("app.py", "prewarm.py", "script_extract.py"):
        hits = _slim_dict_literals(_SRC / name)
        assert len(hits) <= allowed.get(name, 0), (
            f"{name}: full_text/segments만 든 dict 리터럴 {hits} — "
            f"저장 경로면 script_extract.storable()을 써라(tag_qa 누락 재발)")
