from app.config import get_settings


def test_defaults():
    s = get_settings()
    assert s.model == "claude-sonnet-4-6"
    assert s.price_input_per_mtok == 3.0
    assert s.price_output_per_mtok == 15.0
    assert s.refund_window_days == 30
    assert s.escalation_threshold == 500.0
