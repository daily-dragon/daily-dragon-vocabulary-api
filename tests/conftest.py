import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from daily_dragon.auth.cognito import cognito_auth, DailyDragonCognitoToken
from daily_dragon.daily_dragon_app import app
from daily_dragon.service.settings_service import SettingsService
from daily_dragon.service.vocabulary_service import VocabularyService

def dummy_auth():
    return DailyDragonCognitoToken.model_validate({
        "aud": "test-aud",
        "sub": "test-sub",
        "email": "test@example.com",
        "cognito:username": "testuser",
        "email_verified": True,
        "token_use": "id"
    })

@pytest.fixture
def mock_service():
    return MagicMock()


@pytest.fixture
def mock_settings_service():
    return MagicMock()


@pytest.fixture
def test_client(mock_service, mock_settings_service):
    app.dependency_overrides = dict()
    app.dependency_overrides[VocabularyService] = lambda: mock_service
    app.dependency_overrides[SettingsService] = lambda: mock_settings_service
    app.dependency_overrides[cognito_auth.auth_required] = lambda: dummy_auth()

    client = TestClient(app)
    yield client

    app.dependency_overrides = {}
