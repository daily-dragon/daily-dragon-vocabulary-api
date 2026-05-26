import json
import logging
import os
from typing import Dict

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SettingsRepository:
    USER_SETTINGS_FILE_SUFFIX = "_settings.json"

    DEFAULT_SETTINGS = {
        "hsk_level": 1,
        "placement_completed": False
    }

    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv("S3_BUCKET")

    def get_settings(self, user_id: str) -> Dict:
        try:
            key = self._create_key(user_id)
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read().decode())
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.info("Settings file not found, creating defaults for user %s", user_id)
                return self._create_default_settings(user_id)
            else:
                logger.error("Error fetching settings file: %s", e)
                raise

    def save_settings(self, user_id: str, settings: Dict) -> None:
        key = self._create_key(user_id)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(settings, ensure_ascii=False).encode('utf-8')
        )

    def _create_default_settings(self, user_id: str) -> Dict:
        defaults = dict(self.DEFAULT_SETTINGS)
        key = self._create_key(user_id)
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(defaults).encode('utf-8'),
                ContentType='application/json'
            )
            logger.info("Created default settings for user %s", user_id)
        except ClientError as e:
            logger.error("Failed to create settings file: %s", e)
            raise
        return defaults

    def _create_key(self, user_id: str) -> str:
        return f"{user_id}{self.USER_SETTINGS_FILE_SUFFIX}"
