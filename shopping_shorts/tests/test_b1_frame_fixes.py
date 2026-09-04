# -*- coding: utf-8 -*-
"""B1 프레임 태깅 수리 (2026-09-04) — 조용한 버그 3개의 재발 방지.

실측(로컬 4편, docs/superpowers/specs/2026-09-04-3단계매칭-파서재설계-design.md §9-5):
  ① 프레임 파일명이 없어 전부 덮어써 모든 컷이 마지막 프레임 한 장으로 태깅됐다
  ② _default_boundaries가 detect_cuts의 (start_frame, end_frame) 튜플을 초로 캐스팅하다 예외를
     삼켜 항상 구간 1개였다
  ③ response_schema(enum) 강제 호출이 gemini-3.5-flash에서 120초를 넘겨 태깅·판정이 죽었다
가드는 **옛 버그를 되살리면 빨개져야** 가드다 — 아래 각 테스트는 옛 동작이면 실패하게 짰다."""
import pytest

from shopping_shorts import frame_script as fs


# ── ① 프레임 파일명 ───────────────────────────────────────────────────────
def test_컷마다_프레임_파일명이_전부_다르다():
    names = []

    def fake_frame_at(path, dest, ts, filename=None):
        names.append(filename)
        return f"{dest}/{filename}"

    fs.extract_script_frames(
        "v.mp4", "s1", _no_classic=True,
        get_boundaries=lambda p: [0.0, 3.0, 6.0, 9.0],
        extract_frame_at=fake_frame_at, extract_audio=lambda v, o: None,
        transcribe_words=lambda m: None,
        tag_frames=lambda groups, c, s, b=None: [{"scene_desc": "x", "shot_role": "완성"}] * len(s))
    assert names and all(names), "파일명 없이 부르면 기본값(frame_hint.jpg)에 덮어쓴다"
    assert len(set(names)) == len(names), f"중복 파일명: {names}"
    assert len(names) == 3 * fs.FRAMES_PER_CUT


def test_태깅에는_구간별_묶음으로_넘긴다():
    got = {}

    def fake_tag(groups, caption, segs, brief=None):
        got["groups"] = groups
        got["brief"] = brief
        return [{"scene_desc": "a", "shot_role": "완성"}] * len(segs)

    fs.extract_script_frames(
        "v.mp4", "s1", _no_classic=True,
        get_boundaries=lambda p: [0.0, 3.0, 6.0],
        extract_frame_at=lambda p, d, t, f=None: f"{d}/{f}",
        extract_audio=lambda v, o: None, transcribe_words=lambda m: None, tag_frames=fake_tag)
    groups = got["groups"]
    assert len(groups) == 2 and all(isinstance(g, list) for g in groups)
    # 가짜 경로라 띠를 못 만든다 → 중간 한 장으로 폴백. 어느 쪽이든 **구간당 이미지 1장**이다.
    assert all(len(g) == 1 for g in groups)


def test_frame_times_는_시작중간끝이고_짧은_구간은_한_장():
    ts = fs.frame_times(10.0, 13.0, 3)
    assert len(ts) == 3 and ts[0] > 10.0 and ts[-1] < 13.0 and abs(ts[1] - 11.5) < 1e-6
    assert fs.frame_times(10.0, 10.3, 3) == [10.15]


