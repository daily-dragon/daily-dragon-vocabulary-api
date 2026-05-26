def _level_progress(level: int, total: int = 10, mastered: int = 5, in_progress: int = 3, new: int = 2) -> dict:
    return {'level': level, 'total': total, 'mastered': mastered, 'in_progress': in_progress, 'new': new}


class TestGetHskProgress:
    def test_returns_all_7_levels(self, test_client, mock_settings_service, mock_hsk_service):
        mock_settings_service.get_settings.return_value = {'hsk_level': 2, 'placement_completed': True}
        mock_hsk_service.get_level_progress.side_effect = lambda user_id, lvl: _level_progress(lvl)

        response = test_client.get("/daily-dragon/hsk/progress")

        assert response.status_code == 200
        body = response.json()
        assert body['current_level'] == 2
        assert len(body['levels']) == 7
        assert body['levels'][0]['level'] == 1
        assert body['levels'][6]['level'] == 7

    def test_level_progress_fields_present(self, test_client, mock_settings_service, mock_hsk_service):
        mock_settings_service.get_settings.return_value = {'hsk_level': 1, 'placement_completed': False}
        mock_hsk_service.get_level_progress.side_effect = lambda user_id, lvl: _level_progress(lvl)

        response = test_client.get("/daily-dragon/hsk/progress")

        level = response.json()['levels'][0]
        assert set(level.keys()) == {'level', 'total', 'mastered', 'in_progress', 'new'}

    def test_uses_authenticated_user_id(self, test_client, mock_settings_service, mock_hsk_service):
        mock_settings_service.get_settings.return_value = {'hsk_level': 1, 'placement_completed': False}
        mock_hsk_service.get_level_progress.side_effect = lambda user_id, lvl: _level_progress(lvl)

        test_client.get("/daily-dragon/hsk/progress")

        mock_settings_service.get_settings.assert_called_once_with("test-sub")
        for call in mock_hsk_service.get_level_progress.call_args_list:
            assert call[0][0] == "test-sub"


class TestSubmitReviewsWithHskPromotion:
    def test_check_and_promote_called_after_reviews(self, test_client, mock_service, mock_hsk_service):
        mock_service.record_reviews.return_value = {
            'results': [{'word': '你好', 'success': True, 'next_review_date': 9999999, 'interval': 1}],
            'total_processed': 1,
            'successful': 1,
            'failed': 0,
        }
        mock_hsk_service.check_and_promote.return_value = False

        response = test_client.post(
            "/daily-dragon/vocabulary/reviews",
            json={"reviews": [{"word": "你好", "quality": 8}]},
        )

        assert response.status_code == 200
        mock_hsk_service.check_and_promote.assert_called_once_with("test-sub")

    def test_reviews_result_still_returned_when_no_promotion(self, test_client, mock_service, mock_hsk_service):
        mock_service.record_reviews.return_value = {
            'results': [],
            'total_processed': 1,
            'successful': 1,
            'failed': 0,
        }
        mock_hsk_service.check_and_promote.return_value = False

        response = test_client.post(
            "/daily-dragon/vocabulary/reviews",
            json={"reviews": [{"word": "你好", "quality": 5}]},
        )

        assert response.status_code == 200
        body = response.json()
        assert 'total_processed' in body
