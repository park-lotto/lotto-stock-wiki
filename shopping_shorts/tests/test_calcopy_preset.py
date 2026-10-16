"""프리셋 저장·재사용(tools/calcopy/engine/preset_save.py) — 왕복·manifest 필수 항목·변수 자리·변수 채우기."""
import copy
import json
from pathlib import Path

import pytest

from shopping_shorts.calcopy_frame import schema
from tools.calcopy.engine import preset_save as P

ROOT = Path(__file__).resolve().parents[2]
FRAME_A = json.loads((ROOT / "shopping_shorts/calcopy_frame/examples/frame_A_auto_ZdeZRtCeAC4.json").read_text(encoding="utf-8"))
J = {"engine": "합성", "measured_at": "2026-10-16", "unknown": ["시험"]}


def title(f):
    return next(l for l in f["layers"] if l.get("role") == "title")


def other_video(f):
    """같은 틀의 다른 편: 창·제목 자리·크기·줄 색·글자만 다르다(1_V 꼴)."""
    g = copy.deepcopy(f); g.pop("made_from", None)
    v = next(l for l in g["layers"] if l["kind"] == "video"); v["y"], v["h"] = 352, 1269
    t = title(g); t.update(y=140, size=106.8, line_h=110, line_rgb=[[0, 0, 0], [186, 0, 120]], text="다이소 기획자도 감탄한\n공간 활용 끝판왕")
    return g


def test_save_load_roundtrip_and_manifest(tmp_path):
    d = tmp_path / "sseolpulda" / "preset" / "A_흰바탕창"
    M = P.save(J, FRAME_A, d, "ZdeZRtCeAC4", "x/뜯기.json")
    pre, M2 = P.load(d)
    assert M2 == M and all(k in M2 for k in P.REQUIRED_MANIFEST)
    assert M2["slug"] == "sseolpulda" and M2["style"] == "A_흰바탕창" and M2["made_by"] == P.MADE_BY
    assert [s["id"] for s in M2["sources"]] == ["ZdeZRtCeAC4"] and M2["sources"][0]["font_confidence"] == FRAME_A["made_from"]["font_confidence"]
    assert M2["variables"] == ["layers[text:title].text"]               # 처음엔 제목 글자만 변수
    # 왕복: 변수에 원래 값을 넣으면 원래 설명서와 같다(정규화 기준)
    back = P.apply(pre, FRAME_A)
    assert schema.validate(back) == schema.validate({k: v for k, v in FRAME_A.items() if k != "made_from"})


def test_merge_marks_only_differing_places(tmp_path):
    d = tmp_path / "s" / "preset" / "A"
    P.save(J, FRAME_A, d, "ZdeZRtCeAC4", "x")
    M = P.save(J, other_video(FRAME_A), d, "1_VtwOkbbVE", "y")
    assert set(M["variables"]) == {"layers[video].y", "layers[video].h", "layers[text:title].y", "layers[text:title].size",
                                   "layers[text:title].line_h", "layers[text:title].line_rgb", "layers[text:title].text"}
    pre, _ = P.load(d)
    assert next(l for l in pre["layers"] if l.get("role") == "brand")["font"] == "TmonMonsori"   # 같은 값은 고정
    assert [s["id"] for s in M["sources"]] == ["ZdeZRtCeAC4", "1_VtwOkbbVE"]
    with pytest.raises(ValueError):
        P.save(J, FRAME_A, d, "ZdeZRtCeAC4", "x")                        # 같은 편 두 번 = 거절


def test_apply_fills_variables_and_refuses_unfilled(tmp_path):
    d = tmp_path / "s" / "preset" / "A"
    P.save(J, FRAME_A, d, "ZdeZRtCeAC4", "x")
    P.save(J, other_video(FRAME_A), d, "1_VtwOkbbVE", "y")
    pre, _ = P.load(d)
    target = other_video(FRAME_A)
    out = P.apply(pre, target)
    assert title(out)["line_rgb"] == [[0, 0, 0], [186, 0, 120]] and title(out)["text"].startswith("다이소")
    assert next(l for l in out["layers"] if l["kind"] == "video")["y"] == 352
    out2 = P.apply(pre, target, {"layers[text:title].text": "새 제목\n둘째 줄"})   # 덮어쓰기가 먼저
    assert title(out2)["text"] == "새 제목\n둘째 줄"
    with pytest.raises(ValueError) as e:
        P.apply(pre, None, {"layers[text:title].text": "x"})                # 그 편 값 없이 = 못 채운 변수 목록으로 멈춤
    assert "layers[video].y" in str(e.value)


