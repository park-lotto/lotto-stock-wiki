"""사용자 API 키 암복호 — 평문을 DB에 두지 않기 위한 최소 유틸.

마스터키는 `/etc/shopping-shorts.env`의 BYOK_MASTER_KEY(서버 전용, git 미포함).
★키가 없으면 기능을 끈다 — 평문 저장으로 조용히 폴백하지 않는다. 조용한 폴백은
"되는 줄 알았는데 안 되는" 사고를 만든다(CLAUDE.md 0순위-B).

생성: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import hashlib
import os

_MASTER = os.environ.get("BYOK_MASTER_KEY", "").strip()
_fernet = None
if _MASTER:
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_MASTER.encode())
    except Exception:       # 형식이 틀린 키 — 기능을 끄고 조용히 넘어가지 않는다
        _fernet = None


def enabled():
    """키 등록 기능을 쓸 수 있는가. False면 화면에서 등록란을 감춘다."""
    return _fernet is not None


def encrypt(plain):
    if _fernet is None:
        raise RuntimeError("BYOK_MASTER_KEY가 없어 키를 저장할 수 없습니다")
    return _fernet.encrypt(plain.encode()).decode()


def decrypt(token):
    if _fernet is None:
        raise RuntimeError("BYOK_MASTER_KEY가 없어 키를 읽을 수 없습니다")
    return _fernet.decrypt(token.encode()).decode()


def mask(plain):
    """화면 표시용. 앞8·뒤5만 남기고 가운데를 가린다.
    짧은 키(20자 미만)는 앞뒤를 보여주면 통째로 드러나므로 전부 가린다."""
    if not plain:
        return ""
    if len(plain) < 20:
        return "•" * 12
    return f"{plain[:8]}{'•' * 8}{plain[-5:]}"


def fingerprint(plain):
    """키 식별자(sha256 앞16자). 중복검사·소진표시에 쓴다.
    ★인덱스 번호를 쓰면 사용자별 풀이 섞인다(comment_gen.py:68의 기존 함정)."""
    return hashlib.sha256(plain.encode()).hexdigest()[:16]
