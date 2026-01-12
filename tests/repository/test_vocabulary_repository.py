import json
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from daily_dragon.exceptions import WordAlreadyExistsError
from daily_dragon.repository.vocabulary_repository import VocabularyRepository

user_id = "user_id"


@pytest.fixture
def mock_s3_client():
    return MagicMock()


@pytest.fixture
def repo_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "my-test-bucket")
    monkeypatch.setenv("S3_FILE_PATH", "vocab.json")


@pytest.fixture
def vocabulary_repo(mock_s3_client, repo_env):
    with patch("boto3.client", return_value=mock_s3_client):
        return VocabularyRepository()


def test_get_vocabulary_success(vocabulary_repo, mock_s3_client):
    body = json.dumps({"hello": {"adoption": 1, "created_on": 1234567890}}).encode("utf-8")
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=body))}

    vocab = vocabulary_repo.get_vocabulary(user_id)

    assert "hello" in vocab
    mock_s3_client.get_object.assert_called_once_with(Bucket='my-test-bucket', Key='user_id_vocabulary.json')


def test_get_vocabulary_no_such_key(vocabulary_repo, mock_s3_client):
    error = ClientError(
        error_response={"Error": {"Code": "NoSuchKey"}},
        operation_name="GetObject"
    )
    mock_s3_client.get_object.side_effect = error

    vocab = vocabulary_repo.get_vocabulary(user_id)

    assert vocab == {}


def test_get_vocabulary_other_error(vocabulary_repo, mock_s3_client):
    error = ClientError(
        error_response={"Error": {"Code": "AccessDenied"}},
        operation_name="GetObject"
    )
    mock_s3_client.get_object.side_effect = error

    with pytest.raises(ClientError):
        vocabulary_repo.get_vocabulary(user_id)


def test_save_vocabulary(vocabulary_repo, mock_s3_client):
    test_vocab = {"test": {"adoption": 0, "created_on": 123}}

    vocabulary_repo.save_vocabulary(user_id, test_vocab)

    mock_s3_client.put_object.assert_called_once()
    _, kwargs = mock_s3_client.put_object.call_args
    assert kwargs["Bucket"] == "my-test-bucket"
    assert kwargs["Key"] == "user_id_vocabulary.json"
    assert json.loads(kwargs["Body"].decode("utf-8")) == test_vocab


def test_add_word_success(vocabulary_repo, mock_s3_client):
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"{}"))}

    vocabulary_repo.add_word(user_id, "新词")

    mock_s3_client.put_object.assert_called_once()
    body = mock_s3_client.put_object.call_args[1]["Body"]
    vocab_after = json.loads(body.decode())
    assert "新词" in vocab_after


def test_add_word_already_exists(vocabulary_repo, mock_s3_client):
    existing_vocab = {"重复": {"adoption": 0, "created_on": 123456}}
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=json.dumps(existing_vocab).encode()))
    }

    with pytest.raises(WordAlreadyExistsError):
        vocabulary_repo.add_word(user_id, "重复")
