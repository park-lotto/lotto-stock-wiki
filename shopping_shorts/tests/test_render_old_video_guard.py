"""렌더 중에 '옛 완성본'이 다운로드되던 것(2026-09-02 고객 박세현 실사고).

제보: "최종 렌더를 눌러서 다운받고, 다시 재생하니 영상이 달라진 거예요. 전후 영상 다
다운돼 있어요." — 렌더를 다시 걸어도 video_path가 이전 파일을 가리켰고 파일도 새 렌더가
끝날 때까지 옛 내용이라, 그 사이 받은 사람은 옛 영상을 받았다.

처방 두 겹: ①렌더 시작 때 video_path를 비운다(화면에서 완성본이 사라진다)
           ②만드는 중이면 /api/mix/video가 409로 막는다(주소를 기억한 브라우저 대비).
"""
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


def _src():
    return APP.read_text(encoding="utf-8")


def test_렌더_시작하면_옛_완성본_경로를_비운다():
    s = _src()
    i = s.index('store.update_mix_job(job_id, status="rendering", error=None')
    line = s[i:s.index("\n", i)]
    assert 'video_path=""' in line, "렌더 시작 시 video_path를 비워야 옛 영상이 안 나간다"


def test_만드는_중이면_완성본을_안_준다():
    s = _src()
    i = s.index("def api_mix_video(")
    head = s[i:i + 1200]
    assert '"rendering", "removing_subtitles"' in head
    assert "409" in head, "만드는 중이면 409로 막아야 한다(옛 파일 제공 금지)"
    # 막는 검사가 파일 존재 검사보다 **앞**이어야 한다 — 뒤면 옛 파일이 먼저 나간다.
    assert head.index('"rendering", "removing_subtitles"') < head.index('Path(job["video_path"]).exists()')


def test_안내문구는_사람말이다():
    s = _src()
    i = s.index("def api_mix_video(")
    assert "만드는 중이에요" in s[i:i + 1200]


# ── 미리보기 낡음 표시 ──────────────────────────────────────────────────────
def test_지문은_한_곳에서_만들고_비교만_한다():
    """만들 때와 비교할 때가 어긋나면 경고가 영영 안 뜨거나 늘 뜬다(0순위-B)."""
    from shopping_shorts import mix_pipeline
    a = mix_pipeline.plan_signature({"beats": [{"narration": "가", "seg_ids": [1], "seconds": 3}]})
    b = mix_pipeline.plan_signature({"beats": [{"narration": "가", "seg_ids": [1], "seconds": 3.0}]})
    c = mix_pipeline.plan_signature({"beats": [{"narration": "나", "seg_ids": [1], "seconds": 3}]})
    assert a == b, "같은 편성이면 같은 지문"
    assert a != c, "문장이 바뀌면 다른 지문"
    d = mix_pipeline.plan_signature({"beats": [{"narration": "가", "seg_ids": [2], "seconds": 3}]})
    assert a != d, "컷이 바뀌면 다른 지문"


def test_지문이_없으면_낡았다고_말하지_않는다(tmp_path, monkeypatch):
    """옛 작업엔 지문 파일이 없다 — 모르면 경고를 붙이지 않는다."""
    from shopping_shorts import app as A
    monkeypatch.setattr(A, "_MIX_WORK_DIR", str(tmp_path))
    assert A._preview_is_stale({"job_id": "x", "preview_status": "ready", "edit_plan": {}}) is False


def test_편성이_바뀌면_낡았다고_말한다(tmp_path, monkeypatch):
    from shopping_shorts import app as A
    from shopping_shorts import mix_pipeline
    monkeypatch.setattr(A, "_MIX_WORK_DIR", str(tmp_path))
    (tmp_path / "x").mkdir()
    plan_old = {"beats": [{"narration": "옛 문장", "seg_ids": [1], "seconds": 3}]}
    (tmp_path / "x" / "preview.sig").write_text(mix_pipeline.plan_signature(plan_old), encoding="utf-8")
    job = {"job_id": "x", "preview_status": "ready", "edit_plan": plan_old}
    assert A._preview_is_stale(job) is False
    job["edit_plan"] = {"beats": [{"narration": "새 문장", "seg_ids": [1], "seconds": 3}]}
    assert A._preview_is_stale(job) is True
