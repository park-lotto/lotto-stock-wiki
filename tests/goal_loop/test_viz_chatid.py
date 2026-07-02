import inspect
from scripts import viz_card

def test_send_telegram_photo_has_chat_id_param():
    sig = inspect.signature(viz_card.send_telegram_photo)
    assert "chat_id" in sig.parameters
    assert sig.parameters["chat_id"].default is None
