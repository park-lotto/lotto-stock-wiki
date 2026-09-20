# -*- coding: utf-8 -*-
"""사장님 **계정 보이스**를 남에게 보여주면 안 된다(2026-09-09 실사고 cid 163).

무슨 일이 있었나: 3일간 6잡이 전부 같은 404로 죽었다.
  404 ... /v1/text-to-speech/FWn6AUnLRCEbJ8qmS9fq   (= '로또아나운서')
그 목소리는 voice_presets에 origin='library', owner_customer_id=0으로 있었다
(source_ref='일레븐랩스 계정 보이스', 09-04 등록 — 첫 실패 09-06과 맞아떨어진다).

일레븐랩스 계정 전용 보이스는 **만든 계정 키로만** 불린다. 그런데 keyroute 규칙상
개인 키를 낸 회원은 폴백 없이 자기 키만 쓴다 → 그 voice_id가 없어 404. 영원히 못 넘어간다.

★owner=0 안에 성격이 다른 둘이 섞여 있다(라이브 실측):
    curated 65행 = 공용 내장(어느 키로도 됨 — 계속 보여야 한다)
    library   4행 = 사장님 계정 보이스(1그룹 '로또아나운서' — 남은 못 쓴다)
그래서 owner만 보면 안 되고 **origin으로 갈라야** 한다.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shopping_shorts.store import Store  # noqa: E402


def _store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Store(path)


def _customer(st, cid=163):
    """set_last_voice는 UPDATE라 고객 행이 먼저 있어야 한다(없으면 조용히 안 써진다).

    ⚠️password_hash·salt가 NOT NULL이다 — 빼면 INSERT가 터지는데, OR IGNORE로 감싸면
      조용히 넘어가 '기억이 안 된다'로 잘못 보인다(만들면서 실제로 겪었다)."""
    with st._conn() as c:
        c.execute("INSERT INTO customers(id,username,password_hash,salt) "
                  "VALUES(?,?,?,?)", (cid, "u%d" % cid, "x", "y"))


def _add(st, preset_id, origin, owner, name="목소리"):
    with st._conn() as c:
        c.execute(
            "INSERT INTO voice_presets(preset_id,name,lang,base_voice_id,origin,"
            "owner_customer_id,created_at,voice_settings_json) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (preset_id, name, "KR", "V" + preset_id, origin, owner,
             "2026-09-04", "{}"))


def _ids(rows):
    return {r["preset_id"] for r in rows}


def test_사장님_계정보이스는_남에게_안보인다():
    """★이게 실사고 그 자체다 — 이 목소리가 목록에 뜨니까 고객이 골랐고, 3일을 잃었다."""
    st = _store()
    _add(st, "lib-voice-fwn6au-stable", "library", 0, "로또아나운서")   # 사장님 계정 보이스
    _add(st, "curated-kr-mina", "curated", 0)                          # 공용 내장
    ids = _ids(st.list_voice_presets(customer_id=163))
    assert "lib-voice-fwn6au-stable" not in ids, \
        "사장님 계정 보이스가 남의 목록에 뜨면 그 회원은 자기 키로 불러 404가 난다"
    assert "curated-kr-mina" in ids, "공용 내장(curated)까지 숨기면 고를 목소리가 사라진다"


def test_사장님_본인에게는_그대로_보인다():
    """키의 주인은 사장님이다 — 본인 화면에서까지 사라지면 안 된다."""
    st = _store()
    _add(st, "lib-voice-fwn6au-stable", "library", 0, "로또아나운서")
    assert "lib-voice-fwn6au-stable" in _ids(st.list_voice_presets(customer_id=0))


def test_내가_담은_보이스는_보인다():
    """회원이 자기 일레븐랩스 계정에서 담은 것(owner=본인)은 자기 키로 되므로 보여야 한다."""
    st = _store()
    _add(st, "lib-mine", "library", 163)
    _add(st, "lib-남의것", "library", 999)
    ids = _ids(st.list_voice_presets(customer_id=163))
    assert "lib-mine" in ids
    assert "lib-남의것" not in ids, "남이 담은 보이스는 내 키로 못 쓴다"


def test_소유자를_안가리는_곳은_전부_준다():
    """관리자 화면·배치는 customer_id 없이 부른다 — 기존 동작을 바꾸면 안 된다."""
    st = _store()
    _add(st, "lib-voice-fwn6au-stable", "library", 0)
    _add(st, "curated-kr-mina", "curated", 0)
    assert len(st.list_voice_presets()) == 2


def test_못쓰는_목소리에_고착되지_않는다():
    """★목록에서 숨기는 것만으론 안 된다 — 마지막에 쓴 목소리가 저장돼 다시 실린다.

    실사고: cid 163의 customers.last_voice_json이 'lib-voice-fwn6au-stable'이라,
    새 작업을 만들 때마다 그 목소리가 자동으로 실려 3일간 같은 404를 맞았다(6잡 전부).
    목록에 없는 목소리면 기억을 버리고 기본값으로 돌아가야 한다.
    """
    st = _store()
    _customer(st)
    _add(st, "lib-voice-fwn6au-stable", "library", 0, "로또아나운서")
    st.set_last_voice(163, {"preset_id": "lib-voice-fwn6au-stable",
                            "voice_id": "FWn6AUnLRCEbJ8qmS9fq"})
    assert st.get_last_voice(163) is None, \
        "못 쓰는 목소리를 기억해두면 새 작업마다 같은 404가 재발한다"


def test_쓸수있는_목소리_기억은_지켜진다():
    """고착 방지가 과해서 멀쩡한 기억까지 버리면 매번 목소리를 다시 골라야 한다."""
    st = _store()
    _customer(st)
    _add(st, "curated-kr-mina", "curated", 0)
    st.set_last_voice(163, {"preset_id": "curated-kr-mina", "voice_id": "Vcurated-kr-mina"})
    got = st.get_last_voice(163)
    assert got and got["preset_id"] == "curated-kr-mina"
