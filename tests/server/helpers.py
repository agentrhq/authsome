"""Shared helpers for server route tests."""

from fastapi.testclient import TestClient

from authsome.server.app import create_app
from tests.conftest import TEST_AUTHSOME_BASE_URL


def create_server_test_client() -> TestClient:
    """Create a TestClient using the daemon base URL configured for tests."""
    return TestClient(create_app(), base_url=TEST_AUTHSOME_BASE_URL)
