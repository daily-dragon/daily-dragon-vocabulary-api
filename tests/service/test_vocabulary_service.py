import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from daily_dragon.service.vocabulary_service import VocabularyService

user_id = "user_id"


@pytest.fixture
def mock_repository():
    mock = MagicMock()
    mock.get_vocabulary.return_value = {
        "学习": {"adoption": 0, "date_added": "2025-04-08"},
        "大众": {"adoption": 1, "date_added": "2025-04-01"},
    }
    return mock


def test_add_word(mock_repository):
    service = VocabularyService(vocabulary_repository=mock_repository)
    service.add_word(user_id, "测试")
    mock_repository.add_word.assert_called_once_with(user_id, "测试")


def test_get_vocabulary(mock_repository):
    service = VocabularyService(vocabulary_repository=mock_repository)
    vocabulary = service.get_vocabulary(user_id)
    assert vocabulary == mock_repository.get_vocabulary.return_value
    mock_repository.get_vocabulary.assert_called_once_with(user_id)


def test_delete_word_exists(mock_repository):
    service = VocabularyService(vocabulary_repository=mock_repository)

    service.delete_word(user_id, "大众")

    updated_vocab = {
        "学习": {"adoption": 0, "date_added": "2025-04-08"},
    }
    mock_repository.save_vocabulary.assert_called_once_with(user_id, updated_vocab)


def test_delete_word_not_exists(mock_repository):
    service = VocabularyService(vocabulary_repository=mock_repository)

    service.delete_word(user_id, "不存在的词")

    mock_repository.save_vocab.assert_not_called()


def test_get_due_words(mock_repository):
    """Test get_due_words delegates to repository and formats response."""
    due_words_data = [
        {
            'word': 'word1',
            'metadata': {
                'created_on': 123456,
                'interval': 0,
                'repetition': 0,
                'ease_factor': 2.5,
                'next_review_date': None,
                'last_review_date': None,
                'days_overdue': 5
            }
        }
    ]
    mock_repository.get_due_words.return_value = due_words_data

    service = VocabularyService(vocabulary_repository=mock_repository)
    result = service.get_due_words(user_id)

    mock_repository.get_due_words.assert_called_once_with(user_id, limit=5)
    assert result['due_words'] == due_words_data
    assert result['total_due'] == 1
    assert result['returned'] == 1


def test_record_reviews_all_valid(mock_repository):
    """Test record_reviews with all valid reviews."""
    vocab = {
        'word1': {
            'created_on': 123456,
            'interval': 0,
            'repetition': 0,
            'ease_factor': 2.5,
            'next_review_date': None,
            'last_review_date': None
        },
        'word2': {
            'created_on': 123457,
            'interval': 1,
            'repetition': 1,
            'ease_factor': 2.5,
            'next_review_date': 123500,
            'last_review_date': 123450
        }
    }
    mock_repository.get_vocabulary.return_value = vocab
    mock_repository.ensure_spaced_repetition_fields.side_effect = lambda x: x

    service = VocabularyService(vocabulary_repository=mock_repository)
    reviews = [
        {'word': 'word1', 'quality': 5},
        {'word': 'word2', 'quality': 4}
    ]

    result = service.record_reviews(user_id, reviews)

    # Verify response structure
    assert result['total_processed'] == 2
    assert result['successful'] == 2
    assert result['failed'] == 0
    assert len(result['results']) == 2

    # Verify all results are successful
    for res in result['results']:
        assert res['success'] is True
        assert 'next_review_date' in res
        assert 'interval' in res

    # Verify save was called once
    mock_repository.save_vocabulary.assert_called_once()


def test_record_reviews_invalid_quality(mock_repository):
    """Test record_reviews with invalid quality ratings."""
    vocab = {
        'word1': {
            'created_on': 123456,
            'interval': 0,
            'repetition': 0,
            'ease_factor': 2.5,
            'next_review_date': None,
            'last_review_date': None
        }
    }
    mock_repository.get_vocabulary.return_value = vocab
    mock_repository.ensure_spaced_repetition_fields.side_effect = lambda x: x

    service = VocabularyService(vocabulary_repository=mock_repository)
    reviews = [
        {'word': 'word1', 'quality': 6},  # Too high
        {'word': 'word1', 'quality': -1},  # Too low
        {'word': 'word1', 'quality': 'invalid'}  # Wrong type
    ]

    result = service.record_reviews(user_id, reviews)

    assert result['total_processed'] == 3
    assert result['successful'] == 0
    assert result['failed'] == 3

    for res in result['results']:
        assert res['success'] is False
        assert 'Quality must be between 0 and 5' in res['error']

    # Verify save was NOT called (no successful reviews)
    mock_repository.save_vocabulary.assert_not_called()


