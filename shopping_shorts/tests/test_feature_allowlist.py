"""관리자 아닌 사람에게 **기능 하나만** 열어주는 길 (2026-08-31 사장님 지시).

★admin=1을 주면 안 된다 — 수집·차단·계정목록까지 통째로 열린다.
"""
from shopping_shorts import app as A
from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(tmp_path / "t.db")


def test_허용목록에_있으면_열린다(tmp_path):
    st = _store(tmp_path)
    st.set_setting("feature_allow_naverclip", "11")
    assert A._feature_allowed(st, 11, "naverclip") is True


def test_남은_안_열린다(tmp_path):
    st = _store(tmp_path)
    st.set_setting("feature_allow_naverclip", "11")
    assert A._feature_allowed(st, 12, "naverclip") is False
    assert A._feature_allowed(st, None, "naverclip") is False


def test_목록이_비면_아무도_안_열린다(tmp_path):
    assert A._feature_allowed(_store(tmp_path), 11, "naverclip") is False


def test_여러명_공백이나_쉼표_섞여도_읽는다(tmp_path):
    st = _store(tmp_path)
    st.set_setting("feature_allow_naverclip", " 11, 42 ,7 ")
    for cid in (11, 42, 7):
        assert A._feature_allowed(st, cid, "naverclip") is True
    assert A._feature_allowed(st, 8, "naverclip") is False


def test_모르는_기능은_안_열린다(tmp_path):
    """오타(`naverclipp`)로 아무 설정키나 만들어 권한이 새면 안 된다."""
    st = _store(tmp_path)
    st.set_setting("feature_allow_아무거나", "11")
    assert A._feature_allowed(st, 11, "아무거나") is False


def test_관리자는_설정과_무관하게_열린다(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "_is_admin", lambda cid: cid == 0)
    assert A._feature_allowed(_store(tmp_path), 0, "naverclip") is True


def test_설정키가_관리자화면에서_바꿀수있게_등록돼있다():
    """배포 없이 사장님이 넣고 뺄 수 있어야 한다."""
    assert "feature_allow_naverclip" in A._ADMIN_SETTING_KEYS
