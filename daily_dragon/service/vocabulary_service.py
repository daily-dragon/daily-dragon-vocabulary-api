import logging
import random

from fastapi import Depends

from daily_dragon.repository.vocabulary_repository import VocabularyRepository

logger = logging.getLogger(__name__)


class VocabularyService:

    def __init__(self, vocabulary_repository: VocabularyRepository = Depends()):
        self.vocabulary_repository = vocabulary_repository

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
