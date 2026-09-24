# -*- coding: utf-8 -*-
"""2단계(사진·밈·프레임) — 가짜 이미지로 프레임 조립과 이미지 단계 재사용을 검사한다. EvoLink는 부르지 않는다."""
import json
import re
import shutil
from pathlib import Path

import pytest
from PIL import Image

from shopping_shorts.brainbulb import frames, images, spec, timing as tmod, pipeline

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _png(path, size, color):
    Image.new("RGB", size, color).save(path)


def test_compose_places_photo_in_slot_and_meme_by_height(tmp_path):
    photo = tmp_path / "p.png"; _png(photo, (1248, 832), (200, 30, 30))
    meme = tmp_path / "m.png"; Image.new("RGBA", (231, 218), (30, 200, 30, 255)).save(meme)
    out1 = frames.compose(str(photo), str(tmp_path / "a.jpg"))
    im = Image.open(out1); assert im.size == (spec.CANVAS_W, spec.CANVAS_H)
    # 슬롯 안은 사진색, 슬롯 밖(제목 영역·자막 영역)은 검정
    assert im.getpixel((spec.SLOT_X + 10, spec.SLOT_Y + 10))[0] > 150
    assert im.getpixel((540, 200)) == (0, 0, 0) and im.getpixel((540, 1400)) == (0, 0, 0)
    assert im.getpixel((spec.SLOT_X - 5, spec.SLOT_Y + 100)) == (0, 0, 0)
    out2 = frames.compose(str(meme), str(tmp_path / "b.jpg"), kind="meme")
    im2 = Image.open(out2)
    # 밈은 슬롯 높이에 맞춰 가운데: 슬롯 좌우 끝은 검정, 가운데는 밈색
    assert im2.getpixel((540, spec.SLOT_Y + spec.SLOT_H // 2))[1] > 150
    assert im2.getpixel((spec.SLOT_X + 5, spec.SLOT_Y + 100)) == (0, 0, 0)


def test_frames_build_timeline_sums_to_total_and_uses_memes(tmp_path):
    meme_dir = tmp_path / "pepe"; meme_dir.mkdir()
    for n in ("013", "008"):
        Image.new("RGBA", (300, 300), (0, 0, 255, 255)).save(meme_dir / f"{n}.png")
    img = tmp_path / "01.png"; _png(img, (600, 400), (255, 255, 255))
    groups = [{"text": "하나", "color": "WHITE", "role": "NARR", "img": 1},
              {"text": "둘", "color": "RED", "role": "CHAR", "meme": "경악/충격"},
              {"text": "셋", "color": "RED", "role": "PUNCH", "meme": "무표정/멍"}]
    t = tmod.build(1.0, [1.0, 0.8, 1.2], groups)
    r = frames.build(str(tmp_path), t, {"groups": groups}, {"1": str(img)}, meme_dir=str(meme_dir))
    kinds = [x["kind"] for x in r["timeline"]]
    assert kinds == ["card", "img", "meme", "meme"]
    assert all(x["src"] for x in r["timeline"])                       # 카드는 슬롯1 사진, 밈 둘 다 파일 매핑됨
    s = open(r["list"], encoding="utf-8").read()
    durs = [float(x) for x in re.findall(r"duration ([\d.]+)", s)]
    assert abs(sum(durs) - t["total"]) < 1e-6


def test_generate_all_reuses_same_prompt(tmp_path):
    calls = []
    def gen(prompt, out):
        calls.append(prompt); _png(out, (64, 64), (1, 2, 3))
    p = {"1": "a", "2": "b"}
    images.generate_all(p, str(tmp_path), gen, log=lambda *a: None)
    images.generate_all(p, str(tmp_path), gen, log=lambda *a: None)          # 같은 프롬프트 → 재생성 없음
    assert len(calls) == 2
    images.generate_all({"1": "a", "2": "b2"}, str(tmp_path), gen, log=lambda *a: None)
    assert calls[-1] == "b2" and len(calls) == 3


def test_cast_goes_only_to_slots_that_name_it():
    """★cast는 **지정된 슬롯에만** 붙는다.

    실측 2026-09-13(볼케이노 3편): 주인공이 화면에 나오는 슬롯에만 달렸다(5/10 · 3/9 · 6/9).
    예전 우리 코드는 지정이 없으면 전체 cast를 모든 슬롯에 붙였고(`cast.get(k) or cast_all`),
    그 탓에 케냐 슬럼가·시장통 컷에까지 휠체어 탄 남자가 그려졌다
    (사장님 "이미지를 이렇게 쓰면 안되겠다. 전혀 다른게 나온다").
    """
    script = {"groups": [{"text": "x", "color": "WHITE", "role": "NARR", "img": 1},
                         {"text": "y", "color": "WHITE", "role": "NARR", "img": 2}]}
    raw = json.dumps({"cast": {"1": "a Korean man in his 50s"},          # 1번에만 지정
                      "prompts": {"1": "on a plane", "2": "airport ground crew unloading bags"}})
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert "a Korean man in his 50s" in r["prompts"]["1"]
    assert "a Korean man in his 50s" not in r["prompts"]["2"], "인물 없는 슬롯에 주인공이 붙었다"
    assert all(v.startswith(spec.IMAGE_PROMPT_PREFIX) for v in r["prompts"].values())


def test_cast_appears_twice_in_prompt():
    """cast는 장면 앞과 접미 직전에 **두 번** 들어간다(실측 볼케이노 전 슬롯)."""
    script = {"groups": [{"text": "x", "color": "WHITE", "role": "NARR", "img": 1}]}
    raw = json.dumps({"cast": {"1": "a Korean man in his 50s"}, "prompts": {"1": "on a plane"}})
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert r["prompts"]["1"].count("a Korean man in his 50s") == 2


def test_suffix_blocks_legible_numbers():
    """★접미 금지어 — 가짜 구독자 수·그래프가 그려지던 구멍(실측 2026-09-13 '1,000,000')."""
    for ban in ("no legible numbers or currency amounts", "not an illustration",
                "no legible words", "no logos", "no watermarks"):
        assert ban in spec.IMAGE_PROMPT_SUFFIX, ban


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음")
def test_pipeline_with_fake_images_and_memes_renders(tmp_path):
    import subprocess
    meme_dir = tmp_path / "pepe"; meme_dir.mkdir()
    Image.new("RGBA", (300, 300), (0, 0, 255, 255)).save(meme_dir / "013.png")
    s = {"title": {"h1": "제목 하나", "h2": "숫자 2개 들어간 둘째", "card": "오프닝 카드 문장은 이렇게 한 문장으로 간다"},
         "groups": [{"text": "첫 컷은 끝내지 않고", "color": "WHITE", "role": "NARR", "img": 1},
                    {"text": "둘째 컷이다", "color": "WHITE", "role": "NARR", "img": 1},
                    {"text": "진짜 대단하다", "color": "RED", "role": "CHAR", "meme": "경악/충격"},
                    {"text": "끝났다", "color": "RED", "role": "PUNCH", "meme": "경악/충격"}]}
    def tts(text, out):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={0.4 + 0.07 * len(text):.3f}",
                        "-ar", "44100", "-ac", "2", out], check=True, stdin=subprocess.DEVNULL)
    def gen(prompt, out): _png(out, (1248, 832), (120, 120, 200))
    llm_calls = []
    def llm(p):
        llm_calls.append(p)
        if "이미지 디렉터" in p:
            return json.dumps({"cast": {"1": "a man"}, "prompts": {"1": "a man on a plane"}})
        return json.dumps(s, ensure_ascii=False)
    r = pipeline.run_all(str(tmp_path / "job"), source_text="소재", llm=llm, tts=tts, imagegen=gen, meme_dir=str(meme_dir), log=lambda *a: None, min_cuts=1)
    assert r["status"] == "ok", r
    d = pipeline.load(str(tmp_path / "job"))["data"]
    assert d["images"]["files"]["1"].endswith("01.png")
    assert [x["kind"] for x in d["frames"]["timeline"]] == ["card", "img", "img", "meme", "meme"]
    assert d["review"]["ok"], d["review"]


