"""Shared pytest fixtures for all test suites."""

import pytest


@pytest.fixture(scope="session")
def fhir_base_url() -> str:
    return "http://localhost:8080/fhir/r4"


@pytest.fixture(scope="session")
def payer_cds_url() -> str:
    return "http://localhost:3001"


@pytest.fixture(scope="session")
def payer_dtr_url() -> str:
    return "http://localhost:3002"


@pytest.fixture(scope="session")
def payer_pas_url() -> str:
    return "http://localhost:3003"
