import pytest
from unittest.mock import MagicMock

from daily_dragon.service.hsk_service import HskService, MAX_HSK_LEVEL, HSK_LEVEL_WORD_COUNT
from daily_dragon.service.spaced_repetition import SpacedRepetitionService

USER_ID = "test-user"
MASTERY_INTERVAL = SpacedRepetitionService.MASTERY_INTERVAL


def _word_meta(interval: int, hsk_level: int = 1) -> dict:
    return {
        'created_on': 1000000,
        'interval': interval,
        'repetition': 0,
        'ease_factor': 2.5,
        'next_review_date': None,
        'last_review_date': None,
        'hsk_level': hsk_level,
    }


@pytest.fixture
def mock_hsk_repo():
    return MagicMock()


@pytest.fixture
def mock_vocab_repo():
    return MagicMock()


@pytest.fixture
def mock_settings_repo():
    return MagicMock()


@pytest.fixture
def service(mock_hsk_repo, mock_vocab_repo, mock_settings_repo):
    return HskService(mock_hsk_repo, mock_vocab_repo, mock_settings_repo)


class TestGetHskWords:
    def test_delegates_to_repository(self, service, mock_hsk_repo):
        mock_hsk_repo.get_hsk_words.return_value = ["一", "二"]
        result = service.get_hsk_words(1)
        assert result == ["一", "二"]
        mock_hsk_repo.get_hsk_words.assert_called_once_with(1)


class TestGetUnseededWords:
    def test_returns_words_not_in_vocabulary(self, service, mock_hsk_repo, mock_vocab_repo):
        mock_hsk_repo.get_hsk_words.return_value = ["一", "二", "三"]
        mock_vocab_repo.get_vocabulary.return_value = {"一": _word_meta(0)}

        result = service.get_unseeded_words(USER_ID, 1)

        assert result == ["二", "三"]

    def test_returns_all_words_when_vocabulary_empty(self, service, mock_hsk_repo, mock_vocab_repo):
        mock_hsk_repo.get_hsk_words.return_value = ["一", "二"]
        mock_vocab_repo.get_vocabulary.return_value = {}

        result = service.get_unseeded_words(USER_ID, 1)

        assert result == ["一", "二"]

    def test_returns_empty_when_all_seeded(self, service, mock_hsk_repo, mock_vocab_repo):
        mock_hsk_repo.get_hsk_words.return_value = ["一", "二"]
        mock_vocab_repo.get_vocabulary.return_value = {"一": _word_meta(0), "二": _word_meta(0)}

        result = service.get_unseeded_words(USER_ID, 1)

        assert result == []


class TestSeedNextBatch:
    def test_seeds_up_to_batch_size(self, service, mock_hsk_repo, mock_vocab_repo):
        mock_hsk_repo.get_hsk_words.return_value = [str(i) for i in range(50)]
        mock_vocab_repo.get_vocabulary.return_value = {}

        count = service.seed_next_batch(USER_ID, 1, batch_size=20)

        assert count == 20
        saved = mock_vocab_repo.save_vocabulary.call_args[0][1]
        assert len(saved) == 20

    def test_seeded_words_have_hsk_metadata(self, service, mock_hsk_repo, mock_vocab_repo):
        mock_hsk_repo.get_hsk_words.return_value = ["一", "二"]
        mock_vocab_repo.get_vocabulary.return_value = {}

        service.seed_next_batch(USER_ID, 3)

        saved = mock_vocab_repo.save_vocabulary.call_args[0][1]
        for meta in saved.values():
            assert meta['hsk_level'] == 3
            assert meta['interval'] == 0
            assert meta['ease_factor'] == SpacedRepetitionService.INITIAL_EASE_FACTOR

    def test_returns_zero_when_nothing_to_seed(self, service, mock_hsk_repo, mock_vocab_repo):
        mock_hsk_repo.get_hsk_words.return_value = ["一"]
        mock_vocab_repo.get_vocabulary.return_value = {"一": _word_meta(0)}

        count = service.seed_next_batch(USER_ID, 1)

        assert count == 0
        mock_vocab_repo.save_vocabulary.assert_not_called()

    def test_seeds_only_unseeded_words(self, service, mock_hsk_repo, mock_vocab_repo):
        mock_hsk_repo.get_hsk_words.return_value = ["一", "二", "三"]
        mock_vocab_repo.get_vocabulary.return_value = {"一": _word_meta(5)}

        service.seed_next_batch(USER_ID, 1, batch_size=5)

        saved = mock_vocab_repo.save_vocabulary.call_args[0][1]
        assert "一" in saved
        assert saved["一"]["interval"] == 5  # unchanged
        assert "二" in saved
        assert "三" in saved

    def test_saves_vocabulary_once(self, service, mock_hsk_repo, mock_vocab_repo):
        mock_hsk_repo.get_hsk_words.return_value = ["一", "二"]
        mock_vocab_repo.get_vocabulary.return_value = {}

        service.seed_next_batch(USER_ID, 1)

        mock_vocab_repo.save_vocabulary.assert_called_once()


