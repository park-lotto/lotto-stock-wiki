# -*- coding: utf-8 -*-
"""재료 출처 규칙 — 사장님 10-21 "반드시 원본을 찾아서 / 다른 채널의 연예인 영상을 그대로 가져다 쓰면 절대 안 된다".
판단 주인(볼케이노형 분해 뒤): ①② 벤치·얼굴 컷 = hybrid/rules.source_rule_static(서버 지시서가 부른다) ·
③ 원본 밖 재료 컷의 장면 전환(10-21 이미도: 리뷰여왕 별 전환) = hybrid/runner_ops.source_rule_scan(영상이 있는 회원 PC 가 잰다)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.hybrid import rules as RU  # noqa: E402


def _clip(path: Path, wipe: bool):
    """2초 회색 화면. wipe=True 면 1초에 노랑·민트가 번갈아 번쩍(남의 편집 전환)."""
    vf = "geq=lum='if(between(T,1,1.6),if(mod(N,2),230,40),120)':cb=128:cr=128" if wipe else "null"
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=gray:s=160x160:d=2:r=30", "-vf", vf, "-pix_fmt", "yuv420p", str(path)],
                   check=True, stdin=subprocess.DEVNULL)


def test_face_cut_must_come_from_origin():
    M = {"cuts": {"N1": [{"src": "6E0Mqxsxrgc.mp4", "face": "이미도"}], "N2": [{"src": "hrT1RQX_a6s.mp4", "face": "없음"}],
                  "N3": [{"src": "hrT1RQX_a6s.mp4", "face": "이미도"}], "N4": [{"src": "dL1t0o9k2Gk.mp4", "face": "없음"}]}}
    bad = RU.source_rule_static(M, {"6E0Mqxsxrgc.mp4"}, "dL1t0o9k2Gk", {})
    assert any(b.startswith("N3:") for b in bad)        # 남의 채널 영상의 연예인 얼굴
    assert any(b.startswith("N4:") for b in bad)        # 벤치 쇼츠를 재료로
    assert not any(b.startswith(("N1:", "N2:")) for b in bad)


def test_other_performer_shot():
    shots = {"6E0Mqxsxrgc": [{"i": 0, "a": 0.0, "b": 3.0, "who": "main"}, {"i": 1, "a": 3.0, "b": 6.0, "who": "other", "desc": "PD"}]}
    M = {"cuts": {"N1": [{"src": "6E0Mqxsxrgc.mp4", "ss": 1.0, "face": "이미도"}], "N2": [{"src": "6E0Mqxsxrgc.mp4", "ss": 4.0, "face": "이미도"}]}}
    bad = RU.source_rule_static(M, {"6E0Mqxsxrgc.mp4"}, "", shots)
    assert [b.split(":")[0] for b in bad] == ["N2"], bad


def test_transition_inside_other_channel_cut(tmp_path):
    from tools.calcopy.hybrid import runner_ops as R
    _clip(tmp_path / "src" / "wipe.mp4", True)
    _clip(tmp_path / "src" / "calm.mp4", False)
    T = {"cuts": [{"line": "N3", "src": "wipe.mp4", "ss": 0.3, "dur": 1.6}, {"line": "N4", "src": "calm.mp4", "ss": 0.3, "dur": 1.6}]}
    bad = R.source_rule_scan(tmp_path, T, set())
    assert [b.split(":")[0] for b in bad] == ["N3"], bad


def test_fill_shot_max_centers_main():
    shots = {"o": [{"i": 0, "a": 0.0, "b": 4.0, "who": "main", "cx": 0.75}]}
    M = {"cuts": {"N1": [{"src": "o.mp4", "ss": 1.0, "face": "이미도", "crop": "face"}]}}
    RU.fill_shot_max(M, None, {"o.mp4": [1920, 1080]}, shots, 9 / 16)
    c = M["cuts"]["N1"][0]
    assert c["max"] == 3.0 and c["center"] == "주인공"
    assert abs((c["crop"][0] + c["crop"][2] / 2) - 0.75 * 1920) <= 1      # 주인공 얼굴 가운데


def test_text_is_blurred_not_zoomed():
    """박힌 글자는 흐림(재료.blur), 칸은 원본 높이 그대로(확대 1.0) — 사장님 10-22 · 강주은 첫 컷 1.4배 뭉개짐(예전 avoid_text 최대 2.2배)."""
    shots = {"o": [{"i": 0, "a": 10.0, "b": 14.0, "who": "main", "cx": 0.5, "text": [[0.15, 0.85, 0.85, 0.95]]}]}
    M = {"cuts": {"N1": [{"src": "o.mp4", "ss": 11.0, "face": "주인공"}]}}
    RU.fill_shot_max(M, None, {"o.mp4": [1920, 1080]}, shots, 1.0)
    c = M["cuts"]["N1"][0]
    assert c["crop"][3] == 1080 and c["crop"][2] == 1080                      # 확대 1.0
    assert M["blur"]["o.mp4"] == [[288, 918, 1344, 108, 10.0, 14.0]]          # 자막 자리 흐림(그 샷 동안)
    z = RU.material_problems({"cuts": {"N2": [{"src": "o.mp4", "ss": 1, "crop": [580, 0, 770, 770]}]}}, {"o.mp4"}, set(), {"o.mp4": [1920, 1080]})
    assert len(z) == 1 and "확대" in z[0]


def test_fill_shot_max_keeps_numeric_crop_and_alternates_stills():
    """숫자로 정한 칸은 엔진이 덮지 않는다(98 #21·#25) · 같은 상품 사진이 이어지면 움직임 번갈아."""
    shots = {"o": [{"i": 0, "a": 0.0, "b": 4.0, "who": "main", "cx": 0.3, "text": [[0.0, 0.8, 1.0, 0.95]]}]}
    M = {"cuts": {"N1": [{"src": "o.mp4", "ss": 1.0, "face": "주인공", "crop": [680, 0, 600, 1080]}],
                  "N2": [{"src": "prod_1_0.jpg"}, {"src": "prod_1_0.jpg"}]}}
    RU.fill_shot_max(M, None, {"o.mp4": [1920, 1080]}, shots, 9 / 16)
    assert M["cuts"]["N1"][0]["crop"] == [680, 0, 600, 1080] and M["cuts"]["N1"][0]["max"] == 3.0
    assert [c["move"] for c in M["cuts"]["N2"]] == ["in", "left"]


def test_fix_crop_units_ratio_to_pixels():
    """판정 답이 crop 을 0~1 비율로 적으면 픽셀로(10-21 성시경 2차: crop=0.45:0.8:0.275:0 → ffmpeg 실패) · 화면 밖은 안으로."""
    M = {"cuts": {"N1": [{"src": "o.mp4", "crop": [0.275, 0.0, 0.45, 0.8]}], "N2": [{"src": "o.mp4", "crop": [1800, 0, 600, 1080]}],
                  "N3": [{"src": "o.mp4", "crop": [100, 0, 600, 1080]}]}}
    ch = RU.fix_crop_units(M, {"o.mp4": [1920, 1080]})
    assert M["cuts"]["N1"][0]["crop"] == [528, 0, 864, 864], M
    assert M["cuts"]["N2"][0]["crop"] == [1320, 0, 600, 1080]
    assert M["cuts"]["N3"][0]["crop"] == [100, 0, 600, 1080] and len(ch) == 2


def test_origin_candidates_product_word_first():
    """원본 후보 순서 — 제품 낱말 검색어에 걸린 본인 채널 영상이 이름만 검색한 일반 영상보다 앞(10-21 정재형 실전: 후보 16개가 전부 토크·룸투어)."""
    from tools.calcopy.hybrid import flow
    st = {"read": {"celeb": "정재형", "product_words": ["팔로산토"], "source_label": "출처: 요정재형", "channel_hint": "요정재형", "queries": []},
          "bench": {"id": "b", "dur": 19}, "tries": {}, "log": []}
    found = [{"id": f"talk{i}", "title": "토크", "channel": "요정재형", "dur": 3000, "qs": ["정재형"]} for i in range(20)] + \
            [{"id": "orig", "title": "근데 인테리어 아이템도 알려줌", "channel": "요정재형", "dur": 1000, "qs": ["정재형 팔로산토", "요정재형 화장실 냄새"]}]
    flow.ph_search_got(st, {"search": {"found": found}}, {}, {})
    assert st["cands"][0]["id"] == "orig"
    assert flow._queries(st)[0] == "정재형 팔로산토"


def test_narration_bench_goes_to_visual_origin():
    """벤치가 내레이션뿐이면 말 지문 0 → 원본 자막의 장면 낱말('서촌')이 나온 본인 채널 후보를 화면 대조로(10-22 고현정 가방 실전 멈춤)."""
    from tools.calcopy.hybrid import flow
    words = [[638.0, "오늘은"], [640.2, "서촌에"], [641.0, "왔어요"]]
    assert RU.word_hits(words, ["서촌", "가방"]) == [{"term": "서촌", "origin_t": 640.2}]
    st = {"read": {"celeb": "고현정", "scene_words": ["서촌"], "product_words": ["가방"]}, "bench": {"title": "t", "sheet": "bench/sheet.jpg"},
          "mixed": [{"id": "bag", "title": "가방 리뷰", "channel": "남의 채널"}, {"id": "v19", "title": "고현정 브이로그 19", "channel": "고현정"},
                    {"id": "v20", "title": "고현정 브이로그 20", "channel": "고현정", "dur": 1200}], "tries": {}, "log": []}
    hits = {"bag": [{"term": "가방", "origin_t": 10.0}] * 9, "v19": [{"term": "가방", "origin_t": 50.0}], "v20": [{"term": "서촌", "origin_t": 640.2}]}
    res = flow.ph_subs_got(st, {"subs": {"matched": {}, "hits": hits}}, {}, {})
    assert res == {"goto": "vis_get"} and [c["id"] for c in st["vis"]] == ["v20", "v19"]      # 남의 채널은 후보가 아니다
    flow.ph_vis_get(st, {}, {}, {})
    assert st["origin"]["window"] == [0.0, 1200.0]                                    # 통째로(가방 장면이 장면 낱말 시각 앞뒤에 없던 10-22 2차)
    r = flow.ph_vis_got(st, {"origin": {"files": [{"name": "v20.mp4", "dur": 1200}], "offset": 0.0}}, {}, {})
    assert r["do"][0]["fps"] == 0.1 and r["do"][0]["t"] == 1200 and st["vis_step"] == 10
    assert flow.ph_vis_pick(st, {}, {"origin_visual": {"same": True, "origin_t": [645]}}, {}) == {"goto": "product_sheet"}
    assert st["origin"]["matched"][0]["origin_t"] == 645.0


def test_origin_from_source_label_first():
    """출처 표기가 원본으로 가는 길(사장님 10-22) — 없으면 건너뜀 · 있으면 그 채널 → 후보 조사(한 번 요청) → 내레이션이면 미리보기 대조 → 그 1편만 통째로."""
    import pytest
    from tools.calcopy.hybrid import flow
    st = {"bench": {"id": "b", "dur": 19, "date": "20261016", "title": "t", "sheet": "bench/sheet.jpg"}, "tries": {}, "log": []}
    no = {"origin_read": {"celeb": "고현정", "queries": [], "is_shopping": True, "source_label": ""}}
    with pytest.raises(flow._Stop):
        flow.ph_origin_read(st, {}, no, {})
    yes = {"origin_read": {"celeb": "고현정", "queries": [], "is_shopping": True, "source_label": "출처: 고현정", "scene_words": ["서촌"], "product_words": ["가방"]}}
    r = flow.ph_origin_read(st, {}, yes, {})
    assert r["do"][0]["cmd"] == "channel_find" and r["do"][0]["label"] == "고현정" and r["do"][0]["celeb"] == "고현정"
    titles = [{"id": "s1", "title": "쇼츠", "dur": 30}, {"id": "v21", "title": "브이로그 21", "dur": 691}, {"id": "v20", "title": "브이로그 20", "dur": 725}]
    r = flow.ph_src_got(st, {"src": {"picked": [{"id": "UC", "name": "고현정"}], "titles": titles}}, {}, {})
    assert r["do"][0]["cmd"] == "origin_probe" and r["do"][0]["ids"] == ["v21", "v20"] and r["do"][0]["before"] == "20261016"
    sheets = {"v21": {"file": "look/sb_v21.jpg"}, "v20": {"file": "look/sb_v20.jpg"}}
    r = flow.ph_probe_got(st, {"probe": {"matched": {}, "sheets": sheets, "hits": {"v20": [{"term": "서촌", "origin_t": 640}]}}}, {}, {})
    assert r["review"][0]["id"] == "origin_sb" and list(st["sb"]) == ["v20", "v21"]          # 장면 낱말이 걸린 후보가 앞
    r = flow.ph_sb_pick(st, {}, {"origin_sb": {"origin_id": "v20", "origin_t": [302, 330]}}, {})
    assert r["do"][0] == {"id": "origin", "cmd": "origin_get", "vid": "v20", "a": 0.0, "b": 725.0, "ts": [], "full": True}


def test_source_channel_title_words_before_recency():
    """출처 채널 후보 = 제목에 장면·제품 낱말 든 영상 먼저, 그다음 최신순(98 #58 선우용여 여주 아울렛 — 반년 전 원본이 최신 10편 밖)."""
    from tools.calcopy.hybrid import flow
    st = {"bench": {"id": "b", "dur": 22, "date": "20261018"}, "tries": {}, "log": [], "read": {"scene_words": ["여주 아울렛"], "product_words": ["신발"]}}
    many = [{"id": f"n{i}", "title": f"브이로그 {i}", "dur": 900} for i in range(12)] + [{"id": "old", "title": "여주 아울렛에서 하루 쇼핑", "dur": 1426}]
    r = flow.ph_src_got(st, {"src": {"picked": [{"id": "UC", "name": "순풍"}], "titles": many}}, {}, {})
    assert r["do"][0]["ids"][0] == "old" and r["do"][0]["ids"][1] == "n0" and len(r["do"][0]["ids"]) == flow.SRC_PROBE
    st["read"] = {"celeb": "함익병", "scene_words": [], "product_words": ["유리아 크림"]}   # 남의 채널 손님 — 제목에 손님 이름
    guests = [{"id": f"g{i}", "title": f"손님 {i} 이야기 #이성미의나는꼰대다", "dur": 900} for i in range(12)] + [{"id": "ham", "title": "[3부] 무좀·주름 습관 #함익병", "dur": 1300}]
    r = flow.ph_src_got(st, {"src": {"picked": [{"id": "UC", "name": "이성미의 나는 꼰대다"}], "titles": guests}}, {}, {})
    assert r["do"][0]["ids"][0] == "ham"


def test_source_kind_program_marked_and_kept():
    """출처가 프로그램 이름이면 편 상태에 표시하고 채널 검색을 건너뛴다 — 다시 시도해도 같은 길(사장님 10-22 '안 헷갈리게')."""
    from tools.calcopy.hybrid import flow
    st = {"bench": {"id": "b", "dur": 14, "date": "20261009"}, "tries": {}, "log": []}
    rp = {"origin_read": {"celeb": "선우용여", "queries": [], "is_shopping": True, "source_label": "출처: 옥탑방의 문제아들", "source_kind": "program"}}
    r = flow.ph_origin_read(st, {}, rp, {})
    assert r["do"][0]["kind"] == "program" and st["src"] == {"label": "옥탑방의 문제아들", "kind": "program"}
    flow.ph_src_got(st, {"src": {"how": "search", "picked": [], "titles": [{"id": "q", "title": "선우용여 #옥탑방의문제아들", "dur": 999, "channel": "KBS Entertain"}]}}, {}, {})
    assert st["src"]["channel"] == "KBS Entertain"
    msg = flow._msg(st, "probe_got")
    assert "원본" in msg and "옥탑방" not in msg and "KBS" not in msg          # 고객 진행 줄은 단계만(사장님 10-22 "세부적으로 알려 주면 안 된다") — 출처 판단은 편 상태에만


def test_run_do_parallel_safe_only(tmp_path, monkeypatch):
    """서로 기다릴 필요 없는 일(받아쓰기·샷 표·쿠팡…)은 한꺼번에, 나머지(쓰기→읽기·유튜브)는 차례대로 — 결과는 id 별로 그대로(10-22)."""
    import time
    from tools.calcopy.hybrid import runner_ops as O
    order = []
    def slow(name):
        def f(W, d):
            order.append(("start", name)); time.sleep(0.4); order.append(("end", name)); return {"n": name}
        return f
    monkeypatch.setattr(O, "CMDS", {"asr_spans": slow("asr"), "shot_sheets": slow("shots"), "write_doc": slow("write"), "orig_heard": slow("heard")})
    t = time.time()
    out = O.run_do(tmp_path, [{"id": "a", "cmd": "asr_spans"}, {"id": "s", "cmd": "shot_sheets"}, {"id": "w", "cmd": "write_doc"}, {"id": "h", "cmd": "orig_heard"}], log=lambda *_: None)
    assert time.time() - t < 1.5 and set(out) == {"a", "s", "w", "h"}
    assert order.index(("end", "write")) < order.index(("start", "heard"))        # 쓰기 다음에 읽기


def test_sns_source_goes_to_search():
    """출처가 유튜브 밖(인스타그램 등)이면 원본이 아니다(사장님 10-22) — 엉뚱한 채널을 뒤지지 않고 '<연예인> <제품 낱말>' 검색 길로."""
    from tools.calcopy.hybrid import flow
    st = {"bench": {"id": "b", "dur": 20}, "tries": {}, "log": []}
    rp = {"origin_read": {"celeb": "이영애", "queries": [], "is_shopping": True, "source_label": "출처: 이영애 인스타그램", "source_kind": "channel"}}
    assert flow.ph_origin_read(st, {}, rp, {}) == {"goto": "search"} and st["src"]["kind"] == "sns"


def test_product_not_near_match_goes_wide_once():
    """말이 맞은 곳 앞뒤에 제품이 없으면 원본 전체 시트로 한 번 더 — 두 번째도 없으면 멈춤(10-22 강주은: 가방은 10분 50초)."""
    import pytest
    from tools.calcopy.hybrid import flow
    st = {"origin": {"files": [{"name": "o.mp4", "dur": 1200}]}, "read": {"product_words": ["가방"]}, "bench": {}, "tries": {}, "log": []}
    r = flow.ph_product_cands(st, {}, {"product_pick": {"scenes": [], "coupang_queries": []}}, {})
    assert r["then"] == "product_pick_wide" and r["do"][0]["t"] == 1200 and st["look_step"] == 10
    r = flow.ph_product_pick_wide(st, {"psheet": {"file": "look/origin_wide.jpg"}}, {}, {})
    assert r["review"][0]["id"] == "product_pick" and "10초 간격" in r["review"][0]["ask"]
    with pytest.raises(flow._Stop):
        flow.ph_product_cands(st, {}, {"product_pick": {"scenes": [], "coupang_queries": []}}, {})


def test_unknown_render_error_gets_one_fix_then_retryable_stop():
    """처음 보는 렌더 오류(KeyError 'ss' 등)도 재료로 한 번 고쳐 보고, 또 나면 다시 시도할 수 있는 멈춤(10-22 강주은)."""
    import pytest
    from tools.calcopy.hybrid import flow
    st = {"version": "키치잇판", "script": {"S": {"lines": []}, "M": {"cuts": {}}}, "tries": {}, "log": [], "bench": {}, "origin": {"files": [{"name": "o.mp4"}]}}
    r = flow.ph_render_got(st, {"render": {"ok": False, "error": "KeyError: 'ss'"}}, {}, {})
    assert r["then"] == "render_fix" and "KeyError" in r["review"][0]["ask"]
    with pytest.raises(flow._Stop) as e:
        flow.ph_render_got(st, {"render": {"ok": False, "error": "KeyError: 'ss'"}}, {}, {})
    assert e.value.kw.get("retry") == "render" if hasattr(e.value, "kw") else True


def test_any_stop_retries_from_last_asker_with_its_inputs(monkeypatch):
    """뿌리(10-22): 멈춤 34곳 중 5곳만 이어 가기 → 고칠 때마다 처음부터. 이제 어느 멈춤이든 마지막으로 일을 시킨 단계부터, 그 단계가 받았던 입력과 함께."""
    from tools.calcopy.hybrid import flow
    seen = []
    def c(st, m, rp, u):
        seen.append(rp.get("q"))
        if not rp.get("q"):
            raise flow._Stop("입력 없음")
        return {"do": [{"id": "x", "cmd": "env"}], "then": "d"}
    def d(st, m, rp, u):
        raise flow._Stop("실행 결과가 이상함")
    monkeypatch.setitem(flow.PHASES, "c", c)
    monkeypatch.setitem(flow.PHASES, "d", d)
    monkeypatch.setitem(flow.PHASE_STAGE, "c", "product")
    monkeypatch.setitem(flow.PHASE_STAGE, "d", "product")
    st = {"phase": "c", "tries": {"plan": 3}, "log": []}
    assert flow.step(st, {}, {"q": {"v": 1}}, {})["status"] == "execute"
    r = flow.step(st, {"x": {}}, {}, {})
    assert r["status"] == "stop" and r.get("retry_ok") and st["stopped"]["retry"] == "c"
    r = flow.step(st, {}, {}, {"retry": True})
    assert r["status"] == "execute" and seen == [{"v": 1}, {"v": 1}] and st["tries"] == {}
    st2 = {"phase": "stopped", "stopped": {"why": "의약품", "fix": ""}, "tries": {}, "log": []}
    assert flow.step(st2, {}, {}, {"retry": True})["status"] == "stop"            # final 멈춤·retry 없는 멈춤은 그대로


def test_material_problems_caught_before_render():
    """재료 답 꼴(받은 파일·영상 컷 ss·숫자·crop 꼴)을 계획 단계에서 — 렌더 KeyError 로 터지기 전에(뿌리 10-22 강주은)."""
    M = {"cuts": {"L1": [{"src": "o.mp4"}], "L5": [{"src": "prod_1.jpg"}], "L6": [{"src": "m.mp4"}],
                  "L7": [{"src": "x.mp4", "ss": "3초", "crop": [0.1, 0, 1]}]}}
    p = RU.material_problems(M, {"o.mp4", "prod_1.jpg", "m.mp4"}, {"L1"})
    assert len(p) == 4 and p[0].startswith("L6#1") and all(x.startswith("L7#1") for x in p[1:])   # 원음 줄 o.mp4·사진 컷은 통과


def test_customer_stop_text_has_no_internals():
    """멈춤 글(고객에게 보임)에 오류 원문·내부 이름이 없다 — 세부는 작업 기록(log)에만(사장님 10-22)."""
    import pytest
    from tools.calcopy.hybrid import flow
    st = {"version": "키치잇판", "script": {"S": {"lines": []}, "M": {"cuts": {}}}, "tries": {"render_err": 1}, "log": [], "bench": {}, "origin": {"files": [{"name": "o.mp4"}]}}
    with pytest.raises(flow._Stop) as e:
        flow.ph_render_got(st, {"render": {"ok": False, "error": "KeyError: 'ss' prod_1.jpg"}}, {}, {})
    assert "KeyError" not in e.value.why + e.value.fix and "prod_1" not in e.value.fix and any("KeyError" in x for x in st["log"])
    with pytest.raises(flow._Stop) as e:
        flow._reply({}, "plan_키치잇판", ("ok",))
    assert "plan_" not in e.value.why


def test_review_counts_banned_and_alt_scene_rule():
    """후기 개수·평점 숫자 금지(셀링포인트로) · 대체 제품이면 원음 뒤 제품 줄에 연예인 장면 금지(사장님 10-22 강주은 뒷부분)."""
    S = {"lines": [{"id": "L1", "kind": "tts", "tts": "강주은 씨가 든 가방이 있다네요?"}, {"id": "O1", "kind": "orig"},
                   {"id": "L8", "kind": "tts", "tts": "근데 진짜 놀라운 건 후기가 백팔십육 개래요.", "caps": ["후기가 186개래요"]},
                   {"id": "L9", "kind": "tts", "tts": "후기 보니까 수납이 칸칸이 나뉘어 있대요."}]}
    p = RU.script_claim_problems(S)
    assert len(p) == 1 and p[0].startswith("L8")
    M = {"cuts": {"L1": [{"src": "o.mp4"}], "L8": [{"src": "prod_1.jpg"}], "L9": [{"src": "o.mp4"}]}}
    a = RU.alt_scene_problems(S, M, {"o.mp4"})
    assert len(a) == 1 and a[0].startswith("L9")                    # 훅 줄(원음 앞)의 연예인 장면은 괜찮다


def test_reviews_phase_after_product():
    from tools.calcopy.hybrid import flow
    st = {"product": {"product_id": "8003851952"}, "tries": {}, "log": []}
    r = flow.ph_reviews(st, {}, {}, {})
    assert r["do"][0] == {"id": "reviews", "cmd": "coupang_reviews", "product_id": "8003851952"}
    st["product"]["name"] = "SHOPPI 여성 모던 가죽 토트백"
    r = flow.ph_reviews_got(st, {"reviews": {"reviews": [], "blocked": True}}, {}, {})
    assert r["do"][0]["cmd"] == "naver" and r["do"][0]["queries"][0] == "SHOPPI 여성 모던 가죽 후기" and "막음" in st["log"][-1]   # 쿠팡 막히면 네이버로(사장님 10-22)
    assert flow.ph_reviews_naver(st, {"nreviews": {"texts": {"q": "수납이 넉넉"}}}, {}, {}) == {"goto": "research"} and st["reviews"][0]["id"] == "n1"


def test_ad_mark_badge_small_top_right(tmp_path):
    """오른쪽 위 '광고' 표시 — 작게(1080 너비에서 상자 높이 60px 이하·너비 120px 이하), 주인 = engine/ad_mark(사장님 10-22)."""
    from tools.calcopy.engine import ad_mark
    png, m = ad_mark.badge(1080, tmp_path / "b.png")
    from PIL import Image
    w, h = Image.open(png).size
    assert w <= 120 and h <= 60 and 15 <= m <= 30


def test_product_judgment_gets_candidate_photos():
    """같은 제품 판정에 쿠팡 후보 사진 시트를 같이 — 이름만으로 고르지 않게(10-22 강주은 둥근 실버 잠금 가방)."""
    from tools.calcopy.hybrid import flow
    st = {"tries": {}, "log": [], "product_shots": ["look/p1.jpg"]}
    r = flow.ph_product_same(st, {"shots": {"files": ["look/p1.jpg"]}, "coupang": {"items": [{"product_id": "1", "image": "https://x/1.jpg", "name": "a"}]}}, {}, {})
    assert r["do"][0]["cmd"] == "cand_sheet" and r["then"] == "cand_look"
    r = flow.ph_cand_look(st, {"csheet": {"file": "look/cand_sheet.jpg"}}, {}, {})
    rv = r["review"][0]
    assert rv["id"] == "product_same" and any(x.get("file") == "look/cand_sheet.jpg" for x in rv["show"]) and "사진으로도 같아야" in rv["ask"]


def test_still_crop_checked_against_real_size():
    """상품 사진 crop 은 실제 픽셀로·사진 너비 40% 이상 — 미리보기 크기로 잘라 렌더 3번 돈 것(10-22 강주은) 계획 단계에서."""
    M = {"cuts": {"n4": [{"src": "prod_1.jpg", "crop": [0, 0, 300, 300]}], "n5": [{"src": "prod_1.jpg", "crop": [0, 0, 900, 900]}],
                  "n6": [{"src": "prod_1.jpg", "crop": [500, 0, 900, 900]}], "n7": [{"src": "prod_1.jpg"}]}}
    p = RU.material_problems(M, {"prod_1.jpg"}, set(), {"prod_1.jpg": [1000, 1000]})
    assert [x.split(":")[0] for x in p] == ["n4#1", "n6#1"]


def test_every_stop_has_fix_line():
    """멈춤은 고객에게 이유·해결 두 줄(사장님 10-22) — 해결이 빈 멈춤 금지(10-23 함익병: '숏템이 따로 알려 준 방법은 없어요'로 나갔다)."""
    import re
    src = (Path(__file__).resolve().parents[2] / "tools/calcopy/hybrid/flow.py").read_text(encoding="utf-8")
    bad = re.findall(r'_Stop\(\s*"[^"]*"\s*\)|_Stop\(\s*"[^"]*"\s*,\s*""', src)
    assert not bad, bad


def test_spoken_only_product_uses_given_product():
    """원본에 제품이 말로만 나오면 고객이 정한 쿠팡 제품으로(사장님 10-23 함익병 기미크림 — '실제 올린 채널의 상품을 참고') · 정한 게 없으면 그대로 멈춤.
    정한 제품은 연예인 것과 같다고 확인된 게 아니라 alt 규칙(원음 뒤 연예인 장면 금지)에 given 말투(연예인이 썼다고 말하지 않음)."""
    import pytest
    from tools.calcopy.hybrid import flow
    st = flow.start("https://youtu.be/Ei0UAhOL6p0", "kitchit", "s1", "메디필 멜라논 엑스 크림 https://www.coupang.com/vp/products/7694655931?itemId=2")
    st.update({"origin": {"files": [{"name": "o.mp4", "dur": 1200}]}, "read": {"product_words": ["기미크림"]}, "bench": {}, "_wide_product": True})
    assert flow.ph_product_cands(st, {}, {"product_pick": {"scenes": [], "coupang_queries": []}}, {}) == {"goto": "given"}
    r = flow.ph_given(st, {}, {}, {})
    assert r["do"][0] == {"id": "coupang", "cmd": "coupang", "queries": ["메디필 멜라논 엑스 크림"]}
    r = flow.ph_given_same(st, {"coupang": {"items": [{"product_id": "7694655931", "image": "https://x/1.jpg", "name": "메디필 멜라논 엑스 크림, 30ml, 2개"}]}}, {}, {})
    assert r["do"][0]["cmd"] == "cand_sheet"
    rv = flow.ph_cand_look(st, {"csheet": {"file": "look/cand_sheet.jpg"}}, {}, {})["review"][0]
    assert rv["id"] == "given_same" and "7694655931" in rv["ask"]
    assert flow.ph_product_done(st, {}, {"given_same": {"product_id": "7694655931", "name": "메디필 멜라논 엑스 크림", "category": "화장품"}}, {}) == {"goto": "reviews"}
    assert st["product"]["mode"] == "alt" and st["product"]["given"] is True
    with pytest.raises(flow._Stop):                                         # 정한 제품이 후보에 없으면 멈춤(대체로 넘어가지 않는다)
        flow.ph_product_done(st, {}, {"given_same": {"product_id": ""}}, {})
    st2 = flow.start("u", "kitchit", "s2")
    st2.update({"origin": {"files": [{"name": "o.mp4", "dur": 1200}]}, "read": {}, "bench": {}, "_wide_product": True})
    with pytest.raises(flow._Stop):
        flow.ph_product_cands(st2, {}, {"product_pick": {"scenes": [], "coupang_queries": []}}, {})
    assert "given" in RU.PRODUCT_TALK and "추천했다고 말하지" in RU.PRODUCT_TALK["given"]


def test_source_channel_search_hits_first():
    """출처 채널 안 검색('<연예인> <낱말>')에 걸린 영상이 후보 맨 앞 — 98 #65 셀코TV 함익병 기미: 원본이 최신 60편 밖이라 7분 넘게 헤맸다(채널 안 검색은 2초에 1위)."""
    from tools.calcopy.hybrid import flow
    assert flow._src_queries({"celeb": "함익병", "queries": ["함익병 멜라논 크림", "함익병 기미크림", "x"]}) == ["함익병 멜라논 크림", "함익병 기미크림"]
    assert flow._src_queries({"celeb": "함익병", "product_words": ["기미크림"]}) == ["함익병 기미크림"]
    st = {"bench": {"id": "b", "dur": 13}, "read": {"celeb": "함익병", "product_words": ["기미크림"]}, "tries": {}, "log": []}
    titles = [{"id": f"n{i}", "title": f"함익병 피부 {i}", "dur": 600} for i in range(12)] + [{"id": "old", "title": "잡티,기미,검버섯 (함익병)", "dur": 1592}]
    r = flow.ph_src_got(st, {"src": {"titles": titles, "searched": ["old", "n5"], "picked": [{"id": "c", "name": "셀코TV"}], "how": "channel"}}, {}, {})
    assert r["do"][0]["ids"][:2] == ["old", "n5"]


def test_given_research_note_and_stop_hides_judgment():
    """고객이 정한 제품이면 조사에 given 안내(원본 제품이 의약품이어도 그것만으로 멈추지 않음) · 조사 멈춤 글은 기록에만(98 #66)."""
    import pytest
    from tools.calcopy.hybrid import flow
    assert "고객이 정한 제품" in flow.RESEARCH_GIVEN and "멈추지 않는다" in flow.RESEARCH_GIVEN
    st = {"tries": {}, "log": [], "version": "kitchit"}
    with pytest.raises(flow._Stop) as e:
        flow.ph_research_check(st, {}, {"research": {"stop": "동아에스티 전문의약품(히드로퀴논)", "조사_md": "x", "keywords": [], "queries": [], "spans": []}}, {})
    assert "동아" not in e.value.why and "동아" in st["log"][-1]


def test_misread_label_falls_back_to_similar_channel(monkeypatch, tmp_path):
    """출처 글자를 잘못 읽어(셀코TV→쌩코TV) 채널 검색이 0건이면 '<연예인> <낱말>' 영상 검색에서 이름이 닮은 채널로(98 #67)."""
    import types
    from tools.calcopy.hybrid import runner_ops as R
    monkeypatch.setattr(R, "CACHE", False)
    monkeypatch.setattr(R, "_blocked", lambda r: False)
    monkeypatch.setattr(R, "yt", lambda args, timeout=0: types.SimpleNamespace(returncode=0, stdout='{"entries": []}', stderr=""))
    monkeypatch.setattr(R, "_vsearch", lambda q, n=20: ([{"id": "v1", "channel": "셀코TV / 잘 먹고 잘 사는 방법", "channel_id": "UCsel"},
                                                         {"id": "v2", "channel": "이성미의 나는 꼰대다", "channel_id": "UCkon"}], False))
    monkeypatch.setattr(R, "c_channel_list", lambda W, d: {"titles": [{"id": "x", "title": "t", "dur": 600}]})
    r = R.c_channel_find(tmp_path, {"label": "쌩코TV", "kind": "channel", "celeb": "함익병", "queries": ["함익병 기미"]})
    assert r["picked"][0]["id"] == "UCsel" and r["titles"]


def test_origin_read_gets_big_frame_for_label():
    """출처 글자는 큰 장면 한 장으로 읽는다(98 #69: 시트 칸 300px → '셀코TV'를 '없음'·'쌩코TV'로)."""
    from tools.calcopy.hybrid import flow
    st = {"tries": {}, "log": []}
    r = flow.ph_bench_got(st, {"bench": {"id": "b", "sheet": "bench/sheet.jpg", "big": "bench/big.jpg", "lines": []}}, {}, {})
    rv = r["review"][0]
    assert any(x.get("file") == "bench/big.jpg" for x in rv["show"]) and "둘째 그림" in rv["ask"] and st["bench"]["big"] == "bench/big.jpg"
