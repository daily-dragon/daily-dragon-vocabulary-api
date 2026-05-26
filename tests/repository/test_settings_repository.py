import json
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from daily_dragon.repository.settings_repository import SettingsRepository

user_id = "user_id"


@pytest.fixture
def mock_s3_client():
    return MagicMock()


@pytest.fixture
def repo_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "my-test-bucket")


@pytest.fixture
def settings_repo(mock_s3_client, repo_env):
    with patch("boto3.client", return_value=mock_s3_client):
        return SettingsRepository()


def test_get_settings_success(settings_repo, mock_s3_client):
    body = json.dumps({"hsk_level": 2, "placement_completed": True}).encode("utf-8")
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=body))}

    settings = settings_repo.get_settings(user_id)

    assert settings == {"hsk_level": 2, "placement_completed": True}
    mock_s3_client.get_object.assert_called_once_with(Bucket="my-test-bucket", Key="user_id_settings.json")


def test_get_settings_no_such_key_creates_defaults(settings_repo, mock_s3_client):
    error = ClientError(
        error_response={"Error": {"Code": "NoSuchKey"}},
        operation_name="GetObject"
    )
    mock_s3_client.get_object.side_effect = error

    settings = settings_repo.get_settings(user_id)

    assert settings == {"hsk_level": 1, "placement_completed": False}
    mock_s3_client.put_object.assert_called_once()
    _, kwargs = mock_s3_client.put_object.call_args
    assert kwargs["Key"] == "user_id_settings.json"


def test_get_settings_other_error_reraises(settings_repo, mock_s3_client):
    error = ClientError(
        error_response={"Error": {"Code": "AccessDenied"}},
        operation_name="GetObject"
    )
    mock_s3_client.get_object.side_effect = error

    with pytest.raises(ClientError):
        settings_repo.get_settings(user_id)


def test_save_settings(settings_repo, mock_s3_client):
    settings = {"hsk_level": 3, "placement_completed": True}

    settings_repo.save_settings(user_id, settings)

    mock_s3_client.put_object.assert_called_once()
    _, kwargs = mock_s3_client.put_object.call_args
    assert kwargs["Bucket"] == "my-test-bucket"
    assert kwargs["Key"] == "user_id_settings.json"
    assert json.loads(kwargs["Body"].decode("utf-8")) == settings
