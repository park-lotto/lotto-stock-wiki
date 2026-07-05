from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "yt_agents"))
import quote_extractor as qe
import json
import subprocess
import pytest

FIX = Path(__file__).parent / "fixtures"

def test_parse_vtt_basic():
    segs = qe.parse_vtt((FIX / "sample.ko.vtt").read_text(encoding="utf-8"))
    assert len(segs) == 2
    assert segs[0].start == 12.0
    assert segs[0].text == "HBM 공급부족은 최소 내년까지 갑니다"
    assert segs[1].start == 220.5
    assert segs[1].text == "밸류 부담은 분명히 있습니다"   # 태그 제거됨

def test_to_mmss():
    assert qe.to_mmss(73.4) == "01:13"
    assert qe.to_mmss(220.5) == "03:40"

def test_parse_heatmap_present():
    info = json.loads((FIX / "info_with_heatmap.json").read_text(encoding="utf-8"))
    hm = qe.parse_heatmap(info)
    assert len(hm) == 2
    assert hm[1]["start"] == 200.0 and hm[1]["value"] == 0.95

def test_parse_heatmap_absent():
    assert qe.parse_heatmap({"title": "x"}) == []

def test_fetch_info_nonzero_returncode_raises_runtimeerror(monkeypatch):
    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "boom"

    def fake_run(*args, **kwargs):
        return FakeResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        qe.fetch_info("https://example.com/watch?v=x")

def test_fetch_info_timeout_raises_runtimeerror(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["python", "-m", "yt_dlp"], timeout=90)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        qe.fetch_info("https://example.com/watch?v=x")

def test_fetch_info_malformed_json_raises_runtimeerror(monkeypatch):
    class FakeResult:
        returncode = 0
        stdout = "not json{{{"
        stderr = ""

    def fake_run(*args, **kwargs):
        return FakeResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        qe.fetch_info("https://example.com/watch?v=x")

def test_transcript_cmd_builder():
    # 내부 커맨드 빌더가 python -m yt_dlp + auto-sub + lang 을 쓰는지
    cmd = qe._transcript_cmd("https://youtu.be/x", "ko", "/tmp/wd")
    assert cmd[:3] == ["python", "-m", "yt_dlp"]
    assert "--write-auto-sub" in cmd
    assert "ko" in cmd

def test_get_transcript_timeout_raises_transcriptunavailable(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["python", "-m", "yt_dlp"], timeout=120)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(qe.TranscriptUnavailable):
        qe.get_transcript("https://example.com/watch?v=x", workdir=str(tmp_path))


def test_parse_score_reply_filters_golden():
    reply = json.loads((FIX / "gemini_score_reply.json").read_text(encoding="utf-8"))
    cands = qe.parse_score_reply(reply, source="채널/URL")
    assert len(cands) == 2                      # golden=false 1개 제외
    c0 = cands[0]
    assert c0.stance == "강세" and c0.evidence == "수급"
    assert c0.score >= 4                         # 필수3(3) + 구체성 가점(1)
    assert cands[1].score == 3                   # 필수3만, 구체성 없음


def test_build_score_prompt_has_rubric():
    p = qe.build_score_prompt("반도체 고점인가", [qe.Segment(12.0, "HBM 부족")])
    assert "필수" in p and "강세" in p and "12" in p


def test_chunk_segments_splits_on_max_chars():
    segs = [qe.Segment(0.0, "1234567890"),   # 10 chars
            qe.Segment(1.0, "1234567890"),   # 10 chars -> cumulative 20, still <= 20
            qe.Segment(2.0, "1234567890")]   # would push to 30 -> new chunk
    chunks = qe.chunk_segments(segs, max_chars=20)
    assert len(chunks) == 2
    assert len(chunks[0]) == 2
    assert len(chunks[1]) == 1
    assert chunks[1][0].text == "1234567890" and chunks[1][0].start == 2.0


def test_chunk_segments_empty_input():
    assert qe.chunk_segments([], max_chars=20) == []


