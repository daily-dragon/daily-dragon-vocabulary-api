from daily_dragon.exceptions import WordAlreadyExistsError


def test_add_word_success(test_client, mock_service):
    mock_service.add_word.return_value = None

    response = test_client.post("daily-dragon/vocabulary", json={"word": "测试"})

    assert response.status_code == 201
    assert response.json() == {"message": "Word 测试 added to vocabulary"}
    mock_service.add_word.assert_called_once_with("test-sub", "测试")


def test_add_word_already_exists(test_client, mock_service):
    mock_service.add_word.side_effect = WordAlreadyExistsError()

    response = test_client.post("daily-dragon/vocabulary", json={"word": "重复"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Word 重复 already exists"}


def test_get_vocabulary(test_client, mock_service):
    mock_service.get_vocabulary.return_value = {
        "你好": {"adoption": 0, "created_on": 1234567890}
    }

    response = test_client.get("daily-dragon/vocabulary")

    assert response.status_code == 200
    assert "你好" in response.json()


def test_delete_word(test_client, mock_service):
    mock_service.delete_word.return_value = None

    response = test_client.delete("daily-dragon/vocabulary/你好")

    assert response.status_code == 200
    mock_service.delete_word.assert_called_once_with("test-sub", "你好")
