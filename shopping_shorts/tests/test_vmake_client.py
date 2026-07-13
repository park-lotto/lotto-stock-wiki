"""vmake_client (공식 SDK 래퍼) 오케스트레이션 테스트.

실제 서명/OSS/폴링은 번들 vmake_sdk가 담당하므로, 여기서는 래퍼가 SkillClient를
올바른 태스크명·파라미터로 호출하고 결과 URL을 내려받는지, 실패를 raise하는지 검증한다.
"""
import pytest

from shopping_shorts import vmake_client as vc


def test_split_key_colon():
    assert vc._split_key("appkey:secret") == ("appkey", "secret")


def test_split_key_no_colon():
    assert vc._split_key("solokey") == ("solokey", "solokey")


def test_split_key_strips():
    assert vc._split_key(" app : sec ") == ("app", "sec")


class _FakeClient:
    def __init__(self, result):
        self._result = result
        self.calls = []

    def run_task(self, task_name, image_path, params=None):
        self.calls.append({"task_name": task_name, "image_path": image_path, "params": params})
        return self._result


def test_remove_subtitles_success(tmp_path, monkeypatch):
    fake = _FakeClient({"output_urls": ["http://x/clean.mp4"]})
    monkeypatch.setattr(vc, "_client", lambda ak, sk: fake)
    dl = {}

    def fake_dl(url, dest):
        dl["url"] = url
        open(dest, "wb").write(b"clean")
        return str(dest)

    monkeypatch.setattr(vc, "_download", fake_dl)

    out = tmp_path / "clean.mp4"
    result = vc.remove_subtitles(str(tmp_path / "in.mp4"), "appkey:secret", out_path=str(out))

    assert result == str(out)
    assert dl["url"] == "http://x/clean.mp4"
    assert out.read_bytes() == b"clean"
    # 올바른 비디오 태스크명·파라미터로 호출됐는지
    assert fake.calls[0]["task_name"] == "videoscreenclear"
    assert fake.calls[0]["params"] == {"parameter": {"rsp_media_type": "url"}}
    assert fake.calls[0]["image_path"] == str(tmp_path / "in.mp4")


def test_remove_subtitles_no_key_raises(tmp_path):
    with pytest.raises(ValueError, match="API 키"):
        vc.remove_subtitles(str(tmp_path / "in.mp4"), "", out_path=str(tmp_path / "o.mp4"))


def test_remove_subtitles_failure_result_raises(tmp_path, monkeypatch):
    fake = _FakeClient({"error": "task_failed", "detail": "quota exhausted", "skill_status": "failed"})
    monkeypatch.setattr(vc, "_client", lambda ak, sk: fake)
    with pytest.raises(RuntimeError, match="quota exhausted"):
        vc.remove_subtitles(str(tmp_path / "in.mp4"), "k:s", out_path=str(tmp_path / "o.mp4"))


def test_remove_subtitles_empty_urls_raises(tmp_path, monkeypatch):
    fake = _FakeClient({"output_urls": []})
    monkeypatch.setattr(vc, "_client", lambda ak, sk: fake)
    with pytest.raises(RuntimeError, match="비었"):
        vc.remove_subtitles(str(tmp_path / "in.mp4"), "k:s", out_path=str(tmp_path / "o.mp4"))