def test_record_reviews_word_not_found(mock_repository):
    """Test record_reviews with word not in vocabulary."""
    vocab = {
        'word1': {
            'created_on': 123456,
            'interval': 0,
            'repetition': 0,
            'ease_factor': 2.5,
            'next_review_date': None,
            'last_review_date': None
        }
    }
    mock_repository.get_vocabulary.return_value = vocab
    mock_repository.ensure_spaced_repetition_fields.side_effect = lambda x: x

    service = VocabularyService(vocabulary_repository=mock_repository)
    reviews = [
        {'word': 'nonexistent', 'quality': 5}
    ]

    result = service.record_reviews(user_id, reviews)

    assert result['total_processed'] == 1
    assert result['successful'] == 0
    assert result['failed'] == 1
    assert result['results'][0]['success'] is False
    assert 'Word not found in vocabulary' in result['results'][0]['error']

    # Verify save was NOT called
    mock_repository.save_vocabulary.assert_not_called()


def test_record_reviews_mixed_valid_invalid(mock_repository):
    """Test record_reviews with mix of valid and invalid reviews."""
    vocab = {
        'word1': {
            'created_on': 123456,
            'interval': 0,
            'repetition': 0,
            'ease_factor': 2.5,
            'next_review_date': None,
            'last_review_date': None
        },
        'word2': {
            'created_on': 123457,
            'interval': 1,
            'repetition': 1,
            'ease_factor': 2.5,
            'next_review_date': 123500,
            'last_review_date': 123450
        }
    }
    mock_repository.get_vocabulary.return_value = vocab
    mock_repository.ensure_spaced_repetition_fields.side_effect = lambda x: x

    service = VocabularyService(vocabulary_repository=mock_repository)
    reviews = [
        {'word': 'word1', 'quality': 5},  # Valid
        {'word': 'nonexistent', 'quality': 4},  # Word not found
        {'word': 'word2', 'quality': 10},  # Invalid quality
        {'word': 'word2', 'quality': 3}  # Valid
    ]

    result = service.record_reviews(user_id, reviews)

    assert result['total_processed'] == 4
    assert result['successful'] == 2
    assert result['failed'] == 2

    # Check individual results
    assert result['results'][0]['success'] is True  # word1
    assert result['results'][1]['success'] is False  # nonexistent
    assert result['results'][2]['success'] is False  # invalid quality
    assert result['results'][3]['success'] is True  # word2

    # Verify save was called once (had successful reviews)
    mock_repository.save_vocabulary.assert_called_once()


def test_record_reviews_all_quality_ratings(mock_repository):
    """Test record_reviews handles all valid quality ratings (0-5)."""
    vocab = {}
    for i in range(6):
        vocab[f'word{i}'] = {
            'created_on': 123456,
            'interval': 0,
            'repetition': 0,
            'ease_factor': 2.5,
            'next_review_date': None,
            'last_review_date': None
        }

    mock_repository.get_vocabulary.return_value = vocab
    mock_repository.ensure_spaced_repetition_fields.side_effect = lambda x: x

    service = VocabularyService(vocabulary_repository=mock_repository)
    reviews = [{'word': f'word{i}', 'quality': i} for i in range(6)]

    result = service.record_reviews(user_id, reviews)

    assert result['total_processed'] == 6
    assert result['successful'] == 6
    assert result['failed'] == 0

    # All should be successful
    for res in result['results']:
        assert res['success'] is True


def test_record_reviews_single_save(mock_repository):
    """Test that record_reviews calls save_vocabulary only once for batch."""
    vocab = {
        'word1': {'created_on': 123456, 'interval': 0, 'repetition': 0, 'ease_factor': 2.5, 'next_review_date': None, 'last_review_date': None},
        'word2': {'created_on': 123457, 'interval': 0, 'repetition': 0, 'ease_factor': 2.5, 'next_review_date': None, 'last_review_date': None},
        'word3': {'created_on': 123458, 'interval': 0, 'repetition': 0, 'ease_factor': 2.5, 'next_review_date': None, 'last_review_date': None}
    }
    mock_repository.get_vocabulary.return_value = vocab
    mock_repository.ensure_spaced_repetition_fields.side_effect = lambda x: x

    service = VocabularyService(vocabulary_repository=mock_repository)
    reviews = [
        {'word': 'word1', 'quality': 5},
        {'word': 'word2', 'quality': 4},
        {'word': 'word3', 'quality': 3}
    ]

    service.record_reviews(user_id, reviews)

    # Verify save was called exactly once (not once per review)
    assert mock_repository.save_vocabulary.call_count == 1
