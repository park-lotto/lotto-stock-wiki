from shopping_shorts import vmake_client as vc


def test_sign_deterministic():
    a = vc._sign("appkey", "secret", "1700000000", "nonce123")
    b = vc._sign("appkey", "secret", "1700000000", "nonce123")
    assert a == b
    assert isinstance(a, str) and len(a) >= 16


def test_sign_changes_with_input():
    base = vc._sign("appkey", "secret", "1700000000", "n1")
    assert base != vc._sign("appkey", "secret", "1700000000", "n2")
    assert base != vc._sign("appkey", "secret", "1700000001", "n1")
    assert base != vc._sign("appkey", "other", "1700000000", "n1")


def test_auth_headers_shape():
    h = vc._auth_headers("appkey", "secret", timestamp="1700000000", nonce="n1")
    assert h["X-App-Key"] == "appkey"
    assert h["X-Timestamp"] == "1700000000"
    assert h["X-Nonce"] == "n1"
    assert "X-Sign" in h and h["X-Sign"]
