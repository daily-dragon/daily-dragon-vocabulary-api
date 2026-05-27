import logging
import random
from typing import List, Dict, Any

from fastapi import Depends

from daily_dragon.repository.vocabulary_repository import VocabularyRepository
from daily_dragon.service.hsk_service import HskService

DUE_WORDS_LIMIT = 5
from daily_dragon.service.spaced_repetition import SpacedRepetitionService

logger = logging.getLogger(__name__)


class VocabularyService:

    def __init__(
        self,
        vocabulary_repository: VocabularyRepository = Depends(),
        hsk_service: HskService = Depends(),
    ):
        self.vocabulary_repository = vocabulary_repository
        self.hsk_service = hsk_service

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
        limit = DUE_WORDS_LIMIT
        due_words = self.vocabulary_repository.get_due_words(user_id, limit=limit)

        shortfall = limit - len(due_words)
        if shortfall > 0:
            seeded = self.hsk_service.seed_words(user_id, shortfall)
            if seeded > 0:
                due_words = self.vocabulary_repository.get_due_words(user_id, limit=limit)

        return {
            'due_words': due_words,
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
        vocabulary = self.vocabulary_repository.get_vocabulary(user_id)

        migrated_any = False
        for word_key in vocabulary:
            if 'adoption' in vocabulary[word_key] or 'interval' not in vocabulary[word_key]:
                migrated_any = True
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
                if word not in vocabulary:
                    results.append({
                        'word': word,
                        'success': False,
                        'error': 'Word not found in vocabulary'
                    })
                    failed += 1
                    continue

                updated_metadata = SpacedRepetitionService.calculate_next_review(
                    vocabulary[word],
                    quality
                )

                vocabulary[word].update(updated_metadata)

                results.append({
                    'word': word,
                    'success': True,
                    'next_review_date': updated_metadata['next_review_date'],
                    'interval': updated_metadata['interval']
                })
                successful += 1

            except Exception:
                logger.exception(f"Error processing review for word {word}")
                results.append({
                    'word': word,
                    'success': False,
                    'error': 'An internal error occurred while processing this review'
                })
                failed += 1

        if successful > 0 or migrated_any:
            self.vocabulary_repository.save_vocabulary(user_id, vocabulary)

        return {
            'results': results,
            'total_processed': len(reviews),
            'successful': successful,
            'failed': failed
        }
