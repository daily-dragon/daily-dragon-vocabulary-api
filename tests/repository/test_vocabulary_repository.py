import json
import time
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
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


def test_add_word_creates_sm2_fields(vocabulary_repo, mock_s3_client):
    """Test that new words are created with SM-2 fields, not adoption field."""
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"{}"))}

    vocabulary_repo.add_word(user_id, "test")

    body = mock_s3_client.put_object.call_args[1]["Body"]
    vocab_after = json.loads(body.decode())
    word_metadata = vocab_after["test"]

    # Verify SM-2 fields are present
    assert 'created_on' in word_metadata
    assert 'interval' in word_metadata
    assert 'repetition' in word_metadata
    assert 'ease_factor' in word_metadata
    assert 'next_review_date' in word_metadata
    assert 'last_review_date' in word_metadata

    # Verify adoption field is NOT present
    assert 'adoption' not in word_metadata

    # Verify default values
    assert word_metadata['interval'] == 0
    assert word_metadata['repetition'] == 0
    assert word_metadata['ease_factor'] == 2.5
    assert word_metadata['next_review_date'] is None
    assert word_metadata['last_review_date'] is None


def test_ensure_spaced_repetition_fields_migration(vocabulary_repo):
    """Test that ensure_spaced_repetition_fields migrates old data structure."""
    old_metadata = {
        'adoption': 5,
        'created_on': 123456789
    }

    migrated = vocabulary_repo.ensure_spaced_repetition_fields(old_metadata)

    # Verify adoption is removed
    assert 'adoption' not in migrated

    # Verify created_on is preserved
    assert migrated['created_on'] == 123456789

    # Verify SM-2 fields are added with defaults
    assert migrated['interval'] == 0
    assert migrated['repetition'] == 0
    assert migrated['ease_factor'] == 2.5
    assert migrated['next_review_date'] is None
    assert migrated['last_review_date'] is None


def test_ensure_spaced_repetition_fields_idempotent(vocabulary_repo):
    """Test that ensure_spaced_repetition_fields is idempotent (already migrated)."""
    already_migrated = {
        'created_on': 123456789,
        'interval': 6,
        'repetition': 2,
        'ease_factor': 2.6,
        'next_review_date': 987654321,
        'last_review_date': 987654000
    }

    result = vocabulary_repo.ensure_spaced_repetition_fields(already_migrated.copy())

    # Should remain unchanged
    assert result == already_migrated


def test_get_due_words_empty_vocabulary(vocabulary_repo, mock_s3_client):
    """Test get_due_words with empty vocabulary."""
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"{}"))}

    due_words = vocabulary_repo.get_due_words(user_id)

    assert due_words == []
    mock_s3_client.put_object.assert_not_called()


def test_get_due_words_all_new_words(vocabulary_repo, mock_s3_client):
    """Test get_due_words with new words (never reviewed)."""
    vocab = {
        "word1": {
            "created_on": int((datetime.now() - timedelta(days=5)).timestamp()),
            "interval": 0,
            "repetition": 0,
            "ease_factor": 2.5,
            "next_review_date": None,
            "last_review_date": None
        },
        "word2": {
            "created_on": int((datetime.now() - timedelta(days=2)).timestamp()),
            "interval": 0,
            "repetition": 0,
            "ease_factor": 2.5,
            "next_review_date": None,
            "last_review_date": None
        }
    }
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=json.dumps(vocab).encode()))
    }

    due_words = vocabulary_repo.get_due_words(user_id)

    mock_s3_client.put_object.assert_not_called()
    # Both words should be due (never reviewed)
    assert len(due_words) == 2
    # Older word should be first (more days_overdue)
    assert due_words[0]['word'] == 'word1'
    assert due_words[0]['metadata']['days_overdue'] >= 4
    assert due_words[1]['word'] == 'word2'


def test_get_due_words_respects_limit(vocabulary_repo, mock_s3_client):
    """Test that get_due_words respects the limit parameter."""
    # Create 10 due words
    vocab = {}
    for i in range(10):
        vocab[f"word{i}"] = {
            "created_on": int((datetime.now() - timedelta(days=i+1)).timestamp()),
            "interval": 0,
            "repetition": 0,
            "ease_factor": 2.5,
            "next_review_date": None,
            "last_review_date": None
        }

    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=json.dumps(vocab).encode()))
    }

    due_words = vocabulary_repo.get_due_words(user_id, limit=5)

    mock_s3_client.put_object.assert_not_called()
    assert len(due_words) == 5
    # Most overdue word first
    assert due_words[0]['metadata']['days_overdue'] >= due_words[1]['metadata']['days_overdue']


def test_get_due_words_mixed_due_and_not_due(vocabulary_repo, mock_s3_client):
    """Test get_due_words filters out words not yet due."""
    current_time = int(datetime.now().timestamp())
    vocab = {
        "due_word": {
            "created_on": current_time - 86400 * 5,
            "interval": 1,
            "repetition": 1,
            "ease_factor": 2.5,
            "next_review_date": current_time - 86400,  # 1 day overdue
            "last_review_date": current_time - 86400 * 2
        },
        "not_due_word": {
            "created_on": current_time - 86400 * 5,
            "interval": 1,
            "repetition": 1,
            "ease_factor": 2.5,
            "next_review_date": current_time + 86400,  # Due tomorrow
            "last_review_date": current_time
        }
    }
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=json.dumps(vocab).encode()))
    }

    due_words = vocabulary_repo.get_due_words(user_id)

    mock_s3_client.put_object.assert_not_called()
    assert len(due_words) == 1
    assert due_words[0]['word'] == 'due_word'
    assert due_words[0]['metadata']['days_overdue'] >= 1


def test_get_due_words_migrates_old_data(vocabulary_repo, mock_s3_client):
    """Test that get_due_words automatically migrates old vocabulary format."""
    old_vocab = {
        "old_word": {
            "adoption": 5,
            "created_on": int((datetime.now() - timedelta(days=3)).timestamp())
        }
    }
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=json.dumps(old_vocab).encode()))
    }

    due_words = vocabulary_repo.get_due_words(user_id)

    # Migration should have been persisted to S3
    mock_s3_client.put_object.assert_called_once()
    assert len(due_words) == 1
    metadata = due_words[0]['metadata']

    assert 'adoption' not in metadata
    assert metadata['interval'] == 0
    assert metadata['repetition'] == 0
    assert metadata['ease_factor'] == 2.5
    assert metadata['next_review_date'] is None
