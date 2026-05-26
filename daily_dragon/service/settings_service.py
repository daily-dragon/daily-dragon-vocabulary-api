import logging
from typing import Dict, Any

from fastapi import Depends

from daily_dragon.repository.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)


class SettingsService:

    def __init__(self, settings_repository: SettingsRepository = Depends()):
        self.settings_repository = settings_repository

    def get_settings(self, user_id: str) -> Dict:
        return self.settings_repository.get_settings(user_id)

    def update_settings(self, user_id: str, updates: Dict[str, Any]) -> Dict:
        settings = self.settings_repository.get_settings(user_id)
        for key, value in updates.items():
            if value is not None:
                settings[key] = value
        self.settings_repository.save_settings(user_id, settings)
        return settings
