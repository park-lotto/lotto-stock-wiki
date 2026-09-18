from shopping_shorts import app as appmod


def test_landing_footer_shows_mail_order_registration(monkeypatch):
    class EmptySettingsStore:
        def __init__(self, _path):
            pass

        def get_setting(self, _key, _default=""):
            return ""

    monkeypatch.setattr(appmod, "Store", EmptySettingsStore)

    html = appmod._with_pay(appmod._LANDING_HTML)

    assert "통신판매업신고 2026-용인수지-3213" in html