def test_exclude_layer_is_not_compared(tmp_path):
    d = tmp_path / "s" / "preset" / "A"
    P.save(J, FRAME_A, d, "Z", "x")
    g = copy.deepcopy(FRAME_A); g.pop("made_from", None)
    next(l for l in g["layers"] if l.get("role") == "caption")["y"] = 132   # 분석기가 자막을 제목으로 잘못 읽은 편(D9)
    M = P.save(J, g, d, "7D", "y", exclude=("text:caption",))
    assert not any("caption" in v for v in M["variables"]) and M["sources"][1]["excluded_layers"] == ["text:caption"]


def _five(tmp_path):
    """같은 틀 다섯 편 — 창 y 426/340/365/352/378 · 줄색 하나만 없음(ZdeZ 꼴) — 기본값·범위 셈 확인용."""
    d = tmp_path / "s" / "preset" / "A"
    P.save(J, FRAME_A, d, "Z", "x", caption_style="창아래_검정")
    for sid, vy, col in (("h", 340, [251, 2, 82]), ("7", 365, [217, 5, 134]), ("1", 352, [186, 0, 120]), ("w", 378, [253, 1, 80])):
        g = other_video(FRAME_A)
        next(l for l in g["layers"] if l["kind"] == "video")["y"] = vy
        title(g)["line_rgb"] = [[0, 0, 0], col]
        P.save(J, g, d, sid, "y", exclude=("text:caption",), caption_style="창안_흰외곽선")
    return d


def test_variable_stats_values_default_range(tmp_path):
    d = _five(tmp_path)
    _, M = P.load(d)
    vy = M["variable_stats"]["layers[video].y"]
    assert vy["values"] == {"Z": 426, "h": 340, "7": 365, "1": 352, "w": 378}
    assert vy["default"] == 365 and vy["range"] == [340, 426]            # 중앙값·최소최대
    lr = M["variable_stats"]["layers[text:title].line_rgb"]
    assert lr["default"] == [[0, 0, 0], [234, 2, 101]] and lr["how"].startswith("자리별 중앙값(4/5")   # 같은 모양 4편의 자리별 중앙값
    assert M["variable_stats"]["layers[text:title].text"]["default"] is None   # 내용은 기본값 없음


def test_apply_defaults_for_new_material(tmp_path):
    d = _five(tmp_path)
    pre, M = P.load(d)
    with pytest.raises(ValueError) as e:
        P.apply(pre, None, None, M["variable_stats"])                     # 제목 글자 없이는 못 만든다
    assert "layers[text:title].text" in str(e.value)
    out = P.apply(pre, None, {"layers[text:title].text": "새 소재\n제목"}, M["variable_stats"])
    assert next(l for l in out["layers"] if l["kind"] == "video")["y"] == 365
    assert title(out)["line_rgb"] == [[0, 0, 0], [234, 2, 101]] and title(out)["text"] == "새 소재\n제목"


def test_caption_styles_recorded_per_source(tmp_path):
    d = _five(tmp_path)
    pre, M = P.load(d)
    st = {s["name"]: s for s in M["caption_styles"]}
    assert st["창아래_검정"]["layer"]["role"] == "caption" and st["창아래_검정"]["sources"] == ["Z"]
    assert st["창안_흰외곽선"]["layer"] is None and st["창안_흰외곽선"]["status"] == "미측정" and len(st["창안_흰외곽선"]["sources"]) == 4
    assert [s["caption_style"] for s in M["sources"]] == ["창아래_검정"] + ["창안_흰외곽선"] * 4
    with pytest.raises(ValueError):
        P.apply(pre, None, {"layers[text:title].text": "x"}, M["variable_stats"], st["창안_흰외곽선"])   # 미측정 스타일은 못 씀


