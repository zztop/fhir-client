"""Unit tests for pydantic-settings config."""

import os

import pytest

from src.config import Settings


def test_defaults_load_without_env_file():
    s = Settings(_env_file=None)
    assert s.fhir_base_url == "http://localhost:8080/fhir/r4"
    assert s.port_cds == 3001
    assert s.port_dtr == 3002
    assert s.port_pas == 3003
    assert s.log_level == "INFO"
    assert s.pend_delay_seconds == 0
    assert s.enable_auth is False


def test_env_overrides_are_applied(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FHIR_BASE_URL", "http://custom-fhir:9090/fhir/r4")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PEND_DELAY_SECONDS", "5")
    s = Settings(_env_file=None)
    assert s.fhir_base_url == "http://custom-fhir:9090/fhir/r4"
    assert s.log_level == "DEBUG"
    assert s.pend_delay_seconds == 5


def test_enable_auth_parses_bool(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_AUTH", "true")
    s = Settings(_env_file=None)
    assert s.enable_auth is True