def test_구간의_프레임들은_띠_한_장으로_합쳐져_구간당_이미지_1장이_된다(tmp_path):
    """★2026-09-04 2차 실측: 이미지 2~3장을 따로 실으면 모델이 1장=1구간으로 세어 묘사가 2배 압축돼
    밀렸다(s3 재료표 12.73초 → 37.23초 칸). 띠로 합치면 이미지 수 = 구간 수라 못 어긋난다."""
    from PIL import Image

    def real_frame_at(path, dest, ts, filename=None):
        p = tmp_path / filename
        Image.new("RGB", (64, 36), (int(ts * 10) % 255, 0, 0)).save(p)
        return str(p)

    got = {}

    def fake_tag(groups, caption, segs, brief=None):
        got["groups"] = groups
        got["brief"] = brief
        return [{"scene_desc": "a", "shot_role": "완성"}] * len(segs)

    briefs = []

    def fake_brief(grid, caption, transcript):
        briefs.append(grid)
        return {"product": "쿠키", "flow": "0~3초 반죽 → 3~6초 완성", "confidence": "높음"}

    out = fs.extract_script_frames(
        "v.mp4", "s1", _no_classic=True,
        get_boundaries=lambda p: [0.0, 3.0, 6.0],
        extract_frame_at=real_frame_at, extract_audio=lambda v, o: None,
        transcribe_words=lambda m: None, tag_frames=fake_tag, story_brief=fake_brief)
    groups = got["groups"]
    assert len(groups) == 2 and all(len(g) == 1 for g in groups)
    strip = Image.open(groups[0][0])
    assert strip.height == fs.STRIP_HEIGHT
    assert strip.width > fs.STRIP_HEIGHT * 64 / 36 * 2, "띠 폭이 프레임 3장 합보다 작다 — 안 합쳐졌다"
    # ★1차 브리프: 격자 한 장이 만들어져 브리프 함수에 갔고, 그 결과가 2차 태깅과 반환값에 실린다
    assert briefs and briefs[0] and Image.open(briefs[0]).height == fs.GRID_HEIGHT
    assert got["brief"]["product"] == "쿠키"
    assert out["source_brief"]["flow"].startswith("0~3초")


def test_brief_block_은_불명이면_보수_지시를_붙이고_비면_빈문자열():
    assert fs.brief_block({}) == ""
    b = fs.brief_block({"product": "방충망 청소 도구", "flow": "0~4초 문제 → 4~15초 사용", "confidence": "불명"})
    assert "방충망 청소 도구" in b and "0~4초 문제" in b and "지어내지 마라" in b
    assert "지어내지 마라" not in fs.brief_block({"product": "x", "confidence": "높음"})


def test_태깅_프롬프트에_브리프와_공용_필드정의가_들어간다(monkeypatch, tmp_path):
    from shopping_shorts import comment_gen, script_extract
    seen = {}

    class _M:
        def generate_content(self, model, contents, config):
            seen["prompt"] = contents[0]
            return _FakeResp('{"tags": [{"seg_no": 1, "scene_desc": "a", "shot_role": "완성", '
                             '"label": "완성품 클로즈업", "use_point": "마무리 대목에", "change": "매끈해졌다", '
                             '"action": "없음", "has_effect": true}]}')

    class _C:
        models = _M()

    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _C())
    f = tmp_path / "a.jpg"; f.write_bytes(b"\xff\xd8x")
    tags = fs._gemini_tag_frames([[str(f)]], "", [{"start": 0, "end": 1, "text": ""}],
                                 brief={"product": "방충망 청소 도구", "flow": "0~4초 문제"})
    p = seen["prompt"]
    assert "방충망 청소 도구" in p and "0~4초 문제" in p
    # 필드 정의는 script_extract 한 곳의 문장 그대로다(복사본이면 갈라진다)
    assert "- use_point:" in script_extract._SEG_FIELD_GUIDE and "- use_point:" in p
    assert "- label:" in p and "- change:" in p and "has_effect" in p
    assert tags[0]["label"] == "완성품 클로즈업" and tags[0]["change"] == "매끈해졌다" and tags[0]["has_effect"] is True
    # merge → _assign_seg_ids를 지나면 통째 업로드 추출과 같은 정규화가 걸린다
    merged = fs.merge_frame_tags([{"start": 0, "end": 1, "text": ""}], tags)
    segs = script_extract._assign_seg_ids("v", merged)
    assert segs[0]["label"] == "완성품 클로즈업" and segs[0]["use_point"] == "마무리 대목에"
    assert segs[0]["change"] == "매끈해졌다" and segs[0]["has_effect"] is True and segs[0]["action"] is None


def test_make_strip_은_한_장이면_None():
    assert fs.make_strip(["only.jpg"], "out.jpg") is None
    assert fs.make_strip([], "out.jpg") is None


