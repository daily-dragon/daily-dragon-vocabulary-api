# CLAUDE.md

FastAPI vocabulary API deployed as AWS Lambda, storing per-user data in S3.

## Commands

```bash
pip install -r requirements.txt
uvicorn daily_dragon.daily_dragon_app:app --reload   # http://localhost:8000/docs
pytest --cov=.                                        # 80% coverage required, fails fast
pytest tests/test_daily_dragon_app.py::test_name     # single test
```

## Architecture

```
daily_dragon_app.py → service/vocabulary_service.py → repository/vocabulary_repository.py → S3
```

- **Auth**: Cognito via `cognito_auth.auth_required`; `auth.sub` is the user ID
- **Storage**: One JSON file per user in S3: `{user_id}_vocabulary.json`
- **Spaced repetition**: SM-2 algorithm in `service/spaced_repetition.py`; `SpacedRepetitionService` is stateless

## Vocabulary data structure

```json
{
  "word": {
    "created_on": 1234567890,
    "interval": 0,
    "repetition": 0,
    "ease_factor": 2.5,
    "next_review_date": null,
    "last_review_date": null
  }
}
```

Old files with `adoption` field are lazily migrated on read (`ensure_spaced_repetition_fields()`).

## Testing

Uses `dependency_overrides` to mock `VocabularyService` and `cognito_auth.auth_required`. See `tests/conftest.py`.

## Deployment

GitHub Actions deploys to Lambda on push to `main` (via Mangum adapter in `daily_dragon_handler.py`). Manual deployment not needed.

## Environment

`.env` file: `S3_BUCKET=<bucket-name>`

## HTTP examples

`requests/` — `vocabulary_local.http`, `vocabulary_aws.http`, `spaced_repetition_test_local.http`, `spaced_repetition_test_aws.http`