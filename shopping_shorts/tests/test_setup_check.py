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


ALL = ("youtube.com", "instagram.com", "tiktok.com")


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
    have = {"typecast": False, "vmake": False, "speechmatics": True, "coupang": "ok"}
    monkeypatch.setattr(R, "coupang_key_state", lambda: have["coupang"])
    monkeypatch.setattr(R, "browser_ok", lambda: True)
    monkeypatch.setattr(R, "have_speechmatics", lambda: have["speechmatics"])
    monkeypatch.setattr(providers, "typecast_key", lambda kf=None: "k" if have["typecast"] else "")
    monkeypatch.setattr(VC, "key_source", lambda: "member")
    monkeypatch.setattr(VC, "member_key", lambda: "k" if have["vmake"] else "")
    monkeypatch.setattr(VC, "paid_off", lambda: False)
    from tools.calcopy import origin_find as OF      # 받기(yt)가 쓰는 로그인 = 회원 PC 처럼 브라우저 프로필 없음(쿠키 파일만)
    monkeypatch.setattr(OF, "yt_auth", lambda url: ["--js-runtimes", "node"])
    monkeypatch.setattr(R, "yt_probe", lambda url: "")                  # 실제 받기 시험 = 성공(시험은 회선을 두드리지 않는다)
    return have, tmp_path, monkeypatch


def _ids(xs):
    return sorted(x["id"] for x in xs)


def test_all_missing_at_once_overseas(member_pc):
    """11-02 사장님 "무조건 3개 다 로그인 처음에 · 쿠팡 키 점검" — 빠진 것은 시작 전에 한 번에. 스피치매틱스·VMake 는 대체가 있어 요구하지 않는다."""
    have, tmp, mp = member_pc
    have.update(speechmatics=False, coupang="none")
    v = _version_of("해외원본형")
    got = R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "해외원본형")
    assert _ids(got) == ["coupang", "login:instagram", "login:tiktok", "login:youtube", "typecast"], got
    with pytest.raises(F._Stop) as e:
        F.ph_setup_check({"version": v, "log": []}, {"env": {"missing": got}}, {}, {})
    why, fix = e.value.why, e.value.fix
    assert why == F.SETUP_WHY and F.member_ok(why)
    assert F.member_ok(fix, need_next=True), fix
    for label in ("목소리 키(타입캐스트)", "쿠팡 파트너스 키", "유튜브 계정 연결", "틱톡 계정 연결", "인스타그램 계정 연결"):
        assert label in fix, fix
    assert e.value.retry == "setup"
    for bad in ("TYPECAST", "VMAKE", ".shortem", "keys/", "need_list"):
        assert bad not in fix


def test_three_logins_regardless_of_source(member_pc):
    """소재가 유튜브여도 재료 단계에서 틱톡·인스타를 받는다 — 소재 주소와 상관없이 셋 다 시작 전에."""
    have, tmp, mp = member_pc
    have["typecast"] = True
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, "youtube.com"))
    v = _version_of("연예인형")
    got = R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "연예인형")
    assert _ids(got) == ["login:instagram", "login:tiktok"], got
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, *ALL))
    assert R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "연예인형") == []


def test_instagram_session_file_alone_is_not_login(member_pc):
    """세션 파일이 남아 있어도 쿠키가 죽었으면 로그인이 아니다(파일 있음 = 통과였던 구멍)."""
    have, tmp, mp = member_pc
    have["typecast"] = True
    f = tmp / "instagram.json"
    f.write_text("{}", encoding="utf-8")
    mp.setenv("INSTAGRAM_SESSION_PATH", str(f))
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, "youtube.com", "tiktok.com"))
    assert "login:instagram" in _ids(R.need_list(_version_of("연예인형"), "", "연예인형"))


def test_coupang_key_checked_by_real_call_state(member_pc):
    """쿠팡 키 = 있나만 보지 않고 실제 호출 결과로. 없음·죽음 모두 시작 전에 요구, 제품 없는 자막노래형은 안 묻는다."""
    have, tmp, mp = member_pc
    have["typecast"] = True
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, *ALL))
    v = _version_of("연예인형")
    for st in ("none", "bad"):
        have["coupang"] = st
        assert _ids(R.need_list(v, "", "연예인형")) == ["coupang"]
    assert "coupang" not in _ids(R.need_list(v, "", "자막노래형"))


def test_browser_required_for_login_window(member_pc):
    have, tmp, mp = member_pc
    have["typecast"] = True
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, *ALL))
    mp.setattr(R, "browser_ok", lambda: False)
    got = R.need_list(_version_of("연예인형"), "", "연예인형")
    assert _ids(got) == ["browser"], got
    assert F.member_ok(F.setup_fix(got), need_next=True), F.setup_fix(got)


def test_everything_present_passes(member_pc):
    have, tmp, mp = member_pc
    have.update(typecast=True, vmake=True)
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, *ALL))
    v = _version_of("해외원본형")
    assert R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "해외원본형") == []
    st = {"version": v, "log": []}
    assert F.ph_setup_check(st, {"env": {"missing": [], "keys": {}}}, {}, {}) == {"goto": "bench"}


def test_mina_voice_needs_elevenlabs_on_member_pc(member_pc):
    have, tmp, mp = member_pc
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, *ALL))
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
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, *ALL))
    assert R.need_list(_version_of("해외원본형"), "", "해외원본형") == []


