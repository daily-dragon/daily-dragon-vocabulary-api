from datetime import datetime, timedelta
from typing import Dict, Optional


class SpacedRepetitionService:
    """
    Implements the SuperMemo-2 (SM-2) spaced repetition algorithm.

    Quality ratings (0-5):
    - 0: Complete blackout
    - 1: Incorrect, but word felt familiar
    - 2: Incorrect, but seemed easy to recall
    - 3: Correct with serious difficulty
    - 4: Correct after hesitation
    - 5: Perfect recall

    The SM-2 algorithm adjusts review intervals based on how well the user
    recalls each word, optimizing long-term retention.
    """

    MIN_EASE_FACTOR = 1.3
    INITIAL_EASE_FACTOR = 2.5
    INITIAL_INTERVAL = 0
    INITIAL_REPETITION = 0

    @staticmethod
    def calculate_next_review(word_metadata: Dict, quality: int) -> Dict:
        """
        Calculate next review date and updated metadata based on SM-2 algorithm.

        Algorithm:
        - If quality < 3 (incorrect): repetition = 0, interval = 0
        - If quality >= 3 (correct):
          - If repetition = 0: interval = 1 day
          - If repetition = 1: interval = 6 days
          - If repetition > 1: interval = previous_interval * ease_factor
        - Update ease_factor: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        - Ease factor cannot go below 1.3

        Args:
            word_metadata: Current word metadata dict
            quality: Quality rating from 0-5

        Returns:
            Dict with updated metadata fields (interval, repetition, ease_factor,
            next_review_date, last_review_date)
        """
        current_time = int(datetime.now().timestamp())

        ease_factor = word_metadata.get('ease_factor', SpacedRepetitionService.INITIAL_EASE_FACTOR)
        repetition = word_metadata.get('repetition', SpacedRepetitionService.INITIAL_REPETITION)
        interval = word_metadata.get('interval', SpacedRepetitionService.INITIAL_INTERVAL)

        # Update ease factor (cannot go below MIN_EASE_FACTOR)
        ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ease_factor = max(ease_factor, SpacedRepetitionService.MIN_EASE_FACTOR)

        # Calculate interval based on quality
        if quality < 3:
            # Failed review - restart
            repetition = 0
            interval = 0
        else:
            # Successful review
            repetition += 1
            if repetition == 1:
                interval = 1
            elif repetition == 2:
                interval = 6
            else:
                interval = int(interval * ease_factor)

        # Calculate next review date
        next_review_date = int((datetime.now() + timedelta(days=interval)).timestamp())

        return {
            'interval': interval,
            'repetition': repetition,
            'ease_factor': round(ease_factor, 2),
            'next_review_date': next_review_date,
            'last_review_date': current_time
        }

    @staticmethod
    def initialize_word_metadata(created_on: int) -> Dict:
        """
        Initialize metadata for a new word with default SM-2 values.

        Args:
            created_on: Unix timestamp when the word was created

        Returns:
            Dict with all metadata fields initialized
        """
        return {
            'created_on': created_on,
            'interval': SpacedRepetitionService.INITIAL_INTERVAL,
            'repetition': SpacedRepetitionService.INITIAL_REPETITION,
            'ease_factor': SpacedRepetitionService.INITIAL_EASE_FACTOR,
            'next_review_date': None,
            'last_review_date': None
        }

    @staticmethod
    def is_due(word_metadata: Dict, current_time: Optional[int] = None) -> bool:
        """
        Check if a word is due for review.

        Args:
            word_metadata: Word metadata dict
            current_time: Unix timestamp (defaults to now)

        Returns:
            True if the word should be reviewed, False otherwise
        """
        if current_time is None:
            current_time = int(datetime.now().timestamp())

        next_review = word_metadata.get('next_review_date')

        # Never reviewed or explicitly due
        if next_review is None:
            return True

        return current_time >= next_review

    @staticmethod
    def days_overdue(word_metadata: Dict, current_time: Optional[int] = None) -> int:
        """
        Calculate how many days overdue a word is (for prioritization).

        For never-reviewed words, calculates days since creation.
        For reviewed words, calculates days past the next_review_date.

        Args:
            word_metadata: Word metadata dict
            current_time: Unix timestamp (defaults to now)

        Returns:
            Number of days overdue (0 if not due yet)
        """
        if current_time is None:
            current_time = int(datetime.now().timestamp())

        next_review = word_metadata.get('next_review_date')

        if next_review is None:
            # Never reviewed - use created_on date
            created_on = word_metadata.get('created_on', current_time)
            return (current_time - created_on) // 86400  # Convert to days

        if current_time < next_review:
            return 0

        return (current_time - next_review) // 86400  # Convert to days