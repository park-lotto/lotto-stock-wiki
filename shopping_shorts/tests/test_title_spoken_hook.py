"""제목형 유튜브 템플릿의 화면/음성 경계를 잠근다."""
from shopping_shorts import bank_assemble


def _legacy_style():
    return {
        "id": 60,
        "name": "유튜브 「OO 개발자도 무릎 탁」",
        "beat_roles": ["title", "story", "benefit"],
        "beat_chain": ["화면 제목", "탄생 사연", "핵심 효과"],
        "templates": {
            "title": ["{나라} 개발자도 놀란 {제품}"],
            "story": ["{계기} 때문에 만들었다"],
            "benefit": ["핵심은 {효능}"],
        },
    }


def test_옛_제목형은_화면제목_첫tts후킹_본문으로_보강된다():
    old = _legacy_style()
    got = bank_assemble.with_spoken_hook(old)

    assert got["beat_roles"] == ["title", "hook", "story", "benefit"]
    assert got["title_visual_only"] is True
    assert "첫 TTS" in got["beat_descs"]["hook"]
    assert "되풀이하지" in got["beat_descs"]["hook"]
    assert got["templates"]["hook"] == []
    assert old["beat_roles"] == ["title", "story", "benefit"], "DB 원본을 제자리에서 바꾸면 안 된다"


def test_이미_첫tts후킹이_있으면_두번_끼우지_않는다():
    style = bank_assemble.with_spoken_hook(_legacy_style())
    assert bank_assemble.with_spoken_hook(style) is style


def test_일반_첫대사형은_건드리지_않는다():
    style = {"beat_roles": ["hook", "proof"], "templates": {}}
    assert bank_assemble.with_spoken_hook(style) is style


def test_생성_프롬프트에도_첫tts칸이_본문_앞에_고정된다():
    block = bank_assemble.style_block(
        bank_assemble.with_spoken_hook(_legacy_style()), seconds=25)
    assert block.index('role="title"') < block.index('role="hook"') < block.index('role="story"')
    assert "화면 제목을 소리 내어 되풀이하지 말고" in block

