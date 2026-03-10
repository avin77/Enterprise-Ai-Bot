# tests/backend/test_conversation.py
"""
Wave 0 stubs for VOIC-03 (conversation session tracking).
Status: PENDING -- skipped until Plan 01-03 implements the modules.
"""
import pytest


def test_slo_flag_set_on_turn_write():
    """write_conversation_turn sets slo_met=True when total_ms < 1500, False otherwise.
    Skipped until Plan 01-03 creates backend/app/services/conversation.py.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented in Plan 01-03.")
