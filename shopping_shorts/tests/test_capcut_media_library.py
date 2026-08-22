"""캡컷 **미디어 보관함**(draft_meta_info.json의 draft_materials) 검증.

## 왜 (2026-08-23 사장님)

> "복잡하니까 원본 그대로 올려주고, 라이브러리 그쪽에 조각 영상들 불러올 수 있게 되나"

타임라인 구조는 그대로 두고, **장면 조각을 캡컷 보관함에 넣어** 끌어다 갈아끼울 수
있게 한다. 자막·TTS는 트랙이 따로라 갈아끼워도 그대로 남는다.

## 형식 근거 — 추측 아님

실제 캡컷 프로젝트를 열어 실측했다(2026-08-23):
`%LOCALAPPDATA%/CapCut/User Data/Projects/com.lveditor.draft/0618/draft_meta_info.json`

  draft_materials = [{"type": 0, "value": [영상항목...]}, {"type": 1, "value": []}, ...]
  영상항목 = {id, type:0, metetype:"video", file_Path, extra_info, duration(μs),
             width, height, roughcut_time_range, sub_time_range, item_source, ...}
"""
from shopping_shorts import capcut_draft as cd


def _entries(meta):
    """draft_materials에서 type=0(영상·이미지) 목록만 꺼낸다."""
    for grp in meta.get("draft_materials") or []:
        if grp.get("type") == 0:
            return grp.get("value") or []
    return []


def test_보관함_그룹이_실제_캡컷과_같은_모양이다():
    """type 0~6 그룹이 다 있어야 캡컷이 읽는다(빈 그룹도 있어야 한다)."""
    meta = cd.build_meta("p", "C:/cap/p", 1_000_000)
    groups = meta.get("draft_materials")
    assert isinstance(groups, list) and groups, "draft_materials가 비었다"
    types = [g.get("type") for g in groups]
    assert types == sorted(types), "type 순서가 뒤죽박죽"
    assert 0 in types, "영상 그룹(type=0)이 없다"


def test_조각을_주면_보관함에_등록된다():
    media = [{"path": "C:/cap/p/cut_00_훅.mp4", "name": "cut_00_훅.mp4",
              "dur": 2.0, "w": 1080, "h": 1920}]
    meta = cd.build_meta("p", "C:/cap/p", 2_000_000, media=media)
    ent = _entries(meta)
    assert len(ent) == 1
    e = ent[0]
    assert e["file_Path"] == "C:/cap/p/cut_00_훅.mp4"
    assert e["extra_info"] == "cut_00_훅.mp4"      # 보관함에 보이는 이름
    assert e["metetype"] == "video"
    assert e["duration"] == 2_000_000              # 마이크로초
    assert e["width"] == 1080 and e["height"] == 1920


def test_항목마다_필수키가_다_있다():
    """캡컷이 읽다 죽지 않게 실측 항목의 키를 전부 채운다."""
    media = [{"path": "C:/cap/p/a.mp4", "name": "a.mp4", "dur": 1.0}]
    e = _entries(cd.build_meta("p", "C:/cap/p", 1_000_000, media=media))[0]
    for k in ("id", "type", "metetype", "file_Path", "extra_info", "duration",
              "width", "height", "roughcut_time_range", "sub_time_range",
              "item_source", "create_time", "import_time", "import_time_ms",
              "ai_group_type", "md5", "enter_from"):
        assert k in e, f"필수 키 없음: {k}"
    assert e["roughcut_time_range"] == {"start": 0, "duration": 1_000_000}
    assert e["sub_time_range"] == {"start": -1, "duration": -1}


def test_음성은_metetype이_music이다():
    """mp3를 video로 넣으면 캡컷이 잘못 읽는다. 확장자로 가른다."""
    media = [{"path": "C:/cap/p/beat_00.mp3", "name": "beat_00.mp3", "dur": 1.0}]
    e = _entries(cd.build_meta("p", "C:/cap/p", 1_000_000, media=media))[0]
    assert e["metetype"] == "music"


def test_id는_항목마다_다르다():
    """같은 id면 캡컷이 하나만 인식한다."""
    media = [{"path": f"C:/cap/p/c{i}.mp4", "name": f"c{i}.mp4", "dur": 1.0}
             for i in range(5)]
    ids = [e["id"] for e in _entries(cd.build_meta("p", "C:/cap/p", 1_000_000, media=media))]
    assert len(set(ids)) == 5


def test_media를_안_주면_예전과_같다():
    """회귀 0 — 기존 호출부(인자 없음)는 빈 보관함 그대로."""
    assert _entries(cd.build_meta("p", "C:/cap/p", 1_000_000)) == []


