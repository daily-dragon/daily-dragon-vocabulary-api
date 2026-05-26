def test_get_settings(test_client, mock_settings_service):
    mock_settings_service.get_settings.return_value = {"hsk_level": 1, "placement_completed": False}

    response = test_client.get("daily-dragon/settings")

    assert response.status_code == 200
    assert response.json() == {"hsk_level": 1, "placement_completed": False}
    mock_settings_service.get_settings.assert_called_once_with("test-sub")


def test_patch_settings_updates_hsk_level(test_client, mock_settings_service):
    mock_settings_service.update_settings.return_value = {"hsk_level": 2, "placement_completed": False}

    response = test_client.patch("daily-dragon/settings", json={"hsk_level": 2})

    assert response.status_code == 200
    assert response.json() == {"hsk_level": 2, "placement_completed": False}
    mock_settings_service.update_settings.assert_called_once_with(
        "test-sub", {"hsk_level": 2, "placement_completed": None}
    )


def test_patch_settings_marks_placement_completed(test_client, mock_settings_service):
    mock_settings_service.update_settings.return_value = {"hsk_level": 1, "placement_completed": True}

    response = test_client.patch("daily-dragon/settings", json={"placement_completed": True})

    assert response.status_code == 200
    assert response.json()["placement_completed"] is True


def test_patch_settings_empty_body(test_client, mock_settings_service):
    mock_settings_service.update_settings.return_value = {"hsk_level": 1, "placement_completed": False}

    response = test_client.patch("daily-dragon/settings", json={})

    assert response.status_code == 200
    mock_settings_service.update_settings.assert_called_once_with(
        "test-sub", {"hsk_level": None, "placement_completed": None}
    )
