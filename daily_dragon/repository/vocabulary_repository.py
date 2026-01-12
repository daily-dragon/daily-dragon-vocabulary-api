import json
import logging
import os
import time
from typing import Dict

import boto3
from botocore.exceptions import ClientError

from daily_dragon.exceptions import WordAlreadyExistsError

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

    def add_word(self, user_id: str, word: str) -> None:
        vocabulary = self.get_vocabulary(user_id)

        if word in vocabulary:
            logger.info("Word already exists in vocabulary: %s", word)
            raise WordAlreadyExistsError()

        word_details = {
            'adoption': 0,
            'created_on': int(time.time())
        }

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