def test_slug_style_for_sub_style(tmp_path):
    d = tmp_path / "channel" / "sseolpulda" / "preset" / "A_흰바탕창" / "창안_흰외곽선"
    assert P.slug_style(d) == ("sseolpulda", "A_흰바탕창/창안_흰외곽선")
    M = P.save(J, FRAME_A, d, "Z", "x")
    assert M["slug"] == "sseolpulda" and M["style"] == "A_흰바탕창/창안_흰외곽선"


def test_relation_rules_compute_dependents(tmp_path):
    """종속값은 규칙으로: 창 y = 제목 아래 끝 + gap, 창 아래 끝 = video_bottom, 제목 크기 = min(상한, 가장 긴 줄이 fill_w)."""
    d = tmp_path / "s" / "preset" / "A" / "창안"
    g1 = other_video(FRAME_A)                                           # 제목 140 + 2×110 = 360, 창 352 → gap −8, 아래 1621
    g2 = other_video(FRAME_A); t2 = title(g2)
    t2.update(y=120, size=100.0, line_h=103, text="짧은 제목\n둘째 줄")
    v2 = next(l for l in g2["layers"] if l["kind"] == "video"); v2["y"], v2["h"] = 120 + 206 - 8, 1621 - (120 + 206 - 8)
    P.save(J, g1, d, "a", "x"); M = P.save(J, g2, d, "b", "y")
    K = {k: v["default"] for k, v in M["rules"]["keys"].items()}
    assert K["gap"] == -8 and K["video_bottom"] == 1621 and K["size_cap"] == 103.4   # 크기 = 잰 크기 중앙값
    assert K["video_anchor"] == "gap_ink"                                # 제목 끝–창 간격 고정(관제 10-16)
    assert K["fill_w"] >= 1080 - P.EDGE_MARGIN                           # 폭 상한 바닥 = 화면 폭 − 48
    pre, M = P.load(d)
    out = P.apply(pre, None, {"layers[text:title].text": "아주 아주 아주 아주 긴 제목 줄 입니다\n둘째"}, M["variable_stats"], None, M["rules"])
    t, v = title(out), next(l for l in out["layers"] if l["kind"] == "video")
    assert v["y"] == round(P.title_ink_bottom(t) + K["gap_ink"]) and v["y"] + v["h"] == 1621
    assert t["size"] < K["size_cap"]                                    # 긴 줄은 폭에 맞춰 작아진다
    short = P.apply(pre, None, {"layers[text:title].text": "짧\n다"}, M["variable_stats"], None, M["rules"])
    assert title(short)["size"] == K["size_cap"]                        # 짧은 줄은 상한


def test_fix_value_pins_and_survives_merge(tmp_path):
    d = tmp_path / "s" / "preset" / "A"
    P.save(J, FRAME_A, d, "Z", "x")
    M = P.fix_value(d, "layers[text:brand].outline", {"px": 3, "rgb": [96, 95, 98]}, "렌더 대조: 4px 잉크 +25% 밖, 3px 안")
    assert M["fixed"]["layers[text:brand].outline"]["value"]["px"] == 3
    g = other_video(FRAME_A); next(l for l in g["layers"] if l.get("role") == "brand")["outline"] = {"px": 5, "rgb": [10, 10, 10]}
    M = P.save(J, g, d, "1", "y")
    pre, _ = P.load(d)
    assert "layers[text:brand].outline" not in M["variables"]
    assert next(l for l in pre["layers"] if l.get("role") == "brand")["outline"] == {"px": 3, "rgb": [96, 95, 98]}


def test_fill_w_prefers_measured_ink_width(tmp_path):
    d = tmp_path / "s" / "preset" / "A"
    f = copy.deepcopy(FRAME_A); f["made_from"] = {**f.get("made_from", {}), "title_ink_w": 782}
    M = P.save(J, f, d, "Z", "x")
    assert M["rules"]["keys"]["fill_w"]["values"] == {"Z": 782}        # 실측 잉크 폭이 있으면 그것(글꼴 계산 대신)



