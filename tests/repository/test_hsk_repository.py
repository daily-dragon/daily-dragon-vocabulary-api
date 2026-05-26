import json
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from daily_dragon.repository.hsk_repository import HskRepository

HSK_LEVEL = 1
HSK_WORDS = ["一", "二", "三", "你好", "谢谢"]


@pytest.fixture
def mock_s3_client():
    return MagicMock()


@pytest.fixture
def repo_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "my-test-bucket")


@pytest.fixture
def hsk_repo(mock_s3_client, repo_env):
    with patch("boto3.client", return_value=mock_s3_client):
        return HskRepository()


def test_get_hsk_words_success(hsk_repo, mock_s3_client):
    body = json.dumps(HSK_WORDS).encode("utf-8")
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=body))}

    words = hsk_repo.get_hsk_words(HSK_LEVEL)

    assert words == HSK_WORDS
    mock_s3_client.get_object.assert_called_once_with(
        Bucket="my-test-bucket", Key="hsk/hsk1.json"
    )


def test_get_hsk_words_level_7(hsk_repo, mock_s3_client):
    body = json.dumps(["一丁点儿"]).encode("utf-8")
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=body))}

    hsk_repo.get_hsk_words(7)

    mock_s3_client.get_object.assert_called_once_with(
        Bucket="my-test-bucket", Key="hsk/hsk7.json"
    )


def test_get_hsk_words_no_such_key_raises_value_error(hsk_repo, mock_s3_client):
    error = ClientError(
        error_response={"Error": {"Code": "NoSuchKey"}},
        operation_name="GetObject"
    )
    mock_s3_client.get_object.side_effect = error

    with pytest.raises(ValueError, match="HSK level 99 not found"):
        hsk_repo.get_hsk_words(99)


def test_get_hsk_words_other_error_reraises(hsk_repo, mock_s3_client):
    error = ClientError(
        error_response={"Error": {"Code": "AccessDenied"}},
        operation_name="GetObject"
    )
    mock_s3_client.get_object.side_effect = error

    with pytest.raises(ClientError):
        hsk_repo.get_hsk_words(1)
