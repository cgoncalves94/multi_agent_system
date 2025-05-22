import pytest
from httpx import AsyncClient
from src.backend.app import (
    app,
)  # Assuming your FastAPI app instance is named 'app' in main.py or app.py


@pytest.fixture(scope="session")
def client():
    # Use TestClient for synchronous tests if needed, though AsyncClient is preferred for FastAPI
    # For this example, focusing on AsyncClient as FastAPI is async-first
    # If you have synchronous endpoints or prefer TestClient for some tests:
    # with TestClient(app) as c:
    #     yield c
    # This fixture might not be used if all tests are async
    pass


@pytest.fixture(
    scope="function"
)  # Use "function" scope for async client if tests need isolation
async def async_client():
    async with AsyncClient(
        app=app, base_url="http://127.0.0.1:8000"
    ) as ac:  # Ensure base_url matches your test server setup
        yield ac


# If you need to override dependencies for testing, you can do it here.
# For example, mocking an external service client:
# from src.backend.services import ExternalServiceClient
# from unittest.mock import MagicMock

# @pytest.fixture
# def mock_external_service():
#     mock = MagicMock(spec=ExternalServiceClient)
#     # Configure your mock further if needed
#     return mock

# app.dependency_overrides[ExternalServiceClient] = lambda: mock_external_service