def test_title_gap_fixed_window_follows_title(tmp_path):
    """제목 끝–창 간격(gap_ink)은 고정, 창 y 는 제목 잉크 아래 끝 + gap_ink — 제목 y·줄높이가 다른 편 값으로 바뀌어도
    마지막 줄이 창으로 내려앉지 않는다(LOO ho5: 둘째 줄 12px 내려가 창에 걸침, 10-16)."""
    d = tmp_path / "s" / "preset" / "A" / "창안"
    g1 = other_video(FRAME_A); v1 = next(l for l in g1["layers"] if l["kind"] == "video"); v1["y"], v1["h"] = 323, 1298
    g2 = other_video(FRAME_A); t2 = title(g2); t2.update(y=107, size=99.6, line_h=126)
    v2 = next(l for l in g2["layers"] if l["kind"] == "video"); v2["y"], v2["h"] = 323, 1298
    P.save(J, g1, d, "a", "x"); M = P.save(J, g2, d, "b", "y")
    K = {k: v["default"] for k, v in M["rules"]["keys"].items()}
    assert K["video_anchor"] == "gap_ink"
    gaps = M["rules"]["keys"]["gap_ink"]["values"]
    pre, M = P.load(d)
    out = P.apply(pre, None, {"layers[text:title].text": "새 제목" + chr(10) + "둘째 줄"}, M["variable_stats"], None, M["rules"])
    t, v = title(out), next(l for l in out["layers"] if l["kind"] == "video")
    assert abs((v["y"] - P.title_ink_bottom(t)) - K["gap_ink"]) <= 0.5 and min(gaps.values()) <= K["gap_ink"] <= max(gaps.values())
    assert v["y"] + v["h"] == 1621


def _two_fonts(tmp_path, pooled=None):
    d = tmp_path / "s" / "preset" / "A" / "창안"
    g1 = other_video(FRAME_A); title(g1)["font"] = "Cafe24Ohsquare"
    g2 = other_video(FRAME_A); title(g2)["font"] = "YgJalnan"
    J1 = {**J, "fonts": {"title": {"top5": [{"font": "Cafe24Ohsquare.ttf", "score": 0.54}, {"font": "yg-jalnan.ttf", "score": 0.50}]}}}
    J2 = {**J, "fonts": {"title": {"top5": [{"font": "yg-jalnan.ttf", "score": 0.67}, {"font": "Cafe24Ohsquare.ttf", "score": 0.40}]}}}
    if pooled:
        J2["fonts"]["title_pooled"] = pooled
    P.save(J1, g1, d, "a", "x")
    return P.save(J2, g2, d, "b", "y")


def test_title_font_tie_broken_by_summed_scores(tmp_path):
    M = _two_fonts(tmp_path)
    st = M["variable_stats"]["layers[text:title].font"]
    assert st["default"] == "YgJalnan" and "점수 합" in st["how"]          # 1:1 동률 → 0.50+0.67 > 0.54+0.40


def test_title_font_prefers_pooled(tmp_path):
    M = _two_fonts(tmp_path, pooled={"top3": [{"font": "Cafe24Ohsquare.ttf", "score": 0.7}]})
    st = M["variable_stats"]["layers[text:title].font"]
    assert st["default"] == "Cafe24Ohsquare" and "묶음 판별" in st["how"]