def test_screen_orders_are_sent_back_for_rewrite():
    """★화면 주문은 판정으로 막되 **반려해서 다시 쓰게** 한다 — 조용히 갈아치우지 않는다.

    실측 2026-09-13(v5 슬롯9): "computer screen showing a social media profile with a
    downward trend line"이 접미 금지어 16개를 뚫고 **가짜 그래프**를 그렸다.
    지시문에 "화면을 주문하지 마라"가 이미 있었는데도 모델이 어겼다 → 판정이 필요하다.

    ★2026-09-14: 그런데 걸렸을 때 「빈 방」 문장으로 **통째로 갈아치우던 것**이 더 큰 병이었다.
      작성자는 자기 프롬프트가 버려진 걸 모르고 로그에도 안 남아, 최민식 편에서 돈 이야기
      세 컷이 사람 없는 현대식 사무실로 나갔다(1초·13초·30초가 같은 그림).
      → 볼케이노처럼 **반려 사유를 붙여 다시 쓰게** 하고, 고쳐 온 것을 쓴다.
    """
    script = {"groups": [{"text": "x", "color": "WHITE", "role": "NARR", "img": 1},
                         {"text": "y", "color": "WHITE", "role": "NARR", "img": 2}]}
    bad = json.dumps({"cast": {},
                      "prompts": {"1": "a computer screen showing a subscriber count dropping",
                                  "2": "a quiet alley at dusk with nobody around"}})
    good = json.dumps({"cast": {},
                       "prompts": {"1": "a woman staring at her hands on a kitchen table",
                                   "2": "a quiet alley at dusk with nobody around"}})
    seen = []

    def call(p):
        seen.append(p)
        return bad if len(seen) == 1 else good

    r = images.make_prompts(script, "소재", call, log=lambda *a: None)
    assert len(seen) == 2, "반려하고 다시 쓰게 하지 않았다"
    assert "슬롯 1" in seen[1], "어느 슬롯이 왜 반려됐는지 알려주지 않았다"
    assert "computer screen" not in r["prompts"]["1"].lower()
    assert "staring at her hands" in r["prompts"]["1"], "고쳐 온 프롬프트를 안 썼다"
    assert "quiet alley" in r["prompts"]["2"], "멀쩡한 장면까지 건드리면 안 된다"


