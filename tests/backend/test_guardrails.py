"""Tests for content guardrails — prompt injection and category coverage."""
from backend.app.safety.guardrails import GUARDRAIL_RULES, build_response_system_prompt

def test_guardrail_rules_covers_legal_advice():
    assert "legal" in GUARDRAIL_RULES.lower()

def test_guardrail_rules_covers_medical_advice():
    assert "medical" in GUARDRAIL_RULES.lower()

def test_guardrail_rules_covers_financial_advice():
    assert "financial" in GUARDRAIL_RULES.lower()

def test_guardrail_rules_covers_county_promise():
    assert "commit" in GUARDRAIL_RULES.lower() or "promise" in GUARDRAIL_RULES.lower()

def test_guardrail_rules_covers_third_party_pii():
    assert "personal information" in GUARDRAIL_RULES.lower() or "third" in GUARDRAIL_RULES.lower()

def test_build_response_system_prompt_contains_base():
    base = "You are a helpful assistant."
    result = build_response_system_prompt(base)
    assert "You are a helpful assistant." in result

def test_build_response_system_prompt_appends_guardrails():
    base = "You are a helpful assistant."
    result = build_response_system_prompt(base)
    assert "PROHIBITED" in result
    assert len(result) > len(base)
