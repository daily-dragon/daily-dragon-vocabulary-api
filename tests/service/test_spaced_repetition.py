import pytest
from datetime import datetime, timedelta
from daily_dragon.service.spaced_repetition import SpacedRepetitionService


class TestSpacedRepetitionService:
    """Test suite for the SpacedRepetitionService SM-2 algorithm implementation."""

    def test_initialize_word_metadata(self):
        """Test that new words are initialized with correct default values."""
        created_on = int(datetime.now().timestamp())
        metadata = SpacedRepetitionService.initialize_word_metadata(created_on)

        assert metadata['created_on'] == created_on
        assert metadata['interval'] == 0
        assert metadata['repetition'] == 0
        assert metadata['ease_factor'] == 2.5
        assert metadata['next_review_date'] is None
        assert metadata['last_review_date'] is None
        assert 'adoption' not in metadata  # Ensure adoption field is not present

    def test_calculate_next_review_first_success(self):
        """Test first successful review (quality >= 5) sets interval to 1 day."""
        metadata = {
            'interval': 0,
            'repetition': 0,
            'ease_factor': 2.5,
            'next_review_date': None,
            'last_review_date': None
        }

        result = SpacedRepetitionService.calculate_next_review(metadata, quality=10)

        assert result['interval'] == 1
        assert result['repetition'] == 1
        assert result['ease_factor'] >= 2.5  # Should increase with quality 10
        assert result['next_review_date'] is not None
        assert result['last_review_date'] is not None

    def test_calculate_next_review_second_success(self):
        """Test second successful review sets interval to 6 days."""
        metadata = {
            'interval': 1,
            'repetition': 1,
            'ease_factor': 2.6,
            'next_review_date': int(datetime.now().timestamp()),
            'last_review_date': int((datetime.now() - timedelta(days=1)).timestamp())
        }

        result = SpacedRepetitionService.calculate_next_review(metadata, quality=8)

        assert result['interval'] == 6
        assert result['repetition'] == 2

    def test_calculate_next_review_subsequent_success(self):
        """Test that subsequent successful reviews multiply interval by the pre-update ease factor."""
        metadata = {
            'interval': 6,
            'repetition': 2,
            'ease_factor': 2.5,
            'next_review_date': int(datetime.now().timestamp()),
            'last_review_date': int((datetime.now() - timedelta(days=6)).timestamp())
        }

        # quality=6 changes EF: new_ef = 2.5 - 0.14 = 2.36
        # interval must use old EF (2.5) → int(6 * 2.5) = 15, not int(6 * 2.36) = 14
        result = SpacedRepetitionService.calculate_next_review(metadata, quality=6)

        assert result['interval'] == int(6 * 2.5)  # 15, not 14
        assert result['repetition'] == 3

    def test_calculate_next_review_failed(self):
        """Test that failed review (quality < 5) resets repetition and interval."""
        metadata = {
            'interval': 15,
            'repetition': 3,
            'ease_factor': 2.5,
            'next_review_date': int(datetime.now().timestamp()),
            'last_review_date': int((datetime.now() - timedelta(days=15)).timestamp())
        }

        result = SpacedRepetitionService.calculate_next_review(metadata, quality=4)

        assert result['interval'] == 0
        assert result['repetition'] == 0
        # Ease factor should still be updated, even on failure
        assert result['ease_factor'] < 2.5

    def test_ease_factor_minimum_boundary(self):
        """Test that ease factor never goes below 1.3."""
        metadata = {
            'interval': 1,
            'repetition': 1,
            'ease_factor': 1.3,
            'next_review_date': int(datetime.now().timestamp()),
            'last_review_date': int(datetime.now().timestamp())
        }

        # Quality 0 should decrease ease factor, but it should stay at minimum 1.3
        result = SpacedRepetitionService.calculate_next_review(metadata, quality=0)

        assert result['ease_factor'] >= 1.3
        assert result['ease_factor'] == 1.3  # Should be exactly at minimum

    def test_ease_factor_increases_with_high_quality(self):
        """Test that ease factor increases with quality ratings of 9 or 10."""
        metadata = {
            'interval': 6,
            'repetition': 2,
            'ease_factor': 2.5,
            'next_review_date': int(datetime.now().timestamp()),
            'last_review_date': int(datetime.now().timestamp())
        }

        result = SpacedRepetitionService.calculate_next_review(metadata, quality=10)

        assert result['ease_factor'] > 2.5

    def test_ease_factor_decreases_with_low_quality(self):
        """Test that ease factor decreases with quality ratings of 0-4."""
        metadata = {
            'interval': 6,
            'repetition': 2,
            'ease_factor': 2.5,
            'next_review_date': int(datetime.now().timestamp()),
            'last_review_date': int(datetime.now().timestamp())
        }

        result = SpacedRepetitionService.calculate_next_review(metadata, quality=4)

        assert result['ease_factor'] < 2.5

    def test_all_quality_ratings(self):
        """Test that all quality ratings (0-10) are handled correctly."""
        metadata = {
            'interval': 1,
            'repetition': 1,
            'ease_factor': 2.5,
            'next_review_date': int(datetime.now().timestamp()),
            'last_review_date': int(datetime.now().timestamp())
        }

        for quality in range(11):
            result = SpacedRepetitionService.calculate_next_review(metadata.copy(), quality=quality)

            assert 'interval' in result
            assert 'repetition' in result
            assert 'ease_factor' in result
            assert 'next_review_date' in result
            assert 'last_review_date' in result

            # Failed reviews (quality < 5) should reset
            if quality < 5:
                assert result['interval'] == 0
                assert result['repetition'] == 0
            else:
                # Successful reviews should advance
                assert result['repetition'] >= 1

    def test_is_due_never_reviewed(self):
        """Test that words with null next_review_date are due."""
        metadata = {
            'next_review_date': None,
            'created_on': int(datetime.now().timestamp())
        }

        assert SpacedRepetitionService.is_due(metadata) is True

    def test_is_due_past_review_date(self):
        """Test that words past their review date are due."""
        past_timestamp = int((datetime.now() - timedelta(days=1)).timestamp())
        metadata = {
            'next_review_date': past_timestamp,
            'created_on': int((datetime.now() - timedelta(days=10)).timestamp())
        }

        assert SpacedRepetitionService.is_due(metadata) is True

    def test_is_not_due_future_review_date(self):
        """Test that words with future review dates are not due."""
        future_timestamp = int((datetime.now() + timedelta(days=1)).timestamp())
        metadata = {
            'next_review_date': future_timestamp,
            'created_on': int((datetime.now() - timedelta(days=10)).timestamp())
        }

        assert SpacedRepetitionService.is_due(metadata) is False

    def test_days_overdue_never_reviewed(self):
        """Test days_overdue for never-reviewed words uses created_on."""
        days_ago = 5
        created_on = int((datetime.now() - timedelta(days=days_ago)).timestamp())
        metadata = {
            'next_review_date': None,
            'created_on': created_on
        }

        days = SpacedRepetitionService.days_overdue(metadata)

        # Should be approximately days_ago (allowing for slight timing variations)
        assert days >= days_ago - 1
        assert days <= days_ago + 1

    def test_days_overdue_past_review_date(self):
        """Test days_overdue calculation for overdue reviews."""
        days_overdue = 3
        next_review = int((datetime.now() - timedelta(days=days_overdue)).timestamp())
        metadata = {
            'next_review_date': next_review,
            'created_on': int((datetime.now() - timedelta(days=10)).timestamp())
        }

        days = SpacedRepetitionService.days_overdue(metadata)

        # Should be approximately days_overdue (allowing for slight timing variations)
        assert days >= days_overdue - 1
        assert days <= days_overdue + 1

    def test_days_overdue_not_due_yet(self):
        """Test that words not yet due return 0 days overdue."""
        future_review = int((datetime.now() + timedelta(days=2)).timestamp())
        metadata = {
            'next_review_date': future_review,
            'created_on': int((datetime.now() - timedelta(days=10)).timestamp())
        }

        days = SpacedRepetitionService.days_overdue(metadata)

        assert days == 0

    def test_interval_progression_sequence(self):
        """Test the complete interval progression: 1 -> 6 -> 15 -> 37..."""
        metadata = {
            'interval': 0,
            'repetition': 0,
            'ease_factor': 2.5,
            'next_review_date': None,
            'last_review_date': None
        }

        # First review (quality 8)
        metadata = SpacedRepetitionService.calculate_next_review(metadata, quality=8)
        assert metadata['interval'] == 1
        assert metadata['repetition'] == 1

        # Second review (quality 8)
        metadata = SpacedRepetitionService.calculate_next_review(metadata, quality=8)
        assert metadata['interval'] == 6
        assert metadata['repetition'] == 2

        # Third review (quality 6) - interval uses pre-update ease factor
        ease_factor_before = metadata['ease_factor']
        metadata = SpacedRepetitionService.calculate_next_review(metadata, quality=6)
        expected_interval = int(6 * ease_factor_before)
        assert metadata['interval'] == expected_interval  # uses old EF, not post-update EF
        assert metadata['repetition'] == 3

    def test_ease_factor_rounded_to_two_decimals(self):
        """Test that ease factor is rounded to 2 decimal places."""
        metadata = {
            'interval': 6,
            'repetition': 2,
            'ease_factor': 2.5,
            'next_review_date': int(datetime.now().timestamp()),
            'last_review_date': int(datetime.now().timestamp())
        }

        result = SpacedRepetitionService.calculate_next_review(metadata, quality=7)

        # Check that ease_factor has at most 2 decimal places
        assert len(str(result['ease_factor']).split('.')[-1]) <= 2