def test_expired_cookie_is_not_login(member_pc):
    have, tmp, mp = member_pc
    have["typecast"] = True
    f = tmp / "c.txt"
    f.write_text("\t".join([".youtube.com", "TRUE", "/", "TRUE", "1000", "SAPISID", "x"]) + "\n", encoding="utf-8")
    mp.setenv("YTDLP_COOKIES_YOUTUBE", str(f))
    assert "login:youtube" in _ids(R.need_list(_version_of("연예인형"), "", "연예인형"))


def test_setup_fix_groups_disk_and_install():
    fix = F.setup_fix([{"id": "typecast", "label": "목소리 키(타입캐스트)", "how": "setting"},
                       {"id": "disk", "label": "C 드라이브 빈 공간 1.5GB", "how": "disk"},
                       {"id": "tools:ffmpeg", "label": "숏템 영상 도구", "how": "install"}])
    assert F.member_ok(fix, need_next=True), fix
    assert fix.count("다시 시도해 주시면") == 1 and "C 드라이브" in fix and "다시 설치" in fix, fix
    print(json.dumps(fix, ensure_ascii=False))


def test_youtube_check_uses_same_auth_as_download(member_pc):
    """10-27 실사고: 준비 확인은 쿠키 파일만 보고 통과, 실제 받기(runner_ops.yt → origin_find.yt_auth)는 전용 프로필(mcp*) 로그인 없음으로 멈춤.
    준비 확인은 받기와 **같은 함수**로 판정해야 한다 — 받기가 PermissionError 면 쿠키 파일이 있어도 '유튜브 계정 연결'이 나와야 한다."""
    have, tmp, mp = member_pc
    have["typecast"] = True
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, *ALL))
    from tools.calcopy import origin_find as OF

    def no_login(url):
        raise PermissionError("유튜브 전용 프로필(mcp*)에 로그인된 계정이 없다")
    mp.setattr(OF, "yt_auth", no_login)
    v = _version_of("연예인형")
    assert "login:youtube" in _ids(R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "연예인형"))
    mp.setattr(OF, "yt_auth", lambda url: ["--cookies-from-browser", "firefox:x", "--js-runtimes", "node"])   # 프로필로 받는 PC = 쿠키 파일 없어도 받는다
    mp.delenv("YTDLP_COOKIES_YOUTUBE")
    assert "login:youtube" not in _ids(R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "연예인형"))


def test_probe_catches_download_failure_even_when_login_looks_fine(member_pc):
    """뿌리(98 #157·#158·#159·10-27): 준비 확인이 파일·쿠키 이름만 보고 통과 → 실제 받기에서 멈춤이 꼴만 바꿔 4번.
    준비 확인은 그 편 소재 영상을 **실제 받기 함수(yt)** 로 한 번 시험한다 — 실패하면 그 이유를 한 번에 보여 준다."""
    have, tmp, mp = member_pc
    have["typecast"] = True
    mp.setenv("YTDLP_COOKIES_YOUTUBE", _cookies(tmp, *ALL))
    mp.setattr(R, "yt_probe", lambda url: "Video unavailable")
    v = _version_of("연예인형")
    got = R.need_list(v, "https://www.youtube.com/shorts/abcdefghijk", "연예인형")
    assert "probe:youtube" in _ids(got), got
    assert "Video unavailable" in next(x["label"] for x in got if x["id"] == "probe:youtube")
    assert "probe:youtube" not in _ids(R.need_list(v, "https://www.instagram.com/reel/xyz/", "연예인형"))   # 유튜브 소재만 시험


def test_gate_uses_whisper_when_speechmatics_missing(monkeypatch):
    """11-02: 스피치매틱스가 없어도 위스퍼로 판정한다 — 미측정 ×로 완성이 막히지 않게."""
    from tools.calcopy.hybrid import quality_gate as QG
    from tools.calcopy.engine import narr_verify as NV

    def no_key(voice):
        raise RuntimeError("키 없음")
    monkeypatch.setattr(NV, "heard_words", no_key)
    words, src = QG.narr_words("v.wav", lambda: [(1.0, 1.5, "안녕")])
    assert words == [{"s": 1.0, "e": 1.5, "w": "안녕"}] and "위스퍼" in src
    monkeypatch.setattr(NV, "heard_words", lambda voice: [{"s": 2.0, "e": 2.5, "w": "네"}])
    words, src = QG.narr_words("v.wav", lambda: pytest.fail("키가 있으면 위스퍼를 부르지 않는다"))
    assert words[0]["w"] == "네" and "스피치매틱스" in src


def test_gate_fail_finishes_with_notice():
    """11-02 "권고사항": 고칠 한도를 다 쓴 자동 관문 ×는 멈춤이 아니라 알림과 함께 완성이다. 검사를 안 돈 편은 여전히 못 낸다."""
    st = {"version": "v", "log": [], "tries": {"look": F.LIMITS["look"]},
          "auto": {"ok": False, "rows": [{"what": "B14 효과음 과다", "ok": False}]}, "look": {"ok": False, "problems": ["1단 자동 관문 미통과 — 눈 검수 생략"], "skipped": True}}
    assert F.ph_check_judge(st, {}, {}, {}) == {"goto": "deliver"}
    assert st["look_left"] == ["B14 효과음 과다"] and "B14 효과음 과다" in st["notice"]
    assert F.finish_passed(st)
    assert not F.finish_passed({"auto": {"ok": False}, "look": {"ok": False}})
