import json
import logging
import os
from typing import List

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class HskRepository:
    HSK_PREFIX = "hsk/hsk"
    HSK_SUFFIX = ".json"

    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv("S3_BUCKET")

    def get_hsk_words(self, level: int) -> List[str]:
        key = f"{self.HSK_PREFIX}{level}{self.HSK_SUFFIX}"
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read().decode())
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise ValueError(f"HSK level {level} not found at key: {key}")
            logger.error("Error fetching HSK file for level %d: %s", level, e)
            raise
