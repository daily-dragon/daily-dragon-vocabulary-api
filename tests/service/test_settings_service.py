import pytest
from unittest.mock import MagicMock

from daily_dragon.service.settings_service import SettingsService

user_id = "test-user"


@pytest.fixture
def mock_repository():
    return MagicMock()


@pytest.fixture
def settings_service(mock_repository):
    return SettingsService(settings_repository=mock_repository)


def test_get_settings_delegates(settings_service, mock_repository):
    mock_repository.get_settings.return_value = {"hsk_level": 1, "placement_completed": False}

    result = settings_service.get_settings(user_id)

    assert result == {"hsk_level": 1, "placement_completed": False}
    mock_repository.get_settings.assert_called_once_with(user_id)


def test_update_settings_merges_non_none_values(settings_service, mock_repository):
    mock_repository.get_settings.return_value = {"hsk_level": 1, "placement_completed": False}

    result = settings_service.update_settings(user_id, {"hsk_level": 2, "placement_completed": None})

    assert result["hsk_level"] == 2
    assert result["placement_completed"] is False
    mock_repository.save_settings.assert_called_once_with(user_id, {"hsk_level": 2, "placement_completed": False})


def test_update_settings_all_none_is_noop(settings_service, mock_repository):
    mock_repository.get_settings.return_value = {"hsk_level": 1, "placement_completed": False}

    result = settings_service.update_settings(user_id, {"hsk_level": None, "placement_completed": None})

    assert result == {"hsk_level": 1, "placement_completed": False}
    mock_repository.save_settings.assert_called_once_with(user_id, {"hsk_level": 1, "placement_completed": False})


def test_update_settings_both_fields(settings_service, mock_repository):
    mock_repository.get_settings.return_value = {"hsk_level": 1, "placement_completed": False}

    result = settings_service.update_settings(user_id, {"hsk_level": 3, "placement_completed": True})

    assert result == {"hsk_level": 3, "placement_completed": True}
