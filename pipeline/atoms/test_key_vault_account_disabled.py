from pipeline.atoms import key_vault


def test_is_account_disabled_error_detects_unauthenticated():
    exc = Exception(
        "401 UNAUTHENTICATED. {'error': {'code': 401, 'message': "
        "'The bound service account is deleted or disabled.', "
        "'status': 'UNAUTHENTICATED', 'details': [{'reason': 'ACCOUNT_STATE_INVALID'}]}}"
    )
    assert key_vault.is_account_disabled_error(exc) is True


def test_is_account_disabled_error_false_for_quota_error():
    exc = Exception("429 RESOURCE_EXHAUSTED. PerDay limit reached")
    assert key_vault.is_account_disabled_error(exc) is False


def test_is_account_disabled_error_false_for_unrelated_error():
    exc = Exception("500 Internal Server Error")
    assert key_vault.is_account_disabled_error(exc) is False
