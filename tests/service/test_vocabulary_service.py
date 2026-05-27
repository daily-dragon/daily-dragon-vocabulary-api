import pytest
from unittest.mock import MagicMock

from daily_dragon.service.vocabulary_service import VocabularyService

user_id = "user_id"


@pytest.fixture
def mock_repository():
    mock = MagicMock()
    mock.get_vocabulary.return_value = {
        "学习": {"created_on": 1712534400, "interval": 0, "repetition": 0, "ease_factor": 2.5, "next_review_date": None, "last_review_date": None},
        "大众": {"created_on": 1711929600, "interval": 6, "repetition": 2, "ease_factor": 2.6, "next_review_date": 1712534400, "last_review_date": 1711929600},
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
        "学习": {"created_on": 1712534400, "interval": 0, "repetition": 0, "ease_factor": 2.5, "next_review_date": None, "last_review_date": None},
    }
    mock_repository.save_vocabulary.assert_called_once_with(user_id, updated_vocab)


def test_delete_word_not_exists(mock_repository):
    service = VocabularyService(vocabulary_repository=mock_repository)

    service.delete_word(user_id, "不存在的词")

    mock_repository.save_vocab.assert_not_called()


def test_get_due_words_no_seeding_when_full(mock_repository):
    due_words_data = [
        {'word': f'word{i}', 'metadata': {'interval': 0, 'next_review_date': None, 'days_overdue': 5}}
        for i in range(5)
    ]
    mock_repository.get_due_words.return_value = due_words_data
    mock_hsk_service = MagicMock()

    service = VocabularyService(vocabulary_repository=mock_repository, hsk_service=mock_hsk_service)
    result = service.get_due_words(user_id)

    mock_hsk_service.seed_words.assert_not_called()
    assert result['due_words'] == due_words_data
    assert result['returned'] == 5


def test_get_due_words_tops_up_when_empty():
    mock_repository = MagicMock()
    mock_hsk_service = MagicMock()
    mock_hsk_service.seed_words.return_value = 5

    seeded_due_words = [
        {'word': f'新{i}', 'metadata': {'interval': 0, 'next_review_date': None, 'days_overdue': 0}}
        for i in range(5)
    ]
    mock_repository.get_due_words.side_effect = [[], seeded_due_words]

    service = VocabularyService(vocabulary_repository=mock_repository, hsk_service=mock_hsk_service)
    result = service.get_due_words(user_id)

    mock_hsk_service.seed_words.assert_called_once_with(user_id, 5)
    assert result['due_words'] == seeded_due_words
    assert result['returned'] == 5


def test_get_due_words_tops_up_partial_shortfall():
    mock_repository = MagicMock()
    mock_hsk_service = MagicMock()
    mock_hsk_service.seed_words.return_value = 3

    initial_due = [
        {'word': f'due{i}', 'metadata': {'interval': 5, 'next_review_date': 0, 'days_overdue': 3}}
        for i in range(2)
    ]
    topped_up = initial_due + [
        {'word': f'新{i}', 'metadata': {'interval': 0, 'next_review_date': None, 'days_overdue': 0}}
        for i in range(3)
    ]
    mock_repository.get_due_words.side_effect = [initial_due, topped_up]

    service = VocabularyService(vocabulary_repository=mock_repository, hsk_service=mock_hsk_service)
    result = service.get_due_words(user_id)

    mock_hsk_service.seed_words.assert_called_once_with(user_id, 3)
    assert result['due_words'] == topped_up
    assert result['returned'] == 5


def test_get_due_words_no_top_up_when_hsk_exhausted():
    mock_repository = MagicMock()
    mock_hsk_service = MagicMock()
    mock_hsk_service.seed_words.return_value = 0

    mock_repository.get_due_words.return_value = []

    service = VocabularyService(vocabulary_repository=mock_repository, hsk_service=mock_hsk_service)
    result = service.get_due_words(user_id)

    mock_hsk_service.seed_words.assert_called_once_with(user_id, 5)
    assert result['due_words'] == []
    assert result['returned'] == 0


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
        {'word': 'word1', 'quality': 10},
        {'word': 'word2', 'quality': 8}
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
        {'word': 'nonexistent', 'quality': 10}
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
        {'word': 'word1', 'quality': 10},      # Valid
        {'word': 'nonexistent', 'quality': 8}, # Word not found
        {'word': 'word2', 'quality': 6}        # Valid
    ]

    result = service.record_reviews(user_id, reviews)

    assert result['total_processed'] == 3
    assert result['successful'] == 2
    assert result['failed'] == 1

    # Check individual results
    assert result['results'][0]['success'] is True   # word1
    assert result['results'][1]['success'] is False  # nonexistent
    assert result['results'][2]['success'] is True   # word2

    # Verify save was called once (had successful reviews)
    mock_repository.save_vocabulary.assert_called_once()


def test_record_reviews_all_quality_ratings(mock_repository):
    """Test record_reviews handles all valid quality ratings (0-10)."""
    vocab = {}
    for i in range(11):
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
    reviews = [{'word': f'word{i}', 'quality': i} for i in range(11)]

    result = service.record_reviews(user_id, reviews)

    assert result['total_processed'] == 11
    assert result['successful'] == 11
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
        {'word': 'word1', 'quality': 10},
        {'word': 'word2', 'quality': 8},
        {'word': 'word3', 'quality': 6}
    ]

    service.record_reviews(user_id, reviews)

    # Verify save was called exactly once (not once per review)
    assert mock_repository.save_vocabulary.call_count == 1
