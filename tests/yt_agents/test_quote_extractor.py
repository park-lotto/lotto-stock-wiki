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
