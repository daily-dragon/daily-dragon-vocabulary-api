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


def test_get_due_words(test_client, mock_service):
    """Test GET /vocabulary/due endpoint returns due words."""
    mock_service.get_due_words.return_value = {
        'due_words': [
            {
                'word': 'word1',
                'metadata': {
                    'created_on': 123456,
                    'interval': 0,
                    'repetition': 0,
                    'ease_factor': 2.5,
                    'next_review_date': None,
                    'last_review_date': None,
                    'days_overdue': 5
                }
            }
        ],
        'returned': 1
    }

    response = test_client.get("daily-dragon/vocabulary/due")

    assert response.status_code == 200
    data = response.json()
    assert 'due_words' in data
    assert 'returned' in data
    assert len(data['due_words']) == 1
    mock_service.get_due_words.assert_called_once_with("test-sub")


def test_submit_reviews_all_valid(test_client, mock_service):
    """Test POST /vocabulary/reviews with all valid reviews."""
    mock_service.record_reviews.return_value = {
        'results': [
            {'word': 'word1', 'success': True, 'next_review_date': 123500, 'interval': 1},
            {'word': 'word2', 'success': True, 'next_review_date': 123600, 'interval': 1}
        ],
        'total_processed': 2,
        'successful': 2,
        'failed': 0
    }

    response = test_client.post("daily-dragon/vocabulary/reviews", json={
        "reviews": [
            {"word": "word1", "quality": 5},
            {"word": "word2", "quality": 4}
        ]
    })

    assert response.status_code == 200
    data = response.json()
    assert data['total_processed'] == 2
    assert data['successful'] == 2
    assert data['failed'] == 0
    assert len(data['results']) == 2


def test_submit_reviews_invalid_quality(test_client, mock_service):
    """Test POST /vocabulary/reviews with invalid quality rating."""
    response = test_client.post("daily-dragon/vocabulary/reviews", json={
        "reviews": [
            {"word": "word1", "quality": 6}  # Invalid quality
        ]
    })

    # Should return 422 validation error
    assert response.status_code == 422


def test_submit_reviews_empty_array(test_client, mock_service):
    """Test POST /vocabulary/reviews with empty reviews array."""
    response = test_client.post("daily-dragon/vocabulary/reviews", json={
        "reviews": []
    })

    # Should return 422 validation error
    assert response.status_code == 422


def test_submit_reviews_mixed_results(test_client, mock_service):
    """Test POST /vocabulary/reviews with mix of successful and failed reviews."""
    mock_service.record_reviews.return_value = {
        'results': [
            {'word': 'word1', 'success': True, 'next_review_date': 123500, 'interval': 1},
            {'word': 'nonexistent', 'success': False, 'error': 'Word not found in vocabulary'},
            {'word': 'word2', 'success': True, 'next_review_date': 123600, 'interval': 6}
        ],
        'total_processed': 3,
        'successful': 2,
        'failed': 1
    }

    response = test_client.post("daily-dragon/vocabulary/reviews", json={
        "reviews": [
            {"word": "word1", "quality": 5},
            {"word": "nonexistent", "quality": 4},
            {"word": "word2", "quality": 5}
        ]
    })

    assert response.status_code == 200
    data = response.json()
    assert data['total_processed'] == 3
    assert data['successful'] == 2
    assert data['failed'] == 1

    # Check individual results
    assert data['results'][0]['success'] is True
    assert data['results'][1]['success'] is False
    assert 'Word not found' in data['results'][1]['error']
    assert data['results'][2]['success'] is True


def test_submit_reviews_all_quality_ratings(test_client, mock_service):
    """Test POST /vocabulary/reviews with all valid quality ratings (0-5)."""
    mock_service.record_reviews.return_value = {
        'results': [
            {'word': f'word{i}', 'success': True, 'next_review_date': 123500 + i, 'interval': i}
            for i in range(6)
        ],
        'total_processed': 6,
        'successful': 6,
        'failed': 0
    }

    response = test_client.post("daily-dragon/vocabulary/reviews", json={
        "reviews": [
            {"word": f"word{i}", "quality": i}
            for i in range(6)
        ]
    })

    assert response.status_code == 200
    data = response.json()
    assert data['successful'] == 6
