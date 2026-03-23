import logging
import random
from typing import List, Dict, Any

from fastapi import Depends

from daily_dragon.repository.vocabulary_repository import VocabularyRepository
from daily_dragon.service.spaced_repetition import SpacedRepetitionService

logger = logging.getLogger(__name__)


class VocabularyService:

    def __init__(self, vocabulary_repository: VocabularyRepository = Depends()):
        self.vocabulary_repository = vocabulary_repository
        self.spaced_repetition_service = SpacedRepetitionService()

    def add_word(self, user_id: str, word: str):
        return self.vocabulary_repository.add_word(user_id, word)

    def get_vocabulary(self, user_id: str):
        return self.vocabulary_repository.get_vocabulary(user_id)

    def delete_word(self, user_id: str, word: str):
        vocabulary = self.vocabulary_repository.get_vocabulary(user_id)
        if word in vocabulary:
            del vocabulary[word]
            self.vocabulary_repository.save_vocabulary(user_id, vocabulary)
        logger.info(f"Deleted word {word}")

    def get_random_vocabulary(self, user_id: str, count: int):
        all_vocabulary = self.vocabulary_repository.get_vocabulary(user_id)
        random_words = random.sample(list(all_vocabulary.keys()), min(count, len(all_vocabulary)))
        return {word: all_vocabulary[word] for word in random_words}

    def get_due_words(self, user_id: str) -> Dict[str, Any]:
        """
        Get words that are due for review.

        Args:
            user_id: User ID

        Returns:
            Dict with due_words list, total_due count, and returned count
        """
        due_words = self.vocabulary_repository.get_due_words(user_id, limit=5)

        return {
            'due_words': due_words,
            'total_due': len(due_words),  # Total is same as returned since limit is applied in repo
            'returned': len(due_words)
        }

    def record_reviews(self, user_id: str, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Record batch reviews for multiple words and update their spaced repetition schedules.

        Args:
            user_id: User ID
            reviews: List of dicts with 'word' and 'quality' keys

        Returns:
            Dict with results list, total_processed, successful, and failed counts
        """
        # Get vocabulary once for efficiency
        vocabulary = self.vocabulary_repository.get_vocabulary(user_id)

        # Apply migration to all words
        for word_key in vocabulary:
            vocabulary[word_key] = self.vocabulary_repository.ensure_spaced_repetition_fields(
                vocabulary[word_key]
            )

        results = []
        successful = 0
        failed = 0

        for review in reviews:
            word = review['word']
            quality = review['quality']

            try:
                # Validate quality
                if not isinstance(quality, int) or quality < 0 or quality > 5:
                    results.append({
                        'word': word,
                        'success': False,
                        'error': 'Quality must be between 0 and 5'
                    })
                    failed += 1
                    continue

                # Check word exists
                if word not in vocabulary:
                    results.append({
                        'word': word,
                        'success': False,
                        'error': 'Word not found in vocabulary'
                    })
                    failed += 1
                    continue

                # Calculate next review using SM-2 algorithm
                updated_metadata = self.spaced_repetition_service.calculate_next_review(
                    vocabulary[word],
                    quality
                )

                # Merge updated metadata (preserve created_on)
                vocabulary[word].update(updated_metadata)

                results.append({
                    'word': word,
                    'success': True,
                    'next_review_date': updated_metadata['next_review_date'],
                    'interval': updated_metadata['interval']
                })
                successful += 1

            except Exception as e:
                logger.error(f"Error processing review for word {word}: {e}")
                results.append({
                    'word': word,
                    'success': False,
                    'error': str(e)
                })
                failed += 1

        # Save vocabulary once at the end (only if there were successful reviews)
        if successful > 0:
            self.vocabulary_repository.save_vocabulary(user_id, vocabulary)

        return {
            'results': results,
            'total_processed': len(reviews),
            'successful': successful,
            'failed': failed
        }