# ── 타임라인: 화면 조각이 **전부** 올라가는가 ────────────────────────────────
# 실사고(2026-08-23): 비트에 화면이 여러 개인데 primary 하나만 올려서 화면의 3분의 1만
# 나갔다(실측 19개 중 7개). 완성본과 다른 영상이 캡컷에서 열렸다.

_SRC2 = {"s0": r"C:\real\s0.mp4", "s1": r"C:\real\s1.mp4"}
_ASSET2 = {r"C:\real\s0.mp4": "C:/cap/p/s0.mp4", r"C:\real\s1.mp4": "C:/cap/p/s1.mp4",
           r"C:\real\b0.mp3": "C:/cap/p/b0.mp3"}


def _plan_multi():
    """비트 1개에 화면 3개(primary + alternates 2)."""
    return {"beats": [{
        "beat_idx": 0, "role": "훅", "narration": "세 장면짜리",
        "primary": {"video_id": "s0", "start": 0.0, "end": 2.0},
        "alternates": [{"video_id": "s1", "start": 0.0, "end": 2.0},
                       {"video_id": "s0", "start": 5.0, "end": 7.0}]}]}


def test_비트의_화면조각이_전부_타임라인에_올라간다():
    draft, _ = cd.build_draft(
        plan=_plan_multi(),
        timeline=[{"beat_idx": 0, "t0": 0.0, "dur": 6.0, "narration": "세 장면짜리", "role": "훅"}],
        source_video_paths=_SRC2, tts_paths={0: r"C:\real\b0.mp3"},
        asset_paths=_ASSET2, project_name="t",
        video_durs={r"C:\real\s0.mp4": 30.0, r"C:\real\s1.mp4": 30.0})
    vid = [t for t in draft["tracks"] if t["type"] == "video"][0]
    assert len(vid["segments"]) == 3, \
        f"화면 3개인데 {len(vid['segments'])}개만 올라갔다 — primary만 보고 있다"


def test_조각들이_시간을_나눠_갖고_겹치지_않는다():
    """합이 비트 길이와 같고, 앞 조각 끝 == 뒤 조각 시작(빈틈·겹침 0)."""
    draft, _ = cd.build_draft(
        plan=_plan_multi(),
        timeline=[{"beat_idx": 0, "t0": 0.0, "dur": 6.0, "narration": "세 장면짜리", "role": "훅"}],
        source_video_paths=_SRC2, tts_paths={0: r"C:\real\b0.mp3"},
        asset_paths=_ASSET2, project_name="t",
        video_durs={r"C:\real\s0.mp4": 30.0, r"C:\real\s1.mp4": 30.0})
    segs = sorted([t for t in draft["tracks"] if t["type"] == "video"][0]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    spans = [(s["target_timerange"]["start"], s["target_timerange"]["duration"]) for s in segs]
    assert spans[0][0] == 0
    for (a_st, a_du), (b_st, _b) in zip(spans, spans[1:]):
        assert a_st + a_du == b_st, f"빈틈/겹침: {a_st}+{a_du} != {b_st}"
    assert spans[-1][0] + spans[-1][1] == 6_000_000


def test_대안소스도_폴더에_복사된다(tmp_path):
    """★같은 병의 **세 번째 자리**(2026-08-23 실측으로 발견).

    `assemble_draft_folder`가 복사할 소스를 고를 때도 `primary`만 봐서, alternates가 쓰는
    소스 파일이 폴더에 안 들어갔다. 그러면 asset_paths에 없어 build_draft가 그 조각을
    **조용히 건너뛴다** — 타임라인에 화면 3개 중 2개만 올라갔다.
    """
    srcs = {}
    for i in range(2):
        f = tmp_path / f"s{i}.mp4"
        f.write_bytes(b"x")          # 존재만 하면 복사 대상이 된다
        srcs[f"s{i}"] = str(f)
    plan = {"beats": [{"beat_idx": 0, "role": "훅", "narration": "n",
                       "primary": {"video_id": "s0", "start": 0.0, "end": 2.0},
                       "alternates": [{"video_id": "s1", "start": 0.0, "end": 2.0}]}]}
    out = tmp_path / "out"
    out.mkdir()
    proj, _p, files = cd.assemble_draft_folder(
        out, "C:/cap", plan=plan,
        timeline=[{"beat_idx": 0, "t0": 0.0, "dur": 4.0, "narration": "n", "role": "훅"}],
        source_video_paths=srcs, tts_paths={}, project_name="t",
        probe=lambda p: 10.0)

    assert "src_s0.mp4" in files, "primary 소스가 없다"
    assert "src_s1.mp4" in files, "대안 소스가 복사 안 됐다 — 그 조각이 조용히 사라진다"