def test_loo_judge_two_tiers():
    """LOO 두 층 판정: 고정(창 x·w·아래 끝, [광고] 띠 #0)은 뺀 편과, 변수(창 y, 제목 띠 #1+)는 다른 편 원본 범위 ±10%."""
    from tools.calcopy.engine import loo_preset as L

    def run(win_o, win_u, h1_o, h1_u, ink0_status="in"):
        return {"rows": [
            {"key": "frame.window", "name": "창", "orig": win_o, "ours": win_u, "diff": 0, "status": "out"},
            {"key": "band.ink#0", "name": "광고 잉크", "orig": 0.025, "ours": 0.025, "diff": 0, "status": ink0_status},
            {"key": "band.line_h#1", "name": "제목1 높이", "orig": h1_o, "ours": h1_u, "diff": 0, "status": "out"}]}
    R = {"a": run([0, 322, 1080, 1300], [0, 342, 1080, 1280], 93.0, 84.0),
         "b": run([0, 323, 1080, 1298], [0, 338, 1080, 1284], 110.0, 87.0, "out"),
         "c": run([0, 323, 1080, 1298], [0, 400, 1080, 1221], 91.0, 130.0)}
    J = L.judge(R)
    a = {r["key"]: r["in"] for r in J["a"]["rows"]}
    assert a == {"frame.window.fixed": True, "frame.window.y": True, "band.ink#0": True, "band.line_h#1": True}  # 84 ∈ [81.9,121]
    b = {r["key"]: r["in"] for r in J["b"]["rows"]}
    assert b["band.ink#0"] is False and b["band.line_h#1"] is True                     # 고정은 compare 판정 그대로
    c = {r["key"]: r["in"] for r in J["c"]["rows"]}
    assert c["frame.window.y"] is False and c["band.line_h#1"] is False                 # 400 > 355.3, 130 > 121
    assert J["c"]["defects"] == ["영상 창 y", "제목1 높이"]


def test_preset_fixed_values_equal_auto_frame(tmp_path):
    """프리셋 고정값 == 자동본 값(10-16 창아래_검정: 자막 낱말 간격 6.8 → 0, lh_ratio 1.03 → 1.0 으로 넘어가 창 y 6px 밖).
    한 편으로 만든 프리셋은 자동본의 자막 자간·낱말 간격·외곽선과 규칙 비율을 그대로 가져야 한다."""
    f = copy.deepcopy(FRAME_A)
    cap = next(l for l in f["layers"] if l.get("role") == "caption")
    cap.update(letter_spacing=-7.4, word_spacing=6.8, outline={"px": 3, "rgb": [10, 10, 10]})
    t = title(f); t["line_h"] = round(t["size"] * 1.03)
    d = tmp_path / "s" / "preset" / "A" / "창아래"
    M = P.save(J, f, d, "Z", "x")
    pre, M = P.load(d)
    pc = next(l for l in pre["layers"] if l.get("role") == "caption")
    for k in ("letter_spacing", "word_spacing", "outline"):
        assert pc[k] == cap[k], (k, pc[k], cap[k])
    assert M["rules"]["keys"]["lh_ratio"]["default"] == round(t["line_h"] / t["size"], 3)
    out = P.apply(pre, None, {"layers[text:title].text": t["text"]}, M["variable_stats"], None, M["rules"])
    assert title(out)["line_h"] == t["line_h"]


def test_manifest_meta_roles_source_kind_rules_path(tmp_path):
    """manifest 의 대본·소재 칸(roles·source_kind·rules_path) — 검사하고 저장, 프리셋을 다시 만들어도(loo_preset.build) 남는다."""
    from tools.calcopy.engine import loo_preset as L
    d = tmp_path / "channel" / "sseolpulda" / "preset" / "A" / "창아래"
    P.save(J, FRAME_A, d, "Z", "x")
    M = P.set_meta(d, roles=["발견", "의심"], source_kind="해외영상", rules_path="channel/sseolpulda/제품_이야기썰형.rules.json")
    assert M["roles"] == ["발견", "의심"] and M["source_kind"] == "해외영상"
    for bad in ({"source_kind": "아무거나"}, {"roles": []}, {"rules_path": "없는/파일.json"}):
        with pytest.raises(ValueError):
            P.set_meta(d, **bad)
    tg = tmp_path / "t.json"; tg.write_text(json.dumps(J), encoding="utf-8")
    old = L.tteutgi
    L.tteutgi = lambda slug, vid: tg
    try:
        M2 = L.build(d, "sseolpulda", ["Z"], {"Z": FRAME_A}, "note")
    finally:
        L.tteutgi = old
    assert M2["roles"] == ["발견", "의심"] and M2["rules_path"] == "channel/sseolpulda/제품_이야기썰형.rules.json"


