import json
import logging
import os
import time
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

from daily_dragon.exceptions import WordAlreadyExistsError
from daily_dragon.service.spaced_repetition import SpacedRepetitionService

logger = logging.getLogger(__name__)


class VocabularyRepository:
    USER_VOCABULARY_FILE_SUFFIX = "_vocabulary.json"

    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv("S3_BUCKET")

    def get_vocabulary(self, user_id: str) -> Dict[str, Dict]:
        try:
            key = self._create_key(user_id)
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read().decode())
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.info("Vocabulary file not found, creating a new one.")
                return self._create_new_vocabulary_file(user_id)
            else:
                logger.error("Error fetching vocabulary file: %s", e)
                raise

    def save_vocabulary(self, user_id: str, vocabulary: Dict[str, Dict]):
        key = self._create_key(user_id)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(vocabulary, ensure_ascii=False).encode('utf-8')
        )

    def ensure_spaced_repetition_fields(self, word_metadata: Dict) -> Dict:
        """
        Ensure word has all spaced repetition fields (lazy migration).
        Removes adoption field if present and adds missing SM-2 fields.
        Returns a new dict; does not mutate the input.
        """
        result = {k: v for k, v in word_metadata.items() if k != 'adoption'}
        result.setdefault('interval', SpacedRepetitionService.INITIAL_INTERVAL)
        result.setdefault('repetition', SpacedRepetitionService.INITIAL_REPETITION)
        result.setdefault('ease_factor', SpacedRepetitionService.INITIAL_EASE_FACTOR)
        result.setdefault('next_review_date', None)
        result.setdefault('last_review_date', None)
        return result

    def get_due_words(self, user_id: str, limit: int = 5) -> List[Dict]:
        """
        Get words that are due for review, sorted by most overdue first.

        Args:
            user_id: User ID
            limit: Maximum number of words to return (default 5)

        Returns:
            List of dicts with 'word' and 'metadata' (including days_overdue)
        """
        vocabulary = self.get_vocabulary(user_id)

        migrated = False
        for word, metadata in vocabulary.items():
            if 'adoption' in metadata or 'interval' not in metadata:
                vocabulary[word] = self.ensure_spaced_repetition_fields(metadata)
                migrated = True

        if migrated:
            self.save_vocabulary(user_id, vocabulary)

        current_time = int(time.time())

        due_words = []
        for word, metadata in vocabulary.items():
            days = SpacedRepetitionService.days_overdue(metadata, current_time)
            if SpacedRepetitionService.is_due(metadata, current_time):
                due_words.append({
                    'word': word,
                    'metadata': {**metadata, 'days_overdue': days}
                })

        # Sort by days_overdue descending (most overdue first)
        due_words.sort(key=lambda x: x['metadata']['days_overdue'], reverse=True)

        # Return top N words
        return due_words[:limit]

    def add_word(self, user_id: str, word: str) -> None:
        vocabulary = self.get_vocabulary(user_id)

        if word in vocabulary:
            logger.info("Word already exists in vocabulary: %s", word)
            raise WordAlreadyExistsError()

        created_on = int(time.time())
        word_details = SpacedRepetitionService.initialize_word_metadata(created_on)

        vocabulary[word] = word_details

        self.save_vocabulary(user_id, vocabulary)
        logger.info("Word added to vocabulary: %s", word)

    def _create_new_vocabulary_file(self, user_id):
        empty_vocab = {}
        key = self._create_key(user_id)
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(empty_vocab).encode('utf-8'),
                ContentType='application/json'
            )
            logger.info("Created new vocabulary file for user %s", user_id)
        except ClientError as put_error:
            logger.error("Failed to create vocabulary file: %s", put_error)
            raise
        return empty_vocab

    def _create_key(self, user_id: str):
        return f"{user_id}{self.USER_VOCABULARY_FILE_SUFFIX}"
