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


def test_avoid_text_cuts_band_and_caption_keeps_face_center():
    """박힌 글자 피하기(rules.avoid_text) — 위 제목 띠·아래 자막을 칸 밖으로, 창 비율·주인공 가운데 유지(10-21 선우용여, 98 #24)."""
    sw, sh, ar = 1920, 1080, 1.0
    band, cap = [240, 0, 630, 90], [300, 900, 1600, 1000]
    x, y, w, h = c = RU.avoid_text([420, 0, 1080, 1080], [band, cap], 960.0, sw, sh, ar)
    assert y >= 90 and y + h <= 900, c                      # 띠 아래 · 자막 위
    assert abs(w - h * ar) <= 1 and abs((x + w / 2) - 960) <= 1, c
    assert RU.avoid_text([0, 0, 1080, 1080], [[0, 0, 1920, 700]], 500.0, sw, sh, ar) == [0, 0, 1080, 1080]   # 너무 줄어들면 그대로


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