class TestGetLevelProgress:
    def test_counts_mastered_in_progress_and_new(self, service, mock_vocab_repo):
        mock_vocab_repo.get_vocabulary.return_value = {
            "一": _word_meta(MASTERY_INTERVAL, hsk_level=1),       # mastered
            "二": _word_meta(MASTERY_INTERVAL + 5, hsk_level=1),   # mastered
            "三": _word_meta(10, hsk_level=1),                      # in_progress
            "四": _word_meta(0, hsk_level=1),                       # new
            "五": _word_meta(0, hsk_level=2),                       # different level — ignored
        }

        result = service.get_level_progress(USER_ID, 1)

        assert result['level'] == 1
        assert result['total'] == HSK_LEVEL_WORD_COUNT[1]
        assert result['mastered'] == 2
        assert result['in_progress'] == 1
        assert result['new'] == 1

    def test_returns_zeros_for_empty_level(self, service, mock_vocab_repo):
        mock_vocab_repo.get_vocabulary.return_value = {}

        result = service.get_level_progress(USER_ID, 1)

        assert result == {'level': 1, 'total': HSK_LEVEL_WORD_COUNT[1], 'mastered': 0, 'in_progress': 0, 'new': 0}

    def test_ignores_words_without_hsk_level(self, service, mock_vocab_repo):
        meta_no_level = {'created_on': 1000, 'interval': 30, 'repetition': 5,
                         'ease_factor': 2.5, 'next_review_date': None, 'last_review_date': None}
        mock_vocab_repo.get_vocabulary.return_value = {"旧词": meta_no_level}

        result = service.get_level_progress(USER_ID, 1)

        assert result['total'] == HSK_LEVEL_WORD_COUNT[1]


class TestCheckAndPromote:
    def test_promotes_when_80_percent_mastered(self, service, mock_vocab_repo, mock_settings_repo, mock_hsk_repo):
        mock_settings_repo.get_settings.return_value = {'hsk_level': 1, 'placement_completed': True}
        total = HSK_LEVEL_WORD_COUNT[1]
        mastered_count = int(total * 0.8)  # exactly 80%
        mock_vocab_repo.get_vocabulary.return_value = {
            **{f"mastered_{i}": _word_meta(MASTERY_INTERVAL) for i in range(mastered_count)},
            **{f"not_mastered_{i}": _word_meta(5) for i in range(total - mastered_count)},
        }
        mock_hsk_repo.get_hsk_words.return_value = []

        promoted = service.check_and_promote(USER_ID)

        assert promoted is True
        saved_settings = mock_settings_repo.save_settings.call_args[0][1]
        assert saved_settings['hsk_level'] == 2

    def test_does_not_promote_when_below_80_percent(self, service, mock_vocab_repo, mock_settings_repo):
        mock_settings_repo.get_settings.return_value = {'hsk_level': 1, 'placement_completed': True}
        mock_vocab_repo.get_vocabulary.return_value = {
            **{str(i): _word_meta(MASTERY_INTERVAL) for i in range(7)},  # 7 mastered
            "未掌握1": _word_meta(5),                                       # 79% — just under
            "未掌握2": _word_meta(3),
            "未掌握3": _word_meta(1),
        }

        promoted = service.check_and_promote(USER_ID)

        assert promoted is False
        mock_settings_repo.save_settings.assert_not_called()

    def test_does_not_promote_at_max_level(self, service, mock_settings_repo, mock_vocab_repo):
        mock_settings_repo.get_settings.return_value = {'hsk_level': MAX_HSK_LEVEL, 'placement_completed': True}

        promoted = service.check_and_promote(USER_ID)

        assert promoted is False
        mock_vocab_repo.get_vocabulary.assert_not_called()
        mock_settings_repo.save_settings.assert_not_called()

    def test_does_not_promote_when_no_words_seeded(self, service, mock_vocab_repo, mock_settings_repo):
        mock_settings_repo.get_settings.return_value = {'hsk_level': 1, 'placement_completed': True}
        mock_vocab_repo.get_vocabulary.return_value = {}

        promoted = service.check_and_promote(USER_ID)

        assert promoted is False
        mock_settings_repo.save_settings.assert_not_called()

    def test_legacy_settings_without_hsk_level_defaults_to_1(self, service, mock_vocab_repo, mock_settings_repo):
        mock_settings_repo.get_settings.return_value = {'placement_completed': False}
        mock_vocab_repo.get_vocabulary.return_value = {}

        promoted = service.check_and_promote(USER_ID)

        assert promoted is False
        saved_settings = mock_settings_repo.save_settings.call_args[0][1]
        assert saved_settings['hsk_level'] == 1

    def test_seeds_first_batch_of_new_level_on_promotion(self, service, mock_vocab_repo, mock_settings_repo, mock_hsk_repo):
        mock_settings_repo.get_settings.return_value = {'hsk_level': 1, 'placement_completed': True}
        total = HSK_LEVEL_WORD_COUNT[1]
        mastered_count = int(total * 0.8)
        mock_vocab_repo.get_vocabulary.return_value = {
            **{f"mastered_{i}": _word_meta(MASTERY_INTERVAL) for i in range(mastered_count)},
            **{f"not_mastered_{i}": _word_meta(5) for i in range(total - mastered_count)},
        }
        mock_hsk_repo.get_hsk_words.return_value = ["新1", "新2"]

        service.check_and_promote(USER_ID)

        mock_hsk_repo.get_hsk_words.assert_called_with(2)
        mock_vocab_repo.save_vocabulary.assert_called_once()
        saved = mock_vocab_repo.save_vocabulary.call_args[0][1]
        assert "新1" in saved or "新2" in saved
