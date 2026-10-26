"""첫 제작 요청 준비 점검(사장님 10-26 "제작에 필요한 도구·API 키를 처음 제작 요청 때 점검 · 없으면 한 번에 요구").
주인 = tools/calcopy/hybrid/runner_ops.need_list(이 판·소재에 실제로 쓰는 것만) → flow.ph_setup_check 은 멈춤/진행만.
결과물 = 회원 화면 1/13 준비 확인 줄(why·fix) — 빠진 것이 여럿이어도 **한 번에** 전부 나오나, 다 있으면 통과하나."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402
from tools.calcopy.hybrid import runner_ops as R  # noqa: E402
from tools.calcopy.hybrid import styles as STY  # noqa: E402


def _version_of(fmt: str, voice_prefix: str = "tc_") -> str:
    for n in STY.names():
        if n.startswith("_"):
            continue
        try:
            f0, _ = F.flow_format_of(n)
        except Exception:  # noqa: BLE001
            continue
        if f0 == fmt and str((STY.load(n).get("voice") or {}).get("voice_id") or "").startswith(voice_prefix):
            return n
    pytest.skip(f"{fmt} 판({voice_prefix}) 없음")


def _cookies(tmp: Path, *domains) -> str:
    rows = ["# Netscape HTTP Cookie File"]
    names = {"youtube.com": "SAPISID", "instagram.com": "sessionid", "tiktok.com": "sessionid"}
    for d in domains:
        rows.append("\t".join([f".{d}", "TRUE", "/", "TRUE", "0", names[d], "x" * 8]))
    f = tmp / "cookies.txt"
    f.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(f)


@pytest.fixture
def member_pc(monkeypatch, tmp_path):
    """회원 PC 흉내 — 키·로그인을 시험이 정한다(실제 키 파일은 읽지 않는다)."""
    from shopping_shorts.channelkit import providers
    from tools.calcopy import vmake_clean as VC
    monkeypatch.setenv("CALCOPY_CUSTOMER_MODE", "1")
    for k in ("ELEVENLABS_API_KEY", "CALCOPY_DEV_MINA_SERVER", "SHORTEM_NO_PAID", "INSTAGRAM_SESSION_PATH", "YTDLP_COOKIES_YOUTUBE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(R, "CACHE", "")
    monkeypatch.setattr(R, "PAID_OFF", False)
    monkeypatch.setattr(R.shutil, "which", lambda t: "x")
    have = {"typecast": False, "vmake": False, "speechmatics": True}
    monkeypatch.setattr(R, "have_speechmatics", lambda: have["speechmatics"])
    monkeypatch.setattr(providers, "typecast_key", lambda kf=None: "k" if have["typecast"] else "")
    monkeypatch.setattr(VC, "key_source", lambda: "member")
    monkeypatch.setattr(VC, "member_key", lambda: "k" if have["vmake"] else "")
    monkeypatch.setattr(VC, "paid_off", lambda: False)
    return have, tmp_path, monkeypatch


def _ids(xs):
    return sorted(x["id"] for x in xs)


def test_all_missing_at_once_overseas(member_pc):
    have, tmp, mp = member_pc
    have["speechmatics"] = False
    v = _version_of("해외원본형")
    got = R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "해외원본형")
    assert _ids(got) == ["login:youtube", "speechmatics", "typecast", "vmake"], got
    with pytest.raises(F._Stop) as e:
        F.ph_setup_check({"version": v, "log": []}, {"env": {"missing": got}}, {}, {})
    why, fix = e.value.why, e.value.fix
    assert why == F.SETUP_WHY and F.member_ok(why)
    assert F.member_ok(fix, need_next=True), fix
    for label in ("목소리 키(타입캐스트)", "VMake 키", "유튜브 계정 연결", "스피치매틱스 키(무료)"):
        assert label in fix, fix
    assert e.value.retry == "setup"
    for bad in ("TYPECAST", "VMAKE", ".shortem", "keys/", "need_list"):
        assert bad not in fix


def test_vmake_only_for_overseas_and_insta_only_for_insta(member_pc):
    have, tmp, mp = member_pc
    have["typecast"] = True
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, "youtube.com"))
    v = _version_of("연예인형")
    assert R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "연예인형") == []        # 연예인형은 VMake 를 부르지 않는다
    got = R.need_list(v, "https://www.instagram.com/reel/xyz/", "연예인형")
    assert _ids(got) == ["login:instagram"], got
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, "youtube.com", "instagram.com"))
    assert R.need_list(v, "https://www.instagram.com/reel/xyz/", "연예인형") == []


def test_everything_present_passes(member_pc):
    have, tmp, mp = member_pc
    have.update(typecast=True, vmake=True)
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, "youtube.com"))
    v = _version_of("해외원본형")
    assert R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "해외원본형") == []
    st = {"version": v, "log": []}
    assert F.ph_setup_check(st, {"env": {"missing": [], "keys": {}}}, {}, {}) == {"goto": "bench"}


def test_mina_voice_needs_elevenlabs_on_member_pc(member_pc):
    have, tmp, mp = member_pc
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, "youtube.com"))
    v = _version_of("연예인형", "kr-mina")
    assert _ids(R.need_list(v, "", "연예인형")) == ["elevenlabs"]
    mp.setenv("ELEVENLABS_API_KEY", "k")
    assert R.need_list(v, "", "연예인형") == []


def test_paid_off_needs_no_paid_keys(member_pc):
    """돈 0 스위치(개발 완주) = 목소리·받아쓰기·VMake 를 부르지 않는다 → 그 키도 요구하지 않는다(로그인은 그대로)."""
    have, tmp, mp = member_pc
    have["speechmatics"] = False
    mp.setattr(R, "PAID_OFF", True)
    mp.setattr(__import__("tools.calcopy.vmake_clean", fromlist=["x"]), "paid_off", lambda: True)
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, "youtube.com"))
    assert R.need_list(_version_of("해외원본형"), "", "해외원본형") == []


def test_expired_cookie_is_not_login(member_pc):
    have, tmp, mp = member_pc
    have["typecast"] = True
    f = tmp / "c.txt"
    f.write_text("\t".join([".youtube.com", "TRUE", "/", "TRUE", "1000", "SAPISID", "x"]) + "\n", encoding="utf-8")
    mp.setenv("YTDLP_COOKIES_YOUTUBE", str(f))
    assert _ids(R.need_list(_version_of("연예인형"), "", "연예인형")) == ["login:youtube"]


def test_setup_fix_groups_disk_and_install():
    fix = F.setup_fix([{"id": "typecast", "label": "목소리 키(타입캐스트)", "how": "setting"},
                       {"id": "disk", "label": "C 드라이브 빈 공간 1.5GB", "how": "disk"},
                       {"id": "tools:ffmpeg", "label": "숏템 영상 도구", "how": "install"}])
    assert F.member_ok(fix, need_next=True), fix
    assert fix.count("다시 시도해 주시면") == 1 and "C 드라이브" in fix and "다시 설치" in fix, fix
    print(json.dumps(fix, ensure_ascii=False))
