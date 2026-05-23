from datetime import timedelta

from app.backend.services.support_delivery import delivery_backoff


def test_delivery_backoff_is_exponential_and_capped():
    assert delivery_backoff(0) == timedelta(seconds=30)
    assert delivery_backoff(1) == timedelta(seconds=60)
    assert delivery_backoff(20) == timedelta(seconds=3600)
