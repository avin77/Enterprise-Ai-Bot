"""Tests for PII scrubber — input and output passes."""
import pytest
from backend.app.safety.pii import scrub_input, scrub_output, preload_models

preload_models()

def test_scrub_ssn_in_input():
    text = "My SSN is 456-78-9012, can I apply for a tax exemption?"
    scrubbed, entities = scrub_input(text)
    assert "456-78-9012" not in scrubbed
    assert "US_SSN" in entities

def test_scrub_phone_in_input():
    text = "Call me at 816-555-1234 to confirm."
    scrubbed, entities = scrub_input(text)
    assert "816-555-1234" not in scrubbed
    assert "PHONE_NUMBER" in entities

def test_scrub_email_in_input():
    text = "Email me at john.doe@example.com"
    scrubbed, entities = scrub_input(text)
    assert "john.doe@example.com" not in scrubbed
    assert "EMAIL_ADDRESS" in entities

def test_no_pii_passes_through():
    text = "How do I apply for a building permit?"
    scrubbed, entities = scrub_input(text)
    assert scrubbed == text
    assert entities == []

def test_scrub_output_same_behaviour():
    text = "Please send your SSN 456-78-9012 to the county clerk."
    scrubbed, entities = scrub_output(text)
    assert "456-78-9012" not in scrubbed
    assert "US_SSN" in entities

def test_scrub_returns_placeholder_not_empty():
    text = "My SSN is 456-78-9012"
    scrubbed, _ = scrub_input(text)
    assert "<" in scrubbed and ">" in scrubbed