def test_multi_frame_preset_roundtrip_and_span_per_video(tmp_path):
    """틀 여러 장(훅+본문) 프리셋: flat↔unflat 그대로, 틀 시간축(span)은 편마다 변수(기본값 = 중앙값), 제목 글은 기본값 없음."""
    def mk(he, title):
        return {"canvas": [1080, 1920], "made_by": "x", "source": "s", "template_off": None,
                "frames": [{"id": "hook", "span": [0, he], "layers": [{"kind": "bg", "rgb": [64, 64, 64]},
                            {"kind": "text", "role": "title", "x": 540, "y": 200, "w": 1000, "lines": 2, "font": "BMDOHYEON",
                             "size": 100, "line_h": 110, "rgb": [255, 255, 255], "text": title}]},
                           {"id": "body", "span": [he, None], "layers": [{"kind": "bg", "rgb": [255, 255, 255]}]}]}
    a = mk(3.137, "가\n나")
    f = P.flat(schema.validate(a))
    assert f["frames[hook].span"] == [0, 3.137] and "frames[hook].layers[text:title].size" in f
    assert P.unflat(f, P.layer_order(schema.validate(a))) == {k: v for k, v in schema.validate(a).items()}
    d = tmp_path / "channel" / "yummyknow" / "preset" / "게시글형"
    P.save(J, a, d, "a", "x"); M = P.save(J, mk(2.446, "다\n라"), d, "b", "y")
    assert set(M["variables"]) == {"frames[hook].span", "frames[body].span", "frames[hook].layers[text:title].text"}
    assert M["variable_stats"]["frames[hook].span"]["default"] == [0, 2.792]
    assert M["variable_stats"]["frames[hook].layers[text:title].text"]["default"] is None
    pre, M = P.load(d)
    out = P.apply(pre, None, {"frames[hook].layers[text:title].text": "새\n제목"}, M["variable_stats"])
    assert schema.validate(out)["frames"][1]["span"] == [2.792, None]


def test_auto_diff_and_rebuild_from_auto_frames(tmp_path):
    """옛 to_frame 판으로 만든 프리셋(자막 낱말 간격 0·제목 줄 배율 옛 값) → auto_diff 가 자동본과 어긋난 고정 자리를 집고,
    rebuild 뒤엔 0 — 손으로 못 박은 자리(fixed)·META(roles·source_kind)·만든 시각은 그대로 남는다."""
    old = copy.deepcopy(FRAME_A)
    next(l for l in old["layers"] if l.get("role") == "caption").update(word_spacing=0)
    title(old)["line_scale"] = [1.2, 0.8]
    d = tmp_path / "s" / "preset" / "A" / "창아래"
    tj = tmp_path / "뜯기.json"; tj.write_text(json.dumps(J, ensure_ascii=False), encoding="utf-8")
    P.save(J, old, d, "Z", str(tj), caption_style="창아래", caption_note="워커 정답")
    P.fix_value(d, "layers[text:brand].size", 48.0, "렌더 대조")
    P.set_meta(d, roles=["발견", "감탄"])
    created = P.load(d)[1]["created_at"]
    auto = copy.deepcopy(FRAME_A)
    next(l for l in auto["layers"] if l.get("role") == "caption").update(word_spacing=6.8)
    before = P.auto_diff(d, {"Z": auto})
    assert {x["path"] for x in before} == {"layers[text:caption].word_spacing", "layers[text:title].line_scale"}, before
    M = P.rebuild(d, {"Z": auto})
    assert P.auto_diff(d, {"Z": auto}) == []
    pre, M = P.load(d)
    assert next(l for l in pre["layers"] if l.get("role") == "brand")["size"] == 48.0 and "layers[text:brand].size" in M["fixed"]
    assert M["roles"] == ["발견", "감탄"] and M["created_at"] == created and M["rebuilt"]["from"] == P.AUTO_TOOL
    assert M["caption_styles"][0]["name"] == "창아래" and M["caption_styles"][0]["notes"] == ["Z: 워커 정답"]
    assert not list(d.parent.glob("_old_*"))                                    # 옛 폴더는 다 만든 뒤 지운다
