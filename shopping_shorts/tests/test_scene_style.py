import pytest
from shopping_shorts.scene_style import context_for, validate_snapshot


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
    assert [s['caption'] for s in context['scenes']]==['','첫 줄','다음 줄','본문']
    assert [s['kind'] for s in context['scenes']]==['hook','hook','hook','body']
    assert context['scenes'][0]['end']==.2
    assert context['scenes'][-1]['end']==3
    assert context['text']['hook1']=='실제 제목'
    assert context['text']['hook2']=='둘째 제목'


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
