import sys

import pytest
from shopping_shorts import scene_style
from shopping_shorts.scene_style import context_for, validate_snapshot


def test_branding_is_saved_and_size_is_bounded():
    saved={"mode":"story","presetId":"t11","branding":{"watermark":{"on":True,"text":"@channel","x":10,"y":80,"size":3,"opacity":65,"color":"#ffffff"}}}
    assert validate_snapshot(saved)["branding"]==saved["branding"]
    saved["branding"]["watermark"]["size"]=100
    with pytest.raises(ValueError):
        validate_snapshot(saved)


def test_caption_mask_placement_survives_validation():
    saved={"mode":"story","presetId":"t11","captionLayouts":{"t11:story:1:caption":{"placement":"free","w":80,"h":12,"background":"#ffffff","color":"#111111"}}}
    assert validate_snapshot(saved)["captionLayouts"]==saved["captionLayouts"]
    saved["captionLayouts"]["t11:story:1:caption"]["h"]=90
    with pytest.raises(ValueError):
        validate_snapshot(saved)


def test_real_caption_gaps_and_hook_beat_are_preserved():
    timeline=[{"beat_idx":7,"t0":0,"dur":2,"narration":"첫 줄 다음 줄","caption_lines":["첫 줄","다음 줄"],"cap_durs":[.7,1.1],"cap_lead":.2},
              {"beat_idx":9,"t0":2,"dur":1,"narration":"본문","caption_lines":["본문"]}]
    context=context_for(timeline,{"text":"실제 제목\n둘째 제목"})
    # 2026-09-21 사장님 제보 "4번 장면 본문 첫인데 자막에 글자가 없고 5번부터 시작된다".
    #   자막 리드(cap_lead)만큼의 자투리를 독립 장면으로 세우면 장면 번호가 밀려, 편집기에서
    #   글자 없는 장면을 넘겨야 한다. 실측(최근 job 25개, 빈 자막 장면 70개): 최대 0.52초로
    #   사실상 전부 자투리였다 → 이웃 구절이 삼킨다(scene_style._MIN_SILENT_SCENE).
    #   ★이 테스트가 지키는 본질은 **시간축과 훅/본문 구분**이다 — 그건 그대로 검사한다.
    assert [s['caption'] for s in context['scenes']]==['첫 줄','다음 줄','본문']
    assert [s['kind'] for s in context['scenes']]==['hook','hook','body']
    assert context['scenes'][0]['start']==0       # 리드가 앞 장면에 흡수돼 빈틈이 없다
    assert context['scenes'][-1]['end']==3
    assert context['text']['hook1']=='실제 제목'
    assert context['text']['hook2']=='둘째 제목'


def test_scene_context_uses_paired_subline_for_even_body_structure():
    timeline=[{"beat_idx":0,"t0":0,"dur":1,"narration":"훅"},
              {"beat_idx":1,"t0":1,"dur":1,"narration":"본문"}]
    context=context_for(timeline,{"text":"건망증 환자를 살려낸\n일본 천재의 발명품",
                                  "subline":"건망증 환자를 살려낸 발명품?"})
    assert context["text"]["hook1"] == "건망증 환자를 살려낸"
    assert context["text"]["hook2"] == "일본 천재의 발명품"
    assert context["text"]["bodyTitle"] == "건망증 환자를 살려낸 발명품?"
    assert context["text"]["supportTitle"] == context["text"]["bodyTitle"]


def test_linux_layer_render_enables_chrome_no_sandbox(monkeypatch, tmp_path):
    """운영 Linux에서 user namespace가 막혀도 Chrome 레이어 렌더가 시작돼야 한다."""
    captured = {}

    def fake_run(_cmd, **kwargs):
        captured.update(kwargs)
        (tmp_path / "scene-style-layers.json").write_text("[]", encoding="utf-8")

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("SCENE_STYLE_NO_SANDBOX", raising=False)
    monkeypatch.setattr(scene_style.subprocess, "run", fake_run)

    scene_style.render_layers(
        [{"beat_idx": 0, "t0": 0, "dur": 1, "narration": "훅"}],
        {"mode": "story", "presetId": "t11"},
        tmp_path,
    )

    assert captured["env"]["SCENE_STYLE_NO_SANDBOX"] == "1"


@pytest.mark.parametrize('extra',[
    {'colors':{'x':'url(https://example.com/a)'}},
    {'fontScales':{'x':float('nan')}},
    {'fontScales':{'x':9000}},
    {'fixedLayouts':{'x':{'top':50,'bottom':35}}},
    {'effects':{'0':{'highlight':'invalid'}}},
    {'text':{'hook1':{'nested':'not text'}}},
])
def test_invalid_saved_configuration_is_rejected(extra):
    with pytest.raises(ValueError):
        validate_snapshot({'mode':'story','presetId':'t11',**extra})


def test_레이어_제한시간은_영상길이에_비례한다():
    """2026-09-17: 29.7초 영상이 245초 걸려 고정 240초 제한에 세 번 연속 잘렸다."""
    from shopping_shorts.scene_style import _layer_render_timeout as t
    assert t({"scenes": [{"end": 5}]}) == 240            # 짧으면 종전 그대로
    assert t({"scenes": [{"end": 29.7}]}) > 245 + 60     # 실측 245초에 여유
    assert t({"scenes": [{"end": 600}]}) == 900          # 상한
    assert t({}) == 240