def test_chunk_segments_single_segment_exceeds_max_chars():
    # 한 세그먼트가 max_chars보다 길어도 쪼개지 않고 그 자체로 한 청크
    segs = [qe.Segment(0.0, "x" * 50)]
    chunks = qe.chunk_segments(segs, max_chars=20)
    assert len(chunks) == 1
    assert len(chunks[0]) == 1
    assert chunks[0][0].text == "x" * 50


def test_score_quotes_skips_failed_chunk_and_concats(monkeypatch):
    import gemini_client

    # 세그먼트 2개, 각 20자 -> max_chars=20이면 청크가 2개로 쪼개짐 (세그먼트별 1청크)
    segs = [qe.Segment(0.0, "a" * 20), qe.Segment(5.0, "b" * 20)]
    chunks = qe.chunk_segments(segs, max_chars=20)
    assert len(chunks) == 2   # 사전 검증: 실제로 2청크로 쪼개지는지 확인

    calls = {"n": 0}

    def fake(prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"quotes": [{
                "ts": 12.0, "text": "HBM 공급부족 내년까지", "golden": True,
                "stance": "강세", "evidence": "수급", "specific": True,
                "reasons": ["r"],
            }]}
        raise RuntimeError("chunk boom")

    monkeypatch.setattr(gemini_client, "call_json", fake)

    result = qe.score_quotes("반도체 고점인가", segs, source="채널/URL", max_chars=20)

    assert calls["n"] == 2   # 청크 2개 모두 호출 시도됨 (실패해도 예외 전파 안 됨)
    assert isinstance(result, list)
    assert len(result) == 1
    assert all(isinstance(c, qe.QuoteCandidate) for c in result)
    assert result[0].stance == "강세"
    assert result[0].score == 4


def _c(ts, has_visual=False):
    return qe.QuoteCandidate(source="s", ts=ts, text="t", stance="강세",
                             evidence="수급", score=3, has_visual=has_visual)


def test_apply_heatmap_sets_heat():
    cands = [_c(210.0), _c(5.0)]
    hm = [{"start":0.0,"end":30.0,"value":0.2},{"start":200.0,"end":230.0,"value":0.95}]
    qe.apply_heatmap(cands, hm)
    assert cands[0].heat == 0.95
    assert cands[1].heat == 0.2


def test_assign_tiers_priority():
    c_vis = _c(210.0, has_visual=True); c_vis.heat = 0.95
    c_hot = _c(210.0); c_hot.heat = 0.9
    c_plain = _c(5.0); c_plain.heat = 0.1
    qe.assign_tiers([c_vis, c_hot, c_plain])
    assert c_vis.tier == 1     # 자료구동 최우선(heat 높아도)
    assert c_hot.tier == 2     # 스파이크
    assert c_plain.tier == 3   # 루브릭만


def test_capture_cmd_seeks_before_input():
    cmd = qe._capture_cmd("http://stream", 210.0, "/tmp/f.png")
    assert cmd[0] == "ffmpeg"
    i_ss = cmd.index("-ss"); i_i = cmd.index("-i")
    assert i_ss < i_i                      # 빠른 seek: -ss 가 -i 앞
    assert "210.0" in cmd and "/tmp/f.png" in cmd
    assert "-frames:v" in cmd


def test_stream_url_timeout_raises_runtimeerror(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["python", "-m", "yt_dlp", "-g"], timeout=90)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        qe._stream_url("https://example.com/watch?v=x")


def test_capture_frame_timeout_raises_runtimeerror(monkeypatch, tmp_path):
    monkeypatch.setattr(qe, "_stream_url", lambda url: "http://stream")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=90)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        qe.capture_frame("https://example.com/watch?v=x", 60.0,
                          str(tmp_path / "f.png"))


def test_candidate_to_dict_shape():
    c = qe.QuoteCandidate(source="채널/URL", ts=220.5, text="밸류 부담",
                          stance="약세", evidence="밸류", score=3,
                          has_visual=True, heat=0.9, tier=1)
    d = qe.candidate_to_dict(c)
    assert d["ts"] == "03:40" and d["ts_sec"] == 220.5
    assert d["tier"] == 1 and d["has_visual"] is True
    assert d["stance"] == "약세" and d["source"] == "채널/URL"