# ── ② 경계 ────────────────────────────────────────────────────────────────
def test_경계는_프레임번호쌍을_초로_바꾼다(monkeypatch):
    from shopping_shorts import scene_cut, frame_extract
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 3.0)
    monkeypatch.setattr(scene_cut, "video_fps", lambda p: 30.0)
    monkeypatch.setattr(scene_cut, "detect_cuts", lambda p, threshold=0.3: [(0, 30), (30, 90)])
    assert fs._default_boundaries("v.mp4") == [0.0, 1.0, 3.0], \
        "옛 코드는 float((0,30))가 TypeError → 삼켜서 [0, 3] 구간 1개였다"


def test_경계는_옛_초_형식도_받는다(monkeypatch):
    from shopping_shorts import scene_cut, frame_extract
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 5.0)
    monkeypatch.setattr(scene_cut, "detect_cuts", lambda p, threshold=0.3: [1.5, 4.0])
    assert fs._default_boundaries("v.mp4") == [0.0, 1.5, 4.0, 5.0]


def test_긴_구간은_상한으로_쪼갠다():
    out = fs.split_long_spans([0.0, 51.0, 75.0], max_span=7.0)
    assert out[0] == 0.0 and out[-1] == 75.0 and 51.0 in out
    assert all(b - a <= 7.0 + 1e-6 for a, b in zip(out, out[1:]))
    # 컷이 촘촘하면 손대지 않는다
    assert fs.split_long_spans([0.0, 2.0, 5.0], max_span=7.0) == [0.0, 2.0, 5.0]


def test_원테이크는_기본_경계에서도_쪼개진다(monkeypatch):
    from shopping_shorts import scene_cut, frame_extract
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 51.0)
    monkeypatch.setattr(scene_cut, "detect_cuts", lambda p, threshold=0.3: [])
    out = fs._default_boundaries("v.mp4")
    assert len(out) > 2 and all(b - a <= fs.MAX_SPAN_SEC + 1e-6 for a, b in zip(out, out[1:]))


# ── ③ 스키마 없는 호출 + 코드 검증 ────────────────────────────────────────
class _FakeResp:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, log):
        self.log = log

    def generate_content(self, model, contents, config):
        self.log.append({"model": model, "config": config})
        return _FakeResp('{"tags": [{"seg_no": 2, "scene_desc": "완성", "shot_role": "완성"},'
                         ' {"seg_no": 1, "scene_desc": "붓기", "shot_role": "이상한값"}]}')


class _FakeClient:
    def __init__(self, log):
        self.models = _FakeModels(log)


def test_태깅_호출은_스키마를_강제하지_않고_값은_코드가_검증한다(monkeypatch, tmp_path):
    from shopping_shorts import comment_gen
    calls = []
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _FakeClient(calls))
    f1 = tmp_path / "a.jpg"; f1.write_bytes(b"\xff\xd8x")
    f2 = tmp_path / "b.jpg"; f2.write_bytes(b"\xff\xd8y")
    segs = [{"start": 0, "end": 1, "text": ""}, {"start": 1, "end": 2, "text": ""}]
    tags = fs._gemini_tag_frames([[str(f1)], [str(f2)]], "", segs)
    assert calls, "모델을 부르지 않았다"
    assert getattr(calls[0]["config"], "response_schema", None) is None, \
        "스키마 강제 호출은 3.5-flash에서 120초 초과로 죽는다(2026-09-04 실측)"
    assert calls[0]["model"] == fs.TAG_MODELS[0]
    # seg_no로 자리를 맞추고, 모르는 shot_role은 '기타'로 떨어진다
    assert tags[0]["scene_desc"] == "붓기" and tags[0]["shot_role"] == "기타"
    assert tags[1]["scene_desc"] == "완성" and tags[1]["shot_role"] == "완성"


def test_normalize_tags_는_번호없으면_순서대로_채운다():
    out = fs.normalize_tags([{"scene_desc": "a", "shot_role": "완성"},
                             "쓰레기",
                             {"scene_desc": "b", "shot_role": "사용중", "product_benefits": "좋다"}], 3)
    assert [t.get("scene_desc") for t in out] == ["a", "b", None]
    assert out[1]["product_benefits"] == ["좋다"]


