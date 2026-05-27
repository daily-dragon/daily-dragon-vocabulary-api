import logging
import time
from typing import Dict, List, Any

from fastapi import Depends

from daily_dragon.repository.hsk_repository import HskRepository
from daily_dragon.repository.settings_repository import SettingsRepository
from daily_dragon.repository.vocabulary_repository import VocabularyRepository
from daily_dragon.service.spaced_repetition import SpacedRepetitionService

logger = logging.getLogger(__name__)

MAX_HSK_LEVEL = 7
PROMOTION_THRESHOLD = 0.8


class HskService:

    def __init__(
        self,
        hsk_repository: HskRepository = Depends(),
        vocabulary_repository: VocabularyRepository = Depends(),
        settings_repository: SettingsRepository = Depends(),
    ):
        self.hsk_repository = hsk_repository
        self.vocabulary_repository = vocabulary_repository
        self.settings_repository = settings_repository

    def get_hsk_words(self, level: int) -> List[str]:
        return self.hsk_repository.get_hsk_words(level)

    def get_unseeded_words(self, user_id: str, level: int) -> List[str]:
        hsk_words = self.hsk_repository.get_hsk_words(level)
        vocabulary = self.vocabulary_repository.get_vocabulary(user_id)
        return [w for w in hsk_words if w not in vocabulary]

    def seed_next_batch(self, user_id: str, level: int, batch_size: int = 20) -> int:
        unseeded = self.get_unseeded_words(user_id, level)
        batch = unseeded[:batch_size]
        if not batch:
            return 0

        vocabulary = self.vocabulary_repository.get_vocabulary(user_id)
        created_on = int(time.time())
        for word in batch:
            metadata = SpacedRepetitionService.initialize_word_metadata(created_on)
            metadata['hsk_level'] = level
            vocabulary[word] = metadata

        self.vocabulary_repository.save_vocabulary(user_id, vocabulary)
        logger.info("Seeded %d new HSK %d words for user %s", len(batch), level, user_id)
        return len(batch)

    def get_level_progress(self, user_id: str, level: int) -> Dict[str, Any]:
        vocabulary = self.vocabulary_repository.get_vocabulary(user_id)
        level_words = {w: m for w, m in vocabulary.items() if m.get('hsk_level') == level}

        mastered = sum(1 for m in level_words.values() if SpacedRepetitionService.is_mastered(m))
        new = sum(1 for m in level_words.values() if m.get('interval', 0) == 0)
        in_progress = len(level_words) - mastered - new

        return {
            'level': level,
            'total': len(level_words),
            'mastered': mastered,
            'in_progress': in_progress,
            'new': new,
        }

    def check_and_promote(self, user_id: str) -> bool:
        logger.info("check_and_promote: fetching settings for user %s", user_id)
        settings = self.settings_repository.get_settings(user_id)
        logger.info("check_and_promote: settings=%s", settings)
        current_level = settings.get('hsk_level', 1)
        if 'hsk_level' not in settings:
            settings['hsk_level'] = current_level
            self.settings_repository.save_settings(user_id, settings)

        if current_level >= MAX_HSK_LEVEL:
            logger.info("check_and_promote: user %s is already at max HSK level %d", user_id, current_level)
            return False

        logger.info("check_and_promote: fetching level %d progress for user %s", current_level, user_id)
        progress = self.get_level_progress(user_id, current_level)
        total = progress['total']
        logger.info("check_and_promote: progress=%s", progress)
        if total == 0:
            return False

        mastery_ratio = progress['mastered'] / total
        logger.info("check_and_promote: mastery_ratio=%.2f for user %s level %d", mastery_ratio, user_id, current_level)
        if mastery_ratio < PROMOTION_THRESHOLD:
            return False

        new_level = current_level + 1
        logger.info("check_and_promote: promoting user %s from level %d to %d", user_id, current_level, new_level)
        settings['hsk_level'] = new_level
        self.settings_repository.save_settings(user_id, settings)
        logger.info("check_and_promote: seeding next batch for user %s at level %d", user_id, new_level)
        self.seed_next_batch(user_id, new_level)
        logger.info("Promoted user %s to HSK level %d", user_id, new_level)
        return True