def test_money_scenes_are_not_blocked():
    """★돈 이야기를 그릴 수 있어야 한다 — 낱말을 넓게 잡으면 편이 통째로 빈 방이 된다.

    실측 2026-09-14(최민식 편): numbers·percentage·counter 까지 막았더니 슬롯 9·11이 걸려
    「빈 사무실」이 세 컷 들어갔다. 자막은 «수수료를 30퍼센트 떼어 갔다» 였다.
    볼케이노는 이 자리에서 실사가 아닌 것을 주문하는 낱말만 막는다(서버 prompt_rules).
    """
    for t in ("a hand pulling several banknotes away from a thin stack on a desk",
              "a stack of 1980s banknotes bound with a paper band on a metal desk",
              "an old promissory note held between two fingers over a worn desk",
              "a young man counting bills in a cramped office"):
        assert not images._bad_words(t), t


def test_nonphoto_orders_are_caught():
    """실사 채널이므로 그림·만화 주문은 막는다(볼케이노가 막는 유일한 범주)."""
    for t in ("Cartoon frog with worried eyes",
              "a watercolor painting of an old street",
              "3d render of a stack of coins"):
        assert images._bad_words(t), t


def test_screen_words_cover_known_leaks():
    """실제로 샜던 표현이 목록에 있나."""
    for w in ("computer screen", "social media profile", "subscriber count", "trend line"):
        assert w in spec.PROMPT_SCREEN_WORDS, w


def test_scene_falls_back_to_gen_when_subtitle_needs_people():
    """★자막이 사람의 행동을 말하면 장소 검색으로 못 채운다.

    실측 2026-09-13(v5): «휠체어 타고 케냐 슬럼가를 찾았음»에 «케냐 슬럼가 골목»으로 검색해
    지붕만 찍힌 사진이, «사람들 도움을 받음»에는 깜깜한 빈 골목이 왔다.
    지시문에 "사람이 필요하면 gen으로"가 있었는데도 안 지켜져 판정을 붙였다.
    """
    script = {"groups": [{"text": "휠체어 타고 케냐", "color": "WHITE", "role": "NARR", "img": 1},
                         {"text": "슬럼가를 찾았음", "color": "WHITE", "role": "NARR", "img": 1},
                         {"text": "사건의 시작은", "color": "WHITE", "role": "NARR", "img": 2},
                         {"text": "열차 내 사고였음", "color": "WHITE", "role": "NARR", "img": 2}]}
    raw = json.dumps({"cast": {}, "prompts": {"1": "kenya alley", "2": "ktx platform"},
                      "sources": {"1": {"kind": "scene", "query": "케냐 슬럼가 골목"},
                                  "2": {"kind": "scene", "query": "KTX 승강장"}}})
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert r["sources"]["1"]["kind"] == "gen", "사람 행동 컷이 장소검색으로 갔다"
    assert r["sources"]["2"]["kind"] == "scene", "순수 장소 컷까지 막으면 안 된다"


