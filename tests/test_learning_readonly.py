"""
Contract tests asserting that GET /vocabulary/due is read-only
and is safe to use from the learning flow without mutating any SRI tate.
"""
import pytest
from unittest.mock import MagicMock

from daily_dragon.service.vocabulary_service import VocabularyService

USER_ID = "test-user"


@pytest.fixture
def mock_repository():
    mock = MagicMock()
    mock.get_due_words.return_value = [
        {"word": "word1", "metadata": {"interval": 0, "next_review_date": None, "days_overdue": 0}},
        {"word": "word2", "metadata": {"interval": 1, "next_review_date": 123456, "days_overdue": 1}},
        {"word": "word3", "metadata": {"interval": 2, "next_review_date": 123456, "days_overdue": 2}},
        {"word": "word4", "metadata": {"interval": 3, "next_review_date": 123456, "days_overdue": 3}},
        {"word": "word5", "metadata": {"interval": 4, "next_review_date": 123456, "days_overdue": 4}},
    ]
    return mock


def test_get_due_words_does_not_mutate_vocabulary(mock_repository):
    """
    get_due_words is called by the learning flow.
    It must never write to the vocabulary store.
    """
    service = VocabularyService(vocabulary_repository=mock_repository)
    service.get_due_words(USER_ID)

    mock_repository.save_vocabulary.assert_not_called()
    mock_repository.add_word.assert_not_called()


def test_get_due_words_returns_word_list(mock_repository):
    """
    Contract: get_due_words returns a dict with a 'due_words' key containing
    a list of word objects. The learning flow extracts the 'word' field
    from each item to pass to the word-cards endpoint.
    """
    service = VocabularyService(vocabulary_repository=mock_repository)
    result = service.get_due_words(USER_ID)

    assert "due_words" in result
    words = [entry["word"] for entry in result["due_words"]]
    assert len(words) == 5
    assert all(isinstance(w, str) for w in words)