def test_판정기도_스키마를_강제하지_않는다(monkeypatch, tmp_path):
    from shopping_shorts import comment_gen, tag_qa_frames
    calls = []

    class _M:
        def generate_content(self, model, contents, config):
            calls.append(config)
            return _FakeResp('{"verdicts": [{"image_no": 1, "verdict": "맞음"}]}')

    class _C:
        models = _M()

    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _C())
    f = tmp_path / "a.jpg"; f.write_bytes(b"\xff\xd8x")
    v = tag_qa_frames._judge([str(f)], [(0, {"scene_desc": "x"})])
    assert v == [{"image_no": 1, "verdict": "맞음"}]
    assert getattr(calls[0], "response_schema", None) is None


def test_판정기는_첫_모델이_죽으면_다음_모델로(monkeypatch, tmp_path):
    from shopping_shorts import comment_gen, tag_qa_frames
    seen = []

    class _M:
        def generate_content(self, model, contents, config):
            seen.append(model)
            if len(seen) == 1:
                raise RuntimeError("504 DEADLINE_EXCEEDED")
            return _FakeResp('{"verdicts": [{"image_no": 1, "verdict": "부분"}]}')

    class _C:
        models = _M()

    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _C())
    f = tmp_path / "a.jpg"; f.write_bytes(b"\xff\xd8x")
    v = tag_qa_frames._judge([str(f)], [(0, {"scene_desc": "x"})])
    assert seen == list(fs.TAG_MODELS[:2]) and v[0]["verdict"] == "부분"


# ── 2차: 배치 호출·관대한 JSON·격자 시각 ───────────────────────────────────
def test_loads_lenient_는_뒤에_붙은_쓰레기와_코드펜스를_견딘다():
    assert fs.loads_lenient('{"tags": [1]}\n\n설명 몇 줄') == {"tags": [1]}
    assert fs.loads_lenient('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError):
        fs.loads_lenient("")


def test_태깅은_TAG_BATCH_구간씩_나눠_부르고_자리를_전체_기준으로_되돌린다(monkeypatch, tmp_path):
    from shopping_shorts import comment_gen
    calls = []

    class _M:
        def generate_content(self, model, contents, config):
            n_img = len(contents) - 1
            calls.append(n_img)
            tags = [{"seg_no": k + 1, "scene_desc": f"batch{len(calls)}-{k+1}", "shot_role": "완성"}
                    for k in range(n_img)]
            return _FakeResp('{"tags": ' + __import__("json").dumps(tags, ensure_ascii=False) + '}')

    class _C:
        models = _M()

    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _C())
    n = fs.TAG_BATCH * 2 + 3
    groups = []
    for i in range(n):
        f = tmp_path / f"{i}.jpg"; f.write_bytes(b"\xff\xd8x")
        groups.append([str(f)])
    segs = [{"start": i, "end": i + 1, "text": ""} for i in range(n)]
    tags = fs._gemini_tag_frames(groups, "", segs)
    assert calls == [fs.TAG_BATCH, fs.TAG_BATCH, 3], "한 호출에 TAG_BATCH장씩"
    assert len(tags) == n
    assert tags[0]["scene_desc"] == "batch1-1"
    assert tags[fs.TAG_BATCH]["scene_desc"] == "batch2-1", "두 번째 묶음의 1번이 전체 13번 자리에"
    assert tags[-1]["scene_desc"] == "batch3-3"


def test_격자에는_컷_시각이_찍힌다(tmp_path):
    from PIL import Image
    paths = []
    for i in range(3):
        p = tmp_path / f"m{i}.jpg"
        Image.new("RGB", (64, 36), (200, 200, 200)).save(p)
        paths.append(str(p))
    out = fs.make_grid(paths, str(tmp_path / "grid.jpg"), times=[0.5, 12.7, 30.0])
    assert out
    g = Image.open(out)
    assert g.height == fs.GRID_HEIGHT
    # 시각 라벨(검정 상자)이 첫 칸 왼쪽 위에 찍혀 원래 회색이 아니다
    assert g.getpixel((2, 2)) != (200, 200, 200)