def test_screen_words_cover_second_leak():
    """★2차 유출 — 낱말을 좁게 잡으면 계속 샌다.

    실측 2026-09-13(v6 슬롯11): «digital sign in a public space showing a downward trend icon
    and blurred numbers» → **신한투자증권 간판 + 종합주가지수 -2,866.93**이 그려졌다.
    실존 브랜드에 가짜 수치라 1차 유출(가짜 구독자 수)보다 나쁘다.

    ★2026-09-14: 이때 `numbers`·`ticker`·`stock`·`billboard`까지 넓혔던 것을 **되돌렸다** —
      그 낱말들이 돈 이야기를 통째로 막았기 때문이다(test_money_scenes_are_not_blocked).
      이 사고의 실제 주문은 «digital sign … showing …» 이었으므로 그 형태만 막으면 걸린다.
    """
    for w in ("digital sign", "display showing", "screen showing", "sign showing"):
        assert w in spec.PROMPT_SCREEN_WORDS, w
    # 그때 실제로 샜던 문장이 지금도 걸리는가 — 낱말 목록을 좁히고도 이건 잡혀야 한다
    leak = "digital sign in a public space showing a downward trend icon and blurred numbers"
    assert images._bad_words(leak), "2차 유출 문장이 안 걸린다"


def test_screen_words_do_not_catch_normal_scenes():
    """멀쩡한 장면까지 막으면 그림이 통째로 빈 방이 된다."""
    for t in ("a quiet alley at dusk with nobody around",
              "KTX station platform with a train arriving",
              "volunteers lifting a wheelchair up stone stairs",
              "a crowded street market in the afternoon"):
        assert not any(w in t.lower() for w in spec.PROMPT_SCREEN_WORDS), t


def test_overseas_slot_gets_its_own_locale():
    """★로케일을 한국으로 박으면 해외 장면이 한국으로 그려진다.

    실측 2026-09-13(v7 슬롯4): 케냐 슬럼가 계단 장면인데 접두가 "In South Korea"라
    **한국 지하철 계단에서 파란 조끼 자원봉사자들이 휠체어를 드는 그림**이 나왔다
    (사장님 "전체 맥락 없이 만든거야?"). 한 편 안에서도 나라가 갈린다.
    """
    script = {"region": {"region": "국내", "place": ""},
              "groups": [{"text": "케냐 계단", "color": "WHITE", "role": "NARR", "img": 1},
                         {"text": "KTX 사고", "color": "WHITE", "role": "NARR", "img": 2}]}
    raw = json.dumps({"cast": {}, "places": {"1": "Kenya", "2": ""},
                      "prompts": {"1": "volunteers lifting a wheelchair up stairs",
                                  "2": "a train station platform"}})
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert r["prompts"]["1"].startswith("In Kenya,"), r["prompts"]["1"][:40]
    assert "South Korea" not in r["prompts"]["1"], "해외 컷에 한국이 붙었다"
    assert r["prompts"]["2"].startswith(spec.IMAGE_LOCALE_DEFAULT), "국내 컷은 기본 로케일"


def test_script_region_overseas_applies_when_slot_has_no_place():
    """슬롯이 장소를 안 적었으면 대본의 region/place를 쓴다(볼케이노 보르네오 편 방식)."""
    script = {"region": {"region": "해외", "place": "인도네시아 보르네오"},
              "groups": [{"text": "산불", "color": "WHITE", "role": "NARR", "img": 1}]}
    raw = json.dumps({"cast": {}, "prompts": {"1": "burning peatland at dusk"}})
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert r["prompts"]["1"].startswith("In 인도네시아 보르네오,")
