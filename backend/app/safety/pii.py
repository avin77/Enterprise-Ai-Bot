"""
backend/app/safety/pii.py
PII detection and scrubbing using Microsoft Presidio.
Two passes: scrub_input (before pipeline) and scrub_output (before sending to user).
Models are pre-loaded at startup via preload_models() — never loaded per-request.
"""
from __future__ import annotations

_analyzer = None
_anonymizer = None

PII_ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN",
    "US_DRIVER_LICENSE", "US_PASSPORT", "US_BANK_NUMBER",
    "CREDIT_CARD", "LOCATION",
]

def preload_models() -> None:
    global _analyzer, _anonymizer
    if _analyzer is not None:
        return
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    _analyzer = AnalyzerEngine()
    _anonymizer = AnonymizerEngine()

def _scrub(text: str) -> tuple[str, list[str]]:
    if _analyzer is None or _anonymizer is None:
        preload_models()
    results = _analyzer.analyze(text=text, entities=PII_ENTITIES, language="en")
    if not results:
        return text, []
    scrubbed = _anonymizer.anonymize(text=text, analyzer_results=results)
    detected = list({r.entity_type for r in results})
    return scrubbed.text, detected

def scrub_input(text: str) -> tuple[str, list[str]]:
    return _scrub(text)

def scrub_output(text: str) -> tuple[str, list[str]]:
    return _scrub(text)
